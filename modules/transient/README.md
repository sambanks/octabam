# `transient` -- TRANSIENT

A transient shaper: ATCK boosts or softens each onset, SUST lengthens or tightens each tail.

On the unit it is an FX2 effect with five knobs on page 1. Turn ATCK up for more punch on drums and plucks, down to soften them; turn SUST up for more room and ring, down to dry a loop out. It has no threshold: the same setting does the same thing to a quiet hit and a loud one, because the detector measures the shape of the envelope in log2 units, not its level. No lookahead, no buffers. The law and the reasoning behind each choice are in [`DESIGN.md`](DESIGN.md); [`transient_ref.py`](transient_ref.py) is the float reference the DSP is proved against.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | ATCK | -64..+63 | onset gain: up to +12 dB at +63, -12 dB at -64; 0 untouched |
| 1 | 1 | SUST | -64..+63 | tail gain: up to +12 dB at +63, -12 dB at -64; 0 untouched |
| 1 | 2 | TIME | 0-127 | how long an onset counts as the transient: 5 ms at 0, 50 ms at 127 (logarithmic); default 40 |
| 1 | 3 | OUT | -64..+63 | output trim, -12 to +12 dB |
| 1 | 4 | MIX | 0-127 | dry/wet; 0 is an exact passthrough, 127 full wet |

ATCK and SUST together are clamped to ±12 dB; OUT adds up to a further ±12 dB.

## Measured

- **19 Nov 2026, the constants pass** (bit-identical: `verify_ident.py` with
  the wider matrix of sambanks/octabam#1172 (the module's own slot, payload B,
  16-sample blocks, a 2 s run, a knob ramp, stereo, the split call, the
  manifest's `dear` settings, and the r7 state after every block), IDENTICAL
  after each commit; 27 renders). Cycles a sample from
  `tools/build/interlock_scan.py` (the core manual's cycle table and stalls: a
  model, on average 3.0 % above the unit, `docs/contributing/CYCLE_SCAN.md`
  section 1): **270.0 → 267.9** at its defaults (6.0 % → 5.9 % of a frame).
  Words 258 → 254 (`dsp_asm` at P:$800). Not measured on the unit. Four
  constants load as one-word short immediates.

All by `tools/verify/verify_transient.py` through `dsp_host` on the audition's scratch image, 3 Oct 2026, unless stated.

- ✅ Defaults (ATCK = SUST = OUT = 0, MIX 127) are a bit-exact passthrough of a full-scale bipolar ramp and of full-scale noise. Falsified by any differing sample.
- ✅ MIX 0 is a bit-exact passthrough with ATCK, SUST and OUT at their extremes.
- ✅ The per-sample gain on a 1 kHz tone burst (1 ms rise, 150 ms decay, -20 dBFS) matches the float reference within 0.062 dB for ATCK ±max, SUST ±max and ATCK max with TIME 127 (peak gains +11.87 to +12.05 dB). Samples below -60 dBFS are not compared.
- ✅ Level independence: the same burst on a noise bed scaled with it (-40 dB re the burst), at -18, -33 and -48 dBFS, gets the same gain within 0.028 dB. The float reference gives 0.0066 dB; from digital silence it gives 0.17 dB after the first millisecond, a property of a log-domain detector rising out of its -96 dBFS floor.
- ✅ A settled 1 kHz sine at -6 dBFS with ATCK and SUST at max is held at a constant +0.13 dB (no pumping; the float reference gives +0.11 dB).
- ✅ No sustain spike: with SUST +63 a hit 9 dB above a louder hit's tail keeps its onset peak (+0.00 dB). Law v1 raised it by up to +12 dB; DESIGN.md has the history.
- ✅ No clicks: with SUST +63 a decaying noise tail's gain steps by at most 0.05 dB between samples (law v2 stepped by up to 12 dB).
- 🟡 A hit less than 3 dB above the tail it lands in, or a sine's first quarter cycle below the tail's envelope, shares the tail's boost (+11.3 and +8.3 dB in the gate's synthetic cases; reported, not gated).
- ✅ A negated input gives the negated output within 3 LSB (two truncations in the output path; an `mpysu` on a negative operand would be off by millions).
- ✅ 184 cycles/sample (`make cycles REMIX=transient`), branch-free, so the word span is the cost; four instances on one core price at 736 of 4,535.
- ✅ The `clb`/`normf` pair that takes the log is the form Elektron's own payloads use (`clb b,a` / `normf a1,b`, three sites each on payloads A and B; `out/dsp/payload_*.asm`).
- ✅ Under the ColdFire port in a real project (`verify_set`, `OT_PROJECT`, 3 Oct 2026): a project made on a MKII on stock 1.40C (T1 THRU, T2 STATIC with trigs), TRANSIENT put on T2's FX2 in every part of every bank with `ot_project.py set-fx` (ATCK 127). LOAD PROJECT completed and 900 frames ran; the live FX2 id on T2 read 0x0f; T2's chain carried audio (in -41.7, out -43.0 dB, the whole chain); the load rewrote no project file; every shared-window DSP write lay in a permitted range. This proves the module loads and runs in a project on the emulated firmware, not how it sounds.
- 🟡 Above full scale the output clips at the limiting store, and the half-scaled `(wet - dry)` limits once the wet is more than 6 dB over full scale. Not measured beyond that the float reference does not model clipping.

## On the unit

- ✅ Image OCTABAM2 (`make image REMIX=transient BUILD=2` at `f6ce41d6`, TRANSIENT beside 13 stock effects) on Ignorato's MKII, 3 Oct 2026, from the card: boots, OS VERSION reads OCTABAM2; TRANSIENT is listed on FX2 (then as `Transient2`; now `TRANSIENT`, no build tag) and runs on T2 of a project made on the unit on stock 1.40C. ATCK works as expected across its range on a kick (PML_MHE_Kick_001) and a clap (PML_MHE_Clap_004). SUST works as expected on the clap, with no added noise.
- ✅ Image OCTABAM3 (`make image REMIX=transient BUILD=3`, the name in capitals, no build tag), same unit and day: boots, OS VERSION reads OCTABAM3, the FX2 list shows `TRANSIENT`, and T2 keeps it with its knobs; all works (tester).
- ✅ The LFO page lists TRANSIENT's destinations under TRNS as ATCK, SUST, TIME, OUT, MIX and `<F>`: page-1 slot 5 is unnamed (six zero bytes in the descriptor) and the firmware labels an unnamed slot by its letter, as it does stock DJ EQ's empty slot 2 (`<B>`, seen on the same unit). Modulating `<F>` does nothing: the DSP reads knob words 0 to 4 only.
- 🟡 With the kick at SUST about +20, a slight white noise was heard. Not reproduced by `dsp_host` (the sample fades to digital zero; the gaps between hits render as silence at every SUST setting). Judged by the tester to be an artefact of that sample; cause not measured. An output capture would tell whether the unit feeds FX2 a low residual between hits, which SUST lifts most there.
- Listened to before flashing (3 Oct 2026): level-matched renders of a 110 BPM drum loop through this DSP code in `dsp_host`; SUST +63 clean after law v3 (v1 spiked, v2 clicked).

## Open

- Voicing beyond one drum loop: the constants (0.5 ms, 50 ms, 500 ms, 10 ms peak release, ±2 bits, the 3 dB onset margin) are first choices.
- Whether 2 bits (12 dB) is the right ATCK/SUST range.
- A gate under the port that measures TRANSIENT's own gain law in a project (today the port proves it loads and passes audio; the law is proved by `dsp_host`).

## Gates

- `tools/verify/verify_transient.py` (the manifest's `Gate`): bit-exact passthroughs, both signs, the law against `transient_ref.py`, level independence, a steady tone, every knob at both ends. It refuses to run if the id resolves to SEND's entry points.
- `make check REMIX=transient`; with `OT_PROJECT=<a project>` it adds `verify_set` under the ColdFire port.

## Design

[`DESIGN.md`](DESIGN.md): the law, why the peak detector and the S lag cap are there (each fixed a defect the float reference found), the r7 slots, the tables.
