#!/bin/bash
# setup-evoxd.sh – legt den EVOX-Speicher außerhalb von Home an (ENTSCHEIDUNGEN.md §20.20).
#
#   tools/setup-evoxd.sh               Probelauf (Standard): prüft und zeigt nur an.
#   sudo tools/setup-evoxd.sh --apply  Echter Lauf: legt die Ordner an.
#
# Ergebnis: /srv/evoxd, /srv/evoxd/templates, /srv/evoxd/overlays – je root:root 0711.
# (libvirt/QEMU brauchen nur Durchgang; Template-Kopien root 0444, Overlays verwaltet libvirt.)
# Danach legt `evoxd setup` die Pools evoxd-templates und evoxd-overlays auf diesen Ordnern an.
# Kein Netzzugriff, keine Änderung außerhalb von /srv/evoxd.
set -euo pipefail
export LC_ALL=C
umask 022
ulimit -c 0

BASE=/srv
D=$BASE/evoxd
SUBS=(templates overlays)
MODE=0711
MIN_FREE_GB=100

APPLY=0
case "${1:-}" in
  "") ;;
  --apply) APPLY=1 ;;
  -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
  *) echo "Unknown option: $1 (use --apply or nothing)" >&2; exit 2 ;;
esac
if [ "$APPLY" = 1 ] && [ "$(id -u)" != 0 ]; then
  echo "--apply needs root: sudo $0 --apply" >&2; exit 2
fi
say() { printf '%s\n' "$*"; }
fail() { say "ABORT: $*"; exit 3; }

say "EVOX setup-evoxd – mode: $([ "$APPLY" = 1 ] && echo APPLY || echo 'DRY RUN (nothing is changed)')"

# Prüfungen (nur lesend)
[ -d "$BASE" ] && [ ! -L "$BASE" ] || fail "$BASE missing or a symlink"
case "$(realpath -- "$BASE")/" in /home/*) fail "$BASE resolves into /home" ;; esac
free=$(df -BG --output=avail -- "$BASE" | tail -n1 | tr -dc 0-9)
say "free space on $BASE: ${free} GB ($(df --output=source,target -- "$BASE" | tail -n1))"
[ -n "$free" ] || fail "cannot read free space on $BASE"
[ "$free" -ge "$MIN_FREE_GB" ] || fail "less than $MIN_FREE_GB GB free on $BASE"

PLAN=()
for p in "$D" "${SUBS[@]/#/$D/}"; do
  if [ -L "$p" ]; then fail "$p is a symlink"; fi
  if [ -e "$p" ]; then
    [ -d "$p" ] || fail "$p exists and is not a directory"
    st=$(stat -c '%U:%G %a' -- "$p")
    say "exists: $p ($st)"
    [ "$st" = "root:root ${MODE#0}" ] || PLAN+=("chown root:root $p; chmod $MODE $p")
  else
    PLAN+=("install -d -o root -g root -m $MODE $p")
  fi
done
if [ -d "$D" ]; then
  extra=$(find "$D" -mindepth 1 -maxdepth 1 $(printf -- '! -name %s ' "${SUBS[@]}") -print | head -n 5)
  [ -z "$extra" ] || fail "unexpected entries in $D: $extra"
fi

if [ "${#PLAN[@]}" = 0 ]; then say "Nothing to do – $D is ready."; exit 0; fi
say "Planned:"; for c in "${PLAN[@]}"; do say "  $c"; done
if [ "$APPLY" = 0 ]; then say "Dry run finished – nothing was changed. Real run: sudo $0 --apply"; exit 0; fi

for p in "$D" "${SUBS[@]/#/$D/}"; do
  if [ -d "$p" ]; then chown root:root -- "$p"; chmod "$MODE" -- "$p"
  else install -d -o root -g root -m "$MODE" -- "$p"; fi
done
for p in "$D" "${SUBS[@]/#/$D/}"; do say "ready: $(stat -c '%A %U:%G %n' -- "$p")"; done
