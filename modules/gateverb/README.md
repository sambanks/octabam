# `gateverb` — GATE VERB

A gated reverb for FX2, built on the reverb stage of Mutable Instruments Clouds
([`clouds/dsp/fx/reverb.h`](https://github.com/pichenettes/eurorack/blob/master/clouds/dsp/fx/reverb.h),
MIT, Emilie Gillet 2014), ported to fixed point. On id `0x1a` (PLATE REV keeps `0x14`); one instance per FX2 slot.

The reverb is Clouds': a Griesinger plate (the Dattorro paper's layout) of four input
allpasses and a loop of two halves, each two allpasses and a delay. The first allpass is
smeared by an LFO and the second delay is modulated. Left and right are the two loop outputs.

## Knobs (page 1)

| slot | name | default | what it does |
|---|---|---|---|
| 0 | AMNT | 40 | dry/wet. 0 is bit-exact dry. The wet is scaled to Clouds' range (the wet path is held at 1/8 internally) |
| 1 | GAIN | 51 | input gain, 0..0.5 (Clouds uses 0.2: 51) |
| 2 | TIME | 64 | loop gain 0.35..0.98 (Clouds: 0.35 + 0.63 x its REVERB knob) |
| 3 | DIFF | 100 | allpass coefficient 0..0.8 (Clouds sets 0.625 at power-up and 0.7 in use: 100 is 0.625) |
| 4 | TONE | 90 | damping lowpass coefficient 0.05..1 (Clouds: 0.7 at power-up: 90) |
| 5 | GATE | 0 | 0 is off. k holds the wet for 2048 + 256 k samples (52 ms to 784 ms) after the input falls quiet, then closes it over 128 samples (about 3 ms) and a 32-sample smoothing; the tank keeps ringing underneath, so the next hit reopens it |

These are Clouds' five setters (`set_amount`, `set_input_gain`, `set_time`, `set_diffusion`, `set_lp`).
The ranges and defaults are this port's, taken from the values Clouds sets in `granular_processor.cc`
and `reverb.h`; they have not been compared by ear.

## The gate

Clouds' reverb has no gate; this part is new. The input (the mean of left and right, before GAIN) feeds an envelope follower with an instant attack and a 1/512 release per sample (about 12 ms). While the envelope is above 0.0078 (-42 dBFS) the hold counter is reloaded; once it falls below, the counter runs down and the wet gain follows `min(counter, 128) / 128`, smoothed. The wet output is multiplied by that gain after the reverb and before the AMNT mix, so the dry signal is untouched. Only the output is gated: the tank keeps ringing.

That is the shape of the 1980s gated reverb: a dense, level wash that cuts off abruptly rather than decaying. Under `dsp_host` the wet is open for the whole hold and exactly silent after the closing ramp (-200 dB against -72 dB with the gate off, in `verify_gateverb`). Whether the wash is dense and flat enough to sound like one is not measured: for the classic effect set TIME and DIFF high, GAIN up and AMNT up, and GATE to taste. The threshold, the release of the envelope and the ramp lengths are constants in `gateverb.asm`, not knobs.

## What differs from Clouds

- **Lengths scaled by 0.9682.** The delay lines total 15,853 words (16,375 in Clouds); with the nine one-word gaps the ring is
  15,862 words. An FX2 instance gets a 16,384-word slot; an effect's buffer stops at `+$3DFD` (octabam's FX2 rule, #785), because
  the slot's last `$202` words are SIDECHAIN_COMPRESSOR's cross-core window in T3's and T7's slot, and the top 256 hold the stock
  mailbox and LOAD METER (`Claims.buffer_words = 15862`, checked by the ledger and by `dsp_host -guard 15862`). Until 19 Oct 2026
  the scale was 0.984 (a 16,120-word ring, to `+$3EF7`).
- **24-bit buffer, not 12-bit.** Clouds stores each value as a 12-bit fixed-point number with a range of +-8. Here a value is held as
  value/8 in a 24-bit word, so the range is the same and the quantisation noise is far lower. Clouds' grit is not reproduced.
- **LFOs.** Clouds uses a cosine oscillator updated every 32 samples. This port uses a parabola `4x(1-|x|)` of a phase accumulator
  updated once a block (16 samples), at the same rates (0.5 Hz on the first allpass smear, 0.3 Hz on the second delay), with the
  same depths scaled with the lengths (60 samples for the smear, 97 for the delay, centred at 4531).
- **Smoothing.** The five coefficients move a sixteenth of the way to their target each block (Clouds changes them as they arrive).
- **Memory.** A modulo ring of 15,862 words (`m5 = 15861`). It is not a power of two. Stock code uses small non-power-of-2 moduli
  (6, 10 and 30), but nothing uses one this size with `(Rn+Nn)` addressing; this is the first thing to check on a unit.

## Measured

Under `dsp_host` (`tools/verify/verify_gateverb.py`, remix `test/gateverb`):
- 425 DSP words on each payload; the pricer counts 219 cycles per sample, a floor (it counts words, not memory stalls).
- The first 77 calls pass the input through while the ring is cleared (206 words a call).
- AMNT 0 is bit-exact dry.
- An impulse and a noise burst through 48,000 samples match a float model (gate off, and an impulse with the gate on) of the same algorithm (same lengths, the same integer LFO phases and
  offsets, the same parameter laws and smoothing) to 58 dB (the difference is the 24-bit arithmetic).
- No write outside the 15,862-word ring (`-guard 15862`); a dirty state block and a dirty ring with silent input give silent output.
- TIME 127 rings longer than TIME 80.

Not measured: sound (no listening yet), hardware, the real allocator's bases on a unit.

### The smear LFO is bipolar, and in the model the tail grows from TIME 94 up (5 Nov 2026, model only)

Clouds' LFOs are unipolar: stmlib's `CosineOscillator::Next()` returns `y + 0.5`, 0 to 1, so
Clouds reads `ap1` at 10..70 and `del2` at 4680..4780. This port's parabola is bipolar, ±1
(`gateverb.asm`, "offset 10 + 60 * lfo1"): the smear reads `ap1` at −50..70, so up to 50 samples of
its reads land behind line 0, in the far end of the last tank line, and are written back into the
first input allpass. That is a second feedback path that TIME does not scale. The `del2` tap swings
4531 ± 97, twice Clouds' excursion.

In the float model the module matches to 58 dB (`tools/harness/gateverb_voice.py --impulse`, impulse
after the knobs settle), with every other knob at its default:

| TIME | RT60, the module's LFOs | RT60, Clouds' LFOs |
|---|---|---|
| 64 | 4.84 s | 2.86 s |
| 80 | 6.87 s | 3.78 s |
| 94 | grows | 5.20 s |
| 127 | grows | 17.91 s |

Making the smear alone unipolar removes the growth (TIME 127: 20.9 s, decaying). One click at TIME
120, AMNT 80, gate off, is still at −18.6 dB RMS 11 s later with the module's LFOs and −90.8 dB with
Clouds'. 🟡 Inferred for the module: the 58 dB match was measured over 48,000 samples at TIME 80, not
over seconds at TIME 94 and up. A `dsp_host` render of one impulse at TIME 120 for 10 s, or the same on
a unit, would confirm or falsify it.

## Credit

Emilie Gillet, Mutable Instruments (`pichenettes/eurorack`, MIT). `THIRD_PARTY.md` has the licence row.
