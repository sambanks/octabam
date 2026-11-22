# `slow-lfo` — SLOW LFO

LFO MULT gains 1/2X, 1/4X and 1/8X on audio and MIDI tracks: LFOs up to eight times slower than stock allows.

Stock LFO MULT runs from 1X to 64X, so the slowest an LFO can go is SPD 1
at 1X. SLOW LFO adds three values after 64X, **1/2X, 1/4X and 1/8X**, which
run at a half, a quarter and an eighth of 1X. They work on every LFO of the
audio and MIDI tracks, follow the project tempo as stock does, and are
saved in the Part like any MULT value. By Nathan Groth
([@nathangroth](https://github.com/nathangroth)), MIT.

## Knobs

| page | knob | values | what it does |
|---|---|---|---|
| LFO SETUP | MULT | 1X, 2X … 64X, **1/2X, 1/4X, 1/8X** | stock's rate multiplier; the last three run at a half, a quarter and an eighth of 1X |

No new knob: stock's MULT has three more values. Stored as 7, 8 and 9.

## How it works

Each pass the LFO engine adds SPD × tempo to a phase accumulator, counts how
many times the accumulator wrapped (modulus 496125), and shifts that count
left by MULT: MULT is stored as a shift count, 0 to 6. For 7, 8 and 9 SLOW
LFO shifts the engine's step right by 1, 2 or 3 before it is added, and
makes the left shift 0. Values 0 to 6 run stock's displaced instructions
unchanged.

The audio-track engine (`0x4000cfa8`) and its MIDI-track copy
(`0x40003c0e`) each get the same two detours: the rate step (`0x4000cfb0` /
`0x40003c16`, 10 bytes) and the MULT load (`0x4000cfd6` / `0x40003c3c`, 6
bytes). Both LFO pages' MULT counts go from 7 to 10 (pokes at `0x400d38b0`
and `0x400d421c`), and the MULT formatter both pages share (`0x4003bda4`)
prints the three new labels. One DRAM unit of 184 bytes. It keeps no clock
of its own: the step is stock's SPD × tempo.

## Open

- A tempo change while playing, and external MIDI clock (the step is stock's
  SPD × tempo, so it should follow both: 🟡 inferred, not run).
- Saving and reloading a Part with 1/2X.
- A project saved with 1/2X, 1/4X or 1/8X opened without the module: 🟡
  expected to show 128X and run that LFO very fast, as stock reads 7 to 9
  as shift counts. Not tried.
- The MIDI engine under the port (needs a fixture that plays a MIDI track).
- An MKII.

## Compatibility

- The new values sit after 64X, not below 1X: stock's stored values for 1X
  to 64X keep their meaning, so every saved project loads the same.
- No other module on `main` patches these sites (checked 4 Nov 2026);
  the build refuses an overlap by name.
