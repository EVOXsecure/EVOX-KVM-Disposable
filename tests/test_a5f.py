"""0.9.1 (A5f): Icon – SVGs wohlgeformt, Texte, Paketinhalt, Icon-Name."""
import re
import unittest
import xml.dom.minidom as minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "packaging" / "icons"


class IconTest(unittest.TestCase):
    def test_svg_wellformed_and_self_contained(self):
        for name in ("evoxd.svg", "evoxd-small.svg"):
            txt = (ICONS / name).read_text(encoding="utf-8")
            doc = minidom.parseString(txt.encode("utf-8"))
            self.assertEqual(doc.documentElement.getAttribute("viewBox"), "0 0 256 256")
            self.assertNotIn("<script", txt)
            self.assertNotIn("href", txt)
            self.assertEqual(re.findall(r"https?://[^\"']+", txt), ["http://www.w3.org/2000/svg"])

    def test_large_has_both_text_lines_with_fixed_width(self):
        doc = minidom.parse(str(ICONS / "evoxd.svg"))
        texts = [t for t in doc.getElementsByTagName("text")]
        self.assertTrue(texts)
        for t in texts:
            self.assertEqual(t.getAttribute("textLength"), "225")
        content = {t.firstChild.data for t in texts}
        self.assertEqual(content, {"EVOX KVM", "DISPOSABLE"})

    def test_small_has_no_text_and_no_hook(self):
        doc = minidom.parse(str(ICONS / "evoxd-small.svg"))
        self.assertEqual(doc.getElementsByTagName("text"), [])
        self.assertNotIn("-8,10 -2,16 9,4", (ICONS / "evoxd-small.svg").read_text())

    def test_packaged(self):
        b = (ROOT / "packaging" / "build-deb.sh").read_text()
        self.assertIn("packaging/icons/evoxd.svg", b)
        self.assertIn("hicolor/scalable/apps", b)

    def test_icon_name(self):
        from evoxd import gui
        self.assertEqual(gui.ICON_NAME, "evoxd")
        self.assertIn("Gtk.Window.set_default_icon_name(ICON_NAME)",
                      (ROOT / "src" / "evoxd" / "gui.py").read_text())


if __name__ == "__main__":
    unittest.main()
