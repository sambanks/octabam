# ColdFire scan: where the ColdFire's time goes

Three tools answer three questions about a module's ColdFire code:

- **Where does the time go?** `tools/build/cf_scan.py profile` attributes
  every instruction the port ran to the module that owns it, and to the
  interrupt level it ran at.
- **What does a routine cost?** `tools/build/cf_scan.py price` prices one
  routine's executed instructions in V4 core cycles, from the processor's
  manual.
- **Did a change leave the output alone?** `tools/verify/verify_cf_ident.py`
  runs two images on one staged card and compares what a listener and a MIDI
  device receive.

`cf_scan.py c07` also finds one common saving in the sources: a zero or sign
extension written as two instructions.

These tools are for a change that should make code cheaper and leave its
output as it was. A change that is meant to sound different needs its
module's own gates instead.

## Where the time goes: `profile`

```bash
make bus REMIX=octabam > out/bus.log
OT_PROFILE_LEVELS=out/levels.txt out/emu/ot_emu --image out/mainos_bus.bin --card CARD.img \
    --set OCTABAM --project PROF --sequencer --internal-clock --frames 2000 \
    --load-ms 90000 --dsp --coverage out/coverage.txt
python3 tools/build/cf_scan.py profile out/levels.txt --frames 2000 --build-log out/bus.log
```

`OT_PROFILE_LEVELS=FILE` makes the port write every PC it sampled with the SR
interrupt mask the instruction ran at, one `addr mask count` line each. With
`--coverage` the port samples every instruction from the transport start, so
the counts are exact. With `--profile` it samples every 64th instruction from
boot.

`profile` reads the build's runtime map and `layout.json` to name the module
that owns each runtime address. With `--build-log` (the output of `make bus`)
it also names the ROM caves. Every other address is stock. The frame
interrupt's own routine (`0x4000aad0..0x4000d9b0`) is reported apart as
`stock: frame ISR`.

How to read it:

- **Counts are instructions.** Divide by `--frames` for instructions a frame.
  A frame is 362.8 µs (16 samples at 44.1 kHz).
- **The mask says who ran the code.** Mask 0 is task code. The frame
  interrupt's handler runs at mask 5, and so does every module it calls: the
  modules at mask 5 are the ones that cost time in every frame.
- **Use the platform of the image that ran.** The ranges and the symbols are
  one build's. `--platform DIR` takes a saved copy of `out/platform`.

## What a routine costs: `price`

```bash
python3 tools/build/cf_scan.py price out/coverage.txt o3_render --frames 2000
python3 tools/build/cf_scan.py price out/coverage.txt o3_render --frames 2000 --detail
python3 tools/build/cf_scan.py --selftest
```

`price` disassembles one runtime routine (to the next symbol) and prices each
executed instruction:

- **The instruction's own time.** MCF54455RM section 3.3.5, Tables 3-13 to
  3-20, for its mnemonic and addressing modes (`tools/build/cf_timing.py`).
  `nop` costs 6 cycles, `tpf` 1. A call through a register costs 5, an
  absolute call 1. A move to MACSR costs 8.
- **The address-use stall.** A register that one instruction writes and the
  next one uses as a base or an index costs 2 more cycles, or 3 for an index
  scaled by 2 or 4 (section 3.3.5.1). A post-increment's or pre-decrement's
  own result does not stall.
- **The accumulator stall.** Storing an EMAC accumulator right after a MAC
  costs 3 more cycles, 2 with one instruction between, 1 with two (the note
  under Table 3-18).

The total is cycles from the tables plus the stalls. `--detail` prints every
executed instruction with its count, its cycles and its stall.

What the price leaves out:

- **Memory.** Every access is a cache hit. A line fill from SDRAM, a store
  through the uncached alias at `0x48000000` and up (at least 6 cycles each),
  and a peripheral access all cost more on the unit.
- **Branch prediction.** Every branch is predicted and every `rts` hits the
  return stack. A mispredicted branch costs 8 cycles more on the unit.
- **The address ALU.** The manual says the core can forward the results of
  some common instructions with no stall, and does not say which. The model
  charges the stall for every register write, so the stall part can be high.

So the price is good for comparing two versions of the same routine. It is
not a measurement of the unit. Its cycles are an estimate from the manual,
not yet checked against the unit.

## Did a change leave the output alone: `verify_cf_ident.py`

```bash
python3 tools/verify/verify_cf_ident.py out/base.bin out/cand.bin CARD.img --frames 2000
python3 tools/verify/verify_cf_ident.py --self out/base.bin CARD.img --frames 2000    # the control
python3 tools/verify/verify_cf_ident.py out/base.bin out/cand.bin CARD.img --live-script keys.txt
```

Build the image before the change and after it (`make bus`, then copy
`out/mainos_bus.bin`). The script boots each image on a copy of the card, loads
the project and runs the scenario: N frames of the internal clock from the
transport start, or a live script. It keeps both DSP cores' outputs and the
MIDI output, and compares them.

| Verdict | Meaning | Exit |
|---|---|---|
| IDENTICAL | every file is byte for byte the same | 0 |
| EQUAL UP TO TIME SHIFTS | every audio channel is the same once shifted; the MIDI is byte for byte the same | 0 |
| CONTENT DIFFERS | a stretch of some channel no shift explains, or different MIDI | 1 |
| FAIL | a run did not load its project or wrote no audio | 2 |

**Why shifts are allowed.** The port runs the DSP in step with the
ColdFire's instructions. Code that runs fewer instructions moves an outside
event, such as the transport start, by a few samples. An event that lands
between two slots of the frame moves the slots by different amounts, so the
script aligns each channel on its own. It reports every re-alignment. A
shift larger than `--max-shift` (256 samples) counts as a difference.

**The control.** `--self` runs one image against itself. It must be
IDENTICAL; if it is not, the port is not deterministic for that scenario and
no verdict on a change can be trusted.

What it cannot see:

- state that never reaches the audio or the MIDI within the run;
- a path the scenario does not take, so choose a scenario that runs the
  changed code (a profile of the candidate shows whether it ran);
- the unit's timing, since the port is not cycle-exact.

## One saving the sources show: `c07`

```bash
python3 tools/build/cf_scan.py c07 modules/load-meter modules/scenes-p2
```

The V4 core runs `mvz` and `mvs` (zero and sign extension of a byte or a
word), so several two-instruction forms are one instruction, 2 bytes shorter:

| Shape | Two instructions | One instruction |
|---|---|---|
| Z1 | `moveq #0,Dn` or `clr.l Dn`, then `move.b <ea>,Dn` | `mvz.b <ea>,Dn` |
| Z2 | `move.b <ea>,Dn`, then `and.l #0xff,Dn` | `mvz.b <ea>,Dn` |
| S1 | `move.b <ea>,Dn`, then `extb.l Dn` | `mvs.b <ea>,Dn` |
| S2 | `move.w <ea>,Dn`, then `ext.l Dn` | `mvs.w <ea>,Dn` |

(The word forms of Z1 and Z2, with `move.w` and `#0xffff`, become `mvz.w`.)

The register ends up the same. The flags can differ in one case:

- In Z1, `move.b` sets N from the byte's top bit, and `mvz` always clears N.
  Z, V and C are the same.
- In Z2, S1 and S2, the second instruction already sets the flags from the
  whole long, as `mvz` and `mvs` do. These shapes are always exact.

So `c07` marks a Z1 site SAFE when the next instruction that touches the
flags sets them itself, or reads only Z or C (`beq`, `bne`, `bhi`, `bls`,
`bcc`, `bcs`). It marks the site REVIEW when a label, a call or a branch on N
comes first: read the code that follows before changing it.

After the change, `python3 tools/verify/verify_cf_forms.py <remix>` reports
any form that stock code never runs. Stock runs the common `mvz` and `mvs`
forms; `mvz.b #imm` is one it does not.
