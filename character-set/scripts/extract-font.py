#!/usr/bin/env python3
"""Transcribe the MB88303 character generator ROM from the datasheet figure.

Reads the 600 dpi render of datasheet page 4-86 produced by fetch-source.sh and
writes build/font-raw.json, holding both figures on the page:

    'a'  Figure 3(a), the character generator ROM patterns   <- the real font
    'b'  Figure 3(b), the same set after inter-dot filling    <- cross-check only

Method. The four glyph rows of each figure are found from the page ink profile.
Within a row the 16 glyph cells are located by least-squares fitting a uniform
pitch to the glyph ink segments. Each glyph is then gridded on its OWN lattice:
its ink bounding box is divided into the number of dot rows and columns implied
by the row lattice, and samples are taken at dot centres. Fitting per glyph
rather than per row matters -- the scan skews enough across a row that one
lattice for all 16 misreads the dense glyphs.

Both edges of a glyph are indexed off the row lattice rather than derived from
its ink width. Width alone rounds wrong when the scan clips a printed dot, which
is what makes 0x3E '~' come out shifted a column if you do it the obvious way.

Dots are sampled over a narrow window at the dot centre -- see SAMPLE_FRAC.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / "build"

# glyph row bands on the 600 dpi page, from its horizontal ink profile
BANDS = {
    "a": [(996, 1162), (1264, 1426), (1531, 1695), (1798, 1966)],
    "b": [(2262, 2434), (2525, 2688), (2786, 2958), (3068, 3226)],
}
XLO, XHI = 1200, 3900          # figure body; excludes scan specks in the margins

# Half-width of the sample window at each dot centre, as a fraction of the dot.
# Printed dots bleed into their neighbours, so a wide window reads ink that
# belongs to the adjacent dot. At 0.30 that flipped one dot: 0x22 '2' row 5
# column 1 sampled 0.61 and decoded as set, giving the digit a spurious pixel in
# its lower left corner. The decoding is identical for every value from 0.06 to
# 0.16 and only changes at 0.18, so 0.12 sits mid-plateau rather than on the edge.
SAMPLE_FRAC = 0.12

# printed as outline boxes, not dot patterns: markers for "nothing" and for the
# black background block. Both are all dots clear.
SPECIAL = {0x0F: "BLANK", 0x2E: "BACKGROUND"}


def clean(mask):
    """drop isolated scan specks: keep ink with at least 3 ink neighbours"""
    b = mask.astype(np.uint8)
    p = np.pad(b, 1)
    n = sum(p[dy:dy + b.shape[0], dx:dx + b.shape[1]]
            for dy in (0, 1, 2) for dx in (0, 1, 2)) - b
    return (b & (n >= 3)).astype(bool)


def band_info(ink, band):
    """row extent, dot size, and the 16 glyph ink segments of one glyph row"""
    y0, y1 = band
    sub = clean(ink[y0:y1, XLO:XHI])

    ys = np.nonzero(sub.sum(1) > 0)[0]
    y_top, y_bot = y0 + int(ys[0]), y0 + int(ys[-1]) + 1

    xs = np.nonzero(sub.sum(0) > 0)[0]
    segs, start, prev = [], xs[0], xs[0]
    for x in xs[1:]:
        if x - prev > 10:
            segs.append((XLO + int(start), XLO + int(prev) + 1))
            start = x
        prev = x
    segs.append((XLO + int(start), XLO + int(prev) + 1))
    if len(segs) != 16:
        raise SystemExit(f"band {band}: found {len(segs)} glyphs, expected 16")

    # uniform glyph pitch, fitted on the glyphs whose ink starts at column 0
    x0 = segs[0][0]
    pitch = (segs[14][0] - segs[0][0]) / 14.0
    for _ in range(4):
        ks = [k for k, (s, _) in enumerate(segs) if abs(s - (x0 + k * pitch)) < 0.12 * pitch]
        A = np.vstack([np.ones(len(ks)), ks]).T
        (x0, pitch), *_ = np.linalg.lstsq(
            A, np.array([segs[k][0] for k in ks], float), rcond=None)

    dot_h = (y_bot - y_top) / 7.0
    # a full-width glyph is exactly 5 dots; take the widest few so bleed averages out
    dot_w = float(np.median(sorted(e - s for s, e in segs)[-3:])) / 5.0
    return y_top, dot_h, dot_w, x0, pitch, segs


def extract_band(ink, band, base, margins=None):
    """glyphs for one row; if margins is a list, append (code,row,col,fill) per dot"""
    y_top, dot_h, dot_w, x0, pitch, segs = band_info(ink, band)
    glyphs = []
    for k, (sx, ex) in enumerate(segs):
        if base + k in SPECIAL:
            glyphs.append([0] * 7)
            continue

        cell_l = x0 + k * pitch
        sub = clean(ink[y_top - 14:y_top + int(7 * dot_h) + 14, sx:ex])
        ys = np.nonzero(sub.sum(1) > 0)[0]
        ty, by = y_top - 14 + int(ys[0]), y_top - 14 + int(ys[-1]) + 1

        # index both edges off the row lattice
        c0 = max(0, min(4, int(round((sx - cell_l) / dot_w))))
        c1 = max(c0, min(4, int(round((ex - cell_l) / dot_w)) - 1))
        r0 = max(0, min(6, int(round((ty - y_top) / dot_h))))
        r1 = max(r0, min(6, int(round((by - y_top) / dot_h)) - 1))
        ncols, nrows = c1 - c0 + 1, r1 - r0 + 1

        rows = [0] * 7
        for j in range(nrows):
            v = 0
            for i in range(ncols):
                cx = sx + (i + 0.5) * (ex - sx) / ncols
                cy = ty + (j + 0.5) * (by - ty) / nrows
                hx = (ex - sx) / ncols * SAMPLE_FRAC
                hy = (by - ty) / nrows * SAMPLE_FRAC
                fill = float(ink[int(cy - hy):int(cy + hy) + 1,
                                 int(cx - hx):int(cx + hx) + 1].mean())
                if margins is not None:
                    margins.append((base + k, r0 + j, c0 + i, round(fill, 3)))
                if fill > 0.5:
                    v |= 1 << (4 - (c0 + i))
            rows[r0 + j] = v
        glyphs.append(rows)
    return glyphs


def main():
    page = Path(sys.argv[1]) if len(sys.argv) > 1 else BUILD / "page-4-86.png"
    if not page.exists():
        raise SystemExit(f"{page} not found -- run fetch-source.sh first")

    ink = np.array(Image.open(page).convert("L")) < 128
    if ink.shape != (5481, 4145):
        print(f"warning: page is {ink.shape[1]}x{ink.shape[0]}, expected 4145x5481 "
              "(600 dpi); the band coordinates assume that size", file=sys.stderr)

    out = {}
    margins = []
    for kind, bands in BANDS.items():
        glyphs = []
        for i, band in enumerate(bands):
            glyphs += extract_band(ink, band, i * 16,
                                   margins if kind == "a" else None)
            y_top, dot_h, dot_w, x0, pitch, _ = band_info(ink, band)
            print(f"fig 3({kind}) band {band}: dot {dot_w:.2f}x{dot_h:.2f} px, "
                  f"pitch {pitch:.2f}", file=sys.stderr)
        out[kind] = glyphs

    BUILD.mkdir(exist_ok=True)
    (BUILD / "font-raw.json").write_text(json.dumps(out))
    (BUILD / "font-margins.json").write_text(json.dumps(margins))
    print(f"wrote {BUILD / 'font-raw.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
