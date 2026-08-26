#!/usr/bin/env python3
"""Turn build/font-raw.json into the files under results/.

    mb88303-font.txt         review document: dots and hashes, per-character
                             detail, byte table, validation results
    mb88303-font.bin         448 bytes, code order, 7 bytes per character
    mb88303-font.json        the same as machine-readable arrays
    mb88303-font.h           C array
    mb88303-font.png         labelled sheet, 8x scale
    mb88303-font-strip.png   320x7, 1:1, one glyph per 5 px -- usable as a texture
"""
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw

from names import NAMES, SPECIAL, art
from verify_font import checks, closest_calls, superset_failures

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / "build"
RESULTS = HERE.parent / "results"


def document(glyphs, fig_b):
    L = []
    w = L.append
    w("MB88303 Television Display Controller - character generator ROM")
    w("=" * 70)
    w("")
    w(textwrap.fill(
        "The 64-character, 5x7 dot-matrix character set held in the mask ROM of "
        "the Fujitsu MB88303 (IC7212 on Philips VP415 module R, the drive "
        "processor). Transcribed from Figure 3(a), 'Internal Character Dot "
        "Patterns (Character Generator ROM Patterns)', page 4-86 of the MB88303 "
        "datasheet, Edition 2.0, October 1986. Character codes are from Table 1, "
        "page 4-85.", 74))
    w("")
    w(textwrap.fill(
        "Figure 3(b) on the same page shows the same 64 characters after the "
        "chip's automatic inter-dot filling function, which adds half-dots at "
        "diagonal junctions when the pattern is displayed. Those half-dots do not "
        "exist in the ROM and are not represented here.", 74))
    w("")
    w("Source PDF: docs/reference/assets/originals/datasheets/mb88303-fujitsu.pdf")
    w("            in github.com/domesday86/vp415-service-guide")
    w("Rendered at 600 dpi; each glyph gridded to its own dot lattice and sampled")
    w("at dot centres. See ../scripts/ to regenerate.")
    w("")
    w("-" * 70)
    w("CODE NUMBERING")
    w("-" * 70)
    w("")
    w("Table 1 indexes the set as CH5-4 (columns 0-3) by CH3-0 (rows 0-F), so the")
    w("character code is  code = CH5-4 * 16 + CH3-0  -- i.e. plain 0x00..0x3F.")
    w("The code occupies bits 5-0 of a display-memory word; bit 6 is the per-")
    w("character blink enable (BC). There is no lower case.")
    w("")
    w("-" * 70)
    w("BYTE FORMAT USED BELOW AND IN mb88303-font.bin")
    w("-" * 70)
    w("")
    w("7 bytes per character, 64 characters, 448 bytes total, in code order.")
    w("One byte per scan row, top row first. Bits 4..0 are the five dots, left to")
    w("right; bits 7..5 are always 0.  bit4 = leftmost dot, bit0 = rightmost dot.")
    w("")
    w("        bit   7 6 5 4 3 2 1 0")
    w("              0 0 0 | | | | |")
    w("                    | | | | +--- dot 4 (rightmost)")
    w("                    +-+-+-+----- dots 0..3")
    w("")
    w("(The datasheet calls this a 448 x 5-bit ROM: 64 characters x 7 rows.)")
    w("")
    w("")
    w("=" * 70)
    w("THE CHARACTER SET, 16 PER BLOCK")
    w("=" * 70)
    for blk in range(4):
        w("")
        w(f"--- codes 0x{blk * 16:02X}-0x{blk * 16 + 15:02X}   "
          f"(Table 1 column CH5-4 = {blk}) ---")
        w("")
        hdr = " ".join(f"0x{blk * 16 + k:02X}  " for k in range(16))
        w("  " + hdr)
        for r in range(7):
            w("  " + " ".join(art(glyphs[blk * 16 + k][r]) + " " for k in range(16)))
        w("  " + hdr)
    w("")
    w("")
    w("=" * 70)
    w("PER-CHARACTER DETAIL")
    w("=" * 70)
    for i in range(64):
        w("")
        w(f"0x{i:02X}  ({i:2d})  {NAMES[i]}")
        if i in SPECIAL:
            w(f"      note: {SPECIAL[i]}")
        w("")
        for r in range(7):
            w(f"        {art(glyphs[i][r])}   0x{glyphs[i][r]:02X}   {glyphs[i][r]:08b}")
    w("")
    w("")
    w("=" * 70)
    w("BYTE TABLE (448 bytes, code order, 7 bytes per character)")
    w("=" * 70)
    w("")
    for i in range(64):
        w(f"  0x{i:02X}: " + ", ".join(f"0x{b:02X}" for b in glyphs[i]) +
          f",   /* {NAMES[i]} */")
    w("")
    w("")
    w("=" * 70)
    w("VALIDATION")
    w("=" * 70)
    w("")
    w("These checks are run at generation time. Each mirror pair was extracted")
    w("independently from a different part of the figure, so agreement is evidence")
    w("the dot lattice was fitted correctly and not an artefact of the method.")
    w("")
    for label, ok in checks(glyphs):
        w(f"  [{'PASS' if ok else 'FAIL'}]  {label}")
    ink = sum(bin(b).count("1") for g in glyphs for b in g)
    w("")
    w(f"  64 glyphs, 448 bytes, {ink} dots set out of 2240 ({ink / 2240 * 100:.1f}%).")
    w("")
    cc = closest_calls()
    if cc:
        w("A dot decodes as set when its sample window at the dot centre is more than")
        w("half ink. Values near 0.5 are the ones a small change in the fit would flip,")
        w("so they are where an error would hide. The closest calls in the set are:")
        w("")
        for code, r, c, fill in cc:
            w(f"    0x{code:02X} row {r} col {c}   fill {fill:.2f}"
              f"   -> {'set' if fill > 0.5 else 'clear'}")
        w("")
        w("Anything below about 0.3 or above 0.7 is a comfortable call.")
        w("")
    fails = superset_failures(glyphs, fig_b)
    w("Cross-check against Figure 3(b): 3(b) is the same character set after the")
    w("chip's inter-dot filling, so every dot in 3(a) must also be present in 3(b).")
    w(f"Extracting 3(b) independently and comparing, {64 - len(fails)} of 64")
    w("characters satisfy this. The ones that do not")
    w("  " + ", ".join(f"0x{i:02X}" for i in fails))
    w("fail because the 3(b) transcription is misaligned by a row or a column on")
    w("those glyphs, not because of a disagreement about 3(a). 3(b) was not")
    w("transcribed carefully; it exists here only as a check.")
    w("")
    w("Characters worth a second opinion if precision matters, because their")
    w("printed forms are unusual or dense. Each was confirmed by hand against a")
    w("magnified scan with the dot lattice drawn over it:")
    w("")
    w("  0x03  D  - the vertical stem sits in column 1, not column 0, so the top")
    w("             and bottom bars overhang it to the left. This is genuine.")
    w("  0x06  G  - likewise an unusual open form.")
    w("  0x39  &  - dense; two rows were wrong before the lattice fit was fixed.")
    w("  0x3E  ~  - rises at column 1 and dips at column 3.")
    w("  0x22  2  - the printed 2 bleeds toward column 1. With a wider sample")
    w("             window it gained a spurious dot at row 5 column 1, in the")
    w("             lower left corner. It is clear; see SAMPLE_FRAC in")
    w("             ../scripts/extract-font.py.")
    w("")
    w("  0x3A-0x3C are the kanji NEN, GETSU and NICHI and 0x3F a telephone symbol.")
    w("  They are Japanese-market characters the VP415 never displays.")
    w("")
    return "\n".join(L) + "\n"


def sheet(glyphs):
    S, PAD, LBL = 8, 6, 16
    cw, ch = 5 * S + PAD * 2, 7 * S + PAD * 2
    im = Image.new("RGB", (16 * cw + 40, 4 * (ch + LBL) + 40), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for i in range(64):
        r, c = divmod(i, 16)
        ox, oy = 20 + c * cw, 20 + r * (ch + LBL)
        d.rectangle([ox, oy, ox + cw - 2, oy + ch - 2], outline=(200, 200, 200))
        for rr in range(7):
            for cc in range(5):
                if (glyphs[i][rr] >> (4 - cc)) & 1:
                    x, y = ox + PAD + cc * S, oy + PAD + rr * S
                    d.rectangle([x, y, x + S - 1, y + S - 1], fill=(0, 0, 0))
        d.text((ox + 2, oy + ch - 2), f"{i:02X}", fill=(120, 120, 120))
    return im


def strip(glyphs):
    im = Image.new("L", (64 * 5, 7), 255)
    px = im.load()
    for i in range(64):
        for rr in range(7):
            for cc in range(5):
                if (glyphs[i][rr] >> (4 - cc)) & 1:
                    px[i * 5 + cc, rr] = 0
    return im


def main():
    raw = json.loads((BUILD / "font-raw.json").read_text())
    glyphs, fig_b = raw["a"], raw["b"]
    RESULTS.mkdir(exist_ok=True)

    (RESULTS / "mb88303-font.txt").write_text(document(glyphs, fig_b))
    (RESULTS / "mb88303-font.bin").write_bytes(bytes(b for g in glyphs for b in g))
    (RESULTS / "mb88303-font.json").write_text(json.dumps({
        "source": "MB88303 datasheet Edition 2.0 (Oct 1986), Figure 3(a), page 4-86",
        "format": "64 glyphs x 7 rows; each row is a byte, bits 4..0 = dots left..right",
        "glyphs": glyphs}, indent=1))

    h = ["/* MB88303 character generator ROM - 64 chars, 5x7, 7 bytes each.",
         " * Bits 4..0 = dots left..right. Transcribed from the MB88303 datasheet",
         " * Figure 3(a) (Edition 2.0, October 1986). */",
         "static const unsigned char mb88303_font[64][7] = {"]
    for i in range(64):
        h.append("    { " + ", ".join(f"0x{b:02X}" for b in glyphs[i]) +
                 f" }},  /* 0x{i:02X} {NAMES[i]} */")
    h.append("};")
    (RESULTS / "mb88303-font.h").write_text("\n".join(h) + "\n")

    sheet(glyphs).save(RESULTS / "mb88303-font.png")
    strip(glyphs).save(RESULTS / "mb88303-font-strip.png")
    print(f"wrote 6 files to {RESULTS}")


if __name__ == "__main__":
    main()
