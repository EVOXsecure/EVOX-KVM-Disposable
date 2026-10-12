#!/bin/bash
# Erzeugt eine bereinigte Kopie des Tags (Standard v1.0.1) nach ~/EVOX-publish/ mit EINEM Anfangs-Commit.
# Nur lesend vom Projekt. Kein Remote, kein push, nichts wird gelöscht.
# Aufruf: tools/export-clean.sh [--dry-run] [Tag]
set -euo pipefail
DRY=""; [ "${1:-}" = --dry-run ] && { DRY=1; shift; }
TAG=${1:-v1.0.1}
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
DEST=${EVOX_PUBLISH_DIR:-$HOME/EVOX-publish}
# Ausgeschlossene Pfade (Entwicklungsnotizen mit Hostdaten, Altbestand, Backups, Claude-Konfiguration)
EXC='^(docs/archiv/|docs/(FORTSCHRITT|STATUS|UEBERGABE|MASTER-PROMPT|TECHNISCHER_IST-STAND|ENTSCHEIDUNGEN|HOST-SCHRITTE|KURZ|ARBEITSREGELN|LASTENHEFT|PLAN-V1|ARCHITEKTUR-V1|FLATPAK-NOTIZ)\.md$|docs/themen/|docs/icons-preview|\.claude/|CLAUDE\.md$|tools/(backup-projekt|backup-check|status|statusline|cleanup-legacy)\.sh$)'
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null || { echo "Tag $TAG fehlt" >&2; exit 2; }
echo "Quelle: $TAG  Ziel: $DEST"
mapfile -t KEEP < <(git ls-tree -r --name-only "$TAG" | grep -Ev "$EXC")
echo "Dateien: ${#KEEP[@]} von $(git ls-tree -r --name-only "$TAG" | wc -l)"
[ -z "$DRY" ] || { echo "[dry-run] ausgeschlossen:"; git ls-tree -r --name-only "$TAG" | grep -E "$EXC" | sed 's/^/  - /'; exit 0; }
[ ! -e "$DEST" ] || [ -z "$(ls -A "$DEST")" ] || { echo "Ziel nicht leer: $DEST (bitte selbst entscheiden)" >&2; exit 3; }
mkdir -p "$DEST"
git archive "$TAG" -- "${KEEP[@]}" | tar -x -C "$DEST"
# neue Dateien aus dem Arbeitsstand (falls vorhanden)
for f in README.md SECURITY.md LICENSE .gitignore tools/make-release.sh tools/export-clean.sh; do
  [ -f "$f" ] && { mkdir -p "$DEST/$(dirname "$f")"; cp -- "$f" "$DEST/$f"; }
done
cd "$DEST"
git init -q -b main
git -c user.name="EVOXsecure" -c user.email="341397211+EVOXsecure@users.noreply.github.com" add -A
git -c user.name="EVOXsecure" -c user.email="341397211+EVOXsecure@users.noreply.github.com" commit -q -m "EVOX KVM DISPOSABLE $TAG"
echo "fertig: $DEST (1 Commit, kein Remote)"
