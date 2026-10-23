# `euclid` — EUCLID

A stereo Euclidean modulation effect for either FX slot. It follows the
Octatrack transport, track speed and swing grid. A 1–64-step rhythm drives
one of five destinations: 12 dB/octave low-pass, band-pass, high-pass,
notch, or amplitude. The rhythm keeps rolling across pattern loops; PLAY
resets phase.

The `euclid` remix retains the stock Plate, Spring and Dark Reverb rows in
FX2. Their descriptors, DSP code and dispatch entries stay stock.

## Knobs

| Page | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| Main | FREQ | RES | DEPTH | DEC / LEN | STEPS | PULSE |
| Setup | ROT | RATE | TYPE | ATK / EDGE / SLEW | OUT mode | MIX |

FREQ is the base cutoff for LP/BP/HP/NOTCH and the base gain for AMP. DEPTH is
bipolar: its center leaves the destination static, positive values increase
it on a pulse, and negative values decrease it. RES controls the four filter
types and is inert for AMP. MIX zero is exact dry passthrough.

TYPE offers LP, BP, HP, AMP and NOTCH. AMP retains value 3 so existing saved
parts remain compatible; NOTCH is appended at value 4. The filter modes use
the same two-pole TPT state-variable core, with NOTCH summing its low-pass and
high-pass taps. AMP applies the Euclidean control signal as gain, so it can
produce rhythmic level envelopes, gates and stepped/random amplitude. In AMP,
the panel renames FREQ/RES/DEPTH to LEVEL/--/AMT; every filter type restores
the original names.

STEPS displays 1–64; PULSE displays 0–64 and is limited internally to STEPS.
STEPS, PULSE and ROT use the full dial arc without changing stored values or
encoder increments. This uses the remixer's shared `WIDE_STEPPED` formatter
support rather than an effect-owned panel detour.

ROT shifts both the rhythm and captured random values right. RATE offers
1/32, 1/16, 1/8, 1/4 and 1/2 relative to track speed; 1/16 is one track
step. A RATE change joins the next point on the new grid without replaying a
backlog.

The output selector names itself ENV, GATE, RAND or LOOP:

- **ENV:** each pulse retriggers an attack and curved decay. ATK ranges from
  immediate to one step. DEC reaches eight steps and may cross several rests.
- **GATE:** each pulse opens the destination for LEN, from 1/128 to one step.
  EDGE smooths both transitions and is limited to half the gate length.
- **RAND:** each pulse chooses and holds a new level. SLEW controls the
  transition, up to one step.
- **LOOP:** freezes the last random value heard at every Euclidean position.
  ROT moves the captured values with the rhythm; returning to RAND resumes
  generation.

Zero pulses and STOP return to the base cutoff or gain. Captured values
survive transport restarts but are runtime state, not project data.

Swing uses the track's swing mask and amount, including Swing All changes.
Rotation and odd Euclidean lengths do not rotate the track swing grid. The
1/32 subdivision interpolates the surrounding track-step offsets.

## On the unit

Cursory testing on Sam's MKII (owner report, 16 Oct 2026).

On radiohagen's MKII (`EUCL EVENTS 98`, owner report, 22 Oct 2026),
start/resume/stop passed with one EUCLID instance, instances on several tracks
and both FX slots on one track; ordinary and arpeggiated MIDI played and stopped
normally.
Ordinary and arpeggiated MIDI start/resume/stop also passed on optimized
`EUCL EVENTS 99` the same day.
EUCLID subscribes only to start/resume. Sample-accurate reset timing and multiple
registered clients were not measured on the unit.

## Clock restart ordering

`eu_clock_start` runs from the PLAY sites in task context; `eu_clock_update`
runs in the frame ISR and reads `now`, `quantum`, `remainder` once
`initialized` is set. `eu_clock_start` clears `initialized` first and sets
it last, and `eu_reset_clock` (hooks.s) holds the interrupt mask at 7 across
the call, restoring the SR saved after the displaced PLAYING store (mask and
CCR). The ordering is by reading the code; the port is lock-step and cannot
interleave the ISR with the task, so it is not measured on the port or the
unit. The store order is checked under the port with `--watch-mem`.

## Gates

`make check REMIX=euclid` runs the Euclid suite as part of the normal verify
target. It checks the native control laws, checked-in ColdFire assembly,
executed hook traces, caller registers and PLAY condition codes, both DSP
payloads, LP/BP/HP/NOTCH response, AMP unity/silence and instruction cost,
rapid TYPE changes, cutoff sweeps, stock-row
isolation and the real panel renderer. With `OT_PROJECT` it also boots a
copied project under the ColdFire port and checks full playback. No test
writes to the source project or hardware.

Manifest gate: `tools/verify/verify_euclid.py` (stage `image`).

## Implementation

`control.c` is the integer rhythm/envelope engine. `generate_control.py`
compiles it to the checked-in `control.s` and appends `hooks.s`. The frame
hook publishes the modulated FREQ value after stock scene and LFO processing,
which otherwise overwrites it. Both PLAY paths call one reset routine and
restore the condition codes produced by the displaced stock PLAYING store.

Firmware addresses and sequencer-record strides are named and cited in the
firmware documentation. Track scale, length, swing and masks are read once
per track even when Euclid occupies both FX slots. The ColdFire engine derives
only the envelope timing used by the active output mode; stopped and inactive
instances skip it.

`filter.asm` contains the stereo two-pole TPT state-variable core and a
dedicated AMP path. AMP reproduces the original gain arithmetic exactly while
skipping the coefficient lookup, reciprocal divide and stereo filters; on the
host instruction meter it falls from about 2,276 to 462 instructions per
16-sample block. Returning to a filter clears the hidden integrators before
processing. Cutoff ramps per sample. Its reciprocal denominator follows a moving
cutoff to avoid closing-sweep overshoots, but a held cutoff reuses the exact
coefficient instead of paying for a 24-step divide on every sample. All DSP
state is initialized and private to the instance; no audio buffer is
allocated.

EUCLID subscribes to EVENTS for PLAY and resume. Its reset remains guarded against the frame ISR; other modules can register independently.
