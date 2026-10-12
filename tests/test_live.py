"""0.7.0 (A3): Live-Werte, check_viewer-Fehler, Remember for purpose – nur Attrappen (FakeHypervisor, nospawn)."""
import contextlib
import json
import sys
import tempfile
import time
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from evoxd import capacity, config, livestats
from evoxd.config import Settings
from evoxd.lifecycle import Evox
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor
from tests.nospawn import NoSpawnMixin

HAVE_DISPLAY = Gtk.init_check([])[0]
GIB_KIB = 2**20
OVL = config.OVERLAY_PATH + "/x.qcow2"


def raw(cur_kib=2 * GIB_KIB, avail=None, usable=None, unused=None, rss=None, cpu=None, nets=None, overlay=None):
    """Roh-Statistik im libvirt-Format (domainListGetStats)."""
    r = {"balloon.current": cur_kib, "balloon.maximum": cur_kib}
    for k, v in (("balloon.available", avail), ("balloon.usable", usable), ("balloon.unused", unused),
                 ("balloon.rss", rss), ("cpu.time", cpu)):
        if v is not None:
            r[k] = v
    if nets is not None:
        r["net.count"] = len(nets)
        for i, (rx, tx) in enumerate(nets):
            r[f"net.{i}.rx.bytes"], r[f"net.{i}.tx.bytes"] = rx, tx
    if overlay is not None:
        r.update({"block.count": 2, "block.0.path": "/var/lib/libvirt/images/other.qcow2", "block.0.physical": 1,
                  "block.1.path": OVL, "block.1.physical": overlay, "block.1.allocation": 7})
    return r


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class LiveStatsTest(unittest.TestCase):
    """Reine Logik (ohne GTK)."""

    def sampler(self):
        self.clock, self.wall = Clock(), Clock(10_000.0)
        return livestats.LiveSampler(clock=self.clock, wall=self.wall)

    def test_ram_level_thresholds(self):
        cases = {None: None, 0: "low", 29: "low", 30: "ok", 60: "ok", 61: "high", 85: "high", 86: "full", 100: "full"}
        for pct, want in cases.items():
            self.assertEqual(livestats.ram_level(pct), want, pct)

    def test_runtime_format(self):
        cases = {None: "n/a", -5: "n/a", 0: "<1 min", 59: "<1 min", 60: "1 min", 3599: "59 min",
                 3600: "1 h 00 min", 3600 + 5 * 60: "1 h 05 min", 86400 + 3600 + 59: "1 d 1 h"}
        for sec, want in cases.items():
            self.assertEqual(livestats.fmt_runtime(sec), want, sec)

    def test_bytes_format(self):
        self.assertEqual(livestats.fmt_bytes(None), "n/a")
        self.assertEqual(livestats.fmt_bytes(500), "500 B")
        self.assertEqual(livestats.fmt_bytes(3 * 1024), "3 KiB")
        self.assertEqual(livestats.fmt_bytes(int(1.5 * 2**20)), f"{capacity.fmt_dec(1.5)} MiB")
        self.assertEqual(livestats.fmt_bytes(2 * 2**30), f"{capacity.fmt_dec(2)} GiB")

    def test_guest_stats_exact(self):
        s = self.sampler()
        v = s.sample("A", raw(avail=2 * GIB_KIB, usable=GIB_KIB), mem_mib=2048, vcpus=2, created=10_000 - 125)
        self.assertEqual((v["ram_used"], v["ram_size"], v["ram_est"], v["ram_pct"]), (2**30, 2**31, False, 50))
        self.assertEqual(v["ram_level"], "ok")
        self.assertEqual(livestats.fmt_runtime(v["runtime"]), "2 min")

    def test_unused_used_when_usable_missing(self):
        v = self.sampler().sample("A", raw(avail=2 * GIB_KIB, unused=GIB_KIB // 2), mem_mib=2048)
        self.assertEqual(v["ram_pct"], 75)
        self.assertEqual(v["ram_level"], "high")

    def test_rss_estimate_marked_and_capped(self):
        s = self.sampler()
        v = s.sample("A", raw(rss=GIB_KIB), mem_mib=2048)
        self.assertTrue(v["ram_est"])
        self.assertEqual(v["ram_pct"], 50)
        v = s.sample("A", raw(rss=3 * GIB_KIB), mem_mib=2048)           # RSS > Gast-RAM (QEMU-Anteil): gekappt
        self.assertEqual((v["ram_pct"], v["ram_level"]), (100, "full"))

    def test_no_stats_is_na(self):
        v = self.sampler().sample("A", None, mem_mib=2048, vcpus=2)
        for k in ("ram_used", "ram_pct", "ram_level", "peak", "cpu_pct", "rx", "tx", "overlay", "runtime"):
            self.assertIsNone(v[k], k)
        self.assertFalse(v["cpu_wait"])

    def test_garbage_values_ignored(self):
        bad = {"balloon.current": "x", "balloon.available": -1, "balloon.usable": True, "balloon.rss": "9",
               "cpu.time": -3, "net.count": "2", "block.count": None}
        v = self.sampler().sample("A", bad, mem_mib=2048)
        self.assertIsNone(v["ram_pct"])
        self.assertIsNone(v["cpu_pct"])
        self.assertIsNone(v["rx"])
        self.assertIsNone(v["overlay"])

    def test_peak_kept_and_forgotten(self):
        s = self.sampler()
        s.sample("A", raw(avail=2 * GIB_KIB, usable=GIB_KIB // 2), mem_mib=2048)   # 75 %
        v = s.sample("A", raw(avail=2 * GIB_KIB, usable=GIB_KIB * 3 // 2), mem_mib=2048)   # 25 %
        self.assertEqual((v["ram_pct"], v["ram_level"], v["peak_pct"]), (25, "low", 75))
        s.forget(["B"])                                                  # VM weg → Spitze vergessen
        v = s.sample("A", raw(avail=2 * GIB_KIB, usable=GIB_KIB * 3 // 2), mem_mib=2048)
        self.assertEqual(v["peak_pct"], 25)

    def test_cpu_percent(self):
        s = self.sampler()
        v = s.sample("A", raw(cpu=0), vcpus=2)
        self.assertTrue(v["cpu_wait"])
        self.assertIsNone(v["cpu_pct"])
        self.clock.t += 5
        v = s.sample("A", raw(cpu=int(5e9)), vcpus=2)                   # 5 s CPU in 5 s bei 2 vCPUs = 50 %
        self.assertEqual(v["cpu_pct"], 50)
        self.clock.t += 5
        v = s.sample("A", raw(cpu=int(50e9)), vcpus=2)                  # unmöglich viel → auf 100 % begrenzt
        self.assertEqual(v["cpu_pct"], 100)
        self.clock.t += 5
        v = s.sample("A", raw(cpu=10), vcpus=2)                         # Zähler kleiner (neue VM gleichen Namens)
        self.assertIsNone(v["cpu_pct"])
        self.assertTrue(v["cpu_wait"])

    def test_net_and_overlay(self):
        s = self.sampler()
        v = s.sample("A", raw(nets=[(1000, 10), (24, 6)], overlay=5 * 2**20))
        self.assertEqual((v["rx"], v["tx"], v["overlay"]), (1024, 16, 5 * 2**20))
        v = s.sample("A", raw(nets=[]))
        self.assertEqual((v["rx"], v["tx"]), ("none", "none"))           # Offline-VM: keine Schnittstelle
        r = raw(nets=[(1, 2)])
        del r["net.0.tx.bytes"]
        self.assertEqual(s.sample("A", r)["rx"], None)                   # unvollständig → n/a
        r = raw(overlay=1)
        r["block.1.path"] = "/var/lib/libvirt/images/foreign.qcow2"
        self.assertIsNone(s.sample("A", r)["overlay"])                   # nur Dateien im Overlay-Ordner


class RememberConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self.tmp.name) / "evoxd" / "config.json"
        self.s = Settings(config_file=self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_and_invalid_entries(self):
        self.assertEqual(self.s.load_remembered_ram(), {})
        self.cfg.parent.mkdir(parents=True)
        self.cfg.write_text(json.dumps({config.REMEMBER_KEY: {
            "EMAIL": 3072, "WEB": True, "BANK": "4096", "email": 2048, "TOOLONGPURPOSE12345": 2048,
            "LOW": 512, "HIGH": 10**6, "OK2": 1024, "A-B": 2048}}))
        self.assertEqual(self.s.load_remembered_ram(), {"EMAIL": 3072, "OK2": 1024})
        self.cfg.write_text(json.dumps({config.REMEMBER_KEY: [1, 2]}))
        self.assertEqual(self.s.load_remembered_ram(), {})

    def test_write_change_forget_and_keep_other_keys(self):
        self.cfg.parent.mkdir(parents=True)
        self.cfg.write_text(json.dumps({"purposes": ["EMAIL", "WEB"], "host_reserve_mib": 3072}))
        self.assertTrue(self.s.remember_ram("EMAIL", 4096))
        data = json.loads(self.cfg.read_text())
        self.assertEqual(data[config.REMEMBER_KEY], {"EMAIL": 4096})
        self.assertEqual((data["purposes"], data["host_reserve_mib"]), (["EMAIL", "WEB"], 3072))   # rückwärtskompatibel
        self.assertEqual(oct(self.cfg.stat().st_mode & 0o777), "0o600")
        mtime = self.cfg.stat().st_mtime_ns
        self.assertFalse(self.s.remember_ram("EMAIL", 4096))             # unverändert → nicht geschrieben
        self.assertEqual(self.cfg.stat().st_mtime_ns, mtime)
        self.assertFalse(self.s.remember_ram("WEB", None))               # nichts zu vergessen → nicht geschrieben
        self.assertTrue(self.s.remember_ram("EMAIL", None))
        self.assertEqual(json.loads(self.cfg.read_text())[config.REMEMBER_KEY], {})
        self.assertEqual(Settings.load(self.cfg).host_reserve_mib, 3072)

    def test_invalid_input_never_written(self):
        for p, v in (("email", 2048), ("A-B", 2048), ("", 2048), ("EMAIL", 512), ("EMAIL", 10**6),
                     ("EMAIL", "2048"), ("EMAIL", 2048.0)):
            self.assertFalse(self.s.remember_ram(p, v), (p, v))
        self.assertFalse(self.cfg.exists())

    def test_broken_file_backed_up_before_write(self):
        self.cfg.parent.mkdir(parents=True)
        self.cfg.write_text("{kaputt")
        self.assertEqual(self.s.load_remembered_ram(), {})
        self.assertTrue(self.s.remember_ram("EMAIL", 2048))
        backups = list(self.cfg.parent.glob("config.json.broken-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "{kaputt")
        self.assertEqual(json.loads(self.cfg.read_text()), {config.REMEMBER_KEY: {"EMAIL": 2048}})

    def test_only_ram_is_stored(self):
        self.s.remember_ram("EMAIL", 2048)
        data = json.loads(self.cfg.read_text())
        self.assertEqual(list(data), [config.REMEMBER_KEY])
        self.assertTrue(all(isinstance(v, int) for v in data[config.REMEMBER_KEY].values()))


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class LiveGuiTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        s = Settings(state_dir=d / "st", runtime_dir=d / "rt", guard_status=d / "x", config_file=d / "cfg.json")
        self.hv = FakeHypervisor()
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.hv.add_foreign("OTHER-VM", state="running")
        self.reg = Registry(s.registry_path)
        self.ev = Evox(s, self.hv, self.reg, net_check=lambda: (True, ""),
                       meminfo=lambda: {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20})
        self.ev.import_template("TEMPLATE-MAIL")

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def window(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        self.clock = Clock()
        w.live = livestats.LiveSampler(clock=self.clock, wall=lambda: self.reg.temp(self.name).created + 3700)
        w.refresh()
        return w

    def start(self, stats=None):
        r = self.ev.start("TEMPLATE-MAIL")
        self.name = r.name
        if stats is not None:
            self.hv.stats[r.name] = stats
        return r

    def select(self, w):
        w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))

    def live_cells(self, w):
        return list(w.store[0])[w.live_col:w.live_col + 4]

    def test_normal_values_in_list_and_details(self):
        import evoxd.gui as G
        self.start(raw(avail=2 * GIB_KIB, usable=GIB_KIB, cpu=0, nets=[(3 * 2**20, 2**20)], overlay=256 * 2**20))
        w = self.window()
        self.select(w)
        w.details_btn.clicked()                                  # 0.7.4: Live Monitor öffnen
        self.clock.t += 5
        self.hv.stats[self.name]["cpu.time"] = int(2.5e9)
        w.refresh()
        self.assertEqual(self.live_cells(w), ["1 h 01 min", "● 50 %", "25 %", w.colors["ok"]])   # 0.7.1 Reihenfolge
        d = capacity.fmt_dec
        self.assertEqual(w.monitor.ram_line.get_text(), f"● OK  {d(1)} / {d(2)} GiB (50 %)")
        self.assertRegex(w.monitor.ram_peak.get_text(), rf"^Peak {d(1)} GiB \(50 %\) at \d\d:\d\d$")
        self.assertEqual(w.monitor.cpu_line.get_text(), "25 % of 2 vCPU(s)")
        txt = [lbl.get_text() for lbl in w.monitor.net_vals]
        self.assertEqual(txt[:3], [f"↓ {d(3)} MiB   ↑ {d(1)} MiB", f"{d(256)} MiB · peak {d(256)} MiB", "1 h 01 min"])
        self.assertIn(w.colors["ok"], w.monitor.ram_line.get_label())           # Farbe zusätzlich zu Symbol + Wort
        self.assertEqual(len(w.view.get_columns()), len(G.T.COLUMNS) + len(G.T.LIVE_COLUMNS))
        w.destroy()

    def test_high_and_full_levels_with_symbol(self):
        self.start(raw(avail=2 * GIB_KIB, usable=GIB_KIB // 2))      # 75 % → HIGH (0.7.1: 61–85 %)
        w = self.window()
        self.select(w)
        w.details_btn.clicked()                                  # 0.7.4: Live Monitor öffnen
        self.assertEqual(self.live_cells(w)[1], "▲ 75 %")
        self.assertEqual(self.live_cells(w)[3], w.colors["warn"])
        self.assertTrue(w.monitor.ram_line.get_text().startswith("▲ HIGH"))
        self.hv.stats[self.name]["balloon.usable"] = 0                  # 100 % → FULL
        w.refresh()
        self.assertEqual(self.live_cells(w)[1], "■ 100 %")
        self.assertEqual(self.live_cells(w)[3], w.colors["bad"])
        self.assertIn(f"Peak {capacity.fmt_dec(2)} GiB (100 %)", w.monitor.ram_peak.get_text())
        self.assertIn("RAM full (over 95 %): 1×", w.monitor.ram_peak.get_text())
        w.destroy()

    def test_estimate_marked(self):
        self.start(raw(rss=GIB_KIB // 2))
        w = self.window()
        self.select(w)
        w.details_btn.clicked()                                  # 0.7.4: Live Monitor öffnen
        self.assertEqual(self.live_cells(w)[1], "○ ~25 %")
        self.assertIn("(est.)", w.monitor.ram_line.get_text())
        w.destroy()

    def test_na_without_stats(self):
        self.start()
        w = self.window()
        self.select(w)
        w.details_btn.clicked()                                  # 0.7.4: Live Monitor öffnen
        self.assertEqual(self.live_cells(w), ["1 h 01 min", "n/a", "n/a", ""])
        self.assertEqual(w.monitor.ram_line.get_text(), "RAM use n/a – the guest reports no memory figures.")
        self.assertEqual(w.monitor.cpu_line.get_text(), "n/a")
        self.assertEqual([lbl.get_text() for lbl in w.monitor.net_vals][:3], ["n/a", "n/a", "1 h 01 min"])
        w.destroy()

    def test_offline_vm_shows_no_network(self):
        self.start(raw(nets=[]))
        w = self.window()
        self.select(w)
        w.details_btn.clicked()                                  # 0.7.4: Live Monitor öffnen
        self.assertEqual(w.monitor.net_vals[0].get_text(), "no network (offline)")
        w.destroy()

    def test_stats_error_never_disturbs_gui(self):
        self.start(raw(avail=2 * GIB_KIB, usable=GIB_KIB))
        self.hv.stats_error = RuntimeError("libvirt: stats failed")
        w = self.window()
        self.select(w)
        w.safe_refresh()
        self.assertNotIn("stats failed", w.msg.get_text())
        self.assertEqual(self.live_cells(w)[1:3], ["n/a", "n/a"])
        self.hv.stats_error = None                                       # danach wieder Werte
        w.refresh()
        self.assertEqual(self.live_cells(w)[1], "● 50 %")
        with mock.patch.object(type(self.hv), "domain_stats", lambda *_: "kein dict"):
            w.refresh()
        self.assertEqual(self.live_cells(w)[1], "n/a")
        w.destroy()

    def test_reads_only_own_running_vms_and_nothing_when_idle(self):
        w = self.window()
        w.refresh()
        self.assertEqual(self.hv.stats_calls, 0)                         # keine Wegwerf-VM → kein Aufruf
        seen = []
        orig = self.hv.domain_stats
        self.hv.domain_stats = lambda names: (seen.append(list(names)), orig(names))[1]
        self.start(raw())
        w.refresh()
        self.assertEqual(seen, [[self.name]])                            # nie fremde VMs (OTHER-VM)
        w.destroy()

    def test_changed_values_update_cells_only(self):
        self.start(raw(avail=2 * GIB_KIB, usable=GIB_KIB, cpu=0))
        w = self.window()
        self.select(w)
        w.refresh()
        calls = Counter()
        watch = [(Gtk.ListStore, "clear"), (Gtk.ListStore, "append"), (Gtk.ListStore, "set_value"),
                 (Gtk.TreeSelection, "select_iter"), (Gtk.TreeSelection, "unselect_all")]
        with contextlib.ExitStack() as st:
            for cls, name in watch:
                orig = getattr(cls, name)
                st.enter_context(mock.patch.object(cls, name, lambda *a, _o=orig, _n=name, **k: (
                    calls.update([_n]), _o(*a, **k))[1]))
            self.hv.stats[self.name]["balloon.usable"] = GIB_KIB // 2       # 75 %
            w.refresh()
        self.assertEqual(calls["clear"] + calls["append"] + calls["select_iter"] + calls["unselect_all"], 0)
        self.assertEqual(calls["set_value"], 2)                          # RAM-Text + Ampelfarbe
        self.assertEqual(w.selected(), self.name)                        # Auswahl bleibt
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class LiveCycleTest(NoSpawnMixin, unittest.TestCase):
    """Unveränderter 5-s-Zyklus mit laufender VM und Live-Werten: 0 GTK-Aufrufe (test_cycle zählt dieselben Arten)."""

    def setUp(self):
        from tests.test_cycle import CycleTest
        self.c = CycleTest("test_unchanged_cycle_makes_no_gtk_calls")
        self.c.setUp()
        name = self.c.ev.list_temps()[0]["name"]
        self.c.hv.stats[name] = raw(avail=2 * GIB_KIB, usable=GIB_KIB, cpu=10**9, nets=[(5, 6)], overlay=2**20)

    def tearDown(self):
        self.c.tearDown()

    def test_unchanged_cycle_zero_calls_with_live_values(self):
        c = self.c
        import evoxd.gui as G
        w = G.MainWindow(c.ev)
        created = c.ev.list_temps()[0]["created"]
        w.live.wall = lambda: created + 600
        w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
        w.details_btn.clicked()                                  # 0.7.4: Live Monitor öffnen
        c.cycle(w)
        c.cycle(w)
        self.assertEqual(w.monitor.cpu_line.get_text(), "0 % of 2 vCPU(s)")      # konstanter Zähler → 0 %
        with c.counting():
            c.calls.clear()
            c.cycle(w)
            c.cycle(w)
        self.assertEqual(dict(c.calls), {}, "unnötige GTK-Aufrufe im unveränderten Zyklus")
        self.assertGreaterEqual(c.hv.stats_calls, 4)                     # Werte wurden wirklich gelesen
        w.destroy()


class _Proc:
    """Attrappe für virt-viewer, der mit Fehler beendet ist."""
    def poll(self):
        return 1


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class ViewerCheckTest(NoSpawnMixin, unittest.TestCase):
    """check_viewer: "ValueError: seek of closed file" (bis 0.6.21) – Ursache und Behebung."""

    def setUp(self):
        GuiSetup.setUp(self)
        self.errors = []
        self._hook = sys.excepthook
        sys.excepthook = lambda *a: self.errors.append(a[1])            # PyGObject meldet Callback-Fehler hierüber

    def tearDown(self):
        sys.excepthook = self._hook
        GuiSetup.tearDown(self)

    def opener(self, _name):
        self.err = tempfile.TemporaryFile()
        self.err.write(b"Domain not found\n")
        return _Proc(), self.err

    def pump(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            Gtk.main_iteration_do(False)
            time.sleep(0.01)

    def test_cause_reading_closed_file(self):
        """Ursache [B]: viewer_error liest aus err; ist err schon geschlossen → genau dieser ValueError."""
        from evoxd.cli import viewer_error
        _p, err = self.opener("x")
        err.close()
        with self.assertRaisesRegex(ValueError, "seek of closed file"):
            viewer_error(_Proc(), err)

    def test_direct_call_then_timer_no_error(self):
        """Ablauf wie im Testlauf bis 0.6.21: direkter Aufruf schließt err, der Zeitgeber feuerte später erneut."""
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        with mock.patch.object(G, "VIEWER_CHECK_S", 1):
            chk = w.show_vm("DISPOSABLE-X-01", opener=self.opener)
            src = chk.state["src"]
            chk()
            self.assertTrue(self.err.closed)
            self.assertIsNone(GLib.MainContext.default().find_source_by_id(src))   # Zeitgeber entfernt
            self.pump(2.6)
            chk()                                                        # weiterer Aufruf: tut nichts
        self.assertEqual(self.errors, [])
        self.assertEqual(w.msg.get_text(), "VM window could not be opened (virt-viewer exit 1): Domain not found")
        self.assertEqual(w._viewer_checks, {})
        w.destroy()

    def test_timer_then_direct_call_no_error(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        with mock.patch.object(G, "VIEWER_CHECK_S", 1):
            chk = w.show_vm("DISPOSABLE-X-01", opener=self.opener)
            self.pump(2.6)
            self.assertTrue(self.err.closed)                             # Zeitgeber hat geprüft und geschlossen
            chk()
        self.assertEqual(self.errors, [])
        w.destroy()

    def test_window_closed_before_check(self):
        """Fenster zu, bevor die Prüfung lief: Zeitgeber weg, Datei zu, keine Meldung an das zerstörte Fenster."""
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        with mock.patch.object(G, "VIEWER_CHECK_S", 1):
            chk = w.show_vm("DISPOSABLE-X-01", opener=self.opener)
            src = chk.state["src"]
            w.destroy()
            self.assertTrue(self.err.closed)
            self.assertIsNone(GLib.MainContext.default().find_source_by_id(src))
            self.pump(2.6)
        self.assertEqual(self.errors, [])

    def test_read_error_ignored(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        with mock.patch.object(G, "viewer_error", side_effect=OSError("io")):
            chk = w.show_vm("DISPOSABLE-X-01", opener=self.opener)
            chk()
        self.assertTrue(self.err.closed)
        self.assertEqual(self.errors, [])
        w.destroy()

    def test_old_code_would_fail(self):
        """Gegenprobe [B]: der alte Ablauf (zweimal prüfen, ohne Schutz) wirft den ValueError."""
        from evoxd.cli import viewer_error
        _p, err = self.opener("x")

        def old_check():
            text = viewer_error(_p, err)
            err.close()
            return text
        old_check()
        with self.assertRaisesRegex(ValueError, "seek of closed file"):
            old_check()


class GuiSetup:
    @staticmethod
    def setUp(t):
        t.tmp = tempfile.TemporaryDirectory()
        d = Path(t.tmp.name)
        t.s = Settings(state_dir=d / "st", runtime_dir=d / "rt", guard_status=d / "x", config_file=d / "cfg.json")
        t.hv = FakeHypervisor()
        t.hv.add_foreign("TEMPLATE-MAIL")
        t.reg = Registry(t.s.registry_path)
        t.ev = Evox(t.s, t.hv, t.reg, net_check=lambda: (True, ""),
                    meminfo=lambda: {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20})
        t.ev.import_template("TEMPLATE-MAIL")

    @staticmethod
    def tearDown(t):
        t.reg.close()
        t.tmp.cleanup()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class RememberDialogTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        GuiSetup.setUp(self)

    def tearDown(self):
        GuiSetup.tearDown(self)

    def dialog(self):
        from evoxd.gui import StartDialog
        return StartDialog(None, self.ev, "TEMPLATE-MAIL")

    def test_default_off(self):
        d = self.dialog()
        self.assertEqual(d.purpose_text, "EMAIL")
        self.assertFalse(d.remember_chk.get_active())
        self.assertFalse(d.remember)
        self.assertEqual(d.remember_chk.get_label(), "Remember RAM for EMAIL")
        self.assertEqual(d.memory_mib, 2048)
        d.destroy()

    def test_remembered_value_suggested_and_checked(self):
        self.s.remember_ram("EMAIL", 4096)
        d = self.dialog()
        self.assertTrue(d.remember)
        self.assertEqual(d.memory_mib, 4096)
        d.purpose.get_child().set_text("WEB")                           # kein Wert für WEB: Haken aus, RAM bleibt
        self.assertFalse(d.remember_chk.get_active())
        self.assertEqual(d.remember_chk.get_label(), "Remember RAM for WEB")
        self.assertEqual(d.memory_mib, 4096)
        d.purpose.get_child().set_text("email")                          # Regel wie Name: groß
        self.assertTrue(d.remember)
        d.purpose.get_child().set_text("A-B")                            # ungültiger Zweck: Haken gesperrt
        self.assertFalse(d.remember_chk.get_sensitive())
        self.assertFalse(d.remember)
        d.destroy()

    def test_capacity_limits_remembered_value(self):
        self.s.remember_ram("EMAIL", 30 * 1024)                          # gültig, aber mehr als der Host erlaubt
        d = self.dialog()
        self.assertEqual(d.ram.get_value(), 9.75)                        # max. aus Kapazität (12 − 2 − 0,25; 0.7.3: 9,75)
        self.assertTrue(d.ok_btn.get_sensitive())
        d.destroy()

    def test_invalid_config_value_ignored(self):
        self.s.config_file.write_text(json.dumps({config.REMEMBER_KEY: {"EMAIL": 100}}))
        d = self.dialog()
        self.assertFalse(d.remember_chk.get_active())
        self.assertEqual(d.memory_mib, 2048)
        d.destroy()

    def test_save_on_start_and_forget(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        w.save_remember("email", 3072, True)
        self.assertEqual(self.s.load_remembered_ram(), {"EMAIL": 3072})
        w.save_remember("WEB", 2048, False)                              # aus, nichts gemerkt: nichts passiert
        self.assertEqual(self.s.load_remembered_ram(), {"EMAIL": 3072})
        w.save_remember("EMAIL", 3072, False)                            # Haken weggenommen: vergessen
        self.assertEqual(self.s.load_remembered_ram(), {})
        w.save_remember("A-B", 3072, True)                               # ungültiger Zweck: still ignoriert
        self.assertEqual(self.s.load_remembered_ram(), {})
        w.destroy()

    def test_on_start_passes_checkbox(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        self.s.remember_ram("EMAIL", 3072)

        def run(d):
            d.ram.set_value(4.0)
            return Gtk.ResponseType.OK
        with mock.patch.object(G.StartDialog, "run", run), mock.patch.object(w, "start_vm", lambda *a, **k: a):
            args = w.on_start(None, offline=True)
        self.assertEqual(self.s.load_remembered_ram(), {"EMAIL": 4096})
        self.assertTrue(args[4])                                         # Modus kommt nur vom Knopf (offline)
        self.assertNotIn("offline", json.dumps(json.loads(self.s.config_file.read_text())))
        w.destroy()

    def test_write_error_reported_not_blocking(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        with mock.patch.object(Settings, "remember_ram", side_effect=OSError("read-only")):
            w.save_remember("EMAIL", 2048, True)
        self.assertIn("could not be remembered", w.msg.get_text())
        w.destroy()


if __name__ == "__main__":
    unittest.main()
