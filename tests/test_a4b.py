"""0.9.0 (A4b): Kontrast nur warnen, Themes Tron Legacy/Cyberpunk, Theme-Datei Export/Import, Notbremse, 150 %-Höhe.
Nur Attrappen (FakeHypervisor, nospawn), kein echtes libvirt."""
import json
import os
import tempfile
import unittest
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import evoxd.gui as G
from evoxd import theme as TH
from tests.test_a3b import HAVE_DISPLAY, GuiBase
from tests.test_a4a import DANGER_RULES, gray_for


class ThemesTest(unittest.TestCase):
    def test_entries_and_readability(self):
        for key in ("tron", "cyberpunk"):
            self.assertIn(key, TH.THEMES)
            r = TH.THEMES[key]["roles"]
            self.assertEqual(set(r), set(TH.DARK))
            for a, b in TH.PAIRS:
                self.assertGreaterEqual(TH.contrast(r[a], r[b]), 4.5, (key, a, b))
            self.assertGreaterEqual(TH.contrast(r["focus"], r["background"]), 3.0, key)
            self.assertTrue(all(TH.valid_hex(v) for v in r.values()))
            self.assertEqual(TH.sanitize({"theme": key})["theme"], key)

    def test_safety_colors_fixed_in_new_themes(self):
        for key in ("tron", "cyberpunk"):
            css = TH.build_css(key, {}, scale=150)
            for rule in DANGER_RULES:
                self.assertIn(rule, css, key)
            self.assertIn("background-color: " + TH.THEMES[key]["roles"]["background"], css)


class WarnOnlyTest(unittest.TestCase):
    def test_no_contrast_rejection_anywhere(self):
        bg = TH.DARK["background"]
        for role in ("text", "verify", "title", "backup_text"):
            for lo, hi, lvl in ((1.0, 1.9, "bad"), (2.1, 2.9, "warn")):
                c = gray_for(TH.DARK["verify_text"] if role == "verify" else bg, lo, hi)
                res = TH.check_role("dark", {}, role, c)
                self.assertIn(res["level"], ("warn", "bad"), role)
                self.assertTrue(res["can_override"], role)
        for k in TH.SAFETY:
            self.assertEqual(TH.check_role("dark", {}, k, "#123456")["level"], "reject")

    def test_saved_bad_value_kept_only_when_accepted(self):
        c = gray_for("#ffffff", 1.2, 1.9)
        self.assertEqual(TH.sanitize({"roles": {"verify": c}})["roles"], {})
        self.assertEqual(TH.sanitize({"roles": {"verify": c}, "accepted": ["verify"]})["roles"], {"verify": c})


class ThemeFileTest(unittest.TestCase):
    def good(self, **kw):
        d = {"format": "evoxd-theme", "version": 1, "base": "tron", "roles": {"verify": "#2a4f74"}}
        d.update(kw)
        return json.dumps(d)

    def test_roundtrip(self):
        a = {"theme": "cyberpunk", "roles": {"verify": "#2A4F74", "heading": "#FFAA00"}, "accepted": [],
             "font_scale": 100}
        d = TH.import_theme(TH.export_theme(a))
        self.assertEqual((d["theme"], d["roles"]), ("cyberpunk", a["roles"]))

    def test_strict_validation(self):
        bad = [self.good(roles={"danger": "#ffffff"}), self.good(roles={"error": "#ffffff"}),
               self.good(roles={"nonsense": "#ffffff"}), self.good(roles={"verify": "red"}),
               self.good(roles={"verify": "#fff"}), self.good(roles={"verify": "#ffffff;}x{"}),
               self.good(roles={"verify": "#ffffffff"}), self.good(roles={"verify": 5}),
               self.good(base="evil"), self.good(extra="x"), self.good(format="other"), self.good(version=2),
               self.good(accepted=["text"]), self.good(roles=[]), "[]", "not json", "", "{" * 5000,
               b"\xff\xfe", " " * (TH.IMPORT_MAX_BYTES + 1)]
        for t in bad:
            with self.assertRaises(ValueError, msg=str(t)[:40]):
                TH.import_theme(t)

    def test_size_limit_bytes(self):
        with self.assertRaises(ValueError):
            TH.import_theme(self.good().encode() + b" " * TH.IMPORT_MAX_BYTES)

    def test_low_contrast_import_marked_accepted_not_refused(self):
        c = gray_for("#ffffff", 1.2, 1.9)
        d = TH.import_theme(self.good(base="dark", roles={"verify": c}))
        self.assertEqual(d["roles"], {"verify": c})
        self.assertEqual(d["accepted"], ["verify"])

    def test_never_css(self):
        css = TH.build_css("tron", TH.import_theme(self.good())["roles"])
        self.assertNotIn("}x{", css)


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class DialogFileTest(GuiBase):
    def dialog(self, a=None):
        d = G.ColorSettingsDialog(None, a or TH.default_appearance())
        self.addCleanup(d.destroy)
        return d

    def test_export_import_files(self):
        d = self.dialog()
        d.set_theme("tron")
        d.propose("verify", "#2a4f74")
        p = Path(self.tmp.name) / "t.json"
        self.assertTrue(d.export_to(p))
        d2 = self.dialog()
        self.assertTrue(d2.import_from(p))
        self.assertEqual((d2.draft["theme"], d2.draft["roles"]), ("tron", {"verify": "#2A4F74"}))
        self.assertEqual(d2.theme_combo.get_active_id(), "tron")

    def test_import_refused_changes_nothing(self):
        d = self.dialog()
        p = Path(self.tmp.name) / "evil.json"
        p.write_text(json.dumps({"format": "evoxd-theme", "version": 1, "base": "dark",
                                 "roles": {"danger": "#00ff00"}}))
        before = json.dumps(d.draft, sort_keys=True)
        self.assertFalse(d.import_from(p))
        self.assertEqual(json.dumps(d.draft, sort_keys=True), before)
        self.assertIn("refused", d.check_lbl.get_text())
        self.assertFalse(d.import_from(Path(self.tmp.name) / "missing.json"))

    def test_reset_buttons_always_visible(self):
        d = self.dialog()
        d.show_all()
        d.propose("verify", gray_for("#ffffff", 1.2, 1.9))
        for b in (d.reset_role_btn, d.reset_theme_btn):
            self.assertTrue(b.get_visible())
        d.use_anyway()
        d.reset_theme()
        self.assertEqual(d.draft["roles"], {})

    def test_bad_color_can_be_saved(self):
        d = self.dialog()
        c = gray_for("#ffffff", 1.2, 1.9)
        self.assertEqual(d.propose("verify", c), "bad")
        self.assertIn("✖", d.check_lbl.get_text())
        self.assertTrue(d.use_anyway())
        d.response(Gtk.ResponseType.OK)
        self.assertEqual(d.result["roles"], {"verify": c})
        self.assertEqual(d.result["accepted"], ["verify"])


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class EmergencyResetTest(GuiBase):
    def test_reset_colors_backs_up_and_resets(self):
        self.ev.s.save_option("appearance", {"theme": "tron", "roles": {"verify": "#2A4F74"}, "font_scale": 150})
        self.ev.s.save_option("host_reserve_mib", 1234)
        path = self.ev.s.config_file
        self.assertTrue(G.reset_colors(self.ev.s))
        backups = list(path.parent.glob(path.name + ".colors-*"))
        self.assertEqual(len(backups), 1)
        self.assertIn("tron", backups[0].read_text())
        data = json.loads(path.read_text())
        self.assertEqual(data["appearance"], TH.default_appearance())
        self.assertEqual(data["host_reserve_mib"], 1234)

    def test_reset_without_config(self):
        self.assertTrue(G.reset_colors(self.ev.s))


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class Height150Test(GuiBase):
    def test_main_window_and_monitor_fit_workarea_at_150(self):
        self.ev.s.save_option("appearance", {"font_scale": 150})
        try:
            w = self.window()
            w.show_all()
            m = G.MonitorWindow(G.COLORS_DARK, None, False)
            m.show_all()
            for _ in range(40):
                Gtk.main_iteration_do(False)
            self.assertEqual(TH.active()["scale"], 150)
            self.assertLessEqual(w.get_preferred_size()[0].height, G.workarea_height())
            self.assertLessEqual(w.get_allocated_height(), G.workarea_height())
            self.assertLessEqual(m.get_preferred_size()[0].height, G.workarea_height())
            self.assertLessEqual(m.get_preferred_size()[0].width, 1300)
            m.destroy()
            w.destroy()
        finally:
            G.apply_appearance(TH.default_appearance())

    def test_compact_follows_scale(self):
        try:
            G.apply_appearance({"font_scale": 100})
            self.assertEqual(G.howto_compact(), G.workarea_height() < G.HOWTO_SMALL_WORKAREA)
            G.apply_appearance({"font_scale": 130})
            self.assertTrue(G.howto_compact())
            self.assertIn("padding-top: 1px", TH.active_css())
            G.apply_appearance({"font_scale": 120})
            self.assertNotIn("padding-top: 1px", TH.active_css())
        finally:
            G.apply_appearance(TH.default_appearance())


if __name__ == "__main__":
    unittest.main()
