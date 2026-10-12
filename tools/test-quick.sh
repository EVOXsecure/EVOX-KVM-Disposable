#!/bin/bash
# Schnelltest: nur Testdateien, deren Name oder Inhalt zum Stichwort passt.
# Volle Suite nur über tools/release.sh.
set -u
if [ $# -lt 1 ]; then
  echo "Nutzung: tools/test-quick.sh <Stichwort>   (z. B. theme, live, net)"
  exit 2
fi
cd "$(dirname "$0")/.." || exit 1
ulimit -c 0
kw="$1"
files=$( { ls tests/test_*.py | grep -i -- "$kw"; grep -il -- "$kw" tests/test_*.py; } 2>/dev/null | sort -u)
if [ -z "$files" ]; then echo "Keine Testdatei zu '$kw'."; exit 1; fi
mods=$(echo "$files" | sed 's#/#.#; s#\.py$##' | tr '\n' ' ')
export PYTHONPATH=src LC_ALL=C.UTF-8 LANG=C.UTF-8
# shellcheck disable=SC2086
timeout 600 python3 -m unittest -q $mods 2>&1 | tail -n 15
exit "${PIPESTATUS[0]}"
