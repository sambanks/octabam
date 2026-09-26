# BusDelay

A multi-mode delay: CLEAN, GRAIN (a pitched granular cloud over the delay
lines: Nimbus's grain readers, four per line, one continuous pitch) and
REVERSE, with a tape wow on the loop tap in every mode. Hosted
on payload B (core 1), which serves tracks 1–4. Stage 1 of the one aux bus:
its output goes on to BusVerb; the repeats come out on the host track.

## Memory: two 32K lines, 741 ms

On the unit as image 28 (15 Sep 2026): "sounds fantastic now".

Since 15 Sep 2026 each line is 32,768 words: LineL is core 1's whole
shared half (`Y:0x38000–0x3FFFF`), LineR the core's private FX2 buffer
region (`Y:0x4000–0xBFFF`) — the region BusVerb's tank owns on core 0 and
nothing writes on core 1 (measured under the port: OCTABAM89 C02, 900
frames, every DSP write per 256-word region on both cores; core 1 wrote
`Y:0x0000–0x07ff`, `0x0900–0x09ff`, `0x36000–0x361ff` and its shared half,
nothing in `0x1000–0xBFFF`). TIME is 64 + knob·256 samples, 1.5–739 ms;
the sticky snap knows twelve divisions, 1/32T … 1/4. — at 121 BPM 1/4 (496
ms) and 1/2T (661 ms) hold, 1/4. (744 ms) from 122 BPM, 1/2 never below
162. REVERSE's mono ring is LineL's 32K, unchanged. LineR's pointer is
base-relative (`y:(r2+n2)`): the private base is only 16K-aligned, so an
absolute pointer cannot be masked — the first build wrote every other
sample 16K away. The DEV hatch (payload A, beside the reverb's tank) keeps
two 16K lines in the shared half; `tools/remix/geom.py` selects the
`; @B` / `; @DEV` lines, and the two geometries render bit-identically at
any TIME both can hold (`verify_twocore`). The ledger refuses a second
owner of the private region on the same payload (`Claims.owns_fx2_buffers`).

Stored TIME bytes from before (64 + knob·128) now mean twice the time:
`ot_project.py stamp-slot <project> busdelay 1 20` puts every part's T1 at
the old default's 118 ms.

TIME is a free dial with a sticky snap: near a division it snaps, holds that
division through tempo changes, and lets go when the knob moves. The tempo
is stock's record word (tempo24 at `r6+$13`, halfword 31 of every track's
record); the MIDI-clock period is derived per block on the DSP (24-step
`div`, `y:$090d`). The held MIDI note arrives from the
[`tempo-sync`](../tempo-sync/) note cave at `r6+$1` bits 8-15; the panel
label comes from its formatter cave.

TIME glides toward the knob (1/1024 per block), the glided value ramps
across each block a sixteenth of the step per sample (the whole step at the
block edge was a click per block for the ~1 s a big move glides, in every
mode; measured and fixed 20 Sep 2026, `tools/harness/glide_census.py`),
and the loop tap reads between samples at the ramp's fraction (the integer
read since the wow went skipped a sample at every integer crossing -- a
click per crossing, recirculating). REVERSE's lag floor and GRAIN's read
base follow the ramp per sample. The step is never smaller than 1/16
sample per block toward the target and never past it, so the state lands
exactly and the fraction is 0 at rest (a standing fraction is a two-sample
average on every pass, which dulled the repeats after a TIME increase in
image 33; images 34-39 snapped from 4 samples out instead). FDBK, TONE,
PING and WET move an eighth of the way to their knob per block, and the
loop steps FDBK, TONE and PING toward that per sample, 1/16 of the gap
(26 Sep 2026; GRAIN's makeup and read step the same way, and the host's
DEL and REV sends 1/64 per sample, `make verify-knobs`). All of it
runs on the first call of a block only (21 Sep 2026): a trig splits the
block into two dispatcher calls, and a glide that ran on both restarted
the ramp at the trig -- a click at every trig while TIME moved. The glide
state is guarded against boot garbage (negative or past the line: start
at the target).

## Knobs

| | CLEAN | GRAIN | REVERSE |
|---|---|---|---|
| page 1: DEL · REV · FDBK · TONE · PING · WET | the same everywhere | | PING reads `---` (the mode pins it to 0) |
| MODE (p6) | CLEAN | GRAIN | REVRS |
| SCTR (p7) | `---` | how far apart the grains read | `---` |
| DENS ⌐(p8) | `---` | density, level-flat | `---` |
| SIZE (p9) | `---` | GLEN: grain length 46 / 93 / 23 ms, XTRM 186 ms | SLEN: segment; XTRM = 371 ms |
| PTCH ⌐(p10) | `---` | ±2 oct, 64 = unison; a held MIDI note overrides | `---` |
| TIME (p11) | delay time, a free dial that sticky-snaps to tempo divisions | the same | the same |

Each mode's `ModeView` re-defaults the knobs and names every knob the mode
never reads `---` (20 Sep 2026, every effect). PING 0 by default: an aux
delay sits still; the bounce is the knob's. DEL (p0) is the host's own dry
send into the delay; REV (p1) its dry send into the reverb's REV
accumulator (26 Sep 2026, SEND's recipe: ramped per sample, counted as a
REV client only while nonzero). On the host page these two are the only
knobs drawn (the remix's `host_slots`); the rest are the TEMPO window's.
TIME moved from p1 to p11 the same day, and the tape wow that sat on p11
(20 Sep 2026, in the freeze's slot) went: at WOW 0 it added exactly 0 to
the lag, so every render at WOW 0 is unchanged (verify-bus). The freeze
hold is gone.
In REVERSE LineL alone is the 32K mono ring (the R line is not read or
written; XTRM = 16,384 samples = 371 ms, the mode's default), PING is forced
off and the output is mono to both channels.

## Local rendering

`dsp_host` renders payload B only under `rig_render.py` (both cores); the
DEV hatch (`make render-delay`) places the delay out of region in payload A.

## Measured

- CLEAN and REVERSE bit-identical across the `verify_delay` cases (defaults,
  PING 0/127, TIME 0/127, FDBK+TONE, split, WET 0, wow, the unknown-mode
  fallback); `verify-bus` 28/28 (GRAIN, REVERSE, PING and the reverb's other arms were added to the gate 23 Sep 2026).
- GRAIN DC gate (0.25 FS DC, full density, unison): p-p 0 across scatter
  0/64/127 and every size (four windows a quarter period apart sum to
  exactly 2).
- GRAIN pitch (438 Hz tone, 93 ms grains, TIME 127): PTCH 64 → 438.7 Hz;
  96 → 869.4 (876 expected); 32 → 223.4 (219); 48 → 309.5 (310); 127 → 1709
  (1714). MIDI note 96 → 869.4, 91 → 654.1, 72 → 223.4. Below about −1.5
  octaves the finder reads 10–25 % low (note 60 → 94 for 110): finder or
  engine, unverified. 186 ms grains at TIME 100 clamp PTCH 127 to 2.5×.
- GRAIN density law (0.5 FS tone, 93 ms): −14.6 / −11.2 / −10.7 / −11.3 /
  −12.0 dBFS at DENS 0/32/64/96/127; GRAIN's peaks sit level with CLEAN's
  (RMS ~4 dB under).
- PING at FDBK 60: 0 mono (L/R correlation 1.000), 32 / 64 near-mono (0.998
  / 0.965), 96 / 127 the bounce (0.73 / 0.01); 127 leans +4.4 dB left (L
  gets repeats 1, 3, 5: L/R = 1/feedback).
- REVERSE at 371 ms: a 50 ms burst comes back reversed ~300 ms later; the
  sine is continuous at every size.
- Cost: 1,300 words on payload B; pricer (`cycle_count.py --modes`, words)
  GRAIN 1,028 / REVERSE 395 per sample (1,354 words and 1,126 before the
  23 Sep 2026 rewrite; 1,326 words after the return left 20 Sep, +28 for
  the TIME ramp).
- 23 Sep 2026: the sample loop reads the aux accumulator through r3 and
  writes the chain at `(r3+n3)`, keeps x_in, the lag, the fraction, the
  TIME ramp, the crossfeed terms and the stage outputs in registers, and
  the GRAIN and REVERSE arms run after the line writes and write the wet
  slots themselves (the SHIFTED substitution and its flag are gone; GRAIN
  keeps s/frac/gain/t0 in registers, its phase cursor in r6 and its wet sum
  in n6; REVERSE keeps its lags and windows in registers). Displaced
  `(r7+$..)` moves per sample, counting each `do #4` body four times and
  callees per call: CLEAN 91 -> 35, GRAIN 294 -> 102, REVERSE 109 -> 39.
  Probe 57 (`docs/firmware/CHIP.md` §2) timed a one-word displaced move at
  3.98 cycles against 2.00 for a pointer or register move. All 28
  `verify-bus` cases bit-identical. Not gated: a TIME move during a render
  (no case glides), so the ramp's move to n4 is by reading, not by render.
- 23 Sep 2026: two per-block writes landed in GRAIN's records. The PITCH
  decode parked f and oct in raw $49, grain 3's scatter word on line L
  (moved to raw $16); the SIZE decode wrote the REVERSE lag cap to raw $56,
  grain 3's window multiplier on line R (the write was a duplicate of raw
  $2a's and is gone). Each change moves the two GRAIN gate cases and none
  of the other 26.

On Sam's unit in every rig flash. Heard: REVERSE 371 ms over 93 ("the long
one is better"); GRAIN DENS 32 → 127 on the loop "sounds pretty good".

## Open

- REVERSE's segment ceiling is 371 ms (its 32K ring is LineL); a 741 ms
  segment would need both lines as one ring, which they are not (LineR is
  in the private region).
- Pitch accuracy below −1.5 octaves: finder or engine.
- The delay's wet is ~4 dB quieter than the reverb's at equal send.
