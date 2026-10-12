#!/bin/bash
# Abschluss eines Abschnitts: Tests (C.UTF-8 + de_DE), .deb, lintian, desktop-file-validate, Backup, Meldung.
# Aufruf: tools/release.sh <Version> [--dry-run]   Kein sudo, kein Netz. Exit != 0 bei Fehlern.
set -uo pipefail
V=${1:?Version}; DRY=${2:-}
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
OUT=${EVOX_RELEASE_OUT:-/srv/evox-testlab/release}; FAIL=0; SUM=()
step() { echo "▶ $*"; }
run() { if [ "$DRY" = --dry-run ]; then echo "  [dry] $*"; else eval "$@"; fi; }
CUR=$(python3 -I -c "import sys; sys.path.insert(0,'src'); import evoxd; print(evoxd.__version__)")
[ "$CUR" = "$V" ] || { echo "Version $V != __version__ $CUR" >&2; [ "$DRY" = --dry-run ] || exit 2; }
for L in C.UTF-8 de_DE.UTF-8; do
  step "Tests $L"
  if [ "$DRY" = --dry-run ]; then echo "  [dry] LC_ALL=$L PYTHONPATH=src python3 -m unittest discover -s tests -t . -q | tail -15"
  else T=$(LC_ALL=$L PYTHONPATH=src python3 -m unittest discover -s tests -t . -q 2>&1); rc=$?; echo "$T" | tail -15
       SUM+=("Tests $L: rc=$rc $(echo "$T" | grep -E '^(OK|FAILED)' | tail -1)"); [ $rc -eq 0 ] || FAIL=1; fi
done
step ".deb bauen"; run "mkdir -p '$OUT' && packaging/build-deb.sh '$OUT' >/dev/null 2>&1 || FAIL=1"
if [ "$DRY" != --dry-run ]; then
  D=$(ls -t "$OUT"/*.deb 2>/dev/null | head -1); [ -n "$D" ] || { FAIL=1; D=/nonexistent; }
  SUM+=(".deb: $(basename "$D") sha256 $(sha256sum "$D" 2>/dev/null | cut -c1-12)")
fi
step "lintian + desktop-file-validate"
run "lintian \"\$D\" 2>&1 | head -10; [ -z \"\$(lintian \"\$D\" 2>&1)\" ] || FAIL=1"
run "desktop-file-validate packaging/evoxd.desktop || FAIL=1"
step "Backup"; run "tools/backup-projekt.sh '$V' 2>&1 | tail -4 || FAIL=1"
if [ "$DRY" != --dry-run ]; then
  SUM+=("Backup: $(ls -t "$HOME"/EVOX-Backups/*"$V".tar.gz 2>/dev/null | head -1 | xargs -r basename)")
  [ $FAIL -eq 0 ] && notify-send "CODE FERTIG" "$V ist fertig und wartet auf den Benutzer." 2>/dev/null
  echo "── Zusammenfassung $V ──"; printf '%s\n' "${SUM[@]}" | head -6; echo "Ergebnis: $([ $FAIL -eq 0 ] && echo PASS || echo FEHLGESCHLAGEN)"
fi
exit $FAIL
