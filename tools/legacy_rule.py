#!/usr/bin/python3 -I
"""Regel für Altlasten im Pool default (von cleanup-legacy.sh benutzt, Unit-Test tests/test_legacy_rule.py).

Eine Datei ist nur dann Altlast, wenn ALLE Bedingungen zutreffen:
  * liegt direkt im Pool-Ordner (kein Unterordner), Name == Dateiname
  * Name beginnt mit "DISPOSABLE-"
  * endet auf ".running" mit Größe 0 und belegt 0  ODER  auf ".qcow2" mit belegt < 1 MiB
  * Pfad wird von keiner definierten VM benutzt (Disk, Backing-Kette, NVRAM)
TEMPLATE-*, VAULT-* und alles andere: nie.

  legacy_rule.py vol < vol-dumpxml            -> "name<TAB>pfad<TAB>groesse<TAB>belegt"
  legacy_rule.py classify POOLDIR PROTLISTE < TSV
                                              -> je Zeile "DEL|KEEP<TAB>name<TAB>pfad<TAB>groesse<TAB>belegt<TAB>grund"
"""
import os
import sys
import xml.etree.ElementTree as ET

PREFIX = "DISPOSABLE-"
MAX_QCOW2_ALLOC = 1024 * 1024   # belegt unter 1 MiB


def classify(name, path, size, alloc, pool_dir, protected):
    """-> (True, grund) wenn löschbar, sonst (False, grund)."""
    if not name or "/" in name or os.path.basename(path) != name:
        return False, "name/path mismatch"
    if os.path.normpath(os.path.dirname(path)) != os.path.normpath(pool_dir):
        return False, "not directly in pool dir"
    if not name.startswith(PREFIX):
        return False, "not DISPOSABLE-*"
    if os.path.realpath(path) in protected or os.path.normpath(path) in protected:
        return False, "used by a defined VM"
    if name.endswith(".running"):
        if size == 0 and alloc == 0:
            return True, ".running, size 0"
        return False, ".running but not empty"
    if name.endswith(".qcow2"):
        if 0 <= alloc < MAX_QCOW2_ALLOC:
            return True, ".qcow2, allocated %d B < 1 MiB" % alloc
        return False, ".qcow2 with data (allocated >= 1 MiB)"
    return False, "other suffix"


def vol_from_xml(text):
    r = ET.fromstring(text)
    def num(tag):
        e = r.find(tag)
        if e is None or e.text is None:
            return -1
        mult = {"bytes": 1, "b": 1, "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3}.get(e.get("unit", "bytes"))
        return int(e.text.strip()) * mult if mult else -1
    return (r.findtext("name") or "", r.findtext("target/path") or "", num("capacity"), num("allocation"))


def main(argv):
    if len(argv) == 2 and argv[1] == "vol":
        print("\t".join(str(x) for x in vol_from_xml(sys.stdin.read())))
        return 0
    if len(argv) == 4 and argv[1] == "classify":
        pool_dir = argv[2]
        with open(argv[3], encoding="utf-8") as f:
            protected = {l.rstrip("\n") for l in f if l.strip()}
        for line in sys.stdin:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 4:
                continue
            name, path, size, alloc = parts
            try:
                size, alloc = int(size), int(alloc)
            except ValueError:
                ok, why = False, "size unknown"
            else:
                ok, why = classify(name, path, size, alloc, pool_dir, protected)
            print("\t".join([("DEL" if ok else "KEEP"), name, path, str(size), str(alloc), why]))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
