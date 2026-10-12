"""0.7.2 (A3c): Live-Takt 1 s nur mit laufender Wegwerf-VM, Lesen im Thread, großer Detailbereich mit Knopf
DETAILS ▼/▲ – nur Attrappen (FakeHypervisor, nospawn), kein echtes libvirt."""
import contextlib
import threading
import time
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from evoxd import domxml, livestats
from evoxd import texts as T
from tests.nospawn import NoSpawnMixin
from tests.test_a3b import HAVE_DISPLAY, GuiBase
from tests.test_core import spec
from tests.test_live import GIB_KIB, raw


class BalloonPeriodTest(NoSpawnMixin, unittest.TestCase):
    """Einzige XML-Änderung gegenüber 0.7.1: Periode 5 → 1; Untergrenze 1 s."""

    def test_only_period_changed(self):
        for net in (True, False):
            now = domxml.build(spec(net))
            with mock.patch.object(domxml, "BALLOON_STATS_S", 5):
                old = domxml.build(spec(net))
            self.assertEqual(now, old.replace('<stats period="5"', '<stats period="1"'))
            self.assertNotEqual(now, old)
            self.assertEqual(ET.fromstring(now).find("devices/memballoon/stats").get("period"), "1")

    def test_lower_bound(self):
        import evoxd.gui as G
        self.assertEqual(G.LIVE_S, 1)
        self.assertGreaterEqual(domxml.BALLOON_STATS_S, 1)
        self.assertEqual(G.REFRESH_S, 5)


def pump(cond, sec=3.0):
    end = time.monotonic() + sec
    while not cond() and time.monotonic() < end:
        Gtk.main_iteration_do(False)
        time.sleep(0.005)
    return cond()


def source_alive(sid):
    return sid is not None and GLib.main_context_default().find_source_by_id(sid) is not None


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class TimerIntervalTest(GuiBase):
    def test_5s_without_vm(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        self.assertEqual(w._tick_s, 5)
        self.assertTrue(source_alive(w._tick_id))
        w.refresh()
        self.assertEqual(w._tick_s, 5)
        w.destroy()

    def test_1s_with_running_vm_switch_back_and_end_on_close(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        self.assertEqual(w._tick_s, 1)
        sid = w._tick_id
        self.assertTrue(source_alive(sid))
        w.refresh()                                                              # unverändert: kein neuer Zeitgeber
        self.assertEqual(w._tick_id, sid)
        self.ev.stop(self.name)                                                  # VM weg → zurück auf 5 s
        w.refresh()
        self.assertEqual(w._tick_s, 5)
        self.assertFalse(source_alive(sid))                                      # alter Zeitgeber entfernt
        self.assertTrue(source_alive(w._tick_id))
        last = w._tick_id
        w.destroy()
        self.assertIsNone(w._tick_id)
        self.assertFalse(source_alive(last))
        w._has_running = True
        w._retime()                                                              # nach dem Schließen nie neu
        self.assertIsNone(w._tick_id)

    def test_timer_full_cycle_only_every_5s(self):
        w = self.window(raw())
        full, live = [], []
        w._tick = lambda: full.append(1)
        w._live_tick = lambda: live.append(1)
        w._full_at = time.monotonic()
        for _ in range(3):
            self.assertTrue(w._on_timer())
        self.assertEqual((len(live), len(full)), (3, 0))
        w._full_at -= 5
        w._on_timer()
        self.assertEqual((len(live), len(full)), (4, 1))
        w.destroy()

    def test_no_live_read_without_vm(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        n = self.hv.stats_calls
        self.assertFalse(w._live_tick())
        self.assertEqual(self.hv.stats_calls, n)
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class LiveThreadTest(GuiBase):
    def test_read_in_thread_updates_cells_and_details(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        w.details_btn.clicked()                                  # 0.7.4: Live Monitor öffnen
        self.assertEqual(w.store[0][4], "● 50 %")
        ids = []
        orig = self.hv.domain_stats
        self.hv.domain_stats = lambda names: (ids.append(threading.get_ident()), orig(names))[1]
        self.hv.stats[self.name]["balloon.usable"] = GIB_KIB // 5                # 90 %
        self.assertTrue(w._live_tick())
        self.assertTrue(pump(lambda: not w._live_running))
        self.assertNotEqual(ids, [])
        self.assertNotEqual(ids[0], threading.get_ident())                      # nie im GTK-Thread
        self.assertEqual(w.store[0][4], "■ 90 %")
        self.assertEqual(w.monitor.ram_bar.value, 90)
        w.destroy()

    def test_skip_while_previous_read_runs(self):
        w = self.window(raw())
        gate = threading.Event()
        orig = self.hv.domain_stats
        calls = []
        self.hv.domain_stats = lambda names: (calls.append(1), gate.wait(2), orig(names))[2]
        self.assertTrue(w._live_tick())
        self.assertFalse(w._live_tick())                                         # Verzögerung → Wert übersprungen
        self.assertFalse(w._live_tick())
        gate.set()
        self.assertTrue(pump(lambda: not w._live_running))
        self.assertEqual(len(calls), 1)
        w.destroy()

    def test_error_keeps_values_and_never_disturbs(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        before = list(w.store[0])
        msg = w.msg.get_text()
        self.hv.stats_error = RuntimeError("libvirt weg")
        w._live_tick()
        self.assertTrue(pump(lambda: not w._live_running))
        self.assertEqual(list(w.store[0]), before)                               # alte Werte bleiben
        self.assertEqual(w.msg.get_text(), msg)                                  # Statuszeile unberührt
        self.assertFalse(w._apply_live([self.name], "kein dict"))
        w.destroy()

    def test_apply_after_close_is_noop(self):
        w = self.window(raw())
        w.destroy()
        self.assertFalse(w._apply_live([self.name], {}))

    def test_full_cycle_reuses_fresh_thread_values(self):
        w = self.window(raw())
        w._live_tick()
        self.assertTrue(pump(lambda: not w._live_running))
        n = self.hv.stats_calls
        w.refresh()                                                              # frisch → kein blockierendes Lesen
        self.assertEqual(self.hv.stats_calls, n)
        w._live_at -= 10
        w.refresh()                                                              # veraltet → liest wieder
        self.assertEqual(self.hv.stats_calls, n + 1)
        w.destroy()

    def test_unchanged_live_tick_zero_gtk_calls(self):
        from tests.test_cycle import WATCH
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB, cpu=10**9, nets=[(5, 6)], overlay=2**20))
        for _ in range(3):
            self.clock.t += 1
            w._apply_live([self.name], self.hv.domain_stats([self.name]))
        calls = Counter()
        with contextlib.ExitStack() as st:
            for cls, name, kind in WATCH + [(Gtk.Button, "set_label", "set_label"),
                                            (Gtk.Widget, "set_size_request", "size")]:
                orig = getattr(cls, name)
                st.enter_context(mock.patch.object(cls, name, lambda *a, _o=orig, _k=kind, **k: (
                    calls.update([_k]), _o(*a, **k))[1]))
            for _ in range(3):
                self.clock.t += 1
                w._apply_live([self.name], self.hv.domain_stats([self.name]))
        self.assertEqual(dict(calls), {})
        w.destroy()


if __name__ == "__main__":
    unittest.main()
