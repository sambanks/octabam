## What it does

MIDI CC numbers stock ignores now reach page 2 of FX1 and FX2. Stock
incoming CC writes page 1 only (CC 16–45).

## The CC numbers

| CC | writes |
|---|---|
| 62–67 | FX2 page 2, slots 6–11 |
| 68–73 | FX1 page 2, slots 6–11 |

## How to use it

Send the CC on a track's channel, with AUDIO CC IN on. The value is
clamped to the slot's range. With MODE DEFAULTS in the image, a MODE
sent over CC re-defaults the knobs around it.

## Notes

- The FX2 block writes BusDelay and BusVerb tracks; other FX2 effects
  are skipped.
- CC 64–67 carry standard pedal meanings (sustain, portamento, sostenuto,
  soft pedal): a sustain pedal on a track's channel writes FX2 page-2
  slot 8 on a bus host.
- The module writes the page the firmware's own editors write; the DSP
  follows the live lane each frame.
