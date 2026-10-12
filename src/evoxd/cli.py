"""Befehlszeile: evoxd <befehl>."""
import argparse
import datetime
import locale
import resource
import shutil
import subprocess
import sys
import tempfile

from . import __version__, capacity, config, storage
from .config import Settings
from .errors import EvoxError
from .net import check, model


def no_core_dumps():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def use_system_locale():
    """Dezimalzeichen wie die Systemsprache (GTK setzt das Locale ohnehin; CLI gleich)."""
    try:
        locale.setlocale(locale.LC_NUMERIC, "")
    except locale.Error:
        pass


def open_evox(settings=None, hv=None):
    from .hv import LibvirtHypervisor
    from .lifecycle import Evox
    from .registry import Registry
    s = settings or Settings.load()
    hv = hv or LibvirtHypervisor(s.uri)
    return Evox(s, hv, Registry(s.registry_path), net_check=check.make_net_check(hv, s))


def _fmt_ts(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else "-"


def fmt_ram(mib):
    return "?" if mib is None else capacity.fmt_gib(mib)


def fmt_cpus(n):
    return "?" if n is None else str(n)


def open_console(name: str):
    """VM-Fenster (virt-viewer) öffnen. Gibt (Prozess, stderr-Datei) zurück; Startfehler → EvoxError."""
    viewer = shutil.which("virt-viewer")
    if not viewer:
        raise EvoxError("virt-viewer is not installed.")
    err = tempfile.TemporaryFile()   # sofort gelöscht; nimmt Fehlermeldungen von virt-viewer auf
    try:
        p = subprocess.Popen([viewer, "--attach", "--connect", config.URI, name],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err,
                             start_new_session=True)
    except OSError as e:
        err.close()
        raise EvoxError(f"Cannot open the VM window: {e}") from e
    return p, err


def open_virt_manager():
    """virt-manager öffnen (Benutzer legt dort VMs an); EVOX selbst ändert nichts in libvirt."""
    vm = shutil.which("virt-manager")
    if not vm:
        raise EvoxError("virt-manager is not installed.")
    try:
        return subprocess.Popen([vm, "--connect", config.URI], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        raise EvoxError(f"Cannot open virt-manager: {e}") from e


def viewer_error(proc, err) -> str:
    """Nach kurzer Wartezeit: Fehlertext, wenn virt-viewer schon mit Fehler beendet ist, sonst ''."""
    rc = proc.poll()
    if rc is None or rc == 0:
        return ""
    err.seek(0)
    lines = [ln for ln in err.read().decode(errors="replace").splitlines() if ln.strip()]
    return f"VM window could not be opened (virt-viewer exit {rc}): {lines[-1][:200] if lines else 'no message'}"


def cmd_setup(ev, a):
    for line in ev.hv.setup(model.network_xml(), model.nwfilter_xml(), storage.pools()) or ["nothing to do"]:
        print(line)


IMPORT_PHASES = {"copy": "Copying the disk (can take several minutes) …", "checksum": "Computing SHA-256 …"}


def cmd_template_import(ev, a):
    bid = ev.import_template(a.domain, progress=lambda p: print(IMPORT_PHASES[p], flush=True))
    b = ev.reg.base(bid)
    print(f"Template '{b.name}' version {b.version} imported ({b.vol_name}, SHA-256 {b.sha256[:16]}…)")


TEMPLATE_OLD_DAYS = 14


def cmd_template_list(ev, a):
    for t in ev.template_overview():
        warn = "  OLD – please update" if t["age_days"] > TEMPLATE_OLD_DAYS else ""
        warn += "  DAMAGED – import again or remove" if t["damaged"] else ""
        size = capacity.fmt_bytes_gib(t["size"]) if t["size"] is not None else "?"
        print(f"{t['name']:28} v{t['version']:<3} {t['firmware']:4} {size:>9} "
              f"{capacity.fmt_dec(t['age_days']):>5} days  in use {t['in_use']}{warn}")


def cmd_template_verify(ev, a):
    ok = ev.verify_template(a.name, a.version)
    print("Template copy unchanged (SHA-256 matches)." if ok else
          "WARNING: template checksum does NOT match – copy marked DAMAGED, no new starts from it.")
    return 0 if ok else 3


def cmd_template_remove(ev, a):
    for b in ev.remove_template(a.name, version=a.version, older=a.older):
        print(f"{b.name} version {b.version} removed ({b.vol_name})")


def cmd_start(ev, a):
    last = ev.s.load_last_start()
    r = ev.start(a.template, purpose=a.purpose or last["purpose"], want_net=not a.no_net,
                 memory_mib=a.memory or last["memory_mib"], vcpus=a.cpus or last["vcpus"])
    for w in r.warnings:
        print(f"Note: {w}", file=sys.stderr)
    print(f"{r.name} started ({'network with lock' if r.net else 'NO network'})")
    if a.console:
        open_console(r.name)


def cmd_list(ev, a):
    st = check.guard_status(ev.s.guard_status)
    cut = set(st.get("tripped_macs", []))
    rows = ev.list_temps()
    if not rows:
        print("No disposable VMs.")
    for t in rows:
        net = "no network" if t["net"] == "none" else ("CUT (guard)" if t["mac"] in cut else "network")
        print(f"{t['name']:22} {t['template']:28} {t['state']:8} {fmt_ram(t['memory_mib']):>8} "
              f"{fmt_cpus(t['vcpus']):>3} CPU {net:12} since {_fmt_ts(t['created'])}")


def cmd_stop(ev, a):
    names = [t["name"] for t in ev.list_temps()] if a.all else a.names
    for n in names:
        ev.stop(n)
        print(f"{n} destroyed")


def cmd_console(ev, a):
    open_console(a.name)


def cmd_reconcile(ev, a):
    for line in ev.reconcile() or ["Everything as expected."]:
        print(line)


def cmd_netcheck(ev, a):
    ok, why = ev.net_check()
    st = check.guard_status(ev.s.guard_status)
    print(f"Network lock: {'OK' if ok else 'NOT OK – ' + why}")
    if st:
        print(f"Guard: trips {st.get('trips', 0)}, last {_fmt_ts(st.get('last_trip'))} {st.get('last_reason', '')}")
    return 0 if ok else 2


def build_parser():
    p = argparse.ArgumentParser(prog="evoxd", description="EVOX KVM Disposable – disposable VMs for e-mail and web")
    p.add_argument("--version", action="version", version=__version__)
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("setup", help="define EVOX network, nwfilter and pools in libvirt (once)").set_defaults(fn=cmd_setup)
    x = sp.add_parser("template-import", help="import a protected copy of a shut-off TEMPLATE-* domain")
    x.add_argument("domain", help="e.g. TEMPLATE-DEBIAN13")
    x.set_defaults(fn=cmd_template_import)
    sp.add_parser("template-list", help="list templates").set_defaults(fn=cmd_template_list)
    x = sp.add_parser("template-verify", help="verify the checksum of a template copy (default: newest)")
    x.add_argument("name")
    x.add_argument("--version", type=int, metavar="N")
    x.set_defaults(fn=cmd_template_verify)
    x = sp.add_parser("template-remove", help="remove an imported template copy (never the original domain)")
    x.add_argument("name", help="e.g. TEMPLATE-DEBIAN13-BACKUP")
    g = x.add_mutually_exclusive_group()
    g.add_argument("--version", type=int, metavar="N", help="remove version N (needed if several exist)")
    g.add_argument("--older", action="store_true", help="remove all older versions, keep the newest")
    x.set_defaults(fn=cmd_template_remove)
    x = sp.add_parser("start", help="start a new disposable VM from the newest template copy")
    x.add_argument("template", help="e.g. TEMPLATE-DEBIAN13")
    x.add_argument("--purpose", help="purpose in the name DISPOSABLE-<PURPOSE>-NN (default: last used, EMAIL)")
    x.add_argument("--memory", type=int, metavar="MIB", help="RAM in MiB, multiples of 256 (default: last used, 2048)")
    x.add_argument("--cpus", type=int, help="number of CPUs (default: last used, 2)")
    x.add_argument("--no-net", action="store_true", help="no network")
    x.add_argument("--console", action="store_true", help="open the console")
    x.set_defaults(fn=cmd_start)
    sp.add_parser("list", help="list disposable VMs").set_defaults(fn=cmd_list)
    x = sp.add_parser("stop", help="stop a disposable VM = destroy it")
    x.add_argument("names", nargs="*")
    x.add_argument("--all", action="store_true")
    x.set_defaults(fn=cmd_stop)
    x = sp.add_parser("console", help="open the console of a disposable VM")
    x.add_argument("name")
    x.set_defaults(fn=cmd_console)
    sp.add_parser("reconcile", help="reconcile with libvirt, destroy leftovers").set_defaults(fn=cmd_reconcile)
    sp.add_parser("netcheck", help="check network lock and guard").set_defaults(fn=cmd_netcheck)
    return p


def main(argv=None, evox_factory=open_evox):
    no_core_dumps()
    use_system_locale()
    a = build_parser().parse_args(argv)
    if a.cmd == "stop" and not (a.names or a.all):
        print("Give a name or --all.", file=sys.stderr)
        return 2
    try:
        ev = evox_factory()
        return a.fn(ev, a) or 0
    except EvoxError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except PermissionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
