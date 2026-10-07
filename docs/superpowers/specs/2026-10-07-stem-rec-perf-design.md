# STEM REC: less CPU, less card traffic

Branch `stems-perf`, from upstream `main` at `6f9e5bc9`, 7 Oct 2026.
Agreed with Yves in chat on 7 Oct 2026. Section 1 is approved; sections 2
and 3 follow the approach he chose (approach 1, "trim in place") and are
open to correction before they're built.

## Goal

STEM REC uses less CPU in the audio interrupt and less card traffic in its
writer, so that:

- **A.** The busy project of flash C (eleven stereo files at 24 bits, T2 to
  T8 Static machines with all 16 trigs on, scenes on several parameters)
  records without `RING FULL` (STEM_REC.md 17.3).
- **B.** The module costs less while nothing records, since the image
  stays on the unit.

Out of scope this round: the menu (a CAPTURE-style live page is a later
round), Modwerk.

## Constraints

- **Every file stays what today's build writes**, sample for sample,
  headers included. The existing sample-for-sample checks are the proof.
- **One flash at the end** (STEMS4): every optimisation, plus a readout
  that tells card contention from a lack of CPU time (section 3).
- **A take cut off mid-way behaves as today**: its files are left at
  0 bytes. Crash recovery comes only if space reservation gives it for
  free (section 2).
- **Testing:** light and modular while developing (`verify_stems_units.py`,
  `verify_stems.py --static`, a few targeted `--only=` runs); the full
  `make check REMIX=stems`, `--long` and `--fat32` after the work.

## Baseline (measured)

Under the port, at `6f9e5bc9`, 7 Oct 2026 (`/home/yvez/xcheck/perf-baseline.log`):
`verify_stems.py --only=cost`, the same method at T1 to T8, and a
2,000-frame take with `--coverage` for the writer, all on the eight-track
THRU fixture; then `stems_sweep.py --counts 8 --latencies 8,16`.

| Instructions a frame | Measured |
|---|---|
| Frame hook, idle | 1,001 (`stems_mirror` 959) |
| Frame hook, T1 to T8, 16 bits | 5,579 (`stems_track16` 3,360, mirror 959, `stems_tdelay_step` 853) |
| Frame hook, T1 to T8, 24 bits | 6,219 (`stems_track24` 4,000) |
| Frame hook, every source, 24 bits | 7,415 (`stems_bus24` 1,022) |
| Writer routines, T1 to T8, 16 bits | 737 per recorded frame (`stems_drain` 702) |
| Writer routines, every source, 24 bits | 1,067 per recorded frame (`stems_drain` 1,026) |
| Whole CPU while recording | 37,974 to 40,174 |

| Tracks | Card delay | Peak fill | Writer | Fill growth | To overflow |
|---|---|---|---|---|---|
| 8 | 8 | 6% (1,002) | 1.36 MB/s | +97 ± 0 frames/s | 163 s |
| 8 | 16 | 9% (1,435) | 1.31 MB/s | +185 ± 1 frames/s | 83 s |

These match STEM_REC.md 18.9 exactly (5 Oct, `3780665`), so the old
figures hold on today's `main`.

## 1. The frame hook

1. **Each track one frame early.** MAIN at hook frame f is core 0's mix
   of the samples in the half `PING` doesn't name as that half read at
   frame f−1, times the gains of the page sent at f−2 (STEM_REC.md 18.5).
   Both are known at frame f−1. So at frame f the hook:
   - writes MAIN, CUE and the inputs of frame f into ring frame f, which
     the previous frame reserved, and publishes it;
   - then computes each track's share for ring frame f+1, from the half
     `PING` doesn't name now and the gains of the page sent at f−1, into
     the next ring frame.

   The one-frame delay copy (`stems_tdelay_step`, `stems_tdelay`) goes.
   The gain lag becomes 1 (`GAIN_LAG`), and the tracks read the half
   directly (`TRACK_DELAY` 0 in the routines). The files don't change.
   - **The start edge.** A take armed before play stages its first track
     frame on the edge, as the copy did, so it starts on the same frame as
     today. When REC is pressed while the sequencer plays, the page of the
     frame before the press has no per-sample gains (item 2), so that
     take stages one frame later and starts one frame (16 samples) later
     than today. `stems_gqok` counts the frames the mirror has written
     gains for since IDLE; the edge needs two.
   - **The ring.** Staging reserves the next frame, so the ring's room
     test moves to the staging step: a take stops when the next frame
     doesn't fit, at the last whole frame, as today. The staged frame of
     a take that stops is never published.
2. **The mirror writes per-sample gains only while ARMED or RECORDING.**
   `GQ_ALWAYS` was there so a take started while playing had the previous
   frame's gains (2 frames of lag); with a lag of 1 it isn't worth about
   550 instructions in every idle frame. The state (`stems_gstate`) still
   follows every page.
   - The mirror alternates two state buffers instead of copying the
     state to `stems_gstate_prev` every frame; `gains`/`gainsdirty` read
     both, with the index of the current one.
3. **The clamp only when it can act.** A track's share is
   `lim(floor(g·x / 2^21))`; with 0 ≤ g ≤ 0x200000 every result fits, at
   both widths, so the limit can't change it. While it writes a slot's 16
   gains, the mirror tests the ends of each segment it writes (the old
   ramp, the hold, the new ramp: each is linear, so its values lie
   between its ends) and stores a per-slot flag beside the gains. A track
   whose flag is clear runs the loop without the limit; otherwise the
   loop of today. With LEVEL 127 and MAIN level 64 the gain settles at
   `0x1f7fe0`, just under a quarter.
4. **Small trims.** The file table carries each file's routine and
   argument, latched with the layout; the gains' frame is found once a
   frame; the loops do two samples a pass.

Estimated (inferred, MAIN level 64 or lower): idle about 350 to 400; T1
to T8 at 16 bits about 3,100; at 24 bits about 3,700; every source at 24
bits about 5,000.

Examined and left out: **gains stored pre-shifted** (`g << 8`) saves one
`lsl` a sample pair in the track loops but costs about four instructions
a slot in the mirror: about 100 a frame at eight tracks, nothing at one
or two. Optional, last.

## 2. The writer and the card (proposed)

1. **The drain per file, not per frame.** Today it walks every file for
   every frame, recomputing the file's buffer (`stems_sbuf`, a `mulu`),
   its frame size and the format each time. Per file over the whole
   batch, with the ring frame's stride, and unrolled. Estimated: 25 to
   35% off `stems_drain`. The 24-bit byte order stays a byte copy: a
   ColdFire has no rotate, and a register shuffle costs more than
   `move.b` memory to memory (1.5 instructions a byte).
2. **Bigger writes.** `CHUNK_FRAMES` 512 to 1,024: 64 KiB a write a
   stereo 16-bit file, 96 KiB at 24 bits, half the commands. The buffers
   grow from 0.70 MB to 1.38 MB; the stems remix has 1.36 MB free between
   the runtime's stage and the buffers, so the ring's 8 MiB stays. The
   risk: card commands run one at a time (STEM_REC.md 11.8), so a longer
   write delays a Static track's next read. The readout's slowest write
   measures it.
3. **Space reservation, a probe first.** Under the port: how many sectors
   the card takes per raw write beyond the data (FAT and directory
   updates), and whether set length (`0x40018788`, which allocates when a
   file grows, STEM_REC.md 7.10) reserves clusters without writing data.
   Adopted only if it cuts card writes and every file stays identical.
   Crash recovery only if it comes with it.

## 3. The readout (proposed)

`STATS.TXT` in each take's folder, written by the writer after the audio
files are closed, also when the take ends with `RING FULL` or a write
error. Times come from DMA timer 3 (`0xfc07c00c`), the free-running
counter the firmware itself timestamps with: 7.58 ns a count at the
132 MHz bus clock (`modules/cfmeter/meter.s`).

- The take: frames, seconds, files, width, status.
- The ring: PEAK in frames and percent, and the time behind at the peak.
- Card writes: count, total time, mean and slowest; the share of the take
  the card spent writing for STEM REC.
- The writer's copy: total and slowest batch.
- The writer's wake gaps: the longest time between passes while data
  waited.
- The frame hook on the unit: mean and longest time a frame, recording.

How it decides: card writes that fill most of the take's time, with slow
outliers, mean card contention; fast writes with long gaps or a long
hook mean CPU.

## 4. Testing

- While developing: `verify_stems_units.py` (Unicorn, every routine
  against its model), `verify_stems.py --static`, and targeted runs:
  `--only=postfader,postmove,all14,all14w,w24,w16v24,sources,mono,gains,cost`.
- After the work: `make check REMIX=stems`, `verify_stems.py --long`,
  `--fat32`, `verify_stems_menu.py`, then the baseline script again on the
  same port binary for the "after" table, and `make reach RUN=1` on the
  rebased tree before the PR (AGENTS.md).
- New checks: a take started while playing starts one frame later and
  equals MAIN from its first frame; the mirror's clamp flag is never
  clear when one of its slot's gains is outside 0..0x200000; the drain
  equals the old drain byte for byte; `STATS.TXT` parses and its counts
  match the take.

## 5. For later (large changes)

- **Core 0 writes each track's share.** Core 0 already computes `g·x` per
  track in its mixdown (STEM_REC.md 18.2, `P:0x259`-`0x28f`). A DSP patch
  that also stored each product would leave the hook a copy. It changes
  the stock mixdown and payload A, and needs the DSP traps of AGENTS.md.
- **Write straight from the ring (approach 2).** The hook writes each
  file's samples in file byte order into its own region; the writer sends
  them with no copy. Needs the ring written through the uncached alias
  for card DMA, which no emulator models; saves at most the writer's copy
  (2 to 3% of the CPU in use, measured above).
- **Crash recovery**, if the probe in 2.3 shows it needs more than
  reservation.
- **The menu**: a CAPTURE-style live STEMS page (octalab's INPUT.md
  section 10 calls, TUNER's live window as the in-tree precedent).
