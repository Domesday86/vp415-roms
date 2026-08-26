# VP415 module W — the host command interface

What module W's firmware **actually does**, read out of the ROM rather than out
of the manual: the SCSI target interface it presents to the host computer, the
serial interface it presents to control module S, the gateway between them, and
every error and status value either can produce.

Written for someone building an emulator of the interface. Where the firmware
departs from the SCSI standard or from the manual, the firmware is described and
the departure is flagged.

**Source:** `LVDOS#1` 6805.3 rev 1.4 (`0x8F90`) and `LVDOS#2` 6806.3 rev 1.4
(`0x56D7`), analysed as one image with `LVDOS#1` at `$0000` and `LVDOS#2` at
`$4000`. Every claim carries the ROM address it came from. Revision 1.3 has an
identical command set at shifted addresses — see
[`module-w-lvdos-vm.md`](module-w-lvdos-vm.md) §10 for the mapping.

**Read this first if you want to verify anything:** LV-DOS is not native Z80.
It is byte code for an interpreter, and a normal disassembler produces garbage
for most of the image. [`module-w-lvdos-vm.md`](module-w-lvdos-vm.md) documents
the machine, and `tools/vp-lvdos.py` regenerates the listings that all the
addresses below refer to:

```sh
python3 tools/vp-lvdos.py \
    original-images/vp415-module-w-ic7247-lvdos1-6805.3-rev1.4-0x8F90.bin \
    original-images/vp415-module-w-ic7248-lvdos2-6806.3-rev1.4-0x56D7.bin \
    -o disasm
```

Addresses written `$0D94` are byte-code addresses in `disasm/lvdos-pcode.lst`;
addresses written `$18AD` in the hardware sections are Z80 addresses in
`disasm/lvdos-native.lst`.

---

## Contents

1. [What is connected to what](#1-what-is-connected-to-what)
2. [I/O port map](#2-io-port-map)
3. [The native primitive table](#3-the-native-primitive-table)
4. [The SCSI bus engine](#4-the-scsi-bus-engine)
5. [The command state machine](#5-the-command-state-machine)
6. [The SCSI command set](#6-the-scsi-command-set)
7. [Status, message and sense](#7-status-message-and-sense)
8. [Error and status code reference](#8-error-and-status-code-reference)
9. [The serial interface to module S](#9-the-serial-interface-to-module-s)
10. [The SCSI-to-serial gateway](#10-the-scsi-to-serial-gateway)
11. [The data path](#11-the-data-path)
12. [Notes for an emulator](#12-notes-for-an-emulator)

---

## 1. What is connected to what

Module W has two serial-ish interfaces, and the ROM is unambiguous about their
directions:

- **SCSI.** Module W is a **target only**. It waits to be selected, accepts a
  command descriptor block, executes it, returns status, and releases the bus.
  It never arbitrates for the bus and never acts as an initiator. This is the
  host computer's connection.

- **The 8041 serial link.** Module W is the **master**. It sends ASCII
  player-control commands and reads short ASCII replies. It never waits for an
  unsolicited command and never acts on one; the only unsolicited traffic it
  handles is a stray reply, which it reads and discards (`PROC_1F2E` at
  `$1F2E`). The other end of this link is control module S, which owns the
  player mechanism, the front panel and the machine's external RS232 port.

So the host's RS232 connection lands on module S, not on module W. What makes
module W look like it has an RS232 command set is that **it exposes the serial
command language to the host over SCSI**: vendor opcode `$CA` sends a command
string down the serial link and `$C8` reads the reply back (§10). That gateway
is almost certainly what the manual's command tables describe, and it is the
part an emulator has to get right.

```
   host computer ──SCSI──► module W ──8041 serial──► module S ──► deck
                            (LV-DOS)                 (control)
                            target                   master side
                                                     of the link
```

## 2. I/O port map

Every `in`/`out` in the firmware, with the routine that proves it.

| Port | Dir | Function | Evidence |
| --- | --- | --- | --- |
| `$00` | R/W | SCSI data. Read after an input phase, written before an output phase | `$1816`, `$182B` |
| `$01` | W | SCSI phase / control register — see §4 | `$17F0`, `$1828`, `$1885` |
| `$02` | W | `1` = arm selection detect, `0` = disarm | `$1AC6`, `$1AF0` |
| `$04` | R | SCSI handshake status. bit 7 = ready for the next byte, bit 1 = DMA count exhausted | `$17F2`, `$1C5B` |
| `$06` | R | SCSI interrupt cause, latched into `$B719` by the ISR. bit 0 = byte transfer completed, bit 3 = we were selected | `$4F34`, `$1AD7` |
| `$09` | R | SCSI bus/ID status. `$80` expected when idle; `(x & $87) == $80` after the initialisation handshake | `$1929`, `$194D` |
| `$0C`,`$0D`,`$0E` | W | 24-bit DMA transfer counter, LSB first. Always loaded with `00 01 00` = 256 | `$1C43`–`$1C4B` |
| `$20` | R/W | 8041 UPI data register | `$1154`, `$1188` |
| `$21` | R/W | 8041 UPI status (R) / command (W). bit 0 = OBF, bit 1 = IBF | `$108E`, `$1178` |
| `$34` | R/W | Data-grabber control and status. Written: bit 0 pulsed low = interrupt acknowledge, bit 5 = reset pulse, bit 6 = start capture, bit 7 = latch. Read: bit 0 = sync found, bit 1 = capture done, bit 2 = byte-strobe, bit 3 = status | `$4F24`, `$19A0`, `$19AC`, `$1A7D` |
| `$35` | W | Grabber mode select, 0–4; the last value written is kept at `$B702` | `$1294`–`$12BC` |
| `$37` | R | Interrupt source. bit 0 = SCSI, bits 1 and 2 = recognised but handled as no-ops | `$4F0C` |
| `$40`,`$41`,`$42` | R | Current picture number from the disc, three BCD bytes | `$1A75` |

The interrupt handler is at `$4F0A` (IM 1, installed by `$4ED2`). On a SCSI
interrupt it latches port `$04` into `$B71A` and port `$06` into `$B719`, sets
the flag `$B718`, then pulses port `$34` bit 0 to acknowledge.

Hardware initialisation, called once from the byte code at `$429A`, is native
code at `$4ED2`:

```
4ED2: im 1
4ED4: ld c,$00 / call $0FC9      ; primitive 0  -- initialise the 8041
4ED9: ld a,$11 / ld ($B72B),a
4EDE: res 0,a / res 4,a / out ($34),a
4EE4: set 0,a / set 4,a / out ($34),a   ; reset pulse to the grabber
4EEA: ei
4EEB: ld c,$17 / call $0FC9      ; primitive 23 -- initialise the SCSI target
4EF0: ret
```

## 3. The native primitive table

All hardware access goes through one native routine, `$0010`, dispatched by
selector through a 44-entry jump table at `$0FDF`. The byte code calls it
through the wrapper `PROC_003C` (and its per-module clones `$1DAC`, `$303D`,
`$385D`, `$4863`), passing `(selector, byte argument, word argument)` and
receiving a byte result.

| Sel | Address | Function |
| --- | --- | --- |
| 0 | `$108E` | Initialise the 8041: command `$81`, data `$27`. Clears `$B71F`, `$B718` |
| 1 | `$10B8` | Read one character of a serial reply line (see §9.2) |
| 2 | `$1168` | Send one byte to the serial link (8041 command `$A1`, then the byte) |
| 3 | `$118D` | Send *A* bytes from `(DE)` to the serial link — **never called** |
| 4 | `$11C8` | Is a serial character available? Returns 1 if the line buffer is non-empty, else port `$21` bit 0 |
| 5 | `$11DC` | Serial transmitter ready — **never called** |
| 6–10 | `$128F`–`$12B7` | Write grabber mode 0/1/2/3/4 to port `$35` — **never called** |
| 11 | `$12C1` | Read back the last grabber mode — **never called** |
| 12 | `$12C7` | Delay loop, *A* × ≈340 µs at 8 MHz |
| 13 | `$12D8` | Read byte `E` of 256-byte block `D` (0–23) of the current frame buffer. **Block ≥ 24 hangs the CPU in an infinite loop at `$12EA`** |
| 14 | `$1306` | Error-correct buffer *A* (1, 2 or 3). Returns 0 = clean, 1 = uncorrectable. Uses the GF log/antilog tables at `$15EC` and `$16EC` |
| 15 | `$1AEE` | SCSI bus free: port `$02` ← 0, port `$01` ← `$01` |
| 16 | `$17EC` | **SCSI DATA OUT** — receive one byte from the host. Failure code 8 |
| 17 | `$1823` | **SCSI DATA IN** — send one byte to the host. Failure code 9 |
| 18 | `$1850` | Stub, returns immediately |
| 19 | `$1853` | **SCSI MESSAGE IN** — send one byte. Failure code 6 |
| 20 | `$1880` | **SCSI STATUS** — send one byte. Failure code 7 |
| 21 | `$18AD` | **SCSI COMMAND** — receive one CDB byte. Failure code 3 |
| 22 | `$18E6` | **SCSI MESSAGE OUT** — receive one byte. Failure code 6. **Never called** |
| 23 | `$1911` | Initialise the SCSI target (§4.2). Failure code 4 |
| 24 | `$1AC4` | Arm selection detect and block until selected. Failure code 5 |
| 25 | `$1AEB` | Stub, returns immediately |
| 26 | `$1C17` | **SCSI DATA IN by DMA** — send *E* blocks of 256 bytes starting at frame block *A*. Failure code 10 |
| 27 | `$1966` | Peek the byte at `(DE)` — **never called** |
| 28,29,30 | `$196A`,`$1975`,`$1980` | Load the three BCD digits of the target picture number into `$B720`–`$B722` |
| 31 | `$198B` | Capture one frame (§11). Returns 0–4 |
| 32–35 | `$1AF9`–`$1B73` | BCD/binary and hex/ASCII conversions — **never called** |
| 36 | `$1BCA` | RAM test of `$2000`–`$27FF` — **never called**, and would fail, since that range is ROM |
| 37 | `$1BF8` | 16-bit sum of `$0000`–`$1FFF` — **never called** |
| 38 | `$1D08` | Copy one 256-byte frame block to `(DE)` — **never called** |
| 39 | `$11E6` | Select which frame-buffer bank the pointers `$B73A`/`$B73C`/`$B73E` address: 0 = the grabber buffers `$8004`/`$8934`/`$9264`, 1 = `$B800`/`$C000`/`$C800`, 2 = `$D000`/`$D800`/`$E000`, 3 = `$E800`/`$F000`/`$F800` |
| 40 | `$1257` | Send *DE* zero bytes over SCSI DATA IN (pad an under-length reply) |
| 41 | `$1274` | Consume and discard *DE* bytes from SCSI DATA OUT |
| 42 | `$1D30` | Copy the three 2048-byte grabber buffers into RAM bank *A* (1–3) |
| 43 | `$114E` | Read one byte from the 8041. If the first byte read is `$A1` it is a framing prefix and the next byte, masked to 7 bits, is the data |

Selectors 3, 5, 6–11, 18, 22, 25, 27, 32–38 are dead code in this build.

## 4. The SCSI bus engine

### 4.1 The phase register

Port `$01` selects the bus phase and starts a handshake. Bit 6 set means
"programmed transfer, one byte at a time"; bit 6 clear means "DMA".

| Value written | Phase | Direction | Primitive |
| --- | --- | --- | --- |
| `$4C` | COMMAND | host → player | 21 |
| `$4D` | DATA OUT | host → player | 16 |
| `$4E` | MESSAGE OUT | host → player | 22 |
| `$50` | STATUS | player → host | 20 |
| `$51` | DATA IN | player → host | 17 |
| `$52` | MESSAGE IN | player → host | 19 |
| `$11` | DATA IN, DMA | player → host | 26 |
| `$01` | bus free | — | 15 |

The low bits are consistent: `+0` = a control phase (command in / status out),
`+1` = data, `+2` = message; base `$0C` for phases the target receives, base
`$10` for phases the target drives.

### 4.2 Target initialisation (primitive 23, `$1911`)

```
1911: out ($34),$00 / out ($34),$01     ; clear the interrupt latch
1919: ($B718) = 0
191E: out ($01),$00                     ; idle the phase register
1922: primitive 12 with A=1             ; ~340 us settle
1929: in a,($09) ; expect $80           ; retry the whole sequence if not
1930: out ($01),$4B
1934: out ($00),$AA
1938: wait for the interrupt flag
1945: if ($B719) bit 0 = 0        -> code 4
194D: in a,($09) ; (a & $87) must be $80 -> else code 4
1956: ($B71F) = 0
```

Writing `$4B` to the phase register with `$AA` on the data lines is the
target's own configuration write; the firmware spins at `$1911` until port `$09`
reads `$80`, so an emulated port `$09` must return `$80` or the player never
boots.

### 4.3 Byte-at-a-time transfers

Input phases (primitives 16 and 21) do a double write:

```
17EC: out ($01),$4D                 ; arm the phase
17F2: wait until (in $04) bit 7 = 1 ; hardware ready
17F8: out ($01),$4D                 ; assert REQ
17FE: wait for the interrupt flag ($B718)
1805: ($B718) = 0
180A: if ($B719) bit 0 = 0  -> ($B71F) = 8, return with A undefined
1816: A = in ($00)
```

Output phases (17, 19, 20) write the phase register then the data register and
wait for the same interrupt; there is no port `$04` wait.

### 4.4 Block transfer (primitive 26, `$1C17`)

Used only by READ. `A` is the first 256-byte block of the current frame, `E`
the number of blocks. For each block:

```
1C41: out ($0C),$00 / out ($0D),$01 / out ($0E),$00   ; count = 256
1C4D: out ($01),$11                     ; DATA IN, DMA (bit 6 clear)
1C55: wait until (in $04) bit 7 = 0
1C5B: loop: if (in $04) bit 1 -> done
            outi                        ; one byte to port $00
            wait until (in $04) bit 7 = 0
1C6B: out ($01),$11
1C71: wait for the interrupt; ($B719) bit 0 must be set, else ($B71F) = 10
1C84: dec the block count; advance the block index; repeat
```

The source address is computed from the block index: blocks 0–7 come from the
first buffer pointer, 8–15 from the second, 16 and above from the third.

### 4.5 The SCSI result latch is never read

Every primitive writes a result code to `$B71F` — 0 on success, otherwise one
of 3–10. **Nothing in the byte code ever reads `$B71F`.** A phase failure is
therefore invisible to LV-DOS: the primitive returns, the application carries
on with whatever was on the data bus, and no sense data is generated. For an
emulator this means the SCSI-level codes in §8 are diagnostics, not host-visible
errors.

## 5. The command state machine

### 5.1 The outer loop

`PROC_4287` (`$4287`, the program entry point) is the whole command loop.

```
$4287  initialise: current LUN = 7, sense = 0, first-command flag = 0
$429A  CALL $4ED2         -- native hardware init (im 1, 8041, grabber, SCSI)
$429E  CALL $4050         -- clear all eight LUN descriptors
$42A2  loop:
$42A6    if $A7D2 != 0 -> HALT           (never taken; see below)
$42AD    sense key = 0
$42B1    CALL $1FF2       -- wait for selection, fetch and classify the CDB
$42C3    if this is the first command since reset, the sense key is still 0
         and the opcode is $08 or $28 -> CALL $4112 (automatic mount)
$42D6    first-command flag = 1
$42DA    if sense key != 0 -> save it in $A87D[LUN], CALL $0D94 (send status)
$42FC    if sense key != 0 -> back to the top of the loop
$42FF    load this LUN's state into the working globals
$4383    if $A7F3[LUN] != 0, i.e. the LUN is mounted:
$4388      $1B                       -> CALL $4112 (mount), CALL $0D94
$4399      $0403 (STOP)              -> CALL $21AC, CALL $4050
$43AB      anything else             -> CALL $21AC
$43C0      write the LUN state back
$4421      if the LUN was ready but the player reported not ready during the
           command -> CALL $4050, unmounting everything
$4441      back to the top of the loop
$4444    otherwise the LUN is not mounted:
$4444      $C8 or $CA                -> CALL $21AC
$4458      $0403 (STOP)              -> CALL $21AC, CALL $4050
$446A      $1B (START)               -> CALL $4112, CALL $0D94
$447B      $03 or $03EB              -> reload the sense address, CALL $21AC
$449E      $00 or $01                -> sense key 2 (NOT READY), CALL $0D94,
                                        clear this LUN's sense address
$44C7      $08 or $28                -> sense key 2 (NOT READY), CALL $0D94
$44DE      save the sense key in $A87D[LUN]
$44EF  jump to loop
$44F2  HALT
```

`$A7D2` is written once, with 0, at `$4297` and read only at `$42A6`, so the
`HALT` at `$44F2` is unreachable: the loop runs forever. The only way out is a
VM trap (§8.4) or a reset.

### 5.2 Selection and CDB fetch — `PROC_1FF2` (`$1FF2`)

```
$1FFB  primitive 24 -- arm port $02 and block until the initiator selects us
$2017  primitive 21 -- receive CDB byte 0 into $B7B6
$203F  group code = CDB[0] DIV 32                       -> $B792
$2053  CDB length by group:  0 -> 6   1 -> 10   5 -> 12   6 -> 6   7 -> 10
$208F  for i = 1 to length-1: primitive 21 -> $B7B6[i]
$20C4  LUN = CDB[1] DIV 32                              -> $AA75
$20D2  sense key = 5 (ILLEGAL REQUEST)
$20D6  ...cleared to 0 if CDB[0] is one of
       $28 $08 $C8 $CA $03 $1B $00 $01 $0A $2A
$2153  if CDB[0] = $03 and CDB[4] >= 8 -> internal command $03EB
$2169  if CDB[0] = $1B and CDB[4]  = 0 -> internal command $0403
$2180  copy $B7B6[0..11] to the saved-CDB area $B79A
```

The CDB lands at `$B7B6`, twelve bytes, `$B7B6 + n` = CDB byte *n*. The
opcode is also kept as a 16-bit "internal command" at `$AA83`, which is how the
two `$03xx`/`$04xx` pseudo-opcodes above can exist alongside the real opcodes.

Three things here are worth an emulator author's attention:

- **Groups 2, 3 and 4 have no entry.** `$B7AE` keeps whatever value it had, and
  `$B7AE` is reused by the READ path (`$2501`). An opcode in `$40`–`$9F` will
  therefore read a CDB of unpredictable length. If that length exceeds 12 the
  range check at `$20A3` fails and the CPU **halts** (VM trap 15).
- **MESSAGE OUT is never entered.** Primitive 22 exists but has no caller. The
  player does not consume an IDENTIFY message; the LUN comes from CDB byte 1
  only.
- **No INQUIRY.** Opcode `$12` is not in the accepted list and gets sense key 5.

### 5.3 Command execution — `PROC_21AC` (`$21AC`)

```
$21B5  restore the saved CDB from $B79A into $B7B6
$21E0  if $08 (READ 6):  decode the CDB, range-check, set up the transfer
$22A6  if $28 (READ 10): decode the CDB, range-check, set up the transfer
$2356  if $08 or $28 (either read is now internal command $08): do the transfer
$26DF  final dispatch:
         $C8   -> CALL $3FBE
         $CA   -> CALL $3B40
         $03   -> CALL $0A9F   (4-byte sense)
         $03EB -> CALL $0BF2   (8-byte sense)
         $1B   -> CALL $0F85   (start playing)
         $0403 -> CALL $0ED4   (stop)
         $00   -> CALL $0DFB   (test unit ready)
         $01   -> CALL $0E57   (rezero)
$2746  CALL $0D94  -- always: send status, send message, release the bus
```

### 5.4 The bus phase sequence for one command

Every command follows the same shape. There is no disconnect/reconnect and no
message phase other than the single COMMAND COMPLETE at the end.

```
BUS FREE
  → (initiator selects)                         primitive 24
  → COMMAND       n bytes, n from the group code  primitive 21
  → [DATA OUT     only for $CA: exactly 256 bytes] primitives 16, 41
  → [DATA IN      $03/$03EB: 4 or 8 bytes;
                  $C8: exactly 256 bytes;
                  $08/$28: 256 bytes per block]  primitives 17, 40, 26
  → STATUS        1 byte                          primitive 20
  → MESSAGE IN    1 byte, always $00              primitive 19
  → BUS FREE                                      primitive 15
```

## 6. The SCSI command set

Ten opcodes are accepted. Anything else returns CHECK CONDITION with sense key
5 and transfers no data.

| Opcode | Name | CDB length | Data phase | Handler |
| --- | --- | --- | --- | --- |
| `$00` | TEST UNIT READY | 6 | none | `$0DFB` |
| `$01` | REZERO UNIT | 6 | none | `$0E57` |
| `$03` | REQUEST SENSE | 6 | DATA IN, 4 or 8 bytes | `$0A9F` / `$0BF2` |
| `$08` | READ (6) | 6 | DATA IN | `$21E0` + `$2356` |
| `$0A` | WRITE (6) | 6 | none — accepted and ignored | — |
| `$1B` | START / STOP UNIT | 6 | none | `$0F85` / `$0ED4` |
| `$28` | READ (10) | 10 | DATA IN | `$22A6` + `$2356` |
| `$2A` | WRITE (10) | 10 | none — accepted and ignored | — |
| `$C8` | *vendor:* read player reply | 6 | DATA IN, 256 bytes | `$3FBE` |
| `$CA` | *vendor:* send player command | 6 | DATA OUT, 256 bytes | `$3B40` |

`$0A` and `$2A` pass the acceptance filter at `$213A` and `$2146` — they get
sense key 0 — but no handler matches them in `PROC_21AC`, so they fall straight
through to `$2746` and return GOOD status having transferred nothing. A host
that issues a WRITE and then waits in DATA OUT phase will hang.

Common to all commands: the LUN is `CDB[1] >> 5`, range 0–7, and each LUN has
its own descriptor and its own pending sense key.

### 6.1 `$00` TEST UNIT READY — `PROC_0DFB` (`$0DFB`)

| CDB byte | Use |
| --- | --- |
| 0 | `$00` |
| 1 | bits 7–5 LUN; rest ignored |
| 2–5 | ignored |

```
$0E04  CALL $02E9   -- discard any pending serial reply
$0E08  CALL $0311   -- clear the reply buffer
$0E18  send "?P" + CR to module S
$0E1C  read the reply
$0E20  if reply[0] != 'P'      -> sense key 2 (NOT READY)
$0E29  else if bit 1 of reply[2] is set -> sense key 3 (MEDIUM ERROR)
$0E52  CALL $3249   -- position to picture 1 with "F1R", then query "?D"
```

Returns no data. GOOD if the player answered `P` with bit 1 of the third
character clear.

Note the interaction with the outer loop: on an **unmounted** LUN the command
never reaches this handler at all — `$449E` short-circuits it to sense key 2 and
also clears that LUN's saved sense address.

### 6.2 `$01` REZERO UNIT — `PROC_0E57` (`$0E57`)

```
$0E60  discard any pending reply, clear the reply buffer
$0E68  target frame = max(1, this LUN's start frame)
$0E85  send "F<frame>R" + CR
$0E93  read the reply
$0E97  if reply[0] != 'A' -> sense key 3 (MEDIUM ERROR)
$0EA7  if reply[0] == 'O' -> sense key 2 (NOT READY), mark the LUN not ready
$0EBB  if no error: send "E1" + CR
```

Returns no data. On an unmounted LUN, `$449E` returns sense key 2 without
touching the deck.

### 6.3 `$03` REQUEST SENSE

The CDB's allocation length, `CDB[4]`, selects between two entirely different
sense formats — this is decided at `$2153` in the CDB classifier, not in the
handler:

- `CDB[4] < 8` → internal command `$03`, handler `PROC_0A9F` (`$0A9F`), **4
  bytes**
- `CDB[4] >= 8` → internal command `$03EB`, handler `PROC_0BF2` (`$0BF2`), **8
  bytes**

The player always sends exactly 4 or exactly 8 bytes; it does not truncate to
`CDB[4]` and does not pad. See §7.3 for the formats.

Executing REQUEST SENSE also reloads the reported address from the LUN's saved
value (`$448B`) before dispatching.

### 6.4 `$08` READ (6) — `$21E0`

| CDB byte | Use |
| --- | --- |
| 0 | `$08` |
| 1 | bits 7–5 LUN, bits 4–0 logical block address bits 20–16 |
| 2 | LBA bits 15–8 |
| 3 | LBA bits 7–0 |
| 4 | transfer length in blocks; 0 means 256 |
| 5 | control — **must be zero**, see §6.6 |

```
$21EC  LBA = (CDB[1] mod 32) * 65536 + CDB[2] * 256 + CDB[3]
$221E  physical block = LBA * (this LUN's block factor) + 24 * (start frame)
$2257  length = CDB[4]; if 0 -> 256                     ($2265)
$226B  total 256-byte blocks = block factor * length
$2283  if physical block + total - 24 * start frame > extent size
            -> sense key 13, command cancelled ($FFF8)
```

A LUN's *block factor* is the number of 256-byte units in one logical block; it
comes from the disc label (§11.3) and defaults to 1.

### 6.5 `$28` READ (10) — `$22A6`

| CDB byte | Use |
| --- | --- |
| 0 | `$28` |
| 1 | bits 7–5 LUN |
| 2 | **ignored** |
| 3 | LBA bits 23–16 |
| 4 | LBA bits 15–8 |
| 5 | LBA bits 7–0 — but **must be zero**, see §6.6 |
| 6 | ignored |
| 7 | transfer length, **least** significant byte |
| 8 | transfer length, **most** significant byte |
| 9 | ignored |

```
$22B3  LBA    = CDB[3] * 65536 + CDB[4] * 256 + CDB[5]
$22D0  length = CDB[8] * 256 + CDB[7]
$22DE  total 256-byte blocks = block factor * length
$2333  same end-of-extent check as READ (6) -> sense key 13
```

> **The transfer length is byte-swapped relative to SCSI.** The standard puts
> the most significant byte in CDB[7]; this firmware reads CDB[8] as the most
> significant. `$22D0` loads `$B7BE` (CDB[8]), multiplies by 256, then adds
> `$B7BD` (CDB[7]). A length of 1 block must be sent as `CDB[7]=$01,
> CDB[8]=$00`; sending it the standard way asks for 256 blocks.

A length of zero is **not** special-cased in READ (10) — it means zero blocks,
and the command returns GOOD having sent nothing.

### 6.6 The read transfer — `$2356` onward

```
$235E  if the read mode flag ($AA77, set by VP6/VP7) is 0,
       send "E" "0" CR to module S
$239E  if $AA79 is set (SJH1), force the block count to 25
$23AB  if CDB[5] != 0 -> transfer length 0 and sense key 5 (ILLEGAL REQUEST)
$23BB  if the read mode flag is 1, poll the serial link and re-issue
       "*" CR, "?F" CR ...
$24DF  while blocks remain:
$24E7    CALL $03DC   -- make sure the wanted frame is in a buffer bank
$24EB    if the grab failed, stop
$24F3    starting block within the frame = round(24 * frame - physical block)
$2504    blocks this pass = min(24 - start, blocks remaining)
$252D    if $AA79 is clear:
$2535      primitive 26 -- DMA that many 256-byte blocks to the host
$2551      subtract from the block count, advance the frame
$255B    otherwise (SJH1): transfer nothing, send "E" "1" CR, reset the block
         count to 48 and step to the next frame -- a continuous frame-stepping
         mode that only ends when a grab fails ($25CB)
$25A4    advance the running block and frame numbers
```

So the unit of transfer on the bus is **256 bytes**, and a video frame carries
**24 of them** (6144 bytes, held as three 2048-byte buffers). A read that spans
a frame boundary is split into several DMA bursts with a frame grab between
them.

> **CDB byte 5 must be zero.** The check at `$23AB` applies to both reads. For
> READ (6) that byte is the control byte and zero is normal. For READ (10) it
> is the least significant byte of the logical block address, so **READ (10)
> only accepts addresses that are a multiple of 256** — anything else is
> rejected with sense key 5 and a zero-length transfer, even though the address
> arithmetic at `$22C8` has already folded the byte into the address. Combined
> with the byte-swapped length field, READ (10) on this firmware is not usable
> as standard SCSI; READ (6) is the command the system actually relies on.

### 6.7 `$1B` START / STOP UNIT

`CDB[4]` bit 0 (in fact the whole byte, tested against zero at `$2172`) selects:

- `CDB[4] != 0` → **START**. The outer loop calls `PROC_4112` (`$4112`), which
  mounts the disc: it reads the label frame, fills in the extent, start frame,
  maximum frame and block factor for every LUN present, marks them ready, then
  calls `PROC_0F85` (`$0F85`) to spin up and position the deck. Status is sent
  by the outer loop at `$4477`.
- `CDB[4] == 0` → **STOP**, internal command `$0403`, handler `PROC_0ED4`
  (`$0ED4`), followed by `PROC_4050` (`$4050`) which clears every LUN
  descriptor.

`PROC_0ED4` begins `if ($AA6D) == 410 then do nothing but flush the serial
input`. `$AA6D` is set to 410 — the decimal model number of the **VP410** — at
`$3842` whenever the unit is started, and to nothing else anywhere in the ROM.
On a VP415 the whole "`,0` then `:`" reset sequence at `$0EEC`–`$0F79` is
therefore dead code, and STOP UNIT after a START does nothing to the deck. A
STOP issued before the first START (while `$AA6D` is still 0 from the reset RAM
clear) *does* run it.

### 6.8 `$C8` read player reply — `PROC_3FBE` (`$3FBE`)

Returns the 12-byte reply buffer belonging to this LUN, then pads to 256 bytes
with zeros.

```
$3FCD  CALL $3B18  -- if a reply is outstanding, fetch it from module S first
$3FD1  base = 12 * LUN
$3FDF  for i = 0 to 11: primitive 17 sends $A8B1[base+i], then clears it
$4021  $A8B1[base] = CR      -- leave the buffer looking empty
$4033  primitive 40 sends (256 - 12) zero bytes
```

The transfer is **always 256 bytes**. The count comes from `$AA7D`, which is a
constant 256 written once at `$384D` during START and never derived from the
CDB. Whatever allocation length the CDB carries is ignored.

The 12 bytes are the reply line module W last read from module S, `CR`
terminated, zero padded. A buffer that has never been filled reads as `CR`
followed by zeros; on a serial timeout it reads `A` `N` `CR` (§9.3).

### 6.9 `$CA` send player command — `PROC_3B40` (`$3B40`)

Accepts a 33-byte command string, discards the rest of the 256-byte transfer,
then interprets or forwards it.

```
$3B49  if no serial session is open, CALL $0060 (resynchronise the link)
$3B5D  for i = 0 to 32: primitive 16 receives a byte into $A92C[i]
$3B91  primitive 41 discards (256 - 33) further DATA OUT bytes
$3BB4  fold 'a'..'z' to upper case in place
$3BFF  CALL $3B18 -- drain any outstanding reply
       ...interpret (see §10.2)...
$3E91  if not fully handled: send $A92C[] byte by byte to module S,
       stopping after the first CR
$3F7A  clear $A92C[]
$3F9F  if a reply is expected, CALL $3FAC -- but see below
```

Again the transfer length is fixed at 256 bytes.

The reply is *not* fetched during this command. `PROC_3FAC` (`$3FAC`) is called
from `PROC_0D94` at `$0DF6` — **after** status and message have been sent and
the bus released. The host must therefore issue a separate `$C8` to collect it,
and there is a real window in which the reply has not arrived yet.

## 7. Status, message and sense

### 7.1 Command completion — `PROC_0D94` (`$0D94`)

Runs at the end of every command that reaches `PROC_21AC`, and is called
directly by the outer loop for the paths that bypass it.

```
$0D9D  status = 2 if the sense key is non-zero, else 0
$0DB0  primitive 20 -- STATUS phase, send the status byte
$0DC7  primitive 19 -- MESSAGE IN phase, send $00
$0DDC  primitive 15 -- bus free
$0DEE  if a player reply is expected, CALL $3FAC to go and read it
```

| Status byte | Meaning |
| --- | --- |
| `$00` | GOOD |
| `$02` | CHECK CONDITION |

No other status is ever generated: no BUSY, no RESERVATION CONFLICT, no
INTERMEDIATE. The message byte is always `$00` (COMMAND COMPLETE), and no other
message is ever sent or received.

### 7.2 Sense keys

The pending sense key lives in `$AA73` while a command runs and is saved
per-LUN in `$A87D[LUN]` at `$44DE` (and at `$42E2` on the early-error path). REQUEST SENSE reads it back through `$AA6B`
(`$4338`).

| Key | Name | Set at | Condition |
| --- | --- | --- | --- |
| 0 | NO SENSE | many | success |
| 2 | NOT READY | `$00CF` | serial resynchronisation got the reply `O` |
| | | `$06EA` | during a frame grab, the player replied `O` |
| | | `$0E4F` | TEST UNIT READY: the reply to `?P` did not begin `P` |
| | | `$0EB4` | REZERO: the reply began `O` |
| | | `$3270`, `$337D`, `$33FD`, `$35A5` | the mount sequence could not talk to the deck |
| | | `$44AD` | TEST UNIT READY or REZERO on an unmounted LUN |
| | | `$44D7` | READ on an unmounted LUN |
| 3 | MEDIUM ERROR | `$083F` | more than 20 accumulated frame-grab failure points |
| | | `$0850` | more than 20 accumulated uncorrectable-data failures |
| | | `$0E48` | TEST UNIT READY: bit 1 of the player status byte set |
| | | `$0EA4` | REZERO: the positioning reply did not begin `A` |
| | | `$32AF`, `$32D1`, `$32EB`, `$32F2`, `$36C1`, `$3768` | the disc label could not be read |
| 5 | ILLEGAL REQUEST | `$20D3` | the opcode is not one of the ten accepted |
| | | `$23B8` | READ with a non-zero CDB byte 5 — see §6.6 |
| | | `$3C9B` | `$CA` with a frame number beyond the disc |
| | | `$3DB3`, `$3DC0` | `$CA` with `VP<n>` where *n* is outside `1`–`5` |
| 13 (`$0D`) | *block address out of range* | `$229D`, `$234D` | the read would run past the end of the LUN's extent |

Key 13 is `$0D`, which standard SCSI-1 assigns to VOLUME OVERFLOW. Here it
means the requested logical block plus the transfer length exceeds the extent
recorded in the disc label. Both sites also force the internal command to
`$FFF8`, cancelling the transfer.

### 7.3 Sense data formats

**Four-byte form**, `CDB[4] < 8`, `PROC_0A9F` (`$0A9F`), sent with primitive 17:

| Byte | Value | Built at |
| --- | --- | --- |
| 0 | sense key, with bit 7 set if the key is 3 — so `$83` for MEDIUM ERROR, otherwise the bare key (built at `$0AE0`) | `$0B14` |
| 1 | address bits 23–16 | `$0B40` |
| 2 | address bits 15–8 | `$0BAF` |
| 3 | address bits 7–0 | `$0BE0` |

**Eight-byte form**, `CDB[4] >= 8`, `PROC_0BF2` (`$0BF2`):

| Byte | Value | Built at |
| --- | --- | --- |
| 0 | `$80` if the sense key is 3, else `$00` (built at `$0C33`) | `$0C5C` |
| 1 | `$00` | `$0C73` |
| 2 | sense key | `$0C8C` |
| 3 | `$00` | `$0CA3` |
| 4 | address bits 23–16 | `$0CCF` |
| 5 | address bits 15–8 | `$0D3E` |
| 6 | address bits 7–0 | `$0D6F` |
| 7 | `$00` | `$0D86` |

The eight-byte form lines up with SCSI extended sense — byte 2 is the key,
bytes 3–6 are a four-byte information field, byte 7 is the additional length —
except that byte 0 carries `$80`/`$00` where the standard expects `$70`/`$F0`.
The four-byte form is SCSI-1 non-extended sense with the error class left at 0
(vendor unique).

The address reported is *not* the failing logical block. It is the value the
LUN was carrying in `$A7D3[LUN]`, loaded into `$AA63` at `$448B`, which the
grab path fills in with a frame number. It is cleared to zero whenever
TEST UNIT READY or REZERO fails on an unmounted LUN (`$44B4`).

Neither form is truncated to the allocation length and neither is padded.

## 8. Error and status code reference

Three independent numbering schemes exist. Only the first is visible to the
host.

### 8.1 Host-visible

Status byte `$00` / `$02`, plus the sense keys 0, 2, 3, 5 and 13 in §7.2. That
is the complete set.

### 8.2 SCSI engine result codes — `$B71F`

Written by the native primitives, **never read** (§4.5). Useful only for
understanding the hardware.

| Code | Written at | Meaning |
| --- | --- | --- |
| 0 | several | success |
| 3 | `$18DC` | COMMAND phase byte not acknowledged |
| 4 | `$195E` | target initialisation handshake failed |
| 5 | `$1ADB` | woken by an interrupt that was not a selection |
| 6 | `$1878`, `$1909` | MESSAGE IN or MESSAGE OUT byte not acknowledged |
| 7 | `$18A5` | STATUS byte not acknowledged |
| 8 | `$181B` | DATA OUT byte not acknowledged |
| 9 | `$1848` | DATA IN byte not acknowledged |
| 10 | `$1C9A` | DMA block transfer not acknowledged |

### 8.3 Frame-capture result — primitive 31 (`$198B`)

Returned to the byte code and used to drive the retry loop at `$06A4`.

| Code | Returned at | Meaning |
| --- | --- | --- |
| 0 | `$1A38` | the wanted picture was captured and verified |
| 1 | `$1A3D` | the picture number arrived but did not match the target |
| 2 | `$1A5B` | captured on the alternate path — counted separately at `$0825` |
| 3 | `$1A60` | timed out waiting for the sync detector (port `$34` bit 0) |
| 4 | `$1A65` | the picture number changed under the capture |

The retry policy is at `$0835` and `$0846`: either counter exceeding 20 gives
sense key 3 (MEDIUM ERROR). Codes 1 and 4 add 1 to the first counter, code 3
adds 2, and code 2 adds 1 to the second counter, which also counts
uncorrectable blocks reported by primitive 14.

### 8.4 Interpreter traps

If the byte code raises a VM trap the CPU **halts** — no status, no bus free,
the initiator times out. The full list is in
[`module-w-lvdos-vm.md`](module-w-lvdos-vm.md) §9. The two an emulator can
provoke from the bus are:

- trap 15 (range check) at `$20A3`, if the CDB length left in `$B7AE` by a
  group-2/3/4 opcode exceeds 12;
- trap 7 (heap exhausted) at `$288D`, on deep recursion — not reachable from
  the command interface in practice.

There is also a **hard hang**, not a trap: primitive 13 loops forever at
`$12EA` if asked for a frame block of 24 or more.

## 9. The serial interface to module S

### 9.1 Framing

The link runs through the NEC D8041AHC UPI at ports `$20`/`$21`.

- **Initialise** (primitive 0, `$108E`): wait for IBF clear, write `$81` to the
  command port `$21`, wait, write `$27` to the data port `$20`.
- **Send a byte** (primitive 2, `$1168`): wait for IBF clear (draining any
  pending output byte via `$11BF`), write `$A1` to the command port, wait, write
  the byte to the data port.
- **Receive a byte** (primitive 43, `$114E`): wait for OBF, read the data port.
  If the byte is `$A1` it is a framing prefix — wait for OBF again, read again,
  and mask to 7 bits. Otherwise the byte is returned as read.

### 9.2 The line reader — primitive 1 (`$10B8`)

Returns one character at a time from a 32-byte line buffer at `$B750`, refilling
it a line at a time.

```
$10B8  if characters remain in the buffer, return the next one
$10C0  poll port $21 bit 0, with primitive 12 (A=2, ~0.7 ms) between polls,
       for up to $1400 = 5120 attempts -- roughly 3.5 seconds
$10E3  on timeout: the line becomes { $FF, CR }
$10F8  otherwise read with primitive 43 and append; stop at CR or 32 characters
$113D  a 32-character overrun returns CR
```

Every reply reader checks for `$FF` in the first position and treats it as a
lost link.

### 9.3 Replies module W understands

Replies are read into a 12-byte buffer, `CR` terminated, by one of three
identical readers: `PROC_025F` (`$025F`, into `$A9AD`), `PROC_1F2E` (`$1F2E`,
into `$B7D1`, used to swallow unsolicited traffic) and `PROC_3A48` (`$3A48`,
into `$A919` and then into the per-LUN `$C8` buffer `$A8B1`).

| First character | Meaning to module W | Checked at |
| --- | --- | --- |
| `A` | command accepted / completed | `$0E97` |
| `O` | **not ready** — clears the LUN's ready flag and gives sense key 2 | `$00C5`, `$02DB`, `$06D9`, `$0EA7`, `$1FAA`, `$3AC4` |
| `P` | the answer to `?P`; bit 1 of the third character set means MEDIUM ERROR | `$0E20`, `$0E29` |
| `$FF` | serial timeout. The reader fabricates the reply `A` `N` `CR` and resynchronises the link with `PROC_0060` | `$02BA`, `$1F89`, `$3AA3` |
| second character `N` | during a frame grab, a rejected positioning command; retried | `$06A8` |

Fabricating `AN` on a timeout means **a dead serial link mostly reads as
success**, because most call sites only test the first character against `A`.
The exception is TEST UNIT READY, which wants `P` and so reports NOT READY.

### 9.4 The resynchronisation handshake — `PROC_0060` (`$0060`)

```
$0069  primitive 2  -- send ' '
$007B  primitive 2  -- send ' '
$008D  primitive 43 -- read one byte
$00A0  primitive 2  -- send 'F'
$00B2  primitive 43 -- read one byte
$00C5  if that byte is 'O' -> sense key 2 (NOT READY)
```

Two spaces terminate any half-typed numeric argument the far end may be holding;
the lone `F` provokes an answer.

### 9.5 Commands module W sends

Built by `PROC_00D3` (`$00D3`, cloned as `$3061` and `$3881`), which takes
`(first character, last character, value)` and emits

```
<first character> <decimal digits of value, no leading zeros> <last character> CR
```

The digit thresholds are at `$00FC`, `$013E`, `$0180`, `$01C2`, `$0204` —
9999.5, 999.5, 99.5, 9.5, 0.5 — so a value of 0 emits no digits at all and
`("?", "P", 0)` produces `?P` `CR`. Either character may be 0 to omit it.

| Sent | Issued at | Purpose |
| --- | --- | --- |
| `?P` CR | `$0E18` | request player status — TEST UNIT READY |
| `?D` CR | `$3287` | request disc status |
| `?F` CR | `$23F8`–`$241E` | request the current picture number |
| `F<n>N` CR | `$0653`, `$08C5`, `$0993` | position to picture *n* for a data grab |
| `F<n>R` CR | `$0E8F`, `$325E`, `$35D4` | position to picture *n* and run |
| `E0` CR | `$2371`, `$3661` | leave still / enter the read mode |
| `E1` CR | `$0ECF`, `$2577`, `$2684`, `$3E85` | still frame |
| `D1` CR | `$3E75` | paired with `E1` by the `SJH2` gateway command |
| `*` CR | `$0779`, `$0A31`, `$23D2`, `$26C4` | halt / freeze |
| `:` CR | `$0F65`, `$35E7` | reset |
| `,0` CR | `$0F56` | (STOP UNIT path, unreachable — §6.7) |
| `,1` CR | `$3554` | enable |
| `VP3` CR | `$34FC`, `$360D` | select display mode 3 |
| `07 07` CR | `$06CD` | two `BEL` characters, sent to clear the far end after a rejected positioning command |
| `[0` `]0` `\0` `A0` `B0` `E0` `D0` `C0` `I1` `J1` `H0` `)0` `$0` `_1`, each CR terminated | `$341D`–`$34ED` | the mount-time configuration block, sent in that order |

## 10. The SCSI-to-serial gateway

This is the part of module W that a host actually uses to control the player,
and the reason the SCSI interface appears to carry an RS232 command set.

### 10.1 The protocol

1. The host issues `$CA` and transfers 256 bytes of DATA OUT. The first 33 are
   kept; the rest are discarded. The command is the leading characters up to
   the first `CR`.
2. Module W upper-cases the string, interprets the parts it cares about (§10.2)
   and forwards the whole thing to module S unless it handled it itself.
3. Module W returns GOOD status.
4. **After** the bus is released, if the command was one that produces a reply,
   module W reads the reply line into this LUN's 12-byte buffer.
5. The host issues `$C8` and transfers 256 bytes of DATA IN: the 12-byte reply,
   `CR` terminated, then zero padding.

Both transfers are always 256 bytes whatever the CDB says (§6.8, §6.9).

### 10.2 What module W intercepts

Interception happens in `PROC_3B40`. Anything not listed is passed through
untouched.

| Command | Handled at | Behaviour |
| --- | --- | --- |
| `F<digits>…` | `$3C03` | The digits are parsed into a frame number. If it exceeds the LUN's maximum frame plus one, the command is rejected with sense key 5 (`$3C9B`). Otherwise the frame number is offset by the LUN's start frame and forwarded |
| `VPX` | `$3CE0` | Not forwarded. Fills this LUN's reply buffer with `V` `P` `<current mode digit>` `CR` — a query of the current display mode |
| `VP6` | `$3D6F` | Not forwarded. Sets the read mode flag `$AA77` to 1 |
| `VP7` | `$3D80` | Not forwarded. Sets the read mode flag to 0 |
| `VP1`–`VP5` | `$3D99` | The digit is stored as the current mode and `V`, `P`, `<digit>` are forwarded. `VP0` or `VP6`–`VP9` reaching this point give sense key 5 (`$3DB3`, `$3DC0`) |
| `SJH0` | `$3E42` | Not forwarded. Zeroes the working start frame `$AA5F`, so subsequent addressing is relative to picture 0 |
| `SJH1` | `$3E53` | Not forwarded. Sets `$AA79`, which switches READ into the frame-stepping mode of §6.6 |
| `SJH2` | `$3E60` | Not forwarded. Sends `D1` CR then `E1` CR to module S |

`SJ` commands are recognised only in the four-character form `SJH<digit>`:
`$3E25` tests for `S` and `J`, `$3E35` requires the third character to be `H`,
and the digit is the fourth. `SJ` followed by anything else falls through to
the pass-through path.

After forwarding, `$3ED1`–`$3F77` decides whether a reply is expected. It sets
the flag `$AA7F` when:

- the command begins with `?` (`$3F08`);
- the command begins with `F` and does **not** end with `S` or `I` (`$3F15`);
- the command begins with `Q` and ends with `N` (`$3F42`);
- the command begins with `Q` and ends with `R` (`$3F5E`).

Only then is `PROC_3FAC` called after status, and only then does a subsequent
`$C8` return anything new.

## 11. The data path

### 11.1 Geometry

| Quantity | Value | Evidence |
| --- | --- | --- |
| SCSI transfer block | 256 bytes | the DMA counter at `$1C41`, always `$000100` |
| Frame buffer | 3 × 2048 bytes at `$8004`, `$8934`, `$9264` | primitive 39, `$11EB` |
| Blocks per video frame | 24 | primitive 13's block-to-buffer mapping (`$12D8`) and the constant 24.0 used throughout the address arithmetic |
| Payload per frame | 6144 bytes | 24 × 256 |
| Cache | 3 banks in RAM above `$B800` | primitive 42, `$1D30` |

All the block-and-frame arithmetic is done in **4-byte Microsoft Binary Format
floating point**, which is why constants such as 24.0, 1000.0, 100000.0 and
54000.0 appear in the listing rather than integers.

### 11.2 Capturing a frame

`PROC_03DC` (`$03DC`) is the cache manager: it looks for the wanted frame among
the three banks, and on a miss picks the least recently used bank, positions the
deck and captures.

The capture itself is primitive 31 (`$198B`):

```
$198B  di; clear the expected picture number
$1997  pulse port $34 bit 5 (reset), clear bits 6 and 7
$19A9  wait up to $14FF polls of port $34 bit 0 for sync -> else code 3
$19BC  read the three BCD picture-number bytes from ports $40/$41/$42
$19C5  BCD-subtract the target from the current picture number
$19F1  if the difference is not 1, step forward and try again
$1A05  skip (difference) fields via the port $34 bit 2 strobe
$1A10  set port $34 bit 6 -- start the capture
$1A1A  wait for port $34 bit 1 (done) or bit 3
$1A25  set port $34 bit 7 -- latch
$1A2F  re-read the picture number and verify -> code 4 on a mismatch
$1A38  code 0
```

Each of the three buffers is then error-corrected by primitive 14 (`$1306`),
which is a Reed–Solomon style pass over 43 × 26 symbols using the Galois-field
log and antilog tables at `$15EC` and `$16EC`. It returns 1 if the block is
uncorrectable, which feeds the retry counter.

### 11.3 The disc label

`PROC_4887` (`$4887`) reads the LUN table from the label frame. The frame is
grabbed, then primitive 13 reads it as eight 256-byte records, record *n*
describing LUN *n*:

| Offset in the record | Read at | Meaning |
| --- | --- | --- |
| `$2E`, `$2F` | `$4A12`, `$4A3E` | fractional adjustment to the start frame (divided by 24) |
| `$37` | `$4ABE` | block factor — 256-byte units per logical block; 0 is corrected to 1 (`$4ACB`) |
| `$38`–`$3A` | `$48E4`, `$4906`, `$4932` | extent size, three bytes, least significant first |
| `$3C`–`$3E` | `$497E`, `$49A0`, `$49CC` | maximum frame number |
| `$3E`, `$3F` | `$4A70`, `$4A92` | start frame |

Everything is little-endian, unlike the SCSI CDBs. An extent size of zero on
LUN 0 is corrected to 2 (`$4962`), and the maximum frame is clamped to 54000
(`$49EA`) — 36 minutes at 25 frames per second, a full CAV side.

The per-LUN state the label produces lives in eight-element arrays:

| Array | Meaning |
| --- | --- |
| `$A7D3` | last reported sense address, 4-byte float |
| `$A7F3` | mounted / ready flag |
| `$A805` | start frame, 4-byte float |
| `$A827` | extent size, 4-byte float |
| `$A849` | start frame used for addressing, 4-byte float |
| `$A86B` | block factor |
| `$A87D` | pending sense key |
| `$A88F` | maximum frame, 4-byte float |
| `$A8B1` | 12-byte `$C8` reply buffer, 8 × 12 = 96 bytes |

## 12. Notes for an emulator

Behaviour to reproduce, with the reason:

1. **Port `$09` must read `$80`** or initialisation at `$1911` never completes
   and the player never reaches its command loop.
2. **Selection is the only entry point.** No arbitration, no ATN, no IDENTIFY
   message. The LUN comes from CDB byte 1 bits 7–5 and nothing else.
3. **CDB length comes from the group code**: `$00`–`$1F` and `$C0`–`$DF` are 6
   bytes, `$20`–`$3F` and `$E0`–`$FF` are 10, `$A0`–`$BF` are 12. `$40`–`$9F`
   is undefined and can halt the CPU.
4. **Ten opcodes**: `$00 $01 $03 $08 $0A $1B $28 $2A $C8 $CA`. Everything else
   is CHECK CONDITION / ILLEGAL REQUEST with no data phase. There is no INQUIRY
   and no MODE SENSE.
5. **`$0A` and `$2A` return GOOD and do nothing.** Do not enter DATA OUT.
6. **READ (10) transfer length is little-endian**, CDB[8] is the high byte.
   And **CDB byte 5 must be zero for both reads** (§6.6), which limits
   READ (10) addresses to multiples of 256.
7. **REQUEST SENSE returns 4 bytes if `CDB[4] < 8`, 8 bytes otherwise**, never
   the allocation length, never padded.
8. **`$C8` and `$CA` always transfer exactly 256 bytes**, whatever the CDB says.
9. **Status is only ever `$00` or `$02`**, and the message is only ever `$00`.
10. **A `$CA` reply is not available until after `$CA` has completed.** It is
    fetched after the bus is released, and only for commands whose form implies
    a reply (§10.2).
11. **The unit starts unmounted.** Until a START UNIT (or the automatic mount
    that the first READ after reset triggers, `$42C3`), TEST UNIT READY, REZERO
    and READ all return CHECK CONDITION with sense key 2.
12. **256-byte SCSI blocks, 24 to a video frame.** A read that crosses a frame
    boundary arrives as several DMA bursts.

Things the firmware gets wrong, which an emulator should reproduce if it is
meant to be faithful and flag if it is meant to be a reference:

- the byte-swapped READ (10) length, and the CDB byte 5 check that makes
  READ (10) reject most addresses (§6.5, §6.6);
- the stale CDB length for command groups 2, 3 and 4 (§5.2);
- the sense byte 0 value of `$80`/`$00` where SCSI expects `$70` (§7.3);
- WRITE accepted but silently ignored (§6);
- a serial timeout fabricating a success reply (§9.3);
- STOP UNIT being a no-op because the model number is hard-wired to 410
  (§6.7).

## Sources

Everything above was read out of `LVDOS#1` 6805.3 and `LVDOS#2` 6806.3 with
`tools/vp-lvdos.py`; the manual was not used as evidence for any claim.
Cross-checks that were run:

- Both revisions, 1.3 and 1.4, decode to **zero overlapping instructions** and
  no branch target outside the programmed part of the ROM. A wrong operand
  length anywhere would collide within a few instructions.
- The 43 procedure entry points found by the recursive trace match, one for one
  and in the same order, the 43 `call`-to-prologue signatures found by a linear
  scan.
- The accepted-opcode list, the group-to-length table and the dispatch chain
  are identical in both revisions.

Not covered here, and the obvious next steps:

- **Module S** (`6804.9`, MCS-51) owns the machine's external RS232 port and is
  the authority on the ASCII command language. §9.5 and §10.2 describe only the
  subset module W uses and validates.
- The LV-ROM sector format, the descrambler table in item 7224 and the sync
  pattern in item 7201 — module W consumes their output but does not describe
  them.
- The disc label beyond the eight fields in §11.3.
