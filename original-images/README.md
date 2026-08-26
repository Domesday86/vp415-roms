# Original images

Unmodified dumps of every distinct piece of firmware in the Philips VP415
LaserDisc player (plus the two VP410 images that came with the same
collection), one file per image, named for the device it belongs to.

The source collection is the
[VP415 service guide](https://github.com/domesday86/vp415-service-guide)
repository, under `docs/reference/assets/originals/firmware/` (copied at commit
`07c878b`). That collection holds **28 files but only 11 distinct images** — the
same ROM was read more than once over the years and filed under different names.
Here each image appears exactly once, under the name of the physical part it was
read from. Nothing has been patched, padded or byte-swapped; every file below
hashes identically to its counterpart in the service guide's
[`planning/firmware-checksums.csv`](https://github.com/domesday86/vp415-service-guide/blob/main/planning/firmware-checksums.csv).

## Naming

```
vp415-module-w-ic7247-lvdos1-6805.3-rev1.4-0x8F90.bin
└─┬──┘ └───┬───┘ └─┬──┘ └─┬──┘ └──┬──┘ └─┬──┘ └──┬─┘
 set    module   item   name  Philips   SW    Philips
                       (role) program  rev.   sum16
                              3104 103 …
```

## The images

| File | Set | Module | Item / PCB | Device | Program `3104 103 …` | SW rev. | Size | sum16 | SHA-256 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `vp415-module-r-ic7204-drive-6803.6-rev1.7-0x68FF.bin` | VP415 | R — drive processor | 7204 | TMS 27128 EPROM | 6803.6 | 1.7 | 16 KB | `0x68FF` | `6ec09eeb8d4751b5c833c859a03d726a0030dc20098c917ca4f12a5b51764819` |
| `vp415-module-s-ic7202-control-6804.9-rev1.8-0x6728.bin` | VP415 | S — control | 7202 | TMS 27512 EPROM | 6804.9 | 1.8 | 64 KB | `0x6728` | `e372542baa52e57f25471e6714a26d3a00996744c52aec669f4dfd1dd229c540` |
| `vp415-module-s-w-8041-slave-0xFC62.bin` | VP415 | S (7211) and W | — | NEC D8041AHC-152, mask ROM | not given | — | 1 KB | `0xFC62` | `35d258eb1ee0bfab3b33cd1293153fcf9618a027f1e6da9d3e417353da846856` |
| `vp415-module-w-ic7201-sync-6808.0-rev1.0-0xD120.bin` | VP415 | W — CPU + data grabber | 7201 / IC1 | TMS 27128 EPROM | 6808.0 | 1.0 | 16 KB | `0xD120` | `bc7eb8ca0f1e5d50b70ad65422b763c5d404400d532cb4f6ead8c270f8e462d8` |
| `vp415-module-w-ic7224-descrambler-6807.0-rev1.0-0x1FBE.bin` | VP415 | W — CPU + data grabber | 7224 / IC24 | TMS 27128 EPROM | 6807.0 | 1.0 | 16 KB | `0x1FBE` | `850498330a6d4920b84034dac0842a304570e8eda6d8fb6d8e3781c6bba6a4a4` |
| `vp415-module-w-ic7247-lvdos1-6805.2-rev1.3-0xB42D.bin` | VP415 | W — CPU + data grabber | 7247 / IC47 | TMS 27128 EPROM | 6805.2 | 1.3 | 16 KB | `0xB42D` | `d929bc98adcd200c5aa7979a7933304ad683f481751d7ebae77aa069a1ba5087` |
| `vp415-module-w-ic7247-lvdos1-6805.3-rev1.4-0x8F90.bin` | VP415 | W — CPU + data grabber | 7247 / IC47 | TMS 27128 EPROM | 6805.3 | 1.4 | 16 KB | `0x8F90` | `ecdd68a65ebe45ae4de5f9eb2bcf715d74a6f0ced53e7c655b07c622ab11eb24` |
| `vp415-module-w-ic7248-lvdos2-6806.2-rev1.3-0x1A1C.bin` | VP415 | W — CPU + data grabber | 7248 / IC48 | TMS 27128 EPROM | 6806.2 | 1.3 | 16 KB | `0x1A1C` | `e230f04b178c253332f018b5524f936eccfb09ed48ea69d84ab8495ca6e55042` |
| `vp415-module-w-ic7248-lvdos2-6806.3-rev1.4-0x56D7.bin` | VP415 | W — CPU + data grabber | 7248 / IC48 | TMS 27128 EPROM | 6806.3 | 1.4 | 16 KB | `0x56D7` | `d87e81e193f38593774db4213c4d6e69a90e50675d46d7ca2ab92772fc018d38` |
| `vp410-module-s-control-a-6811.4-0xFC6F.bin` | VP410 | S — control | — | 64 KB EPROM | 6811.4 † | — | 64 KB | `0xFC6F` | `9dee7647ab7480a4ae5fdfdf382001a2cd04413182835b5e0244c65693de9b40` |
| `vp410-module-s-8041-slave-0xC014.bin` | VP410 | S — control | — | NEC D8041AHC, mask ROM | not given | — | 1 KB | `0xC014` | `b061c815822c0e35282a8182a3d972ff8f67961bdd5522eefbfc938d62c9e512` |

† Read off the dumper's filename. `CS 8 284` covers the VP410 but lists no 6811,
so treat that program number as unverified.

`sum16` is Philips' own checksum — a plain 16-bit sum of every byte in the
image, `sum(bytes) & 0xFFFF` — and it is the number printed on the EPROM sticker
and in the manual's survey of software releases. It is the quickest way to
identify a device you have in front of you.

## What each device does

### VP415 — module R, drive processor, item 7204 (`DRIVE`)

The drive processor board runs the deck: it interprets commands from control
module S over the S-bus, does radial tracking and access, reads the Manchester
code, drives the on-screen display, sequences motor start-up, handles local
**standby** and **eject**, switches audio and video, and provides the service
diagnostics that produce the error codes. This EPROM is its whole program, and
the diagnostic mode is part of it. The board's own processor is IC7201; the ROM
sits beside it at IC7204.

Philips shipped three releases — 6803.4 (rev 1.5), 6803.5 (rev 1.6) and 6803.6
(rev 1.7). **Only the last is dumped here.**

### VP415 — module S, control, item 7202 (`CONTROL`)

Control module S is the player's outward-facing processor: the RS232 interface
to a host computer, the front panel, the RC5 remote input, and the UART link to
module W. Its processor IC7201 (11.059 MHz) addresses 64 KB of ROM — this
device — and 8 KB of battery-backed non-volatile RAM at IC7203.

Philips shipped five releases (6804.4, .5, .6, .7 and .9 — .8 was never
produced). **Only the last, 6804.9 / rev 1.8, is dumped here.**

### VP415 — modules S and W, the NEC D8041AHC slave

A UPI-41A slave microcontroller with a 1 KB masked ROM and 64 bytes of RAM,
handling the serial and remote-control I/O for its host processor. On module S
it is IC7211, clocked at 4 MHz by crystal 5102, serving one RS232 and two RC5
I/Os; module W carries the same part.

**One image covers both positions.** Every VP415 8041 dump in the collection —
eight files, filed under both *module S Control* and *module W CPU* names —
decodes to this single 1 KB image. That is not a filing error: both parts are
marked `NEC D8041AHC 152`, lot `8710X7`, and `D8041AHC` is the **mask-ROM**
UPI-41A (not the windowed `D8741A` EPROM), so `152` is the ROM code and two
parts sharing a ROM code share a program. The parts list agrees — `4822 209
10914 — UPD8041AHC-152` is the only 8041 Philips lists, and it sits among the
collective standard components rather than getting a per-module service code.

The caveat worth keeping: this rests on the markings of one pair of boards from
the same lot. A dump from a module W at a different modification level would
confirm it holds across production runs.

The Philips manual gives no program number or revision for the 8041s.

### VP415 — module W, CPU + data grabber

Module W is one of the three *sandwich* boards beneath the main module carrier —
the part that makes a VP415 rather than a VP410. It carries the data grabber,
which pulls LV-ROM data off the disc via LV-ROM decoder module X, and the CPU
that serves it to the host over SCSI. Four programmed TMS 27128 EPROMs:

- **Item 7201 / IC1 — `SYNC`.** The sync detector. A data block starts with a
  12-byte sync pattern; this EPROM, with D-type flip-flops IC6 and IC7, forms a
  labyrinth that emits the `SNC` pulse only when the correct 96-bit pattern has
  passed through it, starting the byte counter. The manual's survey calls the
  program `SYNC`; the circuit description calls the circuit the sequencer.
- **Item 7224 / IC24 — `DESCR.`** The descrambler table. Each byte arriving
  from the shift registers is EXORed in IC16/IC17 with a byte fetched from this
  EPROM on the F bus, and the descrambled result goes out on the G bus to RAM.
- **Items 7247 / IC47 and 7248 / IC48 — `LVDOS#1` and `LVDOS#2`.** The two
  halves of the LV-DOS program run by the module's CPU (8 MHz, crystal 5001).

`SYNC` and `DESCR.` had one release each. LV-DOS had two, 1.3 and 1.4, and
**both halves are here at both revisions**.

> **The LV-DOS EPROMs are a matched pair.** `CS 8 284`'s own footnote: when the
> program number of the EPROMs in a set deviates from the latest, order *both*
> LV-DOS service codes (4822 209 51261 and 51262). Do not run a 1.3 against a
> 1.4.

The 6807 and 6808 images came to the collection from their dumper, Jules, with
a note identifying 6807 as the descrambler (item 7224) and 6808 as the sequencer
(item 7201) — which is what `CS 8 284` says too.

### VP410 — module S

The two VP410 images are included because they arrived with the same collection
and are useful for comparison, not because they belong in a VP415. `CONTROL A`
is a 64 KB EPROM from the VP410's control module; the 8041 is that module's
slave microcontroller, and it is a **different image** from the VP415 one
(`0xC014` against `0xFC62`) — the two machines do not share one program.

## Devices, by part

| Part | Where | Notes |
| --- | --- | --- |
| **TMS 27128** | R 7204; W 7201, 7224, 7247, 7248 | 16 KB EPROM. Service code 4822 209 71312, supplied **unprogrammed** |
| **TMS 27512** | S 7202 | 64 KB EPROM. Service code 4822 209 71317, also supplied unprogrammed |
| **NEC D8041AHC** | S 7211, and module W | UPI-41A slave, 1 KB mask ROM, 64 bytes RAM. Intel **D8741A** is the EPROM version of the same part |

## About the `.hex` files

The two 8041 images were dumped as Intel HEX, and the collection has no raw
binary of either. Both forms are kept here:

- `*.hex` — the dump exactly as it arrived, byte-for-byte.
- `*.bin` — the same data decoded to a flat 1 KB image (records cover
  `0x0000`–`0x03FF` contiguously, so nothing is filled or invented). This is the
  form the checksums in the table above describe, and the form to disassemble.

Everything else in this directory is already a flat binary image, copied
unchanged.

## Known discrepancy: `BF90` vs `8F90`

The manual's survey of software releases gives the checksum of `LVDOS#1`
6805.3 (rev 1.4) as **`BF90`**. The dump here computes **`0x8F90`**, and the
person who made it put `0x8F90` in the filename — so the file agrees with
itself, and this is the *only* one of the collection's fourteen filename
checksums that the manual contradicts. A typewritten `B` misread for an `8` in
1987 is the obvious explanation, but the alternative — that this image is not
the 6805.3 the survey describes — cannot be ruled out without a second dump of
a known-good 6805.3.

## What is missing

Of the 14 releases the manual's survey lists, **8 are dumped** here: the last
`DRIVE`, the last `CONTROL`, and all six module W EPROMs. The six with no dump
are the earlier `DRIVE` 6803.4 and 6803.5, and the earlier `CONTROL` 6804.4,
.5, .6 and .7.

## Verifying a file

```sh
shasum -a 256 vp415-module-r-ic7204-drive-6803.6-rev1.7-0x68FF.bin

python3 -c 'import sys; d=open(sys.argv[1],"rb").read(); print(f"{sum(d)&0xFFFF:#06X}")' \
  vp415-module-r-ic7204-drive-6803.6-rev1.7-0x68FF.bin
```

## Sources

- [VP415 service guide](https://github.com/domesday86/vp415-service-guide) —
  the firmware collection, its
  [firmware reference page](https://github.com/domesday86/vp415-service-guide/blob/main/docs/reference/firmware.md)
  and per-image checksums.
- Philips VP410/VP415 service manual, chapter 8 — survey of software releases
  (`CS 8 284`, page 187) and the descriptions of software modifications
  (`CS 8 285`–`CS 8 289`, pages 188–192).
- Module data sheets and parts lists: `CS 7 851` (module R), `CS 7 852`
  (module S), `CS 7 857` (module W parts, EPROMs).
