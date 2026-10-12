"""0.7.5: Neongrün statt Lila (Titel bleibt Lila), Titel eine Zeile tiefer und zentriert, EXIT-Knopf mit
Bestätigungsdialog (drei Wege). Nur Attrappen (FakeHypervisor, nospawn), kein echtes libvirt."""
import re
import time
import unittest
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

import evoxd.gui as G
from evoxd import texts as T
from evoxd.errors import EvoxError
from tests.nospawn import NoSpawnMixin
from tests.test_a3b import HAVE_DISPLAY, GuiBase
from tests.test_a3e import MonitorZeroCallsTest, key, pump
from tests.test_selcolor import contrast
from tests.test_live import raw

def buttons(widget):
    out = []
    if isinstance(widget, Gtk.Button):
        out.append(widget)
    if isinstance(widget, Gtk.Container):
        for c in widget.get_children():
            out.extend(buttons(c))
    return out


PURPLE_RE = re.compile(r"b026ff|8c00ff|7a1fd0|d58cff|e6ccff", re.I)


class ColorTest(NoSpawnMixin, unittest.TestCase):
    def test_constant_and_assignment(self):
        self.assertEqual(G.NEON_GREEN, "#39D353")
        for c in (G.TAB_DISPOSABLE_COLOR, G.VMNAME_COLOR, G.NAME_COLOR, G.SELECT_GREEN, G.STEP4_INTERNET_GLOW):
            self.assertEqual(c, G.NEON_GREEN)
        self.assertEqual(G.TAB_COLORS["disposable"], G.NEON_GREEN)
        self.assertEqual(G.HOWTO_CLASSES[3], "evox-start-disposable")
        self.assertEqual(G.STEP4_INTERNET_RING, "#9BF5AE")
        self.assertEqual((G.STEP4_OFFLINE_RING, G.STEP4_OFFLINE_GLOW), ("#4DA3FF", "#0060b3"))      # OFFLINE bleibt Blau
        self.assertEqual(G.MODE_OFFLINE, "#0060b3")

    def test_css_rules_per_element(self):
        css = " ".join(G.CSS.split())
        self.assertIn(f".evox-start-disposable {{ background-image: none; background-color: #39D353; "
                      f"color: {G.DISPOSABLE_TEXT}; border: 2px solid {G.DISPOSABLE_BORDER}; }}", css)   # Reiter, Hauptknopf, HOW-TO 4, Dialog-Start
        self.assertIn(".evox-tabbtn-disposable:not(:checked) { background-color: rgba(57, 211, 83, 0.28)", css)
        self.assertIn(".evox-vmname { font-size: 26pt; font-weight: bold; color: #39D353; }", css)
        self.assertIn(".evox-next.evox-start-disposable { box-shadow: 0 0 0 2px #9BF5AE, 0 0 10px 3px #39D353; }", css)
        self.assertIn(".evox-next.evox-start-offline { box-shadow: 0 0 0 2px #4DA3FF, 0 0 10px 3px #0060b3; }", css)
        self.assertIn("treeview.view.evox-sel-green:selected { background-color: #39D353; background-image: none; "
                      f"color: {G.SELECT_GREEN_TEXT}; }}", css)
        self.assertEqual(G.SELECT_STYLES["green"][1], G.DISPOSABLE_TEXT)

    def test_no_purple_except_title(self):
        hits = [l for l in G.CSS.splitlines() if PURPLE_RE.search(l)]
        self.assertEqual(len(hits), 1, hits)
        self.assertIn(".evox-title", hits[0])
        self.assertIn("color: #8c00ff; text-shadow: 0 0 8px #8c00ff;", hits[0])
        # 0.8.0: Farben stehen in theme.py; im Theme Dark ist die Titelrolle die einzige Lila-Stelle, gui.py hat keine
        with open(G.__file__, encoding="utf-8") as f:
            self.assertEqual(PURPLE_RE.findall(f.read()), [])
        self.assertEqual([k for k, v in G.theme.DARK.items() if PURPLE_RE.search(v)], ["title"])
        self.assertEqual(G.TITLE_COLOR, "#8c00ff")
        self.assertNotIn("purple", G.SELECT_STYLES)

    def test_verify_is_blue_grey_not_start_like(self):
        bg = G.FN_COLORS["verify"][0]
        self.assertEqual(bg, "#4A6F94")
        r, g, b = (int(bg[i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(b, g)
        self.assertGreater(g, r)                                              # bläulich
        self.assertLess(g, 0x90)                                              # nicht grün
        self.assertGreaterEqual(contrast(bg, "#ffffff"), 4.5)

    def test_contrasts(self):
        self.assertGreaterEqual(contrast(G.NEON_GREEN, G.DISPOSABLE_TEXT), 8)            # 8,65
        self.assertGreaterEqual(contrast(G.NEON_GREEN, G.SELECT_STYLES["green"][2]), 7)  # Ersatz für rote Schrift: 7,3
        self.assertGreaterEqual(contrast(G.FOCUS_INNER, G.NEON_GREEN), 9)                # 9,99
        self.assertLess(contrast(G.FOCUS_COLOR, G.NEON_GREEN), 2)                        # Limette allein trennt NICHT (1,67)
        self.assertGreaterEqual(contrast(G.FOCUS_INNER, G.FOCUS_COLOR), 16)              # Innenrand trennt Limette und Grün

    def test_no_collision_with_mode_green(self):
        self.assertEqual(G.MODE_INTERNET, "#1FA855")
        self.assertNotEqual(G.NEON_GREEN.lower(), G.MODE_INTERNET.lower())
        for c in (G.STEP4_INTERNET_RING, G.DISPOSABLE_BORDER, G.SELECT_GREEN):
            self.assertNotEqual(c.lower(), G.MODE_INTERNET.lower())
        self.assertIn(".evox-bar-internet { background-color: #1FA855; }", G.CSS)       # Kopfleiste bleibt
        self.assertIn(".evox-dlg-internet { border: 1px solid #1FA855; }", G.CSS)

    def test_names_green_in_remove_dialog(self):
        self.assertEqual(G.NAME_COLOR, "#39D353")


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class ColorWidgetTest(GuiBase):
    def test_start_dialog_internet_and_name(self):
        w = self.window()
        for offline, cls in ((False, "evox-start-disposable"), (True, "evox-start-offline")):
            d = G.StartDialog(w, self.ev, "TEMPLATE-MAIL", offline=offline)
            self.assertTrue(d.ok_btn.get_style_context().has_class(cls))
            d.destroy()
        d = G.StartDialog(w, self.ev, "TEMPLATE-MAIL")
        self.assertTrue(d.name_lbl.get_style_context().has_class("evox-vmname"))
        d.destroy()
        self.assertTrue(w.tabs.buttons["disposable"].get_style_context().has_class("evox-start-disposable"))
        self.assertTrue(w.howto_btns[3].get_style_context().has_class("evox-start-disposable"))
        self.assertTrue(w.howto_btns[4].get_style_context().has_class("evox-start-offline"))
        self.assertTrue(w.verify_btn.get_style_context().has_class("evox-fn-verify"))
        self.assertTrue(w.view.get_style_context().has_class("evox-sel-green"))
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class TitleLayoutTest(GuiBase):
    def test_title_centered_below_button_row(self):
        w = self.window()
        w.show_all()
        pump(0.4)
        width = w.get_size()[0]
        t, tg = w.title.get_allocation(), w.tagline.get_allocation()
        self.assertEqual(w.title.get_xalign(), 0.5)
        self.assertEqual(w.title.get_justify(), Gtk.Justification.CENTER)
        self.assertAlmostEqual(t.x + t.width / 2, tg.x + tg.width / 2, delta=1)         # mittig über der Tagline
        self.assertAlmostEqual(t.x + t.width / 2, width / 2, delta=2)                  # und zum Fenster
        self.assertGreater(t.y, w.exit_btn.get_allocation().y + w.exit_btn.get_allocation().height - 1)  # unter der Knopfzeile
        self.assertLess(t.y + t.height, tg.y + 1)                                       # Tagline bleibt darunter
        self.assertEqual(tuple(w.get_size_request()), G.MIN_SIZE)                       # Mindestgröße unverändert
        w.destroy()

    def test_window_size_stable_with_exit_dialog(self):
        w = self.window(raw())
        w.show_all()
        pump(0.3)
        base = tuple(w.get_size())
        with mock.patch.object(G.ExitDialog, "run", lambda self: Gtk.ResponseType.CANCEL):
            w.on_exit()
        pump(0.1)
        w.refresh()
        pump(0.1)
        self.assertEqual(tuple(w.get_size()), base)
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class ExitButtonTest(GuiBase):
    def test_button_texts_status_focus(self):
        w = self.window()
        w.show_all()
        pump(0.3)
        b = w.exit_btn
        self.assertEqual((b.get_label(), b.get_tooltip_text()), (T.BTN_EXIT, T.BTN_EXIT_TIP))
        self.assertTrue(b.get_style_context().has_class("evox-fn-exit"))
        self.assertTrue(b.get_can_focus())
        self.assertEqual(w.status_text(b), T.STATUS_EXIT)
        self.assertIn("evox-fn-exit {", G.CSS)
        self.assertEqual(G.FN_COLORS["exit"][0], G.CANCEL_COLOR)                        # gedämpftes Rot
        self.assertGreater(b.get_allocation().x, w.fullscreen_btn.get_allocation().x)   # ganz rechts
        for n in ("BTN_EXIT", "BTN_EXIT_TIP", "STATUS_EXIT", "EXIT_TITLE_VMS", "EXIT_TEXT_VMS", "EXIT_TITLE_NONE",
                  "EXIT_TEXT_NONE", "EXIT_KEEP", "EXIT_ERASE", "EXIT_CONFIRM", "MSG_EXIT_ERASING", "MSG_EXIT_FAILED"):
            self.assertTrue(hasattr(T, n) and hasattr(T, "DE_" + n), n)
        self.assertEqual(T.EXIT_KEEP, "KEEP VMs RUNNING")
        self.assertEqual(T.EXIT_ERASE, "SHUT DOWN & ERASE VMs")
        w.destroy()

    def test_click_opens_dialog_and_window_x_unchanged(self):
        w = self.window()
        runs = []
        with mock.patch.object(G.ExitDialog, "run", lambda self: (runs.append(1), Gtk.ResponseType.CANCEL)[1]):
            w.exit_btn.clicked()
            self.assertEqual(runs, [1])
            ev = Gdk.Event.new(Gdk.EventType.DELETE)
            self.assertFalse(w.emit("delete-event", ev))                                # X: wie bisher, kein EXIT-Dialog
            self.assertEqual(runs, [1])
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class ExitDialogTest(GuiBase):
    def setUp(self):
        super().setUp()
        self.seen = []

    def run_with(self, w, resp):
        """ExitDialog.run ersetzen: Anfangszustand festhalten, dann die vorgegebene Antwort liefern."""
        def fake(dlg):
            self.seen.append(dlg)
            self.focus = dlg.get_focus()
            self.default = dlg.get_default_widget()
            self.labels = [b.get_label() for b in buttons(dlg)]
            return resp
        with mock.patch.object(G.ExitDialog, "run", fake):
            return w.on_exit()

    def join(self, t):
        if t is not None:
            t.join(20)
        end = time.monotonic() + 3
        while time.monotonic() < end:
            Gtk.main_iteration_do(False)
            time.sleep(0.005)

    def watch_destroy(self, w):
        flag = []
        w.connect("destroy", lambda *_: flag.append(1))
        return flag

    def test_dialog_with_vms_names_count_buttons_focus(self):
        w = self.window()
        self.ev.start("TEMPLATE-MAIL", purpose="WEB")
        names = sorted(t["name"] for t in self.ev.list_temps())
        self.run_with(w, Gtk.ResponseType.CANCEL)
        d = self.seen[0]
        self.assertEqual(d.names, names)
        self.assertIn("2", d.get_title())
        for n in names:
            self.assertIn(n, d.text.get_label())
        self.assertEqual(self.labels,
                         [T.BACK, T.EXIT_KEEP, T.EXIT_ERASE])
        self.assertIs(self.focus, d.cancel_btn)                                         # Anfangsfokus ← BACK
        self.assertIs(self.default, d.cancel_btn)
        self.assertTrue(d.keep_btn.get_style_context().has_class("evox-fn-neutral"))    # Blau-Grau
        self.assertTrue(d.erase_btn.get_style_context().has_class("evox-danger"))       # Gefahrrot
        w.destroy()

    def test_dialog_without_vm(self):
        w = self.window()
        self.ev.stop(self.name)
        self.run_with(w, Gtk.ResponseType.CANCEL)
        d = self.seen[0]
        self.assertEqual((d.get_title(), d.names), (T.EXIT_TITLE_NONE, []))
        self.assertEqual(self.labels, [T.BACK, T.EXIT_CONFIRM])
        self.assertIs(self.focus, d.cancel_btn)
        w.destroy()

    def test_enter_right_after_open_does_nothing_and_esc_is_back(self):
        w = self.window()
        for esc in (False, True):
            got = []
            d = G.ExitDialog(w, self.ev.reg and ["DISPOSABLE-WEB-01"])
            d.connect("response", lambda _d, r: got.append(r))
            self.assertIs(d.get_focus(), d.cancel_btn)                                  # Enter trifft nur ← BACK
            self.assertIs(d.get_default_widget(), d.cancel_btn)
            if esc:
                d.emit("key-press-event", key(Gdk.KEY_Escape))
            else:
                d.get_focus().clicked()                                                 # Enter direkt nach dem Öffnen
            self.assertEqual(got, [Gtk.ResponseType.CANCEL])
            d.destroy()
        d = G.ExitDialog(w, [])
        got = []
        d.connect("response", lambda _d, r: got.append(r))
        self.assertIs(d.get_focus(), d.cancel_btn)
        d.get_focus().clicked()
        self.assertEqual(got, [Gtk.ResponseType.CANCEL])                                # auch ohne VM löst Enter nichts aus
        d.destroy()
        w.destroy()

    def test_back_does_nothing(self):
        w = self.window()
        gone = self.watch_destroy(w)
        with mock.patch.object(self.ev, "stop", wraps=self.ev.stop) as stop:
            self.assertIsNone(self.run_with(w, Gtk.ResponseType.CANCEL))
        self.assertEqual((stop.call_count, gone), (0, []))
        self.assertEqual(len(self.ev.list_temps()), 1)
        w.destroy()

    def test_keep_closes_only_gui(self):
        w = self.window()
        gone = self.watch_destroy(w)
        w.details_btn.clicked()
        mon = w.monitor
        with mock.patch.object(self.ev, "stop", wraps=self.ev.stop) as stop:
            self.assertIsNone(self.run_with(w, G.EXIT_KEEP))
        self.assertEqual((stop.call_count, gone), (0, [1]))
        self.assertEqual([t["name"] for t in self.ev.list_temps()], [self.name])        # VM läuft weiter
        self.assertIsNone(w._tick_id)                                                   # Zeitgeber beendet
        self.assertIsNotNone(mon)                                                       # Monitor war offen ...
        self.assertIsNone(w.monitor)                                                    # ... und ist mit der GUI geschlossen

    def test_gui_state_saved_on_quit(self):
        self.ev.s.save_gui_state(1234, 800, False, None)
        w = self.window()
        w.show_all()
        pump(0.3)
        size = tuple(w.get_size())
        self.ev.s.save_gui_state(1, 1, False, None)                                     # Platzhalter, muss überschrieben werden
        self.run_with(w, G.EXIT_KEEP)
        st = self.ev.s.load_gui_state()                                                 # gemerkter Zustand wurde geschrieben
        self.assertEqual((st["width"], st["height"]), size)

    def test_erase_only_disposable_never_vault_or_template(self):
        self.hv.add_vault("VAULT-MAIL")
        w = self.window()
        self.ev.start("TEMPLATE-MAIL", purpose="WEB")
        gone = self.watch_destroy(w)
        before = {n for n in self.hv.domains} if hasattr(self.hv, "domains") else None
        with mock.patch.object(self.ev, "stop", wraps=self.ev.stop) as stop:
            t = self.run_with(w, G.EXIT_ERASE)
            self.join(t)
        called = sorted(c.args[0] for c in stop.call_args_list)
        self.assertEqual(len(called), 2)
        for n in called:
            self.assertRegex(n, r"DISPOSABLE-[A-Z0-9]{1,16}-[0-9]{2}")
            self.assertFalse(n.startswith(("VAULT", "TEMPLATE")))
        self.assertEqual(self.ev.list_temps(), [])
        self.assertIsNotNone(self.hv.domain_xml("VAULT-MAIL"))                          # Vault unberührt
        self.assertIsNotNone(self.hv.domain_xml("TEMPLATE-MAIL"))                       # Original-Template unberührt
        self.assertEqual(gone, [1])                                                     # danach schließt die GUI
        if before is not None:
            self.assertTrue({"VAULT-MAIL", "TEMPLATE-MAIL"} <= set(self.hv.domains))

    def test_candidates_ignore_non_disposable_names(self):
        w = self.window()
        rows = [{"name": "VAULT-X-01"}, {"name": "TEMPLATE-Y-01"}, {"name": "DISPOSABLE-WEB-02"}, {"name": "DISPOSABLE-bad"}]
        with mock.patch.object(self.ev, "list_temps", return_value=rows):
            self.assertEqual(w.exit_candidates(), ["DISPOSABLE-WEB-02"])
        w.destroy()

    def test_erase_error_keeps_gui_open_and_names_failure(self):
        w = self.window()
        self.ev.start("TEMPLATE-MAIL", purpose="WEB")
        bad = sorted(t["name"] for t in self.ev.list_temps())[0]
        real = self.ev.stop
        gone = self.watch_destroy(w)

        def stop(name):
            if name == bad:
                raise EvoxError("kaputt")
            return real(name)
        with mock.patch.object(self.ev, "stop", side_effect=stop):
            t = self.run_with(w, G.EXIT_ERASE)
            self.join(t)
        self.assertEqual(gone, [])                                                      # GUI bleibt offen
        text = w.msg.get_text() or w.msg.get_label()
        self.assertIn(bad, text)
        self.assertIn("kaputt", text)
        self.assertEqual([t["name"] for t in self.ev.list_temps()], [bad])              # die andere VM wurde gelöscht
        w.destroy()

    def test_no_vm_exit_closes_back_does_not(self):
        w = self.window()
        self.ev.stop(self.name)
        gone = self.watch_destroy(w)
        self.run_with(w, Gtk.ResponseType.CANCEL)
        self.assertEqual(gone, [])
        self.run_with(w, Gtk.ResponseType.OK)
        self.assertEqual(gone, [1])


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class ExitZeroCallsTest(GuiBase):
    counted = MonitorZeroCallsTest.counted

    def test_unchanged_cycle_zero_calls(self):
        w = self.window(raw())
        self.assertEqual(self.counted(w, live=False), {})
        self.assertEqual(self.counted(w), {})
        w.destroy()


if __name__ == "__main__":
    unittest.main()
