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

## Measured

Under the ColdFire port (`ot_emu`), stock 1.40C, 2 Nov 2026. The port runs
the firmware's arithmetic, not the audio.

- ✅ Stock, one second of play, `--watch-pc` on each engine: the audio
  engine ran 66,144 times in 2,756 frames, each of the 24 audio LFOs once a
  frame. The MIDI engine did not run (the project plays no MIDI track).
- ✅ Stock, registers at the MULT load and writes to the live MULT byte: the
  engine reads MULT from `0x80000690 + 48·t + 0x24 + lfo`; `0x4000cb8a`
  copies it each frame from the track's live lane `0x80000810 + 72·t + 0x3e
  + lfo`.
- ✅ Unit preloaded on stock (`verify_slow_lfo --stock`), track 1's LFO 1
  MULT set in its lane, the LFO's phase over frames 100..2100: 1X 760,990;
  2X 1,521,980 (stock); 1/2X 380,995 (0.5007); 1/4X 190,997 (0.2510); 1/8X
  94,984 (0.1248). Within 1 % of 1/2, 1/4 and 1/8.
- ✅ Stock with the lane set to 7: 4,291,710,720. Stock reads 7 as a shift
  count and runs the LFO about 5,600 times faster than 1X, which is why the
  new values sit after 64X and need the module.
- ✅ Unit preloaded, the formatter called directly: 0 → 1X, 3 → 8X, 6 →
  64X, 7 → 1/2X, 8 → 1/4X, 9 → 1/8X, 10 → 128X (stock's clamp).
- ✅ Built into the author's private remix `home-base` 7 (beside BAR LED),
  nothing preloaded: 1X 760,990; 1/2X 380,995; 1/8X 94,984, the same as
  preloaded. `make check` on that remix passes.
- ✅ Cost, 2,756 frames, stock against the unit preloaded: 23,082 ColdFire
  instructions a frame stock, 23,298 with the module; +216 for 24 audio
  LFOs at 1X, about 9 per LFO. 🟡 MIDI LFOs add at most as much again while
  MIDI tracks run (not measured).

Not run under the port: the MIDI engine, the page as drawn, turning MULT
with the encoder, a tempo change, external MIDI clock, saving and reloading
a Part with 1/2X.

## On the unit

**4 Nov 2026, the author's MKI, USB.** The same `unit.s`, packaged and
loaded into RAM by [Modwerk](https://github.com/repeat98/modwerk)'s loader
(its beta base, flashed), not an octabam build. The unit's answers were read
over USB; what the LFOs did is the author's report, and the rates were
judged by ear and eye, not measured.

- Trial: LFO SETUP's MULT shows 1/2X, 1/4X and 1/8X after 64X.
- Second trial, audio track: the LFO slows to the expected rate at each
  value. MIDI track (LFO to an external MIDI device): MULT shows the same
  three values and the LFO slows to the expected rate.
- Kept, then a power cycle: MULT still offers the three values after the
  reboot.
- The loader's self-test: passed (module intact, longest frame 420 µs).
- Removed: MULT stops at 64X, as stock.

This octabam form (`make image REMIX=slow-lfo`) has not been flashed.
The `unit.s` here differs from the copy that ran only in the local label `.stock` (now `.Lstock`), which octabam's per-unit symbol table would otherwise try to place; it assembles to the same bytes (compared 4 Nov 2026).

## Open

- A tempo change while playing, and external MIDI clock (the step is stock's
  SPD × tempo, so it should follow both: 🟡 inferred, not run).
- Saving and reloading a Part with 1/2X.
- A project saved with 1/2X, 1/4X or 1/8X opened without the module: 🟡
  expected to show 128X and run that LFO very fast, as stock reads 7 to 9
  as shift counts. Not tried.
- The MIDI engine under the port (needs a fixture that plays a MIDI track).
- An MKII.

## Gates

- `tools/verify/verify_slow_lfo.py REMIX` (image gate, `make check` for
  every remix that carries SLOW LFO): stages `OT_PROJECT` on a card, boots
  the built image under the port, and requires MULT 7, 8 and 9 to move
  track 1's LFO 1 at 1/2, 1/4 and 1/8 of 1X within 1 %, and the formatter
  to print the five labels. SKIPs without `OT_PROJECT`. `--stock` runs the
  same with `unit.s` preloaded on stock.
- `remixes/test/slow-lfo` carries the module alone.

## Compatibility

- The new values sit after 64X, not below 1X: stock's stored values for 1X
  to 64X keep their meaning, so every saved project loads the same.
- No other module on `main` patches these sites (checked 4 Nov 2026);
  the build refuses an overlap by name.
