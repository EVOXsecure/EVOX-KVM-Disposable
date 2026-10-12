"""0.6.20: Vorvorauswahl im Reiter TEMPLATE (neuestes Nicht-BACKUP), DISPOSABLE ohne Vorauswahl (nur Darstellung)."""
import tempfile
import unittest
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from evoxd import texts as T
from evoxd.config import Settings
from evoxd.lifecycle import Evox
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor
from tests.nospawn import NoSpawnMixin

HAVE_DISPLAY = Gtk.init_check([])[0]


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class TemplatePreselectTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        s = Settings(state_dir=d / "st", runtime_dir=d / "rt", guard_status=d / "x", config_file=d / "cfg.json")
        self.hv = FakeHypervisor()
        self.reg = Registry(s.registry_path)
        self.ev = Evox(s, self.hv, self.reg, net_check=lambda: (True, ""),
                       meminfo=lambda: {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20})

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def bases(self, spec):
        """spec: [(Name, created)] -> Registry-Einträge mit festem Importzeitpunkt."""
        for i, (name, created) in enumerate(spec):
            bid = self.reg.add_base(name, 1, f"{name}-{i}.qcow2", f"/p/{name}-{i}.qcow2", "0" * 64, f"u{i}")
            self.reg.db.execute("UPDATE bases SET created=? WHERE id=?", (created, bid))

    def win(self):
        from evoxd.gui import MainWindow
        return MainWindow(self.ev)

    def names(self, w):
        return [t["name"] for t in w.selected_bases()]

    def test_newest_non_backup_preselected(self):
        self.bases([("TEMPLATE-OLD", 1000), ("TEMPLATE-NEW", 3000), ("TEMPLATE-MID", 2000)])
        w = self.win()
        self.assertEqual(self.names(w), ["TEMPLATE-NEW"])
        self.assertEqual(w.tpl_store[0][0], "TEMPLATE-NEW")             # oberste Zeile
        w.destroy()

    def test_backup_never_preselected(self):
        self.bases([("TEMPLATE-A-BACKUP", 3000), ("TEMPLATE-B", 2000), ("TEMPLATE-C", 1000)])
        w = self.win()
        self.assertEqual(self.names(w), ["TEMPLATE-B"])                  # neuestes Nicht-BACKUP
        w.destroy()

    def test_only_backup_or_empty_no_selection(self):
        w = self.win()
        self.assertEqual(self.names(w), [])
        w.destroy()
        self.bases([("TEMPLATE-A-BACKUP", 3000), ("TEMPLATE-B-BACKUP", 2000)])
        w = self.win()
        self.assertEqual(self.names(w), [])
        w.refresh_templates()
        self.assertEqual(self.names(w), [])
        w.destroy()

    def test_user_selection_kept_and_no_extra_signals(self):
        self.bases([("TEMPLATE-OLD", 1000), ("TEMPLATE-NEW", 3000)])
        w = self.win()
        n = []
        w.tpl_view.get_selection().connect("changed", lambda *_: n.append(1))
        sel = w.tpl_view.get_selection()
        sel.unselect_all()
        sel.select_path(Gtk.TreePath.new_from_indices([1]))
        self.assertEqual(self.names(w), ["TEMPLATE-OLD"])
        n.clear()
        for _ in range(3):
            w.refresh_templates()
        self.assertEqual(self.names(w), ["TEMPLATE-OLD"])                # Benutzerauswahl bleibt
        self.assertEqual(n, [])                                          # kein Signal je Zyklus
        w.destroy()

    def test_refresh_preselects_new_template_when_nothing_selected(self):
        self.bases([("TEMPLATE-A-BACKUP", 1000)])
        w = self.win()
        self.assertEqual(self.names(w), [])
        self.bases([("TEMPLATE-Z", 5000)])
        w.refresh_templates()
        self.assertEqual(self.names(w), ["TEMPLATE-Z"])
        n = []
        w.tpl_view.get_selection().connect("changed", lambda *_: n.append(1))
        w.refresh_templates()
        w.refresh_templates()
        self.assertEqual(n, [])                                          # stabil: keine Signale
        w.destroy()

    def test_preselect_changes_nothing_and_buttons_correct(self):
        self.bases([("TEMPLATE-NEW", 3000)])
        before = (list(self.hv.list_domains()), len(self.reg.bases()), self.reg.bases()[0].damaged)
        w = self.win()
        self.assertEqual((list(self.hv.list_domains()), len(self.reg.bases()), self.reg.bases()[0].damaged), before)
        self.assertEqual(self.names(w), ["TEMPLATE-NEW"])
        self.assertTrue(w.remove_btn.get_sensitive() and w.verify_btn.get_sensitive())   # Zustand wie bisher (immer aktiv)
        w.tpl_view.get_selection().unselect_all()
        self.assertIsNone(w.on_remove(None))                             # bestehende Prüfung: ohne Markierung nur Hinweis
        self.assertEqual(w.msg.get_text(), T.MSG_SELECT_TEMPLATE)
        w.destroy()

    def test_disposable_has_no_preselection(self):
        self.bases([("TEMPLATE-NEW", 3000)])
        bid = self.reg.bases()[0].id
        self.hv.add_foreign("DISPOSABLE-NEW-01")
        self.reg.add_temp("DISPOSABLE-NEW-01", "uuid-1", bid, "o", "s", "none", None)
        w = self.win()
        self.assertEqual(len(w.store), 1)                                # laufende VM ist da ...
        for _ in range(3):
            w.refresh()
            self.assertEqual(w.view.get_selection().count_selected_rows(), 0)   # ... aber nie markiert
        self.assertIsNone(w.selected())
        w.destroy()


if __name__ == "__main__":
    unittest.main()
