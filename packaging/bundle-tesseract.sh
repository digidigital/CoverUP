#!/usr/bin/env bash
#
# Enrich a PyInstaller --onedir bundle with a self-contained Tesseract OCR
# (Linux). The three Linux installers (.deb/.rpm/AppImage) all package the same
# dist/coverup tree, so running this once after PyInstaller makes OCR work out
# of the box in every one of them.
#
# Layout produced (inside the bundle's _internal dir):
#   tesseract/tesseract       -> wrapper script (sets LD_LIBRARY_PATH, execs)
#   tesseract/tesseract.bin   -> the real binary
#   tesseract/lib/*.so*       -> its shared-lib closure (minus the glibc core)
#   tessdata/<lang>.traineddata
#
# The wrapper scopes LD_LIBRARY_PATH to the tesseract process only, so the
# app's own environment and its multiprocessing workers are never affected.
#
# Usage:
#   packaging/bundle-tesseract.sh <dist/coverup dir> [lang ...]   # default: eng
set -euo pipefail

BUNDLE="${1:?bundle dir required (e.g. dist/coverup)}"
shift || true
LANGS=("$@")
[ "${#LANGS[@]}" -eq 0 ] && LANGS=("eng")

TESS_BIN="$(command -v tesseract || true)"
[ -n "$TESS_BIN" ] || { echo "ERROR: tesseract not found on PATH" >&2; exit 1; }
TESS_BIN="$(readlink -f "$TESS_BIN")"

# PyInstaller 6 onedir puts data under _internal; older layouts use the root.
INTERNAL="$BUNDLE/_internal"
[ -d "$INTERNAL" ] || INTERNAL="$BUNDLE"

TDIR="$INTERNAL/tesseract"
LIBDIR="$TDIR/lib"
DESTTESS="$INTERNAL/tessdata"
mkdir -p "$LIBDIR" "$DESTTESS"

echo "Bundling tesseract from $TESS_BIN into $TDIR"
cp -L "$TESS_BIN" "$TDIR/tesseract.bin"

# Copy the full shared-lib closure that ldd reports, excluding the glibc core
# (those must come from the host loader; bundling them breaks the runtime).
GLIBC_CORE='^(ld-linux.*|linux-vdso|libc|libm|libdl|librt|libpthread|libresolv|libnsl|libutil|libBrokenLocale)\.so'
ldd "$TESS_BIN" | awk '/=> \//{print $3}' | while read -r lib; do
    [ -e "$lib" ] || continue
    base="$(basename "$lib")"
    if echo "$base" | grep -qE "$GLIBC_CORE"; then
        continue
    fi
    cp -Lf "$lib" "$LIBDIR/"
done

# Wrapper: resolve bundled libs first, fall back to the system, then exec.
cat > "$TDIR/tesseract" <<'WRAP'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="$HERE/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/tesseract.bin" "$@"
WRAP
chmod +x "$TDIR/tesseract"

# Language data: search the usual system locations.
for lang in "${LANGS[@]}"; do
    found=""
    for d in /usr/share/tesseract-ocr/*/tessdata /usr/share/tessdata \
             /usr/share/tesseract-ocr/tessdata "$(dirname "$TESS_BIN")/../share/tessdata"; do
        if [ -f "$d/$lang.traineddata" ]; then
            cp -f "$d/$lang.traineddata" "$DESTTESS/"
            found="$d/$lang.traineddata"
            break
        fi
    done
    if [ -n "$found" ]; then
        echo "  + $lang.traineddata ($found)"
    else
        echo "  ! $lang.traineddata not found on system" >&2
    fi
done

echo "Done. Bundled libs: $(ls -1 "$LIBDIR" | wc -l), languages: ${LANGS[*]}"
