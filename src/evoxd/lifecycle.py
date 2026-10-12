"""Lifecycle der Wegwerf-VMs: Start, Beenden = Vernichten, Abgleich/Recovery (R30, R31, T3).

Namensschema (ENTSCHEIDUNGEN.md §20.20): TEMPLATE-<System> = Vorlage,
DISPOSABLE-<Zweck>-NN = Wegwerf-VM; das Template steht in den Metadaten.
"""
import os
import re
import secrets
import threading
import time
import uuid as uuidlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import capacity, config, domxml, storage
from .errors import Cancelled, CapacityError, EvoxError, LockBusy, NotOwned, SpaceError
from .lock import exclusive
from .ownership import Owner, classify, is_own_overlay_path, is_own_secret_usage, require_owned


@dataclass
class StartResult:
    name: str
    net: bool
    warnings: list = field(default_factory=list)


def template_name(name: str) -> str:
    if not re.fullmatch(config.TEMPLATE_NAME_RE, name or ""):
        raise EvoxError(f"Invalid template name '{name}' (expected TEMPLATE-<SYSTEM>).")
    return name


def purpose_name(purpose: str) -> str:
    p = (purpose or "").strip().upper()
    if not re.fullmatch(config.PURPOSE_RE, p):
        raise EvoxError("Purpose must be 1–16 letters or digits (e.g. EMAIL, WEB).")
    return p


def is_backup(name: str) -> bool:
    """Sicherungskopie des Templates (Name enthält -BACKUP); wird rot angezeigt."""
    return "-BACKUP" in (name or "").upper()


def is_vault(name: str) -> bool:
    return (name or "").startswith(config.VAULT_PREFIX)


# Zustände einer Vault (hv.vault_state); nur "shutoff" erlaubt Make template
VAULT_STATE_TEXT = {"shutoff": "shut off", "running": "running", "paused": "paused", "saved": "saved",
                    "other": "busy"}
PROGRESS_POLL_S = 0.5
SPACE_MARGIN_MIN = 64 * 2**20       # qcow2-Metadaten: mindestens 64 MiB …
SPACE_MARGIN_DIV = 100              # … bzw. 1 % der virtuellen Größe


def space_needed(capacity_b: int, allocation_b: int) -> int:
    """Konservativ: die größere von virtueller und belegter Größe plus Rand für qcow2-Metadaten.

    Die Kopie (qemu-img convert durch libvirt) ist nie größer als die virtuelle Größe plus Metadaten."""
    return max(capacity_b or 0, allocation_b or 0) + max(SPACE_MARGIN_MIN, (capacity_b or 0) // SPACE_MARGIN_DIV)


def suggest_template_name(vault: str, taken) -> str:
    """VAULT-<Zweck> → TEMPLATE-<Zweck>; belegt → -2, -3, …; unerlaubte Zeichen → '-'."""
    purpose = re.sub(r"[^A-Za-z0-9_.-]", "-", vault[len(config.VAULT_PREFIX):] if is_vault(vault) else vault)
    base = config.TEMPLATE_PREFIX + (purpose[:36] or "VAULT")
    taken = {t.upper() for t in taken}
    if base.upper() not in taken:
        return base
    for i in range(2, 1000):
        n = f"{base}-{i}"
        if n.upper() not in taken:
            return n
    raise EvoxError("No free template name found.")


def random_mac() -> str:
    b = secrets.token_bytes(3)
    return "52:54:00:%02x:%02x:%02x" % tuple(b)


class Evox:
    def __init__(self, settings, hv, registry,
                 net_check: Optional[Callable[[], tuple]] = None,
                 meminfo: Callable[[], dict] = capacity.read_meminfo,
                 require_apparmor: bool = True):
        self.s = settings
        self.hv = hv
        self.reg = registry
        self.net_check = net_check or (lambda: (False, "network check not configured"))
        self.meminfo = meminfo
        self.require_apparmor = require_apparmor
        # Aufruf mit base_id, sobald eine Wegwerf-VM vernichtet wurde (GUI: Prüfung nach dem Beenden).
        # Läuft im Thread des Vorgangs und unter der Sperre: nur kurz, nichts Blockierendes.
        self.on_temp_destroyed: Optional[Callable[[int], None]] = None

    def _lock(self):
        return exclusive(self.s.lock_path, self.s.lock_timeout_s)

    # ------------------------------------------------------------ Template
    def _template_source(self, name: str, xml: str) -> tuple:
        """Prüft eine Domain TEMPLATE-* als Importquelle; gibt (Pfad der einzigen Platte, efi) zurück."""
        if classify(name, xml) is Owner.EVOX:
            raise EvoxError("A disposable VM cannot be a template.")
        root = ET.fromstring(xml)
        disks = [d for d in root.findall("devices/disk") if d.get("device") == "disk"]
        if len(disks) != 1 or disks[0].find("source") is None or not disks[0].find("source").get("file"):
            raise EvoxError("Template must have exactly one file-backed disk.")
        os_el = root.find("os")
        efi = os_el is not None and (os_el.get("firmware") == "efi" or os_el.find("loader") is not None)
        return disks[0].find("source").get("file"), efi

    def template_candidates(self) -> list:
        """Nur lesend: alle Domains TEMPLATE-* (nie VAULT-*) mit Zustand, Größe und Hinderungsgrund.

        Gleiche Prüfungen wie import_template(); `problem` leer = importierbar."""
        out = []
        for n, _u in sorted(self.hv.list_domains()):
            if not re.fullmatch(config.TEMPLATE_NAME_RE, n):
                continue
            xml = self.hv.domain_xml(n)
            state = self.hv.domain_state(n)
            if xml is None or state is None:
                continue
            c = {"name": n, "state": state, "size": None, "alloc": None, "problem": "",
                 "backup": is_backup(n)}
            try:
                path, _efi = self._template_source(n, xml)
                c["size"], c["alloc"] = self.hv.vol_size(path)
            except EvoxError as e:
                c["problem"] = str(e)
            except Exception as e:  # noqa: BLE001 – z. B. Platte in keinem libvirt-Pool
                c["problem"] = f"disk not readable via libvirt ({type(e).__name__})"
            if not c["problem"] and state != "shutoff":
                c["problem"] = "running – shut it down first"
            out.append(c)
        return out

    def import_template(self, src_domain: str, progress: Optional[Callable[[str], None]] = None) -> int:
        """Geschützte, flache Kopie der vom Benutzer gepflegten Domain TEMPLATE-* (R7, R9, T4).

        Nur TEMPLATE-* wird gelesen; VAULT-* und alles andere wird abgelehnt (R29).
        progress(phase) meldet "copy" und "checksum" (CLI und GUI benutzen diese Funktion).
        """
        name = template_name(src_domain)
        step = progress or (lambda _p: None)
        with self._lock():
            xml = self.hv.domain_xml(src_domain)
            if xml is None:
                raise EvoxError(f"Domain '{src_domain}' not found.")
            src_path, efi = self._template_source(src_domain, xml)
            if self.hv.domain_state(src_domain) != "shutoff":
                raise EvoxError(f"'{src_domain}' must be shut off.")
            root = ET.fromstring(xml)
            version = self.reg.next_base_version(name)
            vol_name = f"{name}-v{version}.qcow2"
            step("copy")
            self.reg.add_pending(vol_name, name, version, src_domain)
            try:
                path = self.hv.clone_vol(storage.base_vol_xml(vol_name), src_path)
                if self.hv.domain_state(src_domain) != "shutoff":
                    raise EvoxError("Source domain was started during the copy – copy discarded.")
                storage.check_base_vol(self.hv.vol_xml(vol_name))
                step("checksum")
                digest = self.hv.vol_sha256(vol_name)
            except BaseException:
                self._discard_copy(vol_name)
                raise
            src_uuid = root.findtext("uuid")
            bid = self.reg.add_base(name, version, vol_name, path, digest, src_uuid, "efi" if efi else "bios")
            self.reg.drop_pending(vol_name)
            return bid

    def _discard_copy(self, vol_name: str) -> None:
        """Unfertige Kopie restlos löschen; der pending-Eintrag bleibt, falls das Löschen scheitert
        (dann bietet der nächste Start das Aufräumen an)."""
        self.hv.delete_vol(vol_name, pool=config.TEMPLATE_POOL)
        self.reg.drop_pending(vol_name)

    # ------------------------------------------------------------ Vaults (nur lesen, R29)
    def _vault_disk(self, name: str, xml: str) -> dict:
        """Prüft die einzige Platte einer Vault (nur lesend); EvoxError mit Grund, wenn ungeeignet."""
        root = ET.fromstring(xml)
        disks = [d for d in root.findall("devices/disk") if d.get("device") == "disk"]
        if not disks:
            raise EvoxError("no disk")
        if len(disks) > 1:
            raise EvoxError(f"{len(disks)} disks – only VMs with exactly one disk are supported")
        d = disks[0]
        src = d.find("source")
        path = src.get("file") if src is not None else None
        if d.get("type") != "file" or not path:
            raise EvoxError("disk is not a file")
        if d.find("backingStore/source") is not None:
            raise EvoxError("disk has a backing file (snapshot chain) – not supported")
        drv = d.find("driver")
        fmt = drv.get("type") if drv is not None else None
        try:
            vi = self.hv.vol_info(path)
        except Exception as e:  # noqa: BLE001 – z. B. Platte in keinem libvirt-Pool
            raise EvoxError(f"disk not readable via libvirt ({type(e).__name__})") from None
        fmt = vi.get("format") or fmt
        if fmt not in ("qcow2", "raw"):
            raise EvoxError(f"disk format '{fmt}' – only qcow2 or raw")
        if vi.get("backing"):
            raise EvoxError("disk has a backing file (snapshot chain) – not supported")
        os_el = root.find("os")
        efi = os_el is not None and (os_el.get("firmware") == "efi" or os_el.find("loader") is not None)
        return {"path": path, "format": fmt, "capacity": vi["capacity"], "allocation": vi["allocation"],
                "efi": efi, "uuid": root.findtext("uuid")}

    def vault_list(self) -> list:
        """Nur lesend: alle Domains VAULT-* mit Zustand, RAM, CPUs, Platte, Herkunft und Hinderungsgrund.

        `problem` leer = Make template möglich. EVOX startet, ändert oder löscht nie eine Vault (R29)."""
        made = {}
        for o in self.reg.origins():
            made.setdefault(o.vault, []).append(o)
        names = {b.vol_name: f"{b.name} v{b.version}" for b in self.reg.bases()}
        out = []
        for n, _u in sorted(self.hv.list_domains()):
            if not is_vault(n):
                continue
            xml = self.hv.domain_xml(n)
            state = self.hv.vault_state(n)
            if xml is None or state is None:
                continue
            v = {"name": n, "state": state, "state_text": VAULT_STATE_TEXT.get(state, state),
                 **domxml.resources(xml), "size": None, "alloc": None, "format": None, "problem": "",
                 "templates": [names[o.vol_name] for o in made.get(n, []) if o.vol_name in names]}
            try:
                disk = self._vault_disk(n, xml)
                v.update(size=disk["capacity"], alloc=disk["allocation"], format=disk["format"])
            except EvoxError as e:
                v["problem"] = str(e)
            if not v["problem"] and state != "shutoff":
                v["problem"] = f"{v['state_text']} – shut it down first"
            out.append(v)
        return out

    def taken_template_names(self) -> set:
        """Belegte Namen: alle Domains, alle Template-Kopien (Registry, auch unfertige) und Dateien im Template-Pool."""
        taken = {n for n, _u in self.hv.list_domains()}
        taken |= {b.name for b in self.reg.bases(include_retired=True)}
        taken |= {p.name for p in self.reg.pending()}
        try:
            for vname, _p in self.hv.list_vols(config.TEMPLATE_POOL):
                m = re.fullmatch(r"(.+)-v[0-9]+\.qcow2", vname)
                taken.add(m.group(1) if m else vname)
        except Exception:  # noqa: BLE001 – Pool nicht lesbar: Registry/Domains reichen
            pass
        return taken

    def suggest_name(self, vault: str) -> str:
        return suggest_template_name(vault, self.taken_template_names())

    def check_new_name(self, name: str) -> str:
        """Neuer Template-Name: TEMPLATE-…, erlaubte Zeichen, nicht belegt (Domains, Templates, Dateien)."""
        name = (name or "").strip()
        if not name.startswith(config.TEMPLATE_PREFIX):
            raise EvoxError("The name must start with TEMPLATE-.")
        if not re.fullmatch(config.TEMPLATE_NAME_RE, name):
            raise EvoxError("Allowed after TEMPLATE-: 1–40 letters, digits, '_', '.', '-'.")
        if name.upper() in {t.upper() for t in self.taken_template_names()}:
            raise EvoxError(f"'{name}' is already used (domain, template or file).")
        return name

    def template_space(self, need_b: int) -> dict:
        """Platz in /srv/evoxd/templates: benötigt, frei, frei nach Reserve, ok."""
        free = self.hv.pool_free(config.TEMPLATE_POOL)
        reserve = self.s.template_reserve_mib * 2**20
        after = free - reserve
        return {"need": need_b, "free": free, "reserve": reserve, "after": after, "ok": need_b <= after}

    def make_template_plan(self, vault: str) -> dict:
        """Nur lesend: alle Vorabprüfungen für Make template; EvoxError/SpaceError mit Grund."""
        if not is_vault(vault):
            raise NotOwned(f"'{vault}' is not a VAULT-* VM.")
        xml = self.hv.domain_xml(vault)
        if xml is None:
            raise EvoxError(f"VM '{vault}' not found.")
        state = self.hv.vault_state(vault)
        if state != "shutoff":
            raise EvoxError(f"{vault} is {VAULT_STATE_TEXT.get(state, state)} – shut it down first.")
        disk = self._vault_disk(vault, xml)
        sp = self.template_space(space_needed(disk["capacity"], disk["allocation"]))
        return {"vault": vault, "disk": disk, "space": sp, "suggested": self.suggest_name(vault)}

    def make_template(self, vault: str, new_name: str,
                      progress: Optional[Callable[[str, Optional[float]], None]] = None,
                      cancel: Optional[threading.Event] = None) -> int:
        """Geschützte Kopie (root 0444) der Platte einer AUSGESCHALTETEN Vault als neues TEMPLATE-….

        Die Vault wird nur gelesen (XML, Plattenpfad, Kopierquelle); sie wird nie gestartet, geändert,
        gesperrt oder gelöscht (R29). Ablauf: Prüfen → Version reservieren (pending) → Zustand erneut
        prüfen → Kopie durch libvirt (Pool evoxd-templates) → Zustand erneut prüfen → Rechte/flach,
        Format, Größe, SHA-256 → in einem Schritt eintragen. Fehler/Abbruch → Kopie restlos löschen.
        progress(phase, anteil) meldet "check", "copy" (Anteil 0..1 oder None), "verify", "checksum".
        cancel: Event; libvirt kann die Kopie nicht unterbrechen → nach dem Kopierschritt verworfen."""
        step = progress or (lambda _p, _f=None: None)
        cancel = cancel or threading.Event()
        with self._lock():
            step("check", None)
            plan = self.make_template_plan(vault)
            if not plan["space"]["ok"]:
                sp = plan["space"]
                raise SpaceError(f"Not enough space in {config.TEMPLATE_PATH}: needed "
                                 f"{capacity.fmt_bytes_gib(sp['need'])}, free {capacity.fmt_bytes_gib(sp['free'])} "
                                 f"(after reserve {capacity.fmt_bytes_gib(max(0, sp['after']))}).")
            name = self.check_new_name(new_name)
            disk = plan["disk"]
            version = self.reg.next_base_version(name)
            vol_name = f"{name}-v{version}.qcow2"
            self.reg.add_pending(vol_name, name, version, vault)
            try:
                if cancel.is_set():
                    raise Cancelled("Make template cancelled.")
                if self.hv.vault_state(vault) != "shutoff":      # kurz vor dem Kopieren erneut
                    raise EvoxError(f"{vault} was started – nothing copied.")
                step("copy", 0.0)
                path = self._clone_with_progress(vol_name, disk, step)
                if cancel.is_set():
                    raise Cancelled("Make template cancelled – partial copy deleted.")
                if self.hv.vault_state(vault) != "shutoff":
                    raise EvoxError(f"{vault} was started during the copy – copy discarded.")
                step("verify", None)
                vx = self.hv.vol_xml(vol_name)
                storage.check_base_vol(vx)
                vroot = ET.fromstring(vx)
                fmt = vroot.find("target/format")
                if fmt is None or fmt.get("type") != "qcow2":
                    raise EvoxError("Copy check failed: copy is not qcow2.")
                if int(vroot.findtext("capacity") or 0) != int(disk["capacity"]):
                    raise EvoxError("Copy check failed: disk size differs from the original.")
                if cancel.is_set():
                    raise Cancelled("Make template cancelled – partial copy deleted.")
                step("checksum", None)
                digest = self.hv.vol_sha256(vol_name)
                if cancel.is_set():
                    raise Cancelled("Make template cancelled – copy deleted.")
                size = self.hv.vol_alloc(vol_name)
            except BaseException:
                self._discard_copy(vol_name)
                raise
            return self.reg.commit_template(name, version, vol_name, path, digest, disk["uuid"] or "",
                                            "efi" if disk["efi"] else "bios", vault, size)

    def _clone_with_progress(self, vol_name, disk, step) -> str:
        """libvirt kopiert (blockierend); ein Nebenfaden meldet den belegten Platz als Anteil (geschätzt)."""
        total = max(1, disk["allocation"] or disk["capacity"] or 1)
        done = threading.Event()

        def poll():
            while not done.wait(PROGRESS_POLL_S):
                try:
                    a = self.hv.vol_alloc(vol_name)
                except Exception:  # noqa: BLE001 – nur Anzeige
                    a = None
                step("copy", None if a is None else min(0.99, a / total))
        t = threading.Thread(target=poll, daemon=True)
        t.start()
        try:
            return self.hv.clone_vol(storage.base_vol_xml(vol_name), disk["path"])
        finally:
            done.set()
            t.join()

    # ------------------------------------------------------------ Unfertige Kopien (nach Absturz)
    def orphan_copies(self) -> list:
        """Unfertige Kopien früherer Läufe (pending in der Registry); [] solange ein EVOX-Vorgang läuft.

        Nur eigene, in der Registry vermerkte Kopien – fremde Dateien werden nie angeboten."""
        try:
            with exclusive(self.s.lock_path, 0.2):
                out = []
                for p in self.reg.pending():
                    exists = self.hv.find_vol(p.vol_name, config.TEMPLATE_POOL) is not None
                    out.append({"vol_name": p.vol_name, "name": p.name, "version": p.version,
                                "vault": p.vault, "started": p.started, "exists": exists})
                return out
        except LockBusy:
            return []

    def remove_orphans(self) -> list:
        """Alle unfertigen Kopien löschen (nach Bestätigung durch den Benutzer); nur pending-Einträge."""
        removed = []
        with self._lock():
            for p in self.reg.pending():
                if (not re.fullmatch(re.escape(p.name) + r"-v[0-9]+\.qcow2", p.vol_name)
                        or not re.fullmatch(config.TEMPLATE_NAME_RE, p.name)
                        or any(b.vol_name == p.vol_name for b in self.reg.bases(include_retired=True))):
                    continue
                self._discard_copy(p.vol_name)
                removed.append(p.vol_name)
        return removed

    def template_overview(self) -> list:
        """Alle Template-Kopien mit Alter (Tage), belegtem Platz, Zustand und Anzahl aktiver Wegwerf-VMs."""
        now = time.time()
        out = []
        for b in self.reg.bases():
            try:
                size = self.hv.vol_size(b.vol_path)[1]
            except Exception:  # noqa: BLE001 – nur Anzeige
                size = None
            o = self.reg.origin(b.vol_name)
            out.append({"id": b.id, "name": b.name, "version": b.version, "firmware": b.firmware,
                        "created": b.created, "origin": o.vault if o else None, "sha256": b.sha256,
                        "age_days": (now - b.created) / 86400, "in_use": self.reg.temps_using_base(b.id),
                        "size": size, "damaged": bool(b.damaged), "backup": is_backup(b.name)})
        return out

    def find_base(self, name: str, version: Optional[int] = None):
        """Kopie NAME vN; ohne Version die neueste."""
        name = template_name(name)
        if version is None:
            b = self.reg.latest_base(name)
        else:
            b = next((x for x in self.reg.bases() if x.name == name and x.version == int(version)), None)
        if b is None:
            raise EvoxError(f"Unknown template '{name}'" + ("" if version is None else f" version {version}") + ".")
        return b

    def verify_template(self, name: str, version: Optional[int] = None) -> bool:
        return self.verify_base(self.find_base(name, version).id)

    def verify_base(self, base_id: int) -> bool:
        """SHA-256 der Kopie gegen den Wert beim Import. Abweichung → Kopie 'damaged' (keine neuen Starts).

        Deckt ab: Veränderung der Datei nach dem Import (Plattenfehler, Manipulation auf dem Host).
        Deckt nicht ab: Schadsoftware, die schon vor dem Import im Template war, und alles, was nur
        im Overlay einer Wegwerf-VM geschieht (das Overlay wird vernichtet, die Kopie ist schreibgeschützt).
        """
        b = self.reg.base(base_id)
        if b is None:
            raise EvoxError("This template copy no longer exists.")
        storage.check_base_vol(self.hv.vol_xml(b.vol_name))
        ok = self.hv.vol_sha256(b.vol_name) == b.sha256
        if not ok:
            self.reg.set_damaged(b.id)
        return ok

    # ------------------------------------------------------------ Template entfernen
    def _own_template_copy(self, b) -> Optional[str]:
        """Eigentums- und Pfadprüfung einer Kopie; gibt das Volume-XML zurück (None = Datei fehlt schon).

        Nur Registry-Einträge TEMPLATE-* mit Volume TEMPLATE-…-vN.qcow2 direkt unter
        /srv/evoxd/templates im Pool evoxd-templates; nie VAULT-*, nie Domains."""
        expected = f"{config.TEMPLATE_PATH}/{b.vol_name}"
        if (not re.fullmatch(config.TEMPLATE_NAME_RE, b.name) or b.name.startswith(config.VAULT_PREFIX)
                or not re.fullmatch(re.escape(b.name) + r"-v[0-9]+\.qcow2", b.vol_name)
                or b.vol_path != expected):
            raise NotOwned(f"'{b.vol_path}' is not an EVOX template copy – removal refused.")
        xml = self.hv.find_vol(b.vol_name, config.TEMPLATE_POOL)
        if xml is not None and ET.fromstring(xml).findtext("target/path") != expected:
            raise NotOwned(f"Volume '{b.vol_name}' is not at {expected} – removal refused.")
        return xml

    def template_users(self, b) -> list:
        """Wer die Kopie als Backing benutzt: Registry (nicht beendete Wegwerf-VMs), libvirt (jede Domain,
        die den Pfad irgendwo im XML nennt) und Overlays im Overlay-Pool."""
        users = {t.name for t in self.reg.active_temps() if t.base_id == b.id}
        for n, _u in self.hv.list_domains():
            x = self.hv.domain_xml(n)
            if x and any(b.vol_path in (el.get("file"), (el.text or "").strip()) for el in ET.fromstring(x).iter()):
                users.add(n)
        if not self.hv.pool_ok():
            raise EvoxError("EVOX storage pools are not active – cannot check for users.")
        for vname, _p in self.hv.list_vols():
            vx = self.hv.find_vol(vname, config.OVERLAY_POOL)
            if vx and ET.fromstring(vx).findtext("backingStore/path") == b.vol_path:
                users.add(vname)
        return sorted(users)

    def remove_plan(self, name: str, version: Optional[int] = None, older: bool = False) -> list:
        """Nur lesend: welche Kopien remove_template() entfernen würde (nach Version sortiert)."""
        name = template_name(name)
        copies = [b for b in self.reg.bases() if b.name == name]
        if not copies:
            raise EvoxError(f"Unknown template '{name}'.")
        if older:
            if version is not None:
                raise EvoxError("Give either a version or 'older', not both.")
            if len(copies) < 2:
                raise EvoxError(f"{name} has no older versions.")
            return copies[:-1]
        if version is None:
            if len(copies) > 1:
                raise EvoxError(f"{name} has {len(copies)} versions "
                                f"({', '.join('v%d' % b.version for b in copies)}) – give --version N or --older.")
            return copies
        return [self.find_base(name, version)]

    def remove_template(self, name: str, version: Optional[int] = None, older: bool = False) -> list:
        """Template-Kopie(n) im Pool evoxd-templates löschen und Registry-Einträge entfernen.

        Alles oder nichts: verweigert, wenn eine Kopie fremd aussieht oder noch benutzt wird
        (Registry UND libvirt). CLI `evoxd template-remove` und GUI benutzen diese Funktion."""
        with self._lock():
            targets = self.remove_plan(name, version, older)
            checked = []
            for b in targets:
                vol = self._own_template_copy(b)
                users = self.template_users(b)
                if users:
                    raise EvoxError(f"{b.name} v{b.version} is in use by {', '.join(users)} – stop it first.")
                checked.append((b, vol))
            for b, vol in checked:
                if vol is not None:
                    self.hv.delete_vol(b.vol_name, pool=config.TEMPLATE_POOL)
                self.reg.remove_base(b.id)
            return targets

    # ------------------------------------------------------------ Start
    def host_cpus(self) -> int:
        return os.cpu_count() or 1

    def check_resources(self, memory_mib: int, vcpus: int):
        """Grenzen und Kapazität für die gewählten Werte; wirft EvoxError/CapacityError."""
        if not config.ram_on_grid(memory_mib):                       # 0.7.3: zusätzlich 256-MiB-Raster
            raise EvoxError(f"RAM must be between {config.MIN_MEMORY_MIB} and {config.MAX_MEMORY_MIB} MiB "
                            f"in steps of {config.RAM_STEP_MIB} MiB.")
        if not 1 <= vcpus <= min(config.MAX_VCPUS, self.host_cpus()):
            raise EvoxError(f"CPUs must be between 1 and {min(config.MAX_VCPUS, self.host_cpus())}.")
        cap = capacity.assess(self.meminfo(), memory_mib, self.s.host_reserve_mib)
        if cap.level == "red":
            raise CapacityError(
                f"Not enough free memory for this RAM size (available {capacity.fmt_gib(cap.avail_mib)}, "
                f"needed {capacity.fmt_gib(cap.need_mib)}, host reserve {capacity.fmt_gib(cap.reserve_mib)}). "
                "Close a disposable VM or choose less RAM.")
        return cap

    def _next_name(self, purpose: str) -> str:
        used = {n for n, _u in self.hv.list_domains()} | {t.name for t in self.reg.active_temps()}
        for i in range(1, config.MAX_TEMP_NO + 1):
            n = f"{config.TEMP_PREFIX}{purpose}-{i:02d}"
            if n not in used:
                return n
        raise EvoxError(f"No free name for purpose {purpose} (01–{config.MAX_TEMP_NO} in use).")

    def start(self, template: str, purpose: str = config.DEFAULT_PURPOSE, want_net: bool = True,
              memory_mib: Optional[int] = None, vcpus: Optional[int] = None) -> StartResult:
        purpose = purpose_name(purpose)
        memory_mib = self.s.vm_memory_mib if memory_mib is None else int(memory_mib)
        vcpus = self.s.vm_vcpus if vcpus is None else int(vcpus)
        with self._lock():
            self._reconcile_locked()
            base = self.reg.latest_base(template_name(template))
            if base is None:
                raise EvoxError(f"Unknown template '{template}'.")
            if base.damaged:
                raise EvoxError(f"{base.name} v{base.version} is marked DAMAGED (checksum mismatch) – "
                                "import the template again or remove this copy.")
            cap = self.check_resources(memory_mib, vcpus)
            storage.check_base_vol(self.hv.vol_xml(base.vol_name))

            warnings = []
            if cap.level == "yellow":
                warnings.append(f"Memory tight: only {capacity.fmt_gib(cap.left_after_mib)} left for the host "
                                f"(reserve {capacity.fmt_gib(cap.reserve_mib)}).")
            net = want_net
            if want_net:
                ok, reason = self.net_check()
                if not ok:
                    net = False
                    warnings.append(f"Network lock not confirmed ({reason}) – starting WITHOUT network.")

            name = self._next_name(purpose)
            tag = secrets.token_hex(4)
            dom_uuid = str(uuidlib.uuid4())
            sec_uuid = str(uuidlib.uuid4())
            vol_name = f"{name}-{tag}.qcow2"
            overlay_path = f"{config.OVERLAY_PATH}/{vol_name}"
            mac = random_mac() if net else None
            self.reg.add_temp(name, dom_uuid, base.id, vol_name, sec_uuid, "net" if net else "none", mac)
            try:
                self.hv.define_secret(storage.secret_xml(sec_uuid, overlay_path),
                                      storage.new_passphrase())
                overlay_path = self.hv.create_vol(storage.overlay_vol_xml(
                    vol_name, self.hv.vol_capacity(base.vol_path), base.vol_path, sec_uuid))
                spec = domxml.TempSpec(name=name, uuid=dom_uuid, overlay_path=overlay_path,
                                       base_path=base.vol_path, secret_uuid=sec_uuid,
                                       template=base.name, purpose=purpose,
                                       memory_mib=memory_mib, vcpus=vcpus,
                                       net=net, mac=mac, firmware=base.firmware)
                self.hv.create_domain(domxml.build(spec))
                live = self.hv.domain_xml(name)
                if live is None:
                    raise EvoxError("Disposable VM not found after start.")
                domxml.validate_live(live, expect_net=net, require_apparmor=self.require_apparmor)
                # Schlüssel nur noch im QEMU-Prozess (T5, R31)
                self.hv.undefine_secret(sec_uuid)
                self.reg.set_state(name, "running")
            except BaseException:
                self._destroy_resources(name, vol_name, sec_uuid)
                raise
            try:
                self.s.save_last_start(memory_mib, vcpus, purpose)
            except OSError:
                warnings.append("Could not save the last used values.")
            return StartResult(name, net, warnings)

    # ------------------------------------------------------------ Beenden
    def stop(self, name: str) -> None:
        with self._lock():
            xml = self.hv.domain_xml(name)
            if xml is not None:
                require_owned(name, xml, "destroy")
            t = self.reg.temp(name)
            if t is None and xml is None:
                raise EvoxError(f"Unknown disposable VM '{name}'.")
            if t is not None:
                self.reg.set_state(name, "destroying")
                self._destroy_resources(name, t.overlay_name, t.secret_uuid)
            else:
                self._destroy_own_domain(name, xml)

    def _destroy_resources(self, name, vol_name, sec_uuid):
        xml = self.hv.domain_xml(name)
        if xml is not None:
            require_owned(name, xml, "destroy")
            self.hv.destroy_domain(name)
        self.hv.undefine_secret(sec_uuid)
        self.hv.delete_vol(vol_name)
        t = self.reg.temp(name)
        if t is not None:
            self.reg.set_state(name, "gone")
            if self.on_temp_destroyed is not None:
                try:
                    self.on_temp_destroyed(t.base_id)
                except Exception:  # noqa: BLE001 – Vernichten darf daran nicht scheitern
                    pass

    def _destroy_own_domain(self, name, xml):
        require_owned(name, xml, "destroy")
        self.hv.destroy_domain(name)
        src = ET.fromstring(xml).find("devices/disk/source")
        path = src.get("file", "") if src is not None else ""
        if is_own_overlay_path(path):
            self.hv.delete_vol(os.path.basename(path))

    # ------------------------------------------------------------ Abgleich
    def reconcile(self) -> list:
        with self._lock():
            return self._reconcile_locked()

    def _reconcile_locked(self) -> list:
        actions = []
        own = {}
        for n, _u in self.hv.list_domains():
            x = self.hv.domain_xml(n)
            if x is not None and classify(n, x) is Owner.EVOX:
                own[n] = x
        keep_vols, keep_secrets = set(), set()
        for t in self.reg.active_temps():
            running = t.name in own and self.hv.domain_state(t.name) == "running"
            if t.state == "running" and running:
                keep_vols.add(t.overlay_name)
                keep_secrets.add(t.secret_uuid)
                continue
            self._destroy_resources(t.name, t.overlay_name, t.secret_uuid)
            own.pop(t.name, None)
            actions.append(f"{t.name}: leftovers destroyed (state '{t.state}', domain {'present' if running else 'gone'})")
        known = {t.name for t in self.reg.active_temps()}
        for n, x in own.items():
            if n not in known:
                self._destroy_own_domain(n, x)
                actions.append(f"{n}: EVOX domain without registry entry destroyed")
        if self.hv.pool_ok():
            for vname, _p in self.hv.list_vols():
                if vname.startswith(config.TEMP_PREFIX) and vname not in keep_vols:
                    self.hv.delete_vol(vname)
                    actions.append(f"{vname}: orphaned overlay deleted")
        for su, usage in self.hv.list_secrets():
            if is_own_secret_usage(usage) and su not in keep_secrets:
                self.hv.undefine_secret(su)
                actions.append(f"secret {su[:8]}: orphaned, removed")
        return actions

    # ------------------------------------------------------------ Anzeige
    def list_temps(self) -> list:
        out = []
        for t in self.reg.active_temps():
            b = self.reg.base(t.base_id)
            out.append({"name": t.name, "state": self.hv.domain_state(t.name) or "gone",
                        "net": t.net_mode, "mac": t.mac, "base_id": t.base_id,
                        "template": f"{b.name} v{b.version}" if b else "?", "created": t.created,
                        **domxml.resources(self.hv.domain_xml(t.name))})
        return out
