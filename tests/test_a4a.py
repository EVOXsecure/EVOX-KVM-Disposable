"""0.8.0 (A4a): Farbrollen zentral (theme.py), Themes Dark/Light, feste Sicherheitsfarben, Color settings,
Kontrastregeln, Schriftgröße, Live-Anwendung. Nur Attrappen (FakeHypervisor, nospawn), kein echtes libvirt."""
import json
import os
import re
import unittest
from pathlib import Path
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

import evoxd.gui as G
from evoxd import theme as TH
from evoxd import texts as T
from tests.test_a3b import HAVE_DISPLAY, GuiBase
from tests.test_a3e import MonitorZeroCallsTest, key, pump
from tests.test_live import GIB_KIB, raw

SNAP = Path(__file__).parent / "data" / "css-0.7.5.css"
DANGER_RULES = (".evox-danger { background-image: none; background-color: #d41f1f; color: #ffffff;\n"
                "  border: 2px solid #ffd6d6; }",
                ".evox-danger label { color: #ffffff; }",
                ".evox-lock-bad { color: #d41f1f; font-weight: bold; }",
                ".evox-warn { color: #d41f1f; font-weight: bold; }",
                ".evox-bar-internet { background-color: #1FA855; }",
                ".evox-bar-offline { background-color: #0060b3; }")


def gray_for(bg, lo, hi):
    """Eine Grau-Farbe, deren Kontrast zu bg in [lo, hi) liegt (für Grenzfälle der Regeln)."""
    for v in range(256):
        c = "#%02X%02X%02X" % (v, v, v)
        if lo <= TH.contrast(c, bg) < hi:
            return c
    raise AssertionError("kein Grauwert")


def every_safety_override():
    return {k: "#123456" for k in TH.SAFETY}


class DarkIdentityTest(unittest.TestCase):
    def test_dark_css_identical_to_075(self):
        snap = SNAP.read_text()
        self.assertEqual(TH.build_css(), snap)
        self.assertEqual(TH.build_css("dark", {}, "#C6FF00", 100), snap)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(G.FOCUS_ENV, None)
            if G.FOCUS_COLOR == G.FOCUS_DEFAULT:
                self.assertEqual(G.CSS, snap)

    def test_active_default_css_identical(self):
        old = TH.active()["appearance"]
        try:
            TH.activate(None)
            self.assertEqual(TH.active_css(), SNAP.read_text())
            TH.activate({"theme": "nope", "roles": "x", "font_scale": 77})       # Unsinn -> Standard
            self.assertEqual(TH.active_css(), SNAP.read_text())
        finally:
            TH.activate(old)

    def test_aliases_point_to_dark_roles(self):
        self.assertEqual(G.NEON_GREEN, TH.DARK["disposable"])
        self.assertEqual(G.TITLE_COLOR, "#8c00ff")
        self.assertEqual(G.FN_COLORS["verify"], ("#4A6F94", "#dbe6f1", "#ffffff"))
        self.assertEqual(G.SELECT_STYLES["green"], ("#39D353", "#04210c", "#5c0000"))
        self.assertEqual(G.DANGER_COLOR, TH.SAFETY["danger"])

    def test_gui_has_no_color_literals(self):
        """Alle Farben an EINER Stelle: gui.py enthält keine #RRGGBB-Werte außer der festen Peak-Marke."""
        src = Path(G.__file__).read_text(encoding="utf-8")
        hits = set(re.findall(r"#[0-9A-Fa-f]{6}\b", src))
        self.assertEqual(hits, {"#ffffff"}, hits)                 # METER_PEAK_COLOR (weiß, fest)

    def test_themes_are_data_and_complete(self):
        for k, t in TH.THEMES.items():
            self.assertEqual(set(t), {"label", "base", "roles"})
            self.assertEqual(set(t["roles"]), set(TH.ROLES), k)
            self.assertTrue(all(TH.valid_hex(v) for v in t["roles"].values()), k)
            self.assertFalse(set(t["roles"]) & set(TH.SAFETY), k)
        self.assertEqual(TH.THEMES["dark"]["label"], "Dark (default)")
        self.assertEqual(TH.THEMES["dark"]["base"], "system")       # kein Grund-CSS: wie 0.7.5


class LightThemeTest(unittest.TestCase):
    def test_light_contrasts(self):
        r = TH.effective("light")
        for a, b in TH.PAIRS:
            c = TH.contrast(r[a], r[b])
            need = 3.0 if b.endswith("_alt") else 4.5
            self.assertGreaterEqual(c, need, (a, b, round(c, 2)))

    def test_light_adjusts_neon_teal_lime(self):
        r = TH.effective("light")
        for k in ("disposable", "template", "sel_green", "sel_teal", "name", "vm_name"):
            self.assertNotEqual(r[k], TH.DARK[k], k)
        self.assertNotEqual(r["focus"], "#C6FF00")
        self.assertEqual(TH.focus_clash(r), [])                    # Fokus auf jeder Knopffläche ≥ 1,5:1
        for k in TH.BUTTON_FILLS:
            self.assertGreaterEqual(TH.contrast(r["focus"], r[k]), 1.5, k)

    def test_light_paints_base_and_keeps_safety(self):
        css = TH.build_css("light")
        self.assertIn("window, dialog, messagedialog, .background { background-color: #f6f5f4; color: #1a1a1a; }", css)
        for rule in DANGER_RULES:
            self.assertIn(rule, css)

    def test_extensible(self):
        """Ein weiteres Theme (A4b) ist nur ein Eintrag in THEMES."""
        extra = dict(TH.DARK, disposable="#00E5FF")
        with mock.patch.dict(TH.THEMES, {"neo": {"label": "Neo", "base": "system", "roles": extra}}):
            self.assertIn("background-color: #00E5FF", TH.build_css("neo"))
            self.assertEqual(TH.sanitize({"theme": "neo"})["theme"], "neo")
        self.assertEqual(TH.sanitize({"theme": "neo"})["theme"], "dark")


class ValidationTest(unittest.TestCase):
    def test_valid_hex(self):
        for v in ("#ffffff", "#FFFFFF", "#a1B2c3", "#000000"):
            self.assertTrue(TH.valid_hex(v), v)
        for v in ("#fff", "fff000", "#fff;}x{", "#ffffff;}", "#ffffff\n", " #ffffff", "#ffffff ", "#gggggg",
                  "red", "#ffffffff", "", None, 123, ["#ffffff"], "#ffffff}window{color:red", "＃ffffff"):
            self.assertFalse(TH.valid_hex(v), repr(v))

    def test_norm_upper(self):
        self.assertEqual(TH.norm_hex("#a1b2c3"), "#A1B2C3")
        with self.assertRaises(ValueError):
            TH.norm_hex("#fff;}x{")

    def test_injection_never_reaches_css(self):
        bad = {"disposable": "#fff;}x{", "text": "#ffffff}window{color:red", "verify": "url(x)",
               "background": "#000000; } * { color: red", "focus": "#C6FF00\n}"}
        css = TH.build_css("dark", bad)
        self.assertEqual(css, SNAP.read_text())
        self.assertEqual(TH.sanitize({"roles": bad})["roles"], {})
        self.assertNotIn("}x{", TH.build_css("dark", bad, focus="#fff;}x{"))

    def test_case_and_unknown_roles(self):
        a = TH.sanitize({"roles": {"verify": "#2a4f74", "nope": "#000000", 5: "#000000"}})
        self.assertEqual(a["roles"], {"verify": "#2A4F74"})

    def test_sanitize_structures(self):
        for raw_ in (None, [], "x", 5, {"roles": []}, {"roles": "x"}, {"theme": 3}, {"font_scale": "120"},
                     {"font_scale": True}, {"font_scale": 130}, {"accepted": "verify"}):
            a = TH.sanitize(raw_)
            self.assertIn(a["theme"], TH.THEMES)
            self.assertIn(a["font_scale"], TH.FONT_SCALES)
        self.assertEqual(TH.sanitize({"font_scale": 140})["font_scale"], 140)
        self.assertEqual(TH.sanitize({"font_scale": 130})["font_scale"], 130)       # 0.8.1: Raster 80..150


class SafetyColorsTest(unittest.TestCase):
    def test_not_in_roles_and_not_overridable(self):
        self.assertFalse(set(TH.SAFETY) & set(TH.ROLES))
        self.assertEqual(TH.sanitize({"roles": every_safety_override()})["roles"], {})
        for k in TH.SAFETY:
            self.assertEqual(TH.check_role("dark", {}, k, "#123456")["level"], "reject", k)
            self.assertEqual(TH.effective("light", {k: "#123456"})[k], TH.SAFETY[k])

    def test_every_theme_and_override_keeps_safety_css(self):
        for t in TH.THEMES:
            for ov in ({}, every_safety_override(), {"danger": "#00ff00", "error": "#00ff00"},
                       {"background": "#ffffff", "text": "#000000"}):
                css = TH.build_css(t, ov, scale=140)
                for rule in DANGER_RULES:
                    self.assertIn(rule, css, (t, ov))

    def test_role_function_fixed(self):
        old = TH.active()["appearance"]
        try:
            TH.activate({"theme": "light", "roles": every_safety_override()})
            for k, v in TH.SAFETY.items():
                self.assertEqual(TH.role(k), v)
        finally:
            TH.activate(old)

    def test_signal_colors_fixed(self):
        self.assertEqual(G.COLORS_DARK["bad"], "#ff7b72")
        self.assertEqual(G.COLORS_LIGHT["bad"], "#c01c28")
        self.assertIs(G.COLORS_DARK, TH.SIGNAL_DARK)


class ContrastRuleTest(unittest.TestCase):
    def test_bad_below_2_still_allowed(self):
        c = gray_for("#ffffff", 1.2, 1.9)
        res = TH.check_role("dark", {}, "verify", c)          # verify-Fläche gegen weiße Schrift
        self.assertEqual(res["level"], "bad")              # 0.9.0: stärkere Warnung, aber nie verweigert
        self.assertTrue(res["can_override"])

    def test_warn_between_2_and_3_use_anyway_allowed(self):
        c = gray_for("#ffffff", 2.2, 2.9)
        res = TH.check_role("dark", {}, "verify", c)
        self.assertEqual(res["level"], "warn")
        self.assertTrue(res["can_override"])

    def test_text_role_use_anyway_allowed(self):
        c = gray_for(TH.DARK["background"], 2.2, 2.9)
        res = TH.check_role("dark", {}, "text", c)
        self.assertEqual(res["level"], "warn")
        self.assertTrue(res["can_override"])

    def test_ok_and_theme_baseline(self):
        self.assertEqual(TH.check_role("dark", {}, "verify", "#2A4F74")["level"], "ok")
        # Titel liegt im Theme schon unter 3:1 (Glühen): unverändert kein Fehler, schlechter -> Warnung/Ablehnung
        self.assertLess(TH.contrast(TH.DARK["title"], TH.DARK["background"]), 3)
        self.assertEqual(TH.check_role("dark", {}, "title", TH.DARK["title"])["level"], "ok")
        self.assertEqual(TH.check_role("dark", {}, "title", "#2a2a2a")["level"], "bad")

    def test_sanitize_drops_low_contrast_unless_accepted(self):
        c = gray_for("#ffffff", 2.2, 2.9)
        self.assertEqual(TH.sanitize({"roles": {"verify": c}})["roles"], {})
        a = TH.sanitize({"roles": {"verify": c}, "accepted": ["verify"]})
        self.assertEqual(a["roles"], {"verify": c})
        t = gray_for(TH.DARK["background"], 2.2, 2.9)
        self.assertEqual(TH.sanitize({"roles": {"text": t}})["roles"], {})
        self.assertEqual(TH.sanitize({"roles": {"text": t}, "accepted": ["text"]})["roles"], {"text": t})
        r = gray_for("#ffffff", 1.2, 1.9)
        self.assertEqual(TH.sanitize({"roles": {"verify": r}})["roles"], {})
        self.assertEqual(TH.sanitize({"roles": {"verify": r}, "accepted": ["verify"]})["roles"], {"verify": r})

    def test_focus_clash_warning(self):
        res = TH.check_role("dark", {}, "focus", "#4A6F94")        # = Verify-Fläche
        self.assertIn("verify", [k for k, _ in res["focus_clash"]])
        res = TH.check_role("dark", {}, "verify", TH.DARK["focus"])  # Knopf wie Fokusfarbe
        self.assertIn("verify", [k for k, _ in res["focus_clash"]])


class FontScaleTest(unittest.TestCase):
    def test_scale_values(self):
        self.assertIn("window, dialog, messagedialog { font-size: 15.6pt; }", TH.build_css(scale=120))
        self.assertIn(".evox-mon-stopped { font-size: 56pt;", TH.build_css(scale=140))
        self.assertIn("window, dialog, messagedialog { font-size: 11.7pt; }", TH.build_css(scale=90))
        for bad in (100, 77, 0, -5, 1000, "120", None, True):
            self.assertEqual(TH.build_css(scale=bad), SNAP.read_text(), bad)

    def test_only_pt_scaled(self):
        css = TH.build_css(scale=140)
        self.assertEqual(re.findall(r"\d+px", css), re.findall(r"\d+px", SNAP.read_text()))
        self.assertEqual(len(re.findall(r"pt\b", css)), len(re.findall(r"pt\b", SNAP.read_text())))

    def test_preview_scaled(self):
        self.assertIn("font-size: 18.2pt", TH.preview_css({"theme": "dark", "roles": {}, "font_scale": 140}))


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class ColorDialogTest(GuiBase):
    def setUp(self):
        super().setUp()
        self._old = TH.active()["appearance"]

    def tearDown(self):
        G.apply_appearance(self._old)
        super().tearDown()

    def dialog(self, w=None, appearance=None):
        return G.ColorSettingsDialog(w, appearance or TH.default_appearance())

    def test_main_button(self):
        w = self.window()
        b = w.colors_btn
        self.assertTrue(b.get_style_context().has_class("evox-fn-aux"))
        self.assertEqual(b.get_label(), "Color settings")
        self.assertEqual(b.get_tooltip_text(), T.BTN_COLORS_TIP)
        self.assertTrue(b.get_can_focus())
        self.assertEqual(w.status_text(b), T.STATUS_COLORS)
        w.destroy()

    def test_initial_focus_back_and_esc(self):
        d = self.dialog()
        self.assertTrue(d.cancel_btn.has_focus() or d.get_focus() is d.cancel_btn)
        got = []
        d.connect("response", lambda _d, r: got.append(r))
        self.assertTrue(G.dialog_key(d, key(Gdk.KEY_Escape)))
        d.back_top.clicked()
        self.assertEqual(got, [Gtk.ResponseType.CANCEL, Gtk.ResponseType.CANCEL])
        self.assertIsNone(d.result)
        self.assertTrue(d.back_top.get_style_context().has_class("evox-cancel"))
        d.destroy()

    def test_no_safety_role_in_list(self):
        d = self.dialog()
        ids = []
        model = d.role_combo.get_model()
        for row in model:
            ids.append(row[1])
        self.assertEqual(ids, list(TH.ROLES))
        self.assertFalse(set(ids) & set(TH.SAFETY))
        d.destroy()

    def test_propose_ok_warn_reject(self):
        d = self.dialog()
        self.assertEqual(d.propose("verify", "#2a4f74"), "ok")
        self.assertEqual(d.draft["roles"]["verify"], "#2A4F74")
        warn = gray_for("#ffffff", 2.2, 2.9)
        self.assertEqual(d.propose("verify", warn), "warn")
        self.assertEqual(d.draft["roles"]["verify"], "#2A4F74")          # noch nicht übernommen
        self.assertTrue(d.use_btn.get_visible())
        self.assertTrue(d.use_anyway())
        self.assertEqual(d.draft["roles"]["verify"], warn)
        self.assertIn("verify", d.draft["accepted"])
        self.assertEqual(d.propose("verify", gray_for("#ffffff", 1.2, 1.9)), "bad")
        self.assertEqual(d.draft["roles"]["verify"], warn)
        self.assertIn("very hard to read", d.check_lbl.get_text())
        self.assertTrue(d.use_btn.get_visible())
        t = gray_for(TH.DARK["background"], 2.2, 2.9)
        self.assertEqual(d.propose("text", t), "warn")
        self.assertTrue(d.use_btn.get_visible())                          # 0.9.0: auch Text speicherbar
        self.assertTrue(d.use_anyway())
        self.assertEqual(d.draft["roles"]["text"], t)
        self.assertEqual(d.propose("danger", "#00ff00"), "reject")
        self.assertEqual(d.propose("verify", "#fff;}x{"), "reject")
        d.destroy()

    def test_reset_role_theme_and_theme_switch(self):
        d = self.dialog()
        d.role_combo.set_active_id("verify")
        d.propose("verify", "#2a4f74")
        d.propose("aux", "#3a3f64")
        d.reset_role()
        self.assertEqual(d.draft["roles"], {"aux": "#3A3F64"})
        self.assertEqual(G.rgba_hex(d.color_btn.get_rgba()), "#4A6F94")
        d.reset_theme()
        self.assertEqual(d.draft["roles"], {})
        d.propose("verify", "#2a4f74")
        d.theme_combo.set_active_id("light")
        self.assertEqual(d.draft, {"theme": "light", "roles": {}, "accepted": [], "font_scale": 100})
        self.assertEqual(G.rgba_hex(d.color_btn.get_rgba()), TH.LIGHT["verify"].upper())
        d.size_scale.set_value(120)
        self.assertEqual(d.draft["font_scale"], 120)
        d.destroy()

    def test_preview_provider_and_main_css_untouched(self):
        before = TH.active_css()
        d = self.dialog()
        self.assertIsNotNone(d._preview_prov)
        d.propose("disposable", "#00AA44")
        self.assertEqual(TH.active_css(), before)                         # Vorschau ändert das Haupt-CSS nicht
        self.assertTrue(d.el["btn_start_internet"].get_style_context().has_class("evox-start-disposable"))
        d.destroy()
        self.assertIsNone(d._preview_prov)

    def test_dialog_fits_workarea(self):
        d = self.dialog()
        self.assertLessEqual(d.fitted_height, G.workarea_height() - G.DIALOG_DECOR)
        d.destroy()

    def test_save_load_keeps_other_keys_and_applies_live(self):
        cfg = self.ev.s.config_file
        cfg.write_text(json.dumps({"purposes": ["EMAIL"], "host_reserve_mib": 4096}))
        w = self.window()
        res = {"theme": "light", "roles": {"verify": "#2A4F74"}, "accepted": [], "font_scale": 120}

        class FakeDlg:
            def __init__(self, *_a):
                self.result = res

            def run(self):
                return Gtk.ResponseType.OK

            def destroy(self):
                pass
        from tests.test_cycle import WATCH  # noqa: F401  (Zähler unten nur für CSS)
        loads = []
        orig = Gtk.CssProvider.load_from_data
        with mock.patch.object(G, "ColorSettingsDialog", FakeDlg), \
                mock.patch.object(Gtk.CssProvider, "load_from_data", lambda s, d: (loads.append(1), orig(s, d))[1]):
            w.show_colors()
        self.assertEqual(len(loads), 1)                                   # CSS genau einmal neu geladen
        data = json.loads(cfg.read_text())
        self.assertEqual(data["purposes"], ["EMAIL"])
        self.assertEqual(data["host_reserve_mib"], 4096)
        self.assertEqual(data["appearance"], res)
        self.assertEqual(oct(cfg.stat().st_mode & 0o777), "0o600")
        self.assertEqual(TH.active()["theme"], "light")
        self.assertIn("font-size: 15.6pt", TH.active_css())
        self.assertEqual(w.msg.get_text(), T.MSG_COLORS_SAVED)
        # gleiche Einstellung erneut anwenden: kein Neuladen
        loads.clear()
        with mock.patch.object(Gtk.CssProvider, "load_from_data", lambda s, d: (loads.append(1), orig(s, d))[1]):
            G.apply_appearance(res)
        self.assertEqual(loads, [])
        w.destroy()
        w2 = G.MainWindow(self.ev)                                        # neuer Start lädt die Einstellung
        self.assertEqual(w2.appearance["theme"], "light")
        self.assertEqual(w2.appearance["font_scale"], 120)
        w2.destroy()

    def test_broken_config_backed_up(self):
        cfg = self.ev.s.config_file
        cfg.write_text("{kaputt")
        w = self.window()
        self.assertEqual(w.appearance, TH.default_appearance())
        self.ev.s.save_option(TH.KEY, TH.default_appearance())
        self.assertTrue(list(cfg.parent.glob(cfg.name + ".broken-*")))
        w.destroy()

    def test_old_config_without_key(self):
        self.ev.s.config_file.write_text(json.dumps({"purposes": ["EMAIL"]}))
        w = self.window()
        self.assertEqual(w.appearance, TH.default_appearance())
        self.assertEqual(TH.active_css(), SNAP.read_text() if G.focus_env() is None else TH.active_css())
        w.destroy()

    def test_cancel_does_not_save(self):
        w = self.window()

        class FakeDlg:
            result = {"theme": "light", "roles": {}, "accepted": [], "font_scale": 140}

            def __init__(self, *_a):
                pass

            def run(self):
                return Gtk.ResponseType.CANCEL

            def destroy(self):
                pass
        with mock.patch.object(G, "ColorSettingsDialog", FakeDlg):
            w.show_colors()
        self.assertIsNone(self.ev.s.load_option(TH.KEY))
        self.assertEqual(TH.active()["theme"], "dark")
        w.destroy()

    def test_save_button_result(self):
        d = self.dialog()
        d.propose("verify", "#2a4f74")
        d.response(Gtk.ResponseType.OK)
        self.assertEqual(d.result["roles"], {"verify": "#2A4F74"})
        d.destroy()

    def test_focus_env_has_priority(self):
        with mock.patch.dict(os.environ, {G.FOCUS_ENV: "#FF00FF"}):
            G.apply_appearance({"roles": {"focus": "#00FFFF"}})
            self.assertEqual(TH.active()["focus"], "#FF00FF")
            self.assertIn("outline-color: #FF00FF;", TH.active_css())
        with mock.patch.dict(os.environ, {G.FOCUS_ENV: "#ff00ff;}x{"}):
            G.apply_appearance({"roles": {"focus": "#00FFFF"}})
            self.assertEqual(TH.active()["focus"], "#00FFFF")
        os.environ.pop(G.FOCUS_ENV, None)

    def test_light_base_switch_and_back(self):
        st = Gtk.Settings.get_default()
        before = (st.props.gtk_theme_name, st.props.gtk_application_prefer_dark_theme)
        G.apply_appearance({"theme": "light"})
        self.assertEqual(st.props.gtk_theme_name, "Adwaita")
        self.assertFalse(st.props.gtk_application_prefer_dark_theme)
        G.apply_appearance({"theme": "dark"})
        self.assertEqual((st.props.gtk_theme_name, st.props.gtk_application_prefer_dark_theme), before)

    def test_runtime_colors_follow_theme(self):
        G.apply_appearance({"theme": "light"})
        self.assertIn(TH.LIGHT["hint_mark_bg"], G.hint_markup())
        self.assertEqual(TH.role("cpu_bar"), TH.LIGHT["cpu_bar"])

    def test_large_font_layout(self):
        """140 %: Fenster bleibt bei gemerkter Größe, HOW-TO-Zeilen einzeilig mit Ellipsis, Mindesthöhe ≤ Arbeitsfläche."""
        G.apply_appearance({"font_scale": 140})
        w = self.window()
        w.show_all()
        pump(0.3)
        for b in w.howto_btns:
            self.assertEqual(b.get_child().get_ellipsize(), G.Pango.EllipsizeMode.END)
            self.assertTrue(b.get_child().get_single_line_mode())
        self.assertLessEqual(w.get_size_request()[1], G.workarea_height())
        mw, _nw = w.get_preferred_width()
        self.assertLessEqual(mw, 1400)
        w.destroy()


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class ThemeZeroCallsTest(GuiBase):
    counted = MonitorZeroCallsTest.counted

    def tearDown(self):
        G.apply_appearance(TH.default_appearance())
        super().tearDown()

    def test_unchanged_cycle_after_live_apply(self):
        w = self.window(raw(avail=2 * GIB_KIB, usable=GIB_KIB, cpu=10**9, nets=[(5, 6)], overlay=2**20))
        G.apply_appearance({"theme": "light", "font_scale": 120})
        w.colors = G.theme_colors(w)
        w.refresh()
        for _ in range(3):
            self.clock.t += 1
            w._apply_live([self.name], self.hv.domain_stats([self.name]))
        self.assertEqual(self.counted(w), {})
        self.assertEqual(self.counted(w, live=False), {})
        w.destroy()


if __name__ == "__main__":
    unittest.main()
