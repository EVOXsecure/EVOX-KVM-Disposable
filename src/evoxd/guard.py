"""evoxd-netguard: Wächter der Netzsperre (läuft als root, systemd).

Aufgabe (ZUSATZ C5/C24): nft-Tabelle (N2) und Routing-Sperre (R) laden, im Betrieb
überwachen und bei Verlust der Tabelle sofort alle Ports der Bridge trennen (fail-closed).
Kein Steuerkanal nach außen: liest nur eigene Konstanten, schreibt nur die Statusdatei.
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time

from . import config
from .net import model

POLL_S = 0.5


def run(cmd, input_=None, check=True):
    r = subprocess.run(cmd, input=input_, capture_output=True, text=True, timeout=10)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {r.stderr.strip()}")
    return r.stdout


def _strip(obj):
    """nft-JSON ohne veränderliche Felder (Handles, Zähler)."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in ("handle", "packets", "bytes")}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


class Guard:
    def __init__(self, runner=run, status_path=config.GUARD_STATUS, clock=time.time, log=None):
        self.run = runner
        self.status_path = status_path
        self.clock = clock
        self.log = log or (lambda m: print(f"{time.time():.3f} {m}", flush=True))
        self.reference = None
        self.tripped = {}       # ifindex -> MAC der VM
        self.trips = 0
        self.last_trip = None
        self.last_reason = ""

    # ---- nft
    def table_snapshot(self):
        try:
            out = self.run(["nft", "-j", "list", "table", "inet", config.NFT_TABLE])
        except RuntimeError:
            return None
        items = json.loads(out).get("nftables", [])
        return _strip([i for i in items if "metainfo" not in i])

    def load_table(self):
        self.run(["nft", "-f", "-"], input_=model.nft_load_script())
        self.reference = self.table_snapshot()
        if not self.reference:
            raise RuntimeError("table not readable after loading.")

    def table_ok(self) -> bool:
        snap = self.table_snapshot()
        return snap is not None and snap == self.reference

    # ---- Routing-Sperre R
    def rules_present(self) -> set:
        rules = json.loads(self.run(["ip", "-j", "-4", "rule", "show"]) or "[]")
        return {(r.get("priority"), r.get("dst"), r.get("dstlen")) for r in rules
                if r.get("iif") == config.BRIDGE and r.get("action") == "prohibit"}

    def ensure_rules(self) -> bool:
        have = self.rules_present()
        ok = True
        for rule in model.route_rules():
            net, plen = rule["to"].split("/")
            if (rule["pref"], net, int(plen)) not in have:
                ok = False
                self.run(["ip", "-4", "rule", "add", "pref", str(rule["pref"]), "iif", rule["iif"],
                          "to", rule["to"], "prohibit"], check=False)
        return ok

    def ensure_no_ipv6(self) -> bool:
        p = f"/proc/sys/net/ipv6/conf/{config.BRIDGE}/disable_ipv6"
        if not os.path.exists(p):
            return True  # Bridge existiert noch nicht
        with open(p) as f:
            if f.read().strip() == "1":
                return True
        with open(p, "w") as f:
            f.write("1")
        return False

    # ---- Trennen (Bridge-Port-Sperre: Port-Zustand "disabled", Link bleibt oben)
    def ports(self) -> list:
        """Ports der Gast-Bridge mit MAC (ip) und Bridge-Zustand (bridge)."""
        try:
            links = json.loads(self.run(["ip", "-j", "link", "show", "master", config.BRIDGE], check=False) or "[]")
            states = json.loads(self.run(["bridge", "-j", "link", "show"], check=False) or "[]")
        except ValueError:
            return []
        st = {b.get("ifindex"): b.get("state") for b in states if b.get("master") == config.BRIDGE}
        for p in links:
            p["state"] = st.get(p.get("ifindex"), "unknown")
        return links

    def block_port(self, ifname: str):
        self.run(["bridge", "link", "set", "dev", ifname, "state", "0"], check=False)

    def cut(self, reason: str):
        t0 = self.clock()
        n = 0
        for p in self.ports():
            self.block_port(p["ifname"])
            mac = p.get("address", "")
            self.tripped[p["ifindex"]] = "52" + mac[2:] if mac.startswith("fe") else mac
            n += 1
        self.trips += 1
        self.last_trip = t0
        self.last_reason = reason
        self.log(f"CUT: {reason}; ports blocked: {n}; took {1000*(self.clock()-t0):.1f} ms")

    def enforce_tripped(self):
        present = {p["ifindex"]: p for p in self.ports()}
        for idx in list(self.tripped):
            if idx not in present:
                del self.tripped[idx]   # VM beendet
            elif present[idx].get("state") != "disabled":
                self.block_port(present[idx]["ifname"])
                self.log(f"port {present[idx]['ifname']} blocked again")

    # ---- Ablauf
    def check_once(self) -> dict:
        tbl = self.table_ok()
        if not tbl:
            self.cut("nft table missing or changed")
            try:
                self.load_table()
                tbl = self.table_ok()
                if tbl:
                    self.log("table reloaded; blocked ports stay blocked")
            except RuntimeError as e:
                self.log(f"ERROR while reloading: {e}")
            if not tbl:
                self.cut("table not restored – all ports blocked")
        rules = self.ensure_rules()
        v6 = self.ensure_no_ipv6()
        if not rules:
            self.log("routing lock restored")
        self.enforce_tripped()
        st = {"ts": self.clock(), "state": "ok" if tbl else "error", "table_ok": tbl,
              "rules_ok": True if rules else self.ensure_rules(), "ipv6_off": v6 or self.ensure_no_ipv6(),
              "tripped_macs": sorted(self.tripped.values()), "trips": self.trips,
              "last_trip": self.last_trip, "last_reason": self.last_reason, "pid": os.getpid()}
        self.write_status(st)
        return st

    def write_status(self, st: dict):
        tmp = self.status_path + ".tmp"
        os.makedirs(os.path.dirname(self.status_path), mode=0o755, exist_ok=True)
        with open(tmp, "w") as f:
            json.dump(st, f)
        os.chmod(tmp, 0o644)
        os.replace(tmp, self.status_path)


def _monitor(events: "queue.Queue"):
    """nft monitor: meldet jede Regeländerung sofort (flush, delete, Neustart nftables)."""
    while True:
        try:
            p = subprocess.Popen(["nft", "monitor", "ruleset"], stdout=subprocess.PIPE, text=True)
            for _line in p.stdout:
                events.put(1)
            p.wait()
        except OSError:
            pass
        events.put(1)
        time.sleep(0.2)


def main(argv=None):
    os.umask(0o022)
    g = Guard()
    g.load_table()
    g.ensure_rules()
    g.run(["ip", "link", "set", "dev", config.BRIDGE, "up"], check=False)
    g.log("guard started, table and routing lock loaded")
    events = queue.Queue()
    threading.Thread(target=_monitor, args=(events,), daemon=True).start()
    while True:
        try:
            g.check_once()
        except Exception as e:  # Wächter darf nicht sterben; systemd startet sonst neu
            g.log(f"ERROR: {e}")
        try:
            events.get(timeout=POLL_S)
            while not events.empty():
                events.get_nowait()
        except queue.Empty:
            pass


if __name__ == "__main__":
    sys.exit(main())
