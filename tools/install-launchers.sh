#!/bin/bash
# Legt Starter für EVOX GUI und Claude Code an (Menü + Schreibtisch). Kein sudo, nur unter $HOME.
#   tools/install-launchers.sh --dry-run   zeigt nur an
#   tools/install-launchers.sh             anlegen (idempotent)
#   tools/install-launchers.sh --remove    nur eigene Starter entfernen (Marke X-EVOX-Launcher)
# Logik in install_launchers.py (testbar ohne echte Programme). Gehört nicht ins evoxd-Paket.
set -euo pipefail
ulimit -c 0
exec /usr/bin/python3 -I "$(dirname "$(readlink -f "$0")")/install_launchers.py" "$@"
