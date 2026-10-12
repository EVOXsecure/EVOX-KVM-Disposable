"""Registry: Absicht und Protokoll; die Wahrheit liefert libvirt (T9)."""
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 2   # v2: bases.damaged; Tabellen origins/pending (0.6.0) nur ergänzt, Spalten von bases unverändert

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bases (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    vol_name TEXT NOT NULL UNIQUE,
    vol_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    src_uuid TEXT NOT NULL,
    firmware TEXT NOT NULL DEFAULT 'bios' CHECK (firmware IN ('bios', 'efi')),
    created REAL NOT NULL,
    retired INTEGER NOT NULL DEFAULT 0,
    damaged INTEGER NOT NULL DEFAULT 0,
    UNIQUE (name, version)
);
CREATE TABLE IF NOT EXISTS temps (
    name TEXT PRIMARY KEY,
    uuid TEXT NOT NULL UNIQUE,
    base_id INTEGER NOT NULL REFERENCES bases(id),
    overlay_name TEXT NOT NULL,
    secret_uuid TEXT NOT NULL,
    net_mode TEXT NOT NULL CHECK (net_mode IN ('net', 'none')),
    mac TEXT,
    state TEXT NOT NULL CHECK (state IN ('creating', 'running', 'destroying', 'gone')),
    created REAL NOT NULL,
    ended REAL
);
-- 0.6.0 (Make template): Herkunft je Kopie und unfertige Kopien. Eigene Tabellen, damit 0.5.x
-- die Registry weiter öffnen kann (SELECT * FROM bases bleibt gleich). Schlüssel vol_name wird
-- nie wiederverwendet (Versionsnummern steigen immer).
CREATE TABLE IF NOT EXISTS origins (
    vol_name TEXT PRIMARY KEY,
    vault TEXT NOT NULL,
    vault_uuid TEXT,
    created REAL NOT NULL,
    size INTEGER
);
CREATE TABLE IF NOT EXISTS pending (
    vol_name TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    vault TEXT NOT NULL,
    started REAL NOT NULL
);
"""


@dataclass
class Base:
    id: int
    name: str
    version: int
    vol_name: str
    vol_path: str
    sha256: str
    src_uuid: str
    firmware: str
    created: float
    retired: int
    damaged: int = 0


@dataclass
class Origin:
    vol_name: str
    vault: str
    vault_uuid: Optional[str]
    created: float
    size: Optional[int]


@dataclass
class Pending:
    vol_name: str
    name: str
    version: int
    vault: str
    started: float


@dataclass
class Temp:
    name: str
    uuid: str
    base_id: int
    overlay_name: str
    secret_uuid: str
    net_mode: str
    mac: Optional[str]
    state: str
    created: float
    ended: Optional[float]


class Registry:
    """Eine SQLite-Verbindung je Thread (sqlite3 erlaubt keine Thread-übergreifende Nutzung).

    Die GUI ruft Evox-Methoden aus Arbeits-Threads auf; WAL + flock (lock.py) regeln die
    Nebenläufigkeit zwischen den Verbindungen. close() schließt die Verbindung des
    aufrufenden Threads.
    """

    def __init__(self, path: Path):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = path
        self._local = threading.local()
        new = not path.exists()
        db = self.db
        if new:
            os.chmod(path, 0o600)
        db.executescript(_SCHEMA)
        row = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is not None and int(row[0]) > SCHEMA_VERSION:
            raise RuntimeError(f"Registry schema {row[0]} is newer than this program ({SCHEMA_VERSION}).")
        # v1 → v2: Spalte damaged (Prüfsumme abweichend → keine neuen Starts)
        if "damaged" not in {r[1] for r in db.execute("PRAGMA table_info(bases)")}:
            db.execute("ALTER TABLE bases ADD COLUMN damaged INTEGER NOT NULL DEFAULT 0")
        db.execute("INSERT OR REPLACE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))

    @property
    def db(self) -> sqlite3.Connection:
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(str(self.path), isolation_level=None, timeout=30)
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA journal_mode = WAL")
            self._local.db = db
        return db

    def close(self):
        db = getattr(self._local, "db", None)
        if db is not None:
            db.close()
            self._local.db = None

    # Basen
    def next_base_version(self, name: str) -> int:
        """Versionen steigen immer, auch nach Entfernen (Nummer wird nie wiederverwendet)."""
        row = self.db.execute("SELECT MAX(version) FROM bases WHERE name=?", (name,)).fetchone()
        old = self.db.execute("SELECT value FROM meta WHERE key=?", (f"max_version:{name}",)).fetchone()
        return max(row[0] or 0, int(old[0]) if old else 0) + 1

    def add_base(self, name, version, vol_name, vol_path, sha256, src_uuid, firmware="bios") -> int:
        cur = self.db.execute(
            "INSERT INTO bases (name, version, vol_name, vol_path, sha256, src_uuid, firmware, created)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (name, version, vol_name, vol_path, sha256, src_uuid, firmware, time.time()))
        return cur.lastrowid

    # Make template: Version reservieren (pending), danach in einem Schritt eintragen (commit)
    def add_pending(self, vol_name, name, version, vault):
        """Unfertige Kopie merken; Versionsnummer gilt ab hier als vergeben (auch nach Absturz)."""
        db = self.db
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("INSERT INTO pending VALUES (?,?,?,?,?)", (vol_name, name, version, vault, time.time()))
            old = db.execute("SELECT value FROM meta WHERE key=?", (f"max_version:{name}",)).fetchone()
            db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)",
                       (f"max_version:{name}", str(max(version, int(old[0]) if old else 0))))
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise

    def pending(self) -> list:
        return [Pending(*r) for r in self.db.execute("SELECT * FROM pending ORDER BY started")]

    def drop_pending(self, vol_name: str):
        self.db.execute("DELETE FROM pending WHERE vol_name=?", (vol_name,))

    def commit_template(self, name, version, vol_name, vol_path, sha256, src_uuid, firmware,
                        vault, size) -> int:
        """Atomar: unfertige Kopie austragen, Kopie + Herkunft eintragen (alles oder nichts)."""
        db = self.db
        db.execute("BEGIN IMMEDIATE")
        try:
            now = time.time()
            db.execute("DELETE FROM pending WHERE vol_name=?", (vol_name,))
            cur = db.execute(
                "INSERT INTO bases (name, version, vol_name, vol_path, sha256, src_uuid, firmware, created)"
                " VALUES (?,?,?,?,?,?,?,?)", (name, version, vol_name, vol_path, sha256, src_uuid, firmware, now))
            db.execute("INSERT OR REPLACE INTO origins VALUES (?,?,?,?,?)", (vol_name, vault, src_uuid, now, size))
            db.execute("COMMIT")
            return cur.lastrowid
        except BaseException:
            db.execute("ROLLBACK")
            raise

    def origin(self, vol_name: str) -> Optional[Origin]:
        r = self.db.execute("SELECT * FROM origins WHERE vol_name=?", (vol_name,)).fetchone()
        return Origin(*r) if r else None

    def origins(self) -> list:
        """Herkunft aller vorhandenen Kopien (Einträge ohne Kopie, z. B. nach Entfernen mit 0.5.x, zählen nicht)."""
        return [Origin(*r) for r in self.db.execute(
            "SELECT o.* FROM origins o JOIN bases b ON b.vol_name = o.vol_name ORDER BY o.created")]

    def bases(self, include_retired=False) -> list:
        q = "SELECT * FROM bases" + ("" if include_retired else " WHERE retired=0") + " ORDER BY name, version"
        return [Base(*r) for r in self.db.execute(q)]

    def base(self, base_id: int) -> Optional[Base]:
        r = self.db.execute("SELECT * FROM bases WHERE id=?", (base_id,)).fetchone()
        return Base(*r) if r else None

    def latest_base(self, name: str) -> Optional[Base]:
        r = self.db.execute("SELECT * FROM bases WHERE name=? AND retired=0 ORDER BY version DESC LIMIT 1",
                            (name,)).fetchone()
        return Base(*r) if r else None

    def retire_base(self, base_id: int):
        self.db.execute("UPDATE bases SET retired=1 WHERE id=?", (base_id,))

    def set_damaged(self, base_id: int):
        self.db.execute("UPDATE bases SET damaged=1 WHERE id=?", (base_id,))

    def remove_base(self, base_id: int):
        """Eintrag löschen (mit Protokollzeilen beendeter Wegwerf-VMs dieser Kopie); höchste Version merken."""
        b = self.base(base_id)
        if b is None:
            return
        db = self.db
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute("SELECT COUNT(*) FROM temps WHERE base_id=? AND state!='gone'", (base_id,)).fetchone()[0]:
                raise RuntimeError(f"{b.name} v{b.version} is still used by a disposable VM.")
            db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)",
                       (f"max_version:{b.name}", str(self.next_base_version(b.name) - 1)))
            db.execute("DELETE FROM temps WHERE base_id=? AND state='gone'", (base_id,))
            db.execute("DELETE FROM bases WHERE id=?", (base_id,))
            db.execute("DELETE FROM origins WHERE vol_name=?", (b.vol_name,))
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise

    # Temp-VMs
    def add_temp(self, name, uuid, base_id, overlay_name, secret_uuid, net_mode, mac):
        # Namen werden wiederverwendet (DISPOSABLE-EMAIL-01): alte Einträge 'gone' umbenennen, Protokoll bleibt
        self.db.execute("UPDATE temps SET name = name || '#' || uuid WHERE name=? AND state='gone'", (name,))
        self.db.execute(
            "INSERT INTO temps (name, uuid, base_id, overlay_name, secret_uuid, net_mode, mac, state, created)"
            " VALUES (?,?,?,?,?,?,?,'creating',?)",
            (name, uuid, base_id, overlay_name, secret_uuid, net_mode, mac, time.time()))

    def set_state(self, name: str, state: str):
        ended = time.time() if state == "gone" else None
        self.db.execute("UPDATE temps SET state=?, ended=COALESCE(?, ended) WHERE name=?", (state, ended, name))

    def temp(self, name: str) -> Optional[Temp]:
        r = self.db.execute("SELECT * FROM temps WHERE name=?", (name,)).fetchone()
        return Temp(*r) if r else None

    def active_temps(self) -> list:
        return [Temp(*r) for r in self.db.execute("SELECT * FROM temps WHERE state!='gone' ORDER BY created")]

    def temps_using_base(self, base_id: int) -> int:
        return self.db.execute("SELECT COUNT(*) FROM temps WHERE base_id=? AND state!='gone'",
                               (base_id,)).fetchone()[0]
