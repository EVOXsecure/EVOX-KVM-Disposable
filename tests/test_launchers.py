"""tools/install_launchers.py mit Attrappen für HOME/Desktop/dpkg/gio; kein echter Start."""
import importlib.util
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.nospawn import NoSpawnMixin

_T = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location("install_launchers", _T / "install_launchers.py")
il = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(il)

PKG_DESKTOP = ("[Desktop Entry]\nType=Application\nName=EVOX KVM DISPOSABLE\nExec=evoxd-gui\n"
               "Icon=evoxd\nTerminal=false\nCategories=System;Security;\n")


class Case(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.realpath(self.tmp.name)
        self.desk = Path(self.home, "Schreibtisch")
        self.desk.mkdir()
        Path(self.home, CLAUDE := "CLAUDE-Projekts/EVOX-KVM-DISPOSABLE").mkdir(parents=True)
        self.pkg = Path(self.home, "pkg.desktop")
        self.pkg.write_text(PKG_DESKTOP)
        self.calls = []
        self.have = {"gnome-terminal", "gio", "claude"}
        self.gio_rc = 0
        self.pkg_ok = True
        self.out = []

    def tearDown(self):
        self.tmp.cleanup()

    def run_fake(self, cmd, **kw):
        self.calls.append(cmd)
        R = subprocess.CompletedProcess
        if cmd[0] == "xdg-user-dir":
            return R(cmd, 0, f"{self.desk}\n", "")
        if cmd[0] == "dpkg-query":
            if not self.pkg_ok:
                return R(cmd, 1, "", "")
            return R(cmd, 0, f"/.\n{self.pkg}\n/usr/share/icons/hicolor/scalable/apps/evoxd.svg\n", "")
        if cmd[0] == "gio":
            return R(cmd, self.gio_rc, "", "")
        raise AssertionError(cmd)

    def go(self, *args):
        self.out = []
        # das Paket-.desktop liegt im Test nicht unter /usr/share/applications -> Pfad durchreichen
        orig = il.package_entry

        def pe(run, env):
            if not self.pkg_ok:
                return None, None
            return str(self.pkg), "evoxd"
        il.package_entry = pe
        try:
            return il.main(list(args), env={"HOME": self.home, "PATH": ""}, run=self.run_fake,
                           which=lambda n: f"/x/{n}" if n in self.have else None, say=self.out.append)
        finally:
            il.package_entry = orig

    def files(self):
        return sorted(str(p.relative_to(self.home)) for p in Path(self.home).rglob("*.desktop")
                      if p.name != "pkg.desktop")

    def text(self, rel):
        return Path(self.home, rel).read_text()


class Launchers(Case):
    def test_files_and_content(self):
        self.assertEqual(self.go(), 0)
        self.assertEqual(self.files(), [".local/share/applications/code-evox-kvm-disposable.desktop",
                                        "Schreibtisch/code-evox-kvm-disposable.desktop",
                                        "Schreibtisch/evoxd-gui.desktop"])
        c = self.text("Schreibtisch/code-evox-kvm-disposable.desktop")
        self.assertIn("Name=CODE-EVOX-KVM-DISPOSABLE\n", c)
        self.assertIn("Comment=Claude Code im Projektordner EVOX-KVM-DISPOSABLE\n", c)
        self.assertIn(f'Exec=gnome-terminal -- bash -lc "cd {self.home}/CLAUDE-Projekts/EVOX-KVM-DISPOSABLE'
                      f' && claude; exec bash"\n', c)
        self.assertIn("Icon=utilities-terminal\n", c)
        self.assertNotIn("/home/example", c.replace(self.home, ""))
        e = self.text("Schreibtisch/evoxd-gui.desktop")
        self.assertIn("Exec=evoxd-gui\n", e)
        self.assertIn("Icon=evoxd\n", e)
        self.assertIn("X-EVOX-Launcher=evoxd-gui", e)
        for rel, x in ((".local/share/applications/code-evox-kvm-disposable.desktop", False),
                       ("Schreibtisch/code-evox-kvm-disposable.desktop", True),
                       ("Schreibtisch/evoxd-gui.desktop", True)):
            self.assertEqual(bool(Path(self.home, rel).stat().st_mode & stat.S_IXUSR), x, rel)
        trusted = [c for c in self.calls if c[0] == "gio"]
        self.assertEqual(len(trusted), 2)
        self.assertEqual(trusted[0][3:], ["metadata::trusted", "true"])

    def test_x_terminal_fallback_and_none(self):
        self.have = {"x-terminal-emulator", "claude"}
        self.assertEqual(self.go(), 0)
        self.assertIn("Exec=x-terminal-emulator -e bash -lc", self.text("Schreibtisch/code-evox-kvm-disposable.desktop"))
        self.assertTrue(any("gio fehlt" in m for m in self.out))
        self.have = {"claude"}
        Path(self.home, ".local/share/applications/code-evox-kvm-disposable.desktop").unlink()
        Path(self.desk, "code-evox-kvm-disposable.desktop").unlink()
        self.assertEqual(self.go(), 1)
        self.assertTrue(any("weder gnome-terminal" in m for m in self.out))

    def test_gio_failure_hint(self):
        self.gio_rc = 1
        self.assertEqual(self.go(), 0)
        self.assertTrue(any("Starten erlauben" in m for m in self.out))

    def test_dry_run_writes_nothing(self):
        self.assertEqual(self.go("--dry-run"), 0)
        self.assertEqual(self.files(), [])
        self.assertEqual([c for c in self.calls if c[0] == "gio"], [])
        self.assertTrue(any("[dry-run]" in m for m in self.out))

    def test_idempotent(self):
        self.go()
        before = {f: self.text(f) for f in self.files()}
        self.assertEqual(self.go(), 0)
        self.assertEqual({f: self.text(f) for f in self.files()}, before)
        self.assertEqual(sum("unverändert" in m for m in self.out), 3)

    def test_remove_only_own(self):
        self.go()
        foreign = self.desk / "evoxd-gui.desktop"
        foreign.write_text("[Desktop Entry]\nName=fremd\n")
        other = self.desk / "andere.desktop"
        other.write_text("x")
        self.assertEqual(self.go("--remove", "--dry-run"), 0)
        self.assertEqual(len(self.files()), 4)
        self.assertEqual(self.go("--remove"), 0)
        self.assertEqual(self.files(), ["Schreibtisch/andere.desktop", "Schreibtisch/evoxd-gui.desktop"])
        self.assertEqual(foreign.read_text(), "[Desktop Entry]\nName=fremd\n")
        self.assertTrue(any("nicht von diesem Skript" in m for m in self.out))

    def test_missing_project_and_claude(self):
        os.rmdir(Path(self.home, "CLAUDE-Projekts/EVOX-KVM-DISPOSABLE"))
        self.assertEqual(self.go(), 1)
        self.assertTrue(any("Projektordner" in m and "fehlt" in m for m in self.out))
        self.assertEqual(self.files(), ["Schreibtisch/evoxd-gui.desktop"])
        os.mkdir(Path(self.home, "CLAUDE-Projekts/EVOX-KVM-DISPOSABLE"))
        self.have = {"gnome-terminal", "gio"}
        self.assertEqual(self.go(), 1)
        self.assertTrue(any("claude nicht gefunden" in m for m in self.out))
        self.assertEqual(self.files(), ["Schreibtisch/evoxd-gui.desktop"])

    def test_package_missing_hint(self):
        self.pkg_ok = False
        self.assertEqual(self.go(), 1)
        self.assertTrue(any("Paket evoxd nicht installiert" in m for m in self.out))
        self.assertEqual(len(self.files()), 2)

    def test_desktop_outside_home_refused(self):
        self.desk = Path("/tmp")
        self.assertEqual(self.go(), 1)
        self.assertEqual(self.files(), [])

    def test_bad_args_and_wrapper(self):
        self.assertEqual(self.go("--foo"), 2)
        sh = (_T / "install-launchers.sh").read_text()
        self.assertNotIn("sudo ", sh.replace("Kein sudo", ""))
        self.assertTrue(os.access(_T / "install-launchers.sh", os.X_OK))

    def test_desktop_files_not_in_package(self):
        b = (_T.parent / "packaging" / "build-deb.sh").read_text()
        self.assertNotIn("install-launchers", b)
        self.assertNotIn("install_launchers", b)
