#!/bin/bash
# Baut das .deb im Labor (ohne root, fakeroot). Aufruf: build-deb.sh <ausgabeordner>
set -euo pipefail
R=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:?Ausgabeordner}
V=$(python3 -I -c "import sys; sys.path.insert(0,'$R/src'); import evoxd; print(evoxd.__version__)")
S=$(mktemp -d "$OUT/stage.XXXXXX"); chmod 0755 "$S"
umask 022
install -d "$S/DEBIAN" "$S/usr/bin" "$S/usr/lib/python3/dist-packages" "$S/usr/lib/systemd/system" \
           "$S/usr/share/applications" "$S/usr/share/icons/hicolor/scalable/apps" "$S/usr/share/doc/evoxd/manual" "$S/usr/share/man/man1"
cp -r "$R/src/evoxd" "$S/usr/lib/python3/dist-packages/"
find "$S/usr/lib/python3/dist-packages" -name __pycache__ -prune -exec rm -r {} +
find "$S/usr/lib/python3/dist-packages" -type f -exec chmod 0644 {} +
printf '#!/usr/bin/python3 -I\nimport sys\nfrom evoxd.cli import main\nsys.exit(main())\n' > "$S/usr/bin/evoxd"
printf '#!/usr/bin/python3 -I\nimport sys\nfrom evoxd.gui import main\nsys.exit(main())\n' > "$S/usr/bin/evoxd-gui"
chmod 0755 "$S/usr/bin/"*
install -m 0644 "$R/packaging/evoxd-netguard.service" "$S/usr/lib/systemd/system/"
install -m 0644 "$R/packaging/evoxd.desktop" "$S/usr/share/applications/"
install -m 0644 "$R/packaging/icons/evoxd.svg" "$S/usr/share/icons/hicolor/scalable/apps/"
install -m 0644 "$R/packaging/copyright" "$S/usr/share/doc/evoxd/"
install -m 0644 "$R/docs/ARCHITEKTUR-V1.md" "$S/usr/share/doc/evoxd/"
for f in "$R"/docs/manual/*.??.html "$R"/docs/manual/*.??.md; do install -m 0644 "$f" "$S/usr/share/doc/evoxd/manual/"; done
gzip -9n -c "$R/packaging/changelog" > "$S/usr/share/doc/evoxd/changelog.gz"
gzip -9n -c "$R/packaging/evoxd.1" > "$S/usr/share/man/man1/evoxd.1.gz"
ln -s evoxd.1.gz "$S/usr/share/man/man1/evoxd-gui.1.gz"
for f in postinst prerm postrm; do install -m 0755 "$R/packaging/debian/$f" "$S/DEBIAN/"; done
SIZE=$(du -sk --exclude=DEBIAN "$S" | cut -f1)
sed -e "s/@VERSION@/$V/" -e "s/@SIZE@/$SIZE/" "$R/packaging/debian/control" > "$S/DEBIAN/control"
(cd "$S" && find usr -type f -exec md5sum {} + > DEBIAN/md5sums)
chmod 0644 "$S/DEBIAN/control" "$S/DEBIAN/md5sums"
fakeroot dpkg-deb --build --root-owner-group -Zxz "$S" "$OUT/evoxd_${V}_all.deb" >/dev/null
find "$S" -depth -delete
echo "$OUT/evoxd_${V}_all.deb"
