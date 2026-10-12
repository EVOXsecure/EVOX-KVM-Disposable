"""A7b (0.10.3): Full Manual EN+DE, Developer Doc. Nur Dateiprüfungen und Attrappen, kein Browser, kein Netz."""
import importlib.util
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

from evoxd import cli, manual
from tests.test_a3b import HAVE_DISPLAY, GuiBase

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "docs" / "manual"
_spec = importlib.util.spec_from_file_location("bm", ROOT / "tools" / "build_manual.py")
bm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bm)

FILES = ("full-manual.en", "full-manual.de", "developer-doc.en")
REQUIRED = ("intro", "threat", "compare", "install", "setupcheck", "tabs", "howto", "monitor", "colors", "keys", "docs",
            "arch", "h1", "risks", "checklists", "scenarios", "notprotected", "privacy", "emergency", "upkeep",
            "glossary", "trouble", "faq", "cli", "update", "changelog", "roadmap", "license")
VOID = {"meta", "input", "br", "img", "hr", "link"}


def text(name, ext="html"):
    return (MAN / f"{name}.{ext}").read_text(encoding="utf-8")


class Checker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.errors, self.ids, self.h3 = [], [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag == "h3":
            self.h3 += 1
        for k, v in attrs:
            if k == "id":
                self.ids.append(v)
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack[-3:]})")
        else:
            self.stack.pop()


def check(name):
    c = Checker()
    c.feed(text(name))
    c.close()
    return c


class DocFilesTest(unittest.TestCase):
    def test_up_to_date(self):
        for n in FILES:
            stem, lang = n.rsplit(".", 1)
            self.assertEqual(bm.convert(text(n, "md"), lang, stem), text(n), n)

    def test_well_formed(self):
        for n in FILES + ("quick-guide.en", "quick-guide.de"):
            c = check(n)
            self.assertEqual(c.errors, [], n)
            self.assertEqual(c.stack, [], n)

    def test_no_external_urls(self):
        for n in FILES:
            t = text(n).replace('xmlns="http://www.w3.org/2000/svg"', "")
            self.assertNotRegex(t, r"(?i)(https?:)?//[a-z0-9]", n)
            self.assertNotRegex(t, r"(?i)\b(src|href)\s*=\s*[\"'](?!#|full-manual|quick-guide|developer)", n)
            self.assertNotIn("<script src", t)

    def test_en_de_same_structure(self):
        en, de = text("full-manual.en", "md"), text("full-manual.de", "md")
        sec = lambda t: re.findall(r"^## .*\{#(\w+)\}$", t, re.M)       # noqa: E731
        self.assertEqual(sec(en), sec(de))
        self.assertEqual(len(re.findall(r"^### ", en, re.M)), len(re.findall(r"^### ", de, re.M)))
        self.assertEqual(re.findall(r"\{\{svg:\w+\}\}", en), re.findall(r"\{\{svg:\w+\}\}", de))
        for pat in (r"^\|.*\|$", r"^\d+\. ", r"^- "):
            self.assertEqual(len(re.findall(pat, en, re.M)), len(re.findall(pat, de, re.M)), pat)
        he, hd = text("full-manual.en"), text("full-manual.de")
        self.assertEqual(check("full-manual.en").ids, check("full-manual.de").ids)
        self.assertEqual(he.count("<svg"), hd.count("<svg"))

    def test_required_chapters(self):
        ids = check("full-manual.en").ids
        for a in REQUIRED:
            self.assertIn(a, ids)
        self.assertEqual([i for i in ids if i in REQUIRED], list(REQUIRED))
        for a in REQUIRED:
            self.assertIn(f'href="#{a}"', text("full-manual.de"))

    def test_graphics_present(self):
        h = text("full-manual.en")
        for t in ("Risk matrix", "Theme colors", "Security levels", "Flow 1", "Data flow"):
            self.assertIn(t, h)
        self.assertIn("Risiko-Matrix", text("full-manual.de"))

    def test_cli_reference_has_all_subcommands(self):
        sub = [a for a in cli.build_parser()._subparsers._group_actions[0].choices]
        self.assertGreaterEqual(len(sub), 11)
        for n in ("full-manual.en", "full-manual.de"):
            md = text(n, "md")
            chap = md[md.index("{#cli}"):md.index("{#update}")]
            for s in sub:
                self.assertIn(f"`evoxd {s}", chap, (n, s))

    def test_dev_doc_english_only_no_switch(self):
        self.assertFalse((MAN / "developer-doc.de.md").exists())
        self.assertNotIn('class="lang"', text("developer-doc.en"))
        self.assertIn('class="lang"', text("full-manual.en"))
        for a in ("modules", "arch", "files", "tests", "release", "rules", "theme", "catalog", "backup"):
            self.assertIn(a, check("developer-doc.en").ids)

    def test_style_features(self):
        h = text("full-manual.en")
        for part in ('id="q"', 'id="lt"', 'class="logo"', 'class="toc"', 'name="evoxd-version"', "@media print", "EVOX KVM DISPOSABLE 1."):
            self.assertIn(part, h)
        self.assertIn('<main class="long">', h)

    def test_in_package_list(self):
        script = (ROOT / "packaging" / "build-deb.sh").read_text(encoding="utf-8")
        self.assertIn("docs/manual/*.??.html", script)
        self.assertIn("usr/share/doc/evoxd/manual", script)
        for n in FILES:
            self.assertTrue((MAN / f"{n}.html").is_file() and (MAN / f"{n}.md").is_file())


class ManualOpenTest(unittest.TestCase):
    def test_cards_available(self):
        for lang in ("en", "de"):
            self.assertIsNotNone(manual.doc_file("quick", lang, (MAN,)))
            self.assertIsNotNone(manual.doc_file("full", lang, (MAN,)))
        self.assertIsNotNone(manual.doc_file("dev", "en", (MAN,)))
        self.assertIsNone(manual.doc_file("dev", "de", (MAN,)))      # nur Englisch

    def test_context_targets(self):
        self.assertEqual(manual.CONTEXT, {"setup": ("full", "setupcheck"), "colors": ("full", "colors")})
        ids = {l: check(f"full-manual.{l}").ids for l in ("en", "de")}
        for key, anchor in manual.CONTEXT.values():
            for lang in ("en", "de"):
                self.assertIn(anchor, ids[lang])

    def test_open_context_picks_language(self):
        pop = mock.Mock()
        w = lambda n: "/usr/bin/xdg-open"                                  # noqa: E731
        manual.open_context("colors", "de", dirs=(MAN,), which=w, popen=pop)
        self.assertTrue(pop.call_args[0][0][1].endswith("full-manual.de.html#colors"))
        manual.open_context("setup", "en", dirs=(MAN,), which=w, popen=pop)
        self.assertTrue(pop.call_args[0][0][1].endswith("full-manual.en.html#setupcheck"))
        with mock.patch.dict("os.environ", {"LC_ALL": "de_DE.UTF-8"}):
            manual.open_context("setup", dirs=(MAN,), which=w, popen=pop)
        self.assertTrue(pop.call_args[0][0][1].endswith("full-manual.de.html#setupcheck"))


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class CardsGuiTest(GuiBase):
    def test_cards_active(self):
        import evoxd.gui as G
        d = G.DocsDialog(None, dirs=(MAN,), opener=mock.Mock(), lang="en")
        self.addCleanup(d.destroy)
        for k in ("quick", "full", "dev"):
            self.assertTrue(d.cards[k][0].get_sensitive(), k)
        d.lang_btns["de"].set_active(True)
        self.assertTrue(d.cards["full"][0].get_sensitive())
        self.assertFalse(d.cards["dev"][0].get_sensitive())


if __name__ == "__main__":
    unittest.main()
