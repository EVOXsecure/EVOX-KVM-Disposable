"""Dokumentation öffnen (0.10.2, A7a2): nur lokale Dateien, xdg-open mit Argumentliste, kein Netz, keine Shell.
Dateinamen: easy-guide.<en|de>.html, quick-guide.<en|de>.html, full-manual.<en|de>.html, developer-doc.<en|de>.html (Developer Doc zunächst nur EN).
Kein automatischer Fallback auf eine andere Sprache."""
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import __version__
from .errors import EvoxError

PKG_DIR = Path("/usr/share/doc/evoxd/manual")
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "manual"
LANGS = ("en", "de")
# key -> (Dateistem, geplant): geplante Dokumente zeigt der Dialog als „coming soon“, solange die Datei fehlt
DOCS = {"easy": ("easy-guide", False), "quick": ("quick-guide", False), "full": ("full-manual", True), "dev": ("developer-doc", True)}
# Kontext-Hilfe (Knopf „?“): Dialog -> (Dokument, Anker); seit 0.10.3 die Kapitel des Full Manual (DE-Datei bei Locale de)
CONTEXT = {"setup": ("full", "setupcheck"), "colors": ("full", "colors")}
_ANCHOR = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,40}\Z")
_META = re.compile(r'<meta name="evoxd-version" content="([0-9][0-9.]*)"')


def is_german(env=None) -> bool:
    env = os.environ if env is None else env
    for k in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if env.get(k):
            return env[k].lower().startswith("de")
    return False


def lang_default(env=None) -> str:
    return "de" if is_german(env) else "en"


def doc_file(key, lang, dirs=None):
    """Pfad der Datei oder None, wenn sie fehlt (Paketordner zuerst, dann Projektordner)."""
    if key not in DOCS or lang not in LANGS:
        raise EvoxError("Unknown document.")
    for d in (dirs or (PKG_DIR, PROJECT_DIR)):
        f = Path(d) / f"{DOCS[key][0]}.{lang}.html"
        if f.is_file():
            return f
    return None


def vtuple(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return ()


def doc_version(path):
    """Versionsvermerk im Dokumentkopf oder None."""
    try:
        m = _META.search(Path(path).read_text(encoding="utf-8", errors="replace")[:4000])
    except OSError:
        return None
    return m.group(1) if m else None


def is_older(doc_ver, prog_ver=__version__) -> bool:
    d, p = vtuple(doc_ver), vtuple(prog_ver)
    return bool(d and p and d < p)


def open_doc(key, lang, anchor=None, dirs=None, which=shutil.which, popen=subprocess.Popen):
    f = doc_file(key, lang, dirs)
    if f is None:
        raise EvoxError(f"Document not found: {DOCS[key][0]}.{lang}.html")
    opener = which("xdg-open")
    if not opener:
        raise EvoxError("xdg-open is not installed.")
    target = str(f)
    if anchor is not None:
        if not _ANCHOR.match(anchor):
            raise EvoxError("Bad anchor.")
        target = f.resolve().as_uri() + "#" + anchor       # weiterhin nur die lokale Datei (file://)
    try:
        return popen([opener, target], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        raise EvoxError(f"Cannot open the documentation: {e}") from e


def open_context(topic, lang=None, **kw):
    key, anchor = CONTEXT[topic]
    return open_doc(key, lang or lang_default(), anchor, **kw)


# Kompatibilität 0.10.1
def guide_path(german=None, dirs=None) -> Path:
    f = doc_file("quick", "de" if (is_german() if german is None else german) else "en", dirs)
    if f is None:
        raise EvoxError("Quick Guide file not found.")
    return f


def open_guide(german=None, dirs=None, which=shutil.which, popen=subprocess.Popen):
    return open_doc("quick", "de" if (is_german() if german is None else german) else "en", None, dirs, which, popen)
