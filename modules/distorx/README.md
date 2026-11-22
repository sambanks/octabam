# `distorx` — DISTORX

Two pedals in one insert: the BOSS SD-1 Super OverDrive (1981) and the
Pro Co RAT (1978), with the Turbo RAT's LEDs as a third MODE. MODE picks
the pedal; changing it fades to the dry signal and back in about 3 ms, so a
scene or a p-lock can switch pedals without a click. Built for a TB-303
line (OCTA303), fine on anything.

Author: MaMarko (Marko Brajković, [braikomarko-hub](https://github.com/braikomarko-hub)): the idea, the listening and the tests on the unit.
**The code was written by Claude (Anthropic)**: engine, calibration, integration and gates.

> **T1:** v7 tore track 1's read-back block under load (16-sample bursts of junk, "On the unit").
> v9, a quarter lighter and without PAD, played clean on T1 on the owner's MK1 (20 Oct 2026,
> "On the unit (v9)"): one session so far. If junk returns on T1, report it with the load.

**MODE starts at OFF** (v8): nothing runs and the frames pass untouched, so
DISTORX can be put on a track in the middle of a set and a pedal faded in
when wanted.

**FX id `0x1b`** (28 Oct 2026): a free id; stock SPATIALIZER keeps `0x05`. From
22 Oct to 28 Oct 2026 DISTORX held `0x05` with `replaces="SPATIALIZER"` (image
DTXPR3), and before that `0x1b` (until 20 Oct) and `0x0a` (DTXPR1, 21 Oct). A
part saved on one of those ids needs DISTORX chosen again. A part saved before v8
reads its MODE one step lower: SD-1 → OFF, RAT → SD-1, TURB → RAT.

**Beside the other drives in octabam:** CHARACTER's SAT (TAPE / TUBE / INFL,
JClones' models) is a saturation stage inside an FX1 station; SHATTER is a
crush insert (fold, clip, bit and rate crush, feedback). DISTORX is two
specific pedals modelled from their part values, with their tone controls,
as one FX1/FX2 insert. It declares SHATTER a conflict: both are per-track
dirt inserts, one is enough in a remix.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | LEVL | 0–127, default 64 | LEVEL, linear; 64 ≈ the input's loudness at DRIV 64 in every MODE (the RAT's make-up below) |
| 1 | 1 | TONE | 0–127, default 64 | SD-1: TONE. RAT: FILTER, **turned round**: right is bright in every MODE (the real FILTER darkens clockwise) |
| 1 | 2 | DRIV | 0–127, default 64 | SD-1: DRIVE, 18–47 dB. RAT: DISTORTION, the 100k-A pot: 0–67 dB |
| 1 | 3 | IN | bipolar, default 64 | how hard the track hits the pedal: −12 … +12 dB; 0 dBFS = 1 V at the jack |
| 1 | 4 | MIX | 0–127, default 127 | dry/wet: 127 is the pedal alone, 0 an exact passthrough |
| 1 | 5 | MODE | OFF / SD-1 / RAT / TURB | OFF (default: nothing runs) or the pedal (a value past TURB, as an LFO can send, reads as TURB) |

## The SD-1 (MODE 1)

From the BOSS service notes' parts list (the constants are in
`manifest.py`, computed from the part values):

| stage | parts | as computed |
|---|---|---|
| input couplings | C1 47 n, R2 470 k; C2 18 n, R4 100 k | HP 7.2 Hz; HP 88 Hz into IC1a |
| clipping stage | DRIVE VR1 1 M (B) + R5 33 k, the gain leg R6 4.7 k + C3 47 n; the 1S2473 diodes in the feedback, one on the negative side and two in series on the positive | the non-inverting gain (18–47 dB with DRIVE) with the 720 Hz leg; the diode law solved exactly (Wright omega, tabulated), so the clip is asymmetric, as on the pedal; the op-amp's swing ±3.3 V |
| TONE stage | VR3 20 k ("W"), R7 10 k, C4 18 n, C5 27 n, R8 470 Ω, R9 10 k, C6 10 n | the stage by nodal analysis; its coefficients as quadratics in the knob (a P table the decode loops over) |
| output | C7 1 µ, R10 4.7 k, LEVEL VR2 10 k (B) | HP 10.8 Hz into LEVEL, +3 dB of make-up |

Until v8 the clipper ran at 2× through 11-tap halfbands; since v8 it runs
at 1× ("v8" below).

## The RAT (MODES 2 and 3)

Modelled from the parts list and schematic of ElectroSmash's *Pro Co Rat
Analysis*:

| stage | parts | as computed |
|---|---|---|
| input coupling | C1 22 n, R2 1 M | HP 7.2 Hz, at 1×, a 48-bit state |
| — | R3 1 k, C2 1 n | 159 kHz: left out (−0.07 dB at 20 kHz) |
| LM308 stage | DISTORTION ‖ C4, R4 + C5, R5 + C6, C3 30 p | v− = q vo + c0 from the two ground legs (trapezoidal companions, exact); the op-amp an integrator of 0.8 MHz gain-bandwidth, trapezoidal where it is not stiff (θ-method: θ = ½, raised only where the closed loop's own pole is stiff, at DISTORTION near 0), the step held to the slew rate (0.3 V/µs), the output to ±3.5 V |
| clipper node | C7 4.7 µ, R6 1 k, D1/D2 to ground, FILTER + R7 1.5 k, C8 3.3 n, C9 22 n into R8 1 M | one node: v + Rp·Is(e^(v/N) − 1) = u per side, solved exactly — v = u + N k − N ω(U), U = u/N + k + ln k (ω the Wright omega, tabulated: 113 words, 16 segments an octave of U + 12); the FILTER network the node's load, C9/R8 included |
| output | the JFET (unity), C10 1 µ into VOLUME 100 k | HP 1.6 Hz, at 1×, a 48-bit state; then LEVEL × the make-up |

The LM308 stage and the clipper node run at 1×, one straight-line callee
called once a sample. (Until 15 Oct 2026 they ran at 2× through 11-tap
halfbands; on the MK1 that cost too much on core 1, "On the unit".
The owner A/B'd the two by ear, "almost imperceptible", and chose 1×.) At
1× the integrator's W is ~114 and the slew ~6.8 V a sample: W is applied as
W/128 with one more shift, and the slew compares the step at volts/8.

**TURBO** is the same circuit with red LEDs for D1/D2 (the LTspice
`LedRed` model: Is = 93.2 pA, n = 3.73; about 1.6 V at 1 mA).

## Assumptions

What the analysis does not give, and what was chosen:

- **LM308 gain-bandwidth 0.8 MHz**, fitted to the analysis's own clipping
  amplifier curve: 64.4 dB at 714 Hz at full DISTORTION (the curve: ~64 dB
  near 700 Hz), 37.9 dB at 10 kHz (37.5), 31.9 at 20 kHz (31); the 1 k curve
  24.7 dB at 1.5 kHz (24) and 8.2 dB at 60 Hz (8). The datasheet gives no
  number in text.
- **Slew rate 0.3 V/µs** (the analysis, from the datasheet's figure).
- **Output swing ±3.5 V** around the 4.5 V bias (the datasheet's typical
  1 V short of each rail at ±15 V).
- **C4 left out.** With the gain-bandwidth modelled, C4 (100 p across
  DISTORTION) moves the clipping amplifier's response by at most 0.5 dB
  (1 kHz, full DISTORTION) and 0.2 dB above 5 kHz; leaving it out drops a
  state and a division.
- **The derivative held in a word**: the integrator's slope from the last
  sample is stored as a word (±4 V a sample) instead of clamped to the slew;
  the float circuit clamps it, and the two differ by −57 … −82 dB.
- **1N914** as the SD-1's 1N4148/1S2473 model (Is = 2.52 nA, n = 1.752).
- **Pots**: DISTORTION, FILTER (and VOLUME) are 100k-A: an exponential law
  through 0, 10 % at the middle and 1 (33 points, interpolated).
- **The JFET buffer is unity** (a source follower with R9 10 k).
- **Make-up after LEVEL**: 0.51 (RAT), 0.20 (TURBO), so that the three
  modes meet at the same loudness at the default knobs on an acid line
  (−16.5 … −17.3 dBFS RMS). The real Turbo RAT is louder than the RAT; here
  it is not, so a MODE change does not jump in level.

## The MODE fade

d ∈ [−1, 0] steps 1/128 a sample: towards −1 while the knob asks for
another pedal, towards 0 otherwise; MIX is multiplied by (1 + d), exactly
MIX when d = 0. At d = −1 with the knob on another pedal the block zeroes
every state slot ($12..$3c) and the new pedal starts from rest. So a MODE
change is 2.9 ms out to the dry signal, the switch, 2.9 ms back in; with
MIX at 127 the dry signal is heard for those few milliseconds. The effect
starts the same way: d = −1 at init, so it fades in.

## Silence

Silence in, exact zeros out after 100 ms, every MODE. After a loud burst
the SD-1 is back to exact zeros within 0.5 s. The RAT keeps a charge on C7,
which only the diodes can bleed off (C8 and C9 block every other path, as on
the pedal): its slow, subsonic relaxation reaches the output through the
1.6 Hz HP at −95 dBFS after 2 s and about −118 dBFS after 10 s.

## Where it goes

Since v10 (below) DISTORX is 1,629 words: 1,114 of code and the 515-word P
table, still one code stream, so it needs ONE harvested run that long.
(The 1,586 of v7 and the 1,548 of v9 are in "Measured" and "v9".)
CHORUS + PLATE REV + SPRING REV is 1,743 words up to the 35 SPRING REV words
DARK REV still calls (P:0x01586), which cut the run there: DISTORX fits with
114 to spare (v9: 195). A remix that keeps DARK REV and also places another
module of more than 114 words gives up a second, separate run for it.
`make check REMIX=distorx` is what places it; v10's size was counted from
the assembled file, not placed (no stock image where it was written).
aCiDtRacK gives up PHASER: its 207 words join EQUALIZER's 282 (dB666 is on
EQUALIZER's id) into 489, where dB666 (297 + 66 words) goes.

## v8 (18 Oct 2026): lighter, for T1

T1's junk blocks ("On the unit") come when DISTORX ends late in core 1's
frame. v8 makes every MODE end earlier
and adds OFF. Instructions per 16-sample block in `dsp_host` (the owner's
audition dump with v8's code in it, an acid line, the default knobs):

| | v7 (ACIDV68) | v8, knobs still | v8, knobs moving | v8, the fade-in's blocks |
|---|---|---|---|---|
| OFF | — | 29 | 29 | — |
| SD-1 | 5,483 | 2,709 | 2,939 | 3,184 (the first 3,464) |
| RAT / TURBO | 4,540 | 3,801 | 4,140 | 4,276 (the first 4,665) |

What changed:

- **OFF**, MODE 0 and the default: the block returns after the MODE logic;
  the frames, processed in place, pass untouched. Leaving a pedal for OFF
  fades it out (2.9 ms) and then stops; leaving OFF for a pedal switches it
  in from rest and fades it in (2.9 ms), as any MODE change.
- **The SD-1 at 1×.** The clipper ran at 2× through 11-tap
  halfbands, with vp delayed 5 samples to match them; now vf = F(h) and
  o1 = clamp(vp + vf) at the sample rate. Against the circuit at 8×,
  band-limited (an acid line): −39.7 dB at the defaults (2×: −41.5),
  −37.4 at full DRIVE (−39.2), −33.7 at full DRIVE and TONE (−35.4); 1× against
  2×: −37 … −44 dB. The owner chose 1× for the RAT by ear on 15 Oct.
- **A settled block** (d = 0, the knob's pedal on, MIX 127) writes the wet
  alone; MIX × (1 + d) would be 1 − 2⁻²³ (≤ 1 LSB of difference).
- **The knob decode is skipped** when LEVL, TONE and DRIV are the words the
  last decode read ($20..$22, $23 = valid; the init and every switch clear
  it). Words are compared whole, LFO fractions included.
- The halfbands (`dtx_up`, `dtx_down`) are gone: 1,064 words of code (v7:
  1,071), the same P table.
- Every instruction form v8 uses is one v7 already ran on the MK1.
- PAD stayed (T1 only, 8 at most); removed in v9, below.

**On the unit (v7 — v8 was never flashed — the owner's MK1, images ACIDV68 to ACIDV70, 15–19 Oct 2026):**

- On tracks other than T1: hours of playing, on claps and on two OCTA303 tracks with dEVILish,
  beside dB666 and the reverbs; no junk blocks. A 7.5-minute recording (19 Oct): peak −2.2 dBFS,
  no dropouts.
- On T1 (a kick): the junk blocks stay. The PAD that silences them moves with the load: the owner
  turned it up to 14 as effects were added (v8 reads at most 8), and at other times had to go back down to stop the clicks.
  No fixed wait works; T1 is out.

## v9 (19 Oct 2026): PAD removed, lighter

- v9 is v8 without PAD: PAD (page 2, slot 6) and its wait are gone, page 2 is empty; with PAD 0
  the output is v8's, sample for sample; `verify_distorx` passes.
- `dtx_out` is branch-free: v8's settled block returned early with the wet alone, a branch inside a
  `bsr` callee that `make cycles` refuses to price (v8 never passed `make check` on the owner's
  tree, so it was never flashed). v9 computes the mix and then keeps the wet with `tne y0,a` (the
  Tcc form v7 already ran as `tgt`/`tlt x0,a`): the same samples, bit for bit (`verify_distorx`).
- `make cycles`: 289 cycles/sample at worst (RAT/TURB; SD-1 225), v7 381.
- The cause of v7's T1 junk (🟡) stays the one above: the dispatcher's copy of T1's block lands
  inside the ColdFire's read-back pull when the insert ends in that window, which moves with the
  machine's load. It is the same family as BusDelay's open T1 case
  (`docs/contributing/FAILURE_MODES.md`). v9 ends earlier in the block (289 cycles/sample against
  381), which is consistent with the clean T1 below; it does not prove the window can never be
  reached under a heavier load.

**On the unit (v9, the owner's MK1, image ACIDV71 = BUILD 88, remix `acidtrack`, 20 Oct 2026):**

- Five DISTORX at once, all playing: T1 kick in SD-1, T3 hats in RAT, T5 an OCTA303 in SD-1,
  T6 in TURB, and dEVILish with OCTA303 on another track. No clicks, no junk blocks, no
  slow-downs (by ear; no recording of this session).
- A part saved with PAD keeps a byte in slot 6 that nothing reads.

**On the unit (DTXPR1, the final tree of this module's PR, remix `distorx`, BUILD 91, the owner's
MKI, 21 Oct 2026):** the project opens; T1 (kick) FX2 = DISTORX at MODE OFF leaves the sound as it
was; SD-1 → RAT → TURB while playing, no click; LEVL, TONE, DRIV and IN each act in each pedal;
MIX 0 is the dry sound; on FX1 of another track (T3, hats) as well; four at once (T1, T3, T5, T6,
both cores) for five minutes: no clicks, no noise, no slow-down; an LFO on DRIV or TONE moves the
sound, no hang; a scene with another MODE through the crossfader, no click; save, power-cycle,
reload: DISTORX and its knobs are kept. By ear, no recording.

**On the unit (DTXPR3, on `0x05`, the final tree, BUILD 96, the owner's MKI, 22 Oct 2026):** the
T1 run asked for in review: DISTORX on T1 (a kick) for more than four minutes, with the load
T1 and T2 kicks with DISTORX, T3 hats and T4 claps dry, T5 COMB FILTER + DISTORX, T6 COMB FILTER + DARK REV, T7 COMB FILTER + DISTORX, T8 MASTER: four DISTORX at once over both cores. No clicks, no junk blocks, by ear (no USB module in this
remix, so no recording). MODE changed through SD-1, RAT and TURB all along; taken off and chosen
again, it starts at OFF.

## v10 (28 Oct 2026): settled and calm loops, a leaner stage

**Not yet on a unit.** Everything below is a static word count and a bit-exact
render in the emulator; the one hardware figure is v9's (`docs/contributing/COSTS.md`:
9.45 % of core 0 at the dearest, over the 9.07 % that core 0 allows).

The cost was the MODE fade, run on every sample. `dtx_out` computes
MIX x (1 + d), steps d and clamps it, then blends; at d = 0 (the fade is over)
it hands back MIX exactly, and with MIX 127 the settled block's `tne` throws the
whole blend away for the wet. v10 stops computing what a settled block does not
use:

- **Per block, a calm flag** (`$2f`): d = 0 and the step up, so d stays 0
  through the block (the test the settled flag `$30` already made, without MIX).
  Settled (`$30`) is calm with MIX 127.
- **Three loops per pedal**, one straight-line `stage` routine each (`sod_stage`,
  `dtx_rstage`: the input to the wet in y0, the clipper's callee inlined):
  *settled* writes the wet to both channels; *calm* is `dtx_out`'s blend with
  MIX x (1 + d) = MIX, d untouched; *fading* is v9's `dtx_out`, unchanged.
  The output is bit for bit v9's in all three.
- **The RAT stage, bit for bit** (the model is untouched): the diode law's table
  offset in r4 once a block and the segment index without the 2 (m - 1/2)
  subtraction (`lsl`/`lsr` for the fraction, read from `a1` because A2 is stale
  there); three of the stage's constants in n1, n2, n4 (a word a use instead of
  two); the sign select as `tpl`; vp into y0; the HP stages' constant in y0 so
  `mac x1,y0` skips a copy (the signed form: `x1,y1` assembles as `macsu`,
  TRAPS "The assembler mis-encodes"); v- and v kept in b; vo1 in x1 (`y1,x1`,
  signed); the C7 update after the vX sum and the vX terms ordered so x0 already
  holds vh8.

`make cycles REMIX=distorx` reads 267 for the module now (the RAT's fading loop, the worst of the six; v9: 289).
Static cycles a sample (this note's counter, the same method: the loop body plus each callee
plus 4 a call; v9 read 289 and 225 there, this counter 291 and 227, and the
deltas are what is quoted):

| | v9 | settled (MIX 127) | calm (MIX below 127) | fading |
|---|---|---|---|---|
| SD-1 | 227 | 181 | 198 | 226 |
| RAT / TURBO | 291 | 223 | 240 | 268 |

v9's 9.45 % was 289 static cycles at 1.48 measured over static. That ratio, if
it holds, puts the RAT at about 7.2 % settled and 7.8 % calm, under the 9.07 %.
It is an inference from one ratio; the unit decides. **`dear` now sets MIX 126**,
the calm blend, which is the dearest state that lasts: the settled loop is
cheaper than the calm one, and the fade lasts 2.9 ms a MODE change. An LFO on
MODE that keeps the fade running prices at the fading column.

Bit-exactness and the circuit gates: `verify_distorx`'s render gates run
against the same model unchanged (every case 0 LSB); they were run here
through a standalone driver on the emulator library, with garbage in the
r7 block and every scratch register before each call, because the 1.40C was not
at hand. CI's reach job runs the real ones. New instruction forms against
v9: `lsl #n,a` (the load meter runs `lsr #n,a`), `tpl`, `mac -y0,x0,a`,
`mac x1,y0,a`, `mac y1,x1,a`, `mpy y1,x1,a`, `move a,b`; `verify_distorx` lists
the ones with no stock site. n1, n2 and n4 are clobbered across `proc`, as BBD's
n4 and the reverb server's n1 and n4 already are.

## Open

- v10 has not been flashed. To count: the image, then `COST-B`'s read with `dear` (MIX 126), the settled
  state (MIX 127) and a MODE change under load; T1 for a few minutes, since the fix for v7's T1 junk
  was ending earlier in the block and v10 ends earlier still.

- The `-pword` (dirty LFO word) renders of `verify_distorx`: skipped on the owner's tree, whose
  `dsp_host` lacks the option. `make check REMIX=acidtrack` otherwise passes there (20 Oct 2026).
- Instruction forms: every form DISTORX uses has run on the owner's MK1 since v7 (ACIDV68 to
  ACIDV71, DTXPR1); `verify_distorx` lists the ones with no site in the stock payloads.
- The knobs DRIV/TONE/LEVL are applied once per block.

## Files

| file | what |
|---|---|
| `manifest.py` | the module, and every constant computed from the part values |
| `distorx.tmpl.asm` | the DSP code, with `@NAME@` constants |
| `generate_asm.py` | writes `distorx.asm` (dsp_asm has no `equ`); `--check` |
| `distorx.asm` | generated, what the build assembles |
| `distorx_ref.py` | the float circuits (`SD1`, `RATCircuit`) and the bit-exact model (`fixed`) |

## Sources

- BOSS SD-1 service notes, ET5212-510A, 3 Mar 1981: part values only.
- ElectroSmash, *Pro Co Rat Analysis* (the schematic, the parts list, the
  clipping amplifier's response, the LM308's slew rate):
  <https://www.electrosmash.com/proco-rat>.
- The LTspice `LedRed` diode model (IS = 93.2 p, N = 3.73), as quoted on
  the All About Circuits forum:
  <https://forum.allaboutcircuits.com/threads/the-most-simple-ltspice-led-simulation-question.183992/>.
- PedalPCB forum, *Differences between Rat and Turbo Rat* (the LEDs are the
  difference that matters): <https://forum.pedalpcb.com/goto/post?id=69119>.
- D. T. Yeh, J. S. Abel, J. O. Smith, *Simplified, physically-informed
  models of distortion and overdrive guitar effects pedals*, DAFx 2007.
