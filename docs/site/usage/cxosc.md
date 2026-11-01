A Buchla-flavoured complex oscillator as a machine-list machine: two-operator
FM with a sine wavefolder, fold symmetry, and modulator feedback. Derived
from Tim Hastie's FM SYNTH engine (ColdFire voice), not an edit of the
SYNTH MACHINE submodule.

## Access

**FUNC + SRC** or **SELECT MACHINE TYPE** → **CX OSC** (after the stock
five). No marker sample. The Part stores FLEX with signature `"CX", 1`.
At most one CX OSC track per Part (one sounding CX OSC track on the active
Part). It cannot share an image with **SYNTH MACHINE** or
**BLACKPYRAMIDS_303**, which use the same machine list. Beside **ANALOG BD**
or **OCTA-303** it shares the list: CX OSC is the row after theirs, and the
list scrolls.

![SRC SETUP: CX OSC selected in the machine list.](../../img/cxosc/setup.png)

## Operation

![CX OSC PLAYBACK: PTCH RATO INDX FOLD SYMM FDBK.](../../img/cxosc/source.png)


- PLAYBACK reads PTCH RATO INDX FOLD SYMM FDBK.
- PTCH is semitones (−64..+63). Pitch is PTCH alone (no FINE).
- RATO is free 0.25..4 on the knob; FUNC snaps the classic ratio table
  (exact Q8 at those detents, including 1.01 / 1.41).
- INDX is FM index and holds (drone with the knob; LFO / p-lock for motion).
  No DEC envelope on the index.
- FOLD is a sine waveshape (dry/wet). Drive rises with the knob; bass
  level is not monotonic (fold order).
- SYMM biases the fold (DC into the folder). Needs some FOLD to matter;
  0 is centered.
- FDBK is modulator feedback (up to about one cycle at 127).
- Mono only. Stock LFO page (all three LFOs). No VOIC / CHRD.

## Parameters

| Page | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| PLAYBACK | PTCH | RATO | INDX | FOLD | SYMM | FDBK |
