# Cycle scan: where each effect spends its cycles

`tools/build/interlock_scan.py` prices the path an effect's proc executes with
the DSP56300 core's own manual (DSP56300 Family Manual, DSP56300FM Rev 5): each
instruction form's cycles (Table A-1) and the idle cycles the core inserts for
some sequences (sections A.2 and 3.5). This page holds what the scan found for
every effect with DSP code of its own and for every stock effect, scanned on
18 Nov 2026 on main at `5556a840`, and the changes that would make each
cheaper.

It is a model from the manual, not a measurement. Section 1 is how far it has
been checked against the unit: across 38 settings of 22 effects it reads 3.0 %
above the unit on average and never more than 0.2 % below. The unit's own
figures, where they exist, are in [COSTS.md](COSTS.md); where they do not, the
figures here are the best estimate there is.

```bash
python3 tools/build/interlock_scan.py EFFECT --sweep                    # every mode: defaults, all max, all min, dear
python3 tools/build/interlock_scan.py modulation MODE=JUNO LOFI=40 MIX=100 --top 20
python3 tools/build/interlock_scan.py "PLATE REV" --sweep --json out/plate.json
python3 tools/build/interlock_scan.py --selftest                        # the manual's own examples
```

## How to read the figures

- **instr/sample**: instructions executed a sample, the figure `dsp_host -meter`
  reports. `cycle_count.py` prices the words of an effect's worst loop, a
  different figure (MODULATION's LINE: 252 words against 206 instructions in
  JUNO); neither counts cycles.
- **cycles/sample**: the model: Table A-1 for each executed instruction, plus the
  stalls, plus one cycle after each conditional branch not taken (A.2.6.3).
- **narrow**: the model without two stall kinds the manual is not explicit about
  (a `lua` destination, and a Tcc, counted as stall producers). On the unit
  figures, the narrow figure is the closer one (section 1).
- **% of a frame**: cycles/sample ÷ 4,532 (the measured clock, `docs/firmware/CHIP.md`
  section 2). COSTS.md's slot costs are in this unit.
- A run is one steady block of 16 samples (block 263 of the run, past the
  servers' 256-call dry start), on one instance, with a test signal on both
  channels. Every figure is per sample and includes the block's per-block work.
- **dearest**: each value of the selector (MODE, or the first select of at most
  8 values) is run three ways: its defaults (with the mode's view defaults when
  the module has views), every other named knob at its maximum, every other at
  its minimum, and the manifest's `dear` knobs when it declares them. The
  tables show the dearest, as the stock measurements on the unit did.
- **where the cycles above one an instruction go**: the three largest of the
  stall kinds and the slow forms, in cycles a sample. They are what the
  remedies below act on.

## The remedies, by what the scan reports

Each stall kind and each slow form has a standard change. All of them reorder
or re-spell code without touching the arithmetic, so a module's bit-identity
gate (`make verify-ident MOD=<name>`) can prove the output unchanged.

| reported | what it is | the change |
|---|---|---|
| arithmetic stall (`arith`) | a move reads an accumulator the previous ALU instruction wrote: 1 idle cycle | put an independent instruction between the ALU instruction and the move, or carry the store in a later instruction's parallel move |
| transfer stall | a move reads an accumulator the previous move wrote: 1 | the same: one instruction between |
| address-register stall (`agu`) | an R, N or M register written by a move, then that set used for an address within 3 cycles: 3, 2 or 1 idle cycles | write the register 3 cycles before its use (hoist it above independent work), or address through a register written earlier |
| stall after `lua` (`agu-lua`) | the same after a `lua`; counted, but the manual does not say that a `lua` destination interlocks | as above; lower priority until measured |
| stall after Tcc (`arith-tcc`) | a move reads an accumulator a Tcc wrote; counted, the manual does not say | as above; lower priority |
| status stall | an SR read after an ALU instruction: 1 or 2 | move the SR read later |
| calls | `bsr` 4 cycles (5 with a long displacement), `rts` 3: 7 a call | inline the callee in a sample loop; it costs words, which the window and the loader's copy time pay (`DEMAND_LOADER.md`) |
| branches | a short `bcc` or `bra` 4 cycles, a long one 5; a branch not taken delays the next decode by 1 | a mode's arms as separate loops chosen once a block (more words), or a Tcc instead of a short skip |
| `lua` | 3 cycles, where `move (rN)+nN` is 1 | `move (rN)+nN` when updating rN in place is acceptable; otherwise keep the `lua` out of the sample loop |
| displaced moves | `x:(rN+d)` 2 cycles (3 for a two-word displacement), where `x:(rN)+` is 1 | walk a pointer over the state block instead of displacing from r7 (MODULATION's 22 Sep pass, its README) |
| `(rn+nn)` addresses | `(rN+nN)` or `-(rN)`: 2 cycles, where a post-update is 1 | a post-update on the previous access |
| two-word forms | a long immediate or a long absolute address: +1 cycle | keep the constant in a register across the loop, or use the short immediate when the value fits |
| do/rep | 5 cycles to start a hardware loop | per block or per call only; in a sample loop, unroll a short count |
| P reads (`movem`) | a move to or from P memory: 6 cycles in Table A-1 | read a P table once a block into X or Y. Section 1: the unit suggests 6 is high |

A new form must still pass the chip-form register: `tools/build/dsp_forms.py`
and `verify_dsp_forms` refuse a form no stock site, register row or
unit-proven module has run (`TRAPS.md#trap-chip-form`).

## 1. How far the model is checked

Every unit figure the repo has for an effect whose scanned code is the code the
unit ran. The unit's are LOAD METER slot costs
(`tools/remix/slot_costs.json`, 24 to 27 Oct 2026; the dearer core × 4,532),
at the settings the hardware matrix stamped (`tools/hw/ot_matrix.py`: the
manifest's defaults, `dear`, and each mode with and without `dear`, a mode's
view applied when the mode is chosen). A module whose DSP source changed after
its measurement was scanned at its source on main at the measurement's date.
FX1 and FX2 rows of one setting price the same and are shown once.

| effect | setting | source scanned | unit, % of a frame | unit, cycles | instructions | model | narrow | narrow ÷ unit |
|---|---|---|---|---|---|---|---|---|
| BBD | FX2 dear | today's | 11.34 | 513.9 | 365.2 | 528.3 | 519.2 | 1.010 |
| BBD | FX2 def | today's | 10.07 | 456.4 | 328.5 | 468.8 | 460.2 | 1.008 |
| CHORUS | FX1 def | today's | 6.28 | 284.6 | 257.4 | 288.5 | 288.4 | 1.013 |
| COMB FILTER | FX1 def | today's | 2.74 | 124.2 | 99.6 | 130.0 | 126.9 | 1.022 |
| COMPRESSOR | FX1 def | today's | 2.18 | 98.8 | 71.6 | 103.1 | 103.1 | 1.043 |
| DARK REV | FX2 def | today's | 5.49 | 248.8 | 197.2 | 252.9 | 252.9 | 1.016 |
| DISTORX | FX2 dear | main on 2026-10-27 23:00 (14c18ff0) | 9.45 | 428.3 | 269.5 | 439.4 | 435.2 | 1.016 |
| DJ EQ | FX1 def | today's | 7.30 | 330.8 | 297.6 | 334.5 | 334.5 | 1.011 |
| EQUALIZER | FX1 def | today's | 4.10 | 185.8 | 141.9 | 190.2 | 190.2 | 1.024 |
| EUCLID | FX1 def | today's | 4.87 | 220.7 | 141.8 | 232.3 | 232.2 | 1.052 |
| FILTER | FX1 def | today's | 5.11 | 231.6 | 204.9 | 235.8 | 235.8 | 1.018 |
| FLANGER | FX1 def | today's | 3.15 | 142.8 | 119.8 | 148.6 | 144.8 | 1.014 |
| LO-FI | FX1 def | today's | 6.66 | 301.8 | 279.6 | 305.9 | 305.9 | 1.013 |
| LOFI2 | FX2 dear | today's | 13.63 | 617.7 | 410.2 | 653.4 | 646.2 | 1.046 |
| LOFI2 | FX2 def | today's | 8.68 | 393.4 | 254.1 | 424.6 | 417.3 | 1.061 |
| LOFI2 | FX2 mode0+dear | today's | 8.73 | 395.6 | 255.2 | 426.5 | 419.2 | 1.060 |
| LOFI2 | FX2 mode1 | today's | 13.60 | 616.4 | 409.4 | 652.3 | 645.1 | 1.047 |
| LOFI2 | FX2 mode1+dear | today's | 13.64 | 618.2 | 410.6 | 654.2 | 647.0 | 1.047 |
| LOFI2 | FX2 mode2 | today's | 13.58 | 615.4 | 409.1 | 651.5 | 644.2 | 1.047 |
| MINIVERB | FX2 def | today's | 12.29 | 557.0 | 314.5 | 608.5 | 602.5 | 1.082 |
| MODULATION | FX1 dear | main on 2026-10-25 12:00 (9a752f97) | 8.66 | 392.5 | 296.8 | 402.2 | 395.6 | 1.008 |
| MODULATION | FX1 mode0 | main on 2026-10-25 12:00 (9a752f97) | 7.21 | 326.8 | 212.9 | 333.5 | 326.4 | 0.999 |
| MODULATION | FX1 mode1 | main on 2026-10-25 12:00 (9a752f97) | 8.76 | 397.0 | 258.8 | 402.5 | 398.4 | 1.004 |
| MODULATION | FX1 mode2 | main on 2026-10-25 12:00 (9a752f97) | 8.96 | 406.1 | 253.6 | 412.5 | 405.4 | 0.998 |
| MODULATION | FX1 mode3 | main on 2026-10-25 12:00 (9a752f97) | 7.93 | 359.4 | 262.5 | 368.1 | 361.2 | 1.005 |
| PHASER | FX1 def | today's | 5.18 | 234.8 | 185.4 | 240.6 | 238.5 | 1.016 |
| PLATE REV | FX2 def | today's | 5.27 | 238.8 | 186.1 | 243.5 | 243.5 | 1.020 |
| SPATIALIZER | FX1 def | today's | 1.28 | 58.0 | 52.1 | 62.7 | 62.7 | 1.081 |
| SPECTRUM | FX1 dear | today's | 7.08 | 320.9 | 245.1 | 331.2 | 330.4 | 1.030 |
| SPECTRUM | FX1 mode0+dear | today's | 6.55 | 296.8 | 217.9 | 303.2 | 302.8 | 1.020 |
| SPECTRUM | FX1 mode1 | today's | 4.78 | 216.6 | 153.0 | 223.3 | 222.6 | 1.027 |
| SPECTRUM | FX1 mode1+dear | today's | 4.73 | 214.4 | 152.2 | 220.9 | 220.2 | 1.027 |
| SPECTRUM | FX1 mode2 | today's | 7.90 | 358.0 | 254.2 | 371.1 | 369.7 | 1.033 |
| SPECTRUM | FX1 mode3 | today's | 7.14 | 323.6 | 245.9 | 333.6 | 332.8 | 1.029 |
| SPRING REV | FX2 def | today's | 6.38 | 289.1 | 261.1 | 293.1 | 293.1 | 1.014 |
| STUTTR | FX2 dear | today's | 4.60 | 208.5 | 127.7 | 268.4 | 267.3 | 1.282 |
| STUTTR | FX2 def | today's | 3.11 | 140.9 | 75.7 | 153.4 | 153.3 | 1.088 |
| STUTTR | FX2 mode1+dear | today's | 4.19 | 189.9 | 111.2 | 232.9 | 231.8 | 1.221 |
| STUTTR | FX2 mode2+dear | today's | 3.94 | 178.6 | 102.9 | 215.2 | 214.1 | 1.199 |
| TRANSIENT | FX1 dear | today's | 5.32 | 241.1 | 169.0 | 270.0 | 258.9 | 1.074 |
| VOID | FX2 dear | today's | 10.46 | 474.0 | 281.9 | 503.9 | 498.5 | 1.052 |
| VOID | FX2 def | today's | 7.05 | 319.5 | 187.9 | 341.9 | 338.5 | 1.059 |

- **Over the 38 points without STUTTR, the narrow model is a mean 3.0 % above
  the unit (rms 3.8 %), from −0.2 % to +8.2 %.** The full model (both doubtful
  stall kinds counted) is 0 to 4.6 points higher (TRANSIENT the most, its
  Tcc results moved at once).
- The stock effects, Elektron's code and the code with the least risk in the
  comparison, read +1.1 to +4.3 % (SPATIALIZER +8.1 %, 4.7 cycles on 58).
- **A second, independent measurement agrees.** Jannik Aßfalg's idle-pass
  counts on an MKII (`CHIP.md` section 2, 12 Oct 2026, the dearest of
  as-picked, all-min and all-max) against the scan's dearest of defaults, all
  max and all min:

  | effect | unit, core 0 / core 1 | instructions | model | narrow | narrow ÷ core 0 / ÷ core 1 |
  |---|---|---|---|---|---|
  | DJ EQ | 330 / 342 | 297.6 | 334.5 | 334.5 | 1.014 / 0.978 |
  | LO-FI | 301 / 311 | 279.6 | 305.9 | 305.9 | 1.016 / 0.984 |
  | SPRING REV | 288 / 299 | 261.1 | 293.1 | 293.1 | 1.018 / 0.980 |
  | CHORUS | 285 / 295 | 257.8 | 290.0 | 289.9 | 1.017 / 0.983 |
  | FILTER | 276 / 285 | 240.2 | 280.1 | 280.1 | 1.015 / 0.983 |
  | DARK REV | 248 / 257 | 197.4 | 253.5 | 253.5 | 1.022 / 0.986 |
  | PLATE REV | 241 / 249 | 188.1 | 246.9 | 246.9 | 1.024 / 0.991 |
  | PHASER | 234 / 242 | 185.7 | 240.8 | 238.7 | 1.020 / 0.986 |
  | EQUALIZER | 187 / 193 | 142.2 | 191.1 | 191.1 | 1.022 / 0.990 |
  | FLANGER | 142 / 147 | 119.8 | 148.6 | 144.8 | 1.020 / 0.985 |
  | COMB FILTER | 124 / 128 | 99.6 | 130.0 | 126.9 | 1.023 / 0.991 |
  | COMPRESSOR | 99 / 102 | 71.6 | 103.1 | 103.1 | 1.041 / 1.010 |
  | SPATIALIZER | 78 / 80 | 68.6 | 82.1 | 82.1 | 1.053 / 1.027 |

  The narrow model lands between the two cores' readings for eleven of the
  thirteen; COMPRESSOR and SPATIALIZER are 1.0 and 2.7 % above the dearer
  core.
- **STUTTR** reads 8.8 % high at its defaults and up to 28 % at `dear`. Its load
  varies with time (COSTS.md: core 0 mean 40.8 %, maximum 45.1 %), the
  catalog keeps the mean, and the scan prices one block. Against the
  maximum (5.65 %, 256 cycles) the `dear` figure is 4.4 % high.
- **Where the model runs high** (MINIVERB, TRANSIENT, EUCLID, VOID, LOFI2:
  4.6 to 8.2 %), a least-squares fit of the excess against what each run
  contains puts it on P reads (`movem`, 0.53 of their extra cycles),
  address-register stalls (0.35) and displaced moves (0.17); with those three
  the fit leaves 4.2 cycles rms. Inferred, not measured: Table A-1's 6 cycles
  for a P read may be high for internal P, and some address-register stalls
  may be shorter than counted.
- **One reading is open.** A.2.4 counts the three-cycle distance "in clock
  cycles" from the instruction that wrote the register. The scan counts from
  that instruction's end (the default); `ILSCAN_AGU_FROM=start` counts from its
  first cycle, so a two-word writer such as `move #>$ffff8f,n5` is one cycle
  nearer clear. Only MINIVERB separates the two: +8.2 % from the end, +2.8 %
  from the start. Every other point moves by 0.6 points or less (mean +3.0 %
  against +2.8 %). The default stays until a unit separates them.
- **Not checked:** CHARACTER and SHATTER (their October sources no longer
  build against today's tree), GATE VERB (now VERBERATION, rewritten),
  TAPE ECHO and DELAY (on the ColdFire), and every effect the catalog has no
  figure for (VOCODER, RESONATOR, CHARACTER TXTR, VERBERATION, VIBRATO,
  DEVILISH, MULTIBCOMP, the servers, SEND).
- **The shared window is not in the model.** DSP56720RM section 16.2: every
  program fetch from `0x30000..0x3ffff` costs one more cycle, and two cores in
  one 8K block contend. The stock effects and everything measured on 25 Oct
  ran from internal P (window placement landed that evening, `1a7bf9d7`,
  `36b86291`). Where the 27 Oct images (`COST-*`: BBD, DISTORX, MINIVERB,
  STUTTR, VOID) put their effects is not recorded; their figures fit the model
  about as well as the internal ones. A window effect's real cost may be higher than its figure
  here. To settle it, read one effect's slot cost on a unit from internal P
  and from the window, the same code.

## 2. What each effect costs

### The modules

| effect | setting (variant) | instr/sample | cycles/sample | % of a frame | stalls | where the cycles above one an instruction go |
|---|---|---|---|---|---|---|
| MODULATION | JUNO (def) | 206.2 | 321.8 | 7.1 % | 50.7 | arithmetic stalls 28, branches 18, calls 16 |
| MODULATION | DIM (def) | 252.1 | 390.9 | 8.6 % | 55.7 | arithmetic stalls 36, branches 25, two-word forms 18 |
| MODULATION | FLNG (def) | 245.9 | 398.8 | 8.8 % | 61.8 | arithmetic stalls 34, calls 28, branches 26 |
| MODULATION | COMB (def) | 256.1 | 360.9 | 8.0 % | 55.7 | arithmetic stalls 34, calls 16, address-register stalls 15 |
| MODULATION | PHSR (def) | 288.1 | 393.1 | 8.7 % | 45.1 | arithmetic stalls 37, calls 29, do/rep 8 |
| SPECTRUM | LADR (max) | 217.9 | 303.2 | 6.7 % | 48.4 | arithmetic stalls 44, calls 21, displaced moves 5 |
| SPECTRUM | SEM (def) | 153.0 | 223.3 | 4.9 % | 37.6 | arithmetic stalls 28, calls 10, displaced moves 9 |
| SPECTRUM | ISO (def) | 254.2 | 371.1 | 8.2 % | 55.2 | arithmetic stalls 40, (rn+nn) addresses 21, calls 14 |
| SPECTRUM | VOWL (def) | 245.9 | 333.6 | 7.4 % | 41.4 | arithmetic stalls 37, calls 23, displaced moves 7 |
| CHARACTER | SAT=TAPE (max) | 262.8 | 407.5 | 9.0 % | 79.5 | arithmetic stalls 62, branches 16, calls 14 |
| CHARACTER | SAT=TUBE (max) | 258.9 | 428.3 | 9.5 % | 76.7 | arithmetic stalls 57, branches 24, P reads (movem) 20 |
| CHARACTER | SAT=INFL (max) | 230.9 | 363.2 | 8.0 % | 72.2 | arithmetic stalls 54, branches 24, stalls after lua 13 |
| CHARACTER TXTR | SAT=TAPE (max) | 416.1 | 677.5 | 14.9 % | 114.6 | arithmetic stalls 88, P reads (movem) 41, calls 26 |
| CHARACTER TXTR | SAT=TUBE (max) | 411.1 | 697.9 | 15.4 % | 111.8 | arithmetic stalls 83, P reads (movem) 61, branches 28 |
| CHARACTER TXTR | SAT=INFL (max) | 385.8 | 636.2 | 14.0 % | 107.8 | arithmetic stalls 81, P reads (movem) 41, branches 28 |
| TRANSIENT | defaults (def) | 169.0 | 270.0 | 6.0 % | 33.5 | displaced moves 27, P reads (movem) 21, arithmetic stalls 19 |
| SHATTER | HARD (max) | 201.9 | 365.1 | 8.1 % | 33.0 | branches 59, displaced moves 52, arithmetic stalls 24 |
| SHATTER | SOFT (max) | 213.9 | 383.1 | 8.5 % | 37.0 | branches 59, displaced moves 52, arithmetic stalls 28 |
| SHATTER | CHAOS (max) | 202.3 | 366.1 | 8.1 % | 33.1 | branches 59, displaced moves 52, arithmetic stalls 24 |
| VERBERATION | all 4 modes (def) | 238.5 | 455.7 | 10.1 % | 107.8 | address-register stalls 72, displaced moves 58, arithmetic stalls 27 |
| VIBRATO | SHP=SINE, SHP=TRI, SHP=SQR (max) | 121.3 | 206.8 | 4.6 % | 36.4 | arithmetic stalls 19, displaced moves 16, calls 16 |
| VIBRATO | SHP=RND (max) | 118.7 | 202.1 | 4.5 % | 35.9 | arithmetic stalls 19, displaced moves 16, calls 15 |
| VOCODER | INT, EXT (def) | 757.1 | 1245.8 | 27.5 % | 204.8 | arithmetic stalls 179, P reads (movem) 151, displaced moves 96 |
| VOID | SHPE=SIN, SHPE=SQR, SHPE=SAW (dear) | 281.9 | 503.9 | 11.1 % | 62.4 | displaced moves 96, arithmetic stalls 46, branches 36 |
| BBD | STGS=1024, STGS=4096 (dear) | 365.2 | 528.3 | 11.7 % | 54.3 | displaced moves 50, arithmetic stalls 40, two-word forms 25 |
| DISTORX | OFF (def) | 1.8 | 4.1 | 0.1 % | 0.1 |  |
| DISTORX | SD-1 (min) | 180.4 | 285.9 | 6.3 % | 25.8 | displaced moves 38, two-word forms 20, arithmetic stalls 19 |
| DISTORX | RAT, TURB (min) | 232.9 | 375.9 | 8.3 % | 40.8 | displaced moves 70, arithmetic stalls 35, two-word forms 11 |
| EUCLID | every RATE value (5) (def) | 141.8 | 232.3 | 5.1 % | 25.2 | displaced moves 53, arithmetic stalls 20, branches 5 |
| LOFI2 | RING (max) | 255.2 | 426.5 | 9.4 % | 56.5 | displaced moves 71, arithmetic stalls 35, address-register stalls 14 |
| LOFI2 | DOWN (max) | 410.6 | 654.2 | 14.4 % | 89.6 | displaced moves 88, arithmetic stalls 60, two-word forms 34 |
| LOFI2 | UP (max) | 410.2 | 653.4 | 14.4 % | 89.5 | displaced moves 88, arithmetic stalls 60, two-word forms 34 |
| MINIVERB | every RATE value (8) (max) | 314.6 | 608.8 | 13.4 % | 150.3 | address-register stalls 96, displaced moves 59, two-word forms 49 |
| RESONATOR | defaults (max) | 402.1 | 655.9 | 14.5 % | 82.6 | displaced moves 97, arithmetic stalls 53, calls 50 |
| STUTTR | FWD (dear) | 127.7 | 268.4 | 5.9 % | 20.6 | branches 61, displaced moves 40, arithmetic stalls 12 |
| STUTTR | HALF (dear) | 111.2 | 232.9 | 5.1 % | 17.6 | branches 53, displaced moves 34, arithmetic stalls 11 |
| STUTTR | QUART, RND (dear) | 102.9 | 215.2 | 4.7 % | 16.1 | branches 49, displaced moves 30, arithmetic stalls 11 |
| DEVILISH | SWP=ACID, SWP=WHST, SWP=SELF (def) | 1.1 | 1.5 | 0.0 % | | idle: a voice of OCTA303 with nothing triggering it |
| TAPE ECHO | SYNC=FREE, SYNC=BEAT (def) | 1.1 | 1.5 | 0.0 % | | runs on the ColdFire; the DSP entry is a stub |

### The bus

The servers' figures are one instance; SEND's is one client. COSTS.md does
not bound the bus remixes, and these are the first figures for the servers
since the burn sweep's reverb (`CHIP.md` section 2: about 1,650 cycles a
sample for an older engine).

| effect | setting (variant) | instr/sample | cycles/sample | % of a frame | stalls | where the cycles above one an instruction go |
|---|---|---|---|---|---|---|
| REVERB SERVER | ROOM, PLATE, BIG (min) | 1009.4 | 1593.1 | 35.2 % | 261.9 | arithmetic stalls 185, displaced moves 125, two-word forms 64 |
| DELAY SERVER | CLEAN (min) | 775.1 | 976.2 | 21.5 % | 70.2 | displaced moves 65, arithmetic stalls 45, branches 26 |
| DELAY SERVER | GRAIN (min) | 1424.1 | 1966.2 | 43.4 % | 256.2 | arithmetic stalls 157, displaced moves 137, two-word forms 78 |
| DELAY SERVER | REVRS (min) | 851.1 | 1078.2 | 23.8 % | 87.2 | displaced moves 69, arithmetic stalls 57, branches 22 |
| SEND | defaults (def) | 37.1 | 57.5 | 1.3 % | 6.9 | displaced moves 7, arithmetic stalls 6, two-word forms 2 |

### The stock effects

| effect | setting (variant) | instr/sample | cycles/sample | % of a frame | stalls | where the cycles above one an instruction go |
|---|---|---|---|---|---|---|
| CHORUS | TAPS=1, TAPS=2 (def) | 257.3 | 288.1 | 6.4 % | 4.1 | do/rep 11, displaced moves 9, two-word forms 4 |
| CHORUS | TAPS=3, TAPS=4 (def) | 257.6 | 288.9 | 6.4 % | 4.6 | do/rep 11, displaced moves 9, two-word forms 4 |
| CHORUS | TAPS=5 (def) | 257.8 | 290.0 | 6.4 % | 5.1 | do/rep 12, displaced moves 9, two-word forms 4 |
| COMB FILTER | defaults (def) | 99.6 | 130.0 | 2.9 % | 20.2 | arithmetic stalls 8, address-register stalls 7, stalls after lua 3 |
| COMPRESSOR | defaults (def) | 71.6 | 103.1 | 2.3 % | 10.4 | displaced moves 8, two-word forms 7, arithmetic stalls 6 |
| DARK REV | MIXF=MIX (def) | 197.2 | 252.9 | 5.6 % | 14.6 | do/rep 12, arithmetic stalls 12, displaced moves 9 |
| DARK REV | MIXF=SEND (def) | 197.4 | 253.5 | 5.6 % | 14.7 | arithmetic stalls 12, do/rep 12, displaced moves 9 |
| DELAY | not scanned: DELAY runs on the ColdFire (stock.NO_DSP): its DSP entry is the passthrough stub | | | | | |
| DJ EQ | defaults (def) | 297.6 | 334.5 | 7.4 % | 4.9 | calls 16, do/rep 10, displaced moves 5 |
| EQUALIZER | TYP1=LOW, TYP1=PEQ, TYP1=HIGH (max) | 142.2 | 191.1 | 4.2 % | 26.7 | arithmetic stalls 25, do/rep 8, displaced moves 6 |
| FILTER | HP=12dB, HP=24dB (max) | 240.2 | 280.1 | 6.2 % | 11.1 | do/rep 8, arithmetic stalls 8, displaced moves 8 |
| FLANGER | defaults (def) | 119.8 | 148.6 | 3.3 % | 12.3 | arithmetic stalls 6, do/rep 6, lua 5 |
| LO-FI | defaults (def) | 279.6 | 305.9 | 6.7 % | 15.8 | arithmetic stalls 14, displaced moves 3, do/rep 3 |
| MULTIBCOMP | defaults (def) | 4.2 | 4.6 | 0.1 % | | a stub path in the stock image |
| PHASER | NUM=2 (def) | 185.4 | 240.6 | 5.3 % | 29.2 | arithmetic stalls 27, do/rep 12, lua 5 |
| PHASER | every NUM value (4) (def) | 185.5 | 240.6 | 5.3 % | 29.2 | arithmetic stalls 27, do/rep 12, lua 5 |
| PLATE REV | MIXF=MIX (min) | 187.9 | 246.2 | 5.4 % | 34.4 | arithmetic stalls 29, do/rep 11, displaced moves 5 |
| PLATE REV | MIXF=SEND (min) | 188.1 | 246.9 | 5.4 % | 34.5 | arithmetic stalls 30, do/rep 11, displaced moves 5 |
| SPATIALIZER | PHSE=NONE, PHSE=L, PHSE=R (max) | 68.4 | 81.6 | 1.8 % | 3.7 | do/rep 4, arithmetic stalls 3, displaced moves 2 |
| SPATIALIZER | PHSE=L,R (max) | 68.6 | 82.1 | 1.8 % | 3.7 | do/rep 4, arithmetic stalls 3, branches 2 |
| SPRING REV | TYPE=1, TYPE=2 (def) | 261.1 | 293.1 | 6.5 % | 5.9 | do/rep 7, displaced moves 5, arithmetic stalls 5 |
| SPRING REV | TYPE=3 (def) | 260.9 | 292.1 | 6.4 % | 5.9 | do/rep 7, displaced moves 5, arithmetic stalls 5 |

## 3. Where to optimize

In order of what a change would buy against the budget: the effects over the
9.07 % a slot that a core can give every slot (COSTS.md, "free everywhere")
first, then the dearest of the rest. The stall figures are what reordering
alone can recover, at most; a stall between two instructions that depend on
each other needs other work moved between them, which a short loop may not
have.

- **MINIVERB** (13.4 %, over the cap). Its taps load each offset into `n5`
  immediately before the access: `move #>$ffff8f,n5` then
  `move y:(r5+n5),b` (`mv_mix+62..110`). Each tap pays a two-word immediate
  (1 extra), an address-register stall (3; 2 by the other reading, section 1)
  and an `(rn+nn)` address (1 extra): 7 cycles. A two-word displaced move,
  `move y:(r5+$ffff8f),b`, does the access in 3 with no stall: about 4 cycles a
  tap at about 30 taps a sample, up to about 120 of its 609. Check the form
  against the chip-form register first.
- **VOCODER** (27.5 %, not in the catalog). 179 cycles a sample of arithmetic
  stalls, in `vc_gend` (`macr` then a move of the same accumulator, 10 a site)
  and 151 of P reads (if Table A-1's 6 cycles hold; section 1). Interleaving the
  bands' `macr` chains would remove most of the stalls; moving the P tables to Y
  once a block, the P reads.
- **CHARACTER TXTR** (15.4 %) and **CHARACTER** (9.5 %). Arithmetic stalls (55 to
  88), P reads (20 to 61) and a `lua` followed at once by a read through its
  register (`lua (r5+$2),r5` then `move x:(r5),a`, 13 to 16 if a `lua`
  destination interlocks).
- **RESONATOR** (14.5 %). Displaced moves (97), arithmetic stalls in `rs_one`
  (five sites, 8 a sample each) and calls (50).
- **LOFI2** (14.4 %, over the cap). Displaced moves (88), arithmetic stalls (60),
  two-word forms (34), and `move a1,r5` then `move p:(r5),y0` (a P read whose
  address is written the instruction before: 3 + 6 cycles).
- **BBD** (11.7 % at `dear`, over the cap). Displaced moves (50), arithmetic
  stalls (40), two-word forms (25).
- **VOID** (11.1 % at `dear`, over the cap). Displaced moves (96), arithmetic
  stalls (46), branches (36).
- **VERBERATION** (10.1 %). The MINIVERB pattern: `move #>$ffff94,n5` or
  `move x:(r7+$47),n5`, then `y:(r5+n5)` (`gv_p2a`), 72 cycles a sample of
  address-register stalls. An immediate offset takes MINIVERB's remedy; an
  offset read from the state block needs its load three cycles earlier.
- **MODULATION** (up to 8.8 %). `mo_tap` (the linear tap read, twice a sample,
  three times in FLNG): `and #>$3ff,a` / `move a1,n5` / `move (r5)+n5` is an
  arithmetic stall and a three-cycle address-register stall a call; its
  `asl`/`asr` splits add two more. LINE's `move r2,r5` and `move r6,r5` each
  followed by `move (r5)+n5` (3 each). Calls (16 to 29) and LINE's arm
  branches (18 to 26) are the forms. 45 to 62 cycles a sample of stalls,
  depending on the mode.
- **VIBRATO** (4.6 %). `vb_tap` is `mo_tap`'s pattern, with the same stalls;
  one fix serves both.
- **SPECTRUM** (up to 8.2 %). Arithmetic stalls (28 to 44, the ladder core
  `fs_lcore`: each `asr`/`asl` result moved at once) and calls (10 to 23).
- **SHATTER** (8.5 %). Branches (59) and displaced moves (52).
- **DISTORX** (8.3 % at RAT and TURB). Displaced moves (70), arithmetic stalls (35).
- **TRANSIENT** (6.0 %) and **EUCLID** (5.1 %): displaced moves first.
- **STUTTR** (5.9 % at `dear` in FWD): branches (49 to 61) and displaced moves
  (30 to 40).
- **The servers.** The reverb (35.2 % of a core, one instance) has 185 cycles a
  sample of arithmetic stalls in `lfrol` (8 a sample at each of its sites: an
  ALU result moved at once), 125 of displaced moves and 64 of two-word forms.
  The delay's GRAIN (43.4 %) has 157 of arithmetic stalls and 137 of displaced
  moves; CLEAN (21.5 %) and REVRS (23.8 %) have the `move a1,r5` then
  `move y:(r5+n5)` pair (6 a sample a site).

The sites of each effect's dearest setting, largest first (the full list:
`--top N`):

**MODULATION**, FLNG (def): 398.8 cycles a sample, 61.8 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 9.00 | agu | `move (r5)+n5` at mo_tap+13 | `move a1,n5` at mo_tap+12 |
| 4.00 | arith | `move a,x0` at mo_itrd+3 | `sub b,a` at mo_itrd+2 |
| 3.00 | arith | `move a1,y1` at mo_tap+4 | `asl #$b,a,a` at mo_tap+3 |
| 3.00 | arith | `move a1,x0` at mo_tap+7 | `asr #$c,a,a` at mo_tap+6 |
| 3.00 | arith | `move a1,n5` at mo_tap+12 | `and #>$3ff,a` at mo_tap+10 |
| 3.00 | agu | `move (r5)+n5` at mo_line+133 | `move r2,r5` at mo_line+132 |

**SPECTRUM**, ISO (def): 371.1 cycles a sample, 55.2 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 6.00 | agu | `move (r5)+n5` at fs_ccore+2 | `move #$6,n5` at fs_ccore+1 |
| 3.00 | agu | `move x:(r6+n6),a` at fs_cap+73 | `move a1,n6` at fs_cap+72 |
| 3.00 | agu | `move (r3)+n3` at fs_cap+89 | `move #$c,n3` at fs_cap+88 |
| 2.00 | arith | `move a,x0` at fs_ccore+12 | `abs a` at fs_ccore+11 |
| 2.00 | arith | `move a,x:(r1)+` at fs_ccore+15 | `mpy x0,y1,a` at fs_ccore+14 |
| 2.00 | arith | `move a,x:(r1)+` at fs_ccore+20 | `add #>$7fffff,a` at fs_ccore+18 |

**CHARACTER**, SAT=TUBE (max): 428.3 cycles a sample, 76.7 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.00 | agu-lua | `move x:(r5),a` at proc+581 | `lua (r5+$2),r5` at proc+580 |
| 3.00 | agu-lua | `move x:(r5),a` at proc+585 | `lua (r5+$6),r5` at proc+584 |
| 3.00 | agu-lua | `move x:(r5),a` at proc+592 | `lua (r5+$2),r5` at proc+591 |
| 2.00 | agu-lua | `move x:(r3)+,x0` at proc+574 | `lua (r4+$3d),r3` at proc+572 |
| 2.00 | arith | `abs a a,x1` at proc+843 | `mpy x0,y1,a #$40,b` at proc+842 |
| 2.00 | arith | `tst b b,y0` at proc+845 | `sub a,b #$0,x0` at proc+844 |

**CHARACTER TXTR**, SAT=TUBE (max): 697.9 cycles a sample, 111.8 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.00 | agu-lua | `move x:(r5),a` at ch_rdone+11 | `lua (r5+$2),r5` at ch_rdone+10 |
| 3.00 | agu-lua | `move x:(r5),a` at ch_rdone+15 | `lua (r5+$6),r5` at ch_rdone+14 |
| 3.00 | agu-lua | `move x:(r5),a` at ch_rdone+22 | `lua (r5+$2),r5` at ch_rdone+21 |
| 3.00 | agu-lua | `lua (r1+$11),r2` at ch_rdone+69 | `lua (r1-$33),r1` at ch_rdone+68 |
| 2.00 | agu-lua | `move x:(r3)+,x0` at ch_rdone+4 | `lua (r4+$3d),r3` at ch_rdone+2 |
| 2.00 | arith | `move a,b` at chtx2+2 | `abs a` at chtx2+1 |

**TRANSIENT**, defaults (def): 270.0 cycles a sample, 33.5 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 1.00 | arith | `move b,x0` at proc+64 | `abs b` at proc+63 |
| 1.00 | arith-tcc | `move a,x1` at proc+67 | `tlt x0,a` at proc+66 |
| 1.00 | transfer | `move a1,x0` at proc+70 | `move x:(r7+$6),a0` at proc+69 |
| 1.00 | arith-tcc | `move a1,x:(r7+$4)` at proc+76 | `tlt x1,a` at proc+75 |
| 1.00 | arith | `move a1,x1` at proc+89 | `asl #$1,a,a` at proc+88 |
| 1.00 | arith | `move a1,n5` at proc+91 | `asr #$12,a,a` at proc+90 |

**SHATTER**, SOFT (max): 383.1 cycles a sample, 37.0 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 1.00 | arith | `move a,b` at sh00+12 | `add x0,a` at sh00+11 |
| 1.00 | arith | `move a,x0` at sh00+16 | `mpy x0,y1,a` at sh00+15 |
| 1.00 | arith | `move a,y0` at sh00+20 | `add b,a` at sh00+19 |
| 1.00 | arith | `move a1,x1` at sh00+31 | `add b,a` at sh00+30 |
| 1.00 | arith | `move a,y0` at sh00+36 | `asl a` at sh00+35 |
| 1.00 | arith | `move b,y1` at sh02+8 | `mpy x0,x0,b` at sh02+7 |

**VERBERATION**, ROOM (def): 455.7 cycles a sample, 107.8 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.00 | agu | `lua (r5)+n5,r4` at gv_p2a+85 | `move x:(r7+$2e),n5` at gv_p2a+83 |
| 3.00 | agu-lua | `move y:(r4)-,b` at gv_p2a+86 | `lua (r5)+n5,r4` at gv_p2a+85 |
| 3.00 | agu | `move a,y:(r5+n5)` at gv_p2a+95 | `move #>$ffff9c,n5` at gv_p2a+93 |
| 3.00 | agu | `move y0,y:(r5+n5)` at gv_p2a+150 | `move x:(r7+$47),n5` at gv_p2a+148 |
| 3.00 | agu | `move y:(r5+n5),x0` at gv_p2a+153 | `move x:(r7+$48),n5` at gv_p2a+151 |
| 3.00 | agu | `move y:(r5+n5),x0` at gv_p2a+159 | `move #>$ffff94,n5` at gv_p2a+157 |

**VIBRATO**, SHP=TRI (max): 207.0 cycles a sample, 36.2 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 6.00 | agu | `move (r5)+n5` at vb_tap+14 | `move a1,n5` at vb_tap+13 |
| 3.00 | agu | `move (r5)+n5` at vb_mixd+37 | `move r2,r5` at vb_mixd+36 |
| 3.00 | agu | `move (r5)+n5` at vb_mixd+60 | `move r6,r5` at vb_mixd+59 |
| 2.00 | arith | `move a1,y1` at vb_tap+5 | `asl #$b,a,a` at vb_tap+4 |
| 2.00 | arith | `move a1,x0` at vb_tap+8 | `asr #$c,a,a` at vb_tap+7 |
| 2.00 | arith | `move a1,n5` at vb_tap+13 | `and #>$3ff,a` at vb_tap+11 |

**VOCODER**, INT (def): 1245.8 cycles a sample, 204.8 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 10.00 | arith | `sub a,b a,x:(r5)+` at vc_gend+133 | `macr x0,y1,a x:(r7),b` at vc_gend+132 |
| 10.00 | arith | `tfr y1,a b,y0` at vc_gend+135 | `macr -y1,x1,b` at vc_gend+134 |
| 10.00 | arith | `move a,y0` at vc_gend+137 | `macr y0,x0,a` at vc_gend+136 |
| 10.00 | arith | `sub a,b a,x:(r5)+` at vc_gend+143 | `macr x0,y1,a` at vc_gend+142 |
| 10.00 | arith | `tfr y1,a b,y0` at vc_gend+145 | `macr -y1,x1,b` at vc_gend+144 |
| 10.00 | arith | `abs a a,x:(r5)+` at vc_gend+147 | `macr y0,x0,a` at vc_gend+146 |

**VOID**, SHPE=SIN (dear): 503.9 cycles a sample, 62.4 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.00 | agu | `move (r0)+n0` at vd_bal+19 | `move #>$2,n0` at vd_bal+17 |
| 2.81 | agu | `move x:(r0),a` at vd_nbr_go+3 | `move #>$1,n0` at vd_bal+20 |
| 1.00 | transfer | `move a,x:(r7+$22)` at vd_nbr_go+4 | `move x:(r0),a` at vd_nbr_go+3 |
| 1.00 | transfer | `move a,x:(r7+$23)` at vd_nbr_go+6 | `move x:(r0+n0),a` at vd_nbr_go+5 |
| 1.00 | arith | `move b0,x0` at vd_have_in+5 | `asr b` at vd_have_in+4 |
| 1.00 | arith | `move b1,x:(r7+$1)` at vd_have_in+9 | `add #>$6ef35f,b` at vd_have_in+7 |

**BBD**, STGS=1024 (dear): 528.3 cycles a sample, 54.3 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.00 | agu-lua | `move x:(r1)+,x1 y:(r5)+,y0` at bbpreoff+6 | `lua (r2+$35),r5` at bbpreoff+5 |
| 3.00 | agu | `move x:(r1)+,x1 y:(r5)+,y0` at bbpreoff+118 | `move r2,r5` at bbpreoff+117 |
| 1.00 | arith | `move a,x0` at bbpreok+29 | `sub b,a` at bbpreok+28 |
| 1.00 | arith | `move b,x:(r7+$7)` at bbpreok+33 | `mac y0,x0,b` at bbpreok+32 |
| 1.00 | arith | `move a,x:(r7+$16)` at bbpreok+39 | `add b,a` at bbpreok+38 |
| 1.00 | arith | `move a0,x:(r7+$4d)` at bbhsec+12 | `add x,a` at bbhsec+11 |

**DISTORX**, RAT (min): 375.9 cycles a sample, 40.8 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 2.00 | agu | `move (r5)+n5` at dtx_rstage+135 | `move r4,r5` at dtx_rstage+133 |
| 1.00 | arith | `move a,x0` at dtx_rstage+4 | `asr #$1,a,a` at dtx_rstage+3 |
| 1.00 | arith | `move a,x1` at dtx_rstage+7 | `mpy x0,y1,a` at dtx_rstage+6 |
| 1.00 | arith | `move a1,x:(r7+$35)` at dtx_rstage+20 | `mac x1,y0,a` at dtx_rstage+19 |
| 1.00 | arith | `move a1,b` at dtx_rstage+29 | `mac x0,y1,a` at dtx_rstage+28 |
| 1.00 | arith | `move a,x0` at dtx_rstage+33 | `asr #$1,a,a` at dtx_rstage+32 |

**EUCLID**, RATE=1/32 (def): 232.3 cycles a sample, 25.2 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.00 | agu | `move (r0)+n0` at eu_den_held+126 | `move #>$2,n0` at eu_den_held+124 |
| 1.00 | arith | `move a,x:(r7+$2e)` at eu_type_done+18 | `add x0,a` at eu_type_done+17 |
| 1.00 | transfer | `move a,x:(r7+$1c)` at eu_den_held+3 | `move x:(r7+$2e),a` at eu_den_held+2 |
| 1.00 | arith | `move b,x0` at eu_den_held+14 | `asr #$3,b,b` at eu_den_held+13 |
| 1.00 | arith | `move a,x0` at eu_den_held+18 | `asl #$3,a,a` at eu_den_held+17 |
| 1.00 | arith | `move a,x1` at eu_den_held+25 | `add b,a` at eu_den_held+24 |

**LOFI2**, DOWN (max): 654.2 cycles a sample, 89.6 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.00 | agu | `move (r1)+n1` at lf_nomod+75 | `move r7,r1` at lf_nomod+74 |
| 3.00 | agu | `move (r2)+` at lf_nomod+77 | `move r1,r2` at lf_nomod+76 |
| 3.00 | agu | `move p:(r5),y0` at lf_noshift+75 | `move a1,r5` at lf_noshift+74 |
| 3.00 | agu | `move p:(r5),y0` at lf_noshift+82 | `move a1,r5` at lf_noshift+81 |
| 3.00 | agu | `move (r0)+n0` at lf_noshift+161 | `move #>$2,n0` at lf_noshift+159 |
| 2.81 | agu | `move x:(r0),x1` at lf_fwd+66 | `move #>$1,n0` at lf_noshift+162 |

**MINIVERB**, RATE=0.34 (max): 608.8 cycles a sample, 150.3 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.00 | agu | `move y:(r5+n5),b` at mv_mix+64 | `move #>$ffff8f,n5` at mv_mix+62 |
| 3.00 | agu | `move a,y:(r5+n5)` at mv_mix+71 | `move #>$0,n5` at mv_mix+69 |
| 3.00 | agu | `move y:(r5+n5),b` at mv_mix+77 | `move #>$fffee1,n5` at mv_mix+75 |
| 3.00 | agu | `move a,y:(r5+n5)` at mv_mix+84 | `move #>$ffff8e,n5` at mv_mix+82 |
| 3.00 | agu | `move y:(r5+n5),b` at mv_mix+90 | `move #>$fffd8f,n5` at mv_mix+88 |
| 3.00 | agu | `move a,y:(r5+n5)` at mv_mix+97 | `move #>$fffee0,n5` at mv_mix+95 |

**RESONATOR**, defaults (max): 655.9 cycles a sample, 82.6 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 8.00 | arith | `move a,x:(r4)+` at rs_one+5 | `add b,a` at rs_one+4 |
| 8.00 | arith | `move a,x0` at rs_one+14 | `sub b,a` at rs_one+13 |
| 8.00 | arith | `move a,x:(r4)+` at rs_one+18 | `add b,a` at rs_one+17 |
| 8.00 | arith | `move a,x0` at rs_one+22 | `mpy x0,y1,a` at rs_one+21 |
| 8.00 | arith | `move b,x:(r7+$58)` at rs_one+29 | `add a,b` at rs_one+28 |
| 3.00 | agu | `move (r3)+n3` at rs_fbd+47 | `move #$30,n3` at rs_fbd+46 |

**STUTTR**, FWD (dear): 268.4 cycles a sample, 20.6 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.00 | agu | `move y:(r4)+,a` at st25+3 | `move #>$ffffff,m4` at st25+1 |
| 2.00 | agu | `move a,y:(r4)+` at st50+35 | `move #>$ffffff,m4` at st50+32 |
| 1.00 | transfer | `move a,y:(r4)+` at st50+37 | `move x:(r0+n0),a` at st50+36 |
| 1.00 | arith | `move a,x:(r7+$2c)` at st03+13 | `sub #>$1,a` at st03+11 |
| 1.00 | transfer | `move a,x:(r7+$2f)` at st25+4 | `move y:(r4)+,a` at st25+3 |
| 1.00 | transfer | `move a,x:(r7+$30)` at st25+6 | `move y:(r4)+,a` at st25+5 |

**REVERB SERVER**, ROOM (min): 1593.1 cycles a sample, 261.9 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 8.00 | agu | `move y:(r5+n5),b` at lfrol+375 | `move y:(r6)+,n5` at lfrol+372 |
| 8.00 | arith | `move a,r5` at lfrol+378 | `add x0,a` at lfrol+377 |
| 8.00 | arith | `move a,x0` at lfrol+381 | `sub b,a b,y:(r6)+` at lfrol+380 |
| 8.00 | arith | `move a,x0` at lfrol+385 | `sub b,a` at lfrol+384 |
| 8.00 | arith | `move a,y:(r6)+` at lfrol+388 | `add b,a` at lfrol+387 |
| 8.00 | arith | `move a,x0` at lfrol+392 | `sub b,a` at lfrol+391 |

**DELAY SERVER**, GRAIN (min): 1966.2 cycles a sample, 256.2 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 12.00 | agu | `move y:(r5+n5),a` at proc+1117 | `move a1,r5` at proc+1116 |
| 12.00 | agu | `move y:(r5+n5),a` at proc+1214 | `move a1,r5` at proc+1213 |
| 8.00 | agu | `move y:(r5+n5),b` at proc+1111 | `move a1,r5` at proc+1109 |
| 8.00 | agu | `move y:(r5+n5),b` at proc+1208 | `move a1,r5` at proc+1206 |
| 6.00 | agu | `move y:(r5+n5),b` at proc+1409 | `move a1,r5` at proc+1408 |
| 6.00 | agu | `move y:(r5+n5),a` at proc+1414 | `move a1,r5` at proc+1413 |

**SEND**, defaults (def): 57.5 cycles a sample, 6.9 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 1.00 | arith | `move a,x:(r7+$15)` at proc+234 | `add x0,a` at proc+233 |
| 1.00 | arith | `move a,x0` at proc+240 | `asr #$1,a,a` at proc+239 |
| 1.00 | arith | `move a,y:(r2)+` at proc+245 | `add b,a` at proc+244 |
| 1.00 | arith | `move a,x:(r7+$17)` at proc+249 | `add y1,a` at proc+248 |
| 1.00 | arith | `move a,y:(r4)+` at proc+255 | `add b,a` at proc+254 |
| 0.12 | agu | `move a,y:(r3)` at proc+98 | `move #>$ffffff,m3` at proc+95 |

## 4. The stock effects

Their code is Elektron's and is not edited here; a detour could replace a
routine (`MODULES.md`). Stalls are small in most of them (4 to 35 cycles a
sample); `do`/`rep` (5 cycles a loop entered) is often the largest extra. One
pattern recurs: a two-instruction loop whose second instruction
(`mac -x1,y0,a`) writes A and whose first (`mac y1,y0,a a,x1 a,y:(r5)+n5`)
moves A on the next pass, one idle cycle a pass. DJ EQ, PLATE REV and DARK REV
share it at `P:0x9b5` (2.8 to 5.6 cycles a sample); EQUALIZER has its own at
`P:0xc22` and `P:0xc8a` (5.6 and 15).

**CHORUS**, TAPS=5 (def): 290.0 cycles a sample, 5.1 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 0.62 | transfer | `mac x0,y1,b b,y0` at proc+82 | `move x:(r3+$3),b` at proc+81 |
| 0.62 | arith | `move b,x:(r3+$3)` at proc+84 | `mac -y1,y0,b a,y0` at proc+83 |
| 0.62 | transfer | `mac y1,y0,b b,y0` at proc+86 | `move x:(r3),b` at proc+85 |
| 0.62 | agu | `move x:(r1)+,x1 y:(r5)+,y1` at proc+173 | `move r1,r5` at proc+170 |

**COMB FILTER**, defaults (def): 130.0 cycles a sample, 20.2 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.00 | agu | `lua (r6)+n6,r4` at proc+204 | `move x:(r2)+,n6` at proc+203 |
| 3.00 | agu-lua | `move (r4)+n4` at proc+205 | `lua (r6)+n6,r4` at proc+204 |
| 3.00 | agu | `move (r4)+n4` at proc+231 | `move r6,r4` at proc+230 |
| 1.00 | arith | `move a0,b` at proc+110 | `mpyi #>$1000,x0,a` at proc+108 |

**COMPRESSOR**, defaults (def): 103.1 cycles a sample, 10.4 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 2.00 | agu | `move x:(r1+$6c00),b0` at proc+41 | `move a1,r1` at proc+39 |
| 2.00 | agu | `move x:(r2+$7400),a` at proc+69 | `move a,r2` at proc+67 |
| 1.00 | arith | `move a,l:(r5)+` at proc+23 | `mac -y0,x0,a y:(r4)+,y0` at proc+22 |
| 1.00 | arith | `move a1,x0` at proc+36 | `normf b1,a` at proc+35 |

**DARK REV**, MIXF=SEND (def): 253.5 cycles a sample, 14.7 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 5.62 | arith | `mac y1,y0,a a,x1 a,y:(r5)+n5` at P:9b5 | `mac -x1,y0,a` at P:9b6 |
| 3.50 | arith | `tfr y0,a b,x0 b,y:(r4)+` at proc+320 | `mac y1,y0,b a,x:(r1)+` at proc+323 |
| 1.50 | arith | `move b,x:(r3)+` at P:15a1 | `mac -y0,x0,b x:(r1)+,x0` at P:15a0 |
| 0.38 | arith | `move a,x:(r1)+` at P:9b7 | `mac -x1,y0,a` at P:9b6 |

**DJ EQ**, defaults (def): 334.5 cycles a sample, 4.9 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 2.81 | arith | `mac y1,y0,a a,x1 a,y:(r5)+n5` at P:9b5 | `mac -x1,y0,a` at P:9b6 |
| 0.56 | agu | `move (r0)+n0` at proc+309 | `move r3,r0` at proc+306 |
| 0.56 | agu | `move (r0)+n0` at proc+314 | `move r3,r0` at proc+311 |
| 0.50 | arith | `mpy x0,y1,b a,y:(r4)+` at proc+297 | `mpy y1,x1,a` at proc+296 |

**EQUALIZER**, TYP1=HIGH (max): 191.1 cycles a sample, 26.7 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 15.00 | arith | `mac y1,y0,a a,x1 a,y:(r5)+n5` at proc+216 | `mac -x1,y0,a` at proc+217 |
| 5.62 | arith | `mac y1,y0,a a,x1 a,y:(r5)+n5` at proc+112 | `mac -x1,y0,a` at proc+113 |
| 3.75 | arith | `mpy -x0,y1,b a,x:(r0)+n0 b,y0` at proc+267 | `asl #$4,a,a` at proc+274 |
| 0.38 | agu | `move x:(r3+$15c7),a` at proc+91 | `move a,r3` at proc+90 |

**FILTER**, HP=12dB (max): 280.1 cycles a sample, 11.1 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 1.00 | arith | `mpy y0,x0,a b,x1` at proc+384 | `mpy x0,x0,b x0,y1` at proc+383 |
| 1.00 | arith | `asl a b,x0` at proc+386 | `mpy x1,x0,b y:(r5)+,y0` at proc+385 |
| 1.00 | arith | `move b,x0 y:(r5)+,y0` at proc+389 | `mpy x1,x0,b y:(r5)+,x1` at proc+388 |
| 1.00 | arith | `mpy y0,x0,a b,x1` at proc+400 | `mpy x0,x0,b x0,y1` at proc+399 |

**FLANGER**, defaults (def): 148.6 cycles a sample, 12.3 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 3.75 | agu-lua | `move x:(r2)+,x0 y:(r4)+,y0` at proc+210 | `lua (r0)+n0,r4` at proc+216 |
| 2.00 | arith | `move b,y:(r0)+n0` at proc+245 | `mac y1,x1,b` at proc+244 |
| 1.00 | arith | `lsr b a1,y:(r4)+` at proc+78 | `lsr a y:(r4)-,b1` at proc+77 |
| 1.00 | arith | `move b1,y:(r4)+` at proc+79 | `lsr b a1,y:(r4)+` at proc+78 |

**LO-FI**, defaults (def): 305.9 cycles a sample, 15.8 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 4.00 | arith | `mpy y0,x0,a b,x1` at proc+87 | `mpy x0,x0,b x0,y1` at proc+86 |
| 4.00 | arith | `asl a b,x0` at proc+89 | `mpy x1,x0,b y:(r5)+,y0` at proc+88 |
| 4.00 | arith | `move b,x0 y:(r5)+,y0` at proc+92 | `mpy x1,x0,b y:(r5)+,x1` at proc+91 |
| 2.00 | arith | `move a,x1 y:(r4)+,y0` at proc+318 | `rnd a y:(r4)+,y1` at proc+317 |

**PHASER**, NUM=10 (def): 240.8 cycles a sample, 29.2 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 2.00 | agu-lua | `move x:(r0)+,x0 y:(r4)+,y0` at proc+82 | `lua (r7+$24),r0` at proc+80 |
| 2.00 | arith | `move a,y:(r5)+` at proc+91 | `sub y1,a x:(r0)+,x0` at proc+90 |
| 2.00 | arith | `mpy y1,x1,a b,x1 y:(r6)-,y1` at proc+137 | `add x0,b x:(r2)+,x1 y:(r6)+,y1` at proc+136 |
| 2.00 | arith | `mpy y1,x1,b a,x1 y:(r6)+,y1` at proc+140 | `mac -x1,y0,a b,x:(r3)+ y:(r6)+,y1` at proc+139 |

**PLATE REV**, MIXF=SEND (min): 246.9 cycles a sample, 34.5 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 6.00 | arith | `move b,y:(r5)+` at proc+354 | `mac y0,x0,b` at proc+353 |
| 5.62 | arith | `mac y1,y0,a a,x1 a,y:(r5)+n5` at P:9b5 | `mac -x1,y0,a` at P:9b6 |
| 4.69 | arith | `tfr y0,a b,x0 b,y:(r4)+` at proc+114 | `mac y1,y0,b a,x:(r1)+` at proc+117 |
| 3.75 | arith | `mac y0,x0,a a,x:(r1)+ a,y1` at proc+250 | `mac -x0,y1,a y:(r4)+,y0` at proc+251 |

**SPATIALIZER**, PHSE=L,R (max): 82.1 cycles a sample, 3.7 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 1.00 | arith | `move b,x0` at proc+92 | `mac -y1,x1,b a,x1` at proc+91 |
| 1.00 | arith | `mpy y1,x1,b a,x:(r3)+` at proc+150 | `mpy y1,x1,a x:(r5)-,x1 b,y1` at proc+149 |
| 1.00 | arith | `move b,x:(r3)+` at proc+151 | `mpy y1,x1,b a,x:(r3)+` at proc+150 |
| 0.19 | agu | `move x:(r2+$520),a` at proc+168 | `move b,r2` at proc+167 |

**SPRING REV**, TYPE=1 (def): 293.1 cycles a sample, 5.9 of them stalls.

| stall/sample | kind | the instruction that waits | waits on |
|---|---|---|---|
| 2.81 | arith | `mac y1,y0,a a,x1 a,y:(r5)+n5` at P:9b5 | `mac -x1,y0,a` at P:9b6 |
| 1.50 | arith | `move b,x:(r3)+` at proc+739 | `mac -y0,x0,b x:(r1)+,x0` at proc+738 |
| 0.25 | arith | `move a,x:(r0)+ a,y:(r5)+` at proc+316 | `mac -x1,y0,a x:(r2)+,x1 y:(r4)+,y0` at proc+315 |
| 0.19 | agu | `move (r1)-n1` at proc+948 | `move #$6c,n1` at proc+945 |

## 5. Not scanned

- **Frame hooks** (LOAD METER, FRAME GUARD, the demand loader's copier, STEM
  REC's DSP hook, SIDECHAIN_COMPRESSOR's hooks): no effect entry to call. The
  scan traces an effect's proc.
- **The probes** (CF METER, DLPROBE, EXTPROBE, PEXT PROBE, TESTGEN): diagnostics.
- **DELAY and TAPE ECHO**: they run on the ColdFire; their DSP entry is the
  passthrough stub (TAPE ECHO's measures 1.1 instructions a sample).
- **DEVILISH**: a voice of OCTA303; with nothing triggering it, its proc returns
  at once (1.1 instructions a sample). A trace with a voice playing needs the
  port, not `dsp_host`.
- **MULTIBCOMP**: 4.2 instructions a sample, a stub path in the stock image.

## 6. What the scan cannot see

- **The window's wait state and contention** (section 1).
- **One block.** An effect whose work changes over time (STUTTR's buffer
  state, a slow LFO's table steps) is priced at block 263. `dsp_host`'s
  `-diff` picks the traced block; scanning more blocks is a loop around the
  tool.
- **The dispatcher.** `dsp_host` calls the effect through the harness's model
  of the calling convention (`tools/harness/README.md`); the stock dispatcher's
  own work around a call is in the unit's figures and not here.
- **Interrupts.** The frame interrupt and the host commands run between
  instructions on the chip.
- **Knob paths the sweep does not visit.** Three variants a selector value;
  a module with several selects (DEVILISH, VOCODER) has combinations no run
  took.
