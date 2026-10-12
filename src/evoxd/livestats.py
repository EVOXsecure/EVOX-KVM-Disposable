"""Live-Werte laufender Wegwerf-VMs (A3, 0.7.0): nur lesend aus libvirt-Statistiken (hv.domain_stats).

Eingabe je VM ist das Roh-Wörterbuch von libvirt (domainListGetStats: "cpu.time", "balloon.*",
"net.N.rx.bytes", "block.N.*"). Fehlt ein Wert, wird er ehrlich als None (Anzeige "n/a") geführt,
nie geschätzt ohne Kennzeichnung. Keine GTK-Abhängigkeit (testbar ohne Display).
"""
import collections
import math
import re
import time

from . import capacity, config

# RAM-Ampel (0.7.1, Auftrag A3b): grün bis 60 %, gelb bis 85 %, rot darüber; "low" (überdimensioniert) < 30 %
RAM_OK_MAX_PCT = 60
RAM_HIGH_MAX_PCT = 85
RAM_LOW_PCT = 30
RAM_FULL_EVENT_PCT = 95      # Zähler "RAM full": Gast über 95 % (je Übergang einmal gezählt, nur echte Gastwerte)
CPU_HISTORY_LEN = 300        # Sparkline: höchstens 300 Werte (= 5 min im 1-s-Live-Takt, 0.7.2), nur im Speicher
HINT_HEADROOM = 1.25         # 0.7.3 Empfehlung: Spitze + 25 %, aufgerundet auf das 256-MiB-Raster (0.7.1: +30 %, GiB)
HINT_MIN_MIB = config.MIN_MEMORY_MIB   # 0.7.3: kleinste Empfehlung 1 GB (0.7.1: 2 GiB)
HINT_MORE_PCT = RAM_HIGH_MAX_PCT       # 0.7.3: Spitze über 85 % des zugewiesenen RAM → immer „mehr RAM wählen“


def ram_level(pct):
    """'low' | 'ok' | 'high' | 'full' | None (unbekannt)."""
    if pct is None:
        return None
    if pct > RAM_HIGH_MAX_PCT:
        return "full"
    if pct > RAM_OK_MAX_PCT:
        return "high"
    if pct < RAM_LOW_PCT:
        return "low"
    return "ok"


def fmt_runtime(seconds) -> str:
    """Laufzeit minutengenau (Anzeige ändert sich höchstens einmal pro Minute)."""
    if seconds is None or seconds < 0:
        return "n/a"
    m = int(seconds // 60)
    if m < 1:
        return "<1 min"
    if m < 60:
        return f"{m} min"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h} h {m:02d} min"
    d, h = divmod(h, 24)
    return f"{d} d {h} h"


def fmt_bytes(b) -> str:
    """Kompakte Größe (binär), eine Nachkommastelle ab MiB, Dezimalzeichen der Systemsprache."""
    if b is None:
        return "n/a"
    b = max(0, int(b))
    for unit, f in (("GiB", 2**30), ("MiB", 2**20)):
        if b >= f:
            return f"{capacity.fmt_dec(b / f)} {unit}"   # Dezimalzeichen wie übrige Anzeige (LC_NUMERIC)
    return f"{b // 1024} KiB" if b >= 1024 else f"{b} B"


def _int(raw, key):
    v = raw.get(key)
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None


def _ram(raw, mem_mib):
    """(benutzt in Bytes, Größe in Bytes, geschätzt?) – Gaststatistik bevorzugt, sonst RSS als Schätzung."""
    cur = _int(raw, "balloon.current")                 # KiB, dem Gast zugeteilt
    size = cur * 1024 if cur else (mem_mib * 2**20 if mem_mib else None)
    avail = _int(raw, "balloon.available")
    free = _int(raw, "balloon.usable")
    if free is None:
        free = _int(raw, "balloon.unused")
    if avail and free is not None and free <= avail:
        return (avail - free) * 1024, avail * 1024, False
    rss = _int(raw, "balloon.rss")
    if rss and size:
        return min(rss * 1024, size), size, True       # Prozess-RSS enthält QEMU-Anteil → nur Schätzung
    return None, size, False


def _net(raw):
    """(rx, tx) über alle Schnittstellen; ('none', 'none') ohne Schnittstelle; (None, None) ohne Daten."""
    n = _int(raw, "net.count")
    if n is None:
        return None, None
    if n == 0:
        return "none", "none"
    rx = [_int(raw, f"net.{i}.rx.bytes") for i in range(n)]
    tx = [_int(raw, f"net.{i}.tx.bytes") for i in range(n)]
    if None in rx or None in tx:
        return None, None
    return sum(rx), sum(tx)


def _overlay(raw, with_capacity=False):
    """Belegte Größe der Overlay-Datei (geschriebene Daten der Sitzung); None, wenn nicht gefunden.
    with_capacity: (belegt, virtuelle Plattengröße) – Plattengröße None, wenn libvirt sie nicht liefert."""
    n = _int(raw, "block.count") or 0
    for i in range(n):
        path = raw.get(f"block.{i}.path")
        if isinstance(path, str) and path.startswith(config.OVERLAY_PATH + "/"):
            v = _int(raw, f"block.{i}.physical")
            v = v if v is not None else _int(raw, f"block.{i}.allocation")
            return (v, _int(raw, f"block.{i}.capacity") or None) if with_capacity else v
    return (None, None) if with_capacity else None


def purpose_of(name):
    """Zweck aus dem Namen DISPOSABLE-<ZWECK>-NN; None bei fremdem Schema."""
    m = re.fullmatch(r"DISPOSABLE-([A-Z0-9]{1,16})-[0-9]{2}", name or "")
    return m.group(1) if m else None


def fmt_ram_gb(mib) -> str:
    """0.7.3: RAM-Größe im 256-MiB-Raster als GB (1 GB = 1024 MiB) ohne überflüssige Nullen: 1 GB, 1,25 GB, 1,5 GB."""
    txt = capacity.fmt_dec(mib / 1024, 2)
    sep = capacity.fmt_dec(0.5)[1]
    if txt.endswith("0"):
        txt = txt[:-1]
    if txt.endswith(sep + "0"):
        txt = txt[:-2]
    return f"{txt} GB"


def fmt_gb1(mib) -> str:
    """0.7.4: EINE Formatfunktion für Kapazität und freien Platz: eine Nachkommastelle, Einheit GB (1 GB = 1024 MiB),
    z. B. „6,8 GB“. Nur das RAM-Feld im Startdialog zeigt zwei Stellen (0,25-GB-Raster, `fmt_ram_gb`)."""
    return f"{capacity.fmt_dec(mib / 1024)} GB"


def fmt_bytes_gb1(b) -> str:
    """Wie fmt_gb1, aus Bytes; None → „?“."""
    return "?" if b is None else fmt_gb1(b // 2**20)


def grid_floor_mib(mib) -> int:
    """Auf das 256-MiB-Raster abrunden (für Obergrenzen, z. B. Kapazität)."""
    return int(mib) // config.RAM_STEP_MIB * config.RAM_STEP_MIB


def suggest_mib(peak_bytes, max_mib=None) -> int:
    """0.7.3 Empfehlung: Spitze + 25 %, aufgerundet auf das nächste 0,25 GB (256 MiB), mind. 1 GB, nie über dem
    erlaubten Maximum (config.MAX_MEMORY_MIB bzw. max_mib, z. B. Kapazität). Ergebnis ist immer ein wählbarer Wert."""
    step = config.RAM_STEP_MIB * 2**20
    steps = math.ceil(peak_bytes * HINT_HEADROOM / step - 1e-6)
    hi = config.MAX_MEMORY_MIB if max_mib is None else max(HINT_MIN_MIB, grid_floor_mib(min(max_mib,
                                                                                       config.MAX_MEMORY_MIB)))
    return max(HINT_MIN_MIB, min(steps * config.RAM_STEP_MIB, hi))


def needs_more(peak_bytes, size_bytes) -> bool:
    """0.7.3: Spitze über HINT_MORE_PCT (85 %) des zugewiesenen RAM → Hinweis „mehr RAM wählen“."""
    return bool(peak_bytes and size_bytes and peak_bytes * 100 > HINT_MORE_PCT * size_bytes)


def more_mib(peak_bytes, size_mib, max_mib=None) -> int:
    """Empfehlung bei „mehr RAM“: Rechnung (suggest_mib), mindestens ein Rasterschritt über der jetzigen Größe."""
    hi = config.MAX_MEMORY_MIB if max_mib is None else max(HINT_MIN_MIB, grid_floor_mib(min(max_mib,
                                                                                       config.MAX_MEMORY_MIB)))
    up = grid_floor_mib(size_mib) + config.RAM_STEP_MIB
    return min(max(suggest_mib(peak_bytes, max_mib), up), hi)


def ram_hint(peak_bytes, size_bytes, full_count):
    """Hinweis beim Beenden (nur Information): (art, vorschlag_mib) mit art 'full' | 'high' | 'low' | 'ok';
    None ohne echte Gastwerte (dann wird nichts geraten). vorschlag_mib None = Größe passt.
    0.7.3: Vorschlag = suggest_mib (Spitze + 25 %, 256-MiB-Raster, mind. 1 GB); Spitze > 85 % → 'high' mit mehr RAM."""
    if not peak_bytes or not size_bytes or peak_bytes < 0 or size_bytes <= 0:
        return None
    pct = min(100, round(peak_bytes * 100 / size_bytes))
    size_mib = size_bytes // 2**20
    if full_count:
        return "full", more_mib(peak_bytes, size_mib)
    if needs_more(peak_bytes, size_bytes):
        return "high", more_mib(peak_bytes, size_mib)
    sug = suggest_mib(peak_bytes)
    if pct < RAM_LOW_PCT and sug < size_mib:
        return "low", sug
    return "ok", None


class LiveSampler:
    """Hält je VM den vorigen CPU-Stand und den Spitzenwert; liefert Anzeigewerte (Zahlen oder None)."""

    def __init__(self, clock=time.monotonic, wall=time.time):
        self.clock = clock
        self.wall = wall
        self._cpu = {}     # name -> (t, cpu_ns)
        self._peak = {}    # name -> höchster beobachteter RAM-Wert (Bytes)
        self._peak_t = {}  # name -> Uhrzeit (wall) der Spitze
        self._exact = {}   # name -> (höchster ECHTER Gastwert in Bytes, Gast-RAM in Bytes) – Grundlage für Hinweise
        self._full = {}    # name -> Anzahl "RAM full" (Gast über RAM_FULL_EVENT_PCT, je Übergang)
        self._full_on = {}  # name -> zuletzt über der Schwelle?
        self._hist = {}    # name -> deque der CPU-% (begrenzte Länge)
        self._ovl_peak = {}  # name -> höchste Overlay-Größe

    def _maps(self):
        return (self._cpu, self._peak, self._peak_t, self._exact, self._full, self._full_on, self._hist, self._ovl_peak)

    def forget(self, keep) -> dict:
        """Werte nicht mehr laufender VMs verwerfen; gibt deren Zusammenfassung zurück ({name: summary()})."""
        keep = set(keep)
        gone = {k: self.summary(k) for k in self._peak if k not in keep}
        for d in self._maps():
            for k in [k for k in d if k not in keep]:
                del d[k]
        return gone

    def summary(self, name) -> dict:
        """Grundlage für Hinweis und Zweck-Statistik: nur echte Gastwerte (peak None ohne echte Werte)."""
        peak, size = self._exact.get(name, (None, None))
        return {"peak": peak, "size": size, "full": self._full.get(name, 0)}

    def sample(self, name, raw, mem_mib=None, vcpus=None, created=None) -> dict:
        raw = raw if isinstance(raw, dict) else {}
        out = {"runtime": (self.wall() - created) if created else None}
        used, size, est = _ram(raw, mem_mib)
        out.update(ram_used=used, ram_size=size, ram_est=est, ram_pct=None, peak=None, peak_pct=None)
        if used is not None and size:
            out["ram_pct"] = min(100, round(used * 100 / size))
            if used > self._peak.get(name, -1):
                self._peak[name], self._peak_t[name] = used, self.wall()
            peak = self._peak[name]
            out["peak"], out["peak_pct"] = peak, min(100, round(peak * 100 / size))
            if not est:
                if used >= self._exact.get(name, (0, 0))[0]:
                    self._exact[name] = (used, size)
                over = used * 100 > RAM_FULL_EVENT_PCT * size
                if over and not self._full_on.get(name):
                    self._full[name] = self._full.get(name, 0) + 1
                self._full_on[name] = over
        out["peak_time"] = self._peak_t.get(name) if out["peak"] is not None else None
        out["full_count"] = self._full.get(name, 0)
        out["ram_level"] = ram_level(out["ram_pct"])
        cpu_ns, now = _int(raw, "cpu.time"), self.clock()
        out["cpu_pct"], out["cpu_wait"] = None, False
        if cpu_ns is not None:
            prev = self._cpu.get(name)
            if prev and now > prev[0] and cpu_ns >= prev[1]:
                n = vcpus if vcpus and vcpus > 0 else 1
                out["cpu_pct"] = min(100, round((cpu_ns - prev[1]) / ((now - prev[0]) * 1e9 * n) * 100))
            else:
                out["cpu_wait"] = True          # erster Messpunkt: Prozent erst ab dem nächsten Zyklus
            self._cpu[name] = (now, cpu_ns)
        hist = self._hist.setdefault(name, collections.deque(maxlen=CPU_HISTORY_LEN))
        if out["cpu_pct"] is not None:
            hist.append(out["cpu_pct"])
        out["cpu_hist"] = tuple(hist)
        out["rx"], out["tx"] = _net(raw)
        out["overlay"], out["disk_size"] = _overlay(raw, with_capacity=True)
        if out["overlay"] is not None:
            self._ovl_peak[name] = max(out["overlay"], self._ovl_peak.get(name, 0))
        out["overlay_peak"] = self._ovl_peak.get(name)
        return out
