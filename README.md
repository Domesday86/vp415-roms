# vp415-roms
Experimental repo for looking into the Philips VP415 ROM images

## Reverse-engineering environment

A Nix flake provides the tools for disassembling, documenting and extracting
data from these images:

```sh
nix develop            # everything, including Ghidra
nix develop .#lite     # same minus Ghidra's ~700 MB download
```

It brings Ghidra, MAME's `unidasm`, rizin, the ASL macro assembler, srecord and
a Python imaging environment, plus a few helper commands that know which CPU
each image holds — `vp-arch`, `vp-sum16`, `vp-dis`, `vp-ghidra`, `vp-fontdump`,
`vp-lvdos` and `vp-mcs51`.

See [`docs/tooling.md`](docs/tooling.md) for what each tool is for, the
evidence behind the CPU identifications, and a suggested order of work.

## What has been worked out so far

- [`docs/module-w-command-interface.md`](docs/module-w-command-interface.md) —
  module W's SCSI command set, its serial link to control module S, and the
  gateway between them: every command, response format, error and status code,
  with the ROM address behind each claim.
- [`docs/module-w-lvdos-vm.md`](docs/module-w-lvdos-vm.md) — the byte-code
  machine LV-DOS actually runs on, which you need before any of module W's
  addresses mean anything.
- [`docs/player-control-command-set.md`](docs/player-control-command-set.md) —
  the ASCII player-control language, read out of control module S: all 37
  commands, their arguments, every reply, and the two serial ports that carry
  them. This is the command set a host reaches over RS232, or over SCSI
  through module W's `$CA`/`$C8` gateway.
- [`docs/module-s-control.md`](docs/module-s-control.md) — control module S as
  a machine: its hardware and memory map, the eight-task kernel, the two
  command ports and the handshake that decides which one is in charge, and the
  DIP switches with every effect their bits have on the running firmware.
- [`character-set/`](character-set/) — the MB88303 character generator's font,
  extracted and verified against the data sheet.
