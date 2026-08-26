# Character set

The VP415's on-screen display font — extracted from a datasheet, not from a ROM
image, because it was never in one.

## Why it is here and not in `original-images/`

[`docs/tooling.md`](../docs/tooling.md) assumes the OSD font lives in the module
R `DRIVE` EPROM, on the reasoning that module R drives the display. Searching
that image finds nothing: a 1-bit-per-pixel survey at every plausible row width
shows uniform code noise and blocks of `0xFF` erased fill, and a glyph-shape
scan across strides 5–16 over all eleven images returns no candidate font table.

The schematic says why. On `CS 6 883`, the module R circuit diagram, **IC7212 is
a Fujitsu MB88303** — an NMOS Television Display Controller with a **448 × 5-bit
character generator ROM on the die**. The service guide's circuit description
states it plainly:

> Status information from the manchester codes for display on screen is read
> from IC 7211 by processor IC 7201 and loaded into display driver IC 7212.
> IC 7212 contains the character generator for on screen display.

So the `DRIVE` EPROM holds only the code that formats status into MB88303
commands. The glyphs come off the Fujitsu part, and the only published record of
them is Figure 3(a) of the MB88303 datasheet.

> The service guide's [firmware page][fw] lists the MB88303 as "not tied to a
> board by the manual". The module R schematic and circuit description do tie
> it: IC7212. Worth sending upstream.

[fw]: https://github.com/domesday86/vp415-service-guide/blob/main/docs/reference/firmware.md

## The device

| | |
| --- | --- |
| Part | Fujitsu MB88303, NMOS Television Display Controller (TVDC) |
| Position | Module R, IC7212 — Philips service code `4822 209 71278` |
| Package | 22-pin plastic DIP, single +5 V |
| Screen | 20 characters × 9 lines, 180 maximum |
| Character | 5 × 7 dots, 1-dot horizontal and 2-dot vertical spacing |
| Set | 64 characters, no lower case |
| Character ROM | 448 × 5-bit — 64 characters × 7 rows |
| Display RAM | 180 × 7-bit — bits 5–0 character code, bit 6 blink enable |

Data arrives on `DA0`–`DA7` (pins 14–21) from port A of IC7203, a UPD8155C-2.
`ADM` (13) selects direct-address or address-increment mode and `LDI` (12) is
the write strobe. Outputs are `VOW` (5, character) and `VOB` (6, background).

## Layout

```
scripts/    the transcription pipeline
results/    what it produces — the deliverables
build/      intermediates, gitignored
```

## Regenerating

```sh
scripts/fetch-source.sh      # download the datasheet, render page 4-86 at 600 dpi
python3 scripts/extract-font.py
python3 scripts/verify_font.py
python3 scripts/emit-font.py
```

`fetch-source.sh` uses `docs/MB88303.pdf` if it is present and downloads the
datasheet from the service guide otherwise; both give the same bytes.

Needs Python with Pillow and numpy, and `pdftoppm` from poppler-utils — the
repo flake does not carry poppler, so `fetch-source.sh` falls back to
`nix shell nixpkgs#poppler-utils` if the binary is not on `PATH`.

The pipeline is deterministic: `results/mb88303-font.bin` has SHA-256
`c6595809d67a5174f48f1a55c7561324ee21f701325875cc04c6c7e6a7476b33`.

## Results

| File | What it is |
| --- | --- |
| `mb88303-font.txt` | The review document — all 64 glyphs in dots and hashes, per-character detail, byte table, validation results |
| `mb88303-font.bin` | 448 bytes, code order, 7 bytes per character |
| `mb88303-font.json` | The same as machine-readable arrays |
| `mb88303-font.h` | C array |
| `mb88303-font.png` | Labelled sheet at 8× |
| `mb88303-font-strip.png` | 320 × 7, 1:1, one glyph per 5 px |

**Byte format.** One byte per scan row, top row first. Bits 4–0 are the five
dots left to right — bit 4 leftmost, bit 0 rightmost. Bits 7–5 are always zero.

**Character codes.** Datasheet Table 1 indexes the set as CH5-4 (columns 0–3) by
CH3-0 (rows 0–F), so `code = CH5-4 × 16 + CH3-0` — plain `0x00`–`0x3F`.

`0x0F` BLANK and `0x2E` BACKGROUND are printed as outline boxes rather than dot
patterns: they are markers for "nothing" and for the black background block, and
are all-clear in the binary. `0x3A`–`0x3C` are the kanji 年 月 日 and `0x3F` a
telephone symbol — Japanese-market characters the VP415 never displays.

## How far to trust it

This is a transcription of a 1986 scan, so it is evidence rather than a dump.
What supports it:

- Four glyph pairs come out as **exact mirrors** despite being extracted
  independently from different parts of the figure — `↑`/`↓` vertically,
  `←`/`→` and `(`/`)` horizontally. A misfitted lattice would have broken them.
- Figure 3(b) shows the same set after the chip's inter-dot filling, so it can
  only ever *add* dots. 60 of 64 characters satisfy that. The four that do not
  (`0x1E`, `0x30`, `0x3E`, `0x3F`) fail because the 3(b) pass is misaligned on
  those glyphs; 3(b) exists here only as a check and was not transcribed
  carefully.
- `0x03` D, `0x06` G, `0x39` &, `0x3E` ~ and `0x22` 2 were each confirmed by
  hand against a magnified scan with the dot lattice drawn over it. D genuinely
  has its vertical stem in column 1, so the top and bottom bars overhang it to
  the left — it looks like an error and is not.
- `verify_font.py` reports the **closest calls**: the dots whose sample sat
  nearest the ink/blank threshold, which is where an error would hide. The
  nearest in the set is currently 0.36 against a threshold of 0.5.

One error has been found and fixed this way. `0x22` 2 had a spurious dot in its
lower left corner, at row 5 column 1, because the sample window was wide enough
to catch ink bleeding from the bottom bar and the left stem. The decoding is
identical for every window from 0.06 to 0.16 of a dot and only changes at 0.18;
`SAMPLE_FRAC` in `scripts/extract-font.py` is now 0.12, mid-plateau. If you spot
another, the closest-calls list is the place to look first.

What would settle it beyond doubt is reading a real MB88303, or finding the OSD
routine in the `DRIVE` disassembly and checking the codes it writes against
Table 1.

## Sources

- Fujitsu MB88303 datasheet, Edition 2.0, October 1986 — Table 1 (page 4-85),
  Figure 3(a) (page 4-86), Figure 4 register map (page 4-87). In the service
  guide at `docs/reference/assets/originals/datasheets/mb88303-fujitsu.pdf`.
- Philips VP410/VP415 service manual, `CS 6 883` — module R circuit diagram.
- [VP415 service guide](https://github.com/domesday86/vp415-service-guide),
  circuit description, module R.
