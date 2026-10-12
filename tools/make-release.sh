#!/bin/bash
# Erzeugt dist/ mit .deb und SHA256SUMS aus dem Release-Ordner. Lokal, kein Netz, kein sudo.
# Aufruf: tools/make-release.sh [Version]   (ohne Angabe: __version__)
set -euo pipefail
R=$(cd "$(dirname "$0")/.." && pwd); cd "$R"
V=${1:-$(python3 -I -c "import sys; sys.path.insert(0,'src'); import evoxd; print(evoxd.__version__)")}
SRC=${EVOX_RELEASE_OUT:-/srv/evox-testlab/release}
D="$SRC/evoxd_${V}_all.deb"
[ -f "$D" ] || { echo "fehlt: $D" >&2; exit 2; }
mkdir -p dist
cp -- "$D" dist/
( cd dist && sha256sum "evoxd_${V}_all.deb" > SHA256SUMS && sha256sum -c SHA256SUMS )
echo "dist/ fertig: evoxd_${V}_all.deb + SHA256SUMS"
