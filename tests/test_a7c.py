"""A7c (0.10.4): Druckränder und Hinweise im Handbuch. Nur Dateiprüfungen, kein Browser, kein Netz."""
import importlib.util
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "docs" / "manual"
_spec = importlib.util.spec_from_file_location("bm", ROOT / "tools" / "build_manual.py")
bm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bm)

PAIRS = (("quick-guide", "en", "de"), ("full-manual", "en", "de"))
ALL = ("quick-guide.en", "quick-guide.de", "full-manual.en", "full-manual.de", "developer-doc.en")


def html_of(n):
    return (MAN / f"{n}.html").read_text(encoding="utf-8")


def print_css(h):
    return h[h.index("@media print"):h.index("</style>")]


class Tags(HTMLParser):
    VOID = {"meta", "input", "br", "img", "hr", "link"}

    def __init__(self):
        super().__init__()
        self.stack, self.bad = [], []

    def handle_starttag(self, t, a):
        if t not in self.VOID:
            self.stack.append(t)

    def handle_endtag(self, t):
        if t in self.VOID:
            return
        if not self.stack or self.stack.pop() != t:
            self.bad.append(t)


class PrintTests(unittest.TestCase):
    def test_page_margin(self):
        for n in ALL:
            m = re.search(r"@page\{size:A4;margin:(\d+)mm\}", html_of(n))
            self.assertTrue(m, n)
            self.assertEqual(int(m.group(1)), 12 if n.startswith("quick") else 18, n)

    def test_no_overflow_hidden_in_print(self):
        for n in ALL:
            css = print_css(html_of(n)).replace(" ", "")
            self.assertNotIn("overflow:hidden", css, n)
            self.assertIn("main{width:auto;max-width:100%", css, n)

    def test_break_rules(self):
        for n in ALL:
            css = print_css(html_of(n)).replace(" ", "")
            for r in ("break-before:page", "break-after:avoid", "pre-wrap", "svg,tr,pre.cmd"):
                self.assertIn(r, css, (n, r))

    def test_builder_css_has_no_overflow_hidden(self):
        self.assertNotIn("overflow:hidden", bm.CSS.replace(" ", ""))


class HintTests(unittest.TestCase):
    def test_same_chapters_and_anchors(self):
        for stem, a, b in PAIRS:
            ids = [re.findall(r'<section id="([^"]+)"', html_of(f"{stem}.{x}")) for x in (a, b)]
            self.assertEqual(ids[0], ids[1], stem)

    def test_hint_texts(self):
        for n in ALL[:4]:
            t = (MAN / f"{n}.md").read_text(encoding="utf-8")
            self.assertIn("Network lock: active", t, n)
            self.assertIn("Exitcode 2" if n.endswith("de") else "exit code 2", t, n)
            self.assertEqual(t.count("`evoxd reconcile`:"), 1, n)
        for n in ("quick-guide.en", "full-manual.en"):
            self.assertIn("Normally you do not need these. The GUI does it for you.", (MAN / f"{n}.md").read_text(encoding="utf-8"))
        for n in ("quick-guide.de", "full-manual.de"):
            self.assertIn("Normalerweise brauchst du diese nicht.", (MAN / f"{n}.md").read_text(encoding="utf-8"))

    def test_checklist_reconcile_only_after_crash(self):
        self.assertIn("`evoxd reconcile` only after a crash", (MAN / "quick-guide.en.md").read_text(encoding="utf-8"))
        self.assertIn("`evoxd reconcile` nur bei Absturz", (MAN / "quick-guide.de.md").read_text(encoding="utf-8"))

    def test_well_formed_no_external_urls(self):
        for n in ALL:
            h = html_of(n)
            p = Tags()
            p.feed(h)
            self.assertEqual((p.bad, p.stack), ([], []), n)
            self.assertFalse(re.search(r"(?:src|href|url\()\s*=?\s*[\"']?(?:https?:)?//", h), n)

    def test_html_up_to_date(self):
        for n in ALL:
            stem, lang = n.rsplit(".", 1)
            self.assertEqual(bm.convert((MAN / f"{n}.md").read_text(encoding="utf-8"), lang, stem), html_of(n), n)


if __name__ == "__main__":
    unittest.main()
