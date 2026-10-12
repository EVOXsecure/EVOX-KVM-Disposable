import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from evoxd import capacity, livestats
from evoxd import texts as T
from evoxd.config import Settings
from evoxd.lifecycle import Evox
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor
from tests.nospawn import NoSpawnMixin

HAVE_DISPLAY = Gtk.init_check([])[0]
g = livestats.fmt_gb1          # 0.7.4: Kapazität/Platz „6,8 GB“ (eine Stelle), Locale wie GTK


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class GuiTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        s = Settings(state_dir=d / "st", runtime_dir=d / "rt", guard_status=d / "x", config_file=d / "cfg.json")
        self.hv = FakeHypervisor()
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.reg = Registry(s.registry_path)
        self.mem = {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20}
        self.ev = Evox(s, self.hv, self.reg, net_check=lambda: (False, "guard not running"),
                       meminfo=lambda: self.mem)
        self.ev.import_template("TEMPLATE-MAIL")

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def test_window_lists_temps(self):
        from evoxd.gui import MainWindow
        r = self.ev.start("TEMPLATE-MAIL")
        import evoxd.gui as G
        from evoxd import texts as T
        w = MainWindow(self.ev)          # nicht anzeigen
        self.assertEqual(w.active_template(), "TEMPLATE-MAIL")
        self.assertEqual(list(w.store[0])[:3], [r.name, "running", "OFFLINE"])   # 0.7.1 schlank: Name, Zustand, Modus
        self.assertEqual(w.status.get_text(), "🔓 Network lock: INACTIVE – VMs are blocked completely")
        self.assertTrue(w.status.get_style_context().has_class("evox-lock-bad"))   # feste Gefahrfarbe
        self.assertIn(f".evox-lock-bad {{ color: {G.DANGER_COLOR}; font-weight: bold; }}", G.CSS)
        self.assertIn(T.LOCK_TIP, w.status.get_tooltip_text())
        self.assertEqual(w.console_btn.get_label(), "Show selected VM")
        self.assertIn(f"reserve {g(2048)}", w.host_lbl.get_text())
        self.assertIn(f"room for 4 VM(s) of {livestats.fmt_ram_gb(2048)}", w.host_lbl.get_text())   # gleiche Formulierung wie Dialog
        self.ev.net_check = lambda: (True, "")
        w.refresh()
        self.assertIn(w.colors["ok"], w.status.get_label())       # grün bei aktiv
        self.assertEqual(w.status.get_text(), "🔒 Network lock: active – VMs cannot reach your host or home network")
        self.assertFalse(w.status.get_style_context().has_class("evox-lock-bad"))
        self.assertEqual(w.status.get_tooltip_text(), T.LOCK_TIP)
        self.assertTrue(T.LOCK_TIP.startswith("Firewall on the host blocks every disposable VM"))
        self.assertEqual(w.status.get_ellipsize(), Pango.EllipsizeMode.END)
        self.assertEqual([w.tabs.buttons[k].get_label() for k in w.tabs.keys],
                         ["1. VAULT", "2. TEMPLATE", "3. DISPOSABLE"])
        self.assertTrue(T.DE_LOCK_OK.startswith("🔒 Netzsperre: aktiv") and "INAKTIV" in T.DE_LOCK_BAD)
        w.destroy()

    def test_show_vm_errors_in_status_line(self):
        from evoxd.errors import EvoxError
        from evoxd.gui import MainWindow
        w = MainWindow(self.ev)
        w.on_console(None)                                         # nichts gewählt
        self.assertEqual(w.msg.get_text(), "Select a disposable VM in the list first.")

        def missing(_n):
            raise EvoxError("virt-viewer is not installed.")
        w.show_vm("DISPOSABLE-X-01", opener=missing)
        self.assertEqual(w.msg.get_text(), "Error: virt-viewer is not installed.")

        import subprocess
        import sys
        import tempfile as tf

        def failing(_n):                                           # virt-viewer endet sofort mit Fehler
            err = tf.TemporaryFile()
            p = subprocess.Popen([sys.executable, "-c", "import sys; sys.stderr.write('Domain not found\\n'); sys.exit(1)"],
                                 stderr=err)
            p.wait(20)
            return p, err
        check_now = w.show_vm("DISPOSABLE-X-01", opener=failing)
        check_now()
        self.assertEqual(w.msg.get_text(), "VM window could not be opened (virt-viewer exit 1): Domain not found")
        w.destroy()

    def test_start_dialog_defaults_and_capacity(self):
        from evoxd.gui import StartDialog
        self.ev.start("TEMPLATE-MAIL", purpose="WEB", memory_mib=3072, vcpus=1)
        d = StartDialog(None, self.ev, "TEMPLATE-MAIL")
        self.assertEqual((d.memory_mib, d.vcpus, d.purpose_text), (3072, 1, "WEB"))
        self.assertTrue(d.ok_btn.get_sensitive())
        # 12 GiB verfügbar − 2 GiB Reserve − 0,25 GiB Overhead → max. 9,75 GiB (0.7.3: Raster 0,25; vorher 9,5)
        d.ram.set_value(20)
        self.assertEqual(d.ram.get_value(), 9.75)
        self.assertTrue(d.ok_btn.get_sensitive())
        self.assertTrue(d.cap_lbl.get_text().startswith("OK"))
        self.assertIn(f"available {g(12288)}, reserve {g(2048)}, max. for VMs {g(10240)} · room for 1 VM(s) of {capacity.fmt_dec(9.75, 2)} GB",   # 0.7.3
                      d.host_lbl.get_text())
        d.ram.set_value(2.5)
        self.assertIn(f"room for 3 VM(s) of {capacity.fmt_dec(2.5)} GB", d.host_lbl.get_text())
        # Dezimalzeichen im Text = Dezimalzeichen der RAM-Eingabe (GTK, Systemsprache)
        self.assertIn(d.ram.get_text()[1], d.host_lbl.get_text())
        self.assertEqual(d.ram.get_text(), capacity.fmt_dec(2.5, 2))     # 0.7.3: zwei Nachkommastellen (Raster 0,25)
        self.assertIn(f"Max. CPUs: {min(16, self.ev.host_cpus())}", d.host_lbl.get_text())
        d.cpus.set_value(999)
        self.assertEqual(d.vcpus, min(16, self.ev.host_cpus()))
        self.mem = {"MemTotal": 16 * 2**20, "MemAvailable": 2 * 2**20}   # Speicher knapp geworden
        d.update()
        self.assertFalse(d.ok_btn.get_sensitive())
        self.assertIn("start not possible", d.cap_lbl.get_text())
        self.mem = {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20}
        d.ram.set_value(2)
        d.purpose.get_child().set_text("E-MAIL")
        self.assertFalse(d.ok_btn.get_sensitive())
        d.destroy()

    def test_start_dialog_low_memory(self):
        from evoxd.gui import StartDialog
        self.mem = {"MemTotal": 16 * 2**20, "MemAvailable": 2 * 2**20}
        d = StartDialog(None, self.ev, "TEMPLATE-MAIL")
        self.assertEqual(d.memory_mib, 1024)                       # Untergrenze
        self.assertFalse(d.ok_btn.get_sensitive())
        d.destroy()

    def _candidates_setup(self):
        self.hv.add_foreign("TEMPLATE-RUN", state="running", disk="/var/lib/libvirt/images/run.qcow2")
        self.hv.add_foreign("TEMPLATE-MAIL-BACKUP", disk="/var/lib/libvirt/images/b.qcow2")
        self.hv.add_foreign("TEMPLATE-LOOSE", disk="/home/x/nopool.qcow2")
        self.hv.add_foreign("VAULT-WORK")
        self.hv.add_foreign("OTHER-VM")

    def test_import_dialog_lists_only_templates(self):
        from evoxd.gui import ImportDialog, confirm_import_text, theme_colors
        self._candidates_setup()
        d = ImportDialog(None, self.ev)
        rows = {r[0]: (r[1], r[3], r[4]) for r in d.store}
        self.assertEqual(sorted(rows), ["TEMPLATE-LOOSE", "TEMPLATE-MAIL", "TEMPLATE-MAIL-BACKUP", "TEMPLATE-RUN"])
        self.assertEqual(rows["TEMPLATE-RUN"], ("running", "running – shut it down first", False))
        self.assertFalse(rows["TEMPLATE-LOOSE"][2])
        self.assertEqual(rows["TEMPLATE-MAIL"], ("shutoff", "ready", True))
        sel = d.view.get_selection()
        self.assertIsNone(d.selected())                          # nichts vorausgewählt
        self.assertFalse(d.ok_btn.get_sensitive())
        self.assertEqual(d.get_focus(), d.get_widget_for_response(Gtk.ResponseType.CANCEL))
        names = [r[0] for r in d.store]
        self.assertEqual(d.store[names.index("TEMPLATE-MAIL-BACKUP")][5], theme_colors(d)["bad"])   # rot
        self.assertIsNone(d.store[names.index("TEMPLATE-MAIL")][5])
        sel.select_path(names.index("TEMPLATE-RUN"))           # ausgegraut: nicht wählbar
        self.assertIsNone(d.selected())
        self.assertFalse(d.ok_btn.get_sensitive())
        sel.select_path(names.index("TEMPLATE-MAIL-BACKUP"))
        self.assertEqual(d.selected()["name"], "TEMPLATE-MAIL-BACKUP")
        self.assertTrue(d.ok_btn.get_sensitive())
        t = confirm_import_text(d.selected())
        self.assertIn(f"Disk: {g(10240)} (used {g(6144)})", t)
        self.assertIn("-BACKUP", t)
        self.assertNotIn("-BACKUP", confirm_import_text(d.candidates["TEMPLATE-MAIL"]))
        d.destroy()

    def test_import_dialog_space_line(self):
        from evoxd import lifecycle, texts as T
        from evoxd.gui import ImportDialog, theme_colors
        self._candidates_setup()
        d = ImportDialog(None, self.ev)
        names = [r[0] for r in d.store]
        sel = d.view.get_selection()
        one = lifecycle.space_needed(10 * 2**30, 6 * 2**30)
        self.assertEqual(d.space.get_text(), "")                                   # ohne Auswahl keine Zeile
        # ausreichend: gleiche Zeile wie Make template, Knopf aktiv
        sel.select_path(names.index("TEMPLATE-MAIL"))
        self.assertEqual(d.space.get_text(), f"Needed: {g(one // 2**20)}, free: {g(100 * 1024)} "
                                             f"(after reserve: {g(90 * 1024)})")
        self.assertEqual(d.space_msg.get_text(), "")
        self.assertTrue(d.ok_btn.get_sensitive())
        # Mehrfachauswahl: Summe (die Liste wählt heute eine Zeile; chosen() liefert beliebig viele)
        c = d.candidates
        d.chosen = lambda: [c["TEMPLATE-MAIL"], c["TEMPLATE-MAIL-BACKUP"]]
        d.update()
        self.assertIn(f"Needed: {g(2 * one // 2**20)},", d.space.get_text())
        self.assertTrue(d.ok_btn.get_sensitive())
        # knapp: Knopf inaktiv, Grund in Gefahrfarbe
        self.hv.free = 11 * 2**30
        d.chosen = lambda: [c["TEMPLATE-MAIL"]]
        d.update()
        self.assertFalse(d.ok_btn.get_sensitive())
        self.assertIn("Not enough space in /srv/evoxd/templates", d.space_msg.get_text())
        self.assertTrue(d.space_msg.get_use_markup())
        # Größe unbekannt: Hinweis, Import nicht blockiert
        unknown = dict(c["TEMPLATE-MAIL"], name="TEMPLATE-X", size=None, alloc=None)
        d.chosen = lambda: [unknown]
        d.update()
        self.assertTrue(d.ok_btn.get_sensitive())
        self.assertEqual(d.space_msg.get_text(), T.IMP_SPACE_UNKNOWN.format(names="TEMPLATE-X"))
        d.destroy()

    def test_import_in_real_thread_with_progress(self):
        from evoxd.gui import MainWindow
        w = MainWindow(self.ev)
        from evoxd.gui import fmt_datetime
        created = fmt_datetime(self.reg.bases()[0].created)
        self.assertEqual([list(r)[:8] for r in w.tpl_store],
                         [["TEMPLATE-MAIL", "1", created, "bios", g(6144), f"{capacity.fmt_dec(0)} days", "0", "ok"]])
        calls = []
        orig = self.ev.import_template

        def spy(name, progress=None):                  # dieselbe Funktion wie `evoxd template-import`
            calls.append(threading.get_ident())
            return orig(name, progress=progress)
        self.ev.import_template = spy
        self.hv.clone_delay = 0.6                      # Kopie dauert
        t = w.import_template("TEMPLATE-MAIL")
        seen = set()
        end = time.monotonic() + 20
        while w.busy and time.monotonic() < end:
            Gtk.main_iteration_do(False)
            if w.progress.get_visible():
                seen.add(w.progress.get_text().split(" (")[0].split(" …")[0])
            time.sleep(0.01)
        t.join(20)
        self._wait(w)
        self.assertNotEqual(calls, [])
        self.assertNotEqual(calls[0], threading.get_ident())
        self.assertIn("Copying the disk of TEMPLATE-MAIL", seen)
        self.assertFalse(w.progress.get_visible())
        self.assertTrue(w.msg.get_text().startswith("TEMPLATE-MAIL version 2 imported ("), w.msg.get_text())
        self.assertEqual([r[1] for r in w.tpl_store], ["2", "1"])     # neueste zuoberst
        self.assertEqual(w.active_template(), "TEMPLATE-MAIL")
        self.assertTrue(w.import_btn.get_sensitive())
        w.destroy()

    def test_import_error_and_combo_updates_without_restart(self):
        from evoxd.gui import MainWindow
        self._candidates_setup()
        w = MainWindow(self.ev)
        w.import_template("TEMPLATE-RUN").join(20)
        self._wait(w)
        self.assertEqual(w.msg.get_text(), "Error: 'TEMPLATE-RUN' must be shut off.")
        self.assertFalse(w.progress.get_visible())
        w.import_template("TEMPLATE-MAIL-BACKUP").join(20)
        self._wait(w)
        self.assertEqual([r[0] for r in w.base_combo.get_model()], ["TEMPLATE-MAIL", "TEMPLATE-MAIL-BACKUP"])
        self.assertEqual(w.active_template(), "TEMPLATE-MAIL-BACKUP")
        w.destroy()

    def test_verify_button(self):
        from evoxd.gui import MainWindow
        w = MainWindow(self.ev)
        w.tpl_view.get_selection().unselect_all()        # 0.6.20: Vorauswahl abwählen, um "keine Markierung" zu prüfen
        w.on_verify(None)
        self.assertEqual(w.msg.get_text(), "Select a template in the list first.")
        w.tpl_view.get_selection().select_path(0)
        w.on_verify(None).join(20)
        self._wait(w)
        self.assertEqual(w.msg.get_text(), "TEMPLATE-MAIL v1: template copy unchanged (SHA-256 matches).")
        self.hv.vol_sha256 = lambda _n: "0" * 64        # Kopie verändert
        w.on_verify(None).join(20)
        self._wait(w)
        self.assertTrue(w.msg.get_text().startswith("WARNING: TEMPLATE-MAIL v1: checksum does NOT match"))
        self.assertIn(w.colors["bad"], w.msg.get_label())           # rote Warnung
        self.assertEqual(w.tpl_store[0][7], "DAMAGED")
        self.assertEqual(w.tpl_store[0][9], w.colors["bad"])
        w.destroy()

    # ---- echte Arbeits-Threads (Fehler auf dem Host: sqlite3.ProgrammingError in Thread-1)
    def _wait(self, w, timeout=20):
        end = time.monotonic() + timeout
        while (w.busy or w._tick_running) and time.monotonic() < end:
            Gtk.main_iteration_do(False)
            time.sleep(0.01)
        while GLib.MainContext.default().pending():   # restliche idle_add-Aufrufe
            Gtk.main_iteration_do(False)
        self.assertFalse(w.busy or w._tick_running, "Arbeits-Thread nicht fertig")

    def test_background_actions_in_real_threads(self):
        from evoxd.gui import APP_TITLE, MainWindow
        w = MainWindow(self.ev)
        self.assertEqual(w.get_title(), "EVOX KVM DISPOSABLE")
        self.assertEqual(APP_TITLE, w.get_title())
        main_id = threading.get_ident()
        seen = []

        def start():
            seen.append(threading.get_ident())
            return self.ev.start("TEMPLATE-MAIL", purpose="WEB", want_net=False)
        w._run(start, lambda r: w.show(f"{r.name} started")).join(20)
        self._wait(w)
        self.assertNotEqual(seen[0], main_id)
        self.assertEqual(w.msg.get_text(), "DISPOSABLE-WEB-01 started")
        self.assertEqual(w.store[0][0], "DISPOSABLE-WEB-01")

        w._tick()                                      # Reconcile im Thread (Host-Fehler)
        self._wait(w)
        self.assertNotIn("Error", w.msg.get_text())

        w._run(lambda: self.ev.stop("DISPOSABLE-WEB-01"), lambda _r: w.show("erased")).join(20)
        self._wait(w)
        self.assertEqual(w.msg.get_text(), "erased")
        self.assertEqual(len(w.store), 0)
        self.assertTrue(w.start_btn.get_sensitive())
        w.destroy()

    def test_thread_error_shown_in_status_line(self):
        from evoxd.gui import MainWindow
        w = MainWindow(self.ev)

        def boom():
            raise ValueError("unexpected")
        w._run(boom).join(20)
        self._wait(w)
        self.assertEqual(w.msg.get_text(), "Error: ValueError: unexpected")
        self.assertTrue(w.start_btn.get_sensitive())   # nicht dauerhaft gesperrt
        self.assertFalse(w.stop_btn.get_sensitive())   # ohne Auswahl bleibt Stop gesperrt
        w.destroy()


    # ---- 0.4.0: Entfernen, Prüfung nach dem Beenden, -BACKUP rot, Fenstergröße
    def _rows(self, w):
        return [(r[0], r[1]) for r in w.tpl_store]

    def _select(self, w, name, version):
        for i, r in enumerate(w.tpl_store):
            if (r[0], r[1]) == (name, str(version)):
                w.tpl_view.get_selection().select_path(i)
                return
        self.fail(f"{name} v{version} not in list")

    def _select_many(self, w, items):
        sel = w.tpl_view.get_selection()
        sel.unselect_all()
        for i, r in enumerate(w.tpl_store):
            if (r[0], int(r[1])) in items:
                sel.select_path(i)

    def test_remove_dialog(self):
        from evoxd.gui import NAME_COLOR, MainWindow, RemoveDialog
        self.ev.import_template("TEMPLATE-MAIL")
        self.ev.import_template("TEMPLATE-MAIL")
        w = MainWindow(self.ev)
        self.assertEqual(w.tpl_view.get_selection().get_mode(), Gtk.SelectionMode.MULTIPLE)
        w.tpl_view.get_selection().unselect_all()        # 0.6.20: Vorauswahl abwählen
        w.on_remove(None)
        self.assertEqual(w.msg.get_text(), "Select a template in the list first.")
        self._select_many(w, {("TEMPLATE-MAIL", 1)})
        d = RemoveDialog(w, w.selected_bases())
        self.assertIn(f'foreground="{NAME_COLOR}"', d.text.get_label())
        self.assertIn("<b>TEMPLATE-MAIL</b>", d.text.get_label())
        self.assertIn("v1 (" + g(6144) + ")", d.text.get_text())
        self.assertFalse(hasattr(d, "older"))
        d.destroy()
        self._select_many(w, {("TEMPLATE-MAIL", 1), ("TEMPLATE-MAIL", 2)})
        rows = w.selected_bases()
        self.assertEqual(len(rows), 2)
        self.assertIsNone(w.selected_base())                       # Prüfen/Start brauchen genau eine
        d = RemoveDialog(w, rows)
        self.assertEqual(d.text.get_label().count(NAME_COLOR), 2)
        self.assertIn("v1", d.text.get_text())
        self.assertIn("v2", d.text.get_text())
        self.assertIn("Total: " + g(12288), d.text.get_text())
        d.destroy()
        w.destroy()

    def test_remove_in_real_thread(self):
        from evoxd.gui import MainWindow
        for _ in range(3):
            self.ev.import_template("TEMPLATE-MAIL")
        w = MainWindow(self.ev)
        calls = []
        orig = self.ev.remove_template

        def spy(*a, **k):                              # dieselbe Funktion wie `evoxd template-remove`
            calls.append(threading.get_ident())
            return orig(*a, **k)
        self.ev.remove_template = spy
        w.remove_templates([("TEMPLATE-MAIL", 2)]).join(20)
        self._wait(w)
        self.assertNotEqual(calls[0], threading.get_ident())
        self.assertEqual(w.msg.get_text(), "Removed: TEMPLATE-MAIL v2.")
        self.assertEqual(self._rows(w), [("TEMPLATE-MAIL", "4"), ("TEMPLATE-MAIL", "3"), ("TEMPLATE-MAIL", "1")])
        r = self.ev.start("TEMPLATE-MAIL")                          # v4 in Benutzung
        calls.clear()
        w.remove_templates([("TEMPLATE-MAIL", 1), ("TEMPLATE-MAIL", 4), ("TEMPLATE-MAIL", 3)]).join(20)
        self._wait(w)
        self.assertEqual(len(calls), 3)                             # je Kopie ein Aufruf, im Thread
        self.assertNotIn(threading.get_ident(), calls)
        text = w.msg.get_text()
        self.assertIn("Removed: TEMPLATE-MAIL v1, TEMPLATE-MAIL v3.", text)
        self.assertIn(f"Not removed: TEMPLATE-MAIL v4: TEMPLATE-MAIL v4 is in use by {r.name}", text)
        self.assertIn(w.colors["bad"], w.msg.get_label())
        self.assertEqual(self._rows(w), [("TEMPLATE-MAIL", "4")])
        self.assertEqual(w.active_template(), "TEMPLATE-MAIL")
        self.assertTrue(w.remove_btn.get_sensitive())
        w.destroy()

    def _wait_verify(self, w, timeout=20):
        end = time.monotonic() + timeout
        while (w._verifying or GLib.MainContext.default().pending()) and time.monotonic() < end:
            Gtk.main_iteration_do(False)
            time.sleep(0.01)
        self.assertEqual(w._verifying, set(), "Hintergrundprüfung nicht fertig")

    def test_verify_after_shutdown_in_real_threads(self):
        import json
        from evoxd.gui import MainWindow
        w = MainWindow(self.ev)
        self.assertFalse(w.verify_chk.get_active())                 # Standard aus
        r = self.ev.start("TEMPLATE-MAIL")
        w._run(lambda: self.ev.stop(r.name)).join(20)
        self._wait(w)
        self._wait_verify(w)
        self.assertNotIn("Verifying", w.msg.get_text())             # aus → keine Prüfung

        w.verify_chk.set_active(True)
        self.assertEqual(json.loads(self.ev.s.config_file.read_text()), {"verify_after_shutdown": True})
        threads = []
        orig_sha = self.hv.vol_sha256

        def slow_sha(n):                                            # Prüfung dauert, GUI bleibt bedienbar
            threads.append(threading.get_ident())
            time.sleep(0.5)
            return orig_sha(n)
        self.hv.vol_sha256 = slow_sha
        r = self.ev.start("TEMPLATE-MAIL")
        w._run(lambda: self.ev.stop(r.name)).join(20)
        self._wait(w)
        self.assertTrue(w._verifying)
        self.assertFalse(w.busy)
        self.assertTrue(w.start_btn.get_sensitive())
        self.assertTrue(w.msg.get_text().startswith("Verifying TEMPLATE-MAIL v1 in the background"))
        self._wait_verify(w)
        self.assertNotEqual(threads[0], threading.get_ident())
        self.assertEqual(w.msg.get_text(), "TEMPLATE-MAIL v1: template copy unchanged (SHA-256 matches).")

        self.hv.vol_sha256 = lambda _n: "0" * 64                   # Kopie verändert
        r = self.ev.start("TEMPLATE-MAIL")
        del self.hv.domains[r.name]                                 # Gast schaltet sich selbst aus
        w._tick()                                                   # Reconcile vernichtet → Prüfung
        self._wait(w)
        self._wait_verify(w)
        self.assertIn("checksum does NOT match", w.msg.get_text())
        self.assertIn(w.colors["bad"], w.msg.get_label())
        self.assertEqual(w.tpl_store[0][7], "DAMAGED")
        w._run(lambda: self.ev.start("TEMPLATE-MAIL")).join(20)
        self._wait(w)
        self.assertIn("DAMAGED", w.msg.get_text())                  # neue Starts verweigert
        self.assertEqual(Settings.load(self.ev.s.config_file).verify_after_shutdown, True)
        w.destroy()

    def test_backup_red_and_window_size(self):
        from evoxd.gui import MainWindow
        self.hv.add_foreign("TEMPLATE-MAIL-BACKUP", disk="/var/lib/libvirt/images/b.qcow2")
        self.ev.import_template("TEMPLATE-MAIL-BACKUP")
        w = MainWindow(self.ev)
        colors = {r[0]: r[1] for r in w.base_store}
        self.assertEqual(colors, {"TEMPLATE-MAIL": None, "TEMPLATE-MAIL-BACKUP": w.colors["bad"]})
        self.assertEqual({r[0]: r[9] for r in w.tpl_store},
                         {"TEMPLATE-MAIL": None, "TEMPLATE-MAIL-BACKUP": w.colors["bad"]})
        self.assertEqual(w.get_default_size(), (1100, 820))
        w.save_geometry()
        self.ev.s.save_gui_state(1100, 800, False)
        w.destroy()
        w = MainWindow(self.ev)
        self.assertEqual(w.get_default_size(), (1100, 800))
        w.destroy()

    # ---- 0.5.0 (A1): Reiter, Erklärsätze, Tagline, Detailleiste, zwei Start-Knöpfe, Created
    def test_tabs_tagline_and_empty_texts(self):
        from evoxd import texts as T
        from evoxd.gui import MIN_SIZE, MainWindow
        self.ev.remove_template("TEMPLATE-MAIL", version=1)        # keine Templates, keine VMs
        w = MainWindow(self.ev)
        nb = w.tabs
        self.assertEqual([nb.buttons[k].get_label() for k in nb.keys],
                         ["1. VAULT", "2. TEMPLATE", "3. DISPOSABLE"])
        self.assertEqual(nb.get_current_page(), 2)                  # Start im Reiter DISPOSABLE (Reihenfolge 1 → 3)
        self.assertEqual(w.vm_stack.get_visible_child_name(), "empty")
        self.assertEqual(w.vm_stack.empty_label.get_text(),
                         "No disposable VMs running. Pick a template and click Start.")
        self.assertEqual(w.tpl_stack.get_visible_child_name(), "empty")
        self.assertIn("use Make template in the VAULT tab, or Import template", w.tpl_stack.empty_label.get_text())
        self.assertEqual(w.vault_stack.get_visible_child_name(), "empty")
        self.assertTrue(w.vaults_lbl.get_text().startswith("No VAULT-* VMs found."))
        self.assertEqual(w.tagline.get_text(),
                         "Secure. Disposable. Isolated. Encrypted. Network-locked. Erased on exit.")
        self.assertTrue(w.tagline.get_line_wrap())
        self.assertTrue(w.tagline.get_style_context().has_class("evox-tagline"))
        self.assertEqual(w.subline.get_text(), T.SUBLINE)
        self.assertEqual(tuple(w.get_size_request()), MIN_SIZE)
        # bestehende Funktionen im passenden Reiter
        disp, tpl = nb.get_nth_page(2), nb.get_nth_page(1)
        for b in (w.start_btn, w.start_offline_btn, w.console_btn, w.stop_btn, w.base_combo, w.view, w.details):
            self.assertTrue(b.is_ancestor(disp))
        for b in (w.import_btn, w.verify_btn, w.remove_btn, w.verify_chk, w.tpl_view):
            self.assertTrue(b.is_ancestor(tpl))
        self.assertFalse(hasattr(w, "no_net"))                      # Haken entfällt
        self.ev.import_template("TEMPLATE-MAIL")
        w.refresh()
        self.assertEqual(w.tpl_stack.get_visible_child_name(), "list")
        w.destroy()

    def test_colors_tabs_centering_0_5_3(self):
        import evoxd.gui as G
        from evoxd import texts as T
        w = G.MainWindow(self.ev)
        # Reiter: eigene Knöpfe mit den Farbklassen der HOW-TO-Knöpfe; aktiv = :checked (Unterstreichung per CSS)
        nb = w.tabs
        for i, key in enumerate(("vault", "template", "disposable")):
            nb.set_current_page(i)
            self.assertTrue(nb.buttons[key].get_active())
            self.assertEqual(sum(nb.buttons[k].get_active() for k in nb.keys), 1)
            self.assertTrue(nb.buttons[key].get_style_context().has_class(G.TAB_CLASSES[key]))
            self.assertIn(f".evox-tabbtn-{key}:checked {{ border-bottom: 5px solid", G.CSS)
        self.assertEqual((G.TAB_COLORS["template"], G.TAB_COLORS["vault"]), ("#00F0FF", "#D4AF37"))
        self.assertEqual(T.TPL_COLUMNS[0], "TEMPLATE")
        self.assertEqual(w.tpl_view.get_column(0).get_title(), "TEMPLATE")
        # Titel/Tagline: zentriert, feste Titelfarbe mit Glüheffekt
        for lbl in (w.title, w.tagline, w.subline):
            self.assertEqual(lbl.get_xalign(), 0.5)
            self.assertEqual(lbl.get_justify(), Gtk.Justification.CENTER)
        self.assertIn("color: #8c00ff; text-shadow: 0 0 8px #8c00ff;", G.CSS)
        self.assertIn(".evox-tagline { font-size: 15pt; font-weight: bold; color: #00A8B5; }", G.CSS)
        # Startdialog: Knopffarbe folgt dem Modus, Cancel gedämpft rot
        for offline, cls in ((False, "evox-start-disposable"), (True, "evox-start-offline")):
            d = G.StartDialog(w, self.ev, "TEMPLATE-MAIL", offline=offline)
            self.assertTrue(d.ok_btn.get_style_context().has_class(cls))
            self.assertTrue(d.cancel_btn.get_style_context().has_class("evox-cancel"))
            d.destroy()
        self.assertIn("evox-start-internet {{".replace("{{", "{") + " background-image: none; background-color: #1FA855",
                      G.CSS)
        self.assertIn("background-color: #8B2A2A", G.CSS)
        self.assertIn("background-color: #d41f1f", G.CSS)
        self.assertNotEqual(G.CANCEL_COLOR, G.DANGER_COLOR)
        self.assertTrue(w.stop_btn.get_style_context().has_class("evox-danger"))
        # Sperranzeige: eigener Punkt mit Schloss + Text, nicht Teil der Modusfarben
        self.assertTrue(T.LOCK_OK.startswith("🔒") and "Network lock: active" in T.LOCK_OK)
        self.assertNotEqual(w.status.get_parent(), w.start_btn.get_parent())
        w.destroy()

    def test_button_colors_062(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        cls = lambda b, c: b.get_style_context().has_class(c)
        self.assertTrue(cls(w.import_btn, "evox-import-btn"))
        self.assertFalse(cls(w.verify_btn, "evox-import-btn"))
        self.assertFalse(cls(w.remove_btn, "evox-import-btn"))
        self.assertTrue(cls(w.start_btn, "evox-start-disposable"))
        self.assertTrue(cls(w.start_offline_btn, "evox-offline"))
        self.assertFalse(cls(w.start_offline_btn, "evox-start-disposable"))
        self.assertTrue(cls(w.stop_btn, "evox-danger"))
        self.assertTrue(cls(w.virt_manager_btn, "evox-vault-btn"))
        css = " ".join(G.CSS.split())
        self.assertIn(".evox-import-btn { background-image: none; background-color: #00F0FF; color: #001a1c; border: 2px solid #c8fcff; }", css)
        self.assertIn(".evox-start-disposable { background-image: none; background-color: #39D353; color: #04210c; border: 2px solid #c9f7d3; }", css)
        self.assertEqual((G.TAB_TEMPLATE_COLOR, G.TAB_DISPOSABLE_COLOR), ("#00F0FF", "#39D353"))
        self.assertIn("evox-start-offline { background-image: none; background-color: #0060b3", css)
        # Dialogknöpfe unverändert
        for internet, cn in ((False, "evox-start-disposable"), (True, "evox-start-offline")):
            d = G.StartDialog(w, self.ev, "TEMPLATE-MAIL", offline=internet)
            self.assertTrue(cls(d.ok_btn, cn))
            self.assertTrue(cls(d.cancel_btn, "evox-cancel"))
            self.assertFalse(cls(d.ok_btn, "evox-start-internet"))           # 0.7.5: Modus-Grün nicht mehr am Start-Knopf
            d.destroy()
        w.destroy()

    def test_mode_buttons_open_dialog_in_mode(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        self.assertEqual(w.start_btn.title_lbl.get_text(), "Start Disposable VM: INTERNET")
        self.assertEqual(w.start_btn.sub_lbl.get_text(), "Internet only. Host, home network and other VMs blocked.")
        self.assertEqual(w.start_offline_btn.title_lbl.get_text(), "Start Disposable VM: OFFLINE")
        self.assertEqual(w.start_offline_btn.sub_lbl.get_text(), "No connection at all. For untrusted files.")
        self.assertTrue(w.start_offline_btn.get_style_context().has_class("evox-offline"))
        self.assertTrue(w.start_btn.get_style_context().has_class("evox-start-disposable"))
        self.assertFalse(w.start_btn.get_style_context().has_class("suggested-action"))
        self.assertIn("background-color: #0060b3", G.CSS)
        self.assertIn("border: 2px solid #cfe6ff", G.CSS)
        self.assertIn(".evox-bar-offline { background-color: #0060b3; }", G.CSS)    # feste Modusfarbe
        self.assertIn(".evox-bar-internet { background-color: #1FA855; }", G.CSS)   # Grün
        self.assertNotIn("FFB000", G.CSS.upper())
        self.assertEqual(w.start_btn.get_parent(), w.start_offline_btn.get_parent())   # übereinander in einer Box
        self.assertEqual(w.start_btn.get_parent().get_orientation(), Gtk.Orientation.VERTICAL)
        d = G.StartDialog(w, self.ev, "TEMPLATE-MAIL")
        self.assertEqual(d.mode_lbl.get_text(), "INTERNET MODE")
        self.assertEqual(d.mode_icon.get_text(), "🔒〰")
        self.assertTrue(d.mode_bar.get_style_context().has_class("evox-bar-internet"))
        self.assertIs(d.get_content_area().get_children()[0], d.mode_bar)   # ganz oben
        self.assertEqual(d.mode_expl.get_text(),
                         "Internet works. Your computer, your home network and other VMs are blocked.")
        self.assertFalse(d.mode_bar.get_style_context().has_class("evox-bar-offline"))
        d.destroy()
        d = G.StartDialog(w, self.ev, "TEMPLATE-MAIL", offline=True)
        self.assertEqual(d.mode_lbl.get_text(), "OFFLINE MODE")
        self.assertEqual(d.mode_icon.get_text(), "🚫🌐")
        self.assertEqual(d.mode_expl.get_text(), "Fully offline. Use this to open untrusted files.")
        self.assertTrue(d.mode_bar.get_style_context().has_class("evox-bar-offline"))
        d.destroy()
        # Knopf → Modus: Dialog-Antwort OK simulieren, Start im echten Arbeits-Thread
        seen, opened = [], []

        class OkDialog(G.StartDialog):
            def run(self):
                seen.append(self.offline)
                return Gtk.ResponseType.OK

        def no_viewer(name):
            opened.append(name)
            raise RuntimeError("no viewer in test")
        orig_dlg, orig_open = G.StartDialog, G.open_console
        G.StartDialog = OkDialog
        G.open_console = no_viewer                     # Attrappe: kein echtes virt-viewer
        try:
            self.ev.net_check = lambda: (True, "")
            w.start_btn.clicked()
            self._wait(w)
            w.start_offline_btn.clicked()
            self._wait(w)
        finally:
            G.StartDialog, G.open_console = orig_dlg, orig_open
        self.assertEqual(opened, ["DISPOSABLE-EMAIL-01", "DISPOSABLE-EMAIL-02"])
        self.assertEqual(seen, [False, True])
        nets = {r[0]: r[2] for r in w.store}                      # 0.7.1: Spalte Modus
        self.assertEqual(sorted(nets.values()), ["INTERNET", "OFFLINE"])
        self.assertEqual({t["name"]: t["net"] for t in self.ev.list_temps()},
                         {n: ("none" if v == "OFFLINE" else "net") for n, v in nets.items()})
        w.destroy()

    def test_start_offline_in_real_thread_and_details(self):
        from evoxd.gui import MainWindow
        w = MainWindow(self.ev)
        self.assertIsNone(w.monitor)                                 # 0.7.4: Monitorfenster nie automatisch
        self.assertEqual(w.short_lbl.get_text(), T.SHORT_NONE)       # ohne Auswahl Hinweis statt Werte
        calls, opened = [], []
        orig = self.ev.start

        def spy(*a, **k):                              # dieselbe Funktion wie `evoxd start --no-net`
            calls.append((threading.get_ident(), k["want_net"]))
            return orig(*a, **k)
        self.ev.start = spy

        def opener(name):
            opened.append(name)
            raise RuntimeError("no viewer in test")
        self.ev.net_check = lambda: (True, "")
        w.start_vm("TEMPLATE-MAIL", "EMAIL", 2048, 2, True, opener=opener).join(20)
        self._wait(w)
        self.assertNotEqual(calls[0][0], threading.get_ident())
        self.assertFalse(calls[0][1])                                # Offline → want_net=False
        self.assertEqual(opened, ["DISPOSABLE-EMAIL-01"])
        self.assertEqual(w.vm_stack.get_visible_child_name(), "list")
        self.assertEqual(w.store[0][2], "OFFLINE")
        w.view.get_selection().select_path(0)
        self.assertIn("RAM", w.short_lbl.get_text())                 # 0.7.4: Kurzzeile statt Detailbereich
        self.assertIsNone(w.monitor)                                 # Monitor nur auf Knopfdruck
        w.details_btn.clicked()
        mon = w.monitor
        vals = [v.get_text() for v in mon.net_vals]                 # 0.7.1: Block c) Netz/Overlay
        self.assertEqual(vals[3:6], ["TEMPLATE-MAIL v1", "OFFLINE", "– offline (no network)"])
        self.assertIn(self.reg.temp("DISPOSABLE-EMAIL-01").overlay_name, mon.net_vals[1].get_tooltip_text())
        self.assertEqual(vals[6], "EMAIL: 1× started")               # Zweck-Statistik: Start gezählt
        w.refresh()                                                  # Auswahl und Monitor bleiben
        self.assertIs(w.monitor, mon)
        w.details_btn.clicked()
        self.assertIsNone(w.monitor)
        w.destroy()

    def test_stop_and_erase_needs_selection_and_confirmation(self):
        from unittest import mock
        from evoxd.gui import MainWindow
        w = MainWindow(self.ev)
        self.assertEqual(w.stop_btn.get_label(), "Stop and erase VM")
        self.assertFalse(w.stop_btn.get_sensitive())                 # keine Auswahl → gesperrt, mit Grund
        self.assertEqual(w.stop_btn.get_tooltip_text(), "Select a disposable VM in the list first.")
        r1 = self.ev.start("TEMPLATE-MAIL", purpose="A")
        r2 = self.ev.start("TEMPLATE-MAIL", purpose="B")
        w.refresh()
        w.view.get_selection().select_path(0)
        self.assertTrue(w.stop_btn.get_sensitive())
        sel = w.selected()
        texts = {}

        def run_cancel(dlg):
            texts["markup"] = dlg.get_message_area().get_children()[0].get_label()
            texts["buttons"] = sorted(b.get_label() for b in dlg.get_action_area().get_children())
            texts["classes"] = {b.get_label(): [c for c in ("evox-cancel", "evox-danger")
                                                if b.get_style_context().has_class(c)]
                                for b in dlg.get_action_area().get_children()}
            return Gtk.ResponseType.CANCEL
        with mock.patch.object(Gtk.MessageDialog, "run", run_cancel):
            w.on_stop(None)
        self.assertEqual(texts["markup"], f"This ends <b>{sel}</b> immediately and erases all its data.")
        self.assertEqual(texts["buttons"], ["Cancel", "Stop and erase"])
        self.assertEqual(texts["classes"], {"Cancel": ["evox-cancel"], "Stop and erase": ["evox-danger"]})
        self.assertEqual(len(self.ev.list_temps()), 2)               # Abbrechen löscht nichts
        with mock.patch.object(Gtk.MessageDialog, "run", lambda dlg: Gtk.ResponseType.OK):
            w.on_stop(None)
        self._wait(w)
        self.assertEqual([t["name"] for t in self.ev.list_temps()], [n for n in (r1.name, r2.name) if n != sel])
        self.assertEqual(w.msg.get_text(), f"{sel} stopped and erased.")   # nur die markierte VM
        w.destroy()

    def test_created_column_newest_first(self):
        from evoxd.gui import MainWindow, fmt_datetime
        self.ev.import_template("TEMPLATE-MAIL")
        self.hv.add_foreign("TEMPLATE-WEB")
        self.ev.import_template("TEMPLATE-WEB")
        w = MainWindow(self.ev)
        created = {(b.name, str(b.version)): fmt_datetime(b.created) for b in self.reg.bases()}
        rows = [(r[0], r[1], r[2]) for r in w.tpl_store]
        self.assertEqual([(n, v) for n, v, _ in rows],
                         [("TEMPLATE-WEB", "1"), ("TEMPLATE-MAIL", "2"), ("TEMPLATE-MAIL", "1")])
        self.assertEqual([c for _, _, c in rows], [created[(n, v)] for n, v, _ in rows])
        self.assertRegex(rows[0][2], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
        self.assertEqual(w.tpl_view.get_column(2).get_title(), "Created")
        w.destroy()

    # ---- A2: Reiter VAULT und Make template
    def _vaults(self):
        self.hv.add_vault("VAULT-MAIL")
        self.hv.add_vault("VAULT-RUN", state="running")
        self.hv.add_vault("VAULT-SAVED")
        self.hv.vault_states["VAULT-SAVED"] = "saved"
        self.hv.add_vault("VAULT-PAUSE")
        self.hv.vault_states["VAULT-PAUSE"] = "paused"

    def _select_vault(self, w, name):
        sel = w.vault_view.get_selection()
        for i, r in enumerate(w.vault_store):
            if r[0] == name:
                sel.select_path(i)

    def test_vault_tab_list_hint_and_buttons(self):
        from evoxd import texts as T
        from evoxd.gui import TAB_VAULT_COLOR, CSS, MainWindow
        self._vaults()
        w = MainWindow(self.ev)
        vault = w.tabs.get_nth_page(0)
        for b in (w.vault_hint, w.vault_view, w.make_btn, w.virt_manager_btn):
            self.assertTrue(b.is_ancestor(vault))
        self.assertTrue(w.vault_hint.get_text().startswith("EVOX only reads and copies VAULT VMs. It never starts"))
        self.assertIn(f".evox-vault-hint {{ color: {TAB_VAULT_COLOR};", CSS)
        self.assertEqual(TAB_VAULT_COLOR, "#D4AF37")                                 # Gold bleibt
        self.assertEqual([c.get_title() for c in w.vault_view.get_columns()], list(T.VAULT_COLUMNS))
        self.assertEqual([list(r)[:6] for r in w.vault_store][0],
                         ["VAULT-MAIL", "shut off", g(4096), "2", g(20480), "–"])
        self.assertEqual([r[1] for r in w.vault_store], ["shut off", "paused", "running", "saved"])
        self.assertEqual(w.vault_stack.get_visible_child_name(), "list")
        # Knopf: ohne Auswahl, laufend, pausiert, gespeichert → inaktiv mit Grund; ausgeschaltet → aktiv
        self.assertEqual(w.selected_vault()["name"], "VAULT-MAIL")                   # 0.6.12: Vorauswahl
        w.vault_view.get_selection().unselect_all()
        self.assertFalse(w.make_btn.get_sensitive())
        self.assertEqual(w.make_btn.get_tooltip_text(), "Select one shut-off VAULT VM first.")
        for name, word in (("VAULT-RUN", "running"), ("VAULT-PAUSE", "paused"), ("VAULT-SAVED", "saved")):
            self._select_vault(w, name)
            self.assertFalse(w.make_btn.get_sensitive(), name)
            self.assertIn(f"Make template not possible: {word} – shut it down first", w.make_btn.get_tooltip_text())
        self._select_vault(w, "VAULT-MAIL")
        self.assertTrue(w.make_btn.get_sensitive())
        self.assertEqual(w.vault_note.get_text(), "VAULT-MAIL is shut off – ready to make a template.")
        # Kein Start/Stop/Löschen für Vaults im Reiter
        labels = []

        def collect(wd):
            if isinstance(wd, Gtk.Button):
                labels.append(wd.get_label())
            if isinstance(wd, Gtk.Container):
                wd.foreach(collect)
        collect(vault)
        self.assertEqual(sorted(x for x in labels if x), ["Create new VAULT VM in virt-manager…", "Make template…", "✕"])   # ✕ = Hinweisbalken schließen
        # virt-manager: Attrappe statt echtem Programm (nospawn bleibt aktiv)
        opened = []
        w.on_virt_manager(None, opener=lambda: opened.append(1))
        self.assertEqual(opened, [1])
        self.assertIn("VAULT-<purpose>", w.hint_label.get_text())             # seit 0.6.11 als Balken, nicht Statuszeile
        self.assertTrue(w.hint_bar.get_visible())
        import evoxd.cli as C
        import shutil
        old = shutil.which
        shutil.which = lambda _n: None
        try:
            w.on_virt_manager(None)                                                     # echter Pfad: nicht installiert
        finally:
            shutil.which = old
        self.assertEqual(w.msg.get_text(), "Error: virt-manager is not installed.")
        self.assertTrue(callable(C.open_virt_manager))
        w.destroy()

    def test_vault_gold_button(self):
        from evoxd import texts as T
        from evoxd.gui import CSS, MainWindow, VAULT_GOLD, VAULT_GOLD_BORDER, VAULT_GOLD_TEXT
        w = MainWindow(self.ev)
        b = w.virt_manager_btn
        self.assertEqual(b.get_label(), "Create new VAULT VM in virt-manager…")
        self.assertEqual(b.get_tooltip_text(),
                         "Opens virt-manager so you can create a new VAULT VM. EVOX does not change libvirt.")
        self.assertTrue(T.DE_BTN_VIRT_MANAGER.startswith("Neue VAULT-VM") and "libvirt" in T.DE_BTN_VIRT_MANAGER_TIP)
        self.assertTrue(b.get_style_context().has_class("evox-vault-btn"))
        self.assertFalse(w.make_btn.get_style_context().has_class("evox-vault-btn"))
        self.assertEqual(VAULT_GOLD, "#D4AF37")
        self.assertIn(f"background-color: {VAULT_GOLD}; color: {VAULT_GOLD_TEXT}", CSS)
        self.assertIn(f"border: 2px solid {VAULT_GOLD_BORDER}", CSS)
        w.destroy()

    def test_make_template_dialog_name_space_confirmation(self):
        from evoxd.gui import MainWindow, MakeTemplateDialog
        self._vaults()
        w = MainWindow(self.ev)
        plan = self.ev.make_template_plan("VAULT-MAIL")
        d = MakeTemplateDialog(w, self.ev, plan)
        self.assertEqual(d.name_text, "TEMPLATE-MAIL-2")                                 # TEMPLATE-MAIL belegt
        self.assertIn("passwords and browser data", d.warn.get_text())
        self.assertFalse(d.ok_btn.get_sensitive())                                      # Haken fehlt
        d.confirm.set_active(True)
        self.assertTrue(d.ok_btn.get_sensitive())
        sp = plan["space"]
        self.assertEqual(d.space.get_text(), f"Needed: {g(sp['need'] // 2**20)}, free: {g(100 * 1024)} "
                                             f"(after reserve: {g(90 * 1024)})")
        for bad in ("TEMPLATE-MAIL", "VAULT-X", "TEMPLATE-a b", ""):
            d.name.set_text(bad)
            self.assertFalse(d.ok_btn.get_sensitive(), bad)
        d.name.set_text("TEMPLATE-MAIL")
        self.assertIn("already used", d.name_msg.get_text())
        d.name.set_text("TEMPLATE-CLEAN")
        self.assertTrue(d.ok_btn.get_sensitive())
        d.destroy()
        self.hv.free = 5 * 2**30                                                        # zu wenig Platz
        d = MakeTemplateDialog(w, self.ev, self.ev.make_template_plan("VAULT-MAIL"))
        d.confirm.set_active(True)
        self.assertFalse(d.ok_btn.get_sensitive())
        self.assertIn("Not enough space in /srv/evoxd/templates", d.space_msg.get_text())
        self.assertIn("after reserve: " + g(0), d.space.get_text())
        d.destroy()
        # Template-Reiter: Zeile mit freiem Platz
        w.refresh()
        self.assertEqual(w.free_lbl.get_text(), f"Free in /srv/evoxd: {g(5 * 1024)}")
        w.destroy()

    def test_make_template_in_real_thread_progress_and_origin(self):
        from evoxd.gui import MainWindow
        self._vaults()
        w = MainWindow(self.ev)
        self.hv.clone_delay = 1.5
        t = w.make_template("VAULT-MAIL", "TEMPLATE-MAIL-2")
        self.assertTrue(w.cancel_copy_btn.get_visible())
        self.assertFalse(w.make_btn.get_sensitive())
        texts, fracs = set(), set()
        end = time.monotonic() + 20
        while w.busy and time.monotonic() < end:
            Gtk.main_iteration_do(False)
            if w.progress.get_visible():
                texts.add(w.progress.get_text().split("  ")[0])
                fracs.add(round(w.progress.get_fraction(), 2))
            time.sleep(0.01)
        t.join(20)
        self._wait(w)
        self.assertIn("Copying the disk of VAULT-MAIL (can take several minutes) …", texts)
        self.assertTrue([f for f in fracs if 0 < f < 1], fracs)                         # echte Prozentanzeige
        self.assertFalse(w.cancel_copy_btn.get_visible())
        self.assertTrue(w.msg.get_text().startswith("TEMPLATE-MAIL-2 v1 made from VAULT-MAIL ("), w.msg.get_text())
        self.assertEqual(w.tpl_store[0][0], "TEMPLATE-MAIL-2")                          # neueste oben
        w.tpl_view.get_selection().unselect_all()
        w.tpl_view.get_selection().select_path(0)
        self.assertTrue(w.tpl_detail.get_text().startswith("TEMPLATE-MAIL-2 v1: made from VAULT-MAIL on "))
        w.tpl_view.get_selection().unselect_all()
        w.tpl_view.get_selection().select_path(1)
        self.assertIn("imported from domain TEMPLATE-MAIL", w.tpl_detail.get_text())
        self.assertEqual([r[5] for r in w.vault_store if r[0] == "VAULT-MAIL"], ["TEMPLATE-MAIL-2 v1"])
        self.assertIn("TEMPLATE-MAIL-2", [r[0] for r in w.base_combo.get_model()])
        self.assertEqual(self.hv.domains["VAULT-MAIL"][1], "shutoff")
        w.destroy()

    def test_make_template_cancel_and_error(self):
        from evoxd.gui import MainWindow
        self._vaults()
        w = MainWindow(self.ev)
        self.hv.clone_delay = 1.0
        t = w.make_template("VAULT-MAIL", "TEMPLATE-MAIL-2")
        end = time.monotonic() + 5
        while self.reg.pending() == [] and time.monotonic() < end:
            Gtk.main_iteration_do(False)
            time.sleep(0.01)
        w.cancel_copy_btn.clicked()
        self.assertFalse(w.cancel_copy_btn.get_sensitive())
        self.assertTrue(w.progress.get_text().startswith("Cancelling"))
        t.join(20)
        self._wait(w)
        self.assertEqual(w.msg.get_text(), "Make template cancelled – partial copy deleted.")
        self.assertNotIn(w.colors["bad"], w.msg.get_label())                           # kein Fehler, nur Hinweis
        self.assertEqual([v for v in self.hv.vols if v.startswith("TEMPLATE-MAIL-2")], [])
        self.assertEqual(self.reg.pending(), [])
        self.hv.clone_delay = 0
        self.hv.free = 2**30                                                            # Platz knapp → saubere Ablehnung
        w.make_template("VAULT-MAIL", "TEMPLATE-MAIL-2").join(20)
        self._wait(w)
        self.assertTrue(w.msg.get_text().startswith("Error: Not enough space in /srv/evoxd/templates: needed"))
        self.assertIn(w.colors["bad"], w.msg.get_label())
        self.assertTrue(w.import_btn.get_sensitive())
        w.destroy()

    def test_orphan_cleanup_offered_at_start(self):
        from evoxd import config as C
        from evoxd.gui import MainWindow
        self.reg.add_pending("TEMPLATE-WEB-v1.qcow2", "TEMPLATE-WEB", 1, "VAULT-WEB")
        self.hv._add_vol("<volume><name>TEMPLATE-WEB-v1.qcow2</name></volume>", C.TEMPLATE_POOL, C.TEMPLATE_PATH)
        w = MainWindow(self.ev)
        asked = []
        w.offer_orphan_cleanup(ask=lambda title, text: asked.append(text) or False)    # Nein → bleibt
        self.assertIn("TEMPLATE-WEB-v1.qcow2 (from VAULT-WEB", asked[0])
        self.assertIn("TEMPLATE-WEB-v1.qcow2", self.hv.vols)
        self.assertEqual(w.msg.get_text(), "Unfinished copies kept. EVOX asks again at the next start.")
        w.offer_orphan_cleanup(ask=lambda *_: True)
        self._wait(w)
        self.assertNotIn("TEMPLATE-WEB-v1.qcow2", self.hv.vols)
        self.assertIn("TEMPLATE-MAIL-v1.qcow2", self.hv.vols)
        self.assertEqual(w.msg.get_text(), "Unfinished copies deleted: TEMPLATE-WEB-v1.qcow2.")
        asked.clear()
        w.offer_orphan_cleanup(ask=lambda title, text: asked.append(text))
        self.assertEqual(asked, [])                                                     # nichts mehr übrig
        w.destroy()


    def test_refresh_only_on_change_0_6_13(self):
        """Listen werden nur bei geändertem Inhalt neu aufgebaut; Auswahl bleibt ohne neues selection-changed."""
        import evoxd.gui as G
        self._vaults()
        self.ev.start("TEMPLATE-MAIL")
        w = G.MainWindow(self.ev)
        w.safe_refresh()
        clears = {"tpl": 0, "vault": 0, "temp": 0}
        for key, store in (("tpl", w.tpl_store), ("vault", w.vault_store), ("temp", w.store)):
            orig = store.clear

            def counted(k=key, o=orig):
                clears[k] += 1
                o()
            store.clear = counted
        w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
        w.tpl_view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
        self._select_vault(w, "VAULT-MAIL")
        signals = []
        for sel in (w.view, w.tpl_view, w.vault_view):
            sel.get_selection().connect("changed", lambda *_: signals.append(1))
        before = (w.selected(), w.selected_template(), w.selected_vault()["name"])
        calls = []
        for b in (w.make_btn, w.stop_btn, *w.howto_btns):
            orig_s = b.set_sensitive
            b.set_sensitive = lambda v, o=orig_s, n=b: (calls.append(n), o(v))
        for _ in range(3):
            w.safe_refresh()
        self.assertEqual(clears, {"tpl": 0, "vault": 0, "temp": 0})
        self.assertEqual(signals, [])
        self.assertEqual(calls, [])                                     # kein set_sensitive ohne Änderung
        self.assertEqual(before, (w.selected(), w.selected_template(), w.selected_vault()["name"]))
        # echte Änderung (neue VM) → Wegwerf-Liste wird neu aufgebaut, Auswahl bleibt
        self.ev.start("TEMPLATE-MAIL")
        w.safe_refresh()
        self.assertEqual(clears["temp"], 1)
        self.assertEqual(w.selected(), before[0])
        w.destroy()

    def test_tab_buttons_0_6_14(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        nb = w.tabs
        self.assertIsInstance(nb.bar.get_children()[0], Gtk.ToggleButton)      # eigene Knöpfe, kein Notebook
        self.assertEqual(G.TAB_KEYS, ("vault", "template", "disposable"))
        self.assertEqual(nb.get_current_page(), 2)                     # Startreiter DISPOSABLE
        self.assertEqual(nb.stack.get_visible_child_name(), "disposable")
        self.assertEqual((G.TAB_COLORS["vault"], G.TAB_COLORS["template"], G.TAB_COLORS["disposable"]),
                         ("#D4AF37", "#00F0FF", G.NAME_COLOR))
        self.assertTrue(nb.bar.get_homogeneous())
        self.assertEqual(nb.bar.get_spacing(), G.HOWTO_GAP)
        for i, key in enumerate(G.TAB_KEYS):
            b = nb.buttons[key]
            ctx = b.get_style_context()
            self.assertIs(nb.bar.get_children()[i], b)
            for c in (G.TAB_CLASSES[key], "evox-howto", "evox-tabbtn", f"evox-tabbtn-{key}"):
                self.assertTrue(ctx.has_class(c), c)
            self.assertNotEqual(G.TAB_CLASSES[key], "")
            sel = f".evox-tabbtn-{key}"
            self.assertIn(f"{sel}:not(:checked) {{ background-color: rgba(", G.CSS)            # inaktiv: blasse Farbe
            self.assertIn(f"{sel}:not(:checked) label {{ color: mix({G.TAB_COLORS[key]}", G.CSS)
            self.assertNotIn("#ffffff", G.CSS.split(f"{sel}:not(:checked) label {{")[1].split("}")[0])
            self.assertIn(f"{sel}:checked {{ border-bottom: 5px solid", G.CSS)                 # aktiv: Unterstreichung
        self.assertEqual({G.TAB_CLASSES[k] for k in G.TAB_KEYS}, {"evox-vault-btn", "evox-import-btn", "evox-start-disposable"})
        self.assertIn(f"min-height: {G.HOWTO_BTN_HEIGHT - 2 * G.HOWTO_PAD_V - 4}px", G.CSS)    # Höhe wie HOW-TO (evox-howto)
        for i in (0, 1, 2, 1):                                         # Klick auf Knopf schaltet den Stack
            nb.buttons[G.TAB_KEYS[i]].clicked()
            self.assertEqual(nb.stack.get_visible_child_name(), G.TAB_KEYS[i])
            self.assertEqual(nb.get_current_page(), i)
        nb.buttons["template"].clicked()                               # erneuter Klick auf aktiven Reiter: bleibt aktiv
        self.assertTrue(nb.buttons["template"].get_active())
        self.assertEqual(nb.get_current_page(), 1)
        for key, other in (("vault", "disposable"),):                  # Tastatur: Strg+Bild runter/hoch
            from gi.repository import Gdk
            nb.set_current_page(0)
            for kv, want in ((Gdk.KEY_Page_Down, 1), (Gdk.KEY_Page_Down, 2), (Gdk.KEY_Page_Down, 2), (Gdk.KEY_Page_Up, 1)):
                ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
                ev.keyval, ev.state = kv, Gdk.ModifierType.CONTROL_MASK
                self.assertTrue(w._on_key(w, ev))
                self.assertEqual(nb.get_current_page(), want)
        for k in G.TAB_KEYS:                                           # Leertaste/Enter = "activate"/"clicked" auf dem Knopf
            self.assertTrue(nb.buttons[k].get_can_focus())
        for i in range(3):                                             # Wechsel weiter möglich
            nb.set_current_page(i)
            self.assertEqual(nb.get_current_page(), i)
        w.destroy()


class NoSpawnGuardTest(NoSpawnMixin, unittest.TestCase):
    """Der Schutz selbst: ein echter Programmstart wird verhindert und vermerkt; Python bleibt erlaubt."""

    def test_real_program_is_blocked_and_recorded(self):
        import subprocess
        from tests import nospawn
        with self.assertRaises(OSError):
            subprocess.Popen(["/usr/bin/virt-viewer", "--version"])
        with self.assertRaises(OSError):
            subprocess.Popen("virt-viewer --version", shell=False)
        self.assertEqual(len(nospawn.VIOLATIONS), 2)
        nospawn.VIOLATIONS.clear()                        # absichtlich provoziert, nicht als Fehler werten
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        self.assertEqual(p.wait(20), 0)

    def test_mixin_fails_an_unnoticed_start(self):
        import subprocess
        import unittest as ut
        from tests import nospawn

        class Inner(NoSpawnMixin, ut.TestCase):
            def runTest(self):
                try:
                    subprocess.Popen(["virt-viewer"])
                except OSError:
                    pass                                   # Anwendung schluckt den Fehler
        outer = list(nospawn.VIOLATIONS)
        res = ut.TestResult()
        Inner().run(res)
        self.assertEqual(len(res.failures), 1)
        self.assertIn("real program", res.failures[0][1])
        nospawn.VIOLATIONS[:] = outer


class RegistryThreadTest(NoSpawnMixin, unittest.TestCase):
    """Ohne GTK: Registry im Hauptthread öffnen, aus echten Threads benutzen."""

    def test_registry_usable_from_other_threads(self):
        with tempfile.TemporaryDirectory() as d:
            reg = Registry(Path(d) / "r.db")
            bid = reg.add_base("TEMPLATE-X", 1, "v", "/p", "0" * 64, "u")
            errors = []

            def work(i):
                try:
                    reg.add_temp(f"DISPOSABLE-T-{i:02d}", f"uuid-{i}", bid, "o", "s", "none", None)
                    reg.active_temps()
                except Exception as e:  # noqa: BLE001
                    errors.append(e)
                finally:
                    reg.close()
            ts = [threading.Thread(target=work, args=(i,)) for i in range(8)]
            for t in ts:
                t.start()
            for t in ts:
                t.join(20)
            self.assertEqual(errors, [])
            self.assertEqual(len(reg.active_temps()), 8)
            reg.close()


if __name__ == "__main__":
    unittest.main()
