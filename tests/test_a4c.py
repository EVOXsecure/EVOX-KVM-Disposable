"""0.9.2 (A4c): sieben neue Vorauswahl-Themes – vollständig, lesbar, Sicherheitsfarben fest, Export/Import."""
import json
import unittest

from evoxd import theme as TH
from tests.test_a4a import DANGER_RULES

NEW = ("hicontrast", "nord", "solarized", "dracula", "synthwave", "matrix", "amber")
ORDER = ["dark", "light", "hicontrast", "nord", "solarized", "dracula", "tron", "cyberpunk",
         "synthwave", "matrix", "amber"]


class NewThemesTest(unittest.TestCase):
    def test_eleven_themes_in_order(self):
        self.assertEqual(list(TH.THEMES), ORDER)
        self.assertEqual(len({t["label"] for t in TH.THEMES.values()}), 11)

    def test_complete_and_valid(self):
        for key in NEW:
            r = TH.THEMES[key]["roles"]
            self.assertEqual(set(r), set(TH.DARK), key)
            self.assertTrue(all(TH.valid_hex(v) for v in r.values()), key)
            self.assertEqual(TH.THEMES[key]["base"], "dark")

    def test_contrast(self):
        for key in NEW:
            r = TH.THEMES[key]["roles"]
            need = 7.0 if key == "hicontrast" else 4.5
            for a, b in TH.PAIRS:
                self.assertGreaterEqual(TH.contrast(r[a], r[b]), need, (key, a, b))
            self.assertGreaterEqual(TH.contrast(r["focus"], r["background"]), 3.0, key)

    def test_focus_distinct(self):
        for key in NEW:
            r = TH.THEMES[key]["roles"]
            self.assertEqual(TH.focus_clash(r), [], key)
            for k in TH.BUTTON_FILLS + ("sel_amber", "sel_teal", "sel_green"):
                self.assertNotEqual(r["focus"].upper(), r[k].upper(), (key, k))
                self.assertGreaterEqual(TH.contrast(r["focus"], r[k]), 1.5, (key, k))

    def test_safety_fixed_and_red(self):
        for key in NEW:
            eff = TH.effective(key, {role: "#123456" for role in TH.SAFETY})
            for role, val in TH.SAFETY.items():
                self.assertEqual(eff[role], val, (key, role))
            css = TH.build_css(key, {}, scale=100)
            for rule in DANGER_RULES:
                self.assertIn(rule, css, key)
            red = TH.THEMES[key]["roles"]["exit"]
            self.assertGreater(int(red[1:3], 16), int(red[3:5], 16) * 2, key)

    def test_dark_unchanged(self):
        self.assertEqual(TH.THEMES["dark"]["roles"], TH.DARK)
        self.assertEqual(TH.THEMES["dark"]["base"], "system")
        self.assertEqual(TH.DARK["background"], "#242424")
        self.assertEqual(TH.DARK["focus"], "#C6FF00")

    def test_export_import_roundtrip(self):
        for key in ORDER:
            ap = {"theme": key, "roles": {"verify": "#2A4F74"}, "accepted": [], "font_scale": 100}
            d = TH.import_theme(TH.export_theme(ap))
            self.assertEqual((d["theme"], d["roles"]), (key, {"verify": "#2A4F74"}), key)
            self.assertEqual(TH.sanitize({"theme": key})["theme"], key)
            json.loads(TH.export_theme(ap))


if __name__ == "__main__":
    unittest.main()
