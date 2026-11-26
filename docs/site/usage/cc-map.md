This module maps MIDI CC numbers that stock OS ignores to page 2 of FX1 and FX2. Stock OS only accepts incoming CCs for page 1 parameters (CC 16–45).

## The CC numbers

| CC | Writes |
|---|---|
| 102–107 | FX2 page 2, slots 6–11 |
| 108–111, 14, 15 | FX1 page 2, slots 6–11 |

## Operation

With AUDIO CC IN enabled, send any of the CCs above on the target track's MIDI channel. Incoming values are clamped to each parameter's valid range. When MODE DEFAULTS is also included, changing a MODE parameter via CC resets its associated knobs to their defaults.

## Notes

- FX1 page 2 works on any FX1 effect except NONE. FX2 page 2 only applies when a track's FX2 slot hosts a bus delay or reverb server, so in remixes without those servers, only the FX1 CCs take effect.
- Values are written directly to the same memory locations used by the front-panel page-2 editor, so the effect updates on the next audio frame.
