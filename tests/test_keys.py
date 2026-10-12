"""0.6.15: Tastaturbedienung – sichtbarer Fokus, Tasten, Anfangsfokus in Dialogen, Hilfefenster (nur GUI).
Sichtbarkeit des Rands auf echtem Theme und echte Tab-Reihenfolge am Host sind [U] (HOST-SCHRITTE.md, G28)."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

import evoxd.gui as G
from evoxd import texts as T
from evoxd.config import Settings
from evoxd.lifecycle import Evox
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor
from tests.nospawn import NoSpawnMixin

HAVE_DISPLAY = Gtk.init_check([])[0]
CANCEL, OK = Gtk.ResponseType.CANCEL, Gtk.ResponseType.OK


def key(keyval, state=0):
    ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    ev.keyval, ev.state = keyval, state
    return ev


def pump():
    for _ in range(30):
        while Gtk.events_pending():
            Gtk.main_iteration()


def focus_in(w):
    """Fenster als aktiv markieren (ohne Fensterverwaltung bekommt es sonst nie den Toplevel-Fokus; ohne ihn
    bleibt move-focus am ersten Element hängen)."""
    ev = Gdk.Event.new(Gdk.EventType.FOCUS_CHANGE)
    ev.focus_change.window = w.get_window()
    ev.focus_change.in_ = True
    w.event(ev)
    pump()
    assert w.has_toplevel_focus()


def wait_for(cond, secs=1.0):
    """Hauptschleife drehen, bis cond() wahr ist (GTK löst activate eines Knopfes erst nach ~250 ms aus)."""
    end = time.monotonic() + secs
    while not cond() and time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(0.01)
    return cond()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class KeysTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        s = Settings(state_dir=d / "st", runtime_dir=d / "rt", guard_status=d / "x", config_file=d / "cfg.json")
        self.hv = FakeHypervisor()
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.hv.add_vault("VAULT-MAIL")
        self.reg = Registry(s.registry_path)
        self.ev = Evox(s, self.hv, self.reg, net_check=lambda: (False, "guard not running"),
                       meminfo=lambda: {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20})
        self.ev.import_template("TEMPLATE-MAIL")

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def esc_run(self, log=None):
        """Ersatz für Dialog.run: prüft Fokus/Vorgabe, drückt Enter-Ersatz bzw. Esc und liefert die Antwort."""
        def run(dlg):
            if log is not None:
                log.append(dlg)
            got = []
            dlg.connect("response", lambda _d, r: got.append(r))
            self.assertTrue(G.dialog_key(dlg, key(Gdk.KEY_Escape)))
            return got[0]
        return run

    def is_cancel(self, dlg, resp=CANCEL):
        w = dlg.get_widget_for_response(resp)
        self.assertIsNotNone(w)
        return dlg.get_focus() is w and dlg.get_default_widget() is w

    # ---- 1. Fokus-CSS
    def test_focus_css_present_and_loads(self):
        self.assertEqual(G.FOCUS_COLOR, "#C6FF00")
        self.assertIn(G.FOCUS_COLOR, G.CSS)
        self.assertEqual(G.CSS.count(G.FOCUS_COLOR), G.FOCUS_CSS.count(G.FOCUS_COLOR))   # nur an der zentralen Stelle
        for sel in ("button:focus", ".evox-tabbtn:focus", ".evox-chip:focus", ".evox-howto:focus", "entry:focus",
                    "list row:focus", "spinbutton:focus"):
            self.assertIn(sel, G.FOCUS_CSS)
        self.assertIn(f"outline-width: {G.FOCUS_PX}px", G.FOCUS_CSS)
        self.assertTrue(2 <= G.FOCUS_PX <= 4)      # 0.6.16: außen 4 px (Doppelrand)
        self.assertIn(f"outline-offset: -{G.FOCUS_PX}px", G.FOCUS_CSS)                 # innen: kein Platz, kein Versatz
        css = G.FOCUS_CSS.replace("button:focus", "button:focus", 1)
        prov = Gtk.CssProvider()
        prov.load_from_data(G.CSS.encode())                                            # wirft bei Syntaxfehler
        # Fokusrand setzt weder Füllung noch Leuchtrand: .evox-next/.evox-flash (box-shadow) und Bernstein bleiben
        block = css.split("{")[1].split("}")[0]
        for forbidden in ("background", "border:", "color:" + G.SELECT_AMBER):     # 0.6.16: box-shadow = Doppelrand/Schein
            self.assertNotIn(forbidden, block)
        self.assertIn(".evox-next { box-shadow", G.CSS)
        self.assertIn(G.SELECT_AMBER, G.CSS)

    def test_focus_ring_computed_and_no_layout_shift(self):
        w = G.MainWindow(self.ev)
        # Abfrage vor dem Anzeigen: GTK3 wertet das Zustandsargument nur bei nicht realisierten Widgets aus
        for btn in [w.keys_btn, w.fullscreen_btn, *w.howto_btns, *w.tabs.buttons.values(), w.start_btn, w.stop_btn]:
            ctx = btn.get_style_context()
            self.assertEqual(ctx.get_property("outline-width", Gtk.StateFlags.FOCUSED), G.FOCUS_PX)
            self.assertEqual(ctx.get_property("outline-style", Gtk.StateFlags.FOCUSED), Gtk.BorderStyle.SOLID)
            col = ctx.get_property("outline-color", Gtk.StateFlags.FOCUSED)
            self.assertEqual(col.to_string().replace(" ", ""), "rgb(198,255,0)")
        for entry in (w.base_combo,):                                             # Listen: Rahmen am Wrapper (0.6.19)
            self.assertEqual(entry.get_style_context().get_property("outline-width", Gtk.StateFlags.FOCUSED),
                             G.FOCUS_PX)
        w.show_all()
        pump()
        b = w.keys_btn
        before = (b.get_allocated_width(), b.get_allocated_height())
        b.grab_focus()
        pump()
        self.assertEqual((b.get_allocated_width(), b.get_allocated_height()), before)    # Rand verschiebt nichts
        w.destroy()

    # ---- 3. Anfangsfokus und Esc in jedem Dialog
    def test_initial_focus_and_esc_in_every_dialog(self):
        w = G.MainWindow(self.ev)
        dlgs = [G.StartDialog(w, self.ev, "TEMPLATE-MAIL"), G.StartDialog(w, self.ev, "TEMPLATE-MAIL", offline=True),
                G.PurposeEditDialog(w, self.ev.s, ["A", "B"]), G.ImportDialog(w, self.ev),
                G.RemoveDialog(w, [dict(name="TEMPLATE-MAIL", version=1, size=1, in_use=0)]),
                G.MakeTemplateDialog(w, self.ev, self.ev.make_template_plan("VAULT-MAIL")), G.KeysDialog(w)]
        for d in dlgs:
            name = type(d).__name__
            self.assertTrue(self.is_cancel(d), name)
            got = []
            d.connect("response", lambda _d, r: got.append(r))
            self.assertTrue(G.dialog_key(d, key(Gdk.KEY_Escape)), name)
            self.assertEqual(got, [CANCEL], name)
            got.clear()
            self.assertTrue(d.activate_default(), name)                          # Enter direkt nach dem Öffnen
            wait_for(lambda: got)                                                # GTK löst den Knopf zeitversetzt aus
            self.assertEqual(got, [CANCEL], name)
            d.destroy()
        w.destroy()

    def test_initial_focus_in_message_dialogs(self):
        w = G.MainWindow(self.ev)
        self.ev.start("TEMPLATE-MAIL", purpose="A")
        w.refresh()
        w.view.get_selection().select_path(0)
        seen = []

        def run(dlg):
            seen.append((type(dlg).__name__, self.is_cancel(dlg, CANCEL) if dlg.get_widget_for_response(CANCEL)
                         else self.is_cancel(dlg, Gtk.ResponseType.NO)))
            return G.dialog_key(dlg, key(Gdk.KEY_Escape)) and CANCEL
        with mock.patch.object(Gtk.Dialog, "run", run):
            w.on_stop(None)
            self.assertTrue(w._ask("t", "x") is False)
            G.confirm_import(w, dict(name="TEMPLATE-X", backup=False, size=1, alloc=1))
        self.assertEqual(len(seen), 3)
        self.assertTrue(all(ok for _n, ok in seen), seen)
        self.assertEqual(len(self.ev.list_temps()), 1)                                # Esc: nichts gestoppt
        w.destroy()

    def test_esc_closes_dialogs_without_action(self):
        w = G.MainWindow(self.ev)
        self.ev.start("TEMPLATE-MAIL", purpose="A")
        w.refresh()
        w.view.get_selection().select_path(0)
        n_temps = len(self.ev.list_temps())
        n_bases = len(self.ev.reg.bases())
        log = []
        with mock.patch.object(Gtk.Dialog, "run", self.esc_run(log)):
            self.assertIsNone(w.on_start(None))
            self.assertIsNone(w.on_start(None, True))
            w.on_stop(None)
            w.on_import(None)
            w.tpl_view.get_selection().select_path(0)
            w.on_remove(None)
            w.tabs.set_current_page(0)
            w._select_first_vault = None
            w.vault_view.get_selection().select_path(0)
            self.assertIsNone(w.on_make_template(None))
        self.assertGreaterEqual(len(log), 6)
        self.assertEqual(len(self.ev.list_temps()), n_temps)
        self.assertEqual(len(self.ev.reg.bases()), n_bases)
        w.destroy()

    def test_enter_after_open_starts_nothing_and_name_field_only_confirms(self):
        w = G.MainWindow(self.ev)
        d = G.StartDialog(w, self.ev, "TEMPLATE-MAIL")
        got = []
        d.connect("response", lambda _d, r: got.append(r))
        entry = d.purpose.get_child()
        self.assertFalse(entry.get_activates_default())
        entry.grab_focus()
        entry.activate()                                   # Enter im Namensfeld
        self.assertEqual(got, [])                          # kein Start, keine Antwort
        d.cancel_btn.grab_focus()
        d.get_focus().activate()                           # Enter auf dem fokussierten Zurück-Knopf
        wait_for(lambda: got)
        self.assertEqual(got, [CANCEL])
        self.assertNotEqual(d.get_default_widget(), d.ok_btn)
        d.destroy()
        self.assertEqual(self.ev.list_temps(), [])
        w.destroy()

    def test_no_main_window_key_starts_or_deletes_anything(self):
        w = G.MainWindow(self.ev)
        self.ev.start("TEMPLATE-MAIL", purpose="A")
        w.refresh()
        w.view.get_selection().select_path(0)
        opened = []
        with mock.patch.object(Gtk.Dialog, "run", self.esc_run(opened)):
            for kv in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space, Gdk.KEY_Escape, Gdk.KEY_Tab, Gdk.KEY_Left,
                       Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Delete, Gdk.KEY_F1):
                w._on_key(w, key(kv))
                for b in list(w.tabs.buttons.values()) + w.howto_btns:
                    b.emit("key-press-event", key(kv)) if kv in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down) else None
        self.assertEqual([type(d).__name__ for d in opened], ["KeysDialog"])            # nur F1 öffnet etwas (Hilfe)
        self.assertEqual(len(self.ev.list_temps()), 1)
        self.assertEqual(len(self.ev.reg.bases()), 1)
        w.destroy()

    # ---- 2. Reiter, HOW-TO, F1
    def test_arrow_left_right_switch_tabs(self):
        w = G.MainWindow(self.ev)
        nb = w.tabs
        nb.set_current_page(2)
        seq = [(Gdk.KEY_Left, 1), (Gdk.KEY_Left, 0), (Gdk.KEY_Left, 0), (Gdk.KEY_Right, 1), (Gdk.KEY_Right, 2),
               (Gdk.KEY_Right, 2)]
        for kv, want in seq:
            cur = nb.buttons[G.TAB_KEYS[nb.get_current_page()]]
            self.assertTrue(cur.emit("key-press-event", key(kv)))
            self.assertEqual(nb.get_current_page(), want)
            self.assertIs(w.get_focus(), nb.buttons[G.TAB_KEYS[want]])                   # Fokus bleibt auf der Reiterzeile
        self.assertFalse(nb.buttons["vault"].emit("key-press-event", key(Gdk.KEY_a)))
        w.destroy()

    def test_arrow_up_down_between_howto_rows(self):
        w = G.MainWindow(self.ev)
        b = w.howto_btns
        for x in b:
            x.set_sensitive(True)
        path = [(0, Gdk.KEY_Down, 1), (1, Gdk.KEY_Down, 2), (2, Gdk.KEY_Down, 3), (3, Gdk.KEY_Up, 2), (4, Gdk.KEY_Up, 2),
                (2, Gdk.KEY_Up, 1), (1, Gdk.KEY_Up, 0)]
        for i, kv, want in path:
            b[i].emit("key-press-event", key(kv))
            self.assertIs(w.get_focus(), b[want], (i, kv))
        b[1].set_sensitive(False)                                                        # gesperrt: wird übersprungen
        b[0].emit("key-press-event", key(Gdk.KEY_Down))
        self.assertIs(w.get_focus(), b[2])
        w.destroy()

    def test_f1_and_keys_button_open_help_and_tooltips(self):
        w = G.MainWindow(self.ev)
        self.assertEqual(w.keys_btn.get_label(), "⌨ Keys")
        self.assertEqual(w.keys_btn.get_tooltip_text(), T.BTN_KEYS_TIP)
        self.assertTrue(w.keys_btn.get_style_context().has_class("evox-fn-aux"))
        self.assertIs(w.keys_btn.get_parent(), w.fullscreen_btn.get_parent())            # neben Fullscreen
        self.assertEqual(w.tabs.bar.get_tooltip_text(),
                         "Tip: Tab to move, arrow keys to switch tabs, Enter to select, Esc to go back.")
        for b in w.tabs.buttons.values():
            self.assertEqual(b.get_tooltip_text(), T.TABS_TIP)
        shown = []

        def run(dlg):
            shown.append(dlg)
            self.assertTrue(self.is_cancel(dlg))
            texts = " ".join(c.get_text() for c in dlg.get_content_area().get_children()[1].get_children())
            for k in ("Tab", "Shift+Tab", "Enter", "Esc", "F11"):
                self.assertIn(k, texts)
            return CANCEL
        with mock.patch.object(Gtk.Dialog, "run", run):
            self.assertTrue(w._on_key(w, key(Gdk.KEY_F1)))
            w.keys_btn.clicked()
        self.assertEqual([type(d).__name__ for d in shown], ["KeysDialog", "KeysDialog"])
        self.assertEqual(T.KEYS_TITLE, "Keyboard help")
        self.assertTrue(all(hasattr(T, f"DE_{n}") for n in ("BTN_KEYS", "BTN_KEYS_TIP", "TABS_TIP", "KEYS_TITLE",
                                                            "KEYS_ROWS", "KEYS_NOTE")))
        w.destroy()

    def test_esc_leaves_fullscreen_still(self):
        w = G.MainWindow(self.ev)
        w._fullscreen = True
        with mock.patch.object(w, "toggle_fullscreen") as tf:
            self.assertTrue(w._on_key(w, key(Gdk.KEY_Escape)))
            tf.assert_called_once()
        w._fullscreen = False
        self.assertFalse(w._on_key(w, key(Gdk.KEY_Escape)))
        w.destroy()

    # ---- Tab-Reihenfolge ohne Falle, Fokus bleibt im 5-s-Zyklus
    def chain(self, w, direction):
        """Tab/Shift+Tab wie die Tastenbelegung (Signal move-focus des Fensters). Liefert (Reihenfolge, voller Kreis):
        der Fokus muss nach einem Umlauf wieder am Anfang landen (Wrap), ohne vorher in einer Schleife zu hängen."""
        w.set_focus(None)
        seen = []
        for _ in range(120):
            w.emit("move-focus", direction)
            f = w.get_focus()
            if f is None:
                return seen, False
            if seen and f is seen[0]:
                return seen, True
            if f in seen:
                return seen, False
            seen.append(f)
        return seen, False

    def test_tab_order_complete_without_trap(self):
        self.ev.start("TEMPLATE-MAIL", purpose="A")
        w = G.MainWindow(self.ev)
        w.refresh()
        w.show_all()
        pump()
        focus_in(w)
        w.view.get_selection().select_path(0)
        pump()
        for page in range(3):
            w.tabs.set_current_page(page)
            pump()
            for direction in (Gtk.DirectionType.TAB_FORWARD, Gtk.DirectionType.TAB_BACKWARD):
                seen, ended = self.chain(w, direction)
                self.assertTrue(ended, (page, direction))
                self.assertGreater(len(seen), 8)
                must = [b for b in w.howto_btns if b.get_sensitive()] + [w.keys_btn, w.fullscreen_btn,
                                                                         w.tabs.buttons[G.TAB_KEYS[page]]]
                for m in must:
                    self.assertIn(m, seen, (page, m.get_label()))
            fwd, _ = self.chain(w, Gtk.DirectionType.TAB_FORWARD)
            bwd, _ = self.chain(w, Gtk.DirectionType.TAB_BACKWARD)
            self.assertEqual(set(fwd), set(bwd))                                         # Shift+Tab erreicht dasselbe
            idx = {id(x): i for i, x in enumerate(fwd)}                                  # Reihenfolge: HOW-TO → Reiter → Inhalt
            self.assertLess(idx[id(w.howto_btns[0])], idx[id(w.tabs.buttons[G.TAB_KEYS[page]])])
        w.tabs.set_current_page(2)
        pump()
        seen, _ = self.chain(w, Gtk.DirectionType.TAB_FORWARD)
        for m in (w.view, w.start_btn, w.start_offline_btn, w.stop_btn, w.console_btn):
            self.assertIn(m, seen, m)
        self.assertTrue(any(f.is_ancestor(w.base_combo) for f in seen))                  # Auswahl: innerer Knopf der ComboBox
        w.destroy()

    def test_cycle_keeps_focus(self):
        w = G.MainWindow(self.ev)
        w.show_all()
        pump()
        focus_in(w)
        for target in (w.keys_btn, w.tabs.buttons["template"], w.howto_btns[2], w.view):
            target.grab_focus()
            self.assertIs(w.get_focus(), target)
            w.safe_refresh()
            self.assertIs(w.get_focus(), target)
            self.ev.start("TEMPLATE-MAIL", purpose="Z")                                  # Datenstand ändert sich
            w.safe_refresh()
            pump()
            self.assertIs(w.get_focus(), target)
        w.destroy()


if __name__ == "__main__":
    unittest.main()
