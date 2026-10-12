"""0.10.0 (A6): Setup check – Prüflogik, fester Befehlskatalog, Fix-Knöpfe (nur Vorschau, Sperre), Erststart-Merker,
Hinweisbalken, Starter. Nur Attrappen; tests/nospawn.py aktiv, kein echter Terminalstart."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from evoxd import config, setupcheck as S
from evoxd import texts as T
from evoxd.config import Settings
from evoxd.net import model
from tests.nospawn import NoSpawnMixin
from tests.test_a3b import HAVE_DISPLAY, GuiBase


def cp(rc=0, out=""):
    return subprocess.CompletedProcess([], rc, out, "")


def dpkg_run(installed):
    def run(cmd, **kw):
        if cmd[0] == "dpkg-query":
            p = cmd[-1]
            return cp(0, f"ii  1.2.3-{p[:2]}") if p in installed else cp(1, "")
        raise AssertionError(cmd)
    return run


def unit_run(active):
    def run(cmd, **kw):
        assert cmd[:2] == ["systemctl", "is-active"]
        return cp(0, "active\n") if cmd[2] in active else cp(3, "inactive\n")
    return run


class CheckLogicTest(NoSpawnMixin, unittest.TestCase):
    def test_packages_ok_missing_error(self):
        items = S.check_packages(dpkg_run(set(S.PACKAGES) - {"nftables"}))
        self.assertEqual(len(items), len(S.PACKAGES))
        bad = [i for i in items if not i.ok]
        self.assertEqual([i.key for i in bad], ["pkg:nftables"])
        self.assertEqual(bad[0].fix, "apt")
        self.assertTrue(bad[0].why)
        self.assertIn("1.2.3", items[0].text)                      # Version wird gezeigt

        def boom(cmd, **kw):
            raise OSError("no dpkg")
        self.assertTrue(all(not i.ok for i in S.check_packages(boom)))
        self.assertTrue(all(i.fix == "apt" and i.why for i in S.check_packages(boom)))

    def test_internet(self):
        class C:
            def close(self): pass
        self.assertTrue(S.check_internet(lambda *a, **k: C()).ok)
        def bad(*a, **k): raise OSError("down")
        i = S.check_internet(bad)
        self.assertFalse(i.ok)
        self.assertTrue(i.why)

    def test_hardware(self):
        mi = lambda kib: (lambda: {"MemAvailable": kib})
        du = lambda gib: (lambda p: SimpleNamespace(free=gib * 2**30))
        ok = S.check_hardware(mi(8 * 2**20), du(100), lambda p: True, lambda p, m: True)
        self.assertTrue(all(i.ok for i in ok))
        self.assertEqual([i.key for i in ok], ["kvm", "ram", "disk"])
        low = S.check_hardware(mi(2 * 2**20), du(5), lambda p: True, lambda p, m: True)
        self.assertEqual([i.ok for i in low], [True, False, False])
        self.assertTrue(low[1].why and low[2].why)
        nokvm = S.check_hardware(mi(8 * 2**20), du(100), lambda p: p != "/dev/kvm", lambda p, m: True)
        self.assertFalse(nokvm[0].ok)
        denied = S.check_hardware(mi(8 * 2**20), du(100), lambda p: True, lambda p, m: False)
        self.assertFalse(denied[0].ok)
        self.assertNotEqual(nokvm[0].why, denied[0].why)
        def err(p): raise OSError("x")
        unknown = S.check_hardware(lambda: {}, err, lambda p: True, lambda p, m: True)
        self.assertEqual([i.ok for i in unknown], [True, False, False])

    def test_groups(self):
        info = {"libvirt": (900, ("bob",)), "kvm": (901, ())}
        gi_ = lambda g: info.get(g, (None, ()))
        items = S.check_groups("bob", [900, 901], gi_)
        self.assertTrue(all(i.ok for i in items))
        items = S.check_groups("bob", [100], gi_)                  # libvirt: in Datei, nicht im Prozess
        self.assertFalse(items[0].ok)
        self.assertIsNone(items[0].fix)
        self.assertIn("log out and in again", items[0].info)
        self.assertEqual(items[1].fix, "groups")                   # kvm: nicht Mitglied
        self.assertIsNone(S.check_groups("bob", [100], lambda g: (None, ()))[0].fix)

    def test_services(self):
        self.assertTrue(all(i.ok for i in S.check_services(unit_run({"libvirtd", "evoxd-netguard"}))))
        items = S.check_services(unit_run({"libvirtd.socket"}))      # Socket-Aktivierung zählt
        self.assertEqual([i.ok for i in items], [True, False])
        self.assertEqual(items[1].fix, "services")

        def boom(cmd, **kw):
            raise OSError("x")
        self.assertTrue(all(not i.ok for i in S.check_services(boom)))

    def test_evox(self):
        none = S.check_evox(None)
        self.assertEqual([i.ok for i in none], [False])
        hv = SimpleNamespace(network_xml=lambda n: model.network_xml(), nwfilter_xml=lambda n: model.nwfilter_xml(),
                             pool_ok=lambda: True)
        ev = SimpleNamespace(hv=hv)
        self.assertTrue(all(i.ok for i in S.check_evox(ev)))
        hv2 = SimpleNamespace(network_xml=lambda n: None, nwfilter_xml=lambda n: None, pool_ok=lambda: False)
        items = S.check_evox(SimpleNamespace(hv=hv2))
        self.assertEqual([i.ok for i in items], [False, False, False])
        self.assertTrue(all(i.fix == "setup" and i.why for i in items))

        def boom():
            raise RuntimeError("libvirt gone")
        hv3 = SimpleNamespace(network_xml=lambda n: model.network_xml(), nwfilter_xml=lambda n: model.nwfilter_xml(),
                              pool_ok=boom)
        self.assertEqual([i.ok for i in S.check_evox(SimpleNamespace(hv=hv3))], [True, True, False])

    def test_template(self):
        ev = lambda f: SimpleNamespace(template_overview=f)
        self.assertTrue(S.check_template(ev(lambda: [{"damaged": False}]))[0].ok)
        none = S.check_template(ev(lambda: []))[0]
        self.assertFalse(none.ok)
        self.assertIn("Import from existing VM", none.info)
        self.assertIn("Create new VAULT VM", none.info)
        self.assertFalse(S.check_template(ev(lambda: [{"damaged": True}]))[0].ok)

        def boom():
            raise OSError("x")
        self.assertFalse(S.check_template(ev(boom))[0].ok)
        self.assertFalse(S.check_template(None)[0].ok)

    def test_checker_runs_six_steps_and_report(self):
        seen = []
        ch = S.Checker(ev=None, run=dpkg_run(set(S.PACKAGES)), connect=mock.Mock(),
                       meminfo=lambda: {"MemAvailable": 8 * 2**20}, disk_usage=lambda p: SimpleNamespace(free=2**40),
                       exists=lambda p: True, access=lambda p, m: True, user="bob", gids=[1],
                       group_info=lambda g: (1, ("bob",)))
        ch.run = lambda cmd, **kw: dpkg_run(set(S.PACKAGES))(cmd) if cmd[0] == "dpkg-query" else cp(0, "active\n")
        items = ch.all(progress=seen.append)
        self.assertEqual(seen, [1, 2, 3, 4, 5, 6])
        text = S.report(items)
        self.assertIn("✓ python3-gi", text)
        self.assertIn("✗", text)                                   # EVOX setup / Template ohne Evox
        self.assertIn("need attention", text)
        self.assertEqual(S.report([S.Item(1, "x", True, "fine")]).splitlines()[-1], T.SETUP_READY)


class CatalogTest(NoSpawnMixin, unittest.TestCase):
    def test_packages_fixed_and_immutable(self):
        self.assertIsInstance(S.PACKAGES, tuple)
        self.assertEqual(len(S.PACKAGES), 10)
        with self.assertRaises(TypeError):
            S.PACKAGES[0] = "evil"                                 # type: ignore[index]

    def test_apt_only_from_fixed_list(self):
        evil = ["nftables; rm -rf /", "$(id)", "../x", "nftables", "python3-gi"]
        self.assertEqual(S.apt_argv(evil), ["sudo", "apt", "install", "python3-gi", "nftables"])
        self.assertEqual(S.apt_argv(["evil"]), [])
        self.assertEqual(S.apt_argv([]), [])

    def test_fix_argv_ignores_item_texts(self):
        items = [S.Item(1, "pkg:evil; id", False, "x; reboot", fix="apt"), S.Item(1, "pkg:nftables", False, "y", fix="apt")]
        self.assertEqual(S.fix_argv("apt", items), ["sudo", "apt", "install", "nftables"])
        self.assertEqual(S.fix_argv("bogus", items), [])
        self.assertEqual(S.fix_argv("setup", []), ["sudo", "evoxd", "setup"])

    def test_groups_command(self):
        self.assertEqual(S.groups_argv("bob", ["kvm", "libvirt", "evil"]), ["sudo", "usermod", "-aG", "libvirt,kvm", "bob"])
        for user in ("bob; id", "a b", "$(id)", "", "Bob", "-x", None, "a" * 40):
            self.assertEqual(S.groups_argv(user, ["kvm"]), [], user)
        self.assertEqual(S.groups_argv("bob", ["evil"]), [])

    def test_services_command(self):
        self.assertEqual(S.services_argv(["evoxd-netguard", "libvirtd", "evil.service"]),
                         ["sudo", "systemctl", "enable", "--now", "libvirtd", "evoxd-netguard"])
        self.assertEqual(S.services_argv(["x"]), [])

    def test_terminal_call_is_argument_list_with_constant_script(self):
        argv = ["sudo", "apt", "install", "nftables"]
        full = S.terminal_argv(argv, lambda n: n == "gnome-terminal")
        self.assertEqual(full[:3], ["gnome-terminal", "--wait", "--"])
        self.assertEqual(full[3:6], ["bash", "-c", S.TERMINAL_SCRIPT])
        self.assertEqual(full[6:], ["bash"] + argv)
        self.assertNotIn("{", S.TERMINAL_SCRIPT)
        full2 = S.terminal_argv(argv, lambda n: n == "x-terminal-emulator")
        self.assertEqual(full2[:2], ["x-terminal-emulator", "-e"])
        self.assertIsNone(S.terminal_argv(argv, lambda n: None))
        self.assertIsNone(S.terminal_argv([], lambda n: "x"))


class LauncherTest(NoSpawnMixin, unittest.TestCase):
    def test_launcher_only_in_home(self):
        with tempfile.TemporaryDirectory() as t:
            home = os.path.realpath(t)
            os.makedirs(home + "/Desktop")
            src = home + "/evoxd.desktop"
            Path(src).write_text("[Desktop Entry]\nName=EVOX\nIcon=old\nExec=evoxd-gui\n")
            run = lambda cmd, **kw: cp(0, home + "/Desktop\n")
            msg = S.create_launcher(home, run, lambda n: None, src)
            self.assertIn("Launcher written", msg)
            text = Path(home + "/Desktop/evoxd-gui.desktop").read_text()
            self.assertIn("Icon=evoxd", text)
            self.assertNotIn("Icon=old", text)
            self.assertIn("X-EVOX-Launcher=evoxd-gui", text)
            self.assertEqual(S.create_launcher(home, lambda c, **k: cp(0, "/etc\n"), lambda n: None, src),
                             T.SETUP_LAUNCHER_NODIR)
            self.assertEqual(S.create_launcher(home, run, lambda n: None, home + "/none"), T.SETUP_LAUNCHER_NOPKG)


class GuiStateTest(NoSpawnMixin, unittest.TestCase):
    def test_setup_seen_backward_compatible(self):
        with tempfile.TemporaryDirectory() as t:
            st = Settings(state_dir=Path(t) / "st", runtime_dir=Path(t) / "rt", config_file=Path(t) / "c.json")
            self.assertFalse(st.load_gui_state()["setup_seen"])
            st.state_dir.mkdir(parents=True)
            st.gui_state_path.write_text(json.dumps({"width": 900, "height": 700}))     # alte Datei ohne Schlüssel
            self.assertFalse(st.load_gui_state()["setup_seen"])
            st.save_setup_seen()
            g = st.load_gui_state()
            self.assertTrue(g["setup_seen"])
            self.assertEqual((g["width"], g["height"]), (900, 700))
            st.save_gui_state(800, 600, False)
            self.assertTrue(st.load_gui_state()["setup_seen"])                          # bleibt erhalten
            st.gui_state_path.write_text(json.dumps({"setup_seen": "yes"}))
            self.assertFalse(st.load_gui_state()["setup_seen"])


def items_bad():
    return [S.Item(1, "pkg:nftables", False, "nftables – not installed", "why", "apt"),
            S.Item(1, "pkg:iproute2", False, "iproute2 – not installed", "why", "apt"),
            S.Item(4, "unit:evoxd-netguard", False, "svc", "why", "services"),
            S.Item(3, "group:kvm", True, "ok")]


class FakeChecker:
    def __init__(self, seq):
        self.seq = list(seq)
        self.calls = 0

    def all(self, progress=None):
        self.calls += 1
        if progress:
            for n in range(1, 7):
                progress(n)
        return self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class SetupDialogTest(GuiBase):
    def dlg(self, seq, spawn=None, which=lambda n: "/usr/bin/" + n):
        import evoxd.gui as G
        self.chk = FakeChecker(seq)
        self.spawn = spawn or mock.Mock(return_value=mock.Mock())
        d = G.SetupDialog(None, None, checker=self.chk, spawn=self.spawn, which=which, watch=False)
        d.start_check = d.check_now                      # synchron statt Hintergrund-Thread
        d.check_now()
        self.addCleanup(d.destroy)
        return d

    def test_checklist_and_buttons(self):
        d = self.dlg([items_bad()])
        self.assertEqual(len(d.fix_btns), 3)             # je ✗ ein Knopf
        self.assertIn("3 item(s)", d.summary.get_text())
        self.assertIn("Step 6 of 6", d.step_lbl.get_text())
        self.assertIs(d.get_focus(), d.cancel_btn)       # Anfangsfokus BACK
        self.assertEqual(d.get_default_widget(), d.cancel_btn)

    def test_ready_when_all_ok(self):
        d = self.dlg([[S.Item(1, "x", True, "fine")]])
        self.assertEqual(d.fix_btns, [])
        self.assertEqual(d.summary.get_text(), T.SETUP_READY)

    def test_fix_only_previews_until_confirmed(self):
        d = self.dlg([items_bad()])
        d.confirm_fix = mock.Mock(return_value=False)
        d.fix_btns[0].clicked()
        d.confirm_fix.assert_called_once_with(["sudo", "apt", "install", "nftables", "iproute2"])
        self.spawn.assert_not_called()
        self.assertFalse(d.term_open)

    def test_confirmed_fix_starts_one_terminal_and_locks(self):
        d = self.dlg([items_bad(), [S.Item(1, "x", True, "fine")]])
        d.confirm_fix = mock.Mock(return_value=True)
        d.fix_btns[0].clicked()
        self.spawn.assert_called_once()
        full = self.spawn.call_args[0][0]
        self.assertEqual(full[-5:], ["sudo", "apt", "install", "nftables", "iproute2"])
        self.assertIn(S.TERMINAL_SCRIPT, full)
        self.assertTrue(d.term_open)
        self.assertTrue(all(not b.get_sensitive() for b in d.fix_btns))
        self.assertFalse(d.recheck_btn.get_sensitive())
        d.fix_clicked(S.Item(1, "pkg:nftables", False, "x", fix="apt"))          # zweites Terminal: gesperrt
        self.spawn.assert_called_once()
        calls = self.chk.calls
        d._terminal_closed()                                                     # Fenster zu: automatische Neuprüfung
        self.assertFalse(d.term_open)
        self.assertEqual(self.chk.calls, calls + 1)
        self.assertEqual(d.fix_btns, [])
        self.assertEqual(d.summary.get_text(), T.SETUP_READY)                    # ✗ wurde ✓

    def test_no_terminal_and_spawn_error(self):
        d = self.dlg([items_bad()], which=lambda n: None)
        d.confirm_fix = mock.Mock(return_value=True)
        d.fix_btns[0].clicked()
        self.assertEqual(d.msg.get_text(), T.SETUP_NO_TERMINAL)
        self.spawn.assert_not_called()
        d2 = self.dlg([items_bad()], spawn=mock.Mock(side_effect=OSError("boom")))
        d2.confirm_fix = mock.Mock(return_value=True)
        d2.fix_btns[0].clicked()
        self.assertFalse(d2.term_open)
        self.assertIn("boom", d2.msg.get_text())

    def test_confirm_dialog_shows_command_and_defaults_to_back(self):
        import evoxd.gui as G
        c = G.FixConfirmDialog(None, ["sudo", "evoxd", "setup"])
        self.addCleanup(c.destroy)
        self.assertIn("sudo evoxd setup", c.cmd_lbl.get_text())
        self.assertIs(c.get_focus(), c.cancel_btn)
        self.assertEqual(c.get_default_widget(), c.cancel_btn)

    def test_copy_report_and_launcher(self):
        d = self.dlg([items_bad()])
        clip = mock.Mock()
        with mock.patch.object(Gtk.Clipboard, "get", return_value=clip):
            d.copy_report()
        clip.set_text.assert_called_once_with(S.report(d.items), -1)
        d.make_launcher = lambda: "Launcher written: /x"
        d.launcher_btn.clicked()
        self.assertIn("Launcher written", d.msg.get_text())
        self.assertIn("Add to panel", d.msg.get_text())

    def test_threaded_check_posts_result(self):
        import evoxd.gui as G
        from gi.repository import GLib
        d = G.SetupDialog(None, None, checker=FakeChecker([items_bad()]), watch=False)
        self.addCleanup(d.destroy)
        d.start_check()
        ctx = GLib.MainContext.default()
        for _ in range(200):
            while ctx.iteration(False):
                pass
            if d.items:
                break
            import time
            time.sleep(0.01)
        self.assertEqual(len(d.items), 4)


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class MainWindowSetupTest(GuiBase):
    def test_button_status_and_tooltip(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        self.addCleanup(w.destroy)
        self.assertEqual(w.setup_btn.get_label(), "Setup check")
        self.assertTrue(w.setup_btn.get_tooltip_text())
        self.assertEqual(w.status_texts[w.setup_btn], T.STATUS_SETUP)
        self.assertTrue(w.setup_btn.get_can_focus())
        self.assertIn("evox-fn-aux", w.setup_btn.get_style_context().list_classes())     # Hilfsknopf-Farbe

    def test_first_start_opens_dialog_once(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        self.addCleanup(w.destroy)
        opened = []

        class Fake:
            def __init__(self, parent, ev):
                opened.append(1)
            def start_check(self): pass
            def run(self): return Gtk.ResponseType.CANCEL
            def destroy(self): pass
        orig = w.show_setup
        w.show_setup = lambda: orig(dialog_cls=Fake)
        self.assertFalse(self.ev.s.load_gui_state()["setup_seen"])
        w.startup_setup_check(checker=FakeChecker([items_bad()]), sync=True)
        self.assertEqual(opened, [1])
        self.assertTrue(self.ev.s.load_gui_state()["setup_seen"])
        w.startup_setup_check(checker=FakeChecker([[S.Item(1, "x", True, "ok")]]), sync=True)
        self.assertEqual(opened, [1])                                 # kein zweiter Dialog

    def test_normal_start_shows_bar_not_dialog(self):
        import evoxd.gui as G
        self.ev.s.save_setup_seen(True)
        w = G.MainWindow(self.ev)
        self.addCleanup(w.destroy)
        w.show_setup = mock.Mock()
        w.startup_setup_check(checker=FakeChecker([items_bad()]), sync=True)
        w.show_setup.assert_not_called()
        self.assertTrue(w.setup_bar.get_visible())
        self.assertIn("3 item(s)", w.setup_bar_lbl.get_text())
        w.setup_bar.hide()
        w.startup_setup_check(checker=FakeChecker([[S.Item(1, "x", True, "ok")]]), sync=True)
        self.assertFalse(w.setup_bar.get_visible())
        w.startup_setup_check(checker=FakeChecker([[S.Item(1, "internet", False, "no net"),
                                                    S.Item(2, "ram", False, "low")]]), sync=True)
        self.assertFalse(w.setup_bar.get_visible())                   # Internet/RAM allein lösen keinen Balken aus

    def test_fallback_without_libvirt_opens_dialog_without_evox(self):
        import evoxd.gui as G
        with mock.patch.object(G, "SetupDialog") as sd:
            G.offer_setup_without_libvirt()
        sd.assert_called_once_with(None, None)
        sd.return_value.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
