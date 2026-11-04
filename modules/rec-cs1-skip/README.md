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

## Measured

- **Stock's cost.** A PC sampler on Bryan T's MKII put the routine at
  6.4 µs a frame per recording track: the growth from four to seven
  self-recording tracks, 1 Nov 2026. That is two reads and six writes at
  about 0.5 µs each.
- **How many writes are redundant.** Under the ColdFire port, in steady
  play, 358,300 of 358,316 writes stored the value already there.
- **The `[r+300]`/`[r+308]` skips alone, on the MKII.** The routine went
  from 48.0 to 36.4 µs a frame at seven recording tracks.
- **CS1 writes under the port.** A project recording through pattern
  changes, a stop and a start: 468,662 with stock, 317,028 with the first
  kind of skip only, 13,855 with both. All of CS1 (1 MB) and the 44-byte
  records at `0x46c938c4` were byte-identical to stock's at the end.
- **`verify_rec_cs1_skip`.** Stock's routine (from your OS image) and this
  one run side by side under unicorn for 40,000 calls, each on its own
  memory. The calls cover ids 0–9, lengths of 0, under 64, large and
  negative, the flag set and clear, the two tempo words changing, and other
  writers storing into all six fields. The gate holds:
  - the 44-byte records and every byte of the CS1 page are stock's after
    every call;
  - a value another writer stored stands for at most four calls of that
    track;
  - callee-saved registers and the stack are left intact.

  In steady play it counts 2 reads and 6 writes a call for stock, and 2.85
  reads and 1.04 writes for this routine.
- **On hardware.** Bryan T's MKII ran it, with RECORDER LOOP FIX's
  memoised spacing cave, in test builds recording up to eight tracks at
  once (1–2 Nov 2026). Eight self-recording tracks ran at 337 µs of the
  362.8 µs frame. The same test build without these two changes froze the
  unit at eight.

## Inferred, not measured

- **The copy's share on hardware.** The hardware saving from the second
  kind of skip alone was not separated: those builds also carried the
  spacing-cave change.
- **Who writes these fields.** "Only these writers" comes from the port's
  runs and a static search (87 candidate stores at these offsets).
  Something else could store into these fields. If it did, the routine
  would correct it within four calls instead of one.

## The guard

The one difference from stock is the window above, so no selectable
configuration (track count, ids, transport, project load) is left with a
value stock would not hold for longer than four calls of that track: about
a millisecond at one call a frame. The gate measures it. A track with an id
past 7 has no copy and writes as stock.
