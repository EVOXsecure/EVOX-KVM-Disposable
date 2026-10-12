"""0.6.21: Auswahlfarbe je Reiter/Liste (nur Darstellung): TEMPLATE Türkis, DISPOSABLE Neongrün, VAULT Bernstein."""
import os
import re
import unittest

os.environ.setdefault("EVOXD_NOSPAWN", "1")
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402
import evoxd.gui as G  # noqa: E402

HAVE_DISPLAY = Gtk.init_check()[0]


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + .05) / (y + .05)


class SelColorCssTest(unittest.TestCase):
    def rules(self, cls):
        return [l for l in G.CSS.splitlines() if f"treeview.view.evox-sel-{cls}" in l]

    def test_constants(self):
        self.assertEqual(G.SELECT_TEAL, "#00F0FF")
        self.assertEqual(G.SELECT_GREEN, "#39D353")
        self.assertEqual(G.SELECT_AMBER, "#E0A030")

    def test_each_list_has_its_color_in_all_states(self):
        for cls, bg, fg in (("teal", G.SELECT_TEAL, G.TEMPLATE_TEXT), ("green", G.SELECT_GREEN, G.SELECT_GREEN_TEXT)):
            for st in (":selected", ":selected:focus", ":selected:hover", ":selected:backdrop"):
                self.assertIn(f"treeview.view.evox-sel-{cls}{st} {{ background-color: {bg}; background-image: none; color: {fg}; }}", G.CSS)
            self.assertIn(f"treeview.view.evox-sel-{cls}:hover {{ background-color: alpha({bg}, 0.25); }}", G.CSS)

    def test_no_amber_in_teal_or_purple_rules(self):
        for cls in ("teal", "green"):
            self.assertTrue(self.rules(cls))
            for l in self.rules(cls):
                self.assertNotIn(G.SELECT_AMBER.lower(), l.lower())
        self.assertIn("treeview.view:selected { background-color: #E0A030;", G.CSS)    # VAULT/Standard: Bernstein

    def test_contrast_values(self):
        self.assertGreaterEqual(contrast(G.SELECT_TEAL, G.TEMPLATE_TEXT), 7)
        self.assertGreaterEqual(contrast(G.SELECT_GREEN, G.SELECT_GREEN_TEXT), 7)
        for k, (bg, _fg, bad) in G.SELECT_STYLES.items():
            self.assertGreaterEqual(contrast(bg, bad), 4.4, k)
        self.assertGreaterEqual(contrast(G.FOCUS_INNER, G.SELECT_TEAL), 7)             # Innenrand trennt auf Türkis
        self.assertGreaterEqual(contrast(G.FOCUS_INNER, G.SELECT_GREEN), 9)           # Innenrand trennt auf Neongrün (9,99); Limette direkt auf Grün nur 1,67
        self.assertGreaterEqual(contrast(G.FOCUS_COLOR, G.SELECT_GREEN), 1.5)    # ehrlich: nur der dunkle Innenrand trennt

    def test_focus_unchanged(self):
        self.assertEqual(G.FOCUS_DEFAULT, "#C6FF00")
        self.assertEqual(G.CSS.count(G.FOCUS_COLOR), G.FOCUS_CSS.count(G.FOCUS_COLOR))


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class SelColorWidgetTest(unittest.TestCase):
    def test_class_and_override_fg(self):
        st = Gtk.ListStore(str, str)
        st.append(["a-BACKUP", "#c01c28"])
        st.append(["b", None])
        v = Gtk.TreeView(model=st)
        col = G.sel_fg_column(v, "x", 0, 1, "teal")
        v.append_column(col)
        sw = Gtk.ScrolledWindow()
        sw.add(v)
        frame = G.list_frame(sw, v, "teal")
        self.assertTrue(v.get_style_context().has_class("evox-sel-teal"))
        cell = col.get_cells()[0]
        n = []
        v.get_selection().connect("changed", lambda *_: n.append(1))
        col.cell_set_cell_data(st, st.get_iter(0), False, False)
        self.assertEqual(cell.get_property("foreground-rgba").to_string(), "rgb(192,28,40)")
        v.get_selection().select_path(Gtk.TreePath(0))
        col.cell_set_cell_data(st, st.get_iter(0), False, False)
        self.assertEqual(cell.get_property("foreground-rgba").to_string(), "rgb(139,0,0)")
        col.cell_set_cell_data(st, st.get_iter(1), False, False)
        self.assertFalse(cell.get_property("foreground-set"))
        self.assertEqual(n, [1])                                                       # nur das eigene Signal


if __name__ == "__main__":
    unittest.main()
