"""0.7.3: HOW TO USE als Überschrift, Knopf OPEN/CLOSE DETAILS, Fenstergröße beim Öffnen/Schließen der Details,
Höhe nach Inhalt, RAM im 256-MiB-Raster, neue Empfehlung (Spitze + 25 %, 85-%-Regel) – nur Attrappen
(FakeHypervisor, nospawn), kein echtes libvirt."""
import json
import time
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from evoxd import config, domxml, livestats
from evoxd import texts as T
from evoxd.errors import AllowlistViolation, EvoxError
from tests.nospawn import NoSpawnMixin
from tests.test_a3b import HAVE_DISPLAY, GuiBase, d
from tests.test_core import spec
from tests.test_live import GIB_KIB, raw

G = 2**30


def pump(sec=0.5):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        Gtk.main_iteration_do(False)
        time.sleep(0.005)


class RamGridTest(NoSpawnMixin, unittest.TestCase):
    """Raster 256 MiB, Minimum 1024, Maximum MAX_MEMORY_MIB; streng in config, lifecycle und domxml."""

    def test_on_grid(self):
        for ok in (1024, 1280, 1536, 2304, 32768):
            self.assertTrue(config.ram_on_grid(ok), ok)
        for bad in (768, 1000, 1100, 1023, 2049, 32769, 33024, 0, -1024, True, "2048", 2048.0, None):
            self.assertFalse(config.ram_on_grid(bad), bad)

    def test_snap_old_values(self):
        self.assertEqual(config.snap_ram_mib(1024), 1024)
        self.assertEqual(config.snap_ram_mib(1100), 1024)          # nächster Schritt
        self.assertEqual(config.snap_ram_mib(1200), 1280)
        self.assertEqual(config.snap_ram_mib(3000), 3072)
        self.assertEqual(config.snap_ram_mib(1536), 1536)          # alte 0,5-GiB-Werte bleiben gültig
        self.assertEqual(config.snap_ram_mib(32767), 32768)        # nie über MAX
        for bad in (1023, 900, 32769, True, "2048", 1536.0, None):
            self.assertIsNone(config.snap_ram_mib(bad), bad)

    def test_domxml_strict(self):
        for mib in (1024, 1280, 2304, 32768):
            sp = spec()
            sp.memory_mib = mib
            root = ET.fromstring(domxml.build(sp))
            self.assertEqual(root.findtext("memory"), str(mib * 1024))
        for mib in (768, 1000, 1100, 2049, 32769, 33024):
            sp = spec()
            sp.memory_mib = mib
            with self.assertRaises(AllowlistViolation):
                domxml.build(sp)

    def test_domxml_only_memory_differs(self):
        """Andere RAM-Werte ändern nur memory/currentMemory/hard_limit – Geräteliste, Netz, Platte gleich."""
        a, b = spec(), spec()
        b.memory_mib = 1280
        ra, rb = ET.fromstring(domxml.build(a)), ET.fromstring(domxml.build(b))
        for path in ("memory", "currentMemory", "memtune"):
            ra.remove(ra.find(path))
            rb.remove(rb.find(path))
        self.assertEqual(ET.tostring(ra), ET.tostring(rb))


class RamGridStateTest(GuiBase):
    """Remember / last-start: alte Werte aufs Raster, ungültige ignoriert; Start prüft das Raster."""

    def cfg(self, data):
        self.ev.s.config_file.write_text(json.dumps(data))

    def test_remember_old_and_new(self):
        self.cfg({"remember_ram_mib": {"EMAIL": 3000, "WEB": 1536, "BANK": 900, "SHOP": 40000, "X1": "2048"},
                  "host_reserve_mib": 3072})
        self.assertEqual(self.ev.s.load_remembered_ram(), {"EMAIL": 3072, "WEB": 1536})
        self.assertFalse(self.ev.s.remember_ram("EMAIL", 1100))           # neu nur auf dem Raster
        self.assertTrue(self.ev.s.remember_ram("EMAIL", 1280))
        self.assertEqual(self.ev.s.load_remembered_ram()["EMAIL"], 1280)
        data = json.loads(self.ev.s.config_file.read_text())
        self.assertEqual(data["host_reserve_mib"], 3072)                 # andere Schlüssel bleiben

    def test_last_start_snapped(self):
        self.ev.s.state_dir.mkdir(parents=True, exist_ok=True)
        self.ev.s.last_start_path.write_text(json.dumps({"memory_mib": 3000, "vcpus": 2, "purpose": "EMAIL"}))
        self.assertEqual(self.ev.s.load_last_start()["memory_mib"], 3072)
        self.ev.s.last_start_path.write_text(json.dumps({"memory_mib": 512, "vcpus": 2, "purpose": "EMAIL"}))
        self.assertEqual(self.ev.s.load_last_start()["memory_mib"], self.ev.s.vm_memory_mib)

    def test_start_checks_grid(self):
        for mib in (1100, 2049, 768):
            with self.assertRaisesRegex(EvoxError, "steps of 256 MiB"):
                self.ev.start("TEMPLATE-MAIL", memory_mib=mib, vcpus=1)
        self.assertEqual(self.ev.list_temps(), [])
        r = self.ev.start("TEMPLATE-MAIL", memory_mib=1280, vcpus=1)
        self.assertTrue(r.name.startswith("DISPOSABLE-"))


class RecommendTest(NoSpawnMixin, unittest.TestCase):
    def test_table(self):
        for peak, want in ((0.5, 1024), (0.6, 1024), (0.8, 1024), (0.9, 1280), (1.6, 2048), (1.8, 2304)):
            sug = livestats.suggest_mib(int(peak * G))
            self.assertEqual(sug, want, peak)
            self.assertTrue(config.ram_on_grid(sug))

    def test_always_selectable(self):
        for mib in range(1, 40000, 37):
            sug = livestats.suggest_mib(mib * 2**20)
            self.assertTrue(config.ram_on_grid(sug), mib)
        self.assertEqual(livestats.suggest_mib(40 * G), config.MAX_MEMORY_MIB)
        self.assertEqual(livestats.suggest_mib(8 * G, max_mib=5000), 4864)       # Kapazität, aufs Raster abgerundet
        self.assertEqual(livestats.suggest_mib(8 * G, max_mib=500), 1024)        # nie unter 1 GB

    def test_85_percent_rule(self):
        self.assertTrue(livestats.needs_more(int(0.9 * G), G))
        self.assertTrue(livestats.needs_more(int(1.75 * G), 2 * G))
        self.assertFalse(livestats.needs_more(int(0.85 * 2 * G), 2 * G))         # genau 85 %: noch nicht
        self.assertEqual(livestats.ram_hint(int(0.9 * G), G, 0), ("high", 1280))
        # Rechnung kleiner als die jetzige Größe → trotzdem mehr RAM (mind. ein Schritt darüber)
        self.assertEqual(livestats.more_mib(int(0.5 * G), 2048), 2304)
        self.assertEqual(livestats.more_mib(int(30 * G), 32768), 32768)          # nie über MAX

    def test_no_values_no_hint(self):
        for bad in ((0, G, 0), (None, G, 0), (G, None, 0)):
            self.assertIsNone(livestats.ram_hint(*bad))

    def test_fmt_gb(self):
        self.assertEqual(livestats.fmt_ram_gb(1024), "1 GB")
        self.assertEqual(livestats.fmt_ram_gb(1280), f"{d(1.25, 2)} GB")
        self.assertEqual(livestats.fmt_ram_gb(1536), f"{d(1.5)} GB")
        self.assertEqual(livestats.fmt_ram_gb(2304), f"{d(2.25, 2)} GB")
        self.assertEqual(livestats.fmt_ram_gb(32768), "32 GB")


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class LayoutTest(GuiBase):
    def test_howto_title_own_line_above(self):
        import evoxd.gui as G_
        w = G_.MainWindow(self.ev)
        w.show_all()
        pump(0.3)
        bar = w.howto_title.get_parent()
        self.assertEqual(bar.get_orientation(), Gtk.Orientation.VERTICAL)
        self.assertEqual(bar.get_children(), [w.howto_title, w.howto_rows])
        t, b0 = w.howto_title.get_allocation(), w.howto_btns[0].get_allocation()
        self.assertLessEqual(t.y + t.height, b0.y)                              # Titel über Schritt 1
        self.assertEqual(w.howto_rows.get_allocation().width, bar.get_allocation().width)   # volle Breite
        a3, a4 = w.howto_btns[3].get_allocation(), w.howto_btns[4].get_allocation()
        self.assertLessEqual(abs(a3.width - a4.width), 1)                        # INTERNET/OFFLINE je zur Hälfte
        self.assertEqual(w.howto_title.get_text(), T.HOWTO_TITLE)
        w.destroy()

@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class WindowSizeTest(GuiBase):
    """Messung im echten (Test-)Fenster: Öffnen vergrößert nie, Schließen stellt die Größe wieder her."""

    def test_saved_height_limited_to_workarea(self):
        import evoxd.gui as G_
        self.ev.s.save_gui_state(1000, 5000, False, None)
        with mock.patch.object(G_, "workarea_height", return_value=900):
            w = G_.MainWindow(self.ev)
        self.assertEqual(w.get_default_size()[1], 900)
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class StartDialogGridTest(GuiBase):
    def dialog(self):
        import evoxd.gui as G_
        self.w = G_.MainWindow(self.ev)
        return G_.StartDialog(self.w, self.ev, "TEMPLATE-MAIL")

    def tearDown(self):
        self.w.destroy()
        super().tearDown()

    def test_spin_grid_and_display(self):
        dlg = self.dialog()
        adj = dlg.ram.get_adjustment()
        self.assertEqual(adj.get_step_increment(), 0.25)
        self.assertTrue(dlg.ram.get_snap_to_ticks())
        self.assertEqual(dlg.ram.get_range()[0], 1.0)
        self.assertEqual(dlg.ram.get_range()[1], 9.75)                           # Kapazität aufs Raster
        dlg.ram.set_value(1.25)
        self.assertEqual(dlg.memory_mib, 1280)
        self.assertEqual(dlg.ram.get_text(), d(1.25, 2))
        self.assertEqual(dlg.ram_unit.get_text(), "GB")                          # Einheit direkt daneben
        self.assertIs(dlg.ram_unit.get_parent(), dlg.ram.get_parent())
        dlg.ram.set_value(0.5)                                                  # unter Minimum → 1 GB
        self.assertEqual(dlg.memory_mib, 1024)
        dlg.ram.set_value(1.3)                                                  # außerhalb des Rasters → nächster Schritt
        self.assertEqual(dlg.memory_mib, 1280)
        dlg.ram.spin(Gtk.SpinType.STEP_FORWARD, 1)
        self.assertTrue(config.ram_on_grid(dlg.memory_mib))
        dlg.ram.set_value(50)
        self.assertEqual(dlg.memory_mib, 9984)                                   # 9,75 GB, nie darüber
        dlg.destroy()

    def test_remembered_old_value_on_grid(self):
        self.ev.s.config_file.write_text(json.dumps({"remember_ram_mib": {"EMAIL": 1100}}))
        self.ev.s.save_last_start(2048, 2, "EMAIL")
        dlg = self.dialog()
        self.assertTrue(dlg.remember_chk.get_active())
        self.assertEqual(dlg.memory_mib, 1024)
        dlg.destroy()

    def test_recommend_and_more(self):
        self.ev.s.record_purpose_peak("EMAIL", 1900)
        self.ev.s.save_last_start(2048, 2, "EMAIL")
        dlg = self.dialog()
        self.assertIn(T.DLG_RECOMMEND_MORE.format(sug=f"{d(2.5)} GB"), dlg.peak_lbl.get_text())   # 93 % von 2 GB
        dlg.ram.set_value(4)
        self.assertIn(T.DLG_RECOMMEND.format(sug=f"{d(2.5)} GB"), dlg.peak_lbl.get_text())
        self.assertEqual(dlg.memory_mib, 4096)                                   # Hinweis ändert die Auswahl nicht
        dlg.destroy()
