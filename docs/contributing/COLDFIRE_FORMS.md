# ColdFire instruction forms

What `tools/verify/verify_cf_forms.py` checks, and the register of forms a unit run has cleared. The DSP's
counterpart is `docs/firmware/CHIP.md`'s instruction-form register (`verify_dsp_forms`).

The chip is an MCF54455 (ISA C with EMAC). The port runs the firmware on Unicorn plus a V4e layer, and has known
defects in EMAC arithmetic and MAC-with-load decoding (`TRAPS.md`: `trap-unicorn-frac`, `trap-unicorn-macload`,
`trap-macsr`). A form the chip has run is one whose result does not depend on the port.

## What a form is

`tools/build/cf_forms.py` spells an instruction as objdump prints it, with numbers, addresses and branch targets
blanked, register classes kept and the instruction's byte length appended:

| objdump | form |
|---|---|
| `movel %a0@(256),%d0` (4 bytes) | `movel An@(N),Dn  [4b]` |
| `moveal #1207959552,%sp` (6 bytes) | `moveal #N,An  [6b]` |
| `movel 0xfc0c4000,%d2` (6 bytes) | `movel ABS,Dn  [6b]` |
| `movel %a0@(0,%d0:l:4),%d1` (4 bytes) | `movel An@(N,Dn:l:4),Dn  [4b]` |
| `macw %d1l,%d2u,<<,%a0@+&,%d3,%acc0` (4 bytes) | `macw Dnl,Dnu,<<,An@+&,Dn,ACC  [4b]` |
| `moveml %d2-%d7/%a2,%sp@` (4 bytes) | `moveml REGS,An@  [4b]` |

The size suffix is part of the mnemonic. The index register's size and scale are kept. `%macsr`, `%pc`, `%sr` and
`%ccr` keep their names; `%acc0..3` is `ACC` and `%accext01`, `%accext23` are `ACCEXT`.

## What clears a form

A form of a remix's runtime units passes when one of these holds:

- analysed stock code has a site of it: `tools/build/cf_code_runs.tsv` lists the address runs of instructions Ghidra
  found in the stock MAIN OS, and the gate decodes those bytes from the user's own image. A linear sweep of the
  image is not used: it decodes the image's tables as code (2,965 of 3,541 forms, measured);
- its module's strongest `Evidence` is `Level.UNIT` or above;
- a row of the table below names it.

The gate reports the forms with none of these, one line each, and does not refuse them yet.

The module side is read from the build's assembler listings (`out/platform/runtime/<NN>_<label>.lst`, written by
`tools/remix/platform_build.py link_runtime`): a listing line is an instruction unless its source starts with a
directive. The bytes of a unit are decoded in one objdump run and each instruction's decoded length is checked
against its listing line's; a unit where they differ fails the gate.

## Not covered

- ROM caves and detour stubs (`build_bus.py` assembles them without `link_runtime`) and the loader.
- An instruction a source writes as `.short` or `.word`.
- A stock function Ghidra's analysis did not reach: its forms have no stock site here, so the error is toward
  reporting.
- A unit run proves the paths that ran, not every instruction of the source. A source changed after the run keeps
  its level (`tools/build/evidence.py stale` lists those).
- The port may still shim a form that has a stock site.

## Regenerating the stock runs

```bash
make ghidra-install GHIDRA=<stock Ghidra 12.1.4>          # once
python3 tools/ghidra/ot_ghidra.py import --ghidra <the install> --only MAIN_OS
# out/ghidra/code_runs.tsv -> tools/build/cf_code_runs.tsv, with its header: Ghidra version, the image's sha256,
# date, run and byte counts
```

The gate fails when `out/raw/section_3_MAIN_OS.bin`'s sha256 is not the header's.

## Register

A row is a form a unit run has cleared that its module's `Evidence` does not cover (a module below `Level.UNIT`
whose author ran the form on a unit). First cell the form in backticks, as the gate prints it.

| form | how it was run on the chip | date |
|---|---|---|
|  |