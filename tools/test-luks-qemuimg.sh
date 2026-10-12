#!/bin/bash
# Echter qemu-img-Test für den flüchtigen LUKS-Schlüssel (evoxd storage.new_passphrase).
# Nur im Labor (/srv/evox-testlab), als Benutzer, ohne libvirt. Aufräumen am Ende.
# Testschlüssel stehen nur in Variablen/Befehlszeile dieses Laufs (Wegwerf), nie in Dateien.
set -uo pipefail
ulimit -c 0
R=$(cd "$(dirname "$0")/.." && pwd)
LAB=/srv/evox-testlab
D=$(mktemp -d "$LAB/luks-test.XXXXXX")
trap 'rm -f "$D"/*.qcow2 "$D"/*.out; rmdir "$D"; unset K W' EXIT
T="timeout 20"
FAIL=0
ok()  { echo "PASS $1"; }
bad() { echo "FAIL $1"; FAIL=1; }
rc124() { [ "$1" -eq 124 ] && { echo "ABBRUCH: Zeitlimit ($2)"; exit 124; }; }

K=$(PYTHONPATH="$R/src" python3 -I -c 'import sys; sys.path.insert(0, sys.argv[1]); from evoxd import storage; print(storage.new_passphrase().decode())' "$R/src")
W=$(PYTHONPATH="$R/src" python3 -I -c 'import sys; sys.path.insert(0, sys.argv[1]); from evoxd import storage; print(storage.new_passphrase().decode())' "$R/src")
[[ "$K" =~ ^[0-9a-f]{64}$ ]] && ok "Schluesselformat 64 Hex (256 Bit)" || bad "Schluesselformat"

$T qemu-img create -q -f qcow2 "$D/base.qcow2" 64M; rc=$?; rc124 $rc base
[ $rc -eq 0 ] || bad "Basis anlegen rc=$rc"

# 1) neues Format: Overlay wie libvirt (encrypt.format=luks, key-secret, Backing qcow2)
$T qemu-img create -q -f qcow2 --object "secret,id=sec0,data=$K" \
   -o encrypt.format=luks,encrypt.key-secret=sec0 -b "$D/base.qcow2" -F qcow2 "$D/ov.qcow2" >"$D/c.out" 2>&1
rc=$?; rc124 $rc create
[ $rc -eq 0 ] && ok "Overlay mit Hex-Schluessel erzeugt" || { bad "Overlay erzeugen rc=$rc"; head -3 "$D/c.out"; }

$T qemu-img info --output=json "$D/ov.qcow2" >"$D/i.out" 2>&1; rc=$?; rc124 $rc info
python3 -I - "$D/i.out" "$D/base.qcow2" <<'EOF' && ok "info: encrypted=true, luks, Backing=base" || bad "qemu-img info"
import json, sys
i = json.load(open(sys.argv[1]))
assert i["encrypted"] is True, i
assert i["format-specific"]["data"]["encrypt"]["format"] == "luks", i
assert i["backing-filename"] == sys.argv[2], i
EOF

# 2) richtiger Schlüssel öffnet, falscher scheitert
open_ov() { $T qemu-img check -q --object "secret,id=sec0,data=$1" \
  --image-opts "driver=qcow2,file.filename=$D/ov.qcow2,encrypt.key-secret=sec0" >"$D/o.out" 2>&1; }
open_ov "$K"; rc=$?; rc124 $rc check-ok
[ $rc -eq 0 ] && ok "richtiger Schluessel oeffnet" || { bad "richtiger Schluessel rc=$rc"; head -3 "$D/o.out"; }
open_ov "$W"; rc=$?; rc124 $rc check-wrong
[ $rc -ne 0 ] && grep -qi "invalid password\|no.*key" "$D/o.out" && ok "falscher Schluessel scheitert (rc=$rc)" \
  || { bad "falscher Schluessel rc=$rc"; head -3 "$D/o.out"; }

# 3) Gegenprobe alter Fehler: 32 Rohbytes (kein UTF-8) -> qemu-img lehnt ab
RAW=$(python3 -I -c 'import base64, os; print(base64.b64encode(b"\xff" + os.urandom(31)).decode())')
$T qemu-img create -q -f qcow2 --object "secret,id=sec0,data=$RAW,format=base64" \
   -o encrypt.format=luks,encrypt.key-secret=sec0 -b "$D/base.qcow2" -F qcow2 "$D/raw.qcow2" >"$D/r.out" 2>&1
rc=$?; rc124 $rc create-raw; unset RAW
[ $rc -ne 0 ] && grep -q "not valid UTF-8" "$D/r.out" && ok "Rohbytes scheitern wie auf dem Host (not valid UTF-8)" \
  || { bad "Gegenprobe Rohbytes rc=$rc"; head -3 "$D/r.out"; }

[ $FAIL -eq 0 ] && echo "ERGEBNIS: PASS" || echo "ERGEBNIS: FEHLGESCHLAGEN"
exit $FAIL
