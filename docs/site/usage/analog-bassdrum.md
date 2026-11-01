A track machine with two kick-drum engines, 808 and 909, running on the
DSP upstream of the stock AMP and both FX slots. No recordings are
embedded. All eight tracks can hold independent patches.

## Access

Double-tap an Analog BD track to open the engine browser (a sample-pool
style list with 808 and 909 rows). UP/DOWN or LEVEL browses, YES selects,
NO cancels. LEFT returns to the machine chooser; RIGHT on ANALOG BD opens
the engine pool again. Selecting a model keeps the existing knob values
rather than loading a preset. Not in an official remix; build the test
remix `analog-bassdrum`, or `hooks-machines` to have it beside
[OCTA-303](octa303.md) (the machine list then has seven rows and scrolls),
or `hooks-machines-all` with [CX OSC](cxosc.md) as well (eight rows).

## Operation

- The 808's body starts near 49 Hz with a falling pitch envelope and
  decay times of about 16-340 ms. ATK sets the transient, TONE shapes it,
  SWEEP the pitch excursion.
- The 909: PITCH spans 30-100 Hz, TUNE sets the pitch-envelope duration and
  TDEP its amount, ATK the shaped pulse/noise transient. Release is about
  9-454 ms.
- Both engines share the desk stage and output LPF: SAT drives; LOW and
  HIGH are neutral at 64; LPF is off at 0, 500 Hz at 1, about 6.57 kHz
  (ORIG) at 64 and 18 kHz at the new-assignment default of 127.
- Volume stays on the stock AMP.
- An old patch with both desk bands at zero needs them raised to be heard.
- A project saved with Analog BD tracks, loaded on stock, clamps the setup
  controls; keep a separate project copy for stock.
- All eight 808s, all eight 909s and mixed models passed FILTER + DARK in
  tests; eight 909s with DJ EQ in both slots produced silent output.
  Eight voices do not guarantee every effect combination.
- A MK1 report (28 Sep 2026) had all parameters working with no glitches
  on the first image; the current engine browser and eight-track changes:
  cursory testing on Sam's MKII (owner report, 16 Oct 2026).

## Parameters

| Page | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| 808 SRC | PITCH | DECAY | TONE | ATK | SWEEP | SAT |
| 909 SRC | PITCH | DECAY | TUNE | ATK | TDEP | SAT |
| SRC SETUP (both) | -- | ACCNT | LPF | LOW | HIGH | -- |
