"""Namensraum, Pfade und Grenzwerte (T6: getrennt vom Altbestand; Namensschema ENTSCHEIDUNGEN.md §20.20)."""
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

PREFIX = "evoxd"
META_URI = "https://evox.invalid/evoxd/1"

# Namensschema (§20.20). Eigentum erkennt EVOX an den Metadaten, nicht am Namen.
TEMP_PREFIX = "DISPOSABLE-"
TEMPLATE_PREFIX = "TEMPLATE-"
VAULT_PREFIX = "VAULT-"
PROTECTED_PREFIXES = (TEMPLATE_PREFIX, VAULT_PREFIX)
TEMP_NAME_RE = r"DISPOSABLE-[A-Z0-9]{1,16}-[0-9]{2}"
PURPOSE_RE = r"[A-Z0-9]{1,16}"
TEMPLATE_NAME_RE = r"TEMPLATE-[A-Za-z0-9_.-]{1,40}"
DEFAULT_PURPOSE = "EMAIL"
MAX_TEMP_NO = 99

# Speicher außerhalb von Home (angelegt durch tools/setup-evoxd.sh)
DATA_DIR = "/srv/evoxd"
TEMPLATE_POOL = "evoxd-templates"
TEMPLATE_PATH = DATA_DIR + "/templates"
OVERLAY_POOL = "evoxd-overlays"
OVERLAY_PATH = DATA_DIR + "/overlays"

NETWORK = "evoxd-net"
BRIDGE = "evoxd0"
NWFILTER = "evoxd-clean"
NFT_TABLE = "evoxd"
GUARD_STATUS = "/run/evoxd/netguard.json"
URI = "qemu:///system"

# Gastnetz (nicht im Heimnetz-Bereich 192.168/16 des Hosts)
NET_CIDR = "10.213.75.0/24"
NET_GW = "10.213.75.1"
NET_DHCP = ("10.213.75.100", "10.213.75.199")
PUBLIC_RESOLVERS = ("9.9.9.9", "149.112.112.112")

# Grenzen für RAM/CPU je Wegwerf-VM
MIN_MEMORY_MIB = 1024
MAX_MEMORY_MIB = 32768
MONITOR_MIN = 200                  # 0.7.4: kleinste plausible Breite/Höhe des gemerkten Live-Monitor-Fensters (px)
RAM_STEP_MIB = 256                  # 0.7.3: wählbar sind nur Vielfache von 256 MiB (0,25 GB) in MIN..MAX_MEMORY_MIB


def ram_on_grid(mib) -> bool:
    """0.7.3: gültige RAM-Größe = ganze Zahl, Vielfaches von RAM_STEP_MIB, in MIN..MAX_MEMORY_MIB (streng)."""
    return (isinstance(mib, int) and not isinstance(mib, bool) and MIN_MEMORY_MIB <= mib <= MAX_MEMORY_MIB
            and mib % RAM_STEP_MIB == 0)


def snap_ram_mib(mib):
    """0.7.3: alte gespeicherte Werte (ganze Zahl in MIN..MAX) auf das 256-MiB-Raster runden (nächster Schritt,
    nie unter MIN, nie über MAX); alles andere → None (ignorieren)."""
    if not (isinstance(mib, int) and not isinstance(mib, bool) and MIN_MEMORY_MIB <= mib <= MAX_MEMORY_MIB):
        return None
    return max(MIN_MEMORY_MIB, min(MAX_MEMORY_MIB, (mib + RAM_STEP_MIB // 2) // RAM_STEP_MIB * RAM_STEP_MIB))
MAX_VCPUS = 16
REMEMBER_KEY = "remember_ram_mib"   # 0.7.0: {Zweck: MiB} in config.json, nur bei Haken im Startdialog
MAX_PURPOSE_STARTS = 10**6          # 0.7.1 Zweck-Statistik: Obergrenze Startzähler (Schutz gegen Unsinn in der Datei)

# Host-Reserve: bleibt nach jedem Start mindestens verfügbar (Konfigurationsdatei, Standard 2 GiB)
DEFAULT_HOST_RESERVE_MIB = 2048
MIN_HOST_RESERVE_MIB = 512
MAX_HOST_RESERVE_MIB = 65536

# Platz in /srv/evoxd, der beim Anlegen einer Template-Kopie (Make template) frei bleiben muss
DEFAULT_TEMPLATE_RESERVE_MIB = 10240
MIN_TEMPLATE_RESERVE_MIB = 1024
MAX_TEMPLATE_RESERVE_MIB = 1048576


def _plain_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


@dataclass
class Settings:
    uri: str = URI
    state_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / PREFIX)
    runtime_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / PREFIX)
    guard_status: Path = Path(GUARD_STATUS)
    vm_memory_mib: int = 2048
    vm_vcpus: int = 2
    host_reserve_mib: int = DEFAULT_HOST_RESERVE_MIB
    verify_after_shutdown: bool = False
    template_reserve_mib: int = DEFAULT_TEMPLATE_RESERVE_MIB
    config_file: Path = None          # None = ~/.config/evoxd/config.json
    guard_max_age_s: float = 3.0
    lock_timeout_s: float = 30.0

    @staticmethod
    def config_path() -> Path:
        return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / PREFIX / "config.json"

    @classmethod
    def load(cls, path: Path = None) -> "Settings":
        """Settings mit Werten aus ~/.config/evoxd/config.json, z. B. {"host_reserve_mib": 2048}.

        Fehlende oder ungültige Werte → Standard."""
        s = cls(config_file=path)
        try:
            data = json.loads((path or cls.config_path()).read_text())
        except (OSError, ValueError):
            return s
        r = data.get("host_reserve_mib") if isinstance(data, dict) else None
        if isinstance(r, int) and not isinstance(r, bool) and MIN_HOST_RESERVE_MIB <= r <= MAX_HOST_RESERVE_MIB:
            s.host_reserve_mib = r
        r = data.get("template_reserve_mib") if isinstance(data, dict) else None
        if (isinstance(r, int) and not isinstance(r, bool)
                and MIN_TEMPLATE_RESERVE_MIB <= r <= MAX_TEMPLATE_RESERVE_MIB):
            s.template_reserve_mib = r
        v = data.get("verify_after_shutdown") if isinstance(data, dict) else None
        if isinstance(v, bool):
            s.verify_after_shutdown = v
        return s

    def save_option(self, key: str, value) -> None:
        """Einen Wert in config.json setzen; andere Einträge (z. B. host_reserve_mib) bleiben."""
        path = self.config_file or self.config_path()
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except FileNotFoundError:
            data = {}
        except (OSError, ValueError):
            # Defekte Datei nie ohne Sicherung überschreiben
            data = {}
            try:
                shutil.copy2(path, path.with_name(f"{path.name}.broken-{int(time.time())}"))
            except OSError:
                pass
        data[key] = value
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1) + "\n")
        os.chmod(tmp, 0o600)
        tmp.replace(path)

    def load_option(self, key: str):
        """Rohwert eines Schlüssels aus config.json (None bei fehlender/defekter Datei); prüfen muss der Aufrufer."""
        try:
            data = json.loads((self.config_file or self.config_path()).read_text())
        except (OSError, ValueError):
            return None
        return data.get(key) if isinstance(data, dict) else None

    def load_remembered_ram(self) -> dict:
        """0.7.0 "Remember for purpose": {Zweck: RAM in MiB} aus config.json (Schlüssel REMEMBER_KEY).
        Nur gültige Einträge (Zweck nach PURPOSE_RE, ganze Zahl in MIN..MAX_MEMORY_MIB); alles andere wird ignoriert.
        0.7.3: alte Werte außerhalb des 256-MiB-Rasters werden beim Lesen auf das Raster gerundet (snap_ram_mib)."""
        try:
            data = json.loads((self.config_file or self.config_path()).read_text())
        except (OSError, ValueError):
            return {}
        raw = data.get(REMEMBER_KEY) if isinstance(data, dict) else None
        if not isinstance(raw, dict):
            return {}
        return {p: snap_ram_mib(v) for p, v in raw.items()
                if isinstance(p, str) and re.fullmatch(PURPOSE_RE, p) and snap_ram_mib(v) is not None}

    def remember_ram(self, purpose: str, memory_mib) -> bool:
        """RAM für einen Zweck merken (memory_mib) oder vergessen (None). Schreibt nur bei Änderung (atomar,
        defekte Datei wird vorher gesichert, siehe save_option). Nur RAM – nie Modus oder Netzsperre."""
        if not (isinstance(purpose, str) and re.fullmatch(PURPOSE_RE, purpose)):
            return False
        cur = self.load_remembered_ram()
        if memory_mib is None:
            if purpose not in cur:
                return False
            del cur[purpose]
        else:
            if not ram_on_grid(memory_mib):
                return False
            if cur.get(purpose) == memory_mib:
                return False
            cur[purpose] = memory_mib
        self.save_option(REMEMBER_KEY, cur)
        return True

    # ---- 0.7.1 Zweck-Statistik: je Zweck höchste echte RAM-Spitze (MiB) und Anzahl Starts; nur Zahlen + Zweckname
    @property
    def purpose_stats_path(self) -> Path:
        return self.state_dir / "purpose-stats.json"

    def load_purpose_stats(self) -> dict:
        """{Zweck: {"peak_mib": int|None, "starts": int}}; ungültige Einträge werden ignoriert, Fehler → {}."""
        try:
            data = json.loads(self.purpose_stats_path.read_text())
        except (OSError, ValueError):
            return {}
        out = {}
        for p, v in (data.items() if isinstance(data, dict) else ()):
            if not (isinstance(p, str) and re.fullmatch(PURPOSE_RE, p) and isinstance(v, dict)):
                continue
            pk, st = v.get("peak_mib"), v.get("starts", 0)
            pk = pk if isinstance(pk, int) and not isinstance(pk, bool) and 1 <= pk <= MAX_MEMORY_MIB else None
            st = st if isinstance(st, int) and not isinstance(st, bool) and 0 <= st <= MAX_PURPOSE_STARTS else 0
            out[p] = {"peak_mib": pk, "starts": st}
        return out

    def _save_purpose_stats(self, stats: dict) -> None:
        """Atomar (tmp + replace, 0600); eine defekte vorhandene Datei wird vorher als .broken-<zeit> gesichert."""
        path = self.purpose_stats_path
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            try:
                shutil.copy2(path, path.with_name(f"{path.name}.broken-{int(time.time())}"))
            except OSError:
                pass
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(stats, indent=1, sort_keys=True) + "\n")
        os.chmod(tmp, 0o600)
        tmp.replace(path)

    def record_purpose_peak(self, purpose: str, peak_mib) -> bool:
        """Höchste Spitze je Zweck merken; schreibt nur, wenn der Wert neu höher ist."""
        if not (isinstance(purpose, str) and re.fullmatch(PURPOSE_RE, purpose)
                and isinstance(peak_mib, int) and not isinstance(peak_mib, bool) and 1 <= peak_mib <= MAX_MEMORY_MIB):
            return False
        stats = self.load_purpose_stats()
        cur = stats.setdefault(purpose, {"peak_mib": None, "starts": 0})
        if cur["peak_mib"] is not None and cur["peak_mib"] >= peak_mib:
            return False
        cur["peak_mib"] = peak_mib
        self._save_purpose_stats(stats)
        return True

    def count_purpose_start(self, purpose: str) -> bool:
        if not (isinstance(purpose, str) and re.fullmatch(PURPOSE_RE, purpose)):
            return False
        stats = self.load_purpose_stats()
        cur = stats.setdefault(purpose, {"peak_mib": None, "starts": 0})
        cur["starts"] = min(cur["starts"] + 1, MAX_PURPOSE_STARTS)
        self._save_purpose_stats(stats)
        return True

    @property
    def registry_path(self) -> Path:
        return self.state_dir / "registry.sqlite3"

    @property
    def lock_path(self) -> Path:
        return self.runtime_dir / "lock"

    @property
    def gui_state_path(self) -> Path:
        return self.state_dir / "gui.json"

    def load_gui_state(self) -> dict:
        """Fenstergröße der GUI (Breite, Höhe, maximiert) und Detailbereich aufgeklappt (0.7.1); Standard 1100×820.
        details_expanded (0.7.2): True/False = ausdrückliche Wahl des Benutzers, None = noch keine Wahl (Auto);
        seit 0.7.4 ungenutzt (Live Monitor ist ein eigenes Fenster), bleibt aber les- und schreibbar.
        0.7.4: monitor = {"width","height","x","y"} des Fensters Live Monitor oder None (x/y None = nicht gemerkt),
        monitor_pin = „Always on top“ (Standard False). Nur plausible Werte; alte Dateien ohne diese Schlüssel gelten."""
        out = {"width": 1100, "height": 820, "maximized": False, "details_expanded": None,
               "monitor": None, "monitor_pin": False, "setup_seen": False}
        data = self._gui_raw()
        for k in ("width", "height"):
            if _plain_int(data.get(k)) and 400 <= data[k] <= 10000:
                out[k] = data[k]
        for k in ("maximized", "details_expanded"):
            if isinstance(data.get(k), bool):
                out[k] = data[k]
        for k in ("monitor_pin", "setup_seen"):          # setup_seen (0.10.0): Erststart-Assistent schon gezeigt
            if isinstance(data.get(k), bool):
                out[k] = data[k]
        m = data.get("monitor")
        if (isinstance(m, dict) and _plain_int(m.get("width")) and _plain_int(m.get("height"))
                and MONITOR_MIN <= m["width"] <= 10000 and MONITOR_MIN <= m["height"] <= 10000):
            pos = [m.get(k) if _plain_int(m.get(k)) and -20000 <= m.get(k) <= 20000 else None for k in ("x", "y")]
            out["monitor"] = {"width": m["width"], "height": m["height"],
                              "x": pos[0] if None not in pos else None, "y": pos[1] if None not in pos else None}
        return out

    def _gui_raw(self) -> dict:
        try:
            data = json.loads(self.gui_state_path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_gui(self, data: dict) -> None:
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = self.gui_state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        os.chmod(tmp, 0o600)
        tmp.replace(self.gui_state_path)

    def save_gui_state(self, width: int, height: int, maximized: bool, details_expanded=None) -> None:
        """Hauptfenster speichern; die Schlüssel des Live Monitors (0.7.4) bleiben erhalten."""
        cur = self.load_gui_state()
        data = {"width": int(width), "height": int(height), "maximized": bool(maximized),
                "details_expanded": None if details_expanded is None else bool(details_expanded),
                "monitor_pin": cur["monitor_pin"], "setup_seen": cur["setup_seen"]}
        if cur["monitor"]:
            data["monitor"] = cur["monitor"]
        self._write_gui(data)

    def save_monitor_state(self, geometry=None, pin=None) -> None:
        """0.7.4: Position/Größe (dict width,height,x,y) und/oder „Always on top“ des Live Monitors speichern;
        Hauptfenster-Werte bleiben unverändert (atomar, 0600)."""
        data = self._gui_raw()
        if geometry is not None:
            data["monitor"] = {k: int(geometry[k]) for k in ("width", "height")}
            for k in ("x", "y"):
                if geometry.get(k) is not None:
                    data["monitor"][k] = int(geometry[k])
        if pin is not None:
            data["monitor_pin"] = bool(pin)
        self._write_gui(data)

    def save_setup_seen(self, seen: bool = True) -> None:
        """0.10.0: Merker „Setup check beim ersten Start gezeigt“; übrige gui.json-Schlüssel bleiben (atomar, 0600)."""
        data = self._gui_raw()
        data["setup_seen"] = bool(seen)
        self._write_gui(data)

    @property
    def last_start_path(self) -> Path:
        return self.state_dir / "last-start.json"

    def load_last_start(self) -> dict:
        """Zuletzt benutzte Werte (RAM, CPUs, Zweck); Standard 2 GiB / 2 CPUs / EMAIL."""
        out = {"memory_mib": self.vm_memory_mib, "vcpus": self.vm_vcpus, "purpose": DEFAULT_PURPOSE}
        try:
            data = json.loads(self.last_start_path.read_text())
        except (OSError, ValueError):
            return out
        if snap_ram_mib(data.get("memory_mib")) is not None:          # 0.7.3: alte Werte aufs Raster
            out["memory_mib"] = snap_ram_mib(data["memory_mib"])
        if isinstance(data.get("vcpus"), int) and 1 <= data["vcpus"] <= MAX_VCPUS:
            out["vcpus"] = data["vcpus"]
        if isinstance(data.get("purpose"), str) and data["purpose"]:
            out["purpose"] = data["purpose"]
        return out

    def save_last_start(self, memory_mib: int, vcpus: int, purpose: str) -> None:
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = self.last_start_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"memory_mib": memory_mib, "vcpus": vcpus, "purpose": purpose}))
        os.chmod(tmp, 0o600)
        tmp.replace(self.last_start_path)
