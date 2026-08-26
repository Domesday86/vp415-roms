#!/usr/bin/env bash
# Fetch the MB88303 datasheet and render the character-generator page.
#
# Figure 3(a) on datasheet page 4-86 (PDF page 6) is "Internal Character Dot
# Patterns (Character Generator ROM Patterns)" -- the 64 glyphs held in the
# mask ROM of IC7212 on VP415 module R. Everything else here is derived from
# that one page, rendered at 600 dpi so individual printed dots resolve.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
build="$here/../build"
mkdir -p "$build"

url=https://raw.githubusercontent.com/domesday86/vp415-service-guide/main/docs/reference/assets/originals/datasheets/mb88303-fujitsu.pdf
pdf="$build/mb88303-fujitsu.pdf"
local_copy="$here/../../docs/MB88303.pdf"

if [ ! -f "$pdf" ]; then
    if [ -f "$local_copy" ]; then
        echo "using local copy $local_copy"
        cp "$local_copy" "$pdf"
    else
        echo "fetching $url"
        curl -fsSL -o "$pdf" "$url"
    fi
fi

# pdftoppm is in poppler-utils; the repo flake does not carry it
if command -v pdftoppm >/dev/null 2>&1; then
    pdftoppm -png -r 600 -f 6 -l 6 "$pdf" "$build/page"
elif command -v nix >/dev/null 2>&1; then
    nix shell nixpkgs#poppler-utils -c pdftoppm -png -r 600 -f 6 -l 6 "$pdf" "$build/page"
else
    echo "need pdftoppm (poppler-utils) or nix" >&2; exit 1
fi

mv "$build/page-06.png" "$build/page-4-86.png"
echo "wrote $build/page-4-86.png"
