"""A7a (0.10.1): Quick Guide EN/DE – HTML, Help-Knopf, Paketinhalt. Attrappen, nospawn, kein Browser."""
import re
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

from evoxd import manual
from evoxd import texts as T
from tests.nospawn import NoSpawnMixin

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "docs" / "manual"
VOID = {"meta", "br", "hr", "img", "input", "link", "line", "rect", "path", "col"}


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.errors, self.tags, self.attrs = [], [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs += attrs
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs += attrs

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack.pop() != tag:
            self.errors.append(tag)


def parse(lang):
    txt = (MAN / f"quick-guide.{lang}.html").read_text(encoding="utf-8")
    p = Tags()
    p.feed(txt)
    return txt, p


class HtmlTest(unittest.TestCase):
    def test_well_formed(self):
        for lang in ("en", "de"):
            _t, p = parse(lang)
            self.assertEqual(p.errors, [], lang)
            self.assertEqual(p.stack, [], lang)

    def test_content(self):
        for lang in ("en", "de"):
            txt, _p = parse(lang)
            for w in ("VAULT", "TEMPLATE", "DISPOSABLE", "START", "INTERNET", "OFFLINE", "Correct use and risks" if lang == "en" else "Richtig benutzen",
                      "Stop and erase", "evoxd reconcile", "libvirt", "X11", "Qubes OS", "@media print"):
                self.assertIn(w, txt, (lang, w))
            self.assertEqual(txt.count("<svg"), 5)        # Qube-Icon + 4 Grafiken

    def test_same_section_count(self):
        n = {lang: len(re.findall(r"^## ", (MAN / f"quick-guide.{lang}.md").read_text(encoding="utf-8"), re.M)) for lang in ("en", "de")}
        self.assertEqual(n["en"], n["de"])
        self.assertEqual(parse("en")[1].tags.count("section"), parse("de")[1].tags.count("section"))
        self.assertEqual(parse("en")[1].tags.count("svg"), parse("de")[1].tags.count("svg"))

    def test_no_external_resources_or_scripts(self):
        for lang in ("en", "de"):
            txt, p = parse(lang)
            self.assertNotIn("iframe", p.tags)
            self.assertNotRegex(txt, r"https?://(?!www\.w3\.org/2000/svg)")
            self.assertNotRegex(txt.lower(), r"\bon\w+=|src=|@import|url\((?!#)|fetch\(|xmlhttp|import\(")
            self.assertEqual(p.tags.count("script"), 1)
            for k, v in p.attrs:
                if k == "href":
                    self.assertRegex(v, r"^(#[\w-]+|quick-guide\.(en|de)\.html)$")

    def test_html_matches_source(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("bm", ROOT / "tools" / "build_manual.py")
        bm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bm)
        for lang in ("en", "de"):
            md = (MAN / f"quick-guide.{lang}.md").read_text(encoding="utf-8")
            self.assertEqual(bm.convert(md, lang), (MAN / f"quick-guide.{lang}.html").read_text(encoding="utf-8"))

    def test_package_contains_manual(self):
        s = (ROOT / "packaging" / "build-deb.sh").read_text()
        self.assertIn("usr/share/doc/evoxd/manual", s)
        self.assertIn("*.??.html", s)


class ManualTest(NoSpawnMixin, unittest.TestCase):
    def test_language_choice(self):
        self.assertTrue(manual.is_german({"LANG": "de_DE.UTF-8"}))
        self.assertFalse(manual.is_german({"LANG": "en_US.UTF-8"}))
        self.assertFalse(manual.is_german({"LC_ALL": "C.UTF-8", "LANG": "de_DE.UTF-8"}))
        self.assertFalse(manual.is_german({}))

    def test_path_fallback_to_project(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(manual.guide_path(True, (Path(t) / "none", MAN)), MAN / "quick-guide.de.html")
            self.assertEqual(manual.guide_path(False, (MAN,)), MAN / "quick-guide.en.html")
            Path(t, "quick-guide.en.html").write_text("x")
            self.assertEqual(manual.guide_path(False, (Path(t), MAN)), Path(t) / "quick-guide.en.html")
            with self.assertRaises(Exception):
                manual.guide_path(False, (Path(t) / "none",))

    def test_open_only_local_file_argument_list(self):
        pop = mock.Mock()
        manual.open_guide(True, (MAN,), which=lambda n: "/usr/bin/xdg-open", popen=pop)
        args = pop.call_args[0][0]
        self.assertEqual(args, ["/usr/bin/xdg-open", str(MAN / "quick-guide.de.html")])
        self.assertNotIn("shell", pop.call_args[1])
        self.assertFalse(str(args[1]).startswith("http"))

    def test_missing_xdg_open(self):
        with self.assertRaises(Exception):
            manual.open_guide(False, (MAN,), which=lambda n: None, popen=mock.Mock())

    def test_texts_english(self):
        self.assertEqual(T.BTN_DOCS, "Documentation")


if __name__ == "__main__":
    unittest.main()
