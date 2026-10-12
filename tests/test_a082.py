"""0.8.2: Color settings – selected-Zeilen von Anfang an in Markierungsfarbe (Fehler A), -BACKUP-Zeile änderbar (Fehler B),
Schrift/Fläche getrennt je Element, Dark-CSS unverändert, Sicherheitsfarben fest. Nur Attrappen/Testfenster, nospawn aktiv."""
import json
import unittest
import warnings
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import evoxd.gui as G
from evoxd import texts as T
from evoxd import theme as TH
from tests.test_a3b import HAVE_DISPLAY, GuiBase
from tests.test_a4a import gray_for

GOLD = json.loads((Path(__file__).parent / "data" / "css_081.json").read_text())


def spin():
    for _ in range(30):
        Gtk.main_iteration_do(False)


class ThemeStructureTest(unittest.TestCase):
    def test_dark_css_identical_to_081(self):
        for t in ("dark", "light"):
            for s in (80, 100, 150):
                self.assertEqual(TH.build_css(t, None, None, s), GOLD[f"{t}-{s}"], (t, s))
        self.assertEqual(TH.build_css("dark", {"make": "#C06010", "background": "#101010"}, None, 100), GOLD["dark-ov"])

    def test_new_role_named_and_defaults_match_old_signal_red(self):
        self.assertIn("backup_text", TH.ROLES)
        self.assertEqual(TH.ROLES["backup_text"], T.ROLE_NAMES["backup_text"])
        self.assertEqual(TH.DARK["backup_text"], TH.SIGNAL_DARK["bad"])
        self.assertEqual(TH.LIGHT["backup_text"], TH.SIGNAL_LIGHT["bad"])
        self.assertEqual(TH.backup_color({}, TH.SIGNAL_LIGHT), TH.SIGNAL_LIGHT["bad"])      # ohne Wahl wie vorher
        self.assertEqual(TH.backup_color({"backup_text": "#ABCDEF"}, TH.SIGNAL_LIGHT), "#ABCDEF")
        self.assertEqual(TH.backup_color({"backup_text": "red; x"}, TH.SIGNAL_DARK), TH.SIGNAL_DARK["bad"])

    def test_parts_per_element_type(self):
        for key, parts in TH.PREVIEW_PARTS.items():
            kinds = [p for p, _r in parts]
            self.assertIn(key, T.ELEMENT_NAMES)
            for p, r in parts:
                self.assertIn(r, TH.ROLES, key)
                self.assertNotIn(r, TH.SAFETY, key)
                self.assertIn(p, T.PART_NAMES)
            if key.startswith(("btn_", "tab_")) or key in ("row_vault_sel", "row_template_sel", "row_disposable_sel"):
                self.assertEqual(kinds, ["text", "background"], key)             # Knopf/Reiter/selected: beides getrennt
            elif key in ("title", "heading", "text", "name", "row_vault_normal", "row_disposable_normal"):
                self.assertEqual(kinds, ["text"], key)                          # nur Schrift
            elif key == "background":
                self.assertEqual(kinds, ["background"])
            else:
                self.assertEqual(key, "row_template_backup")
                self.assertEqual(kinds, ["text", "selected_text"])
        self.assertEqual(T.PART_NAMES["text"], "Text color")
        self.assertEqual(T.PART_NAMES["background"], "Background color")

    def test_text_and_background_roles_differ_and_are_checked_as_pair(self):
        pairs = {frozenset(p) for p in TH.PAIRS}
        for key, parts in TH.PREVIEW_PARTS.items():
            d = dict(parts)
            if "text" in d and "background" in d:
                self.assertNotEqual(d["text"], d["background"], key)
                self.assertIn(frozenset((d["text"], d["background"])), pairs, key)
        self.assertIn(frozenset(("background", "backup_text")), pairs)
        self.assertIn(frozenset(("sel_teal", "sel_teal_alt")), pairs)

    def test_contrast_rules_on_new_pairs(self):
        bg = TH.DARK["background"]
        for lvl, lo, hi in (("bad", 1.0, 1.9), ("warn", 2.1, 2.9), ("ok", 3.5, 21)):
            res = TH.check_role("dark", {}, "backup_text", gray_for(bg, lo, hi))
            self.assertEqual(res["level"], lvl)
            self.assertEqual(res["can_override"], lvl != "ok")
        for key in ("btn_make", "tab_vault", "row_vault_sel"):                  # Schrift = Fläche: abgelehnt
            parts = dict(TH.PREVIEW_PARTS[key])
            res = TH.check_role("dark", {}, parts["text"], TH.DARK[parts["background"]])
            self.assertEqual(res["level"], "bad", key)
            res = TH.check_role("dark", {}, parts["background"], TH.DARK[parts["text"]])
            self.assertEqual(res["level"], "bad", key)

    def test_safety_still_unchangeable(self):
        for role in TH.SAFETY:
            self.assertNotIn(role, TH.ROLES)
            self.assertEqual(TH.check_role("dark", {}, role, "#00ff00")["level"], "reject")
        for key in TH.PREVIEW_FIXED:
            self.assertNotIn(key, TH.PREVIEW_PARTS)
        r = TH.effective("dark", {k: "#123456" for k in TH.SAFETY})
        for k, v in TH.SAFETY.items():
            self.assertEqual(r[k], v)
        self.assertEqual(TH.sanitize({"roles": {k: "#123456" for k in TH.SAFETY}})["roles"], {})

    def test_migration_of_old_config(self):
        old = {"theme": "dark", "roles": {"sel_teal_alt": "#8B0000", "make": "#C06010", "make_text": "#FFFFFF"},
               "accepted": [], "font_scale": 120}                              # 0.8.1-Form, ohne backup_text
        s = TH.sanitize(old)
        self.assertEqual(s["roles"], {"sel_teal_alt": "#8B0000", "make": "#C06010", "make_text": "#FFFFFF"})
        self.assertEqual(s["font_scale"], 120)
        self.assertEqual(TH.effective(s["theme"], s["roles"])["backup_text"], TH.DARK["backup_text"])
        self.assertEqual(TH.sanitize({"theme": "light", "roles": {"backup_text": "#aa0000"}})["roles"],
                         {"backup_text": "#AA0000"})

    def test_preview_css_selected_beats_background_rule(self):
        css = TH.preview_css(TH.default_appearance())
        self.assertIn(".evox-preview treeview.view:not(:selected)", css)
        self.assertNotIn(".evox-preview treeview.view {", css)


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class DialogTest(GuiBase):
    def dialog(self, appearance=None):
        d = G.ColorSettingsDialog(None, appearance or TH.default_appearance())
        self.addCleanup(self.close, d)
        spin()
        return d

    @staticmethod
    def close(d):
        d.destroy()
        for _ in range(20):
            Gtk.main_iteration_do(False)

    @staticmethod
    def sel_bg(view, focused):
        flags = Gtk.StateFlags.SELECTED | (Gtk.StateFlags.FOCUSED if focused else Gtk.StateFlags.NORMAL)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            c = view.get_style_context().get_background_color(flags)
        return "#%02X%02X%02X" % (round(c.red * 255), round(c.green * 255), round(c.blue * 255))

    def test_selected_rows_initially_in_selection_color(self):
        """Fehler A (belegt, Messung): vorher VAULT ohne Fokus = Fensterhintergrund #242424."""
        for ap in (TH.default_appearance(), {"theme": "light", "roles": {}, "accepted": [], "font_scale": 100},
                   {"theme": "dark", "roles": {"background": "#101820"}, "accepted": [], "font_scale": 100}):
            d = self.dialog(ap)
            r = TH.effective(ap["theme"], ap["roles"])
            for area, key in (("vault", "sel_amber"), ("template", "sel_teal"), ("disposable", "sel_green")):
                view = d._rows[area][0]
                self.assertFalse(view.has_focus())
                self.assertEqual(self.sel_bg(view, False).upper(), r[key].upper(), (ap["theme"], area, "ohne Fokus"))
                self.assertEqual(self.sel_bg(view, True).upper(), r[key].upper(), (ap["theme"], area, "mit Fokus"))
            self.close(d)

    def test_backup_row_changeable_live(self):
        d = self.dialog()
        self.assertEqual(d._cur["backup"], TH.SIGNAL_DARK["bad"])
        d.pick_element("row_template_backup", "text")
        self.assertEqual(d.chooser.role, "backup_text")
        d.chooser.set_rgba(G.hex_rgba("#FF00FF"))
        self.assertEqual(d._cur["backup"], "#FF00FF")                           # live in der Vorschau, Entwurf unberührt
        self.assertNotIn("backup_text", d.draft["roles"])
        view, store, rows = d._rows["template"]
        col = view.get_column(0)
        col.cell_set_cell_data(store, store.get_iter(Gtk.TreePath.new_from_indices([1])), False, False)
        c = col.get_cells()[0].get_property("foreground-rgba")
        self.assertEqual("#%02X%02X%02X" % (round(c.red * 255), round(c.green * 255), round(c.blue * 255)), "#FF00FF")
        d.chooser.response(Gtk.ResponseType.OK)
        self.assertEqual(d.draft["roles"]["backup_text"], "#FF00FF")

    def test_backup_selected_uses_readable_replacement_role(self):
        d = self.dialog()
        d.pick_element("row_template_backup", "selected_text")
        self.assertEqual(d.chooser.role, "sel_teal_alt")
        d.chooser.set_rgba(G.hex_rgba(gray_for(TH.DARK["sel_teal"], 1.0, 1.9)))   # < 2:1 gegen Markierfläche
        self.assertIn("very hard to read", d.check_lbl.get_text())
        d.chooser.response(Gtk.ResponseType.CANCEL)
        self.assertNotIn("sel_teal_alt", d.draft["roles"])

    def test_backup_contrast_rules(self):
        d = self.dialog()
        d.pick_element("row_template_backup", "text")
        d.chooser.set_rgba(G.hex_rgba(gray_for(TH.DARK["background"], 2.2, 2.9)))
        self.assertTrue(d.use_btn.get_visible())                                  # 3:1-Warnung mit Use anyway
        d.chooser.set_rgba(G.hex_rgba(gray_for(TH.DARK["background"], 1.0, 1.9)))
        self.assertIn("very hard to read", d.check_lbl.get_text())                # < 2:1 stärkere Warnung, speicherbar
        self.assertTrue(d.use_btn.get_visible())
        d.chooser.response(Gtk.ResponseType.CANCEL)

    def test_two_parts_flow_and_single_part(self):
        d = self.dialog()
        self.assertIsNone(d.pick_element("tab_vault"))                            # zwei Teile: erst Auswahl
        self.assertIsNone(d.chooser)
        self.assertIsNotNone(d.parts_pop)
        self.assertEqual({p: b.get_label() for p, b in d.part_btns.items()},
                         {"text": "Text color", "background": "Background color"})
        d.part_btns["text"].clicked()
        self.assertEqual(d.chooser.role, "vault_text")
        self.assertIn("Text color", d.chooser.get_title())
        self.assertIn("Text color", d.edit_lbl.get_text())
        d.chooser.response(Gtk.ResponseType.CANCEL)
        d.pick_element("tab_vault")
        d.part_btns["background"].clicked()
        self.assertEqual(d.chooser.role, "vault")
        d.chooser.response(Gtk.ResponseType.CANCEL)
        self.assertEqual(d.pick_element("title"), "title")                        # nur Schrift: direkt
        self.assertEqual(d.chooser.role, "title")
        d.chooser.response(Gtk.ResponseType.CANCEL)
        self.assertEqual(d.pick_element("background"), "background")             # nur Fläche: direkt
        d.chooser.response(Gtk.ResponseType.CANCEL)

    def test_text_and_background_independent_and_live(self):
        d = self.dialog()
        calls = []
        orig = d._preview_prov.load_from_data
        d._preview_prov.load_from_data = lambda *a: calls.append(1) or orig(*a)
        d.pick_element("btn_verify", "text")
        d.chooser.set_rgba(G.hex_rgba("#FFFF00"))
        d.chooser.response(Gtk.ResponseType.OK)
        self.assertEqual(d.draft["roles"], {"verify_text": "#FFFF00"})            # Fläche unberührt
        d.pick_element("btn_verify", "background")
        d.chooser.set_rgba(G.hex_rgba("#204060"))
        d.chooser.response(Gtk.ResponseType.OK)
        self.assertEqual(d.draft["roles"], {"verify_text": "#FFFF00", "verify": "#204060"})
        self.assertIn("#FFFF00", d._pv_css.upper())
        self.assertIn("#204060", d._pv_css.upper())
        self.assertEqual(len(calls), 2)       # je Änderung genau ein Neuladen (Übernahme nach Live-Vorschau lädt nicht erneut)

    def test_part_pick_ignores_safety_and_unknown(self):
        d = self.dialog()
        for key in TH.PREVIEW_FIXED:
            self.assertIsNone(d.pick_element(key, "text"))
            self.assertIsNone(d.chooser)
            self.assertIsNone(d.parts_pop)
        self.assertIsNone(d.pick_element("title", "background"))                  # Teil gibt es nicht
        self.assertIsNone(d.chooser)

    def test_main_window_backup_color(self):
        try:
            self.ev.s.save_option(TH.KEY, {"theme": "dark", "roles": {"backup_text": "#FF00FF"}, "accepted": []})
            w = self.window()
            self.assertEqual(w.backup_color(), "#FF00FF")
            w.destroy()
            self.ev.s.save_option(TH.KEY, TH.default_appearance())
            w = self.window()
            self.assertEqual(w.backup_color(), w.colors["bad"])                   # ohne Wahl wie 0.8.1
            w.destroy()
        finally:
            G.apply_appearance(TH.default_appearance())


if __name__ == "__main__":
    unittest.main()
