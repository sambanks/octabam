ANALOG BD is a track machine with two synthesized kick-drum engines (808 and 909) that run on the DSP before the stock AMP and both FX slots. It uses pure synthesis with no embedded samples, and all eight tracks can run independent patches.

## Access

Double-tap an Analog BD track to open the engine browser, which lists the 808 and 909 models like a sample pool. Use UP/DOWN or LEVEL to browse, YES to select, and NO to cancel. Pressing LEFT returns to the machine list, and pressing RIGHT on ANALOG BD reopens the engine browser. Switching between 808 and 909 preserves your current knob settings rather than loading a preset.

This module is not included in the standard remixes. Build the `analog-bassdrum` remix to use it on its own, or build `machines` to include it alongside [DRUMMER](drummer.md) (which expands the machine list to seven scrollable rows).

## Operation

- The 808 engine starts near 49 Hz with a falling pitch envelope and decay times from roughly 16 to 340 ms. ATK controls the attack transient, TONE shapes its brightness, and SWEEP sets the pitch envelope depth.
- On the 909 engine, PITCH spans 30 to 100 Hz, TUNE sets the pitch envelope duration, TDEP sets the pitch envelope depth, and ATK controls the shaped pulse/noise transient. Release ranges from about 9 to 454 ms.
- Both engines share an output desk stage and low-pass filter. SAT adds saturation drive, and LOW and HIGH are neutral at 64. LPF is off at 0, starts at 500 Hz at 1, reaches about 6.57 kHz (ORIG) at 64, and opens to 18 kHz at its default value of 127.
- Track volume is controlled on the stock AMP page.
- If an older patch has both LOW and HIGH set to 0, turn them up to hear audio output.
- Loading a project that contains Analog BD tracks on stock OS clamps the setup parameters, so keep a separate copy of projects you plan to open on stock firmware.
- Eight tracks of 808s, eight tracks of 909s, and mixed combinations all work with FILTER and DARK REV, but eight 909s with DJ EQ in both FX slots produced silent output in testing. Running all eight voices does not guarantee headroom for every effect combination.

## Parameters

| Page | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| 808 SRC | PITCH | DECAY | TONE | ATK | SWEEP | SAT |
| 909 SRC | PITCH | DECAY | TUNE | ATK | TDEP | SAT |
| SRC SETUP (both) | -- | ACCNT | LPF | LOW | HIGH | -- |
