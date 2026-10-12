"""A7a2 (0.10.2): Documentation-Dialog, Doku-Stil, Kontext-Knopf. Attrappen, nospawn, kein Browser."""
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import evoxd
from evoxd import manual, theme
from evoxd import texts as T
from tests.nospawn import NoSpawnMixin
from tests.test_a3b import HAVE_DISPLAY, GuiBase

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "docs" / "manual"
_spec = importlib.util.spec_from_file_location("bm", ROOT / "tools" / "build_manual.py")
bm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bm)


def html_of(lang):
    return (MAN / f"quick-guide.{lang}.html").read_text(encoding="utf-8")


class DocStyleTest(unittest.TestCase):
    def test_up_to_date_and_version(self):
        for lang in ("en", "de"):
            md = (MAN / f"quick-guide.{lang}.md").read_text(encoding="utf-8")
            self.assertEqual(bm.convert(md, lang, "quick-guide"), html_of(lang))
            self.assertIn(f'<meta name="evoxd-version" content="{evoxd.__version__}">', html_of(lang))
            self.assertIn(f"EVOX KVM DISPOSABLE {evoxd.__version__}", html_of(lang))

    def test_page_functions(self):
        for lang, other in (("en", "de"), ("de", "en")):
            t = html_of(lang)
            self.assertIn(f'href="quick-guide.{other}.html"', t)          # Sprachumschalter
            self.assertIn('class="tg"', t)                                 # Dark/Light (CSS-only)
            self.assertIn('id="q"', t)                                     # lokale Suche
            self.assertIn('<nav class="toc"', t)
            for a in ("what", "steps", "startstop", "netlock", "levels", "keys", "risks", "help"):
                self.assertIn(f'href="#{a}"', t)
                self.assertIn(f'id="{a}"', t)
            self.assertIn("EVOX", re.search(r'<svg class="logo".*?</svg>', t, re.S).group(0))
            self.assertIn("@media print", t)
            self.assertIn("Close this tab to return to EVOX" if lang == "en" else "Schließe diesen Tab", t)

    def test_contrast_palettes(self):
        for name, p in bm.PAL.items():
            for fg in ("fg", "mute", "title", "h_a", "h_b", "code", "link"):
                for bg in ("bg", "panel"):
                    self.assertGreaterEqual(theme.contrast(p[fg], p[bg]), 4.5, (name, fg, bg))
        self.assertEqual(bm.PAL["dark"]["bg"], "#000000")
        for fg in (bm.C["fg"], bm.C["mute"], "#ff8a8a"):
            self.assertGreaterEqual(theme.contrast(fg, bm.C["bg"]), 4.5, fg)

    def test_print_is_light(self):
        t = html_of("en")
        self.assertRegex(t, r"(?s)@media print\{.*?--bg:#ffffff")

    def test_h1_note_replaced(self):
        for lang in ("en", "de"):
            t = html_of(lang)
            self.assertNotIn("H1) is still open", t)
            self.assertNotIn("steht noch aus", t)
            self.assertIn("H1", t)
            for w in ("Quad9", "IPv6", "netcheck", "multicast", "broadcast"):
                self.assertIn(w, t.replace("Multicast", "multicast").replace("Broadcast", "broadcast"))

    def test_code_block_and_index_template(self):
        out = bm.convert("# T\n\n## A {#a}\nUse **evoxd reconcile** now.\n```\nevoxd reconcile\n```\n{{index}}\n", "en", "x", "1.2.3")
        self.assertIn('<pre class="cmd" tabindex="0"><code>evoxd reconcile</code></pre>', out)
        self.assertIn('<li><a href="#a">evoxd reconcile</a></li>', out)


class ManualApiTest(NoSpawnMixin, unittest.TestCase):
    def test_missing_file_no_language_fallback(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t, "quick-guide.en.html").write_text("x")
            self.assertIsNone(manual.doc_file("quick", "de", (t,)))
            with self.assertRaises(Exception) as c:
                manual.open_doc("quick", "de", dirs=(t,), which=lambda n: "/x/xdg-open", popen=mock.Mock())
            self.assertIn("not found", str(c.exception))

    def test_open_local_only(self):
        pop = mock.Mock()
        manual.open_doc("quick", "en", dirs=(MAN,), which=lambda n: "/usr/bin/xdg-open", popen=pop)
        self.assertEqual(pop.call_args[0][0], ["/usr/bin/xdg-open", str(MAN / "quick-guide.en.html")])
        manual.open_doc("quick", "de", "help", dirs=(MAN,), which=lambda n: "/usr/bin/xdg-open", popen=pop)
        arg = pop.call_args[0][0][1]
        self.assertTrue(arg.startswith("file:///") and arg.endswith("quick-guide.de.html#help"))
        for bad in ("x;rm", "http://a", "../x", ""):
            with self.assertRaises(Exception):
                manual.open_doc("quick", "en", bad, dirs=(MAN,), which=lambda n: "/x", popen=pop)
        with self.assertRaises(Exception):
            manual.open_doc("quick", "fr", dirs=(MAN,), which=lambda n: "/x", popen=pop)

    def test_version_warning(self):
        self.assertTrue(manual.is_older("0.10.1", "0.10.2"))
        self.assertFalse(manual.is_older("0.10.2", "0.10.2"))
        self.assertFalse(manual.is_older("0.10.10", "0.10.2"))
        self.assertFalse(manual.is_older("x", "0.10.2"))
        self.assertEqual(manual.doc_version(MAN / "quick-guide.en.html"), evoxd.__version__)

    def test_context_anchors_exist(self):
        for topic, (key, anchor) in manual.CONTEXT.items():
            for lang in ("en", "de"):
                f = manual.doc_file(key, lang, (MAN,))
                self.assertIsNotNone(f)
                self.assertIn(f'id="{anchor}"', f.read_text(encoding="utf-8"))

    def test_texts(self):
        self.assertEqual(T.BTN_DOCS, "Documentation")
        self.assertEqual(T.DOCS_SOON, "coming soon")
        self.assertEqual(set(T.DOCS_CARDS), {"easy", "quick", "full", "dev"})


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class DocsGuiTest(GuiBase):
    def dlg(self, dirs=None, lang="en", opener=None):
        import evoxd.gui as G
        d = G.DocsDialog(None, dirs=dirs or (MAN,), opener=opener or mock.Mock(), lang=lang)
        self.addCleanup(d.destroy)
        return d

    def test_main_button(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        self.addCleanup(w.destroy)
        self.assertEqual(w.docs_btn.get_label(), "Documentation")
        self.assertTrue(w.docs_btn.get_tooltip_text())
        self.assertEqual(w.status_texts[w.docs_btn], T.STATUS_DOCS)
        self.assertTrue(w.docs_btn.get_can_focus())
        self.assertIn("evox-fn-aux", w.docs_btn.get_style_context().list_classes())

    def test_cards_grey_when_missing(self):
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        for f in MAN.glob("quick-guide.*.html"):
            shutil.copy(f, tmp)
        d = self.dlg(dirs=(tmp,))
        cls = lambda k: d.cards[k][0].get_style_context().list_classes()       # noqa: E731
        self.assertIn("evox-doc-quick", cls("quick"))
        self.assertTrue(d.cards["quick"][0].get_sensitive())
        for k in ("full", "dev"):
            self.assertIn("evox-doc-off", cls(k))
            self.assertFalse(d.cards[k][0].get_sensitive())
            self.assertEqual(d.cards[k][1].get_text(), "coming soon")

    def test_language_choice_not_remembered_and_follows_locale(self):
        d = self.dlg(lang="de")
        self.assertEqual(d.lang, "de")
        d.lang_btns["en"].set_active(True)
        self.assertEqual(d.lang, "en")
        d2 = self.dlg(lang="de")
        self.assertEqual(d2.lang, "de")              # nichts gemerkt

    def test_no_fallback_language(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t, "quick-guide.en.html").write_text("x")
            d = self.dlg(dirs=(t,), lang="de")
            self.assertFalse(d.cards["quick"][0].get_sensitive())
            self.assertEqual(d.cards["quick"][1].get_text(), "file missing")
            op = mock.Mock(side_effect=manual.EvoxError("Document not found: quick-guide.de.html"))
            d.opener = op
            d.open("quick")
            self.assertIn("not found", d.msg.get_text())

    def test_open_calls_opener_with_key_and_lang(self):
        op = mock.Mock()
        d = self.dlg(opener=op, lang="de")
        d.cards["quick"][0].clicked()
        op.assert_called_once()
        self.assertEqual(op.call_args[0][:2], ("quick", "de"))

    def test_version_label_and_warning(self):
        d = self.dlg()
        self.assertEqual(d.version_lbl.get_text(), f"Docs for version {evoxd.__version__}")
        self.assertEqual(d.warn.get_text(), "")
        with tempfile.TemporaryDirectory() as t:
            Path(t, "quick-guide.en.html").write_text('<meta name="evoxd-version" content="0.0.1">')
            d = self.dlg(dirs=(t,))
            self.assertEqual(d.version_lbl.get_text(), "Docs for version 0.0.1")
            self.assertIn("older" if False else "may be out of date", d.warn.get_text())

    def test_back_esc_focus(self):
        import evoxd.gui as G
        from gi.repository import Gdk, Gtk
        d = self.dlg()
        self.assertTrue(d.cancel_btn.has_focus() or d.get_focus() is d.cancel_btn or d.cancel_btn.is_focus())
        self.assertEqual(d.get_default_widget(), d.cancel_btn)
        got = []
        d.connect("response", lambda _d, r: got.append(r))
        ev = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        ev.keyval = Gdk.KEY_Escape
        self.assertTrue(G.dialog_key(d, ev))
        self.assertEqual(got, [Gtk.ResponseType.CANCEL])

    def test_context_button_setup_and_colors(self):
        import evoxd.gui as G
        calls = []
        b = G.ctx_help_button("setup", opener=lambda topic: calls.append(topic))
        b.clicked()
        self.assertEqual(calls, ["setup"])
        self.assertEqual(b.get_label(), "?")
        self.assertIn("evox-fn-aux", b.get_style_context().list_classes())
        self.assertTrue(b.get_tooltip_text())
        shown = []
        b2 = G.ctx_help_button("colors", opener=mock.Mock(side_effect=RuntimeError("x")), show=shown.append)
        b2.clicked()
        self.assertTrue(shown)


if __name__ == "__main__":
    unittest.main()
