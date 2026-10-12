"""0.8.1: Color settings – Vorschau mit Direktklick, Klartext-Rollennamen, Compare, Schriftgröße 80..150.
Nur Attrappen/Testfenster, kein libvirt, nospawn aktiv."""
import unittest

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

import evoxd.gui as G
from evoxd import texts as T
from evoxd import theme as TH
from tests.test_a3b import HAVE_DISPLAY, GuiBase
from tests.test_a4a import gray_for


def ev(kind):
    return Gdk.Event.new(kind)


class ScaleTest(unittest.TestCase):
    def test_grid_and_limits(self):
        self.assertEqual(TH.FONT_SCALES, (80, 90, 100, 110, 120, 130, 140, 150))
        self.assertEqual((TH.SCALE_MIN, TH.SCALE_MAX, TH.DEFAULT_SCALE), (80, 150, 100))
        for v in TH.FONT_SCALES:
            self.assertEqual(TH.scale_of(v), v)

    def test_migration_and_invalid(self):
        for old in (90, 100, 120, 140):                      # alte Stufen bleiben gültig
            self.assertEqual(TH.sanitize({"font_scale": old})["font_scale"], old)
        self.assertEqual(TH.scale_of(95), 100)               # auf das Raster gerundet
        self.assertEqual(TH.scale_of(104), 100)
        self.assertEqual(TH.scale_of(145), 150)
        for bad in (79, 0, -10, 151, 1000, "120", None, True, 120.0, [], {}):
            self.assertEqual(TH.scale_of(bad), 100, bad)

    def test_css_scaled_whole_ui(self):
        self.assertIn("window, dialog, messagedialog { font-size: 19.5pt; }", TH.build_css(scale=150))
        self.assertIn("font-size: 10.4pt", TH.build_css(scale=80))
        self.assertIn("font-size: 19.5pt", TH.preview_css({"theme": "dark", "roles": {}, "font_scale": 150}))
        self.assertIn("font-size: 10.4pt", TH.preview_css({"theme": "dark", "roles": {}, "font_scale": 80}))


class NamesTest(unittest.TestCase):
    def test_every_role_has_plain_name(self):
        self.assertEqual(set(TH.ROLES), set(T.ROLE_NAMES))
        for k, v in T.ROLE_NAMES.items():
            self.assertTrue(v.strip(), k)
        self.assertEqual(TH.ROLES["sel_amber"], "VAULT selected row")

    def test_every_element_named_and_mapped(self):
        for k, role in TH.PREVIEW_ELEMENTS.items():
            self.assertIn(role, TH.ROLES, k)
            self.assertIn(k, T.ELEMENT_NAMES, k)
        for k in TH.PREVIEW_FIXED:
            self.assertIn(k, T.ELEMENT_NAMES)
            self.assertNotIn(k, TH.PREVIEW_ELEMENTS)
        self.assertEqual(T.ELEMENT_NAMES["tab_template"], "TEMPLATE tab")
        self.assertEqual(T.ELEMENT_NAMES["btn_start_internet"], "Start INTERNET button")

    def test_no_safety_role_reachable(self):
        for role in TH.PREVIEW_ELEMENTS.values():
            self.assertNotIn(role, TH.SAFETY)


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class PreviewTest(GuiBase):
    def dialog(self, appearance=None):
        d = G.ColorSettingsDialog(None, appearance or TH.default_appearance())
        self.addCleanup(self.close, d)
        return d

    @staticmethod
    def close(d):
        d.destroy()
        for _ in range(20):                       # Zerstörung abarbeiten (X11-Ereignisse), damit spätere Zeittests ungestört laufen
            Gtk.main_iteration_do(False)

    def test_structure_per_area(self):
        d = self.dialog()
        for area in ("vault", "template", "disposable"):
            self.assertTrue(d.el[f"tab_{area}"].get_style_context().has_class(f"evox-tabbtn-{area}"))
            view, store, rows = d._rows[area]
            self.assertEqual(len(store), 2)
            self.assertEqual(store[0][0], "selected")
            self.assertTrue(view.get_selection().path_is_selected(Gtk.TreePath.new_first()))
        self.assertEqual(d._rows["template"][1][1][0], "-BACKUP")
        self.assertEqual(d._rows["vault"][1][1][0], "normal")
        self.assertEqual(d._rows["disposable"][1][1][0], "normal")
        for area, sel in (("vault", "amber"), ("template", "teal"), ("disposable", "green")):
            self.assertTrue(d._rows[area][0].get_style_context().has_class(f"evox-sel-{sel}"))
        for k, cls in (("btn_make", "evox-fn-make"), ("btn_import", "evox-import-btn"),
                       ("btn_start_internet", "evox-start-disposable"), ("btn_start_offline", "evox-offline"),
                       ("title", "evox-title"), ("heading", "evox-tagline")):
            self.assertTrue(d.el[k].get_style_context().has_class(cls), k)   # echte GUI-Klassen
        self.assertNotRegex(d._pv_css, r"\.pv-")                                   # keine Doppel-Definitionen

    def test_click_opens_chooser_for_exact_role(self):
        d = self.dialog()
        for key, parts in TH.PREVIEW_PARTS.items():
            for part, role in parts:
                self.assertEqual(d.pick_element(key, part), role, (key, part))
                self.assertEqual(d.chooser.role, role)
                self.assertEqual(d.role(), role)
                self.assertIn(T.ELEMENT_NAMES[key], d.edit_lbl.get_text())
                self.assertTrue(d.el[key].get_style_context().has_class("evox-pv-mark"))   # kurze Rahmenmarkierung
                d.chooser.response(Gtk.ResponseType.CANCEL)
                self.assertIsNone(d.chooser)

    def test_real_click_signals(self):
        d = self.dialog()
        d.el["btn_verify"].clicked()                                     # zwei Teile: erst Teilauswahl
        self.assertIsNone(d.chooser)
        self.assertEqual(set(d.part_btns), {"text", "background"})
        d.part_btns["background"].clicked()
        self.assertEqual(d.chooser.role, "verify")
        d.chooser.response(Gtk.ResponseType.CANCEL)
        view, _s, _r = d._rows["template"]
        path = Gtk.TreePath.new_from_indices([1])
        rect = view.get_cell_area(path, view.get_column(0))
        self.assertEqual(d._row_key_at("template", rect.x + 3, rect.y + 3), "row_template_backup")
        view.row_activated(path, view.get_column(0))
        self.assertEqual(set(d.part_btns), {"text", "selected_text"})
        d.part_btns["selected_text"].clicked()
        self.assertEqual(d.chooser.role, "sel_teal_alt")
        d.chooser.response(Gtk.ResponseType.CANCEL)
        view.row_activated(path, view.get_column(0))
        d.part_btns["text"].clicked()
        self.assertEqual(d.chooser.role, "backup_text")                  # 0.8.2: unmarkierte -BACKUP-Zeile änderbar
        d.chooser.response(Gtk.ResponseType.CANCEL)
        view = d._rows["vault"][0]
        view.row_activated(Gtk.TreePath.new_from_indices([1]), view.get_column(0))   # normale Zeile -> Rolle text
        self.assertEqual(d.chooser.role, "text")
        d.chooser.response(Gtk.ResponseType.CANCEL)

    def test_live_preview_and_commit(self):
        d = self.dialog()
        before = dict(d.draft["roles"])
        d.pick_element("btn_make", "background")
        d.chooser.set_rgba(G.hex_rgba("#C06010"))                        # live: Vorschau ja, Entwurf nein
        self.assertEqual(d.tentative, ("make", "#C06010"))
        self.assertEqual(d.draft["roles"], before)
        self.assertIn("#C06010", d._pv_css.upper())
        d.chooser.response(Gtk.ResponseType.OK)
        self.assertEqual(d.draft["roles"]["make"], "#C06010")
        self.assertIsNone(d.tentative)

    def test_warning_at_element_and_reject(self):
        d = self.dialog()
        d.pick_element("btn_verify", "background")
        d.chooser.set_rgba(G.hex_rgba(gray_for(TH.DARK["verify_text"], 2.2, 2.9)))
        self.assertEqual(d._warn_key, "btn_verify")
        self.assertTrue(d.el["btn_verify"].get_style_context().has_class("evox-pv-warn"))
        self.assertTrue(d.el["btn_verify"].get_label().startswith("⚠"))
        self.assertIn("Contrast only", d.el["btn_verify"].get_tooltip_text())
        self.assertTrue(d.use_btn.get_visible())
        d.chooser.response(Gtk.ResponseType.OK)
        self.assertEqual(d.pending[0], "verify")
        self.assertNotIn("verify", d.draft["roles"])
        self.assertTrue(d.use_anyway())
        self.assertIn("verify", d.draft["accepted"])
        self.assertFalse(d.el["btn_verify"].get_label().startswith("⚠"))
        d.pick_element("btn_remove", "background")
        d.chooser.set_rgba(G.hex_rgba(gray_for(TH.DARK["remove_text"], 1.0, 1.9)))   # < 2:1
        self.assertTrue(d.el["btn_remove"].get_style_context().has_class("evox-pv-bad"))
        self.assertIn("very hard to read", d.check_lbl.get_text())       # 0.9.0: stärkere Warnung, kein Verbot
        d.chooser.response(Gtk.ResponseType.OK)
        self.assertNotIn("remove", d.draft["roles"])                     # erst mit Use anyway im Entwurf
        self.assertTrue(d.use_anyway())
        self.assertIn("remove", d.draft["roles"])

    def test_no_override_role_text(self):
        d = self.dialog()
        d.pick_element("text")
        d.chooser.set_rgba(G.hex_rgba(gray_for(TH.DARK["background"], 2.2, 2.9)))
        self.assertTrue(d.use_btn.get_visible())                         # 0.9.0: nur warnen, Use anyway auch für Text
        d.chooser.response(Gtk.ResponseType.CANCEL)
        self.assertNotIn("text", d.draft["roles"])

    def test_safety_examples_not_clickable_or_changeable(self):
        d = self.dialog()
        before = dict(d.draft), d._pv_css
        for key in TH.PREVIEW_FIXED:
            w = d.el[key]
            self.assertIsInstance(w, Gtk.Label)                          # kein Knopf, kein Fokus
            self.assertFalse(w.get_can_focus())
            self.assertIsNone(d.pick_element(key))
            self.assertIsNone(d.chooser)
            self.assertIn("fixed for safety", d.check_lbl.get_text())
        self.assertTrue(d.el["fixed_stop"].get_style_context().has_class("evox-danger"))
        self.assertEqual((dict(d.draft), d._pv_css), before)
        for role in ("danger", "error", "mode_internet", "focus_inner"):
            self.assertEqual(d.propose(role, "#00ff00"), "reject")

    def test_danger_red_unchanged_in_preview_css(self):
        d = self.dialog()
        d.propose("remove", "#B05050")
        self.assertIn(".evox-danger { background-image: none; background-color: #d41f1f;", d._pv_css)

    def test_keyboard_focusable_and_status_text(self):
        d = self.dialog()
        for key in TH.PREVIEW_ELEMENTS:
            self.assertTrue(d.el[key].get_can_focus(), key)
            if not key.startswith("row_"):
                self.assertEqual(d.el[key].get_tooltip_text(), d._tip(key))
        d.el["tab_template"].emit("focus-in-event", ev(Gdk.EventType.FOCUS_CHANGE))
        self.assertEqual(d.statusline.get_text(), T.CS_STATUS_PARTS.format(name="TEMPLATE tab"))
        d.el["fixed_stop"].emit("enter-notify-event", ev(Gdk.EventType.ENTER_NOTIFY))
        self.assertIn("fixed for safety", d.statusline.get_text())
        self.assertEqual(d.el["btn_exit"].get_tooltip_text(), T.CS_PARTS_TIP.format(name="EXIT button"))
        self.assertEqual(d.el["title"].get_tooltip_text(), "Title")

    def test_compare(self):
        d = self.dialog()
        self.assertFalse(d.compare(True))
        self.assertIn("Nothing to compare", d.check_lbl.get_text())
        d.propose("make", "#C06010")
        draft = dict(d.draft["roles"])
        self.assertEqual(d.last_change, ("make", None))
        new_css = d._pv_css
        self.assertTrue(d.compare(True))
        self.assertNotEqual(d._pv_css, new_css)
        self.assertNotIn("#C06010", d._pv_css.upper())
        self.assertEqual(d.draft["roles"], draft)                        # rein visuell
        d.compare(False)
        self.assertEqual(d._pv_css, new_css)
        d.propose("make", "#D07020")                                     # zweite Änderung: alt = erste
        d.compare(True)
        self.assertIn("#C06010", d._pv_css.upper())
        self.assertNotIn("#D07020", d._pv_css.upper())
        d.compare(False)
        self.assertEqual(d.draft["roles"]["make"], "#D07020")
        d.compare_btn.emit("pressed")
        d.compare_btn.emit("released")
        self.assertFalse(d.compare_on)

    def test_reload_once_per_change(self):
        d = self.dialog()
        calls = []
        orig = d._preview_prov.load_from_data
        d._preview_prov.load_from_data = lambda *a: calls.append(1) or orig(*a)
        d.update_preview()
        d.update_preview()
        self.assertEqual(calls, [])                                      # nichts geändert: kein Neuladen
        d.size_scale.set_value(150)
        self.assertEqual(len(calls), 1)

    def test_slider_grid_and_range(self):
        d = self.dialog({"theme": "dark", "roles": {}, "accepted": [], "font_scale": 130})
        self.assertEqual(d.size_scale.get_value(), 130)
        adj = d.size_scale.get_adjustment()
        self.assertEqual((adj.get_lower(), adj.get_upper()), (80, 150))
        d.size_scale.set_value(117)                                      # rastet auf 120 ein
        self.assertEqual(d.draft["font_scale"], 120)
        d.size_scale.set_value(500)
        self.assertEqual(d.draft["font_scale"], 150)
        d.size_scale.set_value(1)
        self.assertEqual(d.draft["font_scale"], 80)

    def test_150_percent_layout_fits(self):
        d = self.dialog({"theme": "dark", "roles": {}, "accepted": [], "font_scale": 150})
        self.assertLessEqual(d.fitted_height, G.workarea_height() - G.DIALOG_DECOR)
        self.assertEqual(d.scroller.get_policy()[0], Gtk.PolicyType.AUTOMATIC)   # nichts abgeschnitten: scrollt

    def test_main_window_150_percent(self):
        """150 %: HOW-TO-Zeilen einzeilig mit Ellipsis, Mindestgröße-Anforderung nie über der Arbeitsfläche.
        (Der Inhalt kann auf kleinen Bildschirmen dennoch höher sein – siehe TECHNISCHER_IST-STAND §73.)"""
        try:
            G.apply_appearance({"font_scale": 150})
            w = self.window()
            w.show_all()
            for _ in range(30):
                Gtk.main_iteration_do(False)
            for b in w.howto_btns:
                self.assertEqual(b.get_child().get_ellipsize(), G.Pango.EllipsizeMode.END)
                self.assertTrue(b.get_child().get_single_line_mode())
            self.assertLessEqual(w.get_size_request()[1], G.workarea_height())
            w.destroy()
        finally:
            G.apply_appearance(TH.default_appearance())

    def test_main_css_untouched_by_preview(self):
        before = TH.active_css()
        d = self.dialog()
        d.pick_element("btn_make", "background")
        d.chooser.set_rgba(G.hex_rgba("#C06010"))
        d.chooser.response(Gtk.ResponseType.OK)
        d.size_scale.set_value(150)
        self.assertEqual(TH.active_css(), before)
        d.destroy()
        self.assertIsNone(d._preview_prov)


if __name__ == "__main__":
    unittest.main()
