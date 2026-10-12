"""0.6.14: Flackern – bei unverändertem Datenstand darf ein 5-s-Zyklus KEINE GTK-Aufrufe mehr auslösen (nur GUI).
Gezählt werden die echten GTK-Aufrufe über Attrappen (Wrapper um die Gtk-Methoden), nicht nur der Trace."""
import contextlib
import io
import os
import tempfile
import time
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from evoxd.config import Settings
from evoxd.lifecycle import Evox
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor
from tests.nospawn import NoSpawnMixin

HAVE_DISPLAY = Gtk.init_check([])[0]

# (Klasse, Methode) -> Aufrufart im Bericht
WATCH = [(Gtk.Widget, "set_sensitive", "set_sensitive"), (Gtk.Widget, "set_tooltip_text", "tooltip"),
         (Gtk.Widget, "queue_draw", "queue_draw"), (Gtk.Widget, "grab_focus", "focus"),
         (Gtk.Widget, "show", "show_hide"), (Gtk.Widget, "hide", "show_hide"), (Gtk.Widget, "set_visible", "show_hide"),
         (Gtk.Label, "set_text", "set_text"), (Gtk.Label, "set_markup", "set_markup"),
         (Gtk.Label, "set_label", "set_text"),
         (Gtk.StyleContext, "add_class", "css_class"), (Gtk.StyleContext, "remove_class", "css_class"),
         (Gtk.CssProvider, "load_from_data", "css_load"),
         (Gtk.StyleContext, "add_provider_for_screen", "css_add_provider"),
         (Gtk.ListStore, "clear", "list_rebuild"), (Gtk.ListStore, "append", "list_rebuild"),
         (Gtk.ListStore, "set_value", "list_cell"),
         (Gtk.TreeSelection, "select_iter", "select"), (Gtk.TreeSelection, "select_path", "select"),
         (Gtk.TreeSelection, "unselect_all", "select"), (Gtk.Stack, "set_visible_child_name", "stack_child"),
         (Gtk.ToggleButton, "set_active", "toggle")]


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class CycleTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        s = Settings(state_dir=d / "st", runtime_dir=d / "rt", guard_status=d / "x", config_file=d / "cfg.json")
        self.hv = FakeHypervisor()
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.hv.add_vault("VAULT-MAIL")
        self.reg = Registry(s.registry_path)
        self.ev = Evox(s, self.hv, self.reg, net_check=lambda: (True, ""),
                       meminfo=lambda: {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20})
        self.ev.import_template("TEMPLATE-MAIL")
        self.ev.start("TEMPLATE-MAIL")
        self.calls = Counter()

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    @contextlib.contextmanager
    def counting(self):
        patches = []
        for cls, name, kind in WATCH:
            orig = getattr(cls, name)

            def wrap(*a, _o=orig, _k=kind, **kw):
                self.calls[_k] += 1
                return _o(*a, **kw)
            patches.append(mock.patch.object(cls, name, wrap))
        for p in patches:
            p.start()
        try:
            yield
        finally:
            for p in reversed(patches):
                p.stop()

    def pump(self, w):
        end = time.monotonic() + 20
        while (w.busy or w._tick_running) and time.monotonic() < end:
            Gtk.main_iteration_do(False)
            time.sleep(0.01)
        while GLib.MainContext.default().pending():
            Gtk.main_iteration_do(False)

    def cycle(self, w):
        w._tick()
        self.pump(w)

    def window(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))   # eine VM markiert (Detailleiste sichtbar)
        self.cycle(w)
        self.cycle(w)                                                              # Zustand eingeschwungen
        return w

    def test_unchanged_cycle_makes_no_gtk_calls(self):
        w = self.window()
        sel_vault = w.selected_vault()["name"]
        sel_temp = w.selected()
        with self.counting():
            self.calls.clear()
            self.cycle(w)
            self.cycle(w)
        self.assertEqual(dict(self.calls), {}, "unnötige GTK-Aufrufe im unveränderten Zyklus")
        self.assertEqual(w.selected_vault()["name"], sel_vault)                    # Auswahl bleibt
        self.assertEqual(w.selected(), sel_temp)
        self.assertTrue(w.make_btn.get_sensitive())
        w.destroy()

    def test_tick_does_not_toggle_buttons(self):
        """Ursache des Flackerns bis 0.6.13: der Zeitgeber schaltete alle Aktionsknöpfe (auch Make template) aus/ein."""
        w = self.window()
        states = []
        orig = Gtk.Widget.set_sensitive
        with mock.patch.object(Gtk.Widget, "set_sensitive", lambda self_, v: (states.append((self_, v)), orig(self_, v))[1]):
            self.cycle(w)
        self.assertEqual([x for x in states if x[0] is w.make_btn], [])
        self.assertEqual(states, [])
        w.destroy()

    def test_user_action_still_disables_buttons_and_restores(self):
        w = self.window()
        seen = []
        orig = Gtk.Widget.set_sensitive
        with mock.patch.object(Gtk.Widget, "set_sensitive", lambda self_, v: (seen.append((self_, v)), orig(self_, v))[1]):
            w._run(lambda: None).join(20)
            self.pump(w)
        self.assertIn((w.make_btn, False), seen)                                   # Benutzeraktion: Knöpfe aus ...
        self.assertTrue(w.make_btn.get_sensitive())                                # ... und danach wieder an
        self.assertFalse(w.busy)
        w.destroy()

    def test_real_change_still_updates(self):
        w = self.window()
        self.ev.start("TEMPLATE-MAIL")
        self.cycle(w)
        self.assertEqual(len(w.store), 2)
        self.assertEqual(w.selected(), w.store[0][0])
        w.destroy()

    def test_css_loaded_once(self):
        import evoxd.gui as G
        G._css_done = False
        with self.counting():
            w = G.MainWindow(self.ev)
            self.cycle(w)
            self.cycle(w)
            G.apply_css()
        self.assertEqual(self.calls["css_load"], 1)
        self.assertEqual(self.calls["css_add_provider"], 1)
        w.destroy()

    def test_trace_off_by_default_and_on_with_env(self):
        import evoxd.gui as G
        err = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=False), contextlib.redirect_stderr(err):
            os.environ.pop(G.TRACE_ENV, None)
            G.TRACE_COUNTS.clear()
            w = self.window()
            self.assertEqual(err.getvalue(), "")                                   # ohne Variable: keine Ausgabe
            self.assertEqual(dict(G.TRACE_COUNTS), {})                             # ... und kein Zählen
            w.destroy()
        err = io.StringIO()
        with mock.patch.dict(os.environ, {G.TRACE_ENV: "1"}), contextlib.redirect_stderr(err):
            w = self.window()
            err.truncate(0)
            err.seek(0)
            self.cycle(w)
            out = err.getvalue()
            w.destroy()
        self.assertIn("=== Zyklus", out)
        self.assertIn("(keine Aufrufe)", out)                                      # unveränderter Zyklus: nichts protokolliert

    def test_trace_logs_real_changes(self):
        import evoxd.gui as G
        err = io.StringIO()
        with mock.patch.dict(os.environ, {G.TRACE_ENV: "1"}), contextlib.redirect_stderr(err):
            w = self.window()
            err.truncate(0)
            err.seek(0)
            self.ev.start("TEMPLATE-MAIL")
            self.cycle(w)
            out = err.getvalue()
            w.destroy()
        self.assertIn("list_rebuild temp", out)
        self.assertIn("selection_changed", out)


if __name__ == "__main__":
    unittest.main()
