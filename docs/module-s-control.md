# Module S — the control module

Module S is the VP415's supervisor. It owns both command ports, the remote
control, the front panel, the video-mixer control latch, the DIP switches, and
the link to the drive processor. Everything a host can ask the player to do
arrives here, and every answer leaves from here.

This document describes the module as a machine: its hardware, its multitasking
kernel, its eight tasks, its two serial ports and the handshake that decides
which of them is in charge, and — in detail — the DIP-switch input port and
every effect its bits have on the running firmware. The **command language** it
interprets is a separate document,
[`player-control-command-set.md`](player-control-command-set.md).

**The image.** `CONTROL` 6804.9 rev 1.8, `0x6728`, IC7202, a TMS27512 64 KB
EPROM of which `$0000`–`$D3FF` is programmed.

```sh
python3 tools/vp-mcs51.py \
    original-images/vp415-module-s-ic7202-control-6804.9-rev1.8-0x6728.bin \
    -o disasm
```

All `$xxxx` addresses below are in that image unless the text says otherwise.
Code addresses refer to
`disasm/vp415-module-s-ic7202-control-6804.9-rev1.8-0x6728.lst`; data addresses
are external RAM.

---

## Contents

1. [Hardware](#1-hardware)
2. [Reset and start-up](#2-reset-and-start-up)
3. [The kernel](#3-the-kernel)
4. [The eight tasks](#4-the-eight-tasks)
5. [The two command ports](#5-the-two-command-ports)
6. [The DIP switches — `$FC00` read](#6-the-dip-switches--fc00-read)
7. [The video-mixer latch — `$FC00` write](#7-the-video-mixer-latch--fc00-write)
8. [The 8041 slave protocol](#8-the-8041-slave-protocol)
9. [The S-bus](#9-the-s-bus)
10. [Timers](#10-timers)
11. [Traps and failure modes](#11-traps-and-failure-modes)
12. [Notes for an emulator](#12-notes-for-an-emulator)
13. [Sources and limits](#13-sources-and-limits)

---

## 1. Hardware

| Item | Part | Role |
| --- | --- | --- |
| IC7201 | 8031/8051 family, crystal 5101 at **11.059 MHz** | the processor; no internal ROM is used |
| IC7202 | TMS27512 | the `CONTROL` firmware, 64 KB program space |
| IC7203 | static RAM, 8 K fitted | external data memory, battery-backed |
| IC7204 | address latch | demultiplexes AD0–7 |
| IC7205 | 3-to-8 line decoder | chip selects |
| IC7207 | bidirectional buffer | the S-bus |
| IC7208 | input buffer | reads DIP switches DS1–DS8 |
| IC7209 | output latch | video-mixer controls VP0–2 |
| IC7211 | NEC D8041AHC UPI, crystal 5102 at 4 MHz | one serial channel and two RC-5 channels |
| IC7213 / IC7214 | line receiver / transmitter | RS232-C levels for the rear-panel socket |
| item 1002 | 2.4 V Ni-Cd cell | keeps IC7203 alive with the power off |

### 1.1 External data memory map

Everything below `$1000` is RAM. The four addresses in the `$F000`–`$FFFF`
block are peripherals.

| Address | Direction | Device |
| --- | --- | --- |
| `$0000`–`$0E33` | R/W | RAM actually used by this build (the chip is 8 K, `$0000`–`$1FFF`) |
| `$F000` | R/W | S-bus data register (IC7207) |
| `$F400` | R/W | 8041 **data** port (A9 = 0) |
| `$F600` | R/W | 8041 **command/status** port (A9 = 1) |
| `$FC00` | **R** | DIP switches DS1–DS8 (IC7208, enabled by RD1) |
| `$FC00` | **W** | video-mixer control latch (IC7209, strobed by WR1) |

`$FC00` is the same address in both directions but two different chips: reading
it never returns what was written.

### 1.2 Port pins

`P3.0`/`P3.1` are the UART; `P3.2`/`P3.3` are the two external interrupts.
Timer 1 runs in auto-reload mode with `C/T` = 0, and timer 0 in 16-bit mode
with `C/T` = 0, so the `T0` and `T1` pins are free and the firmware uses them
as ordinary I/O.

| Pin | Direction | Use | Evidence |
| --- | --- | --- | --- |
| `P1.0`, `P1.1` | out | driven low at reset, never touched again | `$05A5` |
| `P1.2` | out | follows DIP bit 5 inverted; almost certainly the `RC IR/EURO` selection (§6.4) | `$BF00`–`$BF0C`, `$D13E` |
| `P1.3` | in | S-bus ready | `$D018`, `$86E8`, `$CAF3` |
| `P1.4` | in | S-bus secondary status | `$CA13`, `$CB5F` |
| `P1.5` | out | pulsed high for five `nop`s on **every** scheduler entry — a watchdog retrigger | `$0044`–`$004B` |
| `P1.6` | out | 8041 reset, active low; held low ≈11 ms at start-up | `$D119`–`$D120` |
| `P1.7` | out | driven low at reset, never touched again | `$05A5` |
| `P3.2` (`/INT0`) | in | S-bus attention; the interrupt wakes task 2 | `$0650` |
| `P3.3` (`/INT1`) | in | 8041 **OBF** — low means the 8041 has a byte; the interrupt wakes task 3 | `$0658`, `$C477` |
| `P3.4` (`T0`) | in | external RS232 handshake in: high blocks transmission | `$CD9D` |
| `P3.5` (`T1`) | out | external RS232 handshake out: raised while a received character is being processed, lowered afterwards | `$CE0A`, `$CE85` |

## 2. Reset and start-up

`$0599`:

```
0599  SP = $30                       the stack lives at $30..$7D
059C  7Eh = $55, 7Fh = $AA           stack-overflow guard (§11)
05A2  P3 = $FF, P1 = $78
05A8  20h..2Bh = 0                   task flags and the message-pool bitmap
05CC  $00B0..$00BF = $FF             all message queues empty
05D9  2Dh = $FF                      all eight software timers disabled
05DC  TH0 = $F0, TL0 = $00, TMOD = $21
05E5  TCON.0 = 1 (IT0 edge), TCON.2 = 0 (IT1 level)
05EC  for t in 0..7:  2Ch = t; select the task's register bank; call its init
0639  2Ch = 8                        "idle"
063C  TCON.4 = 1 (timer 0 run), TCON.6 = 1 (timer 1 run)
0640  IE = ES | EX1 | ET0 | EX0 | EA
064A  loop { call $0030 }            the scheduler, forever
```

The eight init routines, in the order they run:

| Task | Init | Register bank |
| --- | --- | --- |
| 0 | `$CD57` | 3 |
| 1 | `$8FFB` (`ret`) | 3 |
| 2 | `$C550` | 2 |
| 3 | `$D0FF` | 1 |
| 4 | `$8000` | 1 |
| 5 | `$77B8` | 0 |
| 6 | `$8FFD` (`ret`) | 0 |
| 7 | `$2EF4` (`ret`) | 0 |

**Reset does not clear external RAM.** Only `$00B0`–`$00BF` and the internal
bit-flag bytes are wiped; every other RAM location keeps whatever the
battery-backed chip held. What matters is initialised by the task init
routines, but there is no RAM-validity signature and no bulk clear, so a
freshly powered emulator and a real player that has been running for a year do
not start from identical memory.

## 3. The kernel

Eight tasks, strictly prioritised, cooperatively scheduled, communicating by
fixed-size messages. It is small and completely regular, which makes it easy to
reimplement.

### 3.1 The scheduler

`$0030`. It is entered two ways:

- from the main loop, as `lcall $0030`;
- from an interrupt. Each ISR sets a flag, **pushes `$0030` on the stack** and
  executes `reti`, so the interrupt returns *into the scheduler* rather than
  into the interrupted code. The original return address is still underneath,
  and the scheduler's `ljmp $003A` / `$0395` tail eventually pops it.

```
0030  IE.7 = 0; push ACC, DPH, DPL, PSW
003A  if 7Eh != $55 or 7Fh != $AA -> hang forever      (§11)
0044  pulse P1.5 high for five nops                     watchdog
004D  for t in 0..7, in order:
          if flags[t].7 == 0: continue                  task not runnable
          if priority[2Ch] >= priority[t]: return       cannot preempt
          select the task's register bank
          if flags[t].2:  clear it; event[t] = 2        an interrupt happened
          elif flags[t].1: clear it; event[t] = 4       its timer expired
          elif flags[t].0: event[t] = 1                 a message is waiting
                           dequeue it into pointer[t]
                           if the queue is now empty, clear flags[t].0
          2Ch = t; IE.7 = 1; call the task body; IE.7 = 0
          if (flags[t] & $07) == 0: clear flags[t].7
          return
```

Priorities come from the table at `$03A0`, indexed by task number, with 8
meaning "idle":

| Task | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | idle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Priority | 4 | 4 | 3 | 2 | 2 | 1 | 1 | 1 | 0 |

A task may only preempt a task of strictly lower priority — which is exactly
why tasks sharing a priority also share a register bank (§2): they can never be
on the stack at the same time.

### 3.2 Internal RAM

| Address | Contents |
| --- | --- |
| `00h`–`1Fh` | register banks 0–3 |
| `20h`–`27h` | per-task flag bytes, one per task. Bit 0 = message queued, bit 1 = timer expired, bit 2 = interrupt, bit 7 = runnable |
| `28h`–`2Bh` | message-pool allocation bitmap, 32 bits |
| `2Ch` | the task currently running (8 = idle) |
| `2Dh` | timer-disabled bits, one per task |
| `2Fh` | accumulator save inside the ISRs |
| `30h`–`7Dh` | stack |
| `7Eh`, `7Fh` | `$55`, `$AA` — the stack-overflow guard |

### 3.3 External RAM used by the kernel

| Address | Contents |
| --- | --- |
| `$0000`–`$007F` | eight message queues of 16 entries; task *t* uses `$0000 + 16t`. Each entry is a message-slot number |
| `$0080`–`$008F` | eight 16-bit pointers to each task's *current* message; task *t* uses `$0080 + 2t` |
| `$0090`–`$0097` | each task's current event code (1, 2 or 4 — see §3.1) |
| `$0098`–`$009F` | each task's timer reload value, in ticks |
| `$00A0`–`$00A7` | each task's timer counter |
| `$00B0`–`$00B7` | queue **write** indices, modulo 16 |
| `$00B8`–`$00BF` | queue **read** indices, modulo 16 |
| `$0100`–`$02FF` | the message pool: 32 slots of 16 bytes, slot *n* at `$0100 + 16n` |

### 3.4 Messages

A message is 16 bytes:

| Byte | Meaning |
| --- | --- |
| 0 | destination task |
| 1 | source task |
| 2 | payload length, where the receiver cares |
| 3… | payload; byte 3 is conventionally the opcode |

The primitives:

| Routine | What it does |
| --- | --- |
| `$0853` (also entered at `$0850`–`$0852`) | allocate a slot from the bitmap in `28h`–`2Bh`, store its address in `$0080 + 2·2Ch`. **There is no failure path**: if all 32 slots are busy, `$08BE` falls through and slot 32 is "allocated", which is `$0300` — outside the pool |
| `$77F4` | load `DPTR` from the 16-bit pointer at `DPTR` — used as `mov DPTR,#$0086` / `lcall $77F4` to get at the current message |
| `$097E` (entered at `$097B`–`$097D`) | send: read byte 0 for the destination, append the slot number to that task's queue, set its flags bit 0 and bit 7 |
| `$0900` (entered at `$08FC`–`$08FF`) | free the current message, clearing its bit in the bitmap |
| `$0786` (entered at `$0783`–`$0785`) | set the running task's timer: `A` = ticks, `B` = 0 to enable, `B` = `$FF` to disable |
| `$0759`/`$0771` (entered at `$0756…`/`$076E…`) | disable / enable the interrupt whose `IE` bit number is in `A` |

### 3.5 Timer 0 and the tick

Timer 0 is reloaded with `$F000` at every interrupt and so overflows every 4096
machine cycles. At 11.0592 MHz that is

> **1 tick = 4096 × 12 / 11 059 200 s = 4.444 ms**

The ISR at `$0675` walks all eight tasks: for each whose bit in `2Dh` is clear
it decrements `$00A0 + t`, and on reaching zero reloads from `$0098 + t`, sets
that task's flags bit 1 and bit 7. Software timers are therefore **periodic**,
not one-shot; a task that wants a one-shot disables its own timer when it
fires.

### 3.6 Interrupt vectors

| Vector | Address | Effect |
| --- | --- | --- |
| reset | `$0599` | §2 |
| external 0 (`P3.2`, S-bus) | `$0650` | set flags[2].2 and .7, clear `IE.0`, enter the scheduler |
| external 1 (`P3.3`, 8041 OBF) | `$0658` | set flags[3].2 and .7, clear `IE.2`, enter the scheduler |
| timer 0 | `$0675` | §3.5 |
| serial | `$0660` | set flags[0].2 and .7, clear `IE.4`, enter the scheduler |

Each of the three non-timer interrupts **disables itself** and relies on the
woken task to re-enable it — `$0771` with `A` = 0, 2 or 4 respectively. This is
level-sensitive handshaking dressed as an interrupt: the source keeps its line
asserted until the task has drained it.

## 4. The eight tasks

| Task | Body | Role |
| --- | --- | --- |
| 0 | `$CDE0` | the **external RS232 port**: the 8051 UART, its two ring buffers, and the transmission delay |
| 1 | `$8FFC` | unused — a bare `ret` |
| 2 | `$C6E2` | the **drive interface**: receives S-bus status and runs the play/search state machines |
| 3 | `$D193` | the **8041**: the internal command port, RC-5 reception, the line assemblers, the reply transmitter, the DIP-switch poll and the video-mixer latch |
| 4 | `$869F` | the **user interface**: RC-5 commands and front-panel handling |
| 5 | `$77C9` | the **F-code interpreter** — see [`player-control-command-set.md`](player-control-command-set.md) |
| 6 | `$8FFE` | unused — a bare `ret` |
| 7 | `$387B` | the **replay / auto-start sequencer** |

Each body switches on its event code (`$0090 + t`):

| Task | event 1 (message) | event 2 (interrupt) | event 4 (timer) |
| --- | --- | --- | --- |
| 0 | `$CDEC` | `$CE05` | `$CE8B` |
| 2 | `$ADA4` | `$6FAB` | `$C4FB` |
| 3 | `$8D7F` | `$C477` | `$BEB2` |
| 4 | `$8645` | — | `$85BD` |
| 5 | `$5A7A` | — | — |
| 7 | `$387B` inline | — | inline |

Task 3's message opcodes are the ones the F-code interpreter uses to answer a
host, and they are tabulated in
[`player-control-command-set.md`](player-control-command-set.md) §3. The table
itself is at `$8E6B`, covering opcodes `$3D`–`$63`; anything outside that range
is dropped by the bounds check at `$8DD5`.

Task 4's message handler dispatches on payload byte 3 with three bands
(`$867B`): `$04` and `$24` are RC-5 codes, `$46`–`$4C` and `$7F`–`$FF` are
internal requests, and **everything else is silently discarded** — which is why
the `$` F-code's task-4 message goes nowhere.

## 5. The two command ports

Both ports carry the same F-code language and both are always *listening*. What
differs is which one is **enabled**, and that is decided by a handshake, not by
a switch.

| | Internal port | External port |
| --- | --- | --- |
| Hardware | IC7211 (8041) at `$F400`/`$F600` | the 8051 UART, `SCON`/`SBUF` |
| Owned by | task 3 | task 0 |
| Levels | 5 V logic, half duplex, to the CPU board (module W) | RS232-C via IC7213/IC7214, rear-panel socket |
| Baud rate | fixed by the 8041's own configuration (`$81`, `$37` at `$D12A`) | **DIP-selectable**, §6.2 |
| Also carries | RC-5 codes in, RC-5 codes out | — |
| Line buffer | `$0DD3`, index `$0DBE` | `$0BC3`, index `$0DBF` |
| Control byte | `$0DC7` | `$0DC8` |
| Filled by | `$C477` | `$8B17`, from the ring at `$09C1` |
| Line completed by | `$C361` | `$8BE3` |

Earlier drafts of the command-set document called these "port A" and "port B";
those are not names from the manual, and internal/external is what the hardware
actually is.

### 5.1 The control bytes

`$0DC7` and `$0DC8` have the same layout:

| Bit | Meaning |
| --- | --- |
| 7 | this port is enabled: it may deliver commands and it receives replies |
| 5–4 | mode. `10` = F-code mode; `01` = the alternative mode claimed by `H` |
| 3–0 | never written in this build; the tests for `& $03` at `$8967` and `$C2C0` always pass |

**At the end of start-up `$0DC7` = `$00` and `$0DC8` = `$A0`** (`$D140`–`$D14A`).
So a player that has just been switched on answers the **external RS232 socket**
and ignores completed lines arriving from module W.

### 5.2 The claim handshake

After **every** character received on either port, before any enable test, the
firmware looks at the tail of that port's line buffer (`$C2BC` for the internal
port, `$8963` for the external one):

| Tail of the buffer | Effect | Reply |
| --- | --- | --- |
| `SP` `SP` | none | `A` |
| `SP` `SP` `F` | claim this port in F-code mode: set its control byte to `$A0`, **clear bit 7 of the other port's** control byte, reset the line buffer | `A` |
| `SP` `SP` `H` | external port only: set `$0DC8` = `$90` (mode `01`) and clear `$0DC7` bit 7 | `A` |
| `SP` `SP` `<anything else>` | reset the line buffer | `N` |

The two ports are therefore **mutually exclusive**: claiming one always disables
the other. Replies are emitted by `$8A32`, which writes to the internal port if
`$0DC7` bit 7 is set and then to the external port if `$0DC8` bit 7 is set — in
practice exactly one of them.

This is the other half of a mechanism already visible from module W's side.
Module W's `PROC_0060` sends `SP`, `SP`, reads a byte, sends `F`, reads a byte,
and does so at start-up and after every serial timeout
([`module-w-command-interface.md`](module-w-command-interface.md) §9.4). It is
not merely flushing a half-typed argument: it is **taking ownership of the
player**, and while an AIV machine is running the rear RS232 socket is deaf.
A host on that socket can take ownership back by sending the same three
characters.

The `A`/`N` answers are single characters sent with no `CR`: task-3 opcodes
`$47`/`$49` for the internal port (`$88F2`, `$892C`) and `$48`/`$4A` for the
external one (`$88C9`, `$8903`).

### 5.3 Assembling a line

Internal port, `$C477` → `$C35F` → `$C2BC` → `$C361`:

```
C477  if P3.3 is high there is nothing to read -> re-enable IE.2 and return
C47B  read the tag byte from $F400
C487    tag & $30 == $10 -> an RC-5 code: read two more bytes ($0DE0, $0DE1)
C4B2    tag & $30 == $20 -> one character: read it into $0DD3[$0DBE]
C4D3      a CR at index 0 is dropped rather than stored
C4EC      otherwise $0DBE++
C4F2  run the claim detector, then the line-completion test
C40C  if the buffer reached 12 characters without a CR, discard the whole line
C361  require $0DC7 bit 7 set and bit 5 set (F-code mode)
C38C  require the last character to be CR; strip it
C395  build a message: msg[0]=5, msg[1]=3, msg[2]=length, msg[3..]=characters
C401  reset the index and send it to task 5
```

External port, `$8B17`: the UART ISR appends bytes to a 255-entry ring at
`$09C1` (`$CE0C`) and task 3 drains it. While `$0DBF` < 12 characters go into
the line buffer; beyond that they spill into a second 255-byte ring at `$0BE3`.
The completion test at `$8BE3` mirrors `$C361`. An over-long line is not
discarded here: `$8C92` forwards a message whose length field is the real length
but whose payload is only the first character followed by `CR`, which the
dispatcher then rejects on its length check.

Both ports set **`msg[1] = 3`**, so task 5 — the interpreter — cannot tell which
port a command came from.

### 5.4 The external port in detail

Initialised at `$CD57`:

```
CD5C  SCON = $70          mode 1 (8-bit UART), SM2 = 1, REN = 1
CD5F  TCON: TR1 = 1, IE1/IT1 cleared
CD6B  TMOD: timer 1 into mode 2 (8-bit auto-reload), C/T = 0
CD77  TH1 = $FD           9600 baud, until the first DIP poll overrides it
CD7A  P3.5 = 0
CD7C  $09BF = $09C0 = 0   the receive ring is empty
CD86  $0AC0..$0AC2 = 0    the transmit ring is empty
```

`PCON` is never written, so `SMOD` stays 0 and the baud rate is
`fosc / (32 × 12 × (256 − TH1))`.

Transmit, `$CD9D`:

```
CD9D  if P3.4 is high, ask for a 1-tick timer and give up for now
CDA6  if head == tail the ring is empty -> disable the timer and return
CDB5  SBUF = $0AC3[$0AC2]; $0AC2++ (wrapping at $FF)
```

Receive, `$CE05`: on `RI`, raise `P3.5`, take `SBUF`, clear `RI`, and if the ring
was empty send task 3 the opcode `$3E` to wake it; store the byte, advance the
write index. On `TI`, clear it and — unless the transmission delay is on — send
the next character immediately. `P3.5` is lowered again at `$CE85` after the
interrupt has been serviced and `IE.4` re-enabled.

**The transmission delay** (`$09BE`, set by the `)` F-code) makes task 0 request
a 4-tick timer between characters instead of transmitting back to back:

> 4 ticks × 4.444 ms = **17.8 ms per character**

## 6. The DIP switches — `$FC00` read

Reading `$FC00` returns the eight switch inputs buffered by IC7208. Four bits
are used.

| Bit | Switch | Used for | Read at |
| --- | --- | --- | --- |
| 7 | DS8 | not read anywhere | — |
| 6 | DS7 | the rear-panel **`REPLAY` on/off switch** (§6.3) | 18 sites, §6.3 |
| 5 | DS6 | drives `P1.2`, inverted (§6.4) | `$BF00` |
| 4 | DS5 | not read anywhere | — |
| 3–2 | DS4, DS3 | **baud rate** for the external RS232 port (§6.2) | `$BEBE`, `$9344`, `$9979` |
| 1–0 | DS2, DS1 | not read anywhere | — |

The operating instructions describe two of these as separate rear-panel
controls: item 7 is a `BAUD RATE` DIP block next to the RS232-C socket, and
item 3 is a `REPLAY` on/off switch. Electrically they all land on the same
input port. Whether a closed switch reads as 0 or 1 cannot be determined from
the ROM; the tables below give the **port value**, which is what an emulator
has to reproduce.

### 6.1 When the port is read

Task 3's timer handler, `$BEB2`, runs every 32 ticks:

> 32 × 4.444 ms = **≈142 ms**

```
BEB2  read $FC00; if it equals the shadow at $0DC1, skip to $BF0E
BEBE  store the new value; extract bits 3-2 and jump through $BF92
BEE6  TH1 = $FD / $FA / $F4 / $E8
BEF8  re-read $FC00 into the shadow
BF00  if bit 5 is clear, P1.2 = 1, else P1.2 = 0
```

Task 3's init deliberately stores the **complement** of the switches into the
shadow (`$D155`: read, `cpl A`, store), so the very first poll always sees a
change and always applies the baud rate.

**The switches are live.** They are not sampled once at reset: moving one takes
effect within about 142 ms, without a power cycle. An emulator that lets the
user change the baud rate at run time is behaving correctly.

Bit 6 is *not* read by this poll — every one of its consumers reads `$FC00`
directly at the moment it needs it.

### 6.2 Bits 3–2 — baud rate

`(value >> 2) & 3` indexes the two-byte jump table at `$BF92`:

| Bits 3–2 | `TH1` | Divisor | Baud at 11.0592 MHz | Handler |
| --- | --- | --- | --- | --- |
| `00` | `$FD` | 3 | **9600** | `$BEE6` |
| `01` | `$FA` | 6 | **4800** | `$BEEB` |
| `10` | `$F4` | 12 | **2400** | `$BEF0` |
| `11` | `$E8` | 24 | **1200** | `$BEF5` |

The word format is fixed by `SCON = $70`: **8 data bits, no parity, one stop
bit**, and it is not configurable. `SM2` is set, so a character with a framing
error at the stop bit does not raise `RI` and is silently lost.

Two other places read the same two bits for display purposes: `$9344` copies
them to `$0DB8`, and `$9979` multiplies the index by four (`$9983`) to select a
four-character label — the player can show its own baud rate.

### 6.3 Bit 6 — the `REPLAY` switch

Eighteen sites read bit 6, and **every single one of them pairs it with
`$0CFB`**, the flag the `$` F-code sets. The rule throughout is

> the replay function is active when `$0CFB == 1` **and** `$FC00` bit 6 reads 0

so the rear-panel switch and the `$1` command are in series: either one turns
the feature off. Addresses below are the `mov DPTR,#$FC00` that begins each
test.

| Site | In | What bit 6 gates |
| --- | --- | --- |
| `$4774` | the `?P` reply builder | whether wire byte 3 bit 2, "replay function active", is set |
| `$3924` | task 7 | advancing the auto-start sequence; otherwise the state is forced to `$10` |
| `$3969`, `$3994`, `$3A8E`, `$3B2B`, `$3FC5` | task 7 | further steps of the same sequence |
| `$60CC` | `$60C6`, in the drive-state code | sets `$06F1` and issues a task-4 message when replay is *not* active |
| `$6C81`, `$6EBA`, `$6F0D` | task 2's interrupt path | replay-specific drive commands |
| `$820E` | `$81A3` | starts the 54-tick (≈240 ms) timer for the replay sequence |
| `$8343` | `$81A3`'s continuation | selects the replay branch of the front-panel state machine |
| `$91D2`, `$944B` | S-bus status processing | replay-specific reactions to disc status |
| `$B38F` | S-bus status processing | replay-specific branch |
| `$C806`, `$C830` | `$C800`, `$C82A` | the *non*-replay path: task-4 messages `$15`/`$16` are sent only when replay is inactive |

The one externally visible effect is the `?P` status bit. Everything else is
internal sequencing, and it is why the front-panel `REPLAY` indicator and the
`?P` bit agree.

Adding these up accounts for every reference to `$FC00` in the image: 6 writes,
5 whole-byte reads (the poll and its shadow), 2 baud-rate reads and these 18.

### 6.4 Bit 5 — `P1.2`

```
BF00  A = $FC00
BF04  if (A & $20) == 0:  P1.2 = 1
BF0C  else:               P1.2 = 0
```

`P1.2` is an output that goes off-module; the firmware never reads it back and
does nothing else with the bit. It is also set once at `$D13E`, immediately
after the 8041 has been reset and configured, which puts it in the same
initialisation sequence as the RC-5 hardware. Given that IC7211 provides *two*
RC-5 channels and the rear panel carries an `RC IR/EURO` switch — "remote
control reception method selection" — the natural reading is that **`P1.2`
selects which RC-5 input is routed to the 8041**. The ROM alone cannot confirm
that; what it does establish is the exact relationship between the switch bit
and the pin.

### 6.5 What the DIP switches do *not* do

Nothing selects a SCSI address here — those switches are on module W. Nothing
selects parity, word length or stop bits. Nothing selects a player address for
a multi-drop bus: the command language has no addressing. Bits 0, 1, 4 and 7 of
`$FC00` are never read by this firmware revision.

## 7. The video-mixer latch — `$FC00` write

Writes go to IC7209, whose outputs VP0–2 drive the mixing board (module Y).
The firmware keeps a shadow at **`$0DC0`** and always writes the whole byte.

| Bit | Meaning | Written by |
| --- | --- | --- |
| 7 | teletext from disc enabled | the `_` F-code, `$5A49`; initialised to 1 |
| 6–4 | never written | — |
| 3 | cleared when S-bus status `$0336` bit 7 is set, otherwise set | `$95AA`, automatic |
| 2–0 | the video overlay mode selected by `VP1`–`VP5` | `$8D28` |

The latch is initialised to **`$88`** — teletext on, bit 3 on, overlay mode 0 —
in both `$8800` (the serial re-initialisation reached by the `:` and `'`
F-codes) and `$D102` (task 3 init).

The overlay encoding is not monotonic. `$8D28` masks the shadow with `$F8` and
then jumps through the table at `$8E5F`:

| Command | Bits 2–0 | Handler |
| --- | --- | --- |
| `VP1` | `000` | `$8D3C` |
| `VP2` | `001` | `$8D48` |
| `VP3` | `100` | `$8D54` |
| `VP4` | `011` | `$8D60` |
| `VP5` | `010` | `$8D6C` |

The `VPX` query undoes the same permutation when it builds its answer, so it
round-trips correctly.

## 8. The 8041 slave protocol

IC7211 is a true slave: it signals with **OBF** on `P3.3` (low = a byte is
waiting) and is addressed by A9 — `$F400` for data, `$F600` for
command/status.

### 8.1 Start-up

```
D119  P1.6 = 0            reset the 8041
D11B  delay 100 units     ≈11 ms   ($77D4, ≈0.11 ms per unit)
D120  P1.6 = 1
D122  delay 10 units      ≈1.1 ms
D127  wait for the 8041   ($888C)
D12A  $F600 = $81         configure
D133  $F400 = $37         parameter
```

Module W performs the same sequence on its own 8041 with the parameter `$27`
instead of `$37`
([`module-w-command-interface.md`](module-w-command-interface.md) §9.1).

`$888C` is the "settle" routine used before every command: if `P3.3` is low
there is unread input, so it calls `$C477` to consume it first; then it reads
`$F600` into `$0DD1`.

### 8.2 Commands module S writes to `$F600`

| Byte | Meaning |
| --- | --- |
| `$81` | configure, followed by one parameter byte on `$F400` |
| `$93` | transmit an RC-5 code, followed by three bytes on `$F400` (`$BE84`) |
| `$A1` | transmit one byte, followed by that byte on `$F400` |
| `$A0 \| n` | transmit *n* bytes, followed by *n* bytes on `$F400` — used for replies shorter than three characters (`$8A84`) |

Replies of three characters or more are sent one `$A1`-prefixed byte at a time
(`$8A60`); shorter ones use the burst form. Module W's receiver copes with both
because it treats a leading `$A1` as a prefix and masks the byte that follows to
seven bits.

### 8.3 Tagged input

Reading `$F400` yields a tag byte whose bits 5–4 say what follows:

| Tag & `$30` | Meaning |
| --- | --- |
| `$10` | an RC-5 code — two more bytes follow |
| `$20` | a received character — one more byte follows |
| anything else | ignored |

### 8.4 RC-5

`$C41B` accepts a code only if its first byte is `$04` or `$24` — RC-5 system
address 4, with and without the toggle bit. Anything else is dropped. An
accepted code is forwarded to task 4 as a message with `msg[3]` = the address
byte and `msg[4]` = the command byte, and `$0DD2` is set to 1.

RC-5 **output** exists in the ROM at `$BE79`–`$BEB1`: settle, `$93` to `$F600`,
then three bytes from `$0E27`–`$0E29` to `$F400`. It is used for the `H`
pass-through, not by the `#` F-code — task 3's opcode `$50`, which `#` builds,
is a bare `ret` at `$8E2E`.

## 9. The S-bus

`$F000` is a byte-wide port to the rest of the player. Messages are **three
bytes**. Two handshake inputs gate it: `P1.3` (ready) and `P3.2` (attention,
which is also `/INT0` and so wakes task 2). Every wait is bounded by a spin
counter that gives up after 20 iterations, so a stalled peer cannot hang the
firmware.

- **Receive** — `$CA00`, called from task 2's interrupt handler `$6FAB`. Three
  bytes are read from `$F000` into `$0332`–`$0334`, then processed by `$913A`,
  `$B2F3` and `$C08D`.
- **Transmit** — `$D000`, called from `$6FE9`. Each transaction writes `$04`
  and then two bytes taken from a 400-entry FIFO at `$0394`–`$06B3`, with the
  write pointer at `$06B5` and the read pointer at `$06B7`, both wrapping at
  offset `$0320`.
- **The register-write queue** — `$0344`, `$0345`, `$0346`, three parallel
  20-entry arrays with the count at `$0380`. These are the `(register, mask,
  value)` triples the F-code handlers build for the drive processor.

The status bytes the drive processor returns land at `$0332`–`$0340`, and
`$0CE5`–`$0CFD` is the derived state the `?P` builder reads.

## 10. Timers

`$0786` always acts on **the task that is running**, so the owner of a timer is
the caller's task, not a property of the call site. Every call site in the
image — found by raw byte search, not only in the traced code:

| Site | Ticks | Period | Owner | Purpose |
| --- | --- | --- | --- | --- |
| `$CDDC` | 1 | 4.4 ms | task 0 | retry after `P3.4` blocked a transmission |
| `$CDFC`, `$CE98` | 4 | 17.8 ms | task 0 | the `)` transmission delay |
| `$CDB0`, `$CEA3` | — | disable | task 0 | the transmit ring has emptied |
| `$D116` | 32 | **142 ms** | task 3 (init) | **the DIP-switch poll**, and the rest of `$BEB2` |
| `$AD9A`, `$B12F` | 250 | 1.11 s | task 2 | drive-response watchdogs |
| `$AE03`, `$C510`, `$92A1` | — | disable | task 2 | in the message, timer and S-bus-status handlers |
| `$85D8` | — | disable | task 4 | inside task 4's own timer handler |
| `$822A` | 54 | 240 ms | see below | the replay path, guarded by `$0CFB` and DIP bit 6 |
| `$1597` | 100 | 444 ms | see below | the sequencer in `$0B00`–`$2900` |
| `$13C5`, `$27D2` | — | disable | see below | the same sequencer |

The last four sit in routines that more than one task calls — `$81A3`, which
contains `$822A`, is entered from task 4's own code by `ajmp` and from a dozen
places in the F-code handlers by `lcall` — so which task's timer they set
depends on the path taken. Tasks 1, 5 and 6 have no call site that could ever
enable a timer for them.

## 11. Traps and failure modes

| Trap | Where | Behaviour |
| --- | --- | --- |
| Stack overflow | `$003A` | the scheduler checks `7Eh`/`7Fh` for `$55`/`$AA` on every entry and **spins forever** if either has been overwritten. The stack is 78 bytes |
| S-bus fatal status | `$9143` | if `$033B` bit 7 is set, `clr IE.7; sjmp $` — interrupts off, hang |
| Message pool exhausted | `$08BE` | no failure path. With all 32 slots busy the allocator returns index 32, whose address is `$0300` — past the end of the pool, corrupting whatever lives there |
| Line too long, internal port | `$C40C` | the whole line is discarded once it reaches 12 characters without a `CR` |
| Line too long, external port | `$8C92` | a malformed short message is forwarded instead |
| Serial framing error | `SCON` `SM2` = 1 | the character never raises `RI` and is lost with no indication |
| 8041 not responding | `$C477`, `$D000` | bounded spin counters, then give up silently |

The watchdog retrigger on `P1.5` happens on **scheduler entry**, not inside the
task, so a task that loops forever will still be retriggering it as long as
interrupts keep arriving — but the two hang traps above disable interrupts or
predate the pulse, so they do stop it.

## 12. Notes for an emulator

1. **The clock is 11.0592 MHz.** One machine cycle is 12 crystal cycles, so
   921 600 cycles per second and one kernel tick every 4096 of them.
2. **`$FC00` is two registers.** Reads must return the switch value; writes must
   go to a separate latch that reads never see.
3. **Poll the switches every 142 ms**, not once at reset, and apply the baud
   rate on change. Task 3's init pre-loads the complement of the switches into
   `$0DC1` so that the first poll always fires.
4. **Start with the external port owning the interface.** `$0DC7` = `$00`,
   `$0DC8` = `$A0`. Until something sends `SP SP F` on the internal port, lines
   arriving from module W are assembled and then dropped.
5. **Implement the claim handshake before the enable test.** It runs on every
   character on both ports regardless of which port is enabled, and it answers
   `A` or `N` with no `CR`.
6. **Claiming is exclusive.** Enabling one port clears the other's enable bit,
   so replies never appear on both.
7. **Both ports report themselves as task 3** in `msg[1]`, so nothing downstream
   distinguishes them; a single interpreter instance is correct.
8. **The line buffer is 12 characters** on both ports, and the two ports handle
   overflow differently (§5.3).
9. **`SM2` is set on the UART.** A byte with a bad stop bit is dropped silently
   rather than producing a framing error.
10. **`P3.4` gates transmission** on the external port and `P3.5` is asserted
    while a received character is being handled. An emulator with no flow
    control should hold `P3.4` low.
11. **External RAM survives a reset.** Only `$00B0`–`$00BF` and the internal
    flag bytes are cleared. If you want to match a warm player, do not zero RAM
    on reset.
12. **The 8041 is a separate processor.** Its own ROM is
    `vp415-module-s-w-8041-slave-0xFC62.bin`; the framing in §8 is all module S
    knows about it.
13. **Replay is an AND**, not an OR: the `$` command and the rear-panel switch
    both have to agree before the feature — and the `?P` bit — turns on.

## 13. Sources and limits

Everything above was read out of the 6804.9 image with `tools/vp-mcs51.py`,
which recursively traces from the reset and interrupt vectors and resolves
`jmp @A+DPTR` tables until nothing new appears: 21 675 instructions, 42 592 of
53 385 programmed bytes (79.8 %), 66 tables resolved, none unresolved. The
undecoded remainder was checked by raw byte search for every `$F000`, `$F400`,
`$F600` and `$FC00` reference and every call to the timer service, and the
handful of sites the tracer had not reached were disassembled by hand; they are
included above.

Cross-checked against the VP415 service documentation transcribed at
[domesday86/vp415-service-guide](https://github.com/domesday86/vp415-service-guide)
for the crystal frequency, the IC complement, the chip-select arrangement, and
the rear-panel controls. Where the ROM and the documentation are both specific
they agree; the 11.059 MHz crystal in particular is confirmed independently by
the four `TH1` values producing exactly 9600/4800/2400/1200 baud.

**Not established here.** What `P1.2` is physically connected to (§6.4) is an
inference from the rear-panel control list, not from the ROM. The meaning of
individual S-bus registers needs module R's `DRIVE` ROM, which has not been
disassembled. The 8041 firmware itself has not been examined. Tasks 2, 4 and 7
are described by role and by their entry points; their internal state machines —
disc handling, front-panel behaviour and the replay sequence — are mapped only
as far as the DIP switch and the command set reach into them.
