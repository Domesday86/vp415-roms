# The LV-DOS p-code machine

Module W's CPU does **not** run LV-DOS as native Z80 code. `LVDOS#1` holds a
byte-code interpreter and a library of native hardware primitives; `LVDOS#2`
holds the interpreter's opcode dispatch table, a floating-point library and the
interrupt handler. The LV-DOS application itself — everything that implements
the SCSI command set — is byte code, scattered through both EPROMs.

A linear Z80 disassembly of these images is therefore mostly nonsense, which is
why [`docs/tooling.md`](tooling.md) reports that "call and jump targets are
concentrated in 0x0000–0x2FFF with almost none above 0x4000". They are not Z80
call targets at all.

This document describes the machine well enough to read the listings that
`tools/vp-lvdos.py` produces. The command interface itself is documented in
[`module-w-command-interface.md`](module-w-command-interface.md).

Addresses are for **LV-DOS 1.4** (`6805.3` + `6806.3`) with `LVDOS#1` at
`$0000` and `LVDOS#2` at `$4000`. Revision 1.3 differs only in placement; see
the mapping table at the end.

---

## 1. Proof that the 0x4000 base is right

`docs/tooling.md` records the `LVDOS#2` load address as an inference. It is now
settled:

- `$0038`, the Z80 interrupt-mode-1 vector, holds `C3 0A 4F` = `jp $4F0A`, and
  `$4F0A` — inside the programmed part of `LVDOS#2` under a `$4000` base — is a
  textbook maskable-interrupt handler (`ex af,af'` / `exx` / read the interrupt
  source register / `ei` / `reti`).
- The reset path at `$0031` jumps to `$274B`, which reads its stack and heap
  parameters from `$4F54`–`$4F5B`, the last eight programmed bytes of
  `LVDOS#2`, and gets sensible values (`$A000`, 1000, `$A3E8`, 1000).
- The interpreter at `$2C28` uses `$4CD4` as its dispatch-table base and every
  one of the 160 entries lands on real code.

Any other base breaks all three.

---

## 2. Reset and start-up

| Address | What happens |
| --- | --- |
| `$0000` | Clear RAM `$A000`–`$FEFF`, then `jp $0031` |
| `$0010` | The native-call trampoline (see §5) |
| `$0031` | `jp $274B` — the p-code runtime start-up |
| `$0038` | `jp $4F0A` — the IM 1 interrupt handler |
| `$274B` | Set up the p-code stack, heap and frame pointers from `$4F54`, then `ld hl,$4287` / `jp $2C20` — start interpreting at `$4287` |

The configuration block at `$4F54` is four little-endian words:

| Address | Value | Meaning |
| --- | --- | --- |
| `$4F54` | `$A000` | base of the p-code stack; initial frame and heap pointer |
| `$4F56` | `1000` | stack size; SP is set to `$A000 + 1000 = $A3E8` |
| `$4F58` | `$A3E8` | address of the free-list head |
| `$4F5A` | `1000` | heap size; the first free block gets length `1000 − 4 = 996` |

## 3. RAM map

| Range | Contents |
| --- | --- |
| `$8000`–`$9FFF` | Data-grabber buffer RAM. Three 2048-byte frame buffers at `$8004`, `$8934`, `$9264` (2048 × 3 = 6144 = 24 × 256 bytes = one video frame's payload). **Not** cleared at reset |
| `$A000`–`$A3E7` | p-code evaluation stack (grows down from `$A3E8`) |
| `$A3E8`–`$A7CB` | p-code heap (996-byte free list) |
| `$A7D0`–`$B7FF` | statically allocated globals |
| `$B800`–`$FFFF` | Three cached copies of the frame buffers, selected by primitive 39: bank 1 `$B800`/`$C000`/`$C800`, bank 2 `$D000`/`$D800`/`$E000`, bank 3 `$E800`/`$F000`/`$F800` |

## 4. The interpreter

```
2C1C: push hl              ; "push the result and fetch the next opcode"
2C1D: ld hl,($AA2F)        ; "fetch the next opcode"
2C20: ld c,(hl)            ; C = opcode
      ld b,$00
      inc hl
      ld ($AA2F),hl        ; advance the p-code IP
      ex de,hl             ; DE = IP for the handler
      ld hl,$4CD4
      add hl,bc
      add hl,bc            ; + 2 * opcode
      ld a,(hl) / inc hl / ld h,(hl) / ld l,a
      jp (hl)
```

- The Z80 **SP is the p-code operand stack**. Values are 16-bit; floats are four
  bytes (two pushes).
- `DE` holds the p-code instruction pointer inside a handler; `$AA2F` is its
  memory home.
- Handlers end with `jp $2C20` (IP already in `HL`), `jp $2C1D` (reload IP), or
  `jp $2C1C` (push `HL` first).

### Runtime state variables

| Address | Meaning |
| --- | --- |
| `$AA2A` | last runtime trap code (written by the halt path) |
| `$AA2B` | frame pointer (`fp`) — base of the current procedure's parameters |
| `$AA2D` | heap/argument-build pointer |
| `$AA2F` | p-code instruction pointer |
| `$AA31` | display / static-link pointer |
| `$AA33` | stack limit |
| `$AA35` | free-list head |
| `$AA39` | return-kind flag set by the `RET` opcodes |

### Comparison sense

All comparison opcodes pop two words; call the first-pushed operand *A* and the
second *B*. The kernel at `$2DDD` computes `A − B`, so `carry` means `A < B`.
`CMP.GE` (`$1B`) is therefore true when `A >= B`, and so on. The floating-point
kernel at `$4C50` uses the same convention.

`JZ` (`$2C`) branches when the popped byte is **zero**, i.e. it is a
"jump if false".

## 5. Procedures

A compiled procedure begins with `CD 55 28` — `call $2855`, the shared prologue —
followed by a header:

| Offset from the procedure address | Size | Meaning |
| --- | --- | --- |
| +0 | 3 | `CD 55 28` |
| +3 | 1 | flags (skipped by the prologue) |
| +4 | 2 | frame size, signed; equals −(size of the parameter block) |
| +6 | var | var-int: extra local storage to reserve on the heap |
| +? | 2 | skipped |
| +? | … | the p-code body |

The prologue at `$2855` pops the header address that `call` pushed, allocates the
frame and the locals, saves the old display pointer and jumps to `$2C1D`.

Calls use opcode `$64` (`CALL lvl, addr`). The sequence pushes the return IP,
then `$28C7` (the return glue), then `jp (hl)` to the target — so a call target
may equally well be **native Z80** that simply `ret`s to `$28C7`. Exactly two
such native targets exist: `$0010` (the hardware gateway) and `$4ED2` (hardware
initialisation).

Arguments are built on the heap before the call: opcode `$17` (`ARGSPC`)
reserves two bytes for the return value, then each argument is appended with
`$13` (`ARGW`, one word) or `$2D`/`$1C` (`ARGW2`, `ARG3`). Inside the callee,
parameter 1 is at `fp+0`, parameter 2 at `fp+2`, and the return value is written
to `fp−2`.

Scanning `LVDOS#1`+`LVDOS#2` for `CD 55 28` finds 43 procedures in revision 1.4;
the tracer reaches 42 of them plus the entry point (`$1DD0` is dead code).

## 6. The native hardware gateway

Procedure `$0010` is native Z80:

```
0010: push af / push bc / push de
0013: ld de,($B7F2)       ; word argument
0017: ld a,($B7F0)        ; selector
001A: ld c,a
001B: ld a,($B7F1)        ; byte argument
001E: call $0FC9
0021: ld ($B7F4),a        ; byte result
0024: ld a,d
0025: ld ($B7F5),a        ; high byte of the word result
0028: pop de / pop bc / pop af / ret
```

`$0FC9` multiplies the selector by four and jumps into a table of `jp` stubs at
`$0FDF`, 44 entries (selectors 0–43). This is the only path from LV-DOS to the
hardware.

The p-code wrapper `PROC_003C` marshals it:

```
0045: LDB  [fp+0]        -> STB.A  $B7F0     ; selector
004A: LDB.b fp+$02       -> STB.A  $B7F1     ; byte argument
004F: LDW.b fp+$04       -> STW.A  $B7F2     ; word argument
0054: CALL lvl 1, $0010
0058: LDB.A $B7F4        -> STW    [fp-2]    ; byte result
005F: RET.1
```

Every module carries its own copy of this wrapper (`$003C`, `$1DAC`, `$303D`,
`$385D`, `$4863`) and of the player-command wrapper (`$00D3`, `$3061`, `$3881`);
they are identical, so a call to any of them means the same thing.

## 7. Opcode set

Opcodes `$00`–`$7F` are the general-purpose machine; handlers live in
`$2791`–`$2F31`. Opcodes `$80`–`$94` are the floating-point library
(`$4AD8` jump table → `$4B17`–`$4CD3`). Opcodes `$96`–`$9F` are range checks
(`$4E14` jump table → `$4E2F`–`$4ED1`). `$14`, `$22`, `$7C`–`$7E` and `$95` are
unassigned and vector to `$0000` or `$FFFF` — i.e. they reset the CPU.

Operand notation below: `imm8`/`imm16` are literal bytes; `var` is the
variable-length integer decoded by `$2E29` (one byte if `< $80`, otherwise
`(a & $7F) << 8 | next`); `addr` is the effective-address descriptor decoded by
`$2E54` (see §8); `A`/`b`/`W` suffixes are the three short address forms.

| Op | Mnemonic | Operands | Handler | Effect |
| --- | --- | --- | --- | --- |
| `00`–`0F` | `PUSHC0`…`PUSHC15` | — | `$2A27` | push the opcode value as a constant |
| `10` | `DECW.JNZ` | addr, imm16 | `$2D47` | decrement a word variable; jump unless it wrapped past `$8000` |
| `11`,`12` | `DIV`, `DIV.r` | — | `$2CB3`,`$2CCB` | signed 16-bit divide (trap 4 on zero) |
| `13`,`2D` | `ARGW` | — | `$2939`,`$2948` | pop a word into the argument block |
| `15`,`38`,`42`,`1D`,`1A`,`36` | `SCMP.EQ/LT/NE/GT/GE/LE` | var | `$2DEB`… | compare two blocks of *n* bytes |
| `16`,`39`,`43`,`1E`,`1B`,`37` | `CMP.EQ/LT/NE/GT/GE/LE` | — | `$2D94`… | compare two words, push 0/1 |
| `17`,`18` | `ARGSPC` | — | `$27A1`,`$27AD` | reserve two bytes in the argument block |
| `19` | `PUSHPROC` | imm8 lvl, imm16 | `$2A76` | push a procedure value (frame + address) |
| `1C` | `ARG3` | — | `$2953` | append three bytes to the argument block |
| `1F`,`20` | `IDXC2`, `IDXC3` | imm16 / imm16+imm8 | `$29C8`,`$29D0` | add a constant to a computed address |
| `21` | `INCW.JNZ` | addr, imm16 | `$2D2F` | increment a word variable and loop |
| `23`,`24` | `IDX.SCALE`, `IDX.ADD` | var | `$296E`,`$298E` | array index scaling / offset |
| `25`,`27` | `IDX.DESC` | addr | `$299D` | index using a descriptor |
| `26`,`2A` | `BITADDR` | imm8 | `$29BD`,`$29B7` | bit-field address |
| `28` | `CASETAB` | lo8, hi8, (hi−lo+1)×imm16 | `$27BA` | jump table; index 0 doubles as the out-of-range target |
| `29` | `CASETABW` | lo16, hi16, table | `$27E4` | as above with 16-bit bounds |
| `2B` | `JMP` | imm16 | `$290D` | unconditional jump (target 0 → trap 5) |
| `2C` | `JZ` | imm16 | `$2911` | jump if the popped byte is zero |
| `2E`,`30`,`3A` | `LDB`,`LDW`,`LDF` | addr | `$2A3E`,`$2A48`,`$2AF7` | load byte / word / 4-byte float |
| `2F`,`31`,`3B` | `PUSHB`,`PUSHW`,`PUSHF` | imm8 / imm16 / 4 bytes | `$2A2C`,`$2A35`,`$2BAC` | push a literal |
| `32` | `LEA` | addr | `$2A52` | push the effective address |
| `33` | `LITBLK` | var *n*, *n* bytes | `$2A5A` | push the address of an inline literal block and skip it |
| `34` | `LDIND` | — | `$2A65` | load indirect |
| `35`,`54` | `BITGET`, `BITSET` | imm8, addr | `$2AAF`,`$2ACE` | packed bit-field access |
| `3C` | `MUL` | — | `$2CAB` | 16-bit multiply |
| `3D`,`3E` | `MOD`, `MOD.r` | — | `$2D68`,`$2D8A` | remainder (trap 6 on negative) |
| `3F`,`40` | `BLKMOV` | var | `$2BEF`,`$2BFD` | copy *n* bytes |
| `41`,`5E` | `NEG`, `ABS` | — | `$2D1E`,`$2D15` | |
| `44`,`49`,`4A` | `DROP` | — | `$27B5` | discard a word |
| `45`,`46`,`47`,`60` | `NOT`,`NOTB`,`OR`,`AND` | — | `$2C9C`… | logical |
| `48`,`4B`,`4D` | `RET.1`,`RET.FF`,`RET.0` | — | `$28A4`,`$28A9`,`$28AC` | procedure return; the value distinguishes function/procedure |
| `4C`,`57` | `DEC`, `INC` | — | `$2D2A`,`$2D25` | |
| `4E`,`4F`,`5F` | `SUB`,`SUB.r`,`ADD` | — | `$2D01`,`$2D10`,`$2D0A` | |
| `50` | `SQR` | — | `$2CD5` | square |
| `51`,`52`,`53`,`56` | `STB`,`STW`,`STW.d`,`STF` | addr | `$2BB7`,`$2BC6`,`$2BC5`,`$2BD9` | store |
| `55` | `HALT` | — | `$4F47` | stop with trap code 0 |
| `58`,`59`,`5B`,`5C`,`5D` | stack shuffles | — | `$279A`,`$291D`,`$292B`,`$2791` | |
| `5A` | `ARGF` | addr | `$2A9D` | append a 4-byte float to the argument block |
| `61`,`62` | `CASEB`, `CASEW` | imm8/16 + imm16 | `$27FE`,`$2810` | compare-and-branch chain element |
| `63` | `CALLIND` | addr | `$2838` | call through a procedure variable |
| `64` | `CALL` | imm8 lvl, imm16 | `$2819` | call (target 0 → trap 19) |
| `65`–`67` | `LDB.A/.b/.W` | imm16 / imm8 / imm16 | `$2B22`,`$2B1B`,`$2B29` | load byte, short forms |
| `68`–`6A` | `LDW.A/.b/.W` | " | `$2B37`,`$2B30`,`$2B3E` | load word |
| `6B`–`6D` | `LDF.A/.b/.W` | " | `$2B06`,`$2B0D`,`$2B14` | load float |
| `6E`–`70` | `LEA.A/.b/.W` | " | `$2B4C`,`$2B45`,`$2B53` | effective address |
| `71`–`73` | `STB.A/.b/.W` | " | `$2B5A`,`$2B63`,`$2B6A` | store byte |
| `74`–`76` | `STW.A/.b/.W` | " | `$2B71`,`$2B7C`,`$2B83` | store word |
| `77`–`79` | `STF.A/.b/.W` | " | `$2B8A`,`$2B9E`,`$2BA5` | store float |
| `7A`,`7B` | `INCB.JNZ`,`DECB.JNZ` | addr, imm16 | `$2D51`,`$2D5E` | byte loop counters |
| `7F` | *escape* | imm8 sub-op, addr | `$2F20` | second dispatch table at `$2F32`, five sub-ops (`$2F3C`, `$2F8A`, `$2F8F`, `$2FA9`, `$2FCF`) — set and block assignment |

`.A` = absolute 16-bit address; `.b` = `fp` + unsigned byte; `.W` = `fp` +
unsigned word.

### Floating point (`$80`–`$94`)

Numbers are **4-byte Microsoft Binary Format**: byte 0 is the exponent biased by
`$81` (0 means the value is zero), bit 7 of byte 1 is the sign, and bytes 1–3
carry a 23-bit mantissa with an implied leading 1.

| Op | Meaning | Kernel |
| --- | --- | --- |
| `80` | `abs` | `$4B48` |
| `81` | add | `$45B4` |
| `82`,`83` | divide, reverse divide | `$4587` (trap 11 on zero) |
| `84`,`87`,`88`,`89`,`8A`,`8D` | `=`, `>=`, `>`, `<=`, `<`, `<>` | `$4C50` |
| `85`,`86`,`93` | integer → float (various stack depths) | `$47EA` |
| `8B` | multiply | `$453F` |
| `8C` | negate | `$4C9F` |
| `8E` | round to integer (adds the 0.5 constant at `$4C2A`) | `$4BE3` |
| `8F` | square | `$4B6C` |
| `90`,`91` | subtract, reverse subtract | `$45B1` |
| `92` | truncate to integer | `$4C2E` (trap 13 on overflow) |

### Range checks (`$96`–`$9F`)

| Op | Operands | Meaning |
| --- | --- | --- |
| `96` | lo8, hi8 | check the top of stack lies in `[lo,hi]` |
| `97` | lo16, hi16 | 16-bit form |
| `98`,`9A` | addr | bounds taken from memory |
| `99`,`9F` | lo8, hi8 | two-operand forms |
| `9B`,`9C` | imm8 / imm16 | upper bound only |
| `9D`,`9E` | imm8 / imm16 | lower bound only |

A failed range check is trap 15.

## 8. The effective-address descriptor (`$2E54`)

The first byte selects the form. Three values are special-cased for speed:

| First byte | Following bytes | Meaning |
| --- | --- | --- |
| `$02` | word | absolute address |
| `$82` | word | `fp` + word |
| `$81` | byte | `fp` + byte |

Anything else is decoded field by field:

| Bits | Meaning |
| --- | --- |
| 7–6 | base: `00` = absolute (0), `01` = frame at nesting level given by the next byte (via `$2849`), `10`/`11` = current `fp` |
| 3–2 | indirection: `00` = none; `01` = dereference at offset 0; `10` = one-byte offset then dereference; `11` = two-byte offset then dereference |
| 1–0 | displacement: `00` = none; `01` = one byte; `10`/`11` = two bytes |
| 5–4 | if non-zero, add an index taken from the operand stack |

When bits 1–0 are `01` and bits 5–4 are zero, one further scale byte follows.

## 9. Runtime traps

`$4F47` is opcode `$55` (normal termination, code 0). `$4F49` is the trap
entry: it stores the code at `$AA2A`, reloads `HL`/`DE` for a post-mortem and
executes `halt`. **The CPU stops.** Only a reset gets it back.

| Code | Raised at | Cause |
| --- | --- | --- |
| 0 | `$4F47` | `HALT` opcode — normal end of program |
| 4 | `$2CD0` | integer divide by zero |
| 5 | `$27DF` | jump/case target is address 0 |
| 6 | `$2D8F` | `MOD` with a negative operand |
| 7 | `$288D`, `$3027` | heap exhausted (procedure frame or set/block allocation) |
| 10 | `$4B2B` | floating-point overflow in add/subtract |
| 11 | `$4B61` | floating-point divide by zero |
| 12 | `$4BDE` | floating-point conversion overflow |
| 13 | `$4C25` | float → integer conversion out of range |
| 15 | `$4E55` | range-check failure |
| 19 | `$2827`, `$2A8E` | call through a null procedure value |

For an emulator these matter because a malformed command that pushes a value
out of range — for example an unexpected LUN — reaches a range check and
**halts the CPU** rather than returning an error.

## 10. Revision 1.3 versus 1.4

The two revisions are the same program with code inserted; every structure is
in the same order.

| Structure | 1.4 | 1.3 |
| --- | --- | --- |
| interpreter fetch loop | `$2C20` | `$2C21` |
| opcode dispatch table | `$4CD4` | `$4D03` |
| procedure prologue (call signature) | `$2855` (`CD 55 28`) | `$2856` (`CD 56 28`) |
| p-code entry point | `$4287` | `$42B6` |
| native gateway / jump table | `$0FC9` / `$0FDF` | `$0FC9` / `$0FDF` |
| trap handler | `$4F49` | `$4F78` |
| interrupt handler | `$4F0A` | `$4F39` |
| p-code IP variable | `$AA2F` | `$AA2F` |

Procedure entry points, in listing order, map one-to-one:

```
1.4  003C 0060 00D3 025F 02E9 0311 033F 03DC 0A9F 0BF2 0D94 0DFB 0E57 0ED4
1.3  003C 0060 00D3 025F 02E9 0311 033F 03DC 0A9F 0BF2 0D94 0DFB 0E57 0ED4

1.4  0F85 0FAF 1DAC 1F2E 1FB8 1FE0 1FF2 21AC 303D 3061 31BF 3249 32F6 35BF
1.3  0F85 0FAF 1DAD 1F2F 1FB9 1FE1 1FF3 21AD 303E 3062 31C0 324A 32F7 35EE

1.4  364D 3836 385D 3881 39DF 3A48 3B18 3B40 3FAC 3FBE 4050 4112 4863 4887
1.3  367C 3865 388C 38B0 3A0E 3A77 3B47 3B6F 3FDB 3FED 407F 4141 4892 48B6
```

The 44 native hardware primitives are at the same addresses in both revisions.
The SCSI command set is identical in both.

> The two halves are a **matched pair**. Do not analyse `LVDOS#1` 1.3 against
> `LVDOS#2` 1.4 — the dispatch table addresses differ and nothing will decode.

## 11. Regenerating the listings

```sh
python3 tools/vp-lvdos.py \
    original-images/vp415-module-w-ic7247-lvdos1-6805.3-rev1.4-0x8F90.bin \
    original-images/vp415-module-w-ic7248-lvdos2-6806.3-rev1.4-0x56D7.bin \
    -o disasm
```

This writes `disasm/lvdos-pcode.lst` (the byte code) and
`disasm/lvdos-native.lst` (the Z80 primitives, the interpreter's dispatch
targets and the interrupt handler). `--map` prints the layout summary and the
primitive table without writing files.

The tool locates the interpreter, the entry point and the prologue by signature
rather than by a hard-coded table, so it works on both revisions unchanged. Its
self-check is that the recursive trace produces **zero overlapping decodes** —
if any instruction length were wrong the streams would collide almost
immediately. Both revisions currently decode with zero overlaps and no branch
targets outside the programmed part of the ROM.
