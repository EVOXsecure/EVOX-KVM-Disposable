"""0.6.19: ein Fokusrahmen um das ganze Listenfeld statt je Zelle; Bernstein-Markierung bleibt; backup-check.
Echte Darstellung im Host-Theme ist [U] (HOST-SCHRITTE.md, G32)."""
import os
import hashlib
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import evoxd.gui as G

ROOT = Path(__file__).resolve().parent.parent
HAVE_DISPLAY = Gtk.init_check([])[0]


class ListFrameCssTest(unittest.TestCase):
    def test_cell_focus_suppressed_and_frame_on_wrapper(self):
        css = G.CSS
        self.assertIn("treeview.view.cell:focus { outline-style: none; box-shadow: none; }", css)
        self.assertNotIn("treeview.view:focus", G.FOCUS_CSS.split("\n", 3)[1])          # nicht mehr in der Fokusliste
        self.assertIn(".evox-listframe.evox-listfocus", css)
        self.assertIn(f"border: {G.FOCUS_OUTER_PX}px solid transparent", css)           # immer gleich dick: kein Sprung
        self.assertIn(f"border-color: {G.FOCUS_COLOR}", css)
        self.assertIn(f"inset 0 0 0 {G.FOCUS_INNER_PX}px {G.FOCUS_INNER}", css)         # dunkler Innenrand
        self.assertIn(f"0 0 {G.FOCUS_GLOW_PX}px", css)                                  # Schein wie bisher
        self.assertNotIn("animation", css)
        self.assertEqual(G.CSS.count(G.FOCUS_COLOR), G.FOCUS_CSS.count(G.FOCUS_COLOR))  # Farbe nur zentral
        self.assertIn(f"background-color: {G.SELECT_AMBER}", css)                       # Bernstein unverändert


@unittest.skipUnless(HAVE_DISPLAY, "kein Display")
class ListFrameWidgetTest(unittest.TestCase):
    def test_wrapper_class_follows_focus_without_size_change(self):
        v = Gtk.TreeView(model=Gtk.ListStore(str))
        sw = Gtk.ScrolledWindow()
        sw.add(v)
        box = G.list_frame(sw, v)
        ctx = box.get_style_context()
        self.assertTrue(ctx.has_class("evox-listframe"))
        self.assertFalse(ctx.has_class("evox-listfocus"))
        v.emit("focus-in-event", __import__("gi.repository.Gdk", fromlist=["Event"]).Event.new(
            __import__("gi.repository.Gdk", fromlist=["EventType"]).EventType.FOCUS_CHANGE))
        self.assertTrue(ctx.has_class("evox-listfocus"))
        v.emit("focus-out-event", __import__("gi.repository.Gdk", fromlist=["Event"]).Event.new(
            __import__("gi.repository.Gdk", fromlist=["EventType"]).EventType.FOCUS_CHANGE))
        self.assertFalse(ctx.has_class("evox-listfocus"))
        self.assertIs(sw.get_parent(), box)


_LAUNCH = "import os, sys; os.execv(sys.argv[1], sys.argv[1:])"


def run_tool(args, env=None):
    """Skript über einen frischen Python-Interpreter starten (nospawn lässt nur sys.executable zu; Schutz bleibt aktiv)."""
    return subprocess.run([sys.executable, "-I", "-c", _LAUNCH, *map(str, args)], capture_output=True, text=True,
                          timeout=120, env=dict(os.environ, **(env or {})))


def run_check(d):
    return run_tool([ROOT / "tools" / "backup-check.sh", d])


def make_archive(d, name, n, sha=True, mtime=0):
    a = Path(d) / name
    src = Path(d) / "src-tmp"
    src.mkdir(exist_ok=True)
    for i in range(n):
        (src / f"f{i}").write_text(str(i))
    with tarfile.open(a, "w:gz") as t:
        for i in range(n):
            t.add(src / f"f{i}", arcname=f"P/f{i}")
    os.utime(a, (mtime, mtime))
    if sha:
        Path(str(a) + ".sha256").write_text(f"{hashlib.sha256(a.read_bytes()).hexdigest()}  {name}\n")
    for f in src.iterdir():
        f.unlink()
    return a


class BackupCheckTest(unittest.TestCase):
    def test_enough_entries_ok(self):
        with tempfile.TemporaryDirectory() as d:
            make_archive(d, "backup-projekt-a.tar.gz", 20, mtime=1000)
            make_archive(d, "backup-projekt-b.tar.gz", 19, mtime=2000)
            r = run_check(d)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("sha256: OK", r.stdout)
            self.assertIn("ausreichend", r.stdout)

    def test_too_few_entries_warns_and_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            make_archive(d, "backup-projekt-a.tar.gz", 100, mtime=1000)
            make_archive(d, "backup-projekt-b.tar.gz", 10, mtime=2000)
            before = sorted(os.listdir(d))
            r = run_check(d)
            self.assertEqual(r.returncode, 1)
            self.assertIn("WARNUNG: nur 10 statt 100", r.stdout)
            self.assertEqual(sorted(os.listdir(d)), before)

    def test_missing_checksum_warns(self):
        with tempfile.TemporaryDirectory() as d:
            make_archive(d, "backup-projekt-a.tar.gz", 20, mtime=1000)
            make_archive(d, "backup-projekt-b.tar.gz", 20, sha=False, mtime=2000)
            r = run_check(d)
            self.assertEqual(r.returncode, 1)
            self.assertIn("Prüfsumme fehlt", r.stdout)

    def test_wrong_checksum_warns(self):
        with tempfile.TemporaryDirectory() as d:
            a = make_archive(d, "backup-projekt-a.tar.gz", 20, mtime=1000)
            Path(str(a) + ".sha256").write_text("0" * 64 + "  backup-projekt-a.tar.gz\n")
            r = run_check(d)
            self.assertEqual(r.returncode, 1)
            self.assertIn("sha256 stimmt NICHT", r.stdout)

    def test_single_archive_and_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(run_check(d).returncode, 2)
            make_archive(d, "backup-projekt-a.tar.gz", 5, mtime=1000)
            r = run_check(d)
            self.assertEqual(r.returncode, 0)
            self.assertIn("Kein vorheriges", r.stdout)

    def test_backup_script_writes_to_given_dir(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_tool([ROOT / "tools" / "backup-projekt.sh", "9.9.9"], {"EVOX_BACKUP_DIR": d + "/neu"})
            self.assertEqual(r.returncode, 0, r.stderr)
            names = os.listdir(d + "/neu")
            self.assertEqual(len([n for n in names if n.endswith(".tar.gz")]), 1)
            self.assertEqual(len([n for n in names if n.endswith(".sha256")]), 1)
            self.assertIn("sha256: OK", r.stdout)


if __name__ == "__main__":
    unittest.main()
