"""0.6.16/0.6.17: Doppelrand-Fokus (Orchidee), Statuszeile unten (nur Darstellung). Sichtbarkeit auf echtem Theme, Schein,
Lesbarkeit der Statuszeile sind [U] (HOST-SCHRITTE.md, G29)."""
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

import evoxd.gui as G
from evoxd import texts as T
from evoxd.config import Settings
from evoxd.lifecycle import Evox
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor
from tests.nospawn import NoSpawnMixin
from tests.test_keys import focus_in, key, pump

HAVE_DISPLAY = Gtk.init_check([])[0]


class FocusCssTest(unittest.TestCase):
    def test_double_border_and_glow_constants(self):
        css = G.FOCUS_CSS
        self.assertEqual((G.FOCUS_INNER_PX, G.FOCUS_OUTER_PX, G.FOCUS_GLOW_PX), (2, 4, 8))
        self.assertIn(f"outline-width: {G.FOCUS_OUTER_PX}px", css)                       # außen FOCUS_COLOR
        self.assertIn(f"inset 0 0 0 {G.FOCUS_OUTER_PX + G.FOCUS_INNER_PX}px {G.FOCUS_INNER}", css)   # innen dunkel
        self.assertIn(f"0 0 {G.FOCUS_GLOW_PX}px", css)                                   # weicher Schein
        self.assertIn(G.FOCUS_COLOR, css)
        for sel in (".evox-next:focus", "list row:focus", "entry:focus", ".evox-chip:focus", "radiobutton:focus"):
            self.assertIn(sel, css)
        self.assertNotIn("animation", css)                                               # kein Blinken
        self.assertNotIn("transition", css)

    def test_text_catalog_has_german_twins(self):
        for name in ("STATUS_DEFAULT", "STATUS_LOCKED", "STATUS_TABS", "STATUS_HOWTO", "STATUS_MAKE", "STATUS_STOP"):
            self.assertTrue(getattr(T, name))
            self.assertTrue(getattr(T, "DE_" + name))
        self.assertEqual(len(T.STATUS_HOWTO), len(T.DE_STATUS_HOWTO), 5)


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class FocusLineTest(NoSpawnMixin, unittest.TestCase):
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

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def win(self):
        w = G.MainWindow(self.ev)
        w.show_all()
        pump()
        focus_in(w)
        return w

    def test_default_text_without_focus(self):
        w = self.win()
        w.set_focus(None)
        pump()
        self.assertEqual(w.focusline.get_text(), T.STATUS_DEFAULT)
        self.assertTrue(w.focusline.get_visible())
        self.assertIs(w.focusline.get_parent().get_parent(), w)
        kids = w.focusline.get_parent().get_children()
        self.assertIs(kids[-1], w.focusline)                                           # ganz unten
        w.destroy()

    def test_every_main_element_has_text(self):
        w = self.win()
        els = [w.fullscreen_btn, w.keys_btn, w.view, w.tpl_view, w.vault_view, w.base_combo, w.start_btn,
               w.start_offline_btn, w.console_btn, w.stop_btn, w.import_btn, w.verify_btn, w.remove_btn,
               w.verify_chk, w.make_btn, w.virt_manager_btn, w.hint_close, w.cancel_copy_btn, w.details_btn,
               *w.howto_btns, *w.tabs.buttons.values()]
        texts = set()
        for e in els:
            self.assertIn(e, w.status_texts)
            t = w.status_text(e)
            self.assertTrue(t.strip(), e)
            texts.add(t)
        self.assertEqual(len(texts), len(els))                                         # je Element ein eigener Text
        self.assertNotEqual(w.status_text(w.howto_btns[3]), w.status_text(w.howto_btns[4]))
        # jedes sichtbare Knopf-/Listen-Element des Hauptfensters ist abgedeckt
        def walk(x):
            yield x
            if isinstance(x, Gtk.Container):
                for c in x.get_children():
                    yield from walk(c)
        for x in walk(w):
            if isinstance(x, (Gtk.Button, Gtk.TreeView, Gtk.ComboBox)) and x.get_can_focus() \
                    and not isinstance(x.get_parent(), Gtk.ComboBox) and x.get_toplevel() is w:
                cur = x
                while cur is not None and cur not in w.status_texts:
                    cur = cur.get_parent()
                self.assertIsNotNone(cur, x)
        w.destroy()

    def test_focus_sets_text_and_locked_names_reason(self):
        w = self.win()
        w.keys_btn.grab_focus()
        pump()
        self.assertEqual(w.focusline.get_text(), T.STATUS_KEYS)
        w.make_btn.grab_focus()
        pump()
        self.assertEqual(w.focusline.get_text(), T.STATUS_MAKE)
        w.set_focus(None)
        pump()
        # gesperrt (Hover zeigt den Text, Fokus geht nicht): Grund aus dem Tooltip
        w.stop_btn.set_sensitive(False)
        self.assertIn(T.BTN_STOP_TIP_NONE, w.status_text(w.stop_btn))
        self.assertIn(T.STATUS_LOCKED.format(reason=T.BTN_STOP_TIP_NONE), w.status_text(w.stop_btn))
        w._on_hover(w.stop_btn, None, w.stop_btn)
        self.assertIn(T.BTN_STOP_TIP_NONE, w.focusline.get_text())
        w._on_hover(w.stop_btn, None, None)
        self.assertEqual(w.focusline.get_text(), T.STATUS_DEFAULT)
        # gesperrter HOW-TO-Schritt 4 ohne Template
        w.howto_btns[3].set_sensitive(False)
        w.howto_btns[3].set_tooltip_text(T.HOWTO_TIP_NO_TEMPLATE)
        self.assertIn(T.HOWTO_TIP_NO_TEMPLATE, w.status_text(w.howto_btns[3]))
        w.destroy()

    def test_no_arrow_mark_and_labels_plain(self):
        self.assertFalse(hasattr(G, "FOCUS_MARK") or hasattr(G, "focus_mark") or hasattr(G, "FOCUS_MINT"))
        w = self.win()
        for b in (w.tabs.buttons["vault"], w.howto_btns[0]):
            self.assertNotIn("\u25b6", b.get_child().get_text())                          # keine ▶-Marke
            self.assertFalse(b.get_child().get_use_markup())                              # Beschriftung wie vor 0.6.16
            self.assertEqual(b.get_child().get_text(), b.get_label())
            w.set_focus_visible(True)
            b.grab_focus()
            pump()
            self.assertEqual(b.get_child().get_text(), b.get_label())
        w.destroy()

    def test_focus_color_single_value(self):
        self.assertEqual(G.FOCUS_COLOR, "#C6FF00")
        self.assertEqual(G.CSS.count(G.FOCUS_COLOR), G.FOCUS_CSS.count(G.FOCUS_COLOR))   # nur in FOCUS_CSS
        self.assertNotIn("#2CFFB0", G.CSS.upper())                                         # kein Mint mehr
        for c in (G.TITLE_COLOR, G.TAB_DISPOSABLE_COLOR, G.MODE_INTERNET, G.SELECT_AMBER, G.ACCENT):
            self.assertNotEqual(c.upper(), G.FOCUS_COLOR.upper())                        # keine Kollision mit Funktionsfarben

    def test_line_triggers_no_action(self):
        w = self.win()
        calls = []
        with mock.patch.object(G.MainWindow, "on_start", lambda *a, **k: calls.append("start")), \
                mock.patch.object(G.MainWindow, "on_stop", lambda *a, **k: calls.append("stop")), \
                mock.patch.object(G.MainWindow, "on_make_template", lambda *a, **k: calls.append("make")):
            for e in (w.start_btn, w.stop_btn, w.make_btn, w.import_btn, w.tabs.buttons["template"], w.howto_btns[3]):
                e.grab_focus()
                pump()
                w._on_hover(e, None, e)
        self.assertEqual(calls, [])
        self.assertTrue(w.focusline.get_text())
        w.destroy()

    def test_cycle_keeps_focus_line_and_counter(self):
        w = self.win()
        w.tabs.buttons["template"].grab_focus()
        w.set_focus_visible(True)
        pump()
        before = (w.focusline.get_text(), w.get_focus())
        sets = Counter()
        orig = Gtk.Label.set_text

        def wrap(lbl, *a):
            if lbl is w.focusline:
                sets["n"] += 1
            return orig(lbl, *a)
        with mock.patch.object(Gtk.Label, "set_text", wrap):
            w.safe_refresh()
            w.safe_refresh()
        self.assertEqual(sets["n"], 0)
        self.assertEqual((w.focusline.get_text(), w.get_focus()), before)
        w.destroy()


if __name__ == "__main__":
    unittest.main()
