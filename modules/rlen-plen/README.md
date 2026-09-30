# `rlen-plen` — RLEN PLEN

A ColdFire code cave, no DSP code: a new RLEN value past MAX, drawn `PLEN`,
that makes a recording exactly one loop of the track's pattern on the track's
own scale. With TRIG `ONE` and QREC `PLEN`, one REC press records the next
pass and stops.

Why: RLEN counts master-clock 16ths and stops at 64, so a 1/4X track cannot
give its 16-bar pattern a fixed length; MAX has no length and ends at the
next recorder trig (`docs/firmware/RECORDER.md` section 2a), which is what makes a
manual loop need TRIG `ONE2` and a second press.

## Measured

Under the port, `recfix` image, one REC1 + PLAY trig on step 1, RLEN raw 65:

- 64 steps at 1/4X, 120 BPM: 1,411,200 samples = 16 bars, an end post
  (`0x40005e8e`) each pass; the cave rejoins with `d4 = 0x158880` twice per
  frame and the stock MAX/fixed branches no longer run.
- 48 steps at 1/2X, 128 BPM: 496,125 = 6 bars, three passes, an end post each.
- 64 steps at 1/4X, 120 BPM, then a program change to a trig-less pattern:
  the recording stops by itself at 1,411,200 (END frozen there for the rest
  of the run, one end post, no re-arm).
- Without the validator pokes the published byte was 64 and the MAX branch
  ran; with them the file's 65 survives the load.
- The length path is exercised by a sequencer recorder trig, which takes
  the same converter as a manual press.

What the cave relies on (read from the image for the module, 26 Sep 2026):
- The per-frame converter `0x40006da6..0x40006e12` runs while the record's
  length word (`fp@(32)`) is zero; `raw + 1 ≤ 64` takes the tempo product,
  anything above the MAX branch (`d0 = 0x41` at `0x40006db2` on stock). The
  end of a fixed-length recording is posted at `0x40005e8e` (LIMIT
  `0x46c7fe24[track]` := the length); a MAX recording never posts it.
- The stored byte is validated on every bank load at `0x40002c6e` with a
  hard-coded 64 (the file parser `0x400165dc` stores 65, the validator
  writes 64 over it); the setup editor clamps with the descriptor's `min +
  count − 1` (`0x4002efd2`). RECORDING SETUP pushes the RLEN formatter
  itself (`pea 0x4002f224` at `0x4002fb12`; the descriptor's slot-2
  formatter word is 0).
- Pattern length and scale, from the sequencer's step function
  `0x4009da20`: record `0x400eb034 + p × 0x8ed8 + b × 0x9b340` (scale at
  +0, length at −1, a flag at +1 selecting the track record `0x400e21e0 +
  t × 0x91a` + the same offset, length +0x50, scale +0x51); ticks per step
  from `0x400aba50`; the blob pointer `[0x46c82456]` read `0x400e21e0`.

Raw 0..64 keep their meaning; saved parts need no restamp. RECORDER SPACING
is bypassed on the PLEN path (its next-arm model is for chained sequencer
passes).

## Measured (port, recfix image, one REC1 + PLAY trig on step 1, RLEN raw 65)

- 64 steps at 1/4X, 120 BPM: 1,411,200 samples = 16 bars, an end post
  (`0x40005e8e`) each pass; the cave rejoins with `d4 = 0x158880` twice per
  frame and the stock MAX/fixed branches no longer run.
- 48 steps at 1/2X, 128 BPM: 496,125 = 6 bars, three passes, an end post each.
- 64 steps at 1/4X, 120 BPM, then a program change to a trig-less pattern:
  the recording stops by itself at 1,411,200 (END frozen there for the rest
  of the run, one end post, no re-arm).
- Without the validator pokes the published byte was 64 and the MAX branch
  ran; with them the file's 65 survives the load.
- The length path is exercised by a sequencer recorder trig, which takes
  the same converter as a manual press.

The watches are `docs/firmware/RECORDER.md` section 2a's.

## On the unit

An MKII, OCTABAM2 = `bottleservice-rec-plen`, 29 Sep 2026, as a DRAM unit:
PLEN drawn, one-press single-loop takes at 1/4X and 1/8X, PLEN kept through
Octakit's Kit save / load / reload -- by ear and panel, not captured. PER
TRACK mode not tried.

## Open

- The drawn `PLEN` text on the setup screen.
- A manual REC press under the port (the key handler is not located).
- PER TRACK mode: the cave reads the track's own length × scale; the master
  length is not considered (a fixture with master 16 / 1X restarted the
  track every 16 master steps while the cave computed the track's 32 steps
  at 1/8X). Whether one loop should be the track's or the master's is open.

## The cave

    T = clamp(len, 2..64) × ticks[scale]        ticks = 3 4 6 8 12 24 48 (2X … 1/8X)
    L = round(T × 2,646,000 / tempo24)           samples (one tick = 1/24 beat)

Length and scale come from the pattern the sequencer is playing (`0x800065bd`
bank, `0x800065be` pattern), the pattern's own pair or, in PER TRACK mode, the
recording track's. Three entries in one cave:

- hook `0x40006da6` (the arm converter's RLEN read, replayed): raw 65 computes
  `L` and rejoins the fixed-RLEN path at `0x40006e18` with `d4 = L`; anything
  else returns to stock.
- poke `0x4002fb10`: the RECORDING SETUP drawer pushes the cave's formatter
  instead of the stock one; the formatter draws `PLEN` for 65 and tail-calls
  stock (`0x4002f224`) for the rest.
- poke `0x400d3d4e`: the descriptor's RLEN count 65 → 66 (the editor clamps by
  it).
- pokes `0x40002c72`/`0x40002c78`: the part validator's hard-coded RLEN max
  64 → 65 (it runs on every bank load and would rewrite a stored 65 to MAX).

Raw 0..64 keep their meaning; saved parts need no restamp. RECORDER SPACING
is bypassed on the PLEN path (its next-arm model is for chained sequencer
passes).
