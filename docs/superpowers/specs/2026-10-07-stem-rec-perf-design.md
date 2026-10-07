# STEM REC: less CPU, less card traffic

Branch `stems-perf`, from upstream `main` at `6f9e5bc9`, 7 Oct 2026.
Agreed with Yves in chat on 7 Oct 2026: approach 1, "trim in place", one
flash at the end, the files unchanged. Built as written below, with the
probe's decisions in 2.3, the writer's priority left at 1, and one
addition from the same day: T8 is not a source while MASTER TRACK is on
(section 6).

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
     than today (`postmove`: 3,840 samples against MAIN, 3,872 before).
     `stems_gqok` counts the frames the mirror has written gains for in a
     row; the edge needs two.
   - **The ring.** Staging reserves the next frame, so the ring's room
     test moves to the staging step: a take stops when the next frame
     doesn't fit, at the last whole frame, as today. The staged frame of
     a take that stops is never published.
2. **The mirror writes per-sample gains only while a take is armed,
   recording or saving, or the sequencer is stopped.** `GQ_ALWAYS` was
   there so a take started while playing had the previous frame's gains
   (2 frames of lag); with a lag of 1 it isn't worth about 550
   instructions in every frame the sequencer plays without a take. The
   state (`stems_gstate`) still follows every page.
   - **Why stopped too** (found 7 Oct 2026, `stream` and `wrap` at lag 40
     for 39): the port arms a take 9.6 samples before the first playing
     frame (`--call-before-play`), so no armed frame came before the edge
     and the take started late. The frame before a take's first playing
     frame is always a stopped frame, so with the gains written while
     stopped an armed-before-play take starts as before however late it
     was armed. Stopped, the audio engine idles, so the cost there doesn't
     matter.
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
2. **Bigger writes, decided by the probe.** `CHUNK_FRAMES` 512 to 1,024:
   64 KiB a write a stereo 16-bit file, 96 KiB at 24 bits, half the
   commands. The buffers grow from 0.70 MB to 1.38 MB; the stems remix has
   1.36 MB free between the runtime's stage and the buffers, so the ring's
   8 MiB stays. The risk: card commands run one at a time (STEM_REC.md
   11.8), so a longer write delays a Static track's next read; the
   readout's longest write measures it. The gain depends on what each
   write call costs beyond its data, which the probe (2.3) counts first:
   if every call also rewrites a FAT or directory sector, halving the
   calls halves those single-sector writes, which are the slow kind on a
   CF card. With 1,024-frame chunks the checks that need two or three
   chunks in a take (`stream`, `cut`, `mask_take`) need longer takes;
   `stream` and `cut` take their length from `CHUNK_FRAMES` already.
3. **Space reservation, a probe first.** Under the port: how many sectors
   the card takes per raw write beyond the data (FAT and directory
   updates), and whether set length (`0x40018788`, which allocates when a
   file grows, STEM_REC.md 7.10) reserves clusters without writing data.
   Adopted only if it cuts card writes and every file stays identical.
   Crash recovery only if it comes with it.

### The probe's result ✅ under the port, 7 Oct 2026

`ot_emu --cmd-log-end` (new) logs every ATA command of a run;
`perf-probe.py` sorts the writer task's writes by the card's FAT16 layout
(the THRU fixture card: 4 sectors a cluster). A 3,028-frame take at T1 to
T8, 16 bits, and a 3,027-frame take at T1:

| Take | Data commands | Their size | Contiguous | FAT writes | Other single sectors |
|---|---|---|---|---|---|
| T1 to T8 | 673 + 1 + 1 | 4 sectors (1 of 2, 1 of 1) | 663 of 677 follow the one before | 2 | 1 |
| T1 | 97 + 1 | 4 sectors (1 of 2) | 96 of 106 | 4 | 4 |

- **One card command a cluster.** Each 64-sector raw write reaches the
  card as 16 commands of one cluster each, even where the clusters are
  contiguous. The command's size is the card's cluster, not the chunk.
- **The FAT is not rewritten a write.** The file layer keeps it in RAM
  (STEM_REC.md 14.1 reads the whole FAT at mount): 2 to 4 FAT writes a
  take. The directory cluster is rewritten once a file at the start (the
  repeated first address in the log) and at the end.
- **The take is one sequential stream on the card.** The files are
  interleaved, but each write takes the next free clusters, so the card
  sees consecutive addresses.

**Decisions:** no bigger chunks (they don't change the command size; they
would only save calls into the file layer, for 0.7 MB and longer checks)
and no reservation (nothing to save: the FAT is cached and the data is
already contiguous). The lever on the unit is the card's cluster size: a
card formatted with 32 KB clusters gets 16 times fewer, 16 times larger
commands than this fixture, for STEM REC's writes and the Static tracks'
reads alike. The readout records the cluster size (`CARD_SPC`,
`0x46107990`) so a take's numbers can be read against it.

### The writer's priority: left at 1 (Yves, 7 Oct 2026)

A lead for flash C's RING FULL, inferred: upstream's CF METER takes
(`docs/firmware/ARCHITECTURE.md`, Bryan T, 4 Oct
2026) found seven distinct STATIC files drive idle to 0.00 %. STEM REC's
writer runs at priority 1 (`TASK_PRIO`), round robin with the engine task
that streams the samples (census row 5, TCB `0x460ddde4`, also priority 1)
and the UI task (row 7) (STEM_REC.md 3.1, 3.5). On the busy project the
writer may get too little of the processor. Options weighed: create it at
priority 2 (a proven create path, as stock rows 6, 8 and 9; the copy, an
estimated ~2 ms a batch, would hold off the streaming); or raise it only
while behind, which needs the set-priority helper `0x40000744`, which has
no caller in the image (STEM_REC.md 3.7). Decision: priority 1 stays this
round; the readout's longest sleep and the card writes' share of the take
tell whether the writer starved, and a later round acts on that.

## 3. The readout (proposed)

`STATS.TXT` in each take's folder, written by the writer after the audio
files are closed, also when the take ends with `RING FULL` or a write
error. Times come from DMA timer 3 (`0xfc07c00c`), the free-running
counter the firmware itself timestamps with: 7.58 ns a count at the
132 MHz bus clock (`modules/cfmeter/meter.s`).

As built, a line each (CRLF):

```
STEM REC STATS 261007-2015
status OK                          (or the error's name: RING FULL, ...)
165375 frames, 60 s, 11 files, 24 bits
ring peak 1234 of 7943 frames
card writes 2584, 41234 ms in all, longest 62300 us
writer copy 1902 ms in all, longest batch 5100 us
writer longest sleep 12000 us, asks 10000
hook mean 41 us, longest 88 us
hook and frame routine mean 290 us, longest 335 us, 165375 frames
card udma 4 mwdma 0
```

- Card writes: the raw write calls of the take (the chunks and the last
  carries); their time in all, so their share of the take, and the
  longest.
- The writer's copy: the ring to the stream buffers, in all and the
  longest batch.
- The writer's longest sleep: it asks K_DELAY for 10 ms; a much longer
  sleep while recording means it waited for the CPU.
- The hook: from its entry to the stock frame routine; then the hook
  with the stock frame routine after it (the frame is 362.8 µs). Timed on
  the frames that publish a ring frame, so their count is the take's.
- The card: the DMA modes the driver chose (11.7); both 0 is likely PIO.

How it decides: card writes that fill most of the take's time, with long
outliers, mean card contention; fast writes with long sleeps, or a hook
and frame routine near the frame's 362.8 µs, mean CPU.

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
- **One card command a run of contiguous clusters.** The file layer
  sends one command a cluster (2.3's probe). Merging a run of contiguous
  clusters into one command would serve every stock read and write, the
  Static tracks' streaming included. A change to the stock file layer,
  so a module of its own, with its own proof.
- **The writer at priority 2**, if the readout shows it starved (above).
- **A bounded card wait.** A card that refuses a PIO write hangs the stock
  driver for good (STEM_REC.md 11.4); upstream bounded its own USB
  ENDPTFLUSH wait (`5757d982`). A bound here is a stock driver patch.
- **WRITE MULTIPLE (0xC5) for PIO cards.** The stock driver has WRITE
  SECTORS (0x30) and WRITE DMA (0xCA) only (STEM_REC.md 11.7, 11.8). A
  DMA card gains nothing; a PIO card would take one interrupt a block
  instead of one a sector. A stock driver change; the port's PIO card
  would show it.
- **The menu**: a CAPTURE-style live STEMS page (octalab's INPUT.md
  section 10 calls, TUNER's live window as the in-tree precedent).

## 6. T8 with MASTER TRACK on (added 7 Oct 2026)

Yves's request: with MASTER TRACK on, T8 should not be selectable for
recording. Measured first (STEM_REC.md 18.8): with MASTER TRACK on,
`T8.wav` equals `MAIN.wav` sample for sample, and T1 to T7 and CUE lead
both by 32 samples.

- T8's row reads `T8 MASTER` while the MASTER TRACK byte (`0x80000034`)
  is set, and its YES does nothing. The frame hook swaps the label when
  the byte changes (`stems_m8check`), so the row is right before the
  writer task exists.
- A take latched with MASTER TRACK on leaves T8 out; T8 alone becomes
  MAIN, so a take always has a file.
- T8's own bit is kept, so its choice returns when MASTER TRACK goes off.
- The 32-sample lead is documented, not corrected (Yves).
- Checks: `verify_stems_units`' `master_t8`, `verify_stems`' `master8`,
  `T8 MASTER` among `verify_stems_menu`'s texts.

## Appendix: the round's measurement scripts

Run from the tree root under WSL, after `verify_stems.py` has built the
image and the fixtures (`STEMS_TEMPLATE` set). They use the image as
built, so they can run beside a `verify_stems` run.

- `perf-baseline.py`: the hook at T1 to T8 (16 and 24 bits), and the
  writer's routines per recorded frame from a 2,000-frame take; with
  `verify_stems.py --only=cost` and `stems_sweep.py --counts 8 --latencies
  8,16` it made the before and after tables of STEM_REC.md 19.1.
- `perf-probe.py`: one take with `ot_emu --cmd-log-end`, its writes
  sorted by the card's FAT16 layout (STEM_REC.md 19.2); `runs.py`: how
  many of the writer's commands follow the one before on the card.
- `master-measure.py`: a MASTER TRACK take of T1, T8, MAIN and CUE,
  each file against MAIN and T8 by cross-correlation (STEM_REC.md 18.8).

### `perf-baseline.py`

```python
#!/usr/bin/env python3
"""perf-baseline.py, run from the tree root after verify_stems has built the
image and the fixtures. Two measurements under the port, by --coverage:

1. The hook at T1-T8, 16 and 24 bits (400 frames, armed before play): the
   same method and fixture as verify_stems's `cost` (STEM_REC.md 18.9 7).
2. The writer: a 2,000-frame take (three 512-frame chunks drained) at T1-T8
   16 bits and at every source 24 bits. Instructions in each module
   routine of the writer side, per recorded frame, and the whole CPU's
   instructions per frame over the same window, for the share.
"""
import sys
sys.path[:0] = ["tools/verify", "tools"]
import verify_stems as vs  # noqa: E402

s = vs.syms()
starts = sorted(set(s.values()))


def spans(names):
    out = []
    for n in names:
        a = s[n]
        nxt = next((x for x in starts if x > a), a + 0x1000)
        out.append((n, a, nxt))
    return out


WRITER = ("stems_task", "stems_ui", "stems_drain", "stems_flush", "stems_start", "stems_finish",
          "stems_sbuf", "stems_sec0", "stems_make_name", "stems_make_folder", "stems_make_file",
          "stems_hdr_fill", "stems_close_all")


def run(tag, src, fmt, frames):
    cov = vs.run_path(tag, "cov")
    vs.port(s, frames, tag=tag, fixture=vs.FIXTURE_THRU, mask=None, dump_blocks=False,
            pokes_before=[(s["stems_tracks"] + 2, src >> 8), (s["stems_tracks"] + 3, src & 0xff),
                          (s["stems_fmt"] + 3, fmt)], extra=("--coverage", str(cov)))
    return cov


for tag, src, fmt in (("pb-cost8x16", 0x0ff, 0b110), ("pb-cost8x24", 0x0ff, 0b111)):
    cov = run(tag, src, fmt, 400)
    per, frames, split = vs.hook_cost(s, cov)
    top = ", ".join(f"{k} {v}" for k, v in sorted(split.items(), key=lambda kv: -kv[1]) if v)
    print(f"{tag}: hook {per} a frame over {frames} frames ({top})", flush=True)

for tag, src, fmt in (("pb-wr8x16", 0x0ff, 0b110), ("pb-wrall24", 0xfff, 0b001)):
    cov = run(tag, src, fmt, 2000)
    per, frames, _ = vs.hook_cost(s, cov)
    sp = spans([n for n in WRITER if n in s])
    split, total = {}, 0
    for line in cov.read_text().splitlines():
        f = line.split()
        if len(f) != 2:
            continue
        a, n = int(f[0], 16), int(f[1])
        total += n
        for name, lo, hi in sp:
            if lo <= a < hi:
                split[name] = split.get(name, 0) + n
                break
    w = sum(split.values())
    top = ", ".join(f"{k} {v // frames}" for k, v in sorted(split.items(), key=lambda kv: -kv[1]) if v)
    print(f"{tag}: {frames} frames; hook {per} a frame; writer routines {w // frames} a frame ({top}); "
          f"whole CPU {total // frames} a frame", flush=True)
```

### `perf-probe.py`

```python
#!/usr/bin/env python3
"""perf-probe.py [frames] [src] [fmt]: the card traffic of one STEM REC take
under the port (perf design 2.3). Runs a take on the eight-track THRU
fixture with `ot_emu --cmd-log-end`, then sorts every WRITE the card took
during the take by the card's own FAT16 layout: the FATs, the root
directory, the data area (a STEM REC chunk, a single sector there, or other
counts). Run from the tree root after verify_stems has built the image."""
import collections
import pathlib
import struct
import sys
sys.path[:0] = ["tools/verify", "tools"]
import verify_stems as vs  # noqa: E402

frames = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
src = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x0ff
fmt = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0b110
tag = f"probe-{src:03x}-{fmt}"
s = vs.syms()
log = pathlib.Path(f"out/stems_runs/{tag}.cmds")
out, _, card, words, _ = vs.port(s, frames + 200, stop_at=frames, tag=tag, fixture=vs.FIXTURE_THRU, mask=None,
                                 dump_blocks=False,
                                 pokes_before=[(s["stems_tracks"] + 2, src >> 8), (s["stems_tracks"] + 3, src & 0xff),
                                               (s["stems_fmt"] + 3, fmt)],
                                 extra=("--cmd-log-end", str(log)))
st, status, _, wr, rd, nfr = words
print(f"{tag}: state {st}, status {status}, frames {nfr}, rd {rd}, wr {wr}")
img = pathlib.Path(card).read_bytes()
# the partition: MBR entry 0's start, else a bare volume
part = struct.unpack_from("<I", img, 0x1c6)[0] if img[0x1fe:0x200] == b"\x55\xaa" and img[0x1c2] else 0
bpb = part * 512
bps, spc, rsv, nfat, nroot, _, _, fatsz = struct.unpack_from("<HBHBHHBH", img, bpb + 11)
fat0 = part + rsv
root0 = fat0 + nfat * fatsz
data0 = root0 + (nroot * 32 + bps - 1) // bps
print(f"card: partition at {part}, {spc} sectors a cluster, FATs {fat0}..{root0 - 1}, "
      f"root {root0}..{data0 - 1}, data from {data0}")
lines = log.read_text().splitlines()
stems = [ln for ln in lines if "STEM" in ln.upper().split("|")[1]] if lines else []
tasks = collections.Counter(ln.split("|")[1].split()[-1] for ln in lines)
print(f"commands: {len(lines)} in the run; by task: {dict(tasks)}")
kinds = collections.Counter()
sectors = collections.Counter()
for ln in lines:
    what, lba, count = ln.split("|")[0].split()[0], *map(int, ln.split("|")[0].split()[-2:])
    task = ln.split("|")[1].split()[-1]
    if "WRITE" not in what.upper():
        kinds[(task, what, "read")] += 1
        sectors[(task, what, "read")] += count
        continue
    where = "fat" if lba < root0 else "root" if lba < data0 else "data"
    size = "chunk" if count >= 32 else "one" if count == 1 else f"{count}"
    kinds[(task, where, size)] += 1
    sectors[(task, where, size)] += count
for k in sorted(kinds):
    print(f"  {k[0]:>10} {k[1]:>12} {k[2]:>6}: {kinds[k]:6} commands, {sectors[k]:8} sectors")
```

### `runs.py`

```python
# runs.py CMDS: the writer task's WRITE commands in order: how many follow
# the previous one on the card (contiguous), and the lengths of the runs.
import collections, sys
rows = []
for ln in open(sys.argv[1]):
    left, right = ln.split("|")
    t = left.split()
    if "WRITE" in left.upper() and right.split()[-1] == "?":
        rows.append((int(t[-2]), int(t[-1])))
cont = sum(1 for (a, n), (b, _) in zip(rows, rows[1:]) if b == a + n)
runs, cur = [], 1
for (a, n), (b, _) in zip(rows, rows[1:]):
    if b == a + n:
        cur += 1
    else:
        runs.append(cur); cur = 1
runs.append(cur)
print(f"{len(rows)} writes; {cont} start where the previous ended; runs of contiguous commands: {collections.Counter(runs).most_common(8)}")
print("first 20:", rows[:20])
```

### `master-measure.py`

```python
#!/usr/bin/env python3
"""master-measure.py: STEM REC's files against each other with MASTER TRACK
on (the one-THRU master fixture: T1 a THRU track, MASTER TRACK set in the
project). A take of T1, T8, MAIN and CUE at 16 bits, T1 sent to CUE; then
each file's left channel against MAIN's and T8's by normalized
cross-correlation over +-64 samples: the lag where it peaks (positive: the
file leads, its sound comes that many samples earlier). Uses the image
already built (no build), so it can run beside a verify_stems run."""
import math
import sys
sys.path[:0] = ["tools/verify", "tools"]
import verify_stems as vs  # noqa: E402

s = vs.syms()
tag = sys.argv[1] if len(sys.argv) > 1 else "mastermeasure"
src = 0x381                                              # T1, T8, MAIN, CUE
log, dump, card, words, _ = vs.port(s, 900, stop_at=180, tag=tag, fixture=vs.FIXTURE_THRU1_MASTER, mask=None,
                                    pokes_before=[(s["stems_tracks"] + 2, src >> 8), (s["stems_tracks"] + 3, src & 0xff),
                                                  (s["stems_fmt"] + 3, 0b110)],
                                    steps=vs.CUE_STEPS, dump_blocks=False)
print(f"{tag}: state {words[0]}, status {words[1]}, frames {words[5]}")
files = {n.upper(): vs.wav16(d)[0::2] for n, d in vs.take_files(card, vs.FIXTURE_THRU1_MASTER)}
print("files:", {k: len(v) for k, v in files.items()}, "peaks:", {k: max(map(abs, v), default=0) for k, v in files.items()})


def lag(a, b, span=64):
    """The lag L where a[i] best matches b[i + L] (a leads b by L samples)."""
    n = min(len(a), len(b)) - 2 * span
    best = None
    for L in range(-span, span + 1):
        xs = [a[i] for i in range(span, span + n)]
        ys = [b[i + L] for i in range(span, span + n)]
        sxy = sum(x * y for x, y in zip(xs, ys))
        sxx = sum(x * x for x in xs) or 1
        syy = sum(y * y for y in ys) or 1
        c = sxy / math.sqrt(sxx * syy)
        if best is None or c > best[1]:
            best = (L, c)
    return best


for ref in ("MAIN.WAV", "T8.WAV"):
    for name in ("T1.WAV", "T8.WAV", "CUE.WAV", "MAIN.WAV"):
        if name != ref and name in files and ref in files:
            L, c = lag(files[name], files[ref])
            print(f"  {name:8} against {ref:8}: leads by {L:4} samples (corr {c:.4f})")
```
