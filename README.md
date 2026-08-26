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
each image holds — `vp-arch`, `vp-sum16`, `vp-dis`, `vp-ghidra` and
`vp-fontdump`.

See [`docs/tooling.md`](docs/tooling.md) for what each tool is for, the
evidence behind the CPU identifications, and a suggested order of work.
