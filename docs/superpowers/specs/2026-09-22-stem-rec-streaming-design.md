# STEM REC: streaming, and eight tracks in the code

**Status.** Design, approved in conversation on 22 Sep 2026 (Yves). Not
built. It replaces the write-after-stop design of
`2026-09-10-stem-rec-poc-design.md` sections 5 to 8. The rest of that
spec (the menu row, the states, the tap's hook site) still holds unless
this document says otherwise.

**Goal.** STEM REC writes each take to the card while it records, so a
take can run until STOP. The code handles all eight tracks, one WAV per
track. Only T1 is enabled for now. This ships in Flash 13, in place of the
tag 27 image.

Terms used below:

- **Frame.** 16 samples, one audio interrupt, about 363 µs.
- **Read-back block.** Where the DSP leaves each track's post-effects
  audio every frame: track k (0-based) at `0x80003190 + half × 0x400 +
  k × 0x80` (`STEM_REC.md` 9.2, corrected 22 Sep 2026).
- **Raw file routines.** The file layer's own routines, reached through
  the function table at `0x46c823fa`. Each takes the file-system lock
  (`FS_LOCK`) itself (`STEM_REC.md` 7.2). The buffered API that STEM REC
  uses today calls them underneath.
- **Uncached alias.** The same RAM seen at `+0x08000000`, where the
  processor's data cache is bypassed (`PLAN.md`, "The RAM").

## 1. Decisions

| Question | Decision |
|---|---|
| When is the take written? | While it records (streaming). |
| How long may a take be? | Until STOP, with a 60-minute safety cap. |
| Which tracks? | A build-time mask. `TRACKS = 0x01` (T1 only) ships. |
| Layout on the card | One stereo 16-bit WAV per track: `T1.wav` … `T8.wav` in the take's folder. |
| If the card falls behind | Stop cleanly at the last complete frame, finish the files, and record an overflow status. |
| File-layer access | The raw routines, from STEM REC's own buffers. Never the buffered API and its shared buffer `0x4ecd3000`. |

Why raw routines: the buffered API passes every flush through one
unlocked buffer that stock's own saves share (`STEM_REC.md` 7.5 and 7.5a).
Writing whole sectors from STEM REC's own buffers takes STEM REC out of
that race, and it makes the header fix simple (section 5).

## 2. The track mask

`stems_tracks` is a word in the module, an 8-bit mask, bit k for track
k+1, default `0x01`. The frame hook latches it at the ARMED → RECORDING
edge, with the count of set bits (`NTRACKS`) and the ring's geometry for
that count. A mask of 0 counts as T1. Every per-track loop below runs over
the latched bits in order, T1 first. A frame in the ring is
`NTRACKS × 64` bytes. (Amended 22 Sep 2026: the build cannot pass
assembler symbols per unit, so the mask is a word a test can poke.)

Enabling more tracks later is a change to `TRACKS` plus the port tests in
section 8. No other code changes.

## 3. The frame hook

Same site (`0x40004b12`), same states. Changes:

- **Per track.** While RECORDING, for each enabled track k, copy its 16
  stereo samples from the read-back block (`k × 0x80` into the half), the
  top 16 bits of each, big-endian, into the ring.
- **Overflow is a clean stop.** Before copying, the hook checks that the
  ring has room for a whole frame (`wr − rd ≤ RING_SIZE − frame`). If it
  hasn't, it sets `ERR_OVERFLOW` and FINISHING, and copies nothing. The
  take ends at the last complete frame.
- **No 15-second limit.** The hook moves RECORDING to FINISHING when the
  sequencer stops (the transport word is not 1), when the frame count
  reaches the 60-minute cap (`60 × 60 × 44100 / 16 = 9,922,500` frames),
  or when the menu row stops it.

The hook still calls nothing and uses no RTOS service. Its cost grows with
`NTRACKS`: about 122 instructions per frame today, measured again for 1 and
8 tracks (section 8).

## 4. The ring

4 MiB, where it is today (the top of the platform reserve). It becomes a
jitter buffer: it absorbs the card's pauses while the writer drains it.
At T1 only it holds about 24 s; at eight tracks, about 3 s.

## 5. The writer task

Same task, priority, stack, and sleep as today. Its states:

**ARMED.** Nothing on the card yet. A cancel from ARMED leaves nothing
behind.

**RECORDING starts.** On its next wake, the task:

1. Builds the folder name from the clock, as today, and refuses an
   existing name with `ERR_EXISTS`, as today.
2. Creates `<set>/AUDIO/YYMMDD-HHMM` with the folder routine, as today.
3. For each enabled track, opens `Tn.wav` with the raw open, and writes
   sector 0: a placeholder header (sizes 0) and the first 468 bytes of that
   track's audio once they exist. Until 468 bytes of audio exist, sector 0
   waits, and the first sector write happens with the first chunk.

The first frames of the take wait in the ring meanwhile.

**RECORDING.** Whenever the ring holds at least one chunk (32 KiB per
track), the task takes it, splits it per track, swaps each sample to
little-endian, and writes each track's part as whole sectors with the raw
sector write. Each file's first sector keeps a 512-byte copy in memory:
the header's 44 bytes plus the first 468 audio bytes. Because of those 44
bytes, a track's audio never lines up with sector boundaries: each track
keeps a carry of up to 511 bytes that didn't fill a sector, and the next
chunk starts by completing it. Between chunks, the
task sleeps (10 ms, the existing sleep).

**FINISHING.** The task drains the ring, then for each file:

1. Writes the last partial sector, padded with zeros.
2. Seeks to 0 with the raw seek and rewrites sector 0 from its copy, now
   with the real sizes.
3. Sets the file's length to exactly `44 + data` with the set-length
   routine.
4. Closes the file with the raw close.

Then IDLE, and the row can arm again.

**The card's buffers.** The task's sector buffers (one chunk per enabled
track, plus the eight sector-0 copies) sit in the platform reserve, below
the stack, and the task hands the raw write their **uncached** addresses.
On the DMA path the hardware reads the buffer directly (`STEM_REC.md`
11.8), so a cached write not yet in RAM would reach the card stale.

## 6. Errors

Status codes stay: 1 overflow, 2 path, 3 open, 4 exists, 5 write, 7 close,
8 task. 6 returns as `ERR_SEEK`, for the seek in the header fix. After an error mid-take, the task still runs the FINISHING steps
on every file it opened, so what reached the card stays playable. A file
whose sector-0 rewrite fails keeps its placeholder header. Its data is
still on the card.

## 7. What gets measured first

The raw routines are known from how the buffered layer calls them, not
from their own tests. A first phase measures each one under the port, and
nothing else is built until they hold:

| Routine | Slot | To settle |
|---|---|---|
| Open | `0x46c8242a` | the handle; behavior with a new path in `"w"` mode |
| Sector write | `0x46c82402` | the arguments (handle, buffer, sectors, as called at `0x40016718`); whether the file position advances |
| Seek | `0x46c8243e` | a seek to 0 on a file with data, then a one-sector rewrite, leaves the rest intact |
| Set length | `0x46c82436` | sets the exact byte length, including one that ends partway through a sector |
| Close | `0x46c82422` | closes; the file reads back at that length |

Each has a falsifier and a port test that reads the card image back byte
for byte. If any routine behaves otherwise, the design goes back to Yves
before anything is built on it.

The port cannot show two things. They go in the flash notes as open:

- **The uncached alias on the DMA path.** The port does not run DMA. The
  alias itself is proven on hardware (Octakit writes through it).
- **A real card's speed.** One track is 176 KB/s. Eight would be
  1.4 MB/s, untested, and not enabled.

## 8. Verification

All under the port, in `verify_stems.py`, reading the card image back:

- **T1, the shipping mask.** The tap check and "T1's slot is the only
  core-1 slot with sound" stay. A 20-second take (`--long`: past the old
  15 s): the file equals the recorded frames byte for byte, the header is
  right, and the length is exactly `44 + data`. It proves streaming past
  the old 15 s.
- **The ring's wrap.** A take started with the ring offsets poked near its
  end.
- **Stops.** By the row; by the sequencer; a second take in the same
  minute refused, with the first untouched.
- **Overflow.** The port's card slowed until the ring fills: the take
  stops at a frame boundary, the file plays, and the status is overflow.
- **Eight tracks.** A test-only build with `TRACKS = 0xFF` and a fixture
  with a different sound on each track: every `Tn.wav` equals its own slot.
- **Card failure.** The existing refused-write run, on the new path.
- **The hook's cost**, for 1 and 8 tracks, in frames' worth of
  instructions.
- **Boot and gates.** `make check REMIX=stems` and `verify_dram_boot`.

## 9. Flash 13

- The image is rebuilt from this design. Tag 27's images are withdrawn.
- The PIO write patch (`STEM_REC.md` 11.7) stays: PIO cards still take
  it.
- STEM REC no longer uses `0x4ecd3000`, so 7.5a's rule no longer applies
  to it. The single-waiter timer rule stays.
- Test 1 records for at least a minute. Report the file length and whether
  the take plays whole.
- The open CONTROL-row check (`FLASHPLAN.md`) is unchanged by this design.

## 10. Not in this design

- A menu to pick tracks. The mask is build-time.
- 24-bit files.
- Recording anything but the read-back block.
