"""Zentrale Eigentumsprüfung (ENTSCHEIDUNGEN.md §20.16 Punkt 1, §20.20).

Jede verändernde Operation auf einer Domain läuft über require_owned().
EVOX-eigen = EVOX-Metadaten mit Template-Eintrag. Der Name entscheidet nicht;
TEMPLATE-* und VAULT-* sind zusätzlich immer fremd (R29).
"""
import xml.etree.ElementTree as ET
from enum import Enum

from . import config
from .errors import NotOwned


class Owner(Enum):
    EVOX = "evox"          # alle Operationen
    FOREIGN = "foreign"    # nur lesen
    TRANSFER = "transfer"  # nur lesen + Kanal öffnen (Version 2, ohne Funktion)


def classify(name: str, xml: str, transfer_uuids=frozenset()) -> Owner:
    root = ET.fromstring(xml)
    uuid = root.findtext("uuid")
    if uuid in transfer_uuids:
        return Owner.TRANSFER
    if name.startswith(config.PROTECTED_PREFIXES):
        return Owner.FOREIGN
    m = root.find(f"metadata/{{{config.META_URI}}}temp")
    if m is not None and m.get("template"):
        return Owner.EVOX
    return Owner.FOREIGN


def require_owned(name: str, xml: str, operation: str):
    if classify(name, xml) is not Owner.EVOX:
        raise NotOwned(f"'{name}' is not managed by EVOX – '{operation}' refused.")


def is_own_overlay_path(path: str) -> bool:
    return path.startswith(config.OVERLAY_PATH + "/" + config.TEMP_PREFIX)


def is_own_secret_usage(usage: str) -> bool:
    """Secrets der Overlays: usage = Pfad des Overlays im EVOX-Overlay-Pool."""
    return is_own_overlay_path(usage)
