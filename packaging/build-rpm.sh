#!/usr/bin/env bash
# Build a self-contained .rpm from the PyInstaller one-dir output, using fpm.
#
# Mirrors the .deb layout: the bundle (its own Python, Tcl/Tk and libraries)
# goes under /opt/coverup with a /usr/bin/coverup symlink, and the .desktop and
# icon under /usr/share so the app appears in the menu for all users.
#
# Usage: packaging/build-rpm.sh <version> <pyinstaller-dist-dir> [output-dir]
#   e.g. packaging/build-rpm.sh 0.8.0 dist/coverup dist-rpm
# Requires: fpm (and rpmbuild) on PATH.
set -euo pipefail

VERSION="${1:?version required (e.g. 0.8.0)}"
DIST="${2:?PyInstaller dist/coverup dir required}"
OUTDIR="${3:-.}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCH="${RPM_ARCH:-x86_64}"

[ -x "$DIST/coverup" ] || { echo "error: $DIST/coverup not found or not executable" >&2; exit 1; }

STAGE="$(mktemp -d)"
mkdir -p "$STAGE/opt" "$STAGE/usr/bin" \
  "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/scalable/apps" \
  "$STAGE/usr/share/doc/coverup"

cp -r "$DIST" "$STAGE/opt/coverup"
ln -sf /opt/coverup/coverup "$STAGE/usr/bin/coverup"
cp "$ROOT/appimage/coverup.desktop" "$STAGE/usr/share/applications/coverup.desktop"
cp "$ROOT/CoverUP.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/coverup.svg"
cp "$ROOT/LICENSE" "$STAGE/usr/share/doc/coverup/copyright"

SCRIPTS="$(mktemp -d)"
cat > "$SCRIPTS/after-install.sh" <<'EOF'
#!/bin/sh
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -f /usr/share/icons/hicolor 2>/dev/null || true
fi
exit 0
EOF
cat > "$SCRIPTS/after-remove.sh" <<'EOF'
#!/bin/sh
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
exit 0
EOF

mkdir -p "$OUTDIR"
OUT="$OUTDIR/coverup-${VERSION}-1.${ARCH}.rpm"
rm -f "$OUT"
fpm -s dir -t rpm \
  --name coverup \
  --version "$VERSION" \
  --iteration 1 \
  --architecture "$ARCH" \
  --license "GPL-3.0" \
  --maintainer "digidigital <support@digidigital.de>" \
  --url "https://coverup.digidigital.de" \
  --description "PDF and image redaction tool. Redacts sensitive information in
PDFs and images by drawing bars over content and flattening pages to images.
Self-contained build: bundles its own Python, Tcl/Tk and libraries." \
  --depends glibc \
  --after-install "$SCRIPTS/after-install.sh" \
  --after-remove "$SCRIPTS/after-remove.sh" \
  --package "$OUT" \
  -C "$STAGE" \
  opt usr
echo "Built: $OUT"
