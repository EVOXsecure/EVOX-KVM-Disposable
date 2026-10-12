"""A7c Teil 3/4 (0.10.4): Easy Guide EN+DE und Karte im Documentation-Dialog. Nur Dateiprüfungen / Attrappen, kein Browser, kein Netz."""
import re
import unittest
from pathlib import Path
from unittest import mock

from evoxd import manual, texts as T
from tests.test_a3b import HAVE_DISPLAY, GuiBase
from tests.test_a7c import MAN, Tags, bm, html_of, print_css

EASY = ("easy-guide.en", "easy-guide.de")


class EasyGuideTests(unittest.TestCase):
    def test_files_exist_and_up_to_date(self):
        for n in EASY:
            stem, lang = n.rsplit(".", 1)
            self.assertEqual(bm.convert((MAN / f"{n}.md").read_text(encoding="utf-8"), lang, stem), html_of(n), n)

    def test_well_formed_no_external(self):
        for n in EASY:
            h = html_of(n)
            p = Tags()
            p.feed(h)
            self.assertEqual((p.bad, p.stack), ([], []), n)
            self.assertFalse(re.search(r"(?:src|href|url\()\s*=?\s*[\"']?(?:https?:)?//", h), n)
            self.assertNotIn("<img", h)
            self.assertNotIn("<link", h)

    def test_same_structure_and_anchors(self):
        ids = [re.findall(r'<section id="([^"]+)"', html_of(n)) for n in EASY]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[0], ["what", "steps", "buttons", "beforeafter", "safe", "rules", "honest", "check"])
        tags = [re.findall(r"<(svg|ol|li|section)\b", html_of(n)) for n in EASY]
        self.assertEqual(tags[0], tags[1])

    def test_content(self):
        h = [html_of(n) for n in EASY]
        for x in h:
            self.assertEqual(x.count("<svg") - x.count('class="logo"'), 4)       # 4 eigene Inline-SVGs (+ Logo)
            self.assertEqual(len(re.findall(r"<ol><li>.*?</ol>", x, re.S)), 1)
            self.assertEqual(x.count("<li>"), 3)                                # drei Regeln
            for b in ("START: INTERNET", "START: OFFLINE", "Stop and erase"):
                self.assertIn(b, x)
        for w in ("Choose", "Start", "Use", "Erase"):
            self.assertIn(f">{w}</text>", h[0])
        for w in ("Wählen", "Starten", "Benutzen", "Löschen"):
            self.assertIn(f">{w}</text>", h[1])
        self.assertIn("Everything that happens in the box disappears with it.", h[0])
        self.assertIn("Alles, was in der Kiste passiert, verschwindet mit ihr.", h[1])
        self.assertIn("does not protect you from your own mistakes", h[0])
        self.assertIn("nicht vor eigenen Fehlern", h[1])
        for x in h:                                                             # kein Versprechen absoluter Sicherheit
            self.assertNotRegex(x[x.index("<main"):].lower(), r"100 ?%|absolute|guarantee|garantier")

    def test_print_one_page_setup(self):
        for n in EASY:
            h = html_of(n)
            self.assertIn("@page{size:A4;margin:12mm}", h)
            css = print_css(h).replace(" ", "")
            self.assertNotIn("overflow:hidden", css)
            self.assertIn("main.easy{font-size:12pt}", css)
            self.assertIn("break-inside:avoid", css)
            self.assertIn('<main class="easy">', h)

    def test_manual_registry(self):
        self.assertEqual(list(manual.DOCS)[0], "easy")
        for lang in ("en", "de"):
            self.assertEqual(manual.doc_file("easy", lang, (MAN,)).name, f"easy-guide.{lang}.html")
        self.assertEqual(manual.doc_file("easy", "en", (MAN / "none",)), None)

    def test_texts_and_package(self):
        self.assertEqual(list(T.DOCS_CARDS)[0], "easy")
        self.assertEqual(T.DOCS_CARDS["easy"][0], "Easy Guide")
        self.assertIn("Easy Guide", T.BTN_DOCS_TIP)
        deb = (Path(__file__).resolve().parent.parent / "packaging" / "build-deb.sh").read_text(encoding="utf-8")
        self.assertIn("docs/manual/*.??.html", deb)                             # Glob nimmt easy-guide.* mit
        self.assertIn("usr/share/doc/evoxd/manual", deb)


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class EasyCardTests(GuiBase):
    def test_card_first_green_active(self):
        import evoxd.gui as G
        for lang in ("en", "de"):
            d = G.DocsDialog(None, dirs=(MAN,), opener=mock.Mock(), lang=lang)
            self.addCleanup(d.destroy)
            self.assertEqual(list(d.cards)[0], "easy")
            btn, state = d.cards["easy"]
            self.assertTrue(btn.get_sensitive())
            self.assertIn("evox-doc-easy", btn.get_style_context().list_classes())
            self.assertEqual(state.get_text(), "")
        self.assertIn(G.NEON_GREEN.lower(), G.theme.doc_card_css(G.theme.DARK).lower())

    def test_open_uses_selected_language(self):
        import evoxd.gui as G
        op = mock.Mock()
        d = G.DocsDialog(None, dirs=(MAN,), opener=op, lang="de")
        self.addCleanup(d.destroy)
        d.open("easy")
        op.assert_called_once_with("easy", "de", dirs=(MAN,))

    def test_missing_grey(self):
        import evoxd.gui as G
        d = G.DocsDialog(None, dirs=(MAN / "none",), opener=mock.Mock(), lang="en")
        self.addCleanup(d.destroy)
        self.assertFalse(d.cards["easy"][0].get_sensitive())
        self.assertIn("evox-doc-off", d.cards["easy"][0].get_style_context().list_classes())


if __name__ == "__main__":
    unittest.main()
