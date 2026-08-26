# The reverse-engineering environment

`flake.nix` provides a Nix development shell with the tools for disassembling,
documenting and extracting data from the images in
[`original-images/`](../original-images/).

```sh
nix develop            # everything, including Ghidra
nix develop .#lite     # same minus Ghidra's ~700 MB download
```

Everything is available from the NixOS binary cache — nothing compiles from
source on first entry.

## What is in each image

The service manual names the modules but not their processors. These were read
off the bytes themselves, so they are facts about the dumps rather than claims
from the documentation:

| Image | CPU | Evidence |
| --- | --- | --- |
| `*-drive-*`, `*-control*` | **MCS-51** (8031/8051, external ROM) | `02 xx xx` (`LJMP`) at 0x0000, and again at the 0x0003 / 0x000B / 0x0013 / 0x001B interrupt vectors — the MCS-51 vector layout exactly |
| `*8041-slave*` | **MCS-48 / UPI-41A** | Decodes cleanly as MCS-48 from 0x000; `04 09` = `JMP $009`, then `CALL` at the 0x003 IBF vector and `JMP` at the 0x007 timer vector |
| `*lvdos1*`, `*lvdos2*` | **Z80** | `ED 5B` (`LD DE,(nn)`) at 0x0012 is a Z80-only opcode — an 8080 cannot encode it. The reset code at 0x0000 clears 0xA000–0xFFFF, which locates the module's RAM |
| `*sync*`, `*descr*` | **none — data** | No code. `SYNC` has 256 programmed bytes out of 16384; `DESCR` has 7029. They are the lookup tables the manual describes |

`vp-arch` carries this table so you do not have to remember it:

```console
$ vp-arch original-images/vp415-module-w-ic7248-lvdos2-6806.3-rev1.4-0x56D7.bin
kind=code
unidasm=z80
ghidra=z80:LE:16:default
base=0x4000
cpu=Zilog Z80 (module W CPU, 8 MHz)
note=upper half; 0x4000 base is inferred, not proven -- only 0x4000-0x4F5B is programmed
```

### The one address that is a guess

`LVDOS#2` is placed at **0x4000**, directly above `LVDOS#1`. That is inference,
not measurement, and it is worth settling early because every address in that
half depends on it. What supports it:

- `LVDOS#1` fills 0x0000–0x3FFF, and reset clears RAM from 0xA000 up, so ROM
  has room to run contiguously to 0x7FFF.
- A 25-byte record pattern appears at 0x3FEE in `LVDOS#1` and again 25 bytes
  later at 0x4007 in `LVDOS#2` under this mapping — a table running across the
  device boundary.

What argues against taking it as settled: a linear disassembly of `LVDOS#1`
shows call and jump targets concentrated in 0x0000–0x2FFF with almost none
above 0x4000, which is not what you would expect if the second EPROM were
simply more of the same program. It may be banked, or largely data. Treat
0x4000 as a working assumption, and pass `-b` to override it.

Remember the manual's warning: revisions 1.3 and 1.4 of LV-DOS are a **matched
pair**. Do not analyse a 1.3 half against a 1.4 half.

## The helper commands

Thin wrappers that apply the table above so the underlying tools do the right
thing by default. Each takes `-h`.

### `vp-sum16` — check an image is what it claims

`sum16` is Philips' own checksum, a plain 16-bit sum of every byte, and it is
printed on the EPROM sticker. The file names in `original-images/` embed it, so
this verifies the whole collection against itself:

```console
$ vp-sum16 original-images/*.bin
...
  sum16   0x56D7  OK
```

Exit status is non-zero on any mismatch, so it works in CI. `-q` prints only
failures.

### `vp-dis` — first-look disassembly

MAME's `unidasm` with the architecture and load address filled in:

```sh
vp-dis original-images/vp415-module-r-ic7204-drive-6803.6-rev1.7-0x68FF.bin | head
vp-dis -o disasm original-images/*.bin      # batch, with provenance headers
```

This is **linear** disassembly: it walks straight through data tables and emits
nonsense there. Good for a first look and for grepping; use Ghidra when you
want real control flow. Override with `-a ARCH` and `-b BASE`; `-R` drops the
raw hex byte column.

### `vp-ghidra` — import with the right settings

Ghidra's import dialog asks four questions you must get right before it
produces anything useful. This fills them in and runs the auto-analyser:

```sh
vp-ghidra original-images/vp415-module-s-ic7202-control-6804.9-rev1.8-0x6728.bin
vp-ghidra -g original-images/*.bin     # import them all, then open the GUI
```

The project lands in `./ghidra-project` by default.

### `vp-fontdump` — find and extract character sets

The drive processor drives the on-screen display, so its ROM is where an OSD
font is most likely to live. Finding a bitmap font means hunting for it, so
work in two passes.

**Survey** — draw the ROM as one long 1-bit-per-pixel image. Code looks like
noise; a font shows up as a band of regular, legible glyph shapes. Sweep the
row width, because glyphs only snap upright when it matches the font's stride:

```sh
for n in 8 12 16 20 24 32; do
  vp-fontdump rom.bin -o survey-$n.png --mode survey --row-bytes $n
done
```

An entropy scan narrows the search first — a character set is far more regular
than code, so it shows up as a low-entropy block:

```sh
python3 - <<'EOF'
import collections, math
d = open("original-images/vp415-module-r-ic7204-drive-6803.6-rev1.7-0x68FF.bin", "rb").read()
for off in range(0, len(d), 512):
    blk = d[off:off + 512]
    c = collections.Counter(blk)
    H = -sum((n / len(blk)) * math.log2(n / len(blk)) for n in c.values())
    print(f"0x{off:04X} {H:4.2f} {'#' * int(H * 3)}")
EOF
```

**Grid** — once you know where a font starts and how big its glyphs are, cut it
into one labelled cell per glyph:

```sh
vp-fontdump rom.bin -o font.png --mode grid \
    --offset 0x2A00 --width 8 --height 8 --count 96
```

Bit order defaults to MSB-first, which is what character generators of this era
used; pass `--lsb-first` if glyphs come out mirrored, `--invert` if they come
out as negatives, and `--stride` if each glyph is padded to more bytes than its
bitmap needs.

## The underlying tools, and why each is there

| Tool | For |
| --- | --- |
| **`ghidra`** | The main workhorse. Ships processor modules for all three CPUs here — `8048`, `8051` and `Z80` — with a decompiler for 8051. `ghidra-analyzeHeadless` scripts it |
| **`unidasm`** (from `mame-tools`) | One binary that disassembles `upi41`, `i8051` and `z80`, so a single tool covers the whole collection. `mame-tools` also brings `ldverify` and `ldresample` (LaserDisc), plus `romcmp` and `chdman` |
| **`rizin`** | Scriptable CLI analysis for batch questions and diffing. 8051 support includes ESIL emulation; Z80 is disassembly and analysis only. No 8048 — use `unidasm` or Ghidra there |
| **`asl`** | Alfred Arnold's macro assembler. Assembles MCS-48, MCS-51 **and** Z80 from one tool, with `p2bin`/`p2hex` to get a flat image back. This is how you *prove* a disassembly: reassemble it and compare byte-for-byte against the original |
| **`srecord`** | `srec_cat` converts Intel HEX to binary and back, splits, fills and checksums. The two 8041 dumps only exist as `.hex` upstream |
| **`hexyl`**, **`vbindiff`** | Reading bytes, and comparing revisions side by side. Four of the eleven images are an earlier or later revision of another, so diffing earns its place |
| **Python** with Pillow, numpy, matplotlib | Data extraction and structure plots — what `vp-fontdump` is built on |
| **`imagemagick`**, **`graphviz`** | Converting extracted graphics; drawing block diagrams for the write-up |

### Deliberately not included

- **`binwalk`** — it carves filesystems and compressed blobs out of embedded
  Linux firmware. These are 1–64 KB 8-bit ROMs with neither. It would add
  ~320 MB and find nothing.
- **`cutter`** — the Qt GUI for rizin. Ghidra already covers GUI work, and
  `rizin` covers the CLI.
- **`sdcc`**, **`z88dk`** — cross-compilers for writing *new* code for these
  targets. `asl` already covers assembly for all three CPUs, and the job here
  is reading, not building.

Any of them is one line in `flake.nix` if a use turns up.

## Suggested order of work

1. `vp-sum16 original-images/*.bin` — confirm the collection is intact.
2. `vp-dis -o disasm original-images/*.bin` — get greppable listings for all
   eight code images.
3. Diff the revision pairs. `LVDOS#1` 1.3 against 1.4, and `LVDOS#2` 1.3
   against 1.4, are the smallest meaningful changes in the collection and the
   manual describes what changed — a good way to calibrate your reading.
4. Start Ghidra on the module R drive ROM. It is 16 KB, self-contained, and its
   diagnostic error codes and OSD strings give you named anchors to work back
   from.
5. Settle the `LVDOS#2` base address before investing in module W.
