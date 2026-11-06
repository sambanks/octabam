# `studioverb` — STUDIO VERB

A reverb for FX2, rooms to halls, with a desk-style gate, built on the reverb stage of Mutable Instruments Clouds
([`clouds/dsp/fx/reverb.h`](https://github.com/pichenettes/eurorack/blob/master/clouds/dsp/fx/reverb.h),
MIT, Emilie Gillet 2014), ported to fixed point. On id `0x1a` (PLATE REV keeps `0x14`); one instance per FX2 slot.

Until 6 Nov 2026 this module was GATE VERB (`modules/gateverb`; `git log --follow -- modules/studioverb/studioverb.asm`
has its history). It keeps GATE VERB's id, so a Part that used GATE VERB opens STUDIO VERB. The sections below that
describe GATE VERB's fixes (the smear LFO, the gate) are the record of how this code got here.

The reverb is Clouds': a Griesinger plate (the Dattorro paper's layout) of four input
allpasses and a loop of two halves, each two allpasses and a delay. The first allpass is
smeared by an LFO and the second delay is modulated. Left and right are the two loop outputs.

## Knobs (page 1)

| slot | name | default | what it does |
|---|---|---|---|
| 0 | AMNT | 45 | dry/wet. 0 is bit-exact dry. The wet is scaled to Clouds' range (the wet path is held at 1/8 internally) |
| 1 | GAIN | 51 | input gain, 0..0.5 (Clouds uses 0.2: 51) |
| 2 | TIME | 82 | loop gain 0.35..0.98 (Clouds: 0.35 + 0.63 x its REVERB knob) |
| 3 | DIFF | 100 | allpass coefficient 0..0.8 (Clouds sets 0.625 at power-up and 0.7 in use: 100 is 0.625) |
| 4 | TONE | 90 | damping lowpass coefficient 0.05..1 (Clouds: 0.7 at power-up: 90) |
| 5 | GATE | 0 | 0 is off. k holds the wet for 2048 + 256 k samples (52 ms to 784 ms) after the input falls quiet, then releases it as a desk gate does (−60 dB in about 320 ms); once shut, the tank is flushed, so the next hit starts from silence |
| 6 | MODE | PLATE | page 2 (`x:(r6+$c)` knob field, slot 6 as on every effect). A voicing: ROOM, PLATE, HALL, GATED. The DSP does not read it; turning it on the panel lands the other knobs on that mode's values (MODE DEFAULTS, the manifest's `mode_views`; table below). Without MODE DEFAULTS in the remix it only names the voicing |
| 7 | LCUT | 20 | page 2 (`$c` companion). A one-pole high-pass in each half of the tank, after the damping: c = 0.1447 LCUT², smoothed; about 1 kHz at 127, 250 Hz at 64, 63 Hz at 32; 0 passes the tank untouched |
| 8 | MOD | 64 | page 2 (`$d` knob field). The long delay's swing: 0 static, 64 the original (97 samples, scaled by SIZE), 127 twice it; smoothed. The tap's centre moves down with the swing, so it never reads outside its line |
| 9 | RATE | 64 | page 2 (`$d` companion). Both LFOs' speed: 0 frozen, 64 the original (0.5 and 0.3 Hz), 127 twice it |
| 10 | SIZE | 127 | page 2 (`x:(r6+$e)` knob field). The tank's read taps move in to 20 % of each length at 0, smoothed: f = 0.8 (127 − SIZE)/127; 127 is the original lengths, exactly |
| 11 | PRE | 0 | page 2 (`$e` companion, beside SIZE). A predelay of 32 PRE samples (0 to 92 ms) on the mono input, held in the far end of the long delay that SIZE leaves unread: m = 4167 f words past the tap, m − 2 usable, so it clamps to the room SIZE leaves. None at SIZE 127, about 22 ms at 90, 40 ms at 60, 58 ms at 30. With no predelay the input goes through ap1's write cell, which ap1 overwrites later in the sample, so nothing in the ring moves. Turning SIZE up while PRE is engaged lets the long delay's tap read predelay cells briefly (not heard yet) |

The defaults are PLATE's (MODE 1). The modes, chosen from renders of the module (6 Nov 2026):

| MODE | AMNT | GAIN | TIME | DIFF | TONE | GATE | LCUT | MOD | RATE | SIZE | PRE | RT60 (float model) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 ROOM | 45 | 60 | 70 | 90 | 105 | 0 | 30 | 30 | 64 | 35 | 0 | 1.15 s |
| 1 PLATE | 45 | 51 | 82 | 100 | 90 | 0 | 20 | 64 | 64 | 127 | 0 | 3.42 s |
| 2 HALL | 50 | 51 | 108 | 110 | 60 | 0 | 25 | 100 | 40 | 127 | 0 | 7.16 s |
| 3 GATED | 90 | 80 | 118 | 110 | 80 | 26 | 40 | 64 | 64 | 90 | 0 | gated |

Slots 0-4 are Clouds' five setters (`set_amount`, `set_input_gain`, `set_time`, `set_diffusion`, `set_lp`).
Page 2 is this port's (5 Nov 2026); at its defaults the module computes exactly what it did before, and
the ring layout does not move (SIZE shortens reads, not the layout). A Part saved before page 2
existed holds 0 in those slots: MODE ROOM, SIZE 0, MOD 0, RATE 0, a small static room. Re-pick the effect or
stamp the defaults to get the original sound back.
The ranges and defaults are this port's, taken from the values Clouds sets in `granular_processor.cc`
and `reverb.h`; they have not been compared by ear.

## The gate

Clouds' reverb has no gate; this part is new. The input (the mean of left and right, before GAIN) feeds an envelope follower with an instant attack and a 1/512 release per sample (about 12 ms). While the envelope is above 0.0078 (-42 dBFS) the hold counter is reloaded; once it falls below, the counter runs down. While it has time left the wet gain rises 1/32 of the way to 1 a sample (about 0.7 ms). When it runs out the gain falls by 1/2048 a sample: a straight line in dB, a desk gate's release (an SSL channel gate's or a Drawmer DS201's, the In the Air Tonight shape), 46 ms a time constant, −60 dB in about 320 ms. Below 2^-11 (−66 dB) it is 0. The wet output is multiplied by that gain after the reverb and before the AMNT mix, so the dry signal is untouched.

A shut gate also empties the tank. In any block that starts with the gain at 0, the loop gain (TIME's) and the allpass coefficient (DIFF's) are 0. Every line is then a plain delay fed only by the quiet input, and the tank flushes in one pass of its longest path (dap2a, dap2b, del2: 7,283 samples, 165 ms). The next hit starts from silence, so every hit of a backbeat sounds the same instead of opening onto what the last one left. Both come back the moment the gain leaves 0; the first block of a new hit (at most 0.36 ms) runs without them, into an empty tank.

Chosen by ear on 5 Nov 2026 (Sam, from sandbox renders of a backbeat snare and a tom fill; releases of 1/512, 1/1024 and 1/2048 a sample were compared, and the slowest was preferred). Until then the wet closed over 128 samples (about 3 ms), which read as a cut, and the tank rang on underneath.

Under `dsp_host` (`verify_studioverb`, GATE 40): the wet is open for the whole hold (−68.5 dB against −68.3 dB with the gate off); 70 to 110 ms into the release it is −88.9 dB against −72.3 dB, a release, not a cut (the 3 ms gate read −200 dB there); after the release it is exactly silent (−200 dB against −75.7 dB); and a second impulse 190 ms after the gate shuts, less the same impulse alone, is −119.0 dBFS, the truncation floor (−77.7 dBFS with the old gate, whose tank rang on). Whether the wash is dense and flat enough to sound like one is not measured: for the classic effect set TIME and DIFF high, GAIN up and AMNT up, and GATE to taste. The threshold, the envelope's release, the attack and the gate's release are constants in `studioverb.asm`, not knobs.

## What differs from Clouds

- **Lengths scaled by 0.9682, and the tank by a further 0.9.** The four input allpasses keep 0.9682 of Clouds' lengths
  (109, 157, 233, 386); the six tank lines are 0.9 of that again (1,440, 1,776, 2,973, 1,667, 1,449, 4,167). With the nine
  one-word gaps the ring is 14,366 words and ends at slot offset `0x381D`, below `0x3820`, where `octabam`'s demand-loaded code
  starts in the four window slots (T3, T4, T7, T8), with DLCOPY, LOAD METER, SIDECHAIN_COMPRESSOR's window and the mailbox above it
  (`Claims.buffer_words = 14366`, checked by the ledger and by `dsp_host -guard 14366`). That is what lets `octabam-verbs` carry it
  beside the loader. The extra 0.9 came on 6 Nov 2026 and shortens every tail by about 10 % at the same TIME (TIME 64: RT60 2.80 s
  to 2.53 s, from the float model). Before it the ring was 15,862 words, to `+$3DF5` (octabam's FX2 rule `+$3DFD`, #785); until
  19 Oct 2026 the scale was 0.984 (a 16,120-word ring, to `+$3EF7`).
- **24-bit buffer, not 12-bit.** Clouds stores each value as a 12-bit fixed-point number with a range of +-8. Here a value is held as
  value/8 in a 24-bit word, so the range is the same and the quantisation noise is far lower. Clouds' grit is not reproduced.
- **LFOs.** Clouds uses a cosine oscillator updated every 32 samples. This port uses a parabola `4x(1-|x|)` of a phase accumulator
  updated once a block (16 samples), at the same rates (0.5 Hz on the first allpass smear, 0.3 Hz on the second delay), with the
  same depths scaled with the lengths (60 samples for the smear, 97 for the delay, centred at 4068 since 6 Nov 2026, 4531 before).
- **Smoothing.** The five coefficients move a sixteenth of the way to their target each block (Clouds changes them as they arrive).
- **Memory.** A modulo ring of 14,366 words (`m5 = 14365`). It is not a power of two. Stock code uses small non-power-of-2 moduli
  (6, 10 and 30), but nothing uses one this size with `(Rn+Nn)` addressing; this is the first thing to check on a unit.

## Measured

Under `dsp_host` (`tools/verify/verify_studioverb.py`, remix `test/studioverb`):
- The pricer counts 247 cycles per sample (219 before the desk gate, 228 before page 2, 242 before PRE), a floor: it counts words, not memory stalls. Scaled from the 7.76 % GATE VERB measured on a unit at 219, about 8.8 % a slot (🟡 inferred, not read), under the 9.07 % that lets it sit on every FX2 slot. `tools/remix/slot_costs.json` carries no STUDIO VERB entry: GATE VERB's reading was of older code.
- PRE: SIZE 60 with PRE 40 matches the model to 61.1 dB over 8,000 samples; it moves the wet onset by 1,279 samples (32 × 40 = 1,280; the onset is a threshold crossing); PRE 127 at SIZE 90 is clamped to the 1,077 samples of room; at SIZE 127 PRE 127 is bit-exact PRE 0; SIZE 0 with PRE 127 writes nothing outside the ring.
- Page 2 against the model: six settings (SIZE 30; SIZE 0 with MOD 127; LCUT 90; MOD and RATE 0; MOD and RATE 127; SIZE 60, LCUT 40, MOD 100, RATE 30) match to 57-82 dB over the first 8,000 samples, where a wrong integer tap would show at once, and 46-62 dB over the whole render, where the tail meets the 24-bit floor the float model has not got. SIZE 30 decays faster than 127 (−69.3 dB against −56.9 dB at 0.7-0.9 s); LCUT 90 takes 12 dB out under 150 Hz; SIZE 0 with MOD 127 writes nothing outside the ring.
- The first 22 calls pass the input through while the ring is cleared (653 words a call, exactly the ring: 77 × 206 would now write past it, into `octabam`'s window code).
- AMNT 0 is bit-exact dry.
- An impulse and a noise burst through 48,000 samples match a float model (gate off, and an impulse with the gate on) of the same algorithm (same lengths, the same integer LFO phases and
  offsets, the same parameter laws and smoothing) to 58 dB (the difference is the 24-bit arithmetic).
- No write outside the 14,366-word ring (`-guard 14366`); a dirty state block and a dirty ring with silent input give silent output.
- TIME 127 rings longer than TIME 80.

Not measured: sound (no listening yet), hardware, the real allocator's bases on a unit.

### The smear LFO was bipolar, and the tail grew from TIME 94 up (fixed 5 Nov 2026)

Clouds' LFOs are unipolar: stmlib's `CosineOscillator::Next()` returns `y + 0.5`, 0 to 1, so
Clouds reads `ap1` at 10..70 and `del2` at 4680..4780. Until 5 Nov 2026 this port's smear used the
parabola bipolar, ±1: it read `ap1` at −50..70, so up to 50 samples of its reads landed behind line 0,
in the far end of the last tank line, and were written back into the first input allpass. That was a
second feedback path that TIME did not scale. The smear's LFO is now `(lfo1 + 1)/2`, as Clouds'.

✅ Under `dsp_host` (the module, one impulse after the knobs settle, AMNT 80, gate off), half-second
RMS of the left output:

| TIME | before | after |
|---|---|---|
| 64 | −58 dB, then a floor near −85 dB that drifted up to −82 dB | −58 dB to −99 dB in 3 s, then steady |
| 90 | −57 dB, a floor near −70 dB, rising | −57 dB to −95 dB |
| 120 | −56 dB, **grew to −11 dB** in 11 s | −56 dB to −84 dB |
| 127 | grew to −4 dB in 10 s (the gate's `runaway` check on the old code) | −56 dB to −77 dB in 11 s, still falling |

RT60 from the float model (`tools/harness/studioverb_voice.py --impulse`, on the 15,862-word ring of the time): TIME 64 2.80 s (4.84 s
before), 80 3.72 s (6.87 s), 94 5.08 s (grew), 127 17.92 s (grew). The extra path made every tail
longer, not only the unstable ones, so a part voiced on the old code sounds shorter at the same TIME.
`verify_studioverb`'s `runaway` check fails on the old code and passes on the new; the model match is
58.0 / 58.1 dB, as before.

Not changed: the `del2` tap still swings 4531 ± 97, twice Clouds' excursion, and stable
(`studioverb_voice.py --lfo clouds` renders Clouds' form). What is left at the end of a long tail is a
DC offset, not a tone: at TIME 120, the last second reads −84.4 dBFS DC and −97.2 dBFS AC. That is
`mpy`'s truncation bias circulating in the loop; a high-pass in the tank (the LOCUT the sandbox
proposes) would remove it. Not heard on a unit, before or after.

## Credit

Emilie Gillet, Mutable Instruments (`pichenettes/eurorack`, MIT). `THIRD_PARTY.md` has the licence row.
