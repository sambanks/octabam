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

## Open

- A tempo change while playing, and external MIDI clock (the flash is
  stock's, so it should follow both: 🟡 inferred, not run).
- Pause and continue; a pattern change while playing.
- Per-track mode with a MASTER LENGTH (INF would leave only the green after
  PLAY).
- Pattern scales other than 1x.
- An MKII.
- A pattern no longer than one beat (1, 2 or 4 steps at 1x) is green only
  on the first flash after PLAY, then red on every beat: each flash sees
  step 0, so the step never drops. ✅ 4 steps under the port (the gate's
  length poke, reported in review of #1046: `G@0 r@0 r@0 r@0 …`); 8 steps
  at 2x 🟡 inferred from the arithmetic, not run. Counting step ≤ the last
  flash's as a new pass (`bhi` in place of `bcc`) would fix it, but would
  also turn green every flash inside step 0 at a slow scale where one step
  spans several beats. A fix that gets both right needs a second signal,
  such as the tick within the step at other scales; not measured.
