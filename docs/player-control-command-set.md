# The VP415 player-control command set

The ASCII command language the player accepts on its serial port — and, on an
AIV machine, over SCSI through module W's gateway. Read out of the ROM that
actually implements it rather than out of the manual: every command character,
what arguments it takes, what it does, what it answers, and what happens when
it cannot.

**Where this lives.** Not in module W. Module W is only a *client* of this
language (see
[`module-w-command-interface.md`](module-w-command-interface.md) §9–10). The
interpreter is in **control module S, item 7202** — `CONTROL` 6804.9 rev 1.8,
`0x6728`, a 64 KB MCS-51 image of which `$0000`–`$D3FF` is programmed.

```sh
python3 tools/vp-mcs51.py \
    original-images/vp415-module-s-ic7202-control-6804.9-rev1.8-0x6728.bin \
    -o disasm
```

All `$xxxx` addresses below are in that image and refer to
`disasm/vp415-module-s-ic7202-control-6804.9-rev1.8-0x6728.lst`.

**Checked against the manual.** The command set below was worked out from the
ROM first and then compared with the VP415 operating instructions. The 37
implemented characters are exactly the 37 documented F-codes, and the
acknowledgement codes and `?P` status bits line up bit for bit — with two
exceptions, in §12.

**Cross-check.** The VP410's control ROM (`6811.4`, `0xFC6F`) is the same
program at different addresses, with the same dispatcher shape and the same
command table — 37 implemented commands on the VP415, the same 37 plus `0` on
the VP410. Table addresses: dispatcher `$5B14`/table `$5E8D` on the VP415,
`$5F6F`/`$6317` on the VP410.

---

## Contents

1. [The two serial ports](#1-the-two-serial-ports)
2. [Wire format](#2-wire-format)
3. [How a command reaches the interpreter](#3-how-a-command-reaches-the-interpreter)
4. [The dispatcher](#4-the-dispatcher)
5. [The command set](#5-the-command-set)
6. [Queries — the `?` group](#6-queries--the--group)
7. [Replies](#7-replies)
8. [Status bits in the `?P` reply](#8-status-bits-in-the-p-reply)
9. [Errors and what the player does *not* answer](#9-errors-and-what-the-player-does-not-answer)
10. [Reaching this command set over SCSI](#10-reaching-this-command-set-over-scsi)
11. [Notes for an emulator](#11-notes-for-an-emulator)
12. [Correspondence with the operating instructions](#12-correspondence-with-the-operating-instructions)

---

## 1. The two serial ports

Module S runs a small cooperative kernel — eight tasks, each with its own
8051 register bank, resumed through a scheduler at `$0030` (see §3). Two of
them own serial hardware, and **both carry the same command language**.

| | Port A | Port B |
| --- | --- | --- |
| Hardware | NEC D8041AHC UPI at external addresses `$F400` (data) and `$F600` (status/command) | The 8051's own UART, `SCON`/`SBUF` |
| Owned by | task 3, initialised at `$D0FF` | task 0, initialised at `$CD57` |
| Also carries | RC5 remote-control codes | — |
| Baud rate | fixed by the 8041's own init (`$81` then `$37`, `$D127`) | selected from bits 3–2 of the hardware latch `$FC00`: `TH1` = `$FD`/`$FA`/`$F4`/`$E8` = 9600/4800/2400/1200 (`$BEB2`–`$BEF8`) |
| Enable flag | `$0DC7` bit 7, mode bits 5–4 must read `10` (`$8A32`, `$C361`) | `$0DC8` bit 7 |

Replies are transmitted on **both** ports whenever their enable flags are set
(`$8A32` for port A, `$8ABD` for port B), so a host on either port sees the
same answers. `$09BE`, which the `)` command sets, is the **transmission
delay** flag, not a port enable: when it is 1, task 0 paces its output
(`$CDEF`, `$CE8B`).

The 8041 tags everything it hands over. Reading `$F400` gives a type byte
first: bits 5–4 = `01` means an RC5 code follows in two more bytes, `10` means
one received character follows (`$C477`). Transmitting is `$A1` to `$F600`
then the byte to `$F400` (`$88F4`); for a short burst the firmware instead
writes `$A0 | count` and then the bytes (`$8A84`). This is exactly the
protocol module W's 8041 primitives speak, which is why module W's
"receive one byte" routine tests for `$A1` and masks the following byte to
seven bits.

## 2. Wire format

**Command:** printable characters terminated by `CR` (`$0D`). Nothing else —
no addressing, no checksum, no line editing, and no echo.

- The line buffer is 12 bytes (`$0DD3`, index `$0DBE`). Reaching index 13
  without a `CR` **discards the whole line silently** (`$C40C`).
- The `CR` is stripped before the command is passed on (`$C38F`), so the
  interpreter sees at most 11 characters.
- Bit 7 of the command character is ignored: the dispatcher masks with `$7F`
  (`$5AFE`), so `A` and `$C1` are the same command.
- Lower case is **not** accepted. After masking, valid characters are `$21`–`$5F`
  (`!` to `_`), which excludes `` ` `` and `a`–`z` (§4).

**Reply:** a letter identifying the answer, then its data, then `CR`. Replies
are never longer than about eight characters. There is no reply at all to most
commands (§9).

## 3. How a command reaches the interpreter

```
8041 ($F400) ──► task 3 $C477   one character at a time, tagged
                     │          appended to the line buffer $0DD3
                     ▼
              task 3 $C361      CR seen: strip it, build a message
                     │          msg[0]=5 (to the command task)
                     │          msg[1]=3 (from task 3)
                     │          msg[2]=length, msg[3..]=the characters
                     ▼
              task 5 $5A7A      copy the body to $0D5F.., length to $0D6C,
                     │          command character to $0D6D
                     ▼
              task 5 $5AE2      the dispatcher (§4)
```

Messages are 16 bytes taken from a pool of 32 at `$0100` (`$0853`); the
pointer for task *t* lives at `$0080 + 2t`. A reply is a message back to
task 3 whose first payload byte is the task-3 opcode `$3D`; task 3 strips
that byte and transmits the rest (`$8A32`, starting at payload index 1).
**`$3D` never appears on the wire** — it is an internal opcode, not a prefix.

The other task-3 opcodes a command can generate:

| Opcode | Effect | Used by |
| --- | --- | --- |
| `$3D` | transmit the rest of the payload on both ports | every reply |
| `$43` | re-initialise the serial interface (`$8800`) | `'`, `:` |
| `$47` | transmit a single `A` on port A (`$88F4`) | — |
| `$48` | queue a single `A` on port B (`$88C9`) | — |
| `$50` | *no-op in this build* | `#` |
| `$52` | set the VP display mode (`$8D28`) | `VP1`–`VP5` |

## 4. The dispatcher

`$5AE2`–`$5B25`:

```
5AE5  A = command character
5AE9  if A >= $E0                       -> $5D15   (internal event codes)
5AEE  if A <  $21                       -> $5D15
5AFA  A &= $7F
5B04  A -= $21
5B0F  if A >= $3F                       -> $5D12   (return, no reply)
5B1B  jump via the table at $5E8D, three-byte ljmp entries
```

63 slots, one per character from `!` (`$21`) to `_` (`$5F`). Each slot has its
own thunk in `$5B26`–`$5D11`; 26 of them are a bare `ljmp $5D12`, which
returns without doing anything or answering. Most thunks first test the
message length in `$0D6C` and do nothing if it is wrong:

```
5C00: mov DPTR,#$0D6C / movx A,@DPTR
5C04: cjne A,#$02,$5C0A     ; wrong length -> fall through to the exit
5C07: lcall $549D           ; right length -> the handler
5C0A: ljmp $5D12
```

`$0D6C` is the **length of the whole command including its letter**, so a
handler that requires 2 wants `<letter><one character>`.

Command characters `$E0` and above are not reachable from the wire: the line
assembler only ever passes characters the 8041 delivered, and the dispatcher
routes `>= $E0` to `$5D15`, which handles **internally generated events**
(§7.3).

## 5. The command set

37 of the 63 slots are implemented, and they are **exactly the 37 the
operating instructions document** — see §12. Argument characters are read
from `$0D60` (the character after the command letter) and `$0D61` (the one
after that).

Where a command is described as "set/clear", the firmware builds a
three-byte S-bus register write `(register, mask, value)` and queues it for
module R, the drive processor, through task 2 message opcode `$1E`
(`$AE7D` → `$CC94`, which appends it to the 20-deep queue at `$0344`). The
value is the mask for argument `1` and zero for argument `0`; **any character
other than `0` is treated as `1`** — only `'0'` is tested (`$54D9`).

| Cmd | Manual's name | Form | Len | Handler | What the ROM does | Reply |
| --- | --- | --- | --- | --- | --- | --- |
| `!` | sound insert (beep) | `!xy` | 3 | `$51D9` | both arguments must be `0`–`9` (`$51DD`–`$51FB`) or the command is dropped; S-bus `(06, 40, 40)`, and the duration digit is stored as `(y & $0F) + 1` doubled at `$0D71` | none |
| `#` | RC-5 output on the Euroconnector | `#xy` | any | `$5250` | packs `x & $3F` and `y & $3F` into a task-3 message with opcode `$50` — **and task 3 maps `$50` to a bare return** (`$8E2E`). Nothing is transmitted (§9) | none |
| `$` | replay switch enable/disable | `$0` / `$1` | 2 | `$528A` | sets `$0CFB`, which `?P` reports as "replay function active". It also sends task-4 opcode `$00`, which that task's bounds check at `$867B` discards | none |
| `'` | eject | `'` | 1 | `$5447` | if no disc → `O`; otherwise task-2 opcode `$3C`, re-initialise the serial interface, reset the three drive registers, task-2 opcode `$16` | `O` when the tray opens, via internal code `$E9` |
| `)` | transmission delay off/on | `)0` / `)1` | 2 | `$52D1` | sets `$09BE`, which paces task 0's output and is reported by `?P` | none |
| `*` | halt / halt and jump | `*` or `*xxxxx±yy` | any | `$A45E` | S-bus `(00, 20, 00)`, then task-2 opcode `$29` (with a number) or `$28` | none |
| `+` | instant jump forward | `+yy` | any | `$52E6` | task-2 opcode `$32` | none |
| `,` | standby / on | `,0` / `,1` | 2 | `$5B78` | `,1` → `$50C2`, `,0` → `$50E6`. Any other argument does nothing | `,1`: `S`, or `O` if the tray is open, via internal code `$EB` |
| `-` | instant jump reverse | `-yy` | any | `$5313` | task-2 opcode `$33` | none |
| `/` | pause | `/` | 1 | `$5340` | S-bus `(00, C0, 00)` | none |
| `:` | reset to default | `:` | 1 | `$542E` | re-initialise the command task (`$77B8`), re-initialise the serial interface (task-3 opcode `$43`), reset the three drive registers | none |
| `?` | status request | `?<letter>` | 2 | `$4B16` | see §6 | varies |
| `A` | audio 1 off/on | `A0` / `A1` | 2 | `$549D` | S-bus `(02, 02, ·)` | none |
| `B` | audio 2 off/on | `B0` / `B1` | 2 | `$54EE` | S-bus `(02, 04, ·)` | none |
| `C` | chapter number display | `C0` / `C1` | 2 | `$553F` | task-4 opcode `$4C`, then task-2 opcode `$26` (`1`) or `$25` (`0`) | none |
| `D` | picture number / time code display | `D0` / `D1` | 2 | `$556A` | task-4 opcode `$4C`, then task-2 opcode `$24` (`1`) or `$23` (`0`) | none |
| `E` | video off/on | `E0` / `E1` | 2 | `$5595` | S-bus `(02, 01, ·)` | none |
| `F` | picture registers and goto | `F<digits><letter>` | any | `$43C0` | see §5.1 | `O`, `AN`, or a later `A<digit>` |
| `H` | RC to computer off/on | `H0` / `H1` | 2 | `$55E6` | sets or clears `$0DC5`, reported by `?P` | none |
| `I` | local control off/on | `I0` / `I1` | 2 | `$563B` | S-bus `(06, 20, ·)` | none |
| `J` | remote control off/on | `J0` / `J1` | 2 | `$5602` | task-4 opcode `$47` (`1`) or `$48` (`0`), which sets or clears `$0DC4` (`$8530`, `$853D`), reported by `?P` | none |
| `L` | still forward | `L` | 1 | `$568C` | S-bus `(00, 60, 00)` | none |
| `M` | still reverse | `M` | 1 | `$56C8` | S-bus `(00, 70, 00)` | none |
| `N` | play forward / play and jump | `N` or `N<digits>±yy` | any | `$A30E` | S-bus `(00, 00, 00)`, then task-2 opcode `$2B` (with a number) or `$2A` | none |
| `O` | play reverse / play and jump | `O` or `O<digits>±yy` | any | `$A3B4` | S-bus `(00, 10, 00)`, then task-2 opcode `$2D` (with a number) or `$2C` | none |
| `Q` | chapter goto and chapter sequence | `Qxx<R\|N>`, `Qxxyyzz S` | any | `$A0D6` | recognises a trailing `N`, `R` or `S`; builds the sequence and raises internal codes `$FA`/`$FB`/`$F3` | `A6`, `A7`; `AN` on failure, `O` if no disc |
| `S` | set fast / slow speed | `Sxxx`, `SxxxF`, `SxxxS` | any | `$4B76` | dispatches on the **total command length** through the table at `$5156`: lengths 2–5 have handlers (`$4B87`, `$4BAE`, `$4C5F`, `$4D70`), 6–11 are stubs. Stores the speed in `$06E9`/`$06EA` (fast) or `$06EB`/`$06EC` (slow) | none |
| `T` | time code goto / info register | `Txxyy<N\|I>` | any | `$4E78` | task-2 opcodes `$06` and `$0D` | `A8`, `A9`; `AN` on failure, `O` if no disc |
| `U` | slow motion forward | `U` | 1 | `$5704` | S-bus `(00, $06EB\|$40, $06EC)` — the slow speed | none |
| `V` | slow motion reverse, **or** video overlay | `V`, `VP<n>`, `VPX` | any | `$579C` | if the second character is `P`, see §5.2; otherwise S-bus `(00, $06EB\|$50, $06EC)` at `$5750` — slow motion reverse | `VP<n>` for `VPX` |
| `W` | fast forward | `W` | 1 | `$5873` | S-bus `(00, 48, $06EA)` — the fast speed | none |
| `X` | clear | `X` | 1 | `$58B9` | task-2 opcode `$3C`, then S-bus `(00, 20, 00)` | none |
| `Z` | fast reverse | `Z` | 1 | `$5910` | S-bus `(00, 58, $06EA)` | none |
| `[` | audio 1 internal/external | `[0` / `[1` | 2 | `$5956` | S-bus `(02, 40, ·)` | none |
| `\` | video internal/external | `\0` / `\1` | 2 | `$59A7` | S-bus `(02, 20, ·)` | none |
| `]` | audio 2 internal/external | `]0` / `]1` | 2 | `$59F8` | S-bus `(02, 80, ·)` | none |
| `_` | teletext from disc off/on | `_0` / `_1` | 2 | `$5A49` | sets or clears bit 7 of the `$FC00` latch (shadow `$0DC0`) and `$0D70`, reported by `?P` | none |

The speed defaults are set in task 3's initialisation at `$8873`–`$888A`:
`$06E9`=8, `$06EA`=6 (fast), `$06EB`=0, `$06EC`=6 (slow) — the manual's
"default 6" for both.

**Not implemented** — accepted by the dispatcher, silently ignored, no reply:
`"` `%` `&` `(` `.` `0` `1` `2` `3` `4` `5` `6` `7` `8` `9` `;` `<` `=` `>` `@`
`G` `K` `P` `R` `Y` `^`. (The VP410 implements `0`; the VP415 does not.)

Digits are in that list because they are never seen alone — a number is always
part of a command that begins with a letter, and the whole line is dispatched
on its **first** character.

**The "reset the three drive registers" sequence** (`$537C`, used by `'` and
`:`) is three S-bus writes: `(02, F7, 07)`, `(03, FA, 32)`, `(06, E0, 20)`.

### 5.1 `F` — position

`F<digits><letter>`, handler `$43C0`. This is the command module W uses for
every seek.

```
43C0  if ($0CF8 & 1) != 1                      -> reply "O"     (no disc)
43CE  if ($0CED & $20) != $20 or ($0CED & 4) != 4 -> reply "AN" (not ready)
43E4  drop the trailing letter, allocate a message for task 2
43EA  look at that letter:
        N -> task-2 opcode $02
        R -> task-2 opcode $01
        Q -> task-2 opcode $03
        I -> task-2 opcode $0A
        S -> task-2 opcode $0B
446F  parse the number ($41E6) into three BCD bytes -> msg[4..6]
4482  send
```

The number parser `$41E6` walks **backwards** from the end of the command,
taking up to five characters. `F`, `N`, `O` and `*` are treated as zero;
anything else is masked to its low nibble, so `0`–`9` become 0–9 and other
characters alias onto them. The five digits are packed into three BCD bytes,
most significant first, at `$0D79`/`$0D7A`/`$0D7B` (`$428D`–`$42FC`).

A successful `F` produces **no immediate reply**. The completion report
arrives later as an `A<digit>` (§7.3) — for example `$40AE` builds the
internal code `$F3`, which becomes `A7`.

### 5.2 `V` — video overlay mode

Only when the second character is `P`. Anything else falls through to
`$5750`, which is slow motion reverse.

- `VP<digit>` → task-3 opcode `$52`, which lands at `$8D28`: clear the low
  three bits of the `$FC00` latch shadow `$0DC0`, then set them from the table
  at `$8E5F`. The encoding is **not** the digit:

  | Command | Latch bits 2–0 | Manual's meaning |
  | --- | --- | --- |
  | `VP1` | `000` | LaserVision video only (power-on default) |
  | `VP2` | `001` | external RGB only |
  | `VP3` | `100` | hard-keyed overlay |
  | `VP4` | `011` | mixed / transparent overlay |
  | `VP5` | `010` | enhanced overlay |

- `VPX` → reply `VP<n>`. The digit is built as `'1' + (latch & 7)` (`$57E9`),
  which would give `VP5` for a latch of `100`; `$5805`–`$583A` then exchanges
  `3` and `5`, which **undoes** the encoding above. `VPX` therefore returns
  the digit that was set — set `VP3`, read `VP3`.

  (An earlier draft of this document read the exchange in isolation and
  claimed `VPX` swapped 3 and 5. It does not; the two transforms cancel.)

`VP6` and `VP7` do not exist here — only `VP1`–`VP5` and `VPX`. Module W
reserves `6` and `7` for its own read-mode flag and never forwards them.

## 6. Queries — the `?` group

`?<letter>`, handler `$4B16`, requires length exactly 2. The letter is
indexed as `letter − $3D` into the table at `$510B`.

> **There is no bounds check.** `$4B1D`–`$4B32` subtracts `$3D` and jumps
> straight through the table. The table has 25 entries (`$510B`–`$5155`) and
> the `S` command's table begins immediately after it at `$5156`, so
> `?V` through `?a` land in that table and jump into the `S` handlers;
> a second character below `=` wraps to a large index and jumps somewhere
> arbitrary. **Only `?=` through `?U` are safe.**

| Query | Manual's name | Handler | Reply | Source |
| --- | --- | --- | --- | --- |
| `?=` | revision level | `$489D` | `=<5 characters>` — `0`, drive major, drive minor, control major, control minor | `$0CF6`, `$0CF7` |
| `?C` | chapter number | `$4560` | `C<2 digits>`, `00`–`79` | `$0CE9` |
| `?D` | disc program status | `$493E` | `D<5 characters>` | `$0CF0`–`$0CF2`, BCD |
| `?F` | picture number | `$4486` | `F<5 digits>`, `00001`–`59999` | `$0CE6`–`$0CE8`, BCD |
| `?P` | player status | `$4609` | `P<5 status characters>` | many, see §8 |
| `?U` | user code | `$4A32` | `U<5 characters>` | `$0CF3` |
| `?>` `??` `?@` `?A` `?B` `?E` `?G`–`?O` `?Q`–`?T` | — | none | stubs at `$4B38`–`$4B70` |

`$0CE6`–`$0CFA` are the drive processor's status registers as received over
the S-bus and stored around `$C0C6`–`$C20A`. Their bit meanings belong to
module R's ROM, which is not covered here.

Every implemented query guards on the disc being loaded and answers `O` if it
is not (`$4559`, `$4602`, `$4896`, `$4A2B`); `?F` and `?D` additionally answer
`X` when the value they would report is all `$FF`, i.e. not yet known
(`$4554`, `$4A26`).

## 7. Replies

### 7.1 The fixed short replies

| Wire | Built at | Meaning as used by the firmware |
| --- | --- | --- |
| `O` `CR` | `$413F` | the operation cannot proceed — no disc loaded, or the deck reports not ready |
| `X` `CR` | `$4172` | the value asked for is not available |
| `A` `N` `CR` | `$41A5` | **negative acknowledgement** — the command was recognised but cannot be carried out in the current state (wrong disc type, goto failed) |

Callers: `O` from `$4479`, `$4559`, `$4602`, `$4896`, `$4A2B`, `$4B0F`,
`$50BB`, `$50DF`, `$5496`, `$A307`; `X` from `$4554`, `$45FD`, `$4A26`,
`$4B0A`; `AN` from `$4477`, `$50B3`, `$A2F7`, `$A2FF`.

### 7.2 The query replies

All follow the shape `<letter><data>CR`, and all are built into a message with
`$3D` as the internal opcode, so on the wire the `$3D` is gone:

```
=Fnnnnn   ->  wire:  F n n n n n CR      7 characters
=P#####   ->  wire:  P # # # # # CR      7 characters
=Dnnnnn   ->  wire:  D n n n n n CR      7 characters
=Cnn      ->  wire:  C n n CR            4 characters
=Unnnnn   ->  wire:  U n n n n n CR      7 characters
==nnnnn   ->  wire:  = n n n n n CR      7 characters
=VPn      ->  wire:  V P n CR            4 characters
```

Message byte 2 is the count of characters actually transmitted.

### 7.3 The asynchronous `A` replies

Internal event codes reach the command task as ordinary messages whose command
byte is `$E0` or above (`$5D15`). Two ranges exist:

**`$E9`–`$EB`** (`$5D29`, table `$5F4A`) produce a one-letter reply:

| Code | Reply | Raised by |
| --- | --- | --- |
| `$E9` | `O` | the tray opening — the documented response to `'` (eject) |
| `$EA` | *nothing* | — |
| `$EB` | `S` if the message's fifth byte is zero, otherwise `O` | the documented response to `,1` (on), `O` if the tray is open |

**`$F2`–`$FE`** (`$5DBE`, table `$5F53`) produce `A<digit>`:

| Code | Reply | What the manual says that acknowledgement is for |
| --- | --- | --- |
| `$FC`, `$FE` | `A0` | `FxxxxxR` goto and halt; `FxxxxxQ` goto and continue |
| `$FD` | `A1` | `FxxxxxN` goto and play |
| `$F4` | `A2` | `FxxxxxS` picture number stop register reached |
| `$F5` | `A3` | `FxxxxxI` picture number info register passed |
| `$FA`, `$FB` | `A6` | `QxxR` / `QxxN` chapter goto |
| `$F3` | `A7` | `QxxyyzzS` chapter sequence finished |
| `$F9` | `A8` | `TxxyyN` time code goto |
| `$F2` | `A9` | `TxxyyI` time code info register passed |
| `$F6`–`$F8` | *no digit emitted* | — |

That mapping was derived from the ROM tables alone and then checked against
the operating instructions: every acknowledgement the manual documents —
`A0`, `A1`, `A2`, `A3`, `A6`, `A7`, `A8`, `A9` — appears, and no others. There
are no `A4` or `A5`.

If the event carries a non-zero parameter in `$0D60` the digit is **replaced
by `N`**, giving `AN` (`$5E67`–`$5E7A`). Codes outside `$F1`–`$FE` return
without answering (`$5DAD`).

Identified producers: `$40AE` emits `$F3` (→ `A7`) when a positioning step
completes; the `Q` command emits `$FD` and `$FE` at `$A229` and `$A238`.

This is why a successful `F<digits>R` produces nothing at once and an
`A`-something later, and why module W — which waits for a reply and only
checks whether the first character is `A` — is satisfied either way.

## 8. Status bits in the `?P` reply

Five status characters follow the `P`. Each starts at `$40` (`@`) and has bits
OR-ed into it, so a character with no bits set is `@` and the reply for a
completely idle player is `P@@@@@`. Positions below are **wire positions**,
counting the `P` as byte 0.

| Wire byte | Bit | Manual's meaning (1 =) | Set when | Test at |
| --- | --- | --- | --- | --- |
| 1 | 5 | normal mode (disc loaded) | `$0CED & $04` | `$4692` |
| 1 | 2 | chapter play | `$06CE == 1` | `$46DC` |
| 1 | 1 and 0 | goto action | `$0CEE & $80` | `$46B7` |
| 2 | 2 | chapter numbers exist | `$0CE9 != 0` | `$46FF` |
| 2 | 1 | **CLV detected** | `$0CED & $10` | `$4723` |
| 2 | 0 | **CAV detected** | `$0CED & $20` | `$4748` |
| 3 | 2 | replay function active | `$0CFB != 1`, or `$0CFB & $40` clear | `$476D` |
| 3 | 0 | frame lock | `$0CF8 & $20` **clear** | `$479A` |
| 4 | 4 | RS232-C transmission delay | `$09BE == 1` (the `)` command) | `$47BE` |
| 4 | 3 | remote control enabled | `$0DC4 == 1` (the `J` command) | `$47E1` |
| 4 | 2 | RC routed to computer | `$0DC5 == 1` (the `H` command) | `$4804` |
| 4 | 1 | local controls enabled | **never set — see below** | — |
| 5 | 5 | audio channel 2 enabled | `$0CF9 & $04` | `$4827` |
| 5 | 4 | audio channel 1 enabled | `$0CF9 & $02` | `$484C` |
| 5 | 3 | teletext enabled | `$0D70 == 1` (the `_` command) | `$4871` |

The names come from the operating instructions; the sources and addresses come
from the ROM, and the two agree bit for bit — except one. The builder at
`$4609`–`$4894` contains exactly fourteen `orl A,#` instructions and none of
them touches bit 1 of wire byte 4, so **"local controls enabled" is documented
but never reported** by this revision. The `I0`/`I1` command that would set it
sends its state to the drive processor over the S-bus and module S does not
keep a copy.

Module W's TEST UNIT READY reads **wire byte 2, bit 1** — "CLV detected" — and
reports SCSI sense key 3, MEDIUM ERROR, when it is set. That now reads as
exactly what it is: LV-ROM data is only carried on CAV discs, so a CLV disc in
an AIV player is a medium error. Module W rejects the whole reply if wire byte
0 is not `P`, which is how a serial timeout becomes NOT READY.

For the same reason the `F` command's guard at `$43CE` requires `$0CED` bit 5
(CAV detected) **and** bit 2 (normal mode) before it will accept a picture
number.

`$0CED` is also the register the `F` command tests before it will accept a
seek: it needs bit 5 set and bit 2 set (`$43CE`).

## 9. Errors and what the player does *not* answer

There is no error reply for a bad command. The failure modes, in the order
a character meets them:

| Condition | Where | Result |
| --- | --- | --- |
| Line longer than 12 characters with no `CR` | `$C40C` | the entire line is discarded; no reply |
| Port A not enabled, or its mode bits not `10` | `$C361`, `$C36B` | the line is never assembled; no reply |
| Command character below `$21` after masking | `$5AEE` | routed to `$5D15`, which ignores anything below `$E9`; no reply |
| Command character `$60`–`$7F` (masks to `$60`–`$7F`, index ≥ `$3F`) | `$5B0F` | return; no reply |
| Command character has no handler (26 of the 63) | `$5D12` | return; no reply |
| Command has a handler but the wrong length | e.g. `$5C04` | return; no reply |
| Argument is neither `0` nor `1` | e.g. `$54D9` | treated as `1` |
| No disc loaded | `$43C0`, `$4559`, … | reply `O` |
| Value not yet known | `$4554`, `$45FD` | reply `X` |
| Deck not in a state that permits the command | `$43CE` | reply `AN` |

**A command that is simply wrong is answered with silence.** Any host talking
to this player needs a timeout; module W uses about 3.5 seconds and then
fabricates `AN` for itself.

**One documented command does nothing.** `#xy`, RC-5 output on the
Euroconnector, is accepted, its parameters are masked to six bits and packed
into a task-3 message with opcode `$50`, and task 3's opcode table sends `$50`
to a bare `ret` at `$8E2E`. The ROM does contain a working "transmit RC-5"
path — 8041 command `$93` at `$BE84` — but it is driven by *received* RC-5
codes when `$0DD2` is set (`$C42A`), which is the pass-through the `H` command
controls. Nothing reaches it from `#`. Treat `#` as a no-op in 6804.9.

The one genuine hazard is `?` with a second character outside `=`…`U` (§6),
which jumps through the end of its table. Task 2 has the same shape of
unchecked dispatch (`$AE10`, table `$AF35`), but nothing on the wire can reach
it directly. Task 4, by contrast, *is* bounds-checked (`$867B`–`$869A`), which
is why the `$` command's task-4 message is simply dropped.

## 10. Reaching this command set over SCSI

On an AIV machine the host normally talks SCSI to module W, and module W
carries this language through:

- **`$CA`** — the host sends 256 bytes of DATA OUT; the first 33 are kept, the
  command is the characters up to the first `CR`. Module W upper-cases the
  string, validates and rewrites part of it, and forwards the rest verbatim on
  its own link to module S.
- **`$C8`** — the host reads back 256 bytes of DATA IN: the 12-byte reply line,
  `CR` terminated, zero padded.

Two consequences of module W sitting in the middle:

1. **Frame numbers are relative to the LUN.** Module W parses the digits of an
   `F` command itself, rejects a frame beyond the LUN's maximum with SCSI sense
   key 5, and adds the LUN's start frame before forwarding.
2. **`VPX`, `VP6`, `VP7`, `SJH0`, `SJH1` and `SJH2` never reach module S** —
   module W handles them itself. `VP6`/`VP7` in particular are not commands
   this ROM knows: only `VP1`–`VP5` and `VPX` exist here.

Module W's own use of the language is: `?P`, `?D`, `?F`, `F<n>N`, `F<n>R`,
`E0`, `E1`, `D1`, `*`, `:`, `,0`, `,1`, `VP3`, `07 07`, and the mount-time
block `[0 ]0 \0 A0 B0 E0 D0 C0 I1 J1 H0 )0 $0 _1`. Every one of those is in
the table in §5.

Note `,0`: the `,` handler requires length 2 **and** an argument of `0` or `1`,
and does nothing at all otherwise (`$5B78`–`$5BA0`).

## 11. Notes for an emulator

1. **Terminate on `CR` only.** No LF handling, no backspace, no echo.
2. **12-byte line limit**, and an over-length line vanishes without a trace.
3. **Mask bit 7, reject below `$21` and above `$5F`.** Lower case is invalid.
4. **Length is checked before the argument.** `A` alone does nothing; `A0` and
   `A1` work; `A00` does nothing.
5. **Any argument that is not `0` is `1`** for the on/off commands.
6. **Silence is the normal answer.** Only queries, and the failure paths of
   `F`/`Q`/`T`/`'`, produce anything immediately.
7. **Replies have no prefix.** `Fnnnnn`, `P@@@@@`, `O`, `X`, `AN`, `A7` — then
   `CR`. The `$3D` in the ROM is an internal message opcode.
8. **`?P` returns five characters based at `@`**, and a host that only wants
   "is it ready" should look at wire byte 2 bit 1, as module W does.
9. **Positioning is asynchronous.** `F12345R` answers nothing; the completion
   arrives later as `A<digit>` or `AN`.
10. **Both ports get every reply**, so an emulator with a single port is
    faithful as long as the other is disabled.
11. **`VPX` round-trips.** The latch encoding is not the digit (§5.2), but the
    reply builder compensates, so what you set is what you read.
12. **`#` transmits nothing**, and `?P` never sets "local controls enabled".

## 12. Correspondence with the operating instructions

The command table in §5 was derived from the ROM before the manual's own list
was consulted. Checking the two against each other afterwards:

- The 37 characters the dispatcher implements are **exactly** the 37 the
  operating instructions document — `!` `#` `$` `'` `)` `*` `+` `,` `-` `/`
  `:` `?` `A` `B` `C` `D` `E` `F` `H` `I` `J` `L` `M` `N` `O` `Q` `S` `T` `U`
  `V` `W` `X` `Z` `[` `\` `]` `_`. The 26 slots that are a bare return are
  exactly the 26 characters the manual does not list.
- The six implemented `?` sub-commands are exactly the six documented ones
  (`?=` `?C` `?D` `?F` `?P` `?U`); the other 19 slots in that table are stubs.
- The internal event codes map onto precisely the documented acknowledgements
  `A0` `A1` `A2` `A3` `A6` `A7` `A8` `A9`, with no spare codes and no `A4` or
  `A5` (§7.3).
- All fourteen status bits the `?P` builder sets land on documented meanings
  (§8).
- The speed defaults in the ROM (`$06EA` = 6, `$06EC` = 6) are the manual's
  documented defaults.

Two places where the ROM and the manual differ, both noted in place:

| Manual says | 6804.9 does |
| --- | --- |
| `#xy` transmits an RC-5 command on pin 8 of the Euroconnector | accepts the command and discards it (§9) |
| `?P` byte x4 bit 1 reports "local controls enabled" | never sets that bit (§8) |

Neither was found by looking for it; both fell out of reading every code path
the dispatcher can reach.

## Sources and limits

Everything above was read out of `CONTROL` 6804.9 rev 1.8 with
`tools/vp-mcs51.py`, which decodes 79.8% of the programmed bytes and resolves
all 66 jump tables it meets. The VP410 control ROM was decoded the same way
(82.2%, 71 tables) purely as a cross-check on the command table.

The command names and the meanings in §8 come from the VP415 operating
instructions, as transcribed in the
[VP415 service guide](https://github.com/domesday86/vp415-service-guide)
(`docs/operating-instructions/f-code-commands.md`). Everything else —
handlers, addresses, message opcodes, bit sources, failure paths — is from the
ROM. Where the two disagree, §12 says so and the ROM wins.

What is **not** settled here:

- **What each S-bus register write actually does.** The `(register, mask,
  value)` triples are recorded exactly, but the register semantics live in
  module R's drive-processor ROM (`DRIVE` 6803.6), which this document does
  not cover. `tools/vp-mcs51.py` decodes that image too — it is 16 KB of the
  same instruction set.
- **The `S`, `T` and `Q` command families** are identified and their entry
  points and dispatch tables are given, but their sub-commands are not
  enumerated. `S` dispatches on total length through `$5156`; `T` is at
  `$4E78`; `Q` at `$A0D6`.
- **The meaning of the drive status bits** reported by `?P`, `?C`, `?D`, `?F`,
  `?U` and `?=` — the source registers are named, their bit meanings are
  module R's.
- **The RC5 remote path.** The 8041 delivers remote codes on the same port
  (`$C41B`) and they are routed to task 4, not to this interpreter.
