"""0.6.11/0.6.12: Knopffarben, Hinweisbalken, Vorauswahl im Reiter VAULT, Markierungsfarbe (nur Darstellung)."""
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


def buttons(widget, out=None):
    """Alle echten Knöpfe unterhalb von widget (ohne Häkchen/Umschalter, Tabellenköpfe, Reiterköpfe)."""
    out = [] if out is None else out
    if isinstance(widget, Gtk.Button) and not isinstance(widget, Gtk.ToggleButton):
        out.append(widget)
    if isinstance(widget, (Gtk.TreeView, Gtk.ComboBox, Gtk.Notebook)):
        if isinstance(widget, Gtk.Notebook):
            for i in range(widget.get_n_pages()):
                buttons(widget.get_nth_page(i), out)
        return out
    if isinstance(widget, Gtk.Container):
        for c in widget.get_children():
            buttons(c, out)
    return out


def has_color_class(b):
    ctx = b.get_style_context()
    return any(ctx.has_class(c) for c in ctx.list_classes() if c.startswith("evox-"))


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class ButtonColorTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        s = Settings(state_dir=d / "st", runtime_dir=d / "rt", guard_status=d / "x", config_file=d / "cfg.json")
        self.hv = FakeHypervisor()
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.hv.add_vault("VAULT-MAIL")
        self.reg = Registry(s.registry_path)
        self.ev = Evox(s, self.hv, self.reg, net_check=lambda: (True, ""),
                       meminfo=lambda: {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20})
        self.ev.import_template("TEMPLATE-MAIL")

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def win(self):
        from evoxd.gui import MainWindow
        return MainWindow(self.ev)

    # ---- Hinweisbalken
    def test_hint_bar_hidden_then_shown_until_closed(self):
        w = self.win()
        vault = w.tabs.get_nth_page(0)
        self.assertTrue(w.hint_bar.is_ancestor(vault))
        self.assertFalse(w.hint_bar.get_visible())                     # vorher nicht sichtbar
        w.on_virt_manager(None, opener=lambda: None)
        self.assertTrue(w.hint_bar.get_visible())
        self.assertEqual(w.msg.get_text(), "")                         # kein grauer Text mehr
        w.on_virt_manager(None, opener=lambda: None)                   # bleibt, kein Verschwinden
        self.assertTrue(w.hint_bar.get_visible())
        self.assertTrue(w.hint_bar.get_style_context().has_class("evox-hint-bar"))
        self.assertEqual(w.hint_label.get_text(),
                         "virt-manager opened. Name new VMs  VAULT-<purpose>  or  TEMPLATE-<system> .")
        self.assertIn("<b>virt-manager opened.</b>", w.hint_label.get_label())
        self.assertEqual(w.hint_label.get_label().count("background="), 2)   # zwei Marken
        w.hint_close.clicked()
        self.assertFalse(w.hint_bar.get_visible())
        w.destroy()

    def test_hint_bar_error_does_not_show(self):
        w = self.win()

        def boom():
            raise RuntimeError("nope")
        w.on_virt_manager(None, opener=boom)
        self.assertFalse(w.hint_bar.get_visible())
        w.destroy()

    def test_hint_bar_gold_constant_and_css(self):
        import evoxd.gui as G
        self.assertEqual(G.HINT_BAR_BG, G.VAULT_GOLD)
        self.assertIn(f".evox-hint-bar {{ background-color: {G.VAULT_GOLD};", G.CSS)
        self.assertEqual(T.HINT_CLOSE, "✕")

    def test_hint_bar_below_button_row(self):
        w = self.win()
        page = w.tabs.get_nth_page(0)
        kids = page.get_children()
        row = w.make_btn.get_parent()
        self.assertEqual(kids.index(w.hint_bar), kids.index(row) + 1)
        w.destroy()

    # ---- Make template
    def test_make_template_color_and_locks_unchanged(self):
        import evoxd.gui as G
        w = self.win()
        ctx = w.make_btn.get_style_context()
        self.assertTrue(ctx.has_class("evox-fn-make"))
        self.assertEqual(G.FN_COLORS["make"][0], G.HOWTO_ORANGE)
        self.assertEqual(G.HOWTO_ORANGE, "#E0802A")
        w.vault_view.get_selection().unselect_all(); w._sync_vault()
        self.assertFalse(w.make_btn.get_sensitive())                    # nichts markiert → inaktiv, Klasse bleibt
        self.assertTrue(ctx.has_class("evox-fn-make"))
        self.assertEqual(w.make_btn.get_tooltip_text(), T.BTN_MAKE_TIP_NONE)   # Grund bleibt
        w.vault_view.get_selection().select_path(0)                     # VAULT-MAIL, ausgeschaltet
        self.assertTrue(w.make_btn.get_sensitive())
        self.assertTrue(ctx.has_class("evox-fn-make"))
        self.assertEqual(w.make_btn.get_tooltip_text(), T.BTN_MAKE_TIP)
        w.destroy()

    def test_disabled_css_is_pale_not_grey(self):
        import evoxd.gui as G
        for k, (bg, _b, _t) in G.FN_COLORS.items():
            r, g_, b = (int(bg[i:i + 2], 16) for i in (1, 3, 5))
            self.assertIn(f".evox-fn-{k}:disabled {{ background-color: rgba({r}, {g_}, {b}, 0.28);", G.CSS)
            self.assertIn(f"mix({bg}, @theme_fg_color, 0.35)", G.CSS)
        prov = Gtk.CssProvider()
        prov.load_from_data(G.CSS.encode())                             # CSS muss GTK-gültig sein

    def test_function_colors(self):
        w = self.win()
        for b, cls in ((w.verify_btn, "evox-fn-verify"), (w.remove_btn, "evox-fn-remove"),
                       (w.console_btn, "evox-fn-neutral"), (w.fullscreen_btn, "evox-fn-neutral"),
                       (w.make_btn, "evox-fn-make")):
            self.assertTrue(b.get_style_context().has_class(cls), cls)
        import evoxd.gui as G
        self.assertNotEqual(G.FN_COLORS["remove"][0], G.DANGER_COLOR)   # Remove nicht im kräftigen Gefahrrot
        self.assertEqual(len({v[0] for v in G.FN_COLORS.values()}), len(G.FN_COLORS))
        # unveränderte Knöpfe
        self.assertTrue(w.stop_btn.get_style_context().has_class("evox-danger"))
        self.assertTrue(w.import_btn.get_style_context().has_class("evox-import-btn"))
        self.assertTrue(w.virt_manager_btn.get_style_context().has_class("evox-vault-btn"))
        w.destroy()

    def test_no_button_without_color_class_main_window(self):
        w = self.win()
        bs = buttons(w)
        self.assertGreaterEqual(len(bs), 12)
        bad = [b.get_label() for b in bs if not has_color_class(b)]
        self.assertEqual(bad, [])
        w.destroy()

    def test_no_button_without_color_class_dialogs(self):
        import evoxd.gui as G
        from evoxd import purposes
        w = self.win()
        w.vault_view.get_selection().select_path(0)
        dialogs = [G.StartDialog(w, self.ev, "TEMPLATE-MAIL"),
                   G.StartDialog(w, self.ev, "TEMPLATE-MAIL", offline=True),
                   G.PurposeEditDialog(w, self.ev.s, purposes.DEFAULT_PURPOSES),
                   G.ImportDialog(w, self.ev),
                   G.MakeTemplateDialog(w, self.ev, self.ev.make_template_plan("VAULT-MAIL"))]
        w.tpl_view.get_selection().select_path(0)
        dialogs.append(G.RemoveDialog(w, w.selected_bases()))
        for d in dialogs:
            bs = buttons(d.get_action_area()) + buttons(d.get_content_area())
            self.assertTrue(bs, type(d).__name__)
            bad = [b.get_label() for b in bs if not has_color_class(b)]
            self.assertEqual(bad, [], type(d).__name__)
            d.destroy()
        w.destroy()

    def test_message_dialog_buttons_colored(self):
        import evoxd.gui as G
        d = Gtk.MessageDialog(buttons=Gtk.ButtonsType.YES_NO, text="x")
        G.style_responses(d, Gtk.ResponseType.YES, "evox-fn-remove", Gtk.ResponseType.NO)
        self.assertTrue(d.get_widget_for_response(Gtk.ResponseType.YES).get_style_context().has_class("evox-fn-remove"))
        self.assertTrue(d.get_widget_for_response(Gtk.ResponseType.NO).get_style_context().has_class("evox-cancel"))
        d.destroy()

    # ---- 0.6.12: Vorauswahl, Hinweis ohne VAULT, Markierungsfarbe
    def test_preselect_prefers_shutoff_else_first(self):
        self.hv.add_vault("VAULT-AAA", state="running")           # sortiert vor VAULT-MAIL
        self.hv.vault_states["VAULT-AAA"] = "running"
        w = self.win()
        self.assertEqual(w.selected_vault()["name"], "VAULT-MAIL")  # erste AUSGESCHALTETE
        self.assertTrue(w.make_btn.get_sensitive())
        self.assertEqual(w.make_btn.get_tooltip_text(), T.BTN_MAKE_TIP)
        w.destroy()
        self.hv.vault_states["VAULT-MAIL"] = "paused"
        w = self.win()
        self.assertEqual(w.selected_vault()["name"], "VAULT-AAA")   # keine ausgeschaltete → erste
        self.assertFalse(w.make_btn.get_sensitive())               # bestehende Prüfung unverändert
        w.destroy()

    def test_user_selection_survives_refresh(self):
        self.hv.add_vault("VAULT-ZZZ")
        w = self.win()
        self.assertEqual(w.selected_vault()["name"], "VAULT-MAIL")
        self._pick(w, "VAULT-ZZZ")
        w.refresh_vaults()
        w.refresh_vaults()
        self.assertEqual(w.selected_vault()["name"], "VAULT-ZZZ")
        w.vault_view.get_selection().unselect_all()                # nichts markiert → nächste Aktualisierung markiert
        w.refresh_vaults()
        self.assertEqual(w.selected_vault()["name"], "VAULT-MAIL")
        w.destroy()

    def _pick(self, w, name):
        for i, r in enumerate(w.vault_store):
            if r[0] == name:
                w.vault_view.get_selection().select_path(Gtk.TreePath.new_from_indices([i]))

    def test_preselect_changes_nothing(self):
        before = (list(self.hv.list_domains()), len(self.reg.bases()))
        w = self.win()
        self.assertEqual((list(self.hv.list_domains()), len(self.reg.bases())), before)
        w.destroy()

    def test_no_vault_hint_only_without_vault(self):
        w = self.win()
        self.assertFalse(w.novault_hint.get_visible())
        w.destroy()
        del self.hv.domains["VAULT-MAIL"]
        w = self.win()
        self.assertIsNone(w.selected_vault())
        self.assertTrue(w.novault_hint.get_visible())
        self.assertEqual(w.novault_hint.get_text(), "Before making a template, please create a new VAULT VM.")
        self.assertFalse(w.make_btn.get_sensitive())
        self.assertEqual(w.make_btn.get_tooltip_text(), T.BTN_MAKE_TIP_NONE)
        self.assertFalse(w.hint_bar.get_visible())                 # virt-manager-Balken getrennt, unverändert
        self.assertIsNot(w.novault_hint, w.hint_label)
        self.hv.add_vault("VAULT-NEW")
        w.refresh_vaults()
        self.assertFalse(w.novault_hint.get_visible())
        self.assertEqual(w.selected_vault()["name"], "VAULT-NEW")
        w.destroy()

    def test_selection_color_amber_never_purple(self):
        import re
        import evoxd.gui as G
        self.assertEqual(G.SELECT_AMBER, "#E0A030")
        self.assertIn(f"treeview.view:selected {{ background-color: #E0A030;", G.CSS)
        self.assertIn(":selected:hover", G.SELECT_CSS)
        self.assertIn(":selected:focus", G.SELECT_CSS)
        self.assertNotIn("B026FF".lower(), G.SELECT_CSS.lower())
        self.assertNotIn("8c00ff", G.SELECT_CSS.lower())
        for line in G.CSS.splitlines():                             # Lila nur in Titel/Reiter/Namen, nie bei :selected/:hover
            if re.search(r":selected|:hover", line) and "evox-chip" not in line:
                self.assertNotRegex(line.lower(), r"b026ff|8c00ff|e6ccff")

    def test_texts_have_german(self):
        self.assertTrue(hasattr(T, "NO_VAULT_HINT") and hasattr(T, "DE_NO_VAULT_HINT"))
        for n in ("HINT_OPENED", "HINT_NAME_NEW", "HINT_OR", "HINT_CLOSE_TIP"):
            self.assertTrue(hasattr(T, n) and hasattr(T, "DE_" + n), n)


if __name__ == "__main__":
    unittest.main()
