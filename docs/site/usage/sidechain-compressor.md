The stock COMPRESSOR with a side-chain and a base-width key filter: any of
tracks 1-8 can drive its detector, so one track's level
ducks another. Page 2 adds a switch to listen to the key, the key itself, its
gain, and a high-pass and low-pass pair that sets the band the detector hears.

The base-width filter isolates the key: a kick's fundamental, for example,
with the high-pass cutting the sub-sonic rumble below it. That reduces distortion and keeps the
compression smooth at short attack and release settings.

## Access

An effect on a track: select the track, press FX2 (or FX1), and pick COMPRESSOR
from the chooser; the setup page shows the new knobs. There is no separate
effect to load: COMPRESSOR is the side-chain compressor.

[Octabam](../../remix-octabam.md) 0.3 does not carry it; COMPRESSOR there is stock. The loader form (the
side-chain's DSP code loaded while a track uses COMPRESSOR, in the top of T4's FX2 block) is in the repository and has
not run on a unit in the current `octabam` form.

The test remixes `sidechain-compressor` and `kyoti-mute-sidechain` carry it the
earlier way, in SPRING REV's words, so SPRING REV is off the chooser in those images.
It does not coexist with BusDelay or BusVerb: their core-private and
cross-core memory overlaps, and the build refuses the pair.

![FX2 SETUP with COMPRESSOR selected, showing RMS, MON, KEY (here T2), KGN, KBAS and KWID.](../../img/sidechain-compressor/chooser.png)

*FX2 SETUP with COMPRESSOR selected, showing RMS, MON, KEY (here T2), KGN, KBAS and KWID.*

## Changed on 25 Oct 2026

MON shows OFF on the left and ON on the right. A COMPRESSOR saved with any
earlier version comes up with MON OFF. KEY moves one position per detent
even with the encoder pressed. The earlier octabam form of this filter
gave silence, level jumps and squeals on KBAS and KWID; that is fixed.

## Changed on 22 Oct 2026

The base-width filter replaced an earlier one-knob filter (KFLT), and page 2
was laid out again: it was RMS, KEY, KFLT, KGN and MON. A COMPRESSOR saved
with the earlier version keeps its KEY, but its other page-2 values now land
on different knobs: KGN gets the old KFLT, KBAS the old KGN, KWID the old MON,
and MON comes up OFF. Such a project sounds different until you set KGN,
KBAS, KWID and MON again. A COMPRESSOR saved on stock firmware is not
affected.

## Operation

- KEY chooses what drives the detector: OFF (the track's own signal, as
  stock) or T1-T8. It is drawn as a nine-position switch, OFF pointing
  left and T8 right, and moves one position per detent, also with the
  encoder pressed. Choosing the compressor's own track keys it from its own
  signal through the filter.
- KBAS is the filter's base: a high-pass at OFF or 20 Hz to 19.6 kHz. Its
  readout is in Hz (`1.2k` is 1.2 kHz).
- KWID is the filter's width (the bracket between KBAS and KWID shows the
  pair): a low-pass this many octaves above KBAS, 0.5 to
  9.9, or OFF. Its readout is in octaves. With KBAS at OFF it counts up from
  20 Hz, so it works as a plain low-pass.
- The two cannot cross: raising KBAS moves the whole band up.
- For a kick: KBAS about 30-40 Hz, KWID about 1.2-1.5.
- KGN is the key's gain, about -24 to +24 dB.
- MON lets you hear the processed key in place of the track: OFF on the
  left, ON on the right. Switching it, or changing KEY while it is on,
  fades (about 6 ms) instead of clicking.
- A key on the same DSP core and earlier in the order (T1 keying T2-T4, T5
  keying T6-T8) reaches the detector with no delay, so a trig on both
  tracks at once clicks less at short attack than a key from the other
  core.
- A COMPRESSOR saved on stock firmware comes up with MON OFF, KEY OFF, KGN
  centred and both filters OFF; one saved with an earlier version of this
  module comes up with MON OFF.
- The key works across the two DSP cores in both directions.
- Beside MUTE_MODES a muted key track keeps feeding the key, as stock mute
  does (MUTE_MODES' SC_KEY build).

## Parameters

| Page | Knob | What it does |
|---|---|---|
| 1 | stock COMPRESSOR | as stock |
| 2 | RMS | stock's |
| 2 | MON | hear the processed key |
| 2 | KEY | OFF or T1-T8 |
| 2 | KGN | key gain, about -24 to +24 dB |
| 2 | KBAS | key high-pass, 18 dB/oct: OFF, 20 Hz to 19.6 kHz (Hz) |
| 2 | KWID | key low-pass, 12 dB/oct, this many octaves above KBAS: 0.5 to 9.9, OFF |

Tested on the author's MKI on 22 Oct 2026 in the author's standalone image:
page 2 and its readouts, a kick's fundamental keyed at short attack and
release, MON and KEY declick. The author's KYOTI V1.6 image, which carries it,
ran on the unit the same day. KEY's switch and the KBAS-KWID bracket ran
there in the standalone image on 23 Oct 2026. This octabam form, with
the key-filter fix, MON's switch and KEY's pressed turn, ran on the author's
MKI on 26 Oct 2026: all good.
