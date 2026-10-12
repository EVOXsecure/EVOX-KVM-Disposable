"""0.6.18: Fokusfarbe Limette #C6FF00, Umgebungsvariable EVOXD_FOCUS_COLOR (nur Darstellung). Sichtbarkeit am Host [U] (G31)."""
import os
import subprocess
import sys
import unittest

import evoxd.gui as G

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


class FocusColorTest(unittest.TestCase):
    def test_default_and_single_value(self):
        self.assertEqual(G.FOCUS_DEFAULT, "#C6FF00")
        self.assertEqual(G.CSS.count("#C6FF00"), G.FOCUS_CSS.count("#C6FF00"))
        self.assertNotIn("#C04BFF", G.CSS.upper())
        self.assertEqual(G.FOCUS_INNER, "#0A0A0F")
        self.assertIn("inset", G.FOCUS_CSS)
        self.assertIn(f"{G.FOCUS_GLOW_PX}px", G.FOCUS_CSS)

    def test_env_valid(self):
        for v in ("#FFFFFF", "#9FEFFF", "#abcdef"):
            self.assertEqual(G._focus_color({G.FOCUS_ENV: v}), v)

    def test_env_invalid_ignored(self):
        for v in ("", "red", "#GGG", "#FFF", "FFFFFF", "#GGGGGG", "#fff;}x{", "#FFFFFF;}x{", "#FFFFFF\n", " #FFFFFF",
                  "#FFFFFFF", "url(x)"):
            self.assertEqual(G._focus_color({G.FOCUS_ENV: v}), "#C6FF00", repr(v))
        self.assertEqual(G._focus_color({}), "#C6FF00")

    def _css_with_env(self, v):
        env = dict(os.environ, PYTHONPATH=SRC)
        env[G.FOCUS_ENV] = v
        r = subprocess.run([sys.executable, "-c", "import evoxd.gui as G; print(G.FOCUS_COLOR); print('}x{' in G.CSS)"],
                           env=env, capture_output=True, text=True, timeout=30)
        return r.stdout.split()

    def test_env_at_start(self):
        self.assertEqual(self._css_with_env("#9FEFFF"), ["#9FEFFF", "False"])
        self.assertEqual(self._css_with_env("#fff;}x{"), ["#C6FF00", "False"])

    def test_contrast_documented_values(self):
        self.assertGreaterEqual(ratio("#C6FF00", G.FOCUS_INNER), 10)
        for bg in (G.TAB_DISPOSABLE_COLOR, G.TITLE_COLOR, G.MODE_OFFLINE, G.TAB_TEMPLATE_COLOR, G.VAULT_GOLD,
                   G.SELECT_AMBER, G.HOWTO_ORANGE, G.MODE_INTERNET):
            self.assertGreaterEqual(ratio(G.FOCUS_INNER, bg), 3.0, bg)       # Trennung trägt der dunkle Innenrand
        self.assertNotEqual(G.FOCUS_DEFAULT.upper(), G.MODE_INTERNET.upper())


if __name__ == "__main__":
    unittest.main()
