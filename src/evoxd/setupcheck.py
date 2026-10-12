"""Setup check (0.10.0, Weg 1): nur lesende Prüfungen plus ein fest vorgegebener Befehlskatalog.

Die GUI bekommt nie Root. Ein ✗ kann nur über einen Befehl aus CATALOG behoben werden, der in einem Terminal läuft
(das Passwort wird nur dort eingegeben). Befehle entstehen ausschließlich aus festen Listen (PACKAGES, UNITS, GROUPS):
keine Eingaben aus Dateien, VM-Namen oder Umgebung; Argumente sind immer eine Liste (keine Shell-Interpolation).
Fremde Programme laufen über den Parameter `run`, damit Tests nichts Echtes starten (tests/nospawn.py).
"""
import grp
import os
import pwd
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import config
from . import texts as T
from .net import check

PACKAGES = ("python3-libvirt", "python3-gi", "gir1.2-gtk-3.0", "libvirt-daemon-system", "libvirt-daemon-driver-qemu",
            "nftables", "iproute2", "virt-viewer", "qemu-utils", "qemu-system-x86")
GROUPS = ("libvirt", "kvm")
UNITS = ("libvirtd", "evoxd-netguard")
STEPS = ("packages", "hardware", "groups", "services", "evox", "template")      # "Step n of 6"
MIN_AVAIL_RAM_MIB = 4096
MIN_FREE_DISK_GIB = 20
NET_HOST = ("archive.ubuntu.com", 80)
USER_RE = re.compile(r"[a-z_][a-z0-9_-]{0,31}")
# Wird im Terminal ausgeführt; die Befehlsteile kommen als Positionsargumente ($@), nie als Text im Skript.
TERMINAL_SCRIPT = 'echo "$ $*"; echo; "$@"; rc=$?; echo; echo "Done (exit code $rc). Press Enter to close."; read -r _'
SUDO = "sudo"


@dataclass
class Item:
    step: int                    # 1..6
    key: str                     # eindeutiger Name, z. B. "pkg:nftables"
    ok: bool
    text: str                    # Klartext (Name und Wert)
    why: str = ""                # bei ✗: ein Satz „why this is needed“
    fix: Optional[str] = None    # Schlüssel in CATALOG oder None
    info: str = ""               # zusätzlicher Hinweis (z. B. „log out and in again“)


# ---- Befehlskatalog (fest) --------------------------------------------------------------------------------------
def apt_argv(missing) -> list:
    """Ein gesammeltes `sudo apt install …`; nur Namen aus PACKAGES, in fester Reihenfolge."""
    names = [p for p in PACKAGES if p in set(missing)]
    return [SUDO, "apt", "install", *names] if names else []


def setup_argv() -> list:
    return [SUDO, "evoxd", "setup"]


def groups_argv(user, missing) -> list:
    names = [g for g in GROUPS if g in set(missing)]
    if not names or not isinstance(user, str) or not USER_RE.fullmatch(user):
        return []
    return [SUDO, "usermod", "-aG", ",".join(names), user]


def services_argv(units) -> list:
    names = [u for u in UNITS if u in set(units)]
    return [SUDO, "systemctl", "enable", "--now", *names] if names else []


def fix_argv(kind: str, items) -> list:
    """Befehl zu einem Fix-Schlüssel aus den aktuellen Prüfergebnissen; leer = nichts anzubieten."""
    items = list(items)
    if kind == "apt":
        return apt_argv([i.key[4:] for i in items if i.key.startswith("pkg:") and not i.ok])
    if kind == "setup":
        return setup_argv()
    if kind == "groups":
        return groups_argv(current_user(), [i.key[6:] for i in items if i.key.startswith("group:") and not i.ok
                                            and i.fix == "groups"])
    if kind == "services":
        return services_argv([i.key[5:] for i in items if i.key.startswith("unit:") and not i.ok])
    return []


def current_user() -> Optional[str]:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        return None


def pick_terminal(which) -> Optional[list]:
    """Terminal-Vorspann wie tools/install_launchers.py (gnome-terminal zuerst); --wait: Aufruf kehrt erst beim
    Schließen des Fensters zurück. Sonst None."""
    if which("gnome-terminal"):
        return ["gnome-terminal", "--wait", "--"]
    if which("x-terminal-emulator"):
        return ["x-terminal-emulator", "-e"]
    return None


def terminal_argv(argv, which=shutil.which) -> Optional[list]:
    """Vollständiger Aufruf: Terminal + bash -c <festes Skript> bash <Befehl als Argumentliste>."""
    pre = pick_terminal(which)
    if pre is None or not argv:
        return None
    return [*pre, "bash", "-c", TERMINAL_SCRIPT, "bash", *argv]


def command_text(argv) -> str:
    """Klartext-Anzeige des Befehls (nur Anzeige)."""
    return " ".join(argv)


# ---- Prüfungen (nur lesend) -------------------------------------------------------------------------------------
def _run(run, cmd):
    try:
        r = run(cmd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return r


def check_packages(run=subprocess.run) -> list:
    out = []
    for p in PACKAGES:
        r = _run(run, ["dpkg-query", "-W", "-f=${db:Status-Abbrev} ${Version}", p])
        word = (r.stdout.strip().split(None, 1) if r is not None and r.returncode == 0 else [])
        if len(word) == 2 and word[0].startswith("ii"):
            out.append(Item(1, f"pkg:{p}", True, f"{p} {word[1]}"))
        else:
            out.append(Item(1, f"pkg:{p}", False, f"{p} – {T.SETUP_NOT_INSTALLED}", T.SETUP_WHY_PKG[p], "apt"))
    return out


def check_internet(connect=socket.create_connection) -> Item:
    try:
        connect(NET_HOST, timeout=3).close()
    except (OSError, ValueError):
        return Item(1, "internet", False, T.SETUP_NET_BAD, T.SETUP_WHY_NET)
    return Item(1, "internet", True, T.SETUP_NET_OK)


def read_meminfo(path="/proc/meminfo") -> dict:
    out = {}
    try:
        with open(path) as f:
            for ln in f:
                k, _, v = ln.partition(":")
                if v.split():
                    out[k] = int(v.split()[0])
    except (OSError, ValueError):
        pass
    return out


def check_hardware(meminfo=read_meminfo, disk_usage=shutil.disk_usage, exists=os.path.exists, access=os.access,
                   data_dir=config.DATA_DIR) -> list:
    out = []
    if not exists("/dev/kvm"):
        out.append(Item(2, "kvm", False, T.SETUP_KVM_MISSING, T.SETUP_WHY_KVM))
    elif not access("/dev/kvm", os.R_OK | os.W_OK):
        out.append(Item(2, "kvm", False, T.SETUP_KVM_DENIED, T.SETUP_WHY_KVM_ACCESS))
    else:
        out.append(Item(2, "kvm", True, T.SETUP_KVM_OK))
    avail = meminfo().get("MemAvailable")
    if avail is None:
        out.append(Item(2, "ram", False, T.SETUP_RAM_UNKNOWN, T.SETUP_WHY_RAM.format(gib=MIN_AVAIL_RAM_MIB // 1024)))
    else:
        mib = avail // 1024
        out.append(Item(2, "ram", mib >= MIN_AVAIL_RAM_MIB, T.SETUP_RAM.format(gib=mib / 1024),
                        "" if mib >= MIN_AVAIL_RAM_MIB else T.SETUP_WHY_RAM.format(gib=MIN_AVAIL_RAM_MIB // 1024)))
    path = data_dir if exists(data_dir) else "/"
    try:
        free = disk_usage(path).free / 2**30
    except OSError:
        out.append(Item(2, "disk", False, T.SETUP_DISK_UNKNOWN, T.SETUP_WHY_DISK.format(gib=MIN_FREE_DISK_GIB)))
    else:
        out.append(Item(2, "disk", free >= MIN_FREE_DISK_GIB, T.SETUP_DISK.format(gib=free),
                        "" if free >= MIN_FREE_DISK_GIB else T.SETUP_WHY_DISK.format(gib=MIN_FREE_DISK_GIB)))
    return out


def _group_members(name):
    try:
        g = grp.getgrnam(name)
    except KeyError:
        return None, ()
    return g.gr_gid, tuple(g.gr_mem)


def check_groups(user=None, process_gids=None, group_info=_group_members) -> list:
    """✓ = der laufende Prozess hat die Gruppe. In der Gruppendatei, aber noch nicht im Prozess: ✗ mit Hinweis
    „log out and in again“ (kein Fix-Knopf – der Befehl wäre schon ausgeführt)."""
    user = current_user() if user is None else user
    gids = set(os.getgroups() if process_gids is None else process_gids)
    out = []
    for g in GROUPS:
        gid, members = group_info(g)
        if gid is None:
            out.append(Item(3, f"group:{g}", False, T.SETUP_GROUP_MISSING.format(g=g), T.SETUP_WHY_GROUP[g], None))
        elif gid in gids:
            out.append(Item(3, f"group:{g}", True, T.SETUP_GROUP_OK.format(g=g)))
        elif user in members:
            out.append(Item(3, f"group:{g}", False, T.SETUP_GROUP_RELOGIN.format(g=g), T.SETUP_WHY_GROUP[g], None,
                            T.SETUP_RELOGIN))
        else:
            out.append(Item(3, f"group:{g}", False, T.SETUP_GROUP_NOT.format(g=g), T.SETUP_WHY_GROUP[g], "groups"))
    return out


def check_services(run=subprocess.run) -> list:
    out = []
    for u in UNITS:
        r = _run(run, ["systemctl", "is-active", u])
        active = r is not None and r.returncode == 0 and r.stdout.strip() == "active"
        if not active and u == "libvirtd":      # Socket-Aktivierung: libvirtd.socket genügt
            r = _run(run, ["systemctl", "is-active", "libvirtd.socket"])
            active = r is not None and r.returncode == 0 and r.stdout.strip() == "active"
        out.append(Item(4, f"unit:{u}", active, T.SETUP_UNIT_OK.format(u=u) if active else T.SETUP_UNIT_BAD.format(u=u),
                        "" if active else T.SETUP_WHY_UNIT[u], None if active else "services"))
    return out


def check_evox(ev) -> list:
    """Netz, nwfilter und Pools über die vorhandenen Prüffunktionen (net/check.py, hv.pool_ok); ev=None = libvirt
    nicht erreichbar."""
    if ev is None:
        return [Item(5, "evox", False, T.SETUP_EVOX_NO_LIBVIRT, T.SETUP_WHY_EVOX, "setup")]
    out = []
    for key, label, fn in (("net", T.SETUP_EVOX_NET, lambda: check.check_network(ev.hv.network_xml(config.NETWORK))),
                           ("filter", T.SETUP_EVOX_FILTER,
                            lambda: check.check_nwfilter(ev.hv.nwfilter_xml(config.NWFILTER))),
                           ("pools", T.SETUP_EVOX_POOLS, lambda: (ev.hv.pool_ok(), ""))):
        try:
            ok, why = fn()
        except Exception as e:  # noqa: BLE001 – Prüfung darf nie die GUI stören
            ok, why = False, str(e)[:80]
        out.append(Item(5, f"evox:{key}", bool(ok), label + ("" if ok else f" – {why or T.SETUP_MISSING}"),
                        "" if ok else T.SETUP_WHY_EVOX, None if ok else "setup"))
    return out


def check_template(ev) -> list:
    if ev is None:
        return [Item(6, "template", False, T.SETUP_TPL_UNKNOWN, T.SETUP_WHY_TPL)]
    try:
        n = len([t for t in ev.template_overview() if not t.get("damaged")])
    except Exception:  # noqa: BLE001
        return [Item(6, "template", False, T.SETUP_TPL_UNKNOWN, T.SETUP_WHY_TPL)]
    if n:
        return [Item(6, "template", True, T.SETUP_TPL_OK.format(n=n))]
    return [Item(6, "template", False, T.SETUP_TPL_NONE, T.SETUP_WHY_TPL, None, T.SETUP_TPL_HINT)]


@dataclass
class Checker:
    """Alle sechs Schritte; Fremdzugriffe austauschbar (Tests)."""
    ev: object = None
    run: Callable = subprocess.run
    connect: Callable = socket.create_connection
    meminfo: Callable = read_meminfo
    disk_usage: Callable = shutil.disk_usage
    exists: Callable = os.path.exists
    access: Callable = os.access
    group_info: Callable = _group_members
    user: Optional[str] = None
    gids: Optional[list] = None
    data_dir: str = config.DATA_DIR
    steps: tuple = field(default=STEPS)

    def step(self, n: int) -> list:
        if n == 1:
            return check_packages(self.run) + [check_internet(self.connect)]
        if n == 2:
            return check_hardware(self.meminfo, self.disk_usage, self.exists, self.access, self.data_dir)
        if n == 3:
            return check_groups(self.user, self.gids, self.group_info)
        if n == 4:
            return check_services(self.run)
        if n == 5:
            return check_evox(self.ev)
        return check_template(self.ev)

    def all(self, progress=None) -> list:
        out = []
        for n in range(1, len(self.steps) + 1):
            if progress:
                progress(n)
            out += self.step(n)
        return out


def problems(items) -> list:
    return [i for i in items if not i.ok]


def report(items) -> str:
    """Checkliste als Text (Knopf „Copy report“)."""
    lines = [T.SETUP_REPORT_HEAD]
    for n, name in enumerate(T.SETUP_STEP_NAMES, 1):
        lines.append(f"{n}. {name}")
        for i in items:
            if i.step == n:
                lines.append(f"  {'✓' if i.ok else '✗'} {i.text}" + (f" – {i.why}" if i.why else "")
                             + (f" ({i.info})" if i.info else ""))
    lines.append(T.SETUP_READY if not problems(items) else T.SETUP_PROBLEMS.format(n=len(problems(items))))
    return "\n".join(lines)


# ---- Starter (nur Home), Logik wie tools/install_launchers.py ----------------------------------------------------
MARK = "X-EVOX-Launcher"
PACKAGE_DESKTOP = "/usr/share/applications/evoxd.desktop"


def launcher_content(src_text: str) -> str:
    lines = [ln for ln in src_text.splitlines() if not ln.startswith(("Icon=", MARK + "="))]
    lines.insert(1, "Icon=evoxd")
    lines.append(f"{MARK}=evoxd-gui")
    return "\n".join(lines) + "\n"


def desktop_dir(home: str, run=subprocess.run) -> Optional[str]:
    r = _run(run, ["xdg-user-dir", "DESKTOP"])
    d = (r.stdout.strip() if r is not None and r.returncode == 0 else "") or os.path.join(home, "Desktop")
    d = os.path.realpath(d)
    if not (d == home or d.startswith(home.rstrip("/") + "/")) or not os.path.isdir(d):
        return None
    return d


def create_launcher(home=None, run=subprocess.run, which=shutil.which, src=PACKAGE_DESKTOP) -> str:
    """Schreibtisch-Starter für EVOX GUI (nur unter $HOME, unverändert = nichts schreiben). Gibt eine Meldung zurück."""
    home = os.path.realpath(home or os.path.expanduser("~"))
    try:
        with open(src, encoding="utf-8") as f:
            text = launcher_content(f.read())
    except OSError:
        return T.SETUP_LAUNCHER_NOPKG
    d = desktop_dir(home, run)
    if d is None:
        return T.SETUP_LAUNCHER_NODIR
    path = os.path.join(d, "evoxd-gui.desktop")
    try:
        with open(path, encoding="utf-8") as f:
            same = f.read() == text
    except OSError:
        same = False
    if not same:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    os.chmod(path, 0o755)
    if which("gio"):
        _run(run, ["gio", "set", path, "metadata::trusted", "true"])
    return T.SETUP_LAUNCHER_OK.format(path=path)
