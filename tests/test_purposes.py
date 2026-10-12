"""Quick purpose (0.6.4/0.6.5): Standardliste, Gruppen, Chips, Bearbeiten, Zurück-Knopf, Höhenbegrenzung, Konfig."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from evoxd import config, purposes
from evoxd import texts as T
from evoxd.config import Settings
from evoxd.errors import EvoxError
from evoxd.lifecycle import Evox
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor
from tests.nospawn import NoSpawnMixin

HAVE_DISPLAY = Gtk.init_check([])[0]


class PurposeLogicTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self.tmp.name) / "cfg" / "config.json"
        self.s = Settings(state_dir=Path(self.tmp.name) / "st", config_file=self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults(self):
        self.assertEqual(purposes.DEFAULT_PURPOSES, ("EMAIL", "BROWSING", "SHOPPING", "SOCIAL", "NEWS", "BANKING",
                                                     "PAYPAL", "CRYPTO", "WORK", "DOWNLOAD", "TESTING",
                                                     "DOCUMENTS", "OTHER"))
        self.assertEqual(purposes.load(self.s), list(purposes.DEFAULT_PURPOSES))     # Datei fehlt
        self.assertFalse(hasattr(T, "QP_HINT") or hasattr(T, "DE_QP_HINT") or hasattr(T, "QP_HINT_NAMES"))

    def test_groups(self):
        g = dict(purposes.grouped(purposes.DEFAULT_PURPOSES))
        self.assertEqual(list(g), ["everyday", "money", "work", "more"])           # MY LIST nur bei eigenen
        self.assertEqual(g["everyday"], ["EMAIL", "BROWSING", "SHOPPING", "SOCIAL", "NEWS"])
        self.assertEqual(g["money"], ["BANKING", "PAYPAL", "CRYPTO"])
        self.assertEqual(g["work"], ["WORK", "DOWNLOAD", "TESTING", "DOCUMENTS"])
        self.assertEqual(g["more"], ["OTHER"])
        self.assertEqual(T.QP_GROUPS, {"everyday": "EVERYDAY", "money": "MONEY", "work": "WORK & TECH",
                                       "more": "MORE", "mylist": "MY LIST"})
        self.assertEqual(set(T.DE_QP_GROUPS), set(T.QP_GROUPS))
        mine = purposes.grouped(["ZED", "EMAIL", "ALPHA"])
        self.assertEqual(mine, [("everyday", ["EMAIL"]), ("mylist", ["ZED", "ALPHA"])])   # Reihenfolge bleibt
        self.assertEqual(purposes.group_of("MYBANK"), "mylist")

    def test_validation(self):
        c = purposes.check_purpose
        self.assertEqual(c("mail"), "MAIL")                    # nur Großschreibung
        self.assertEqual(c("A" * 16), "A" * 16)                # Grenze 16 ok
        self.assertEqual(c("a1b2"), "A1B2")
        for bad in ("", "A" * 17, "A B", " A", "A ", "A-B", "A_B", "ÄB", "A.B", "A/B", "A\n", "ＡＢ"):
            with self.assertRaises(EvoxError, msg=repr(bad)):
                c(bad)
        with self.assertRaises(EvoxError) as cm:
            c("email", ["EMAIL"])                              # Duplikat auch bei anderer Schreibweise
        self.assertIn("EMAIL", str(cm.exception))
        with self.assertRaises(EvoxError):
            c("X", [f"P{i}" for i in range(24)])               # 24er-Grenze
        c("X", [f"P{i}" for i in range(23)])                   # 23 vorhanden → 24. ok
        # längster Zweck ergibt einen gültigen VM-Namen
        import re
        self.assertTrue(re.fullmatch(config.TEMP_NAME_RE, f"DISPOSABLE-{'A' * 16}-99"))

    def test_load_broken_and_old(self):
        self.cfg.parent.mkdir(parents=True)
        for content in ("{kaputt", "[]", '{"purposes": "EMAIL"}', '{"purposes": null}', '{"host_reserve_mib": 2048}',
                        '{"purposes": 5}'):
            self.cfg.write_text(content)
            self.assertEqual(purposes.load(self.s), list(purposes.DEFAULT_PURPOSES), content)
            self.assertEqual(self.cfg.read_text(), content)    # Datei beim Lesen unverändert
        self.cfg.write_text(json.dumps({"purposes": ["mail", "MAIL", "A B", 3, "X" * 20, "", "OK1", None]}))
        self.assertEqual(purposes.load(self.s), ["MAIL", "OK1"])
        self.cfg.write_text(json.dumps({"purposes": [f"P{i}" for i in range(30)]}))
        self.assertEqual(len(purposes.load(self.s)), 24)       # höchstens 24
        self.cfg.write_text(json.dumps({"purposes": []}))
        self.assertEqual(purposes.load(self.s), [])            # bewusst leere Liste bleibt leer

    def test_save_keeps_other_keys_and_is_atomic(self):
        self.cfg.parent.mkdir(parents=True)
        self.cfg.write_text(json.dumps({"host_reserve_mib": 4096}))
        purposes.save(self.s, ["WORK", "mail"])
        data = json.loads(self.cfg.read_text())
        self.assertEqual(data, {"host_reserve_mib": 4096, "purposes": ["WORK", "MAIL"]})
        self.assertEqual(oct(self.cfg.stat().st_mode & 0o777), "0o600")
        self.assertEqual([p.name for p in self.cfg.parent.iterdir()], ["config.json"])   # keine Reste
        # Fehler beim Austausch: Original bleibt unverändert
        before = self.cfg.read_text()
        with mock.patch.object(Path, "replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                purposes.save(self.s, ["ONLY"])
        self.assertEqual(self.cfg.read_text(), before)
        # ungültige Liste wird gar nicht geschrieben
        with self.assertRaises(EvoxError):
            purposes.save(self.s, ["A", "A"])
        self.assertEqual(self.cfg.read_text(), before)

    def test_save_backs_up_broken_file(self):
        self.cfg.parent.mkdir(parents=True)
        self.cfg.write_text("{kaputt")
        purposes.save(self.s, ["WORK"])
        self.assertEqual(json.loads(self.cfg.read_text()), {"purposes": ["WORK"]})
        baks = list(self.cfg.parent.glob("config.json.broken-*"))
        self.assertEqual(len(baks), 1)
        self.assertEqual(baks[0].read_text(), "{kaputt")


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class PurposeGuiTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        s = Settings(state_dir=d / "st", runtime_dir=d / "rt", guard_status=d / "x", config_file=d / "cfg.json")
        self.hv = FakeHypervisor()
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.reg = Registry(s.registry_path)
        self.mem = {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20}
        self.ev = Evox(s, self.hv, self.reg, net_check=lambda: (False, "x"), meminfo=lambda: self.mem)
        self.ev.import_template("TEMPLATE-MAIL")

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def dlg(self, offline=False):
        from evoxd.gui import StartDialog
        return StartDialog(None, self.ev, "TEMPLATE-MAIL", offline=offline)

    def test_chips_default_and_click(self):
        for offline in (False, True):
            d = self.dlg(offline)
            self.assertEqual(list(d.chips), list(purposes.DEFAULT_PURPOSES))
            self.assertTrue(all(b.get_style_context().has_class(f"evox-chip-{purposes.group_of(p)}")
                                for p, b in d.chips.items()))
            d.chips["SHOPPING"].clicked()
            self.assertEqual(d.purpose_text, "SHOPPING")
            self.assertEqual(d.name_lbl.get_text(), "DISPOSABLE-SHOPPING-01")
            self.assertEqual(d.offline, offline)                       # Modus unverändert
            cancel_cls = d.ok_btn.get_style_context().has_class("evox-start-offline")
            self.assertEqual(cancel_cls, offline)
            d.purpose.get_child().set_text("eigen")                    # frei editierbar
            self.assertEqual(d.purpose_text, "eigen")
            self.assertTrue(d.ok_btn.get_sensitive())
            d.destroy()

    def test_other_only_focuses(self):
        d = self.dlg()
        d.purpose.get_child().set_text("WORK")
        d.chips["OTHER"].clicked()
        self.assertEqual(d.purpose_text, "WORK")                      # Feld unverändert
        d.destroy()

    def test_chip_click_does_not_start(self):
        from evoxd.gui import MainWindow
        w = MainWindow(self.ev)
        calls = []
        w.start_vm = lambda *a, **k: calls.append(a)
        d = self.dlg()
        d.chips["BANKING"].clicked()
        self.assertEqual(calls, [])
        self.assertEqual(self.ev.s.load_last_start()["purpose"], "EMAIL")
        d.destroy()
        w.destroy()

    def test_no_hint_line(self):
        d = self.dlg()
        self.assertFalse(hasattr(d, "hint_lbl"))
        d.chips["BANKING"].clicked()

        def texts(w):
            out = []
            if isinstance(w, Gtk.Label):
                out.append(w.get_text())
            if isinstance(w, Gtk.Container):
                for c in w.get_children():
                    out += texts(c)
            return out
        self.assertFalse([t for t in texts(d) if "erased completely" in t])
        d.destroy()

    def test_group_headings_and_my_list(self):
        d = self.dlg()
        self.assertEqual({k: l.get_text() for k, l in d.group_labels.items()},
                         {"everyday": "EVERYDAY", "money": "MONEY", "work": "WORK & TECH", "more": "MORE"})
        self.assertTrue(all(l.get_style_context().has_class(f"evox-grp-{k}") for k, l in d.group_labels.items()))
        d.destroy()
        purposes.save(self.ev.s, ["MYBANK", "EMAIL", "OTHER", "ABC"])
        d = self.dlg()
        self.assertEqual(list(d.group_labels), ["everyday", "more", "mylist"])
        self.assertEqual(d.group_labels["mylist"].get_text(), "MY LIST")
        self.assertEqual(list(d.chips), ["EMAIL", "OTHER", "MYBANK", "ABC"])     # Gruppenfolge, Listenfolge
        d.chips["MYBANK"].clicked()
        self.assertEqual(d.purpose_text, "MYBANK")
        d.destroy()

    def test_vm_name_big_bold(self):
        import evoxd.gui as G
        d = self.dlg()
        self.assertTrue(d.name_lbl.get_style_context().has_class("evox-vmname"))
        self.assertIn(".evox-vmname { font-size: 26pt; font-weight: bold; color: #39D353; }", G.CSS)    # 2 x 13 pt Basis
        self.assertIn("font-size: 13pt", G.CSS)
        d.purpose.get_child().set_text("a b")                                            # Fehler: nicht groß
        self.assertFalse(d.name_lbl.get_style_context().has_class("evox-vmname"))
        d.purpose.get_child().set_text("OK1")
        self.assertTrue(d.name_lbl.get_style_context().has_class("evox-vmname"))
        d.destroy()

    def test_back_buttons_start_dialog(self):
        for offline in (False, True):
            d = self.dlg(offline)
            self.assertEqual(T.BACK, "← BACK")
            self.assertEqual((d.back_top.get_label(), d.cancel_btn.get_label()), (T.BACK, T.BACK))
            self.assertIn(d.back_top, self._all(d.mode_bar))                     # Kopfleiste
            self.assertIs(d.get_content_area().get_children()[0], d.mode_bar)
            self.assertNotIn(d.back_top, self._all(d.scroller))                  # nie im scrollenden Teil
            self.assertIn(d.cancel_btn, d.get_action_area().get_children())      # untere Knopfzeile
            self.assertTrue(d.back_top.get_style_context().has_class("evox-cancel"))
            self.assertTrue(d.cancel_btn.get_style_context().has_class("evox-cancel"))
            for b in (d.back_top, d.cancel_btn):
                got = []
                h = d.connect("response", lambda _d, r: got.append(r))
                b.clicked()
                d.disconnect(h)
                self.assertEqual(got, [Gtk.ResponseType.CANCEL])
            d.destroy()

    @staticmethod
    def _all(w):
        out = [w]
        if isinstance(w, Gtk.Container):
            for c in w.get_children():
                out += PurposeGuiTest._all(c)
        return out

    # ---- 0.6.6: Gruppenfarben, Namensanzeige, Layout
    def test_group_colors_constants_and_css(self):
        import evoxd.gui as G
        self.assertEqual(G.GROUP_COLORS, {"everyday": "#4C8DFF", "money": "#E0A030", "work": "#2BB3A3",
                                          "more": "#9AA4B2", "mylist": "#E07AA8"})
        for k, c in G.GROUP_COLORS.items():
            self.assertRegex(G.CSS, rf"\.evox-grp-{k} \{{[^}}]*{c}")
            self.assertRegex(G.CSS, rf"\.evox-chip-{k} \{{[^}}]*border: 1px solid {c}")
        self.assertIn("@theme_fg_color", G.CSS)                      # lesbar auf hellem und dunklem Theme
        prov = Gtk.CssProvider()
        prov.load_from_data(G.CSS.encode())                          # CSS muss fehlerfrei parsen
        # Modusfarbe nur in Kopfleiste und Start-Knopf, nicht mehr an den Chips
        self.assertNotIn("evox-chip-internet", G.CSS)
        self.assertNotIn("evox-chip-offline", G.CSS)
        self.assertIn(".evox-dlg-internet { border: 1px solid", G.CSS)    # schlanker Modus-Rand

    def test_chip_and_heading_classes_per_group(self):
        purposes.save(self.ev.s, ["MYBANK", "EMAIL", "BANKING", "WORK", "OTHER"])
        for offline in (False, True):
            d = self.dlg(offline)
            for name, grp in (("EMAIL", "everyday"), ("BANKING", "money"), ("WORK", "work"),
                              ("OTHER", "more"), ("MYBANK", "mylist")):
                ctx = d.chips[name].get_style_context()
                self.assertTrue(ctx.has_class(f"evox-chip-{grp}"), name)
                self.assertEqual([c for c in ctx.list_classes() if c.startswith("evox-chip-")], [f"evox-chip-{grp}"])
                self.assertTrue(d.group_labels[grp].get_style_context().has_class(f"evox-grp-{grp}"))
            d.destroy()

    def test_vm_name_purple(self):
        import evoxd.gui as G
        self.assertEqual(G.VMNAME_COLOR, G.TAB_DISPOSABLE_COLOR)
        self.assertEqual(G.VMNAME_COLOR, G.NAME_COLOR)
        self.assertIn(f"color: {G.TAB_DISPOSABLE_COLOR}", G.CSS.split(".evox-vmname {")[1].split("}")[0])
        self.assertIn(f".evox-start-disposable {{ background-image: none; background-color: {G.TAB_DISPOSABLE_COLOR}", G.CSS)

    def test_name_display_free_and_taken_live(self):
        d = self.dlg()
        d.purpose.get_child().set_text("EMAIL")
        self.assertEqual((d.vm_name, d.name_lbl.get_text()), ("DISPOSABLE-EMAIL-01", "DISPOSABLE-EMAIL-01"))
        r = self.ev.start("TEMPLATE-MAIL", purpose="EMAIL", memory_mib=2048, vcpus=1)      # belegt
        self.assertEqual(r.name, "DISPOSABLE-EMAIL-01")
        d.chips["EMAIL"].clicked()                                      # Chip-Klick rechnet neu
        self.assertEqual(d.name_lbl.get_text(), "DISPOSABLE-EMAIL-02")
        d.chips["NEWS"].clicked()                                       # anderer Zweck: frei
        self.assertEqual(d.name_lbl.get_text(), "DISPOSABLE-NEWS-01")
        d.purpose.get_child().set_text("email")                         # Eintippen: belegt
        self.assertEqual(d.name_lbl.get_text(), "DISPOSABLE-EMAIL-02")
        d.purpose.get_child().set_text("EMAIL2")                        # wieder frei
        self.assertEqual(d.name_lbl.get_text(), "DISPOSABLE-EMAIL2-01")
        d.purpose.get_child().set_text("EMAIL")                         # belegt -> frei -> belegt
        self.assertEqual(d.vm_name, "DISPOSABLE-EMAIL-02")
        self.ev.stop(r.name)                                            # VM weg: Nummer 01 wieder frei
        d.update()
        self.assertEqual(d.vm_name, "DISPOSABLE-EMAIL-01")
        d.purpose.get_child().set_text("a b")                           # Fehler: kein Name
        self.assertIsNone(d.vm_name)
        d.destroy()

    def test_foreign_domain_counts_as_taken(self):
        self.hv.add_foreign("DISPOSABLE-NEWS-01")
        d = self.dlg()
        d.chips["NEWS"].clicked()
        self.assertEqual(d.name_lbl.get_text(), "DISPOSABLE-NEWS-02")
        d.destroy()

    def _start_via_dialog(self, w, d, shown):
        import evoxd.gui as G
        return w.start_vm("TEMPLATE-MAIL", d.purpose_text, 2048, 1, True, opener=lambda *_: None, expect_name=shown)

    def test_start_name_equals_displayed_name(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        for _i in range(2):
            d = self.dlg()
            d.chips["SOCIAL"].clicked()
            shown = d.vm_name
            self._start_via_dialog(w, d, shown).join(20)
            self.assertIn(shown, {t.name for t in self.reg.active_temps()})
            d.destroy()
        self.assertEqual({t.name for t in self.reg.active_temps()}, {"DISPOSABLE-SOCIAL-01", "DISPOSABLE-SOCIAL-02"})
        w.destroy()

    def test_race_name_taken_meanwhile_refuses(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        msgs = []
        w.show = lambda text, bad=False: msgs.append(text)
        d = self.dlg()
        d.chips["SHOPPING"].clicked()
        shown = d.vm_name
        self.assertEqual(shown, "DISPOSABLE-SHOPPING-01")
        self.ev.start("TEMPLATE-MAIL", purpose="SHOPPING", memory_mib=2048, vcpus=1)    # Rennen: jemand war schneller
        t = self._start_via_dialog(w, d, shown)
        t.join(20)
        while Gtk.events_pending():
            Gtk.main_iteration()
        self.assertEqual({x.name for x in self.reg.active_temps()}, {"DISPOSABLE-SHOPPING-01"})   # nichts Neues
        self.assertTrue(any("DISPOSABLE-SHOPPING-01" in m and "DISPOSABLE-SHOPPING-02" in m and "Not started" in m
                            for m in msgs), msgs)
        d.update()                                                      # Dialog zeigt jetzt die Nummer 02
        self.assertEqual(d.vm_name, "DISPOSABLE-SHOPPING-02")
        d.destroy()
        w.destroy()

    def test_layout_no_scroller_needed(self):
        """Standardgröße: der Inhalt passt ohne Scrollen (Attrappe: natürliche Höhe gegen Dialoghöhe)."""
        import evoxd.gui as G
        purposes.save(self.ev.s, list(purposes.DEFAULT_PURPOSES) + ["MYBANK", "MYMAIL"])
        d = self.dlg()
        d.show_all()
        grid = d.chips_box.get_children()[0]
        pos = {k: (grid.child_get_property(c, "left-attach"), grid.child_get_property(c, "top-attach"))
               for k, c in zip([k for k in d.group_labels if k != "mylist"], reversed(grid.get_children()))}
        self.assertEqual(pos["everyday"], (0, 0))
        self.assertEqual(pos["money"], (1, 0))                           # nebeneinander
        self.assertEqual(pos["work"], (0, 1))
        self.assertEqual(pos["more"], (1, 1))
        self.assertNotIn("mylist", pos)                                  # MY LIST liegt unter MORE (gleiche Zelle)
        self.assertIn(d.group_labels["mylist"], self._all(grid.get_children()[0]))
        G.apply_css()
        w = G.START_SIZE[0]
        need = (d.scroller.get_child().get_preferred_height_for_width(w - 20)[1]
                + d.mode_bar.get_preferred_height_for_width(w)[1] + d.get_action_area().get_preferred_height()[1])
        self.assertLessEqual(need, G.START_SIZE[1])                      # Inhalt + Leisten <= Standardhöhe
        self.assertGreaterEqual(G.START_SIZE[0], 900)                    # etwas breiter
        self.assertLessEqual(G.START_SIZE[1], 560)                       # nicht höher
        d.destroy()

    def test_back_starts_nothing(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        calls = []
        w.start_vm = lambda *a, **k: calls.append(a)
        for btn in ("back_top", "cancel_btn"):
            real = G.StartDialog

            class D(real):
                def run(self, _b=btn):
                    got = []
                    self.connect("response", lambda _d, r: got.append(r))
                    getattr(self, _b).clicked()
                    return got[0]
            G.StartDialog = D
            try:
                w.on_start(None)
            finally:
                G.StartDialog = real
        self.assertEqual(calls, [])
        self.assertEqual(self.ev.s.load_last_start()["purpose"], "EMAIL")     # nichts gespeichert/gestartet
        w.destroy()

    def test_height_limited_to_workarea(self):
        import evoxd.gui as G
        for wa, want in ((1000, 560), (500, 440), (300, 240)):
            with mock.patch.object(G, "workarea_height", lambda _w=None, wa=wa: wa):
                d = self.dlg()
                self.assertEqual(d.fitted_height, want, wa)
                self.assertLessEqual(d.fitted_height, max(240, wa - G.DIALOG_DECOR))
                self.assertEqual(d.get_default_size()[1], want)
                e = G.PurposeEditDialog(None, self.ev.s, purposes.DEFAULT_PURPOSES)
                self.assertEqual(e.fitted_height, min(440, max(240, wa - G.DIALOG_DECOR)))
                d.destroy()
                e.destroy()
        d = self.dlg()
        self.assertTrue(G.workarea_height(None) > 0)                    # echte Ermittlung liefert eine Höhe
        self.assertEqual(d.scroller.get_policy()[0], Gtk.PolicyType.NEVER)
        self.assertEqual(d.scroller.get_policy()[1], Gtk.PolicyType.AUTOMATIC)
        d.destroy()

    def test_fullscreen(self):
        import evoxd.gui as G
        w = G.MainWindow(self.ev)
        calls = []
        w.fullscreen = lambda: calls.append("fs")
        w.unfullscreen = lambda: calls.append("un")
        self.assertEqual(w.fullscreen_btn.get_label(), "Fullscreen")
        w.fullscreen_btn.clicked()
        self.assertEqual((calls, w.fullscreen_btn.get_label()), (["fs"], "Exit fullscreen"))
        w.fullscreen_btn.clicked()
        self.assertEqual((calls, w.fullscreen_btn.get_label()), (["fs", "un"], "Fullscreen"))

        def key(k):
            from gi.repository import Gdk
            e = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
            e.keyval = k
            return w._on_key(w, e)
        from gi.repository import Gdk
        self.assertFalse(key(Gdk.KEY_Escape))                  # Escape tut im Normalmodus nichts
        self.assertTrue(key(Gdk.KEY_F11))
        self.assertTrue(key(Gdk.KEY_Escape))                   # Escape verlässt Vollbild
        self.assertEqual(calls, ["fs", "un", "fs", "un"])
        d = self.dlg()
        self.assertFalse(d.get_window() and d.get_window().get_state() & Gdk.WindowState.FULLSCREEN)
        d.destroy()
        w.destroy()

    def test_custom_list_and_broken_config(self):
        purposes.save(self.ev.s, ["ALPHA", "OTHER"])
        d = self.dlg()
        self.assertEqual(list(d.chips), ["OTHER", "ALPHA"])      # MORE vor MY LIST
        self.assertEqual(len(d.purpose.get_model()), 2)
        d.destroy()
        self.ev.s.config_file.write_text("{kaputt")
        d = self.dlg()                                                # kein Absturz
        self.assertEqual(list(d.chips), list(purposes.DEFAULT_PURPOSES))
        d.destroy()
        self.assertEqual(self.ev.s.config_file.read_text(), "{kaputt")

    def test_edit_dialog(self):
        from evoxd.gui import PurposeEditDialog
        d = PurposeEditDialog(None, self.ev.s, purposes.DEFAULT_PURPOSES)
        self.assertEqual(len(d.store), 13)
        self.assertTrue(d.add("neu"))
        self.assertEqual(d.items[0], "NEU")                           # ganz oben
        self.assertEqual(d.store[0][0], "NEU")
        self.assertEqual(d.selected_index(), 0)                       # markiert
        self.assertFalse(d.add("neu"))                                # Duplikat
        self.assertIn("NEU", d.msg.get_text())
        self.assertFalse(d.add("a b"))
        self.assertEqual(d.msg.get_text(), T.QP_ERR_CHARS)
        self.assertFalse(d.add(""))
        self.assertFalse(d.add("X" * 17))
        self.assertEqual(len(d.items), 14)                            # Fehler ändern nichts
        d.view.get_selection().select_path(Gtk.TreePath(1))
        d.move(-1)
        self.assertEqual(d.items[:2], ["EMAIL", "NEU"])
        d.move(1)
        d.view.get_selection().select_path(Gtk.TreePath(len(d.items) - 1))
        d.move(1)                                                     # am Ende: keine Wirkung
        d.view.get_selection().select_path(Gtk.TreePath(1))
        d.remove()
        self.assertNotIn("EMAIL", d.items)
        d.on_save()
        self.assertEqual(purposes.load(self.ev.s), d.items)
        d.reset()
        self.assertEqual(d.items, list(purposes.DEFAULT_PURPOSES))
        d.destroy()

    def test_edit_dialog_new_visible_and_buttons(self):
        from evoxd.gui import PurposeEditDialog
        d = PurposeEditDialog(None, self.ev.s, [f"P{i}" for i in range(20)])
        d.show()
        d.view.scroll_to_cell(Gtk.TreePath(19), None, False, 0, 0)     # nach unten gescrollt
        self.assertTrue(d.add("neu"))
        self.assertEqual((d.items[0], d.selected_index()), ("NEU", 0))
        rect = d.view.get_visible_rect()
        self.assertEqual(rect.y, 0)                                    # Liste steht oben: Eintrag sichtbar
        cls = lambda b: [c for c in ("evox-import-btn", "evox-danger", "evox-offline", "evox-vault-btn",
                                     "evox-start-internet", "evox-cancel") if b.get_style_context().has_class(c)]
        self.assertEqual(cls(d.add_btn), ["evox-import-btn"])
        self.assertEqual(cls(d.remove_btn), ["evox-danger"])
        self.assertEqual(cls(d.up_btn), ["evox-offline"])
        self.assertEqual(cls(d.down_btn), ["evox-offline"])
        self.assertEqual(cls(d.reset_btn), ["evox-vault-btn"])
        self.assertEqual(cls(d.save_btn), ["evox-start-internet"])
        self.assertEqual(cls(d.back_top), ["evox-cancel"])
        self.assertEqual((d.back_top.get_label(), d.cancel_btn.get_label()), (T.BACK, T.BACK))
        self.assertIn(d.back_top, self._all(d.head_bar))
        self.assertIn(d.cancel_btn, d.get_action_area().get_children())
        for b in (d.back_top, d.cancel_btn):
            got = []
            h = d.connect("response", lambda _d, r: got.append(r))
            b.clicked()
            d.disconnect(h)
            self.assertEqual(got, [Gtk.ResponseType.CANCEL])
        self.assertEqual(purposes.load(self.ev.s), list(purposes.DEFAULT_PURPOSES))     # BACK speichert nichts
        d.destroy()

    def test_edit_dialog_limit_and_entry_upper(self):
        from evoxd.gui import PurposeEditDialog
        d = PurposeEditDialog(None, self.ev.s, [f"P{i}" for i in range(24)])
        self.assertFalse(d.add("EXTRA"))
        self.assertEqual(d.msg.get_text(), T.QP_ERR_FULL.format(n=24))
        d.entry.set_text("abc")
        self.assertEqual(d.entry.get_text(), "ABC")                   # automatisch groß
        d.destroy()

    def test_edit_via_start_dialog_updates_chips(self):
        d = self.dlg()
        d.set_purpose_list(["ONE", "TWO"])
        self.assertEqual(list(d.chips), ["ONE", "TWO"])
        d.chips["TWO"].clicked()
        self.assertEqual(d.purpose_text, "TWO")
        d.destroy()


if __name__ == "__main__":
    unittest.main()
