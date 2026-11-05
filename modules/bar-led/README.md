# `bar-led` — BAR LED

The tempo LED flashes green on the pattern's 1 while the sequencer plays; every other beat stays stock red.

A visual downbeat for players who can't use the click track (when the cue
outputs feed external effects, the click goes with them). It reads the
sequencer's own step, so the green follows the pattern's length and scale.
Stopped, the LED is stock. Nothing to set: no menu row, knob or effect slot.
By Nathan Groth ([@nathangroth](https://github.com/nathangroth)), MIT.

## How it works

Stock flashes the tempo LED from its clock-message loop: every 24 clock
ticks (one beat) it calls `set_led(38, 3)` (`0x40013784`), which lights LED
id 38, the red half of the tempo LED, for three 120 Hz ticks. The panel
numbers each two-colour LED as a red id and the green id after it, as the
trig and track LEDs do, so 39 is the green half.

BAR LED takes that one call (`0x40056f24`, a `jsr` detour to a DRAM unit of
64 bytes). While the transport plays (`0x800065b8` = 1) it reads the master
step (`0x800065b4`, the step now playing, which wraps at the pattern's
length). A flash that sees a lower step than the flash before is the first
since the pattern came round: it passes 39 instead of 38. So does the first
flash after PLAY (stopped, the last step is rearmed to −1). Then it
tail-jumps to stock's `set_led` with the same duration. Every other call,
stopped included, reaches `set_led` unchanged. It keeps no clock or count of
its own: the flash is stock's and the step is the sequencer's.

## Measured

Under the ColdFire port (`ot_emu`), stock 1.40C, 2 Nov 2026. The port shows
which LED ids the firmware asks for, not what the LED shows.

- ✅ Stock, `--sequencer --internal-clock`, the beat-flash call and writes to
  the transport word `0x800065b8`: the word becomes 1 before the first
  flash, then one flash per beat, each `set_led(38, 3)`; no flash before the
  transport starts.
- ✅ Stock, writes to `0x800065b2..0x800065b7`: `0x800065b6` counts ticks
  within a step (0..5 at 1x); `0x800065b4` is the master step now playing,
  `0x800065b2` the next. The master step is written before that step's beat
  flash and wraps at 16 on the 16-step pattern; with pattern A01's length
  (bank RAM `0x400e21e0 + 0x8e53`) poked to 12 it wraps at 12. Falsified
  by a step that is written after its flash.
- ✅ Unit preloaded on stock at `0x400d24d0`, a `jsr` to it at
  `0x40056f24` (`verify_bar_led --stock`), every master-step write and
  every `set_led` call returning to `0x40056f2a`: green (39) on every flash
  at step 0, red (38) on every other, each for 3 ticks. 12 steps
  `G@0 r@4 r@8` repeating, 16 `G@0 r@4 r@8 r@12`, 20
  `G@0 r@4 r@8 r@12 r@16`.
- ✅ The same, length 14: `G@0 r@4 r@8 r@12 G@2 r@6 r@10 G@0 …`. The
  pattern's 1 falls mid-beat every other pass, and the green comes on the
  first flash after it.
- ✅ Built into the author's private remix `home-base` 5 (the unit linked at
  `0x40ac1384`), nothing preloaded, on the built `mainos_bus.bin`: 16 steps
  `G@0 r@4 r@8 r@12` repeating, 12 steps `G@0 r@4 r@8` repeating.
- ✅ Static, the decoded 1.40C: no `pea 0x27` before a call to `set_led` or
  the other LED writers (`0x400136f4`, `0x400131a0`, `0x400131c8`), so
  stock passes no literal 39 and the module lights an LED stock leaves
  alone. 🟡 Computed ids were not traced.
- 🟡 Cost, from the source: at most 11 ColdFire instructions before stock's
  `set_led`, once per beat, in the clock-message loop. No per-frame work,
  no DSP code, no project or battery-RAM bytes. Not measured.

Not run under the port: STOP then PLAY again, pause and continue, a tempo
change, external MIDI clock, a pattern change, per-track mode with a MASTER
LENGTH, pattern scales other than 1x.

## On the unit

The author's MKI. Both runs are the author's report of what the LED did.

- **2 Nov 2026, card build.** The private octabam remix `home-base` 5
  (octabam-home commit `404ef7bd`, carrying this `unit.s`), booted from the
  card through REMIX SWITCH (`/BRAIN/REMIXES/HOMEBAS5.RMX`, SHA-256
  `72a71149…4126eb`), not flashed. Before it, TEST mode lit the tempo LED
  red, green and amber.
  - Stopped: the tempo LED blinks red, as stock.
  - Playing: green on the first beat of the pattern, red on the others.
  - The remix's other sequencer play modes: green only on the pattern's
    first step in each.
  - Master length 17 steps: green on the right step on every pass.
- **4 Nov 2026, USB.** The same `unit.s`, packaged and loaded into RAM by
  [Modwerk](https://github.com/repeat98/modwerk)'s loader (its beta base,
  flashed), not an octabam build. The unit's answers were read over USB.
  - Trial, 120 s: playing, green on the 1 and red on the other beats;
    stopped, red only; after the trial rolled back, red only, as stock.
  - Kept, then a power cycle with the transport stopped through the boot:
    green on the 1 after the reboot.
  - Removed: red only, as stock.
  - Kept again, the loader's self-test with the transport stopped: passed
    (module intact, longest frame 391 µs).

This octabam form (`make image REMIX=bar-led`) has not been flashed.
The `unit.s` here differs from the copy that ran only in the local labels `.playing` and `.red` (now `.Lplaying`, `.Lred`), which octabam's per-unit symbol table would otherwise try to place; it assembles to the same bytes (compared 4 Nov 2026).

## Open

- A tempo change while playing, and external MIDI clock (the flash is
  stock's, so it should follow both: 🟡 inferred, not run).
- Pause and continue; a pattern change while playing.
- Per-track mode with a MASTER LENGTH (INF would leave only the green after
  PLAY).
- Pattern scales other than 1x.
- An MKII.

## Gates

- `tools/verify/verify_bar_led.py REMIX` (image gate, `make check` for
  every remix that carries BAR LED): stages `OT_PROJECT` on a card, boots
  the built image under the port at pattern lengths 12, 16 and 20, and
  requires green on step 0 and red on every other flash. SKIPs without
  `OT_PROJECT`. `--stock` runs the same with `unit.s` preloaded on stock.
- `remixes/test/bar-led` carries the module alone.
