#!/usr/bin/env bash
# Build an AppImage from the PyInstaller one-dir output.
#
# Wraps the self-contained bundle (its own Python, Tcl/Tk and libraries) in an
# AppDir and runs appimagetool. The AppImage is portable but does NOT integrate
# into the application menu by itself (use the .deb for system-wide install).
#
# Usage: packaging/build-appimage.sh <version> <pyinstaller-dist-dir> [output-dir]
#   e.g. packaging/build-appimage.sh 0.8.0 dist/coverup dist-appimage
# Env:
#   APPIMAGETOOL   path to appimagetool (default: "appimagetool" on PATH)
set -euo pipefail

VERSION="${1:?version required (e.g. 0.8.0)}"
DIST="${2:?PyInstaller dist/coverup dir required}"
OUTDIR="${3:-.}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPIMAGETOOL="${APPIMAGETOOL:-appimagetool}"

[ -x "$DIST/coverup" ] || { echo "error: $DIST/coverup not found or not executable" >&2; exit 1; }

APPDIR="$(mktemp -d)/CoverUP.AppDir"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps"

# Bundle goes under usr/bin/coverup; AppRun launches its entry point.
cp -r "$DIST" "$APPDIR/usr/bin/coverup"

# Desktop entry + icon, both at AppDir root (required by appimagetool) and in
# the standard share/ locations.
cp "$ROOT/appimage/coverup.desktop" "$APPDIR/usr/share/applications/coverup.desktop"
cp "$ROOT/appimage/coverup.desktop" "$APPDIR/coverup.desktop"
cp "$ROOT/CoverUP.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/coverup.svg"
cp "$ROOT/CoverUP.svg" "$APPDIR/coverup.svg"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/coverup/coverup" "$@"
EOF
chmod +x "$APPDIR/AppRun"

mkdir -p "$OUTDIR"
OUT="$OUTDIR/CoverUP-${VERSION}-x86_64.AppImage"
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUT"
echo "Built: $OUT"
