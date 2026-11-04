MIDI CC numbers that stock ignores now reach page 2 of FX1 and FX2. Stock
incoming CC writes page 1 only (CC 16–45).

## The CC numbers

| CC | Writes |
|---|---|
| 102–107 | FX2 page 2, slots 6–11 |
| 108–111, 14, 15 | FX1 page 2, slots 6–11 |

## Operation

Send the CC on a track's channel, with AUDIO CC IN on. The value is
clamped to the slot's range. With MODE DEFAULTS in the image, a MODE
sent over CC re-defaults the knobs around it.

## Notes

- Only the FX1 block does anything in this image: FX2 page 2 is reached only
  when a track's FX2 is a delay or reverb server, which this image does not
  have. FX1 page 2 works on any FX1 effect except NONE.
- The value is written where the panel's own page-2 editor writes it, so
  the effect follows it on the next audio frame.
