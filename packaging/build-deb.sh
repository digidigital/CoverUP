#!/usr/bin/env bash
# Build a self-contained .deb from the PyInstaller one-dir output.
#
# The package bundles its own Python, Tcl/Tk and libraries (apt cannot satisfy
# pypdfium2 / FreeSimpleGUI), and installs system-wide so the app shows up in
# the application menu for all users:
#   /opt/coverup/                              -> the PyInstaller bundle
#   /usr/bin/coverup                           -> symlink to the bundle entry
#   /usr/share/applications/coverup.desktop    -> menu launcher
#   /usr/share/icons/hicolor/scalable/apps/coverup.svg
#
# Usage: packaging/build-deb.sh <version> <pyinstaller-dist-dir> [output-dir]
#   e.g. packaging/build-deb.sh 0.8.0 dist/coverup dist-deb
set -euo pipefail

VERSION="${1:?version required (e.g. 0.8.0)}"
DIST="${2:?PyInstaller dist/coverup dir required}"
OUTDIR="${3:-.}"
ARCH="$(dpkg --print-architecture)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

[ -x "$DIST/coverup" ] || { echo "error: $DIST/coverup not found or not executable" >&2; exit 1; }

PKG="$(mktemp -d)/coverup_${VERSION}_${ARCH}"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" \
  "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/scalable/apps" \
  "$PKG/usr/share/doc/coverup"

cp -r "$DIST" "$PKG/opt/coverup"
ln -sf /opt/coverup/coverup "$PKG/usr/bin/coverup"
cp "$ROOT/appimage/coverup.desktop" "$PKG/usr/share/applications/coverup.desktop"
cp "$ROOT/CoverUP.svg" "$PKG/usr/share/icons/hicolor/scalable/apps/coverup.svg"
cp "$ROOT/LICENSE" "$PKG/usr/share/doc/coverup/copyright"

ISIZE="$(du -sk "$PKG" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<EOF
Package: coverup
Version: ${VERSION}
Section: graphics
Priority: optional
Architecture: ${ARCH}
Maintainer: digidigital <support@digidigital.de>
Installed-Size: ${ISIZE}
Depends: libc6
Homepage: https://coverup.digidigital.de
Description: PDF and image redaction tool
 CoverUP redacts sensitive information in PDF documents and images by
 drawing black or white bars over content and flattening pages to images,
 which prevents the original text from being copied or indexed.
 .
 Self-contained build: bundles its own Python, Tcl/Tk and libraries.
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -f /usr/share/icons/hicolor 2>/dev/null || true
fi
exit 0
EOF

cat > "$PKG/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
exit 0
EOF
chmod 0755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"

mkdir -p "$OUTDIR"
OUT="$OUTDIR/coverup_${VERSION}_${ARCH}.deb"
fakeroot dpkg-deb --build "$PKG" "$OUT"
echo "Built: $OUT"
