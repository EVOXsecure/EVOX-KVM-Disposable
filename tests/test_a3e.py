"""0.7.4: Live Monitor als eigenes Fenster (Kurzzeile + OPEN/CLOSE DETAILS im Hauptfenster), einheitliches Zahlenformat
(eine Nachkommastelle in GB, RAM-Feld zwei), HOW TO USE zentriert, gemerkte Geometrie/Pin, Takt nur bei Bedarf –
nur Attrappen (FakeHypervisor, nospawn), kein echtes libvirt."""
import contextlib
import json
import re
import threading
import time
import unittest
from collections import Counter
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from evoxd import capacity, config, livestats
from evoxd import texts as T
from tests.nospawn import NoSpawnMixin
from tests.test_a3b import HAVE_DISPLAY, GuiBase, d
from tests.test_live import GIB_KIB, raw

SCREEN = (0, 0, 1920, 1080)


def key(keyval):
    ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
    ev.keyval, ev.state = keyval, 0
    return ev


def pump(sec=0.3):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        Gtk.main_iteration_do(False)
        time.sleep(0.005)


def source_alive(sid):
    return sid is not None and GLib.main_context_default().find_source_by_id(sid) is not None


class FormatTest(NoSpawnMixin, unittest.TestCase):
    """Eine Formatfunktion für Kapazität und Platz: eine Nachkommastelle, Einheit GB; RAM-Feld zwei Stellen."""

    def test_one_decimal_gb(self):
        self.assertEqual(livestats.fmt_gb1(6963), f"{d(6.8)} GB")
        self.assertEqual(livestats.fmt_gb1(1536), f"{d(1.5)} GB")
        self.assertEqual(livestats.fmt_gb1(100 * 1024), f"{d(100.0)} GB")
        self.assertEqual(livestats.fmt_bytes_gb1(10 * 2**30), f"{d(10.0)} GB")
        self.assertEqual(livestats.fmt_bytes_gb1(None), "?")
        self.assertNotIn("GiB", livestats.fmt_gb1(2048))

    def test_ram_field_keeps_two_decimals(self):
        self.assertEqual(livestats.fmt_ram_gb(1280), f"{d(1.25, 2)} GB")
        self.assertEqual(livestats.fmt_ram_gb(1024), "1 GB")

    def test_single_format_function_in_gui(self):
        import evoxd.gui as G
        self.assertIs(G.gib, livestats.fmt_gb1)
        self.assertIs(G.fmt_size, livestats.fmt_bytes_gb1)
        self.assertEqual(G.fmt_ram(4096), f"{d(4.0)} GB")
        self.assertEqual(G.fmt_ram(None), "?")


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class NumberFormatGuiTest(GuiBase):
    def test_main_and_start_dialog_lines(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        host = w.host_lbl.get_text()
        self.assertNotIn("GiB", host)
        self.assertRegex(host, r"RAM \d+[.,]\d GB, available \d+[.,]\d GB, reserve \d+[.,]\d GB, max\. for VMs \d+[.,]\d GB")
        dlg = G.StartDialog(w, self.ev, "TEMPLATE-MAIL")
        dlg.ram.set_value(1.25)
        self.assertEqual(dlg.memory_mib, 1280)
        self.assertEqual(dlg.ram.get_text(), d(1.25, 2))                          # RAM-Feld: zwei Stellen (0,25-Raster)
        txt = dlg.host_lbl.get_text()
        self.assertNotIn("GiB", txt)
        self.assertRegex(txt, r"available \d+[.,]\d GB, reserve \d+[.,]\d GB, max\. for VMs \d+[.,]\d GB")
        self.assertIn(f"of {d(1.25, 2)} GB", txt)                                # Größe der VM (RAM) bleibt genau
        self.assertNotIn("GiB", dlg.cap_lbl.get_text())
        dlg.destroy()
        w.destroy()

    def test_template_and_vault_sizes_one_decimal(self):
        w = self.window(raw())
        row = list(w.tpl_store[0])
        self.assertTrue(any(re.fullmatch(r"\d+[.,]\d GB", str(c)) for c in row), row)
        self.assertNotIn("GiB", " ".join(str(c) for c in row))
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class HowToCenteredTest(GuiBase):
    def test_title_centered(self):
        w = self.window(raw())
        self.assertEqual(w.howto_title.get_xalign(), 0.5)
        self.assertEqual(w.howto_title.get_justify(), Gtk.Justification.CENTER)
        self.assertEqual(w.howto_title.get_text(), T.HOWTO_TITLE)
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class MonitorWindowTest(GuiBase):
    def test_no_auto_open_and_button_states(self):
        import evoxd.gui as G
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))               # laufende VM ist markiert
        self.assertIsNone(w.monitor)                                            # nie automatisch
        self.assertEqual(w.details_btn.get_label(), T.BTN_DETAILS_OPEN)
        self.assertTrue(w.details_btn.get_sensitive())
        self.assertEqual(w.details_btn.get_tooltip_text(), T.DETAILS_TIP)
        ctx = w.details_btn.get_style_context()
        self.assertTrue(ctx.has_class("evox-fn-neutral") and ctx.has_class("evox-details-btn"))
        self.assertEqual(w.status_text(w.details_btn), T.STATUS_DETAILS)
        self.assertTrue(w.details_btn.get_can_focus())
        w.view.get_selection().unselect_all()
        self.assertFalse(w.details_btn.get_sensitive())                         # ohne Markierung gesperrt + Grund
        self.assertEqual(w.details_btn.get_tooltip_text(), T.DETAILS_TIP_NONE)
        self.assertIn(T.DETAILS_TIP_NONE, w.status_text(w.details_btn))
        self.assertTrue(G.MonitorWindow and hasattr(T, "DE_BTN_DETAILS_OPEN") and hasattr(T, "DE_MON_STOPPED"))
        w.destroy()

    def test_open_close_by_button(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        w.details_btn.clicked()
        m = w.monitor
        self.assertIsNotNone(m)
        self.assertEqual(w.details_btn.get_label(), T.BTN_DETAILS_CLOSE)         # Hauptknopf schließt bei offenem Fenster
        self.assertEqual(m.get_title(), T.MON_HEAD.format(name=self.name))
        self.assertEqual(m.head.get_text(), T.MON_HEAD.format(name=self.name))
        self.assertEqual(m.close_btn.get_label(), T.BTN_DETAILS_CLOSE)
        self.assertIs(m.get_focus(), m.close_btn)                                # Anfangsfokus auf CLOSE
        self.assertEqual(m.focusline.get_text(), T.STATUS_MON_CLOSE)             # Statuszeile folgt dem Fokus
        m._status(None)
        self.assertEqual(m.focusline.get_text(), T.STATUS_MON_DEFAULT)
        self.assertEqual(m.status_texts[m.close_btn], T.STATUS_MON_CLOSE)
        w.details_btn.clicked()
        self.assertIsNone(w.monitor)
        self.assertFalse(m.get_realized())                                       # zerstört
        self.assertEqual(w.details_btn.get_label(), T.BTN_DETAILS_OPEN)
        w.destroy()

    def test_close_by_own_button_escape_and_x(self):
        w = self.window(raw())
        for how in ("button", "escape", "x"):
            w.details_btn.clicked()
            m = w.monitor
            self.assertIsNotNone(m, how)
            if how == "button":
                m.close_btn.clicked()
            elif how == "escape":
                self.assertTrue(m._on_key(m, key(Gdk.KEY_Escape)))
            else:
                self.assertTrue(m.emit("delete-event", Gdk.Event.new(Gdk.EventType.DELETE)))
            self.assertIsNone(w.monitor, how)
            self.assertEqual(w.details_btn.get_label(), T.BTN_DETAILS_OPEN, how)
        m2 = None
        w.details_btn.clicked()
        m2 = w.monitor
        m2.dismiss()
        m2.dismiss()                                                             # zweimal schadet nicht
        self.assertIsNone(w.monitor)
        w.destroy()

    def test_only_one_window(self):
        w = self.window(raw())
        w.details_btn.clicked()
        first = w.monitor
        w.toggle_monitor()                                                       # zweiter Aufruf schließt, öffnet nicht neu
        self.assertIsNone(w.monitor)
        w.toggle_monitor()
        self.assertIsNot(w.monitor, first)
        w.refresh()
        w.view.get_selection().unselect_all()
        w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
        n = [t for t in Gtk.Window.list_toplevels() if type(t).__name__ == "MonitorWindow" and t.get_realized() is not None
             and t is w.monitor]
        self.assertEqual(len(n), 1)
        w.destroy()

    def test_selection_change_updates_and_stopped(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        first = self.name
        r = self.ev.start("TEMPLATE-MAIL", purpose="BANK")
        self.hv.stats[r.name] = raw(avail=2 * GIB_KIB, usable=GIB_KIB // 5)
        w.refresh()
        w.details_btn.clicked()
        m = w.monitor
        self.assertIn(first, m.head.get_text())
        names = [row[0] for row in w.store]
        other = [n for n in names if n != first][0]
        w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([names.index(other)]))
        self.assertIn(other, m.head.get_text())                                  # Markierungswechsel aktualisiert
        self.assertEqual(m.get_title(), T.MON_HEAD.format(name=other))
        self.assertIs(w.monitor, m)                                              # dasselbe Fenster
        self.assertEqual(m.stack.get_visible_child_name(), "live")
        self.assertEqual(m.ram_bar.value, 90)
        w.view.get_selection().unselect_all()                                    # ohne Markierung bleibt das Ziel
        self.assertIn(other, m.head.get_text())
        self.assertEqual(m.stack.get_visible_child_name(), "live")
        w.destroy()

    def test_vm_stopped_shows_message_and_stays_usable(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        w.details_btn.clicked()
        m = w.monitor
        self.assertEqual(m.stack.get_visible_child_name(), "live")
        self.ev.stop(self.name)
        w.refresh()
        self.assertIs(w.monitor, m)
        self.assertEqual(m.stack.get_visible_child_name(), "stopped")
        self.assertEqual(m.stopped_lbl.get_text(), T.MON_STOPPED)
        self.assertEqual(m.head.get_text(), T.MON_HEAD.format(name=self.name))
        self.assertEqual(w.details_btn.get_label(), T.BTN_DETAILS_CLOSE)         # Schließen bleibt möglich
        self.assertTrue(w.details_btn.get_sensitive())
        self.assertEqual(w.short_lbl.get_text(), T.SHORT_NONE)
        w.refresh()                                                              # unveränderter Zyklus bleibt stabil
        self.assertEqual(m.stopped_lbl.get_text(), T.MON_STOPPED)
        m.close_btn.clicked()
        self.assertIsNone(w.monitor)
        w.destroy()

    def test_read_errors_never_disturb(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        w.details_btn.clicked()
        m = w.monitor
        before = m.ram_line.get_text()
        msg = w.msg.get_text()
        self.hv.stats_error = RuntimeError("libvirt weg")
        w._live_tick()
        end = time.monotonic() + 3
        while w._live_running and time.monotonic() < end:
            Gtk.main_iteration_do(False)
        self.assertEqual(m.ram_line.get_text(), before)                          # alte Werte, keine Ausnahme
        self.assertEqual(w.msg.get_text(), msg)
        w.refresh()                                                              # voller Zyklus: n/a statt Absturz
        self.assertIs(w.monitor, m)
        self.assertEqual(w.msg.get_text(), msg)
        w.destroy()

    def test_content_fills_window(self):
        import evoxd.gui as G
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB, cpu=0, nets=[(1, 2)], overlay=2**20))
        w.details_btn.clicked()
        m = w.monitor
        self.assertEqual(len(m.detail_blocks), 3)
        parent = m.detail_blocks[0].get_parent()
        self.assertEqual(parent.get_orientation(), Gtk.Orientation.HORIZONTAL)
        self.assertTrue(parent.get_homogeneous())
        self.assertTrue(parent.child_get_property(m.detail_blocks[0], "expand"))
        for bar in (m.ram_bar, m.cpu_bar):
            self.assertTrue(bar.get_parent().child_get_property(bar, "expand"))  # Balken dehnen sich
        self.assertTrue(m.cpu_spark.get_parent().child_get_property(m.cpu_spark, "expand"))
        self.assertGreater(m.ram_bar.get_size_request()[1], 26)                  # dicker als der alte Detailbereich
        for lbl in (m.ram_line, m.cpu_line):
            self.assertTrue(lbl.get_style_context().has_class("evox-mon-num"))
        self.assertEqual(m.get_size_request(), G.MON_MIN_SIZE)
        self.assertIn("evox-mon-num", G.CSS)
        self.assertEqual(m.cpu_hist_lbl.get_text(), T.CPU_HIST.format(min=5))
        w.destroy()

    def test_ram_recommendation_only_with_real_values(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB // 5))               # 90 % echter Gastwert
        w.details_btn.clicked()
        m = w.monitor
        self.assertTrue(m.ram_rec.get_visible())
        self.assertIn("choose more RAM", m.ram_rec.get_text())
        self.assertTrue(m.ram_rec.get_text().startswith(("■", "▲")))                # mit Symbol
        w.destroy()

    def test_no_recommendation_for_estimate(self):
        w = self.window(raw(rss=GIB_KIB // 2))                                      # nur Schätzung: nichts raten
        w.details_btn.clicked()
        self.assertFalse(w.monitor.ram_rec.get_visible())
        self.assertEqual(w.monitor.ram_rec.get_text(), "")
        w.destroy()

    def test_main_window_close_closes_monitor_and_remembers(self):
        w = self.window(raw())
        w.details_btn.clicked()
        m = w.monitor
        w.destroy()
        self.assertIsNone(w.monitor)
        self.assertFalse(m.get_realized())


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class MonitorGeometryTest(GuiBase):
    def test_fit_geometry(self):
        import evoxd.gui as G
        geo = {"width": 1000, "height": 500, "x": 100, "y": 120}
        self.assertEqual(G.fit_geometry(geo, SCREEN), (1000, 500, 100, 120))     # gültig: unverändert
        self.assertEqual(G.fit_geometry({**geo, "x": 5000, "y": 4000}, SCREEN), (1000, 500, 920, 580))   # außerhalb
        self.assertEqual(G.fit_geometry({**geo, "x": -900, "y": -50}, SCREEN), (1000, 500, 0, 0))
        self.assertEqual(G.fit_geometry({"width": 9000, "height": 9000, "x": 0, "y": 0}, SCREEN)[:2], (1920, 1080))
        self.assertEqual(G.fit_geometry({"width": 300, "height": 250, "x": 1, "y": 1}, SCREEN)[:2], G.MON_MIN_SIZE)
        self.assertEqual(G.fit_geometry({**geo, "x": None, "y": None}, SCREEN), (1000, 500, None, None))
        self.assertEqual(G.fit_geometry({**geo, "x": 100, "y": 100}, (1920, 0, 1280, 1024))[2], 1920)   # 2. Monitor rechts

    def test_load_accepts_only_plausible_values(self):
        s = self.ev.s
        p = s.gui_state_path
        p.parent.mkdir(parents=True, exist_ok=True)
        good = {"width": 1000, "height": 500, "x": -20, "y": 30}
        p.write_text(json.dumps({"monitor": good, "monitor_pin": True}))
        st = s.load_gui_state()
        self.assertEqual(st["monitor"], good)
        self.assertTrue(st["monitor_pin"])
        bad = [{"width": 50, "height": 500}, {"width": "800", "height": 500}, {"width": True, "height": 500},
               {"width": 1000, "height": 99999}, {"width": 1000}, [], "x", 5, None, {"width": 1000.5, "height": 500}]
        for b in bad:
            p.write_text(json.dumps({"monitor": b, "monitor_pin": "yes"}))
            st = s.load_gui_state()
            self.assertIsNone(st["monitor"], b)
            self.assertFalse(st["monitor_pin"])
        p.write_text(json.dumps({"monitor": {"width": 1000, "height": 500, "x": "a", "y": 5}}))
        self.assertEqual(s.load_gui_state()["monitor"], {"width": 1000, "height": 500, "x": None, "y": None})
        p.write_text(json.dumps({"width": 1100, "height": 820, "maximized": False}))      # alte Datei (vor 0.7.4)
        old = s.load_gui_state()
        self.assertIsNone(old["monitor"])
        self.assertFalse(old["monitor_pin"])
        self.assertEqual(old["width"], 1100)
        p.write_text("[1, 2]")
        self.assertEqual(s.load_gui_state()["width"], 1100)                        # kein dict → Standard

    def test_saving_main_and_monitor_keep_each_other(self):
        s = self.ev.s
        s.save_monitor_state(geometry={"width": 700, "height": 400, "x": 10, "y": 20}, pin=True)
        s.save_gui_state(1200, 900, False)                                         # Hauptfenster speichern
        st = s.load_gui_state()
        self.assertEqual(st["monitor"], {"width": 700, "height": 400, "x": 10, "y": 20})
        self.assertTrue(st["monitor_pin"])
        self.assertEqual((st["width"], st["height"]), (1200, 900))
        s.save_monitor_state(pin=False)                                            # nur Pin ändern
        st = s.load_gui_state()
        self.assertFalse(st["monitor_pin"])
        self.assertEqual(st["monitor"]["width"], 700)
        self.assertEqual(st["width"], 1200)
        s.save_monitor_state(geometry={"width": 650, "height": 380, "x": None, "y": None})
        self.assertEqual(s.load_gui_state()["monitor"], {"width": 650, "height": 380, "x": None, "y": None})
        self.assertEqual(oct(s.gui_state_path.stat().st_mode & 0o777), "0o600")

    def test_open_uses_saved_geometry_clamped(self):
        import evoxd.gui as G
        self.ev.s.save_monitor_state(geometry={"width": 1000, "height": 500, "x": 6000, "y": 100})
        w = self.window(raw())
        moved = []
        with mock.patch.object(G, "screen_rect", return_value=SCREEN), \
                mock.patch.object(G.MonitorWindow, "move", lambda self, x, y: moved.append((x, y))):
            w.details_btn.clicked()
        m = w.monitor
        self.assertEqual(m.get_default_size(), (1000, 500))
        self.assertEqual(moved, [(920, 100)])                                     # auf den Bildschirm geschoben
        w.destroy()

    def test_open_without_saved_geometry_uses_default(self):
        import evoxd.gui as G
        w = self.window(raw())
        w.details_btn.clicked()
        self.assertEqual(w.monitor.get_default_size(), G.MON_DEFAULT_SIZE)
        w.destroy()

    def test_geometry_saved_on_close_only_when_shown(self):
        import evoxd.gui as G
        got = []
        m = G.MonitorWindow(G.COLORS_DARK, None, False, on_close=got.append)
        m.dismiss()
        self.assertEqual(got, [None])                                              # nie gezeigt: nichts Falsches speichern
        m2 = G.MonitorWindow(G.COLORS_DARK, None, False, on_close=got.append)
        m2.get_mapped = lambda: True
        m2.dismiss()
        self.assertEqual(set(got[1]), {"width", "height", "x", "y"})
        self.assertGreaterEqual(got[1]["width"], 1)
        w = self.window(raw())
        w._save_monitor(None)
        self.assertIsNone(self.ev.s.load_gui_state()["monitor"])
        w._save_monitor({"width": 640, "height": 360, "x": 5, "y": 6})
        self.assertEqual(self.ev.s.load_gui_state()["monitor"], {"width": 640, "height": 360, "x": 5, "y": 6})
        w.destroy()

    def test_save_error_goes_to_status_line(self):
        w = self.window(raw())
        with mock.patch.object(self.ev.s, "save_monitor_state", side_effect=OSError("voll")):
            w._save_monitor({"width": 640, "height": 360, "x": 5, "y": 6})
            w._save_monitor_pin(True)
        self.assertIn("voll", w.msg.get_text())
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class MonitorPinTest(GuiBase):
    def test_default_off_remembered_and_restored(self):
        import evoxd.gui as G
        w = self.window(raw())
        w.details_btn.clicked()
        m = w.monitor
        self.assertFalse(m.pin_chk.get_active())                                   # Standard aus
        self.assertFalse(self.ev.s.load_gui_state()["monitor_pin"])
        above = []
        m.set_keep_above = above.append
        m.pin_chk.set_active(True)
        self.assertEqual(above, [True])
        self.assertTrue(self.ev.s.load_gui_state()["monitor_pin"])                 # sofort gemerkt
        m.dismiss()
        kept = []
        with mock.patch.object(G.MonitorWindow, "set_keep_above", lambda self, on: kept.append(on)):
            w.details_btn.clicked()
        self.assertTrue(w.monitor.pin_chk.get_active())                            # beim nächsten Öffnen wieder an
        self.assertEqual(kept, [True])
        w.monitor.pin_chk.set_active(False)
        self.assertFalse(self.ev.s.load_gui_state()["monitor_pin"])
        self.assertEqual(w.monitor.status_texts[w.monitor.pin_chk], T.STATUS_MON_PIN)
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class MonitorTimerTest(GuiBase):
    def test_interval_follows_need(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        self.assertEqual(w._tick_s, 1)                                             # laufende VM markiert
        w.view.get_selection().unselect_all()
        self.assertEqual(w._tick_s, 5)                                             # läuft, aber nichts markiert, kein Fenster
        w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
        self.assertEqual(w._tick_s, 1)
        w.details_btn.clicked()
        w.view.get_selection().unselect_all()
        self.assertEqual(w._tick_s, 1)                                             # Fenster offen + VM läuft
        w.details_btn.clicked()
        self.assertEqual(w._tick_s, 5)                                             # Fenster zu, nichts markiert
        w.destroy()

    def test_no_vm_running_stays_5s_even_with_window(self):
        w = self.window(raw())
        w.details_btn.clicked()
        self.assertEqual(w._tick_s, 1)
        self.ev.stop(self.name)
        w.refresh()
        self.assertIsNotNone(w.monitor)
        self.assertEqual(w._tick_s, 5)                                             # keine VM → kein 1-s-Takt
        w.destroy()

    def test_no_extra_timer_and_end_on_close(self):
        w = self.window(raw())
        sid = w._tick_id
        with mock.patch.object(GLib, "timeout_add") as t1, mock.patch.object(GLib, "timeout_add_seconds") as t2, \
                mock.patch.object(GLib, "idle_add") as t3:
            w.details_btn.clicked()
            w.refresh()
            w.details_btn.clicked()
        t1.assert_not_called()
        t2.assert_not_called()                                                     # Takt bleibt 1 s: nichts Neues
        self.assertEqual(w._tick_id, sid)
        w.details_btn.clicked()
        last = w._tick_id
        self.assertTrue(source_alive(last))
        w.destroy()
        self.assertIsNone(w._tick_id)
        self.assertFalse(source_alive(last))                                       # Timer endet beim Schließen
        self.assertIsNone(w.monitor)

    def test_window_close_returns_to_5s_not_to_old_timer(self):
        w = self.window(raw())
        w.view.get_selection().unselect_all()
        w.details_btn.clicked() if w.details_btn.get_sensitive() else None
        self.assertIsNone(w.monitor)
        self.assertEqual(w._tick_s, 5)
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class MonitorZeroCallsTest(GuiBase):
    def counted(self, w, n=3, live=True):
        from tests.test_cycle import WATCH
        calls = Counter()
        with contextlib.ExitStack() as st:
            for cls, name, kind in WATCH + [(Gtk.Button, "set_label", "set_label"),
                                            (Gtk.Window, "set_title", "title"),
                                            (Gtk.Widget, "set_size_request", "size")]:
                orig = getattr(cls, name)
                st.enter_context(mock.patch.object(cls, name, lambda *a, _o=orig, _k=kind, **k: (
                    calls.update([_k]), _o(*a, **k))[1]))
            for _ in range(n):
                self.clock.t += 1
                if live:
                    w._apply_live([self.name], self.hv.domain_stats([self.name]))
                else:
                    w.refresh()
        return dict(calls)

    def test_unchanged_live_step_with_monitor_open(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB, cpu=10**9, nets=[(5, 6)], overlay=2**20))
        w.details_btn.clicked()
        for _ in range(3):
            self.clock.t += 1
            w._apply_live([self.name], self.hv.domain_stats([self.name]))
        self.assertEqual(self.counted(w), {})
        self.assertEqual(self.counted(w, live=False), {})                          # auch voller Zyklus
        w.destroy()

    def test_unchanged_cycle_when_stopped(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        w.details_btn.clicked()
        self.ev.stop(self.name)
        w.refresh()
        w.refresh()
        self.assertEqual(self.counted(w, live=False), {})
        w.destroy()

    def test_value_change_sets_only_what_changed(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB, cpu=10**9))
        w.details_btn.clicked()
        m = w.monitor
        self.assertEqual(m.ram_bar.value, 50)
        self.hv.stats[self.name]["balloon.usable"] = GIB_KIB // 5
        w.refresh()
        self.assertEqual(m.ram_bar.value, 90)                                      # Wertwechsel kommt an
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class ShortLineTest(GuiBase):
    def test_short_line_content_and_levels(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        text = w.short_lbl.get_text()
        self.assertRegex(text, r"^RAM ● OK 50 %  ·  CPU \S+  ·  Up .+$")
        self.assertIn(w.colors["ok"], w.short_lbl.get_label())                     # Farbe zusätzlich zu Symbol + Wort
        self.hv.stats[self.name]["balloon.usable"] = GIB_KIB // 2                  # 75 %
        w.refresh()
        self.assertIn("▲ HIGH 75 %", w.short_lbl.get_text())
        self.hv.stats[self.name]["balloon.usable"] = 0
        w.refresh()
        self.assertIn("■ FULL 100 %", w.short_lbl.get_text())
        w.destroy()

    def test_short_line_na_and_estimate(self):
        w = self.window(raw(rss=GIB_KIB // 2))
        self.assertIn("RAM ○ LOW ~25 %", w.short_lbl.get_text())                   # Schätzung mit ~
        w.destroy()

    def test_short_line_na_without_stats(self):
        r = self.ev.start("TEMPLATE-MAIL", purpose="BANK")
        self.hv.stats.pop(r.name, None)
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        w.refresh()
        w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
        self.assertRegex(w.short_lbl.get_text(), r"^RAM n/a  ·  CPU n/a  ·  Up ")
        w.destroy()

    def test_no_selection_and_not_running_texts(self):
        w = self.window(raw())
        w.view.get_selection().unselect_all()
        self.assertEqual(w.short_lbl.get_text(), T.SHORT_NONE)
        self.assertTrue(w.short_lbl.get_visible())                                 # Zeile bleibt (kein Sprung)
        w.destroy()

    def test_one_line_ellipsized_not_wrapping(self):
        w = self.window(raw())
        self.assertTrue(w.short_lbl.get_single_line_mode())
        self.assertEqual(w.short_lbl.get_ellipsize(), gi.repository.Pango.EllipsizeMode.END)
        page = w.vm_stack.get_parent()
        kids = page.get_children()
        self.assertIs(kids[kids.index(w.vm_stack) + 1], w.details)                 # direkt unter der Liste
        self.assertEqual(w.details.get_children(), [w.short_lbl, w.details_btn])
        self.assertFalse(hasattr(w, "ram_bar"))                                    # kein Detailbereich mehr im Hauptfenster
        w.destroy()

    def test_window_size_never_changes(self):
        """Auswahl, Ampelwechsel, lange Zeile, Monitor auf/zu: Hauptfenster bleibt exakt gleich groß."""
        for height in (1000, 600):
            self.ev.s.save_gui_state(1000, height, False, None)
            w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
            w.show_all()
            pump()
            base = tuple(w.get_size())
            sizes = []
            for usable in (GIB_KIB // 5, 0, GIB_KIB, GIB_KIB // 2):
                self.hv.stats[self.name]["balloon.usable"] = usable
                w.refresh()
                pump(0.05)
                sizes.append(tuple(w.get_size()))
            w.view.get_selection().unselect_all()
            pump(0.05)
            sizes.append(tuple(w.get_size()))
            w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
            pump(0.05)
            sizes.append(tuple(w.get_size()))
            for _ in range(2):
                w.details_btn.clicked()
                pump(0.1)
                sizes.append(tuple(w.get_size()))
                w.details_btn.clicked()
                pump(0.1)
                sizes.append(tuple(w.get_size()))
            self.assertEqual(set(sizes), {base}, (height, base, sizes))
            w.destroy()

    def test_obsolete_panel_gone(self):
        import evoxd.gui as G
        self.assertFalse(hasattr(G, "DetailsPanel"))
        for name in ("LIST_OPEN_MIN_H", "DETAILS_BAR_MIN_H", "DETAILS_SETTLE_S"):
            self.assertFalse(hasattr(G, name), name)


if __name__ == "__main__":
    unittest.main()
