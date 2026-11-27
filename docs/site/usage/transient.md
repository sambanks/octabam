TRANSIENT is a level-independent transient shaper. ATCK boosts or softens each
onset, while SUST lengthens or tightens each tail. Because the detector tracks
envelope shape rather than absolute amplitude, there is no threshold knob and
quiet hits are shaped the same way as loud ones.

## Access

Select a track, press FX2, and choose TRANSIENT from the chooser. All five
knobs are on page 1.

## Operation

- Raising ATCK adds punch to drums and plucks; lowering it softens the attack.
- Raising SUST brings out room ambience and ring; lowering it dries out and
  tightens a loop.
- TIME sets how long an onset is treated as the transient, scaling
  logarithmically from 5 ms at 0 to 50 ms at 127.
- OUT trims the output level. MIX blends dry and wet signals, with 0 as an
  exact passthrough and 127 as full wet.

## Parameters

| Knob | Range | Default | What it does |
|---|---|---|---|
| ATCK | -64..+63 | 0 | onset gain: +63 is +12 dB, -64 is -12 dB |
| SUST | -64..+63 | 0 | tail gain: +63 is +12 dB, -64 is -12 dB |
| TIME | 0..127 | 40 | how long an onset counts as the transient (5–50 ms) |
| OUT | -64..+63 | 0 | output trim, -12 to +12 dB |
| MIX | 0..127 | 0 | dry/wet; 0 is an exact passthrough, 127 full wet |
