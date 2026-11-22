# `rec-cs1-skip` — REC CS1 SKIP

Every recording track costs the ColdFire time in each frame interrupt. Part
of it is the recorder's control-record update (stock `0x4000432c`), which
the write path calls about 1.5 times a recording track a frame. Each call
reads two fields of the track's record in CS1 (`0x100d38f0 + 1096 × id`) and
writes six. CS1 is slow, about 0.5 µs a read or a write on a MKII, and in
steady play almost every one of those writes stores the value already
there.

This module replaces the routine with one that does the same arithmetic
and skips a write when CS1 already holds the value. Nothing on the panel
changes. A recording costs less, which leaves room for more recording
tracks at once.

## How

`skip.s` is stock's routine, instruction for instruction, with the writes
made conditional:

- **`[r+300]` and `[r+308]`.** The routine reads both for its arithmetic. A
  write is skipped when the value read equals the new one, so CS1 ends as
  stock leaves it.
- **`[r+276]`, `[r+280]`, `[r+296].b` and `[r+304]`.** Skipping these would
  need a read each, which costs what the write does. Instead `rcs_m[id]`
  (ids 0–7) keeps a copy in DRAM, and a write is skipped when the copy says
  CS1 already holds the value. Other code also writes these fields (project
  load, the engine and arm tasks). So each call reads one of the four from
  CS1, in turn, and a mismatch drops the copy: that call writes all four
  again. Any other id writes all four, as stock.

`RCS_MIRROR 0` in `skip.s` keeps only the first kind.

## The guard

The one difference from stock is the window above, so no selectable
configuration (track count, ids, transport, project load) is left with a
value stock would not hold for longer than four calls of that track: about
a millisecond at one call a frame. The gate measures it. A track with an id
past 7 has no copy and writes as stock.
