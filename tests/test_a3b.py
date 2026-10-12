"""0.7.1 (A3b): Balloon-Statistik, schlanke Liste, Detailbereich mit drei Blöcken, Hinweis beim Beenden,
Zweck-Statistik, Leuchtrand Schritt 4 – nur Attrappen (FakeHypervisor, nospawn), kein echtes libvirt."""
import contextlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from evoxd import capacity, config, domxml, livestats
from evoxd.config import Settings
from evoxd.errors import AllowlistViolation
from evoxd.lifecycle import Evox
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor
from tests.nospawn import NoSpawnMixin
from tests.test_core import live, s, spec
from tests.test_live import GIB_KIB, Clock, raw

HAVE_DISPLAY = Gtk.init_check([])[0]
d = capacity.fmt_dec


class BalloonXmlTest(NoSpawnMixin, unittest.TestCase):
    """Nur die Statistik-Periode kommt hinzu; Erlaubnisliste bleibt streng."""

    def test_stats_period_set(self):
        for net in (True, False):
            root = ET.fromstring(domxml.build(spec(net)))
            mb = root.findall("devices/memballoon")
            self.assertEqual(len(mb), 1)
            self.assertEqual(mb[0].attrib, {"model": "virtio"})
            self.assertEqual([(c.tag, c.attrib) for c in mb[0]], [("stats", {"period": "1"})])   # 0.7.2: 1 s (0.7.1: 5)
            self.assertEqual(domxml.BALLOON_STATS_S, 1)

    def test_otherwise_unchanged(self):
        root = ET.fromstring(domxml.build(spec(True)))
        self.assertEqual([c.tag for c in root.find("devices")],
                         ["disk", "controller", "interface", "input", "graphics", "audio", "video", "memballoon", "rng"])
        self.assertEqual(len(list(root.iter())), len(list(ET.fromstring(domxml.build(spec(True))).iter())))
        self.assertEqual(len(root.findall(".//stats")), 1)                   # einzige neue Angabe
        for tag in ("channel", "serial", "console", "filesystem", "hostdev", "shmem", "redirdev"):
            self.assertIsNone(root.find(f"devices/{tag}"), tag)              # kein neuer Kanal Gast ↔ Host

    def test_live_xml_with_stats_and_libvirt_extras_passes(self):
        for net in (True, False):
            r = live(net)
            mb = r.find("devices/memballoon")
            ET.SubElement(mb, "alias", name="balloon0")                       # so trägt libvirt es im Live-XML ein
            ET.SubElement(mb, "address", type="pci", domain="0x0000", bus="0x05", slot="0x00", function="0x0")
            domxml.validate_live(s(r), expect_net=net)

    def test_allowlist_still_strict(self):
        def add(tag, **a):
            def m(r):
                ET.SubElement(r.find("devices"), tag, **a)
            return m
        for mutate in (add("channel", type="unix"), add("filesystem", type="mount"), add("hostdev", mode="subsystem"),
                       add("serial", type="pty"), add("shmem", name="x")):
            r = live(True)
            mutate(r)
            with self.assertRaises(AllowlistViolation):
                domxml.validate_live(s(r), expect_net=True)


class LiveLogicTest(unittest.TestCase):
    def sampler(self):
        self.clock, self.wall = Clock(), Clock(10_000.0)
        return livestats.LiveSampler(clock=self.clock, wall=self.wall)

    def test_real_use_is_total_minus_available(self):
        v = self.sampler().sample("DISPOSABLE-EMAIL-01", raw(avail=2 * GIB_KIB, usable=GIB_KIB * 2 // 10), mem_mib=2048)
        self.assertEqual(v["ram_used"], (2 * GIB_KIB - GIB_KIB * 2 // 10) * 1024)   # 1,8 GiB
        self.assertEqual((v["ram_pct"], v["ram_level"], v["ram_est"]), (90, "full", False))

    def test_thresholds_at_borders(self):
        self.assertEqual((livestats.RAM_OK_MAX_PCT, livestats.RAM_HIGH_MAX_PCT, livestats.RAM_FULL_EVENT_PCT),
                         (60, 85, 95))
        for pct, want in ((60, "ok"), (61, "high"), (85, "high"), (86, "full")):
            self.assertEqual(livestats.ram_level(pct), want)

    def test_peak_time_and_full_counter(self):
        sm = self.sampler()
        n = "DISPOSABLE-EMAIL-01"
        sm.sample(n, raw(avail=2 * GIB_KIB, usable=GIB_KIB), mem_mib=2048)            # 50 %
        self.wall.t += 60
        v = sm.sample(n, raw(avail=2 * GIB_KIB, usable=GIB_KIB // 20), mem_mib=2048)  # 97,5 % → voll (1)
        self.assertEqual((v["peak_time"], v["full_count"]), (10_060.0, 1))
        v = sm.sample(n, raw(avail=2 * GIB_KIB, usable=0), mem_mib=2048)              # bleibt voll → kein neuer Zähler
        self.assertEqual(v["full_count"], 1)
        sm.sample(n, raw(avail=2 * GIB_KIB, usable=GIB_KIB), mem_mib=2048)            # wieder frei
        v = sm.sample(n, raw(avail=2 * GIB_KIB, usable=0), mem_mib=2048)              # zweites Mal voll
        self.assertEqual(v["full_count"], 2)
        self.assertEqual(sm.summary(n), {"peak": 2 * 2**30, "size": 2 * 2**30, "full": 2})

    def test_estimates_never_feed_hints(self):
        sm = self.sampler()
        sm.sample("DISPOSABLE-EMAIL-01", raw(rss=2 * GIB_KIB), mem_mib=2048)          # Schätzung 100 %
        self.assertEqual(sm.summary("DISPOSABLE-EMAIL-01"), {"peak": None, "size": None, "full": 0})
        self.assertIsNone(livestats.ram_hint(None, None, 0))

    def test_forget_returns_summary(self):
        sm = self.sampler()
        sm.sample("DISPOSABLE-EMAIL-01", raw(avail=2 * GIB_KIB, usable=GIB_KIB), mem_mib=2048)
        self.assertEqual(sm.forget(["DISPOSABLE-EMAIL-01"]), {})
        gone = sm.forget([])
        self.assertEqual(gone["DISPOSABLE-EMAIL-01"]["peak"], 2**30)
        self.assertEqual(sm.forget([]), {})

    def test_cpu_history_bounded(self):
        sm = self.sampler()
        for i in range(livestats.CPU_HISTORY_LEN + 40):
            self.clock.t += 5
            v = sm.sample("A", raw(cpu=int(i * 5e9)), vcpus=1)
        self.assertEqual(len(v["cpu_hist"]), livestats.CPU_HISTORY_LEN)
        self.assertEqual(livestats.CPU_HISTORY_LEN, 300)   # 0.7.2: 5 min im 1-s-Takt

    def test_overlay_fill_and_peak(self):
        sm = self.sampler()
        r = raw(overlay=2 * 2**30)
        r["block.1.capacity"] = 20 * 2**30
        v = sm.sample("A", r)
        self.assertEqual((v["overlay"], v["disk_size"], v["overlay_peak"]), (2 * 2**30, 20 * 2**30, 2 * 2**30))
        r["block.1.physical"] = 2**30
        self.assertEqual(sm.sample("A", r)["overlay_peak"], 2 * 2**30)

    def test_purpose_of(self):
        self.assertEqual(livestats.purpose_of("DISPOSABLE-EMAIL-01"), "EMAIL")
        for bad in ("VAULT-MAIL", "DISPOSABLE-email-01", "", None, "DISPOSABLE-A-1"):
            self.assertIsNone(livestats.purpose_of(bad))

    def test_hint_cases(self):
        G = 2**30
        # 0.7.3 (angepasst): Spitze + 25 %, 256-MiB-Raster, mind. 1 GB (0.7.1: +30 %, ganze GiB, mind. 2 GiB)
        self.assertEqual(livestats.ram_hint(int(1.8 * G), 2 * G, 0), ("high", 2304))
        self.assertEqual(livestats.ram_hint(int(0.6 * G), 4 * G, 0), ("low", 1024))
        self.assertEqual(livestats.ram_hint(2 * G, 2 * G, 3), ("full", 2560))
        self.assertEqual(livestats.ram_hint(int(1.1 * G), 2 * G, 0), ("ok", None))
        self.assertEqual(livestats.ram_hint(int(0.5 * G), 2 * G, 0), ("low", 1024))  # 0.7.3: 1 GB reicht
        self.assertEqual(livestats.ram_hint(30 * G, 32 * G, 1), ("full", config.MAX_MEMORY_MIB))   # Obergrenze
        for bad in ((0, G, 0), (G, 0, 0), (None, G, 0), (G, None, 0), (-1, G, 0)):
            self.assertIsNone(livestats.ram_hint(*bad))


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class HintTextTest(unittest.TestCase):
    def test_texts_per_case(self):
        import evoxd.gui as G
        g = 2**30
        lvl, text, sug = G.ram_hint_text({"peak": int(1.8 * g), "size": 2 * g, "full": 0})
        self.assertEqual((lvl, sug), ("full", 2304))                            # 90 % = rote Zone (Ampel wie Balken)
        self.assertEqual(text, f"■ RAM peak {d(1.8)} GiB of {d(2)} GiB (90 %). Next time choose more RAM: {d(2.25, 2)} GB.")
        lvl, text, sug = G.ram_hint_text({"peak": int(0.6 * g), "size": 4 * g, "full": 0})
        self.assertEqual(text, f"○ RAM peak only {d(0.6)} GiB of {d(4)} GiB. Next time 1 GB is enough.")
        lvl, text, sug = G.ram_hint_text({"peak": 2 * g, "size": 2 * g, "full": 4})
        self.assertEqual(lvl, "full")
        self.assertEqual(text, f"■ RAM was full 4 times. For better performance choose more RAM next time ({d(2.5)} GB).")
        lvl, text, sug = G.ram_hint_text({"peak": int(1.1 * g), "size": 2 * g, "full": 0})
        self.assertEqual((lvl, sug, text), ("ok", None, f"● RAM peak {d(1.1)} GiB of {d(2)} GiB (55 %). The size fits."))
        self.assertIsNone(G.ram_hint_text({"peak": None, "size": None, "full": 0}))          # n/a → kein Hinweis
        self.assertIsNone(G.ram_hint_text(None))

    def test_german_texts_complete(self):
        from evoxd import texts as T
        self.assertEqual(set(T.DE_HINT_RAM), set(T.HINT_RAM))
        self.assertEqual(len(T.DE_NET_ROWS), len(T.NET_ROWS))
        self.assertEqual(set(T.DE_LOCK_STATE), set(T.LOCK_STATE))
        for k in ("HINT_REMEMBER", "HINT_REMEMBERED", "DLG_PURPOSE_PEAK", "RAM_PEAK", "RAM_FULL_COUNT", "RAM_NA",
                  "CPU_LINE", "CPU_HIST", "OVERLAY_LINE", "STARTS_LINE", "STATUS_HINT_REMEMBER", "LIVE_COLUMNS"):
            self.assertTrue(hasattr(T, "DE_" + k), k)


class PurposeStatsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Settings(state_dir=Path(self.tmp.name) / "st", config_file=Path(self.tmp.name) / "cfg.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_read_only_higher(self):
        self.assertEqual(self.s.load_purpose_stats(), {})
        self.assertTrue(self.s.record_purpose_peak("EMAIL", 1126))
        self.assertFalse(self.s.record_purpose_peak("EMAIL", 900))          # niedriger → nicht geschrieben
        self.assertTrue(self.s.count_purpose_start("EMAIL"))
        self.assertTrue(self.s.count_purpose_start("EMAIL"))
        self.assertEqual(self.s.load_purpose_stats(), {"EMAIL": {"peak_mib": 1126, "starts": 2}})
        self.assertEqual(oct(self.s.purpose_stats_path.stat().st_mode & 0o777), "0o600")
        data = json.loads(self.s.purpose_stats_path.read_text())
        self.assertEqual(data, {"EMAIL": {"peak_mib": 1126, "starts": 2}})     # nur Zahlen + Zweckname

    def test_invalid_input_never_written(self):
        for p, v in (("email", 1000), ("E-MAIL", 1000), ("", 1000), (None, 1000), ("EMAIL", True), ("EMAIL", 0),
                     ("EMAIL", config.MAX_MEMORY_MIB + 1), ("EMAIL", 1.5), ("A" * 17, 1000)):
            self.assertFalse(self.s.record_purpose_peak(p, v), (p, v))
        self.assertFalse(self.s.count_purpose_start("bad name"))
        self.assertFalse(self.s.purpose_stats_path.exists())

    def test_broken_file_backed_up(self):
        self.s.state_dir.mkdir(parents=True)
        self.s.purpose_stats_path.write_text("{kaputt")
        self.assertEqual(self.s.load_purpose_stats(), {})
        self.assertTrue(self.s.record_purpose_peak("WEB", 2048))
        backups = list(self.s.state_dir.glob("purpose-stats.json.broken-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "{kaputt")
        self.assertEqual(self.s.load_purpose_stats(), {"WEB": {"peak_mib": 2048, "starts": 0}})

    def test_garbage_entries_ignored(self):
        self.s.state_dir.mkdir(parents=True)
        self.s.purpose_stats_path.write_text(json.dumps({
            "EMAIL": {"peak_mib": 1500, "starts": 3}, "bad": {"peak_mib": 1}, "WEB": {"peak_mib": True, "starts": -1},
            "BANK": {"peak_mib": 10**9, "starts": "x"}, "SHOP": 5}))
        self.assertEqual(self.s.load_purpose_stats(), {"EMAIL": {"peak_mib": 1500, "starts": 3},
                                                       "WEB": {"peak_mib": None, "starts": 0},
                                                       "BANK": {"peak_mib": None, "starts": 0}})
        self.s.purpose_stats_path.write_text("[1, 2]")
        self.assertEqual(self.s.load_purpose_stats(), {})


class GuiBase(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        dd = Path(self.tmp.name)
        st = Settings(state_dir=dd / "st", runtime_dir=dd / "rt", guard_status=dd / "x", config_file=dd / "cfg.json")
        self.hv = FakeHypervisor()
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.reg = Registry(st.registry_path)
        self.ev = Evox(st, self.hv, self.reg, net_check=lambda: (True, ""),
                       meminfo=lambda: {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20})
        self.ev.import_template("TEMPLATE-MAIL")

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def window(self, stats=None, purpose="EMAIL"):
        import evoxd.gui as G
        r = self.ev.start("TEMPLATE-MAIL", purpose=purpose)
        self.name = r.name
        if stats is not None:
            self.hv.stats[r.name] = stats
        w = G.MainWindow(self.ev)
        self.clock = Clock()
        w.live = livestats.LiveSampler(clock=self.clock, wall=lambda: self.reg.temp(self.name).created + 600)
        w.refresh()
        w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
        return w


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class SlimListAndBlocksTest(GuiBase):
    def test_slim_list_columns(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB, nets=[(1, 2)], overlay=2**20))
        titles = [c.get_title() for c in w.view.get_columns()]
        self.assertEqual(titles, ["Disposable VM", "State", "Mode", "Up", "RAM", "CPU"])
        for gone in ("Network", "Overlay", "Peak", "Template", "CPUs", "Since"):
            self.assertNotIn(gone, titles)
        self.assertEqual(list(w.store[0])[:6], [self.name, "running", "INTERNET", "10 min", "● 50 %", "n/a"])
        w.destroy()

    def test_three_blocks_side_by_side(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB // 5, cpu=0, nets=[(1, 2)], overlay=2**20))
        w.details_btn.clicked()                                  # 0.7.4: Live Monitor öffnen
        self.assertEqual(len(w.monitor.detail_blocks), 3)
        parent = w.monitor.detail_blocks[0].get_parent()
        self.assertEqual(parent.get_orientation(), Gtk.Orientation.HORIZONTAL)
        self.assertTrue(all(b.get_parent() is parent for b in w.monitor.detail_blocks))
        self.assertTrue(w.monitor.ram_bar.zones)
        self.assertEqual((w.monitor.ram_bar.value, w.monitor.ram_bar.peak), (90, 90))
        self.assertEqual(w.monitor.ram_bar.color, w.colors["bad"])
        self.assertEqual(w.monitor.ram_line.get_text(), f"■ FULL  {d(1.8)} / {d(2)} GiB (90 %)")
        self.assertIn("at ", w.monitor.ram_peak.get_text())
        self.hv.stats[self.name]["balloon.usable"] = GIB_KIB                     # 50 % → Spitze bleibt bei 90
        self.clock.t += 5
        self.hv.stats[self.name]["cpu.time"] = int(2.5e9)
        w.refresh()
        self.assertEqual((w.monitor.ram_bar.value, w.monitor.ram_bar.peak), (50, 90))
        self.assertEqual(w.monitor.cpu_bar.value, 25)
        self.assertEqual(w.monitor.cpu_spark.hist, (25,))
        self.assertEqual([lbl.get_text() for lbl in w.monitor.net_vals][3:], ["TEMPLATE-MAIL v1", "INTERNET", "● active", "n/a"])
        w.destroy()

    def test_lock_states_in_block(self):
        w = self.window(raw())
        w.details_btn.clicked()                                  # 0.7.4: Live Monitor öffnen
        self.assertEqual(w.monitor.net_vals[5].get_text(), "● active")
        self.ev.net_check = lambda: (False, "test")
        w.refresh()
        self.assertEqual(w.monitor.net_vals[5].get_text(), "■ INACTIVE – VMs blocked")
        w.destroy()

    def test_sparkline_bounded_and_change_only(self):
        import evoxd.gui as G
        sp = G.Sparkline()
        self.assertTrue(sp.set(range(450)))
        self.assertEqual(len(sp.hist), livestats.CPU_HISTORY_LEN)
        self.assertTrue(sp.set((5,)))
        self.assertFalse(sp.set((5, 5, 5)))                                      # konstant → kein Neuzeichnen
        self.assertTrue(sp.set((5, 5, 7)))
        self.assertEqual(G.spark_key((1, 1, 2, 2, 1)), (1, 2, 1))

    def test_meter_no_redraw_when_unchanged_and_no_timer_unmapped(self):
        import evoxd.gui as G
        m = G.MeterBar(zones=True)
        self.assertTrue(m.set(40, 50, "#00ff00"))
        self.assertFalse(m.set(40, 50, "#00ff00"))
        self.assertTrue(m.set(70, 70, "#00ff00"))
        self.assertIsNone(m._tick_cb)                                            # ungemappt: sofort, kein Tick
        self.assertEqual(m._shown, (70, 70))
        self.assertTrue(m.set(70, 70, "#ff0000"))                                # nur Farbe → neu zeichnen

    def test_draw_offscreen_and_transition_ends(self):
        import time
        import evoxd.gui as G
        win = Gtk.OffscreenWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        m, sp = G.MeterBar(zones=True), G.Sparkline()
        m.set_size_request(200, G.METER_HEIGHT)
        box.pack_start(m, False, False, 0)
        box.pack_start(sp, False, False, 0)
        win.add(box)
        win.show_all()

        def pump(sec):
            end = time.monotonic() + sec
            while time.monotonic() < end:
                Gtk.main_iteration_do(False)
                time.sleep(0.01)
        m.set(20, 30, "#57e389")
        sp.set([0, 50, 100, 20])
        pump(0.2)
        self.assertIsNotNone(win.get_pixbuf())                                   # draw lief ohne Fehler
        m.set(80, 90, "#ff7b72")                                                 # gemappt: weicher Übergang
        self.assertIsNotNone(m._tick_cb)
        pump(G.TRANSITION_S + 0.5)
        self.assertIsNone(m._tick_cb)                                            # Tick entfernt sich selbst
        self.assertEqual(m._shown, (80, 90))
        m.set(None, None)                                                        # n/a: sofort leer
        self.assertIsNone(m._tick_cb)
        pump(0.1)
        win.destroy()

    def test_unchanged_cycle_zero_calls_with_blocks(self):
        from tests.test_cycle import WATCH
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB, cpu=10**9, nets=[(5, 6)], overlay=2**20))
        w.details_btn.clicked()                                  # 0.7.4: Live Monitor öffnen
        for _ in range(3):
            self.clock.t += 5
            w.refresh()
        calls = Counter()
        with contextlib.ExitStack() as st:
            for cls, name, kind in WATCH:
                orig = getattr(cls, name)
                st.enter_context(mock.patch.object(cls, name, lambda *a, _o=orig, _k=kind, **k: (
                    calls.update([_k]), _o(*a, **k))[1]))
            for _ in range(3):
                self.clock.t += 5
                w.refresh()
        self.assertEqual(dict(calls), {})
        self.assertEqual(len(w.monitor.cpu_spark.hist), 1)                               # Bild unverändert (nur 1. Wert)
        w.destroy()

@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class StopHintTest(GuiBase):
    def open_stop(self, w, resp=Gtk.ResponseType.CANCEL, click=False):
        seen = {}

        def run(dlg):
            seen["focus"] = dlg.get_focus().get_label() if dlg.get_focus() else None
            seen["hint"] = dlg.ram_hint.get_text() if dlg.ram_hint else None
            seen["btn"] = dlg.remember_btn.get_label() if dlg.remember_btn else None
            if click and dlg.remember_btn:
                dlg.remember_btn.clicked()
                seen["after"] = (dlg.remember_btn.get_label(), dlg.remember_btn.get_sensitive())
            return resp
        with mock.patch.object(Gtk.MessageDialog, "run", run):
            w.on_stop(None)
        return seen

    def test_high_hint_and_remember_button(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB // 5))            # 90 %
        seen = self.open_stop(w, click=True)
        self.assertEqual(seen["focus"], "Cancel")                                # Anfangsfokus unverändert
        self.assertTrue(seen["hint"].startswith("■ RAM peak"), seen["hint"])
        self.assertIn(f"Next time choose more RAM: {d(2.25, 2)} GB", seen["hint"])    # 0.7.3 (angepasst)
        self.assertEqual(seen["btn"], f"Remember {d(2.25, 2)} GB for EMAIL")
        self.assertEqual(seen["after"], (f"✔ Remembered {d(2.25, 2)} GB for EMAIL", False))
        self.assertEqual(self.ev.s.load_remembered_ram(), {"EMAIL": 2304})      # nur gemerkte Größe
        self.assertEqual([t["name"] for t in self.ev.list_temps()], [self.name])   # Abbrechen: VM bleibt
        w.destroy()

    def test_remember_button_does_not_confirm(self):
        w = self.window(raw(avail=4 * GIB_KIB, usable=int(GIB_KIB * 3.4), cur_kib=4 * GIB_KIB))   # 0,6 von 4
        seen = self.open_stop(w, click=True)
        self.assertEqual(seen["hint"], f"○ RAM peak only {d(0.6)} GiB of {d(4)} GiB. Next time 1 GB is enough.")
        self.assertEqual(self.ev.s.load_remembered_ram(), {"EMAIL": 1024})       # 0.7.3 (angepasst)
        self.assertEqual(len(self.ev.list_temps()), 1)
        w.destroy()

    def test_full_hint(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=0))
        self.assertIn("RAM was full 1 times", self.open_stop(w)["hint"])
        w.destroy()

    def test_ok_hint_without_button(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        seen = self.open_stop(w)
        self.assertEqual(seen["hint"], f"● RAM peak {d(1)} GiB of {d(2)} GiB (50 %). The size fits.")
        self.assertIsNone(seen["btn"])
        w.destroy()

    def test_na_or_estimate_no_hint(self):
        for stats in (raw(), raw(rss=2 * GIB_KIB)):
            w = self.window(stats)
            seen = self.open_stop(w)
            self.assertIsNone(seen["hint"])
            self.assertIsNone(seen["btn"])
            self.assertEqual(seen["focus"], "Cancel")
            w.destroy()
            self.ev.stop(self.name)

    def test_hint_error_never_disturbs_dialog(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        with mock.patch.object(w.live, "summary", side_effect=RuntimeError("boom")):
            seen = self.open_stop(w)
        self.assertIsNone(seen["hint"])
        self.assertEqual(seen["focus"], "Cancel")
        w.destroy()

    def test_stop_records_purpose_peak(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        self.open_stop(w, resp=Gtk.ResponseType.OK)
        for _ in range(100):
            if not w.busy:
                break
            Gtk.main_iteration_do(False)
            import time
            time.sleep(0.02)
        w.refresh()                                                              # VM weg → Spitze gesichert
        self.assertEqual(self.ev.s.load_purpose_stats()["EMAIL"]["peak_mib"], 1024)
        w.destroy()

    def test_window_close_records_peak_and_estimate_not(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB // 2))
        w.destroy()
        self.assertEqual(self.ev.s.load_purpose_stats()["EMAIL"]["peak_mib"], 1536)
        self.ev.stop(self.name)
        w = self.window(raw(rss=2 * GIB_KIB), purpose="WEB")
        w.destroy()
        self.assertNotIn("WEB", {k for k, v in self.ev.s.load_purpose_stats().items() if v["peak_mib"]})


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class StartDialogInfoTest(GuiBase):
    def test_peak_info_only_hint(self):
        import evoxd.gui as G
        self.ev.s.record_purpose_peak("EMAIL", 1126)
        self.ev.s.save_last_start(2048, 2, "EMAIL")
        w = G.MainWindow(self.ev)
        dlg = G.StartDialog(w, self.ev, "TEMPLATE-MAIL")
        self.assertTrue(dlg.peak_lbl.get_visible())
        self.assertEqual(dlg.peak_lbl.get_text(), f"So far EMAIL needed up to {d(1.1)} GiB. "
                                                  f"Recommended: {d(1.5)} GB.")     # 0.7.3: + Empfehlung
        self.assertEqual(dlg.memory_mib, 2048)                                   # Auswahl unverändert
        dlg.purpose.get_child().set_text("WEB")
        self.assertFalse(dlg.peak_lbl.get_visible())
        self.assertEqual(dlg.memory_mib, 2048)
        dlg.destroy()
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class Step4GlowTest(unittest.TestCase):
    def test_colors_constants_and_css(self):
        import evoxd.gui as G
        self.assertEqual((G.STEP4_INTERNET_RING, G.STEP4_INTERNET_GLOW), ("#9BF5AE", "#39D353"))
        self.assertEqual((G.STEP4_OFFLINE_RING, G.STEP4_OFFLINE_GLOW), ("#4DA3FF", "#0060b3"))
        self.assertEqual(G.STEP4_GLOW_PX, 10)
        self.assertIn(".evox-next.evox-start-disposable { box-shadow: 0 0 0 2px #9BF5AE, 0 0 10px 3px #39D353; }", G.CSS)
        self.assertIn(".evox-next.evox-start-offline { box-shadow: 0 0 0 2px #4DA3FF, 0 0 10px 3px #0060b3; }", G.CSS)
        self.assertIn(".evox-next { box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.9)", G.CSS)   # Schritte 1–3 weiß
        self.assertIn(f".evox-next.evox-start-disposable:focus {{ box-shadow: {G._FOCUS_INSET}, 0 0 0 2px #9BF5AE, "
                      f"{G._FOCUS_GLOW}; }}", G.CSS)                       # Limette-Fokus bleibt (FOCUS_COLOR im Schein)
        self.assertIn(G.FOCUS_COLOR, G._FOCUS_GLOW)
        self.assertNotIn(G.FOCUS_COLOR.lower(), (G.STEP4_INTERNET_RING + G.STEP4_OFFLINE_RING).lower())
        self.assertEqual(G.HOWTO_CLASSES[3:], ("evox-start-disposable", "evox-start-offline"))
        css = Gtk.CssProvider()
        css.load_from_data(G.CSS.encode())                                       # CSS gültig


if __name__ == "__main__":
    unittest.main()
