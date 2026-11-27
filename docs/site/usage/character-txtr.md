CharTxtr is a variant of CHARACTER that adds a lo-fi texture stage. Audio flows through fold, texture, saturate, tilt, compress, width, and mix, with all standard CHARACTER parameters unchanged. The new TXTR knob on page 2 adds mu-law companding, bit reduction, sample-and-hold, and blur right after the wavefolder. When TXTR is set to 0, the texture stage is bypassed and the output is bit-identical to standard CHARACTER.

## Access

Select a track, press FX1, and choose CharTxtr from the effect list. It uses DJ EQ's effect ID, so only one module using that ID can be included at a time. This module is not included in the standard remixes; build the `character-txtr` remix to use it. Running four instances alongside the reverb uses 2,751 of the 3,120 available DSP cycles per core.

![FX1 SETUP with CharTxtr selected: TAPE, KEY, KLVL and TXTR on its page 2.](../../img/character-txtr/chooser.png)

*FX1 SETUP with CharTxtr selected: TAPE, KEY, KLVL and TXTR on its page 2.*

## Operation

- TXTR controls the entire texture stage from one knob: 0 turns it off, and increasing it reduces bit depth from 16 down to roughly 4.1 bits, increases the shared stereo sample-and-hold from 0 to 31 samples, and adds blur.
- All other knobs on pages 1 and 2 work the same way as in CHARACTER.

## Parameters

| Page | Knob | What it does |
|---|---|---|
| 1 | DRV, FOLD, WDTH, COMP, TONE, MIX | Same as CHARACTER |
| 2 | SAT, KEY, KLVL | Same as CHARACTER |
| 2 | TXTR | 0-127, default 0: texture amount; 0 bypasses the stage |
