# `verberation` — VERBERATION

A reverb for FX2, rooms to halls, with a desk-style gate, built on the reverb stage of Mutable Instruments Clouds
([`clouds/dsp/fx/reverb.h`](https://github.com/pichenettes/eurorack/blob/master/clouds/dsp/fx/reverb.h),
MIT, Emilie Gillet 2014), ported to fixed point. On id `0x1a` (PLATE REV keeps `0x14`); one instance per FX2 slot.

Until 6 Nov 2026 this module was GATE VERB (`modules/gateverb`), then briefly STUDIO VERB (`modules/studioverb`, #1056; `git log --follow -- modules/verberation/verberation.asm`
has its history). It keeps GATE VERB's id, so a Part that used GATE VERB opens VERBERATION. The sections below that
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
| 3 GATED | 64 | 80 | 118 | 110 | 80 | 26 | 40 | 64 | 64 | 90 | 20 (14.5 ms) | gated |

GATED was AMNT 90 with no predelay until 6 Nov 2026. AMNT is a crossfade, so at 90 the dry hit was down 10.5 dB and the
wash, starting within milliseconds, buried it: on the backbeat the snare's first 5 ms peaked 6.0 dB over the wash
(50-200 ms after the hit). At AMNT 64 with 14.5 ms of predelay it is 14.8 dB over (float model; chosen by ear from
four renders).

Slots 0-4 are Clouds' five setters (`set_amount`, `set_input_gain`, `set_time`, `set_diffusion`, `set_lp`).
Page 2 is this port's (5 Nov 2026); at its defaults the module computes exactly what it did before, and
the ring layout does not move (SIZE shortens reads, not the layout). A Part saved before page 2
existed holds 0 in those slots: MODE ROOM, SIZE 0, MOD 0, RATE 0, a small static room. Re-pick the effect or
stamp the defaults to get the original sound back.
The ranges and defaults are this port's, taken from the values Clouds sets in `granular_processor.cc`
and `reverb.h`; they have not been compared by ear.

## The rows on the stock reverbs' ids

[`octabam-verbs`](../../remixes/octabam-verbs/README.md) gives up PLATE REV, SPRING REV and DARK REV and puts three
rows of this module on their ids: [VERB PLATE](../verberation-plate/README.md) (`0x14`, PLATE mode),
[VERB ROOM](../verberation-room/README.md) (`0x15`, ROOM) and [VERB HALL](../verberation-hall/README.md) (`0x16`,
HALL). Each is a chooser row with its own name and its mode's defaults and no code of its own: `MenuEntry.dsp_of`
points the id at this module's init and proc (the build reports `id 0x14 -> VERBERATION's code`, and a dump of
both payloads reads the same two entry points for 0x14, 0x15, 0x16 and 0x1a). One copy of the code, 644 words a
payload, serves all four rows.

A Part saved with a stock reverb opens on its row at the row's defaults: [VERB PARTS](../verb-parts/README.md)
rewrites its FX2 pages as the firmware applies it (the sign of such a Part: page-2 slots 9 and 10 both 0, which
the stock reverbs never draw).

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

## Credit

By sambanks. The algorithm is Emilie Gillet's, Mutable Instruments (`pichenettes/eurorack`, MIT): the reverb stage of
Clouds, its topology, delay lengths (before the scaling above), the five setters' laws and the LFO rates and depths. No
code is carried: this is DSP56300 fixed-point assembly written from that design. The gate, page 2 and its four modes,
the 24-bit storage, the LFO shape, the smoothing, the ring layout and the smear fix are this module's. Zac-Kyoti sized
the ring under octabam's window rule (18 Oct 2026); Yves Rosius made the bit-identical tap passes (19 Nov 2026).
`THIRD_PARTY.md` has the licence row.
