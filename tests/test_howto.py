"""0.6.7/0.6.8: Reiterfolge, HOW-TO-USE-Leiste (Layout, Farben, geführter Ablauf), Detailleiste, Namensanzeige (nur GUI)."""
import tempfile
import unittest
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from evoxd import texts as T
from evoxd.config import Settings
from evoxd.lifecycle import Evox
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor
from tests.nospawn import NoSpawnMixin

HAVE_DISPLAY = Gtk.init_check([])[0]


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class HowToTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        s = Settings(state_dir=d / "st", runtime_dir=d / "rt", guard_status=d / "x", config_file=d / "cfg.json")
        self.hv = FakeHypervisor()
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.reg = Registry(s.registry_path)
        self.ev = Evox(s, self.hv, self.reg, net_check=lambda: (True, ""),
                       meminfo=lambda: {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20})
        self.imported = False

    def tpl(self):
        if not self.imported:
            self.ev.import_template("TEMPLATE-MAIL")
            self.imported = True

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def win(self, vault=True, tpl=True):
        import evoxd.gui as G
        if vault:
            self.hv.add_vault("VAULT-MAIL")
        if tpl:
            self.tpl()
        return G.MainWindow(self.ev)

    def test_tab_order_labels_and_start_tab(self):
        import evoxd.gui as G
        w = self.win()
        nb = w.tabs
        self.assertEqual([nb.buttons[k].get_label() for k in nb.keys],
                         ["1. VAULT", "2. TEMPLATE", "3. DISPOSABLE"])
        self.assertEqual(G.TAB_KEYS, ("vault", "template", "disposable"))
        self.assertEqual(nb.get_current_page(), 2)
        self.assertTrue(nb.buttons["disposable"].get_active())
        self.assertEqual((G.TAB_COLORS["vault"], G.TAB_COLORS["template"], G.TAB_COLORS["disposable"]),
                         ("#D4AF37", "#00F0FF", "#39D353"))
        self.assertEqual(T.DE_TAB_VAULT, "1. VAULT")
        w.destroy()

    def test_howto_bar_buttons_classes_and_position(self):
        import evoxd.gui as G
        w = self.win()
        self.assertEqual(w.howto_title.get_text(), "HOW TO USE")
        self.assertEqual([b.get_label() for b in w.howto_btns],
                         ["1. CREATE NEW VAULT VM in virt-manager", "2. MAKE TEMPLATE of the VAULT",
                          "3. CHECK / IMPORT TEMPLATE", "4. START: INTERNET", "4. START: OFFLINE"])
        self.assertFalse(hasattr(w, "howto_start_lbl"))          # keine eigene Pille mehr
        for b, cls in zip(w.howto_btns, G.HOWTO_CLASSES):
            self.assertTrue(b.get_style_context().has_class(cls))
            self.assertTrue(b.get_style_context().has_class("evox-howto"))
            self.assertTrue(b.get_tooltip_text())
        self.assertEqual(len(T.HOWTO_STEPS), len(T.DE_HOWTO_STEPS))
        self.assertEqual(len(T.HOWTO_TIPS), len(T.DE_HOWTO_TIPS))
        self.assertTrue(T.DE_HOWTO_TIP_NO_VAULT and T.DE_HOWTO_TIP_NO_TEMPLATE)
        self.assertEqual(T.DE_HOWTO_STEPS[3:], ("4. START: INTERNET", "4. START: OFFLINE"))
        self.assertFalse(hasattr(T, "HOWTO_START_LABEL") or hasattr(T, "DE_HOWTO_START_LABEL"))
        box = w.howto_title.get_parent().get_parent()          # Hauptbox: Leiste direkt unter Tagline, über Reitern
        kids = box.get_children()
        self.assertEqual(kids.index(w.howto_title.get_parent()), kids.index(w.subline) + 1)
        self.assertLess(kids.index(w.howto_title.get_parent()), kids.index(w.tabs))
        w.destroy()

    def test_layout_four_rows_only_step4_has_two_buttons(self):
        w = self.win()
        rows = w.howto_rows.get_children()
        self.assertEqual(len(rows), 4)
        self.assertEqual(w.howto_rows.get_orientation(), Gtk.Orientation.VERTICAL)
        counts = [len([c for c in r.get_children() if isinstance(c, Gtk.Button)]) for r in rows[:3]]
        self.assertEqual(counts, [1, 1, 1])
        self.assertIs(rows[3], w.howto_start_row)
        self.assertEqual(w.howto_start_row.get_children(), [w.howto_btns[3], w.howto_btns[4]])
        for r, i in zip(rows[:3], range(3)):
            self.assertIs(r.get_children()[0], w.howto_btns[i])
        w.destroy()

    def test_fill_homogeneous_and_uniform_gap(self):
        import evoxd.gui as G
        w = self.win()
        self.assertEqual(G.HOWTO_GAP, 4)
        rows = w.howto_rows.get_children()
        self.assertEqual(w.howto_rows.get_spacing(), G.HOWTO_GAP)
        for r in rows[:3]:
            self.assertEqual(r.get_spacing(), G.HOWTO_GAP)
        self.assertEqual(w.howto_start_row.get_spacing(), G.HOWTO_GAP)
        self.assertTrue(w.howto_start_row.get_homogeneous())
        for b in w.howto_btns[:3]:
            p = b.get_parent()
            self.assertTrue(p.child_get_property(b, "expand"))
            self.assertTrue(p.child_get_property(b, "fill"))
        for b in w.howto_btns[3:]:
            p = b.get_parent()
            self.assertTrue(p.child_get_property(b, "expand") and p.child_get_property(b, "fill"))
        bar = w.howto_rows.get_parent()                                  # 0.7.3: Titel als Zeile über den Schritten
        self.assertEqual(bar.get_orientation(), Gtk.Orientation.VERTICAL)
        self.assertEqual(bar.get_children(), [w.howto_title, w.howto_rows])
        self.assertTrue(bar.child_get_property(w.howto_rows, "fill"))
        for b in w.howto_btns:
            lbl = b.get_child()
            self.assertEqual(lbl.get_ellipsize(), Pango.EllipsizeMode.END)
            self.assertTrue(lbl.get_single_line_mode())
        w.destroy()

    def test_fill_in_real_allocation(self):
        import evoxd.gui as G
        w = self.win()
        w.set_default_size(700, 500)
        w.show_all()
        for _ in range(50):
            while Gtk.events_pending():
                Gtk.main_iteration()
        widths = [b.get_allocated_width() for b in w.howto_btns[:3]]
        self.assertEqual(len(set(widths)), 1)
        pair = [b.get_allocated_width() for b in w.howto_btns[3:]]
        self.assertLessEqual(abs(pair[0] - pair[1]), 1)
        self.assertLessEqual(widths[0], w.get_allocated_width())
        total = pair[0] + 4 + pair[1]                      # Zeile 4 exakt so breit wie Zeilen 1–3
        self.assertLessEqual(abs(total - widths[0]), 1)
        self.assertEqual(w.howto_start_row.get_allocated_width(), widths[0])
        heights = {b.get_allocated_height() for b in w.howto_btns}
        self.assertEqual(len(heights), 1)                  # alle gleich hoch
        self.assertGreaterEqual(heights.pop(), G.HOWTO_BTN_HEIGHT if G.workarea_height() >= G.HOWTO_SMALL_WORKAREA
                                else G.HOWTO_BTN_HEIGHT_SMALL)
        w.destroy()

    def test_height_constants_and_compact_fallback(self):
        import evoxd.gui as G
        self.assertEqual((G.HOWTO_BTN_HEIGHT, G.HOWTO_BTN_HEIGHT_SMALL, G.HOWTO_GAP), (36, 30, 4))
        self.assertIn(f"min-height: {G.HOWTO_BTN_HEIGHT - 2 * G.HOWTO_PAD_V - 4}px", G.CSS)
        self.assertLess(G.HOWTO_BTN_HEIGHT_SMALL, G.HOWTO_BTN_HEIGHT)
        w = self.win()
        compact = G.workarea_height() < G.HOWTO_SMALL_WORKAREA
        for b in w.howto_btns:
            self.assertEqual(b.get_style_context().has_class("evox-howto-compact"), compact)
        w.destroy()
        orig = G.workarea_height
        try:
            G.workarea_height = lambda widget=None: 600
            w = self.win()
            self.assertTrue(all(b.get_style_context().has_class("evox-howto-compact") for b in w.howto_btns))
            w.destroy()
        finally:
            G.workarea_height = orig

    def test_colors_distinct_per_step(self):
        import evoxd.gui as G
        self.assertEqual(G.VAULT_GOLD, "#D4AF37")
        self.assertEqual(G.TAB_TEMPLATE_COLOR, "#00F0FF")
        self.assertEqual(G.MODE_OFFLINE, "#0060b3")
        self.assertEqual(G.HOWTO_ORANGE, "#E0802A")
        self.assertEqual(G.HOWTO_CLASSES[0], "evox-vault-btn")          # Gold
        self.assertEqual(G.HOWTO_CLASSES[2], "evox-import-btn")         # Türkis
        self.assertEqual(G.HOWTO_CLASSES[3], "evox-start-disposable")   # Neongrün = Reiter DISPOSABLE
        self.assertEqual(G.TAB_DISPOSABLE_COLOR, "#39D353")
        self.assertEqual(G.HOWTO_CLASSES[4], "evox-start-offline")      # Blau
        self.assertEqual(len(set(G.HOWTO_CLASSES)), 5)
        for cls in G.HOWTO_CLASSES:
            self.assertIn(f".{cls} {{", G.CSS)
        self.assertEqual(len({G.VAULT_GOLD, G.HOWTO_ORANGE, G.TAB_TEMPLATE_COLOR, G.TAB_DISPOSABLE_COLOR,
                              G.MODE_OFFLINE}), 5)
        self.assertEqual((G.TAB_COLORS["vault"], G.TAB_COLORS["template"], G.TAB_COLORS["disposable"]),
                         ("#D4AF37", "#00F0FF", "#39D353"))                 # Reiterfarben unverändert

    def state(self, w):
        return [(b.get_sensitive(), b.get_style_context().has_class("evox-next")) for b in w.howto_btns]

    def test_guided_no_vault_no_template(self):
        w = self.win(vault=False, tpl=False)       # 2 und 4 gesperrt, Schritt 1 hervorgehoben
        self.assertEqual(self.state(w), [(True, True), (False, False), (True, False), (False, False), (False, False)])
        self.assertEqual(w.howto_btns[3].get_tooltip_text(), "First create or import a template")
        self.assertEqual(w.howto_btns[4].get_tooltip_text(), "First create or import a template")
        self.assertEqual(w.howto_btns[1].get_tooltip_text(), T.HOWTO_TIP_NO_VAULT)
        w.destroy()

    def test_guided_only_vault(self):
        w = self.win(vault=True, tpl=False)        # 2 frei, 4 gesperrt, 2 und 3 hervorgehoben
        self.assertEqual(self.state(w), [(True, False), (True, True), (True, True), (False, False), (False, False)])
        self.assertEqual(w.howto_btns[1].get_tooltip_text(), T.HOWTO_TIPS[1])
        w.destroy()

    def test_guided_template_without_vault(self):
        w = self.win(vault=False, tpl=True)        # 2 gesperrt, 4 frei und hervorgehoben
        self.assertEqual(self.state(w), [(True, False), (False, False), (True, False), (True, True), (True, True)])
        self.assertEqual(w.howto_btns[3].get_tooltip_text(), T.HOWTO_TIPS[3])
        w.destroy()

    def test_guided_both(self):
        w = self.win(vault=True, tpl=True)
        self.assertEqual(self.state(w), [(True, False), (True, False), (True, False), (True, True), (True, True)])
        w.destroy()

    def test_steps_1_and_3_always_clickable_and_locked_buttons_do_nothing(self):
        import evoxd.gui as G
        w = self.win(vault=False, tpl=False)
        self.assertTrue(w.howto_btns[0].get_sensitive() and w.howto_btns[2].get_sensitive())
        opened = []
        real = G.StartDialog
        G.StartDialog = lambda *a, **k: opened.append(1)
        try:
            w.howto_btns[3].clicked()           # gesperrt: GTK löst clicked() nicht aus
            w.howto_btns[4].clicked()
        finally:
            G.StartDialog = real
        self.assertEqual(opened, [])
        w.destroy()

    def test_unknown_state_locks_nothing_no_highlight(self):
        w = self.win(vault=False, tpl=False)
        w._vault_known = False
        w._sync_howto()
        self.assertIsNone(w.howto_state())
        self.assertEqual(self.state(w), [(True, False)] * 5)
        w.destroy()
        w = self.win(vault=False, tpl=False)
        w.ev.reg.bases = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
        w._sync_howto()
        self.assertIsNone(w.howto_state())
        self.assertEqual(self.state(w), [(True, False)] * 5)
        w.destroy()

    def test_bar_updates_after_state_change(self):
        w = self.win(vault=False, tpl=False)
        self.assertFalse(w.howto_btns[1].get_sensitive())
        self.hv.add_vault("VAULT-NEW")
        w.safe_refresh()                                            # nächster Aktualisierungszyklus
        self.assertEqual(self.state(w)[:2], [(True, False), (True, True)])
        self.assertFalse(w.howto_btns[3].get_sensitive())
        self.tpl()
        w.refresh_bases()
        w.safe_refresh()
        self.assertEqual(self.state(w), [(True, False), (True, False), (True, False), (True, True), (True, True)])
        w.destroy()

    def test_normal_tab_buttons_unchanged_by_guidance(self):
        w = self.win(vault=False, tpl=False)
        self.assertTrue(w.virt_manager_btn.get_sensitive())
        self.assertFalse(w.make_btn.get_sensitive())               # eigene Prüfung (keine Auswahl), nicht die Leiste
        self.assertEqual(w.make_btn.get_tooltip_text(), T.BTN_MAKE_TIP_NONE)
        self.assertTrue(w.import_btn.get_sensitive())
        self.assertTrue(w.start_btn.get_sensitive() and w.start_offline_btn.get_sensitive())
        for b in (w.virt_manager_btn, w.make_btn, w.import_btn, w.start_btn, w.start_offline_btn):
            self.assertFalse(b.get_style_context().has_class("evox-next"))
        w.destroy()

    def test_steps_1_to_3_only_navigate_and_flash(self):
        import evoxd.gui as G
        w = self.win()

        def boom(*a, **k):
            raise AssertionError("darf nicht aufgerufen werden")
        saved = (G.StartDialog, G.ImportDialog, G.MakeTemplateDialog)
        G.StartDialog = G.ImportDialog = G.MakeTemplateDialog = boom
        try:
            before = (list(self.hv.calls), self.ev.list_temps(), len(self.reg.bases()))
            for step, (page, target) in enumerate(((0, w.virt_manager_btn), (0, w.make_btn), (1, w.import_btn))):
                w.tabs.set_current_page(2)
                w.howto_btns[step].clicked()
                self.assertEqual(w.tabs.get_current_page(), page)
                self.assertTrue(target.get_style_context().has_class("evox-flash"))
                self.assertFalse(w.busy)
            w._unflash()                                            # Hervorhebung endet
            self.assertFalse(w.import_btn.get_style_context().has_class("evox-flash"))
            self.assertEqual(before, (list(self.hv.calls), self.ev.list_temps(), len(self.reg.bases())))
        finally:
            G.StartDialog, G.ImportDialog, G.MakeTemplateDialog = saved
        w.destroy()

    def test_steps_4_5_open_dialog_in_mode_and_start_nothing(self):
        import evoxd.gui as G
        w = self.win()
        seen = []

        class CancelDialog(G.StartDialog):
            def run(self):
                seen.append((self.offline, self.ok_btn.get_style_context().has_class(
                    "evox-start-offline" if self.offline else "evox-start-disposable")))
                return Gtk.ResponseType.CANCEL
        real = G.StartDialog
        G.StartDialog = CancelDialog
        try:
            w.tabs.set_current_page(0)
            w.howto_btns[3].clicked()
            self.assertEqual(w.tabs.get_current_page(), 2)
            w.tabs.set_current_page(1)
            w.howto_btns[4].clicked()
            self.assertEqual(w.tabs.get_current_page(), 2)
        finally:
            G.StartDialog = real
        self.assertEqual(seen, [(False, True), (True, True)])
        self.assertEqual(self.ev.list_temps(), [])                  # nichts gestartet
        self.assertFalse(w.busy)
        w.destroy()

    def test_howto_start_buttons_follow_busy(self):
        w = self.win()
        self.assertTrue(w.howto_btns[3].get_sensitive() and w.howto_btns[4].get_sensitive())
        w._run(lambda: None)                                        # Vorgang läuft: Start-Knöpfe aus
        self.assertFalse(w.howto_btns[3].get_sensitive() or w.howto_btns[4].get_sensitive())
        for _ in range(500):                                        # Vorgang zu Ende laufen lassen
            Gtk.main_iteration_do(False)
            if not w.busy:
                break
        self.assertTrue(w.howto_btns[3].get_sensitive() and w.howto_btns[4].get_sensitive())
        self.assertIn(w.howto_btns[3], w.action_btns)
        self.assertNotIn(w.howto_btns[0], w.action_btns)
        w.destroy()

    def test_details_row_always_visible_button_needs_selection(self):
        """0.7.4: Kurzzeile bleibt immer sichtbar (kein Platzhalter-Sprung), Knopf OPEN DETAILS nur mit Markierung."""
        self.assertFalse(hasattr(T, "DETAILS_NONE"))
        self.tpl()
        self.ev.start("TEMPLATE-MAIL", purpose="EMAIL", memory_mib=2048, vcpus=1)
        w = self.win()
        self.assertTrue(w.details.get_visible())
        self.assertFalse(w.details_btn.get_sensitive())
        w.view.get_selection().select_path(0)
        self.assertTrue(w.details_btn.get_sensitive())
        w.view.get_selection().unselect_all()
        self.assertFalse(w.details_btn.get_sensitive())
        self.assertTrue(w.details.get_visible())
        w.destroy()

    def test_name_display_split_keeps_real_name(self):
        import evoxd.gui as G
        self.assertEqual(G.split_vm_name("DISPOSABLE-EMAIL-01"), ("DISPOSABLE-EMAIL", "-01"))
        self.assertEqual(G.split_vm_name("DISPOSABLE-A1-12"), ("DISPOSABLE-A1", "-12"))
        self.assertEqual(G.split_vm_name("DISPOSABLE-X"), ("DISPOSABLE-X", ""))
        w = self.win()
        d = G.StartDialog(w, self.ev, "TEMPLATE-MAIL")
        d.purpose.get_child().set_text("EMAIL")
        self.assertEqual((d.name_main, d.name_num), ("DISPOSABLE-EMAIL", "-01"))
        self.assertEqual(d.name_lbl.get_text(), d.vm_name)           # angezeigt = tatsächlich
        self.assertEqual(d.name_main + d.name_num, d.vm_name)
        self.assertTrue(d.name_lbl.get_use_markup())
        self.assertIn('size="xx-small"', d.name_lbl.get_label())
        self.assertTrue(d.name_lbl.get_style_context().has_class("evox-vmname"))
        self.ev.start("TEMPLATE-MAIL", purpose="EMAIL", memory_mib=2048, vcpus=1)
        d.update()                                                   # live: nächste Nummer
        self.assertEqual((d.name_lbl.get_text(), d.name_num), ("DISPOSABLE-EMAIL-02", "-02"))
        real = self.ev.start("TEMPLATE-MAIL", purpose="EMAIL", memory_mib=2048, vcpus=1)
        self.assertEqual(real.name, d.vm_name)                       # echter Name inkl. Nummer unverändert
        d.purpose.get_child().set_text("a b")                        # Fehler: kein Markup, Name None
        self.assertIsNone(d.vm_name)
        self.assertFalse(d.name_lbl.get_use_markup())
        d.destroy()
        w.destroy()
