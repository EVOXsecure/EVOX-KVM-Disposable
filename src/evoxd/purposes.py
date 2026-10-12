"""Zweckliste für die Schnellauswahl im Startdialog (0.6.4): Standardliste, Prüfung, Laden/Speichern.

Gespeichert in ~/.config/evoxd/config.json unter dem Schlüssel "purposes" (Liste von Strings).
Regel für einen Zweck = Regel für den Namensteil in DISPOSABLE-<Zweck>-NN (lifecycle.purpose_name)."""
import json

from . import texts as T
from .errors import EvoxError
from .lifecycle import purpose_name

KEY = "purposes"
MAX_PURPOSES = 24
DEFAULT_PURPOSES = ("EMAIL", "BROWSING", "SHOPPING", "SOCIAL", "NEWS", "BANKING", "PAYPAL", "CRYPTO",
                    "WORK", "DOWNLOAD", "TESTING", "DOCUMENTS", "OTHER")
# Feste Gruppenzuordnung der Standardnamen (0.6.5); alles andere gehört zu "mylist"
GROUPS = (("everyday", ("EMAIL", "BROWSING", "SHOPPING", "SOCIAL", "NEWS")),
          ("money", ("BANKING", "PAYPAL", "CRYPTO")),
          ("work", ("WORK", "DOWNLOAD", "TESTING", "DOCUMENTS")),
          ("more", ("OTHER",)),
          ("mylist", ()))
MAX_LEN = 16     # = config.PURPOSE_RE


def check_purpose(raw: str, existing=()) -> str:
    """Gibt den Zweck in Großbuchstaben zurück oder wirft EvoxError mit klarer Meldung.

    Verändert wird nur die Großschreibung; Leerzeichen und Sonderzeichen werden abgelehnt."""
    if not raw:
        raise EvoxError(T.QP_ERR_EMPTY)
    p = raw.upper()
    if not p.isascii() or not all(c.isalnum() for c in p):
        raise EvoxError(T.QP_ERR_CHARS)
    if len(p) > MAX_LEN:
        raise EvoxError(T.QP_ERR_LONG.format(n=MAX_LEN))
    purpose_name(p)                      # vorhandene Regel (lifecycle) als letzte Instanz
    if p in existing:
        raise EvoxError(T.QP_ERR_DUP.format(name=p))
    if len(existing) >= MAX_PURPOSES:
        raise EvoxError(T.QP_ERR_FULL.format(n=MAX_PURPOSES))
    return p


def load(settings) -> list:
    """Liste aus config.json; fehlt der Schlüssel oder ist er kaputt → Standardliste.

    Einzelne ungültige oder doppelte Einträge werden beim Lesen übersprungen (Datei bleibt unverändert)."""
    try:
        data = json.loads((settings.config_file or settings.config_path()).read_text())
    except (OSError, ValueError):
        return list(DEFAULT_PURPOSES)
    raw = data.get(KEY) if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return list(DEFAULT_PURPOSES)
    out = []
    for item in raw:
        if not isinstance(item, str):
            continue
        try:
            out.append(check_purpose(item, out))
        except EvoxError:
            continue
    return out


def save(settings, purposes) -> None:
    """Prüft die ganze Liste und schreibt sie atomar (andere Einträge der config.json bleiben)."""
    out = []
    for p in purposes:
        out.append(check_purpose(p, out))
    settings.save_option(KEY, out)


def group_of(name: str) -> str:
    for key, names in GROUPS:
        if name in names:
            return key
    return "mylist"


def grouped(items) -> list:
    """[(Gruppenschlüssel, [Namen])] in fester Gruppenreihenfolge; leere Gruppen fehlen.
    Innerhalb einer Gruppe bleibt die Reihenfolge der Liste (config.json)."""
    out = {key: [] for key, _n in GROUPS}
    for p in items:
        out[group_of(p)].append(p)
    return [(key, out[key]) for key, _n in GROUPS if out[key]]
