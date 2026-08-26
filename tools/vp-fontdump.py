#!/usr/bin/env python3
"""Render regions of a ROM image as bitmaps, to find and extract character sets.

Two modes, and you normally use them in that order:

  survey  Draw the whole ROM (or a slice) as one long 1-bit-per-pixel image,
          N bytes to a row.  Code looks like noise; a bitmap font looks like a
          band of regular, legible glyph shapes.  Sweep --row-bytes from 1 to
          about 32: when the row width happens to match the font's stride the
          characters snap upright and become readable.

  grid    Once you know where a font starts and how big its glyphs are, cut it
          into one cell per glyph and lay them out in a labelled grid, ready to
          drop into documentation or to trace into a real font file.

Bit order defaults to MSB-first (bit 7 leftmost), which is what almost every
character generator of this era used.  Use --lsb-first if the glyphs come out
mirrored.
"""

import argparse
import sys

from PIL import Image, ImageDraw


def parse_int(text):
    """Accept 0x1234, 1234, 0o17, 0b1010."""
    return int(text, 0)


def bits_of(data, msb_first=True):
    """Yield each bit of data as 0 or 1, in display order."""
    for byte in data:
        rng = range(7, -1, -1) if msb_first else range(8)
        for bit in rng:
            yield (byte >> bit) & 1


def render_survey(data, row_bytes, msb_first, invert):
    """Whole region as a 1bpp bitmap, row_bytes bytes per row."""
    width = row_bytes * 8
    height = (len(data) + row_bytes - 1) // row_bytes
    padded = data + bytes(row_bytes * height - len(data))

    img = Image.new("1", (width, height))
    img.putdata([b ^ invert for b in bits_of(padded, msb_first)])
    return img


def render_grid(data, glyph_w, glyph_h, stride, count, columns,
                msb_first, invert, gap, label):
    """One cell per glyph, laid out columns-wide, optionally with an index."""
    row_bytes = (glyph_w + 7) // 8
    if stride is None:
        stride = row_bytes * glyph_h

    available = (len(data) - (glyph_h * row_bytes)) // stride + 1 if stride else 0
    if count is None:
        count = max(available, 0)
    count = max(min(count, available), 0)
    if count == 0:
        sys.exit("vp-fontdump: region is too small to hold even one glyph")

    columns = max(min(columns, count), 1)
    rows = (count + columns - 1) // columns

    # Pillow's built-in bitmap font is 11px tall; leave room for a caption
    # across the top and an index under every glyph.
    text_h = 11
    top = text_h + 2 if label else 0
    left = 2 if label else 0

    cell_w = glyph_w + gap
    cell_h = glyph_h + gap + (text_h if label else 0)

    img = Image.new("L", (columns * cell_w + gap + left,
                          rows * cell_h + gap + top), 128)
    draw = ImageDraw.Draw(img)

    for index in range(count):
        start = index * stride
        glyph = data[start:start + row_bytes * glyph_h]
        cell = Image.new("1", (row_bytes * 8, glyph_h))
        cell.putdata([b ^ invert for b in bits_of(glyph, msb_first)])
        cell = cell.crop((0, 0, glyph_w, glyph_h))

        x = left + gap + (index % columns) * cell_w
        y = top + gap + (index // columns) * cell_h
        img.paste(cell.convert("L"), (x, y))
        if label:
            draw.text((x, y + glyph_h), f"{index:02X}", fill=0)

    if label:
        draw.text((1, 1), f"{count} glyphs, {glyph_w}x{glyph_h}, stride {stride}", fill=0)

    return img


def main():
    ap = argparse.ArgumentParser(
        prog="vp-fontdump",
        description="Render ROM regions as bitmaps to find and extract character sets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  # sweep the drive ROM looking for a font band
  for n in 8 12 16 20 24 32; do
    vp-fontdump rom.bin -o survey-$n.png --mode survey --row-bytes $n
  done

  # cut 96 8x8 glyphs out of a table you found at 0x2A00
  vp-fontdump rom.bin -o font.png --mode grid \\
      --offset 0x2A00 --width 8 --height 8 --count 96
""")

    ap.add_argument("image", help="ROM image to read")
    ap.add_argument("-o", "--out", required=True, help="PNG to write")
    ap.add_argument("--mode", choices=("survey", "grid"), default="survey")

    ap.add_argument("--offset", type=parse_int, default=0,
                    help="start reading here (default 0)")
    ap.add_argument("--length", type=parse_int, default=None,
                    help="read this many bytes (default: to end of file)")

    ap.add_argument("--row-bytes", type=parse_int, default=16,
                    help="[survey] bytes per row (default 16)")

    ap.add_argument("--width", type=parse_int, default=8,
                    help="[grid] glyph width in pixels (default 8)")
    ap.add_argument("--height", type=parse_int, default=8,
                    help="[grid] glyph height in rows (default 8)")
    ap.add_argument("--stride", type=parse_int, default=None,
                    help="[grid] bytes per glyph (default: exactly the glyph)")
    ap.add_argument("--count", type=parse_int, default=None,
                    help="[grid] how many glyphs (default: as many as fit)")
    ap.add_argument("--columns", type=parse_int, default=16,
                    help="[grid] glyphs per row (default 16)")
    ap.add_argument("--gap", type=parse_int, default=1,
                    help="[grid] pixel gap between cells (default 1)")
    ap.add_argument("--no-label", action="store_true",
                    help="[grid] omit the index printed under each glyph")

    ap.add_argument("--lsb-first", action="store_true",
                    help="bit 0 is the leftmost pixel (default: bit 7)")
    ap.add_argument("--invert", action="store_true",
                    help="1 bits are background rather than ink")
    ap.add_argument("--scale", type=parse_int, default=4,
                    help="nearest-neighbour zoom applied to the output (default 4)")

    args = ap.parse_args()

    with open(args.image, "rb") as handle:
        data = handle.read()

    end = len(data) if args.length is None else args.offset + args.length
    region = data[args.offset:end]
    if not region:
        sys.exit(f"vp-fontdump: nothing to render at offset {args.offset:#x}")

    msb_first = not args.lsb_first
    invert = 1 if args.invert else 0

    if args.mode == "survey":
        img = render_survey(region, args.row_bytes, msb_first, invert)
    else:
        img = render_grid(region, args.width, args.height, args.stride,
                          args.count, args.columns, msb_first, invert,
                          args.gap, not args.no_label)

    if args.scale > 1:
        img = img.resize((img.width * args.scale, img.height * args.scale),
                         Image.NEAREST)

    img.convert("L").save(args.out)
    print(f"wrote {args.out}  {img.width}x{img.height}  "
          f"from {args.image} {args.offset:#06x}-{min(end, len(data)):#06x}")


if __name__ == "__main__":
    main()
