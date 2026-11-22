CHARACTER with a texture stage. The chain is fold → texture → saturate →
tilt → compress → width → mix, and every knob of CHARACTER is unchanged.
The one addition is TXTR on page 2, a lo-fi texture (mu-law companding,
bit reduction, a sample hold and a blur) after the fold. At TXTR 0 the
stage is skipped and the result is bit-identical to the plain station.

## Access

An effect on a track: select the track, press FX1, and pick CharTxtr
from the chooser. It takes DJ EQ's id, which one module can hold. Not in an official
remix; build the test remix `character-txtr`. Four of them beside the reverb price a core at 2,751 of the
3,120 cycles usable.

![FX1 SETUP with CharTxtr selected: TAPE, KEY, KLVL and TXTR on its page 2.](../../img/character-txtr/chooser.png)

*FX1 SETUP with CharTxtr selected: TAPE, KEY, KLVL and TXTR on its page 2.*

## Operation

- TXTR is one knob driving both of the texture's sliders: 0 is off, and
  turning it up quantises from 16 down to about 4.1 bits, lengthens the
  sample hold from 0 to 31 samples (one hold for both channels), and adds
  the blur.
- The rest of the page 1 and page 2 knobs are CHARACTER's.

## Parameters

| Page | Knob | What it does |
|---|---|---|
| 1 | DRV, FOLD, WDTH, COMP, TONE, MIX | as CHARACTER |
| 2 | SAT, KEY, KLVL | as CHARACTER |
| 2 | TXTR | 0-127, default 0: texture amount; 0 skips the stage |
