class EvoxError(Exception):
    """Fehler mit Meldung für den Benutzer."""


class NotOwned(EvoxError):
    """Objekt gehört nicht EVOX – Veränderung verweigert."""


class AllowlistViolation(EvoxError):
    """VM-Beschreibung verletzt die Positivliste."""


class LockBusy(EvoxError):
    """Ein anderer EVOX-Vorgang läuft."""


class CapacityError(EvoxError):
    """Nicht genug Arbeitsspeicher."""


class SpaceError(EvoxError):
    """Nicht genug Platz für eine Template-Kopie."""


class Cancelled(EvoxError):
    """Vorgang vom Benutzer abgebrochen."""
