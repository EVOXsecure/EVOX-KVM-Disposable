"""Schutz: Tests dürfen keine echten Programme starten (z. B. virt-viewer).

install() ersetzt subprocess.Popen.__init__ einmalig global. Erlaubt ist nur der Python-Interpreter
(sys.executable). Jeder andere Start wird verhindert (OSError) und in VIOLATIONS vermerkt;
NoSpawnMixin.run lässt den Test dann fehlschlagen, auch wenn die Anwendung den Fehler schluckt.
"""
import os
import subprocess
import sys

VIOLATIONS = []
_installed = False


def _argv0(args):
    if isinstance(args, (str, bytes, os.PathLike)):
        return os.fspath(args) if not isinstance(args, bytes) else os.fsdecode(args)
    return os.fsdecode(os.fspath(args[0])) if args else ""


def install():
    global _installed
    if _installed:
        return
    orig = subprocess.Popen.__init__

    def guarded(self, args, *a, **k):
        prog = _argv0(args)
        if os.path.realpath(prog.split()[0] if prog else "") != os.path.realpath(sys.executable):
            VIOLATIONS.append(prog)
            raise OSError(f"tests must not start real programs: {prog}")
        orig(self, args, *a, **k)
    subprocess.Popen.__init__ = guarded
    _installed = True


class NoSpawnMixin:
    """Als erste Basisklasse mischen: nach jedem Test schlägt er fehl, wenn ein echter Start versucht wurde
    (auch wenn die Anwendung den Fehler abfängt)."""

    def run(self, result=None):
        install()
        VIOLATIONS.clear()
        result = super().run(result)
        found, VIOLATIONS[:] = list(VIOLATIONS), []
        if found and result is not None:
            try:
                raise AssertionError(f"test tried to start real program(s): {found}")
            except AssertionError:
                import sys as _s
                result.addFailure(self, _s.exc_info())
        return result
