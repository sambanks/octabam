# `bbd` -- BBD

A bucket-brigade delay for FX2, by JamCones (Cam Jones): a 2:1 compander,
clock-tracking anti-alias and reconstruction filters at a third of the clock,
a clocked bucket line with a charge-transfer curve and bucket noise, a
resonant feedback tilt, a freeze, a feedback governor and an input high-pass.
1,075 DSP words and a 32-byte ColdFire stub (`kill.s`);
`bbd.asm` is proven against a float model of the same chain, `bbd_ref.py`.

The mono sum of the track goes through:

1. **Input and compressor.** HPF high-passes the input; a tanh shapes the input (FDBK's returning wet is
   added first), then a feedback compressor divides it by a 10 ms average of
   its own output: 2:1, as in the compander chips BBD delays use.
2. **Anti-alias filter.** An 8th-order Butterworth low-pass at a third of the
   clock: 6.8 kHz at the fastest clock, 1.7 kHz at the slowest.
3. **The bucket line.** A clock between 20.5 and 5.1 kHz shifts the line. On
   each tick the input at the clock edge goes in; the bucket that went in
   1,023 or 4,095 ticks earlier (STGS) comes out through a charge-transfer
   curve, with a little white noise, and is held until the next tick.
4. **Reconstruction.** A 7th- and a 2nd-order Butterworth low-pass at the same
   cutoff smooth the held staircase, a 10 Hz high-pass removes the buckets'
   DC, and the expander undoes the compressor.

TIME is the clock and glides over 20 ms, so locks and LFOs on TIME bend the
pitch of everything in the line. The dry signal is never processed: MIX 0 is
the exact input.

## Knobs

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| main, A | TIME | 0–127 (64) | The clock, 20.5 kHz at 0 to 5.1 kHz at 127, linear in delay time: 50–200 ms with STGS 1024, 200–800 ms with 4096. |
| main, B | FDBK | 0–127 (0) | The wet returned to the input through TONE. With TONE centred the repeats ring longer up to 127 (about 1 dB a second) but never self-oscillate; with TONE at either end the loop rings on from about FDBK 40, and LIM sets how loud. |
| main, C | FRZ | 0–127 (0) | Freeze. Rising from 0, the input fades out of the line and FDBK is taken towards sustain for the current TONE (never lowered), so the trails get longer. At 127 the line loops its own buckets exactly, ignoring the input and FDBK, at the level it had; a crossfade of any speed into 127 keeps that level. A STGS change clears it. |
| main, D | TONE | −64–+63 (0) | The feedback tilt, ±9 dB at the ends, inside the loop only. Right: treble up and bass down about a 200 Hz pivot. Left: a bandpass peak at FREQ, Q 1.5. |
| main, E | FREQ | 0–127 (64) | TONE's bandpass centre, 400 Hz to 2 kHz, logarithmic (64 is about 900 Hz). Heard only with TONE left of centre. |
| main, F | MIX | 0–127 (40) | 0 is exactly dry. To 64 the wet rises to unity over the whole dry; from 64 to 127 the dry fades out. Smoothed per sample. |
| SETUP, A | STGS | 1024 / 4096 (1024) | Bucket count. A change fades the wet out over 16 blocks, clears the line (about 6 ms, dry) and fades back in. |
| SETUP, C | LIM | 0–127 (127) | The feedback governor, 0 off. Past an envelope of 2^(−3.5·LIM/127), FDBK is scaled by the square of the overshoot, so self-oscillation settles at a set level; at 127 it sits about 30 dB under LIM 0. |
| SETUP, E | HPF | 0–127 (0) | 0 is off and costs nothing. Otherwise a 12 dB/oct Butterworth high-pass on the signal entering the line, 20 Hz at 1 to 400 Hz at 127, logarithmic (64 is about 90 Hz). Glides like FREQ. |

**The stop kill.** STOP, STOP, STOP silences the stock reverbs' and DELAY's
tails; it silences BBD's too. The ColdFire's frame pass at `0x40004d0c` zeroes
slots A, F and 11 of every track in the kill mask (`0x8000184b`: all eight
from stop-and-rewind, each cleared when its track triggers again) whose FX2
is PLATE, SPRING or DARK REV. `kill.s` (a detour there) adds BBD's id and
zeroes its slot 11 only: a hidden slot that is 127 otherwise. While it reads 0
BBD outputs the input exactly and clears its line and state (the STGS clear,
no fade), so nothing rings on when the track plays again.

FDBK, TONE, FREQ and HPF glide over about 6 ms; MIX glides per sample; TIME
glides with the clock. `dear` is TIME 0, FDBK 127, TONE 0, FREQ 127, MIX 64,
STGS 4096, HPF 64 (`cycle_count.py` prices HPF on).

## Measured

All 51 gates of `tools/verify/verify_bbd.py` pass on this tree (`dsp_host`, a
private image with the stock code built in and BBD in the space of SPRING REV
and PLATE REV, as `remixes/test/bbd` places it):

- **Exact dry:** MIX 0 renders the input sample for sample, static, with every
  other knob moving, and with trig splits (0 of 48,000 words differ).
- **The DSP against `bbd_ref.py`:** −57 to −79 dB residual across TIME, STGS,
  MIX, FDBK, TONE, FREQ, FRZ, LIM and HPF (1, 64, 127); splits at 1, 7 and 15; STGS
  changed twice mid-signal; FRZ 127 mid-signal.
- **Stop kill:** slot 11 at 0 from block 2000 to 3300 over a ringing loop
  (FDBK 110): the input exactly while it holds (0 of 41,600 words differ), no
  tail after (−102.4 dBFS; −44.0 dBFS without the kill), the model at −74.4 dB.
  Under the ColdFire port (`ot_emu`, this remix's image, a project's T1 with
  its FX2 id poked to BBD's, STOP three times): from the kill on, only record
  byte +53 (slot 11) is zeroed, by `kill.s`, every frame; with DARK REV's id
  the stock pass zeroes +24, +34 and +53 as before.
- **Freeze:** a 0.5 s crossfade into FRZ 127 keeps a self-oscillating loop's
  level (+0.4 dB); FRZ 100 with TONE 0 and FDBK 20 lengthens the trails
  without droning (−97.7 dBFS at 8.5–10 s).
- **Idle and LIM:** tails die away (FDBK 90: −114 dBFS after 9 s); FDBK 127,
  TONE 0 self-oscillates below full scale, and LIM 127 settles it 29.6 dB
  under LIM 0.
- **Isolation:** eight instances under `-guard 0x4000 -guard-shared -dirty
  0x5a`: no stray write or clobber, each bit-identical alone.
- **Garbage start:** silence from a garbage block renders exactly as from a
  zeroed one (at most 2 LSB, −132.5 dBFS: the bucket noise).
- **Zipper:** no block-rate step on any continuous knob.
- **Placement:** BBD at `P:0x01000..0x01433` (payload A) and
  `P:0x00dc0..0x011f3` (B), inside PLATE REV's and SPRING REV's run and clear
  of the 35 SPRING REV words DARK REV calls (`P:0x01586`, `P:0x01346`).
- **DARK REV** renders bit-identically to the stock OS on both cores, fixed and
  moving. A layout with BBD in SPRING REV's space alone covers that routine and
  fails this gate (about 95 % of words differ).

**Cost.** `cycle_count.py`: 378 cycles a sample per instance (the tick path,
HPF on), so four per core take 1,512 of the 3,120 usable. Executed in
`dsp_host` (`benchmark_reverbs.run`, eight instances, four per core, its fixed,
modulated and trig-split cases including every synchronised split): at most
443.2 instructions a sample per instance (28,368 a block per core, synchronised
splits at 1), 398.8 modulated unsplit, 373.8 at the defaults; SPRING REV
318.4 under the same cases. HPF's section is rebuilt each call while it is on,
so a split pays for it twice.

**Sound** (measured before HPF became variable and POST was removed; the
wet path is otherwise the same code). Wet-only audit tables at TIME 0 and 127: harmonics −44 to −76 dBc,
DC −85 to −140 dBFS, nothing on the rails, idle 2 LSB. The aliasing limit
(−60 dBc) fails by design: a bucket brigade is a sampler clocked at 5–20 kHz,
and the charge-transfer curve bends the held samples, so harmonics fold at the
clock (−44 dBc for 1.1 kHz at the fastest clock, −37 dBc at the slowest).

## On the unit

The author played BBD on an Octatrack MKII, OS 1.40C, 11–12 October 2026, in
images built by Modwerk's builder (derived from octabam) with BBD at FX2 id
`0x0e`, before HPF became variable, POST was removed and LIM and HPF moved to
SETUP C and E. **This remix's image (`0x1b`) and the current DSP have not been
flashed.**

- **BBD01–BBD02:** crackle on T1 and, after STGS changes, tracks 1–4 silent:
  the `rep` divides (FAILURE_MODES.md, "Crackle on core B"). **BBD03**, every
  `rep` a `do` loop: clean on T1 behind FILTER and PHASER, STGS clean on T1 and
  T5, a heavy existing project fine.
- **BBD04–BBD13:** FRZ, FREQ, the ±9 dB TONE, LIM (range and default set by
  ear), the MIX curve and the then fixed 150 Hz PRE/POST switches (no
  switch-on thump) as intended.
- **BBD14**, BBD beside the stock effects with SPRING REV and PLATE REV given
  up (`P:0x01000`/`P:0x00dc0`, as here): DARK REV works on FX2; two instances
  at once; eight instances (FX2 on all eight tracks) for 30 minutes with
  feedback and modulation running; a Part or project save and reload; a saved
  project restored after a power cycle; FREQ swept end to end by an LFO; FRZ
  and every other control played through the crossfader.

## Open

- The stop kill on a unit: that the record's slot 11 byte is what the DSP
  reads at `x:(r6+$e)` bits 8-15 is inferred from the slot layout and the stock
  reverbs' own test of bit 8 there, not traced end to end.
- This remix's image on a unit (the FX2 id, the surrounding tree, HPF, the
  SETUP layout and the removal of POST differ from BBD14); the eight-instance
  stress render on the current DSP.
- LFO sweeps of controls other than FREQ, MIDI/USB load, MKI.
- Real-chip headroom: the cycle figures are `cycle_count.py` bounds and
  `dsp_host` counts.

## Limits

- FX2 only: the line needs the 16,384-word FX2 buffer
  (`Claims(stock_instance_buffer=True)`); an FX1 slot (3,072 words) is too
  small.
- Mono wet; the dry stays stereo.
- Free-running TIME: the DSP side has no tempo word. Deliberate: TIME is the
  bucket clock, and gliding it is what bends the pitch.

## Gates

```bash
python3 tools/verify/verify_bbd.py      # 51 render gates (make check runs them)
make check REMIX=bbd
```

## Design

- One output tap, `stages − 1` ticks along the line.
- The input tanh is a Padé approximant, x(27 + x²)/(27 + 9x²) up to |x| = 3,
  folded into the compressor's divide.
- The 8th- and 7th-order filters run as cascaded biquads with 24-bit state; at
  the slowest clock their state noise sits about 56 dB under the signal (the
  −57 dB reference residual there is that noise; in-phase gain error −66 dB).
- One of the nine filter sections follows the clock each 16-frame call, so all
  nine refresh in 144 samples; after a reset all nine are computed at once.
- The feedback tilt uses a 200 Hz split with cubic gain fits and a unity-peak
  bandpass whose coefficients are polynomial fits over FREQ (within 6e-5 of
  the exact design). ±9 dB is deliberate: at ±15 dB a full TONE made the loop
  self-oscillate from about FDBK 25.
- TIME's clock constants (`P16_A`, `P16_B` = `0x113a00`, `0x34162c`) are exact
  Q23 words shared by `bbd.asm` and `bbd_ref.py`, so both tick on the same
  samples. A rounded constant once put 8 % of ticks a sample late (−16 dB
  residual at TIME 0).
- FRZ below 127 works through the feedback loop: the input is scaled by 1 − h
  and FDBK becomes FDBK + h·max(0, S − FDBK), h = FRZ/128, S = (127/128) /
  TONE's peak gain. At 127 the line loops its own buckets. (Mixing old and new
  buckets instead combs a ringing loop down by 6–11 dB on a slow crossfade.)
- HPF's K is 2 tan(π 400/sr) · 2^−e / 2 through LIM's 2^−f fit, gliding 1/16
  a call; its section reuses the clock filters' Butterworth routine (same
  poles) with a high-pass numerator. It feeds its truncation back in: at
  20 Hz the poles near DC lift plain rounding noise about 40 dB (−42.6 dB
  against the model without it, −67.8 dB with it).
- No `rep` anywhere (`tools/build/norep.py`): every divide is a `do` loop.

The charge-transfer curve follows Raffel's BBD paper (CCRMA, 2010); the noise
generator is the Numerical Recipes LCG. No Elektron bytes.
