# Writing all eight tracks to the card while playing

A technical proposition. It says what the firmware already does, what the
numbers are, what nobody has measured, and the order in which to measure it.
It is not a build plan and nothing here is on `PLAN.md`.

Confidence markers as in `docs/firmware/CHIP.md`: ✅ measured, 🟡 inferred with
a falsifier stated, ❌ retracted. Where a number is arithmetic on measured
inputs it says so.

---

## 1. The wish, in one sentence

Record the eight tracks' post-effects outputs to eight files on the
CompactFlash card, continuously, while the sequencer plays, without stopping
for a save.

Related wishes from the same thread, not covered here: a routing matrix to
the recorder buffers, and recording sources other than the track outputs.

---

## 2. What the firmware already does

Everything in this section is in the stock OS today. None of it is new code.

### 2.1 The eight post-FX2 track outputs reach the ColdFire every frame

✅ `docs/firmware/DSP.md`, the frame table and the section after it (read
10 Sep 2026 from both DSP payloads). After each track's FX2 runs, the DSP
copies that track's 16-sample block into a read-back buffer, 64 words per
track. The ColdFire's DMA fetches the buffer every frame:

| DRAM address | tracks | size per frame |
|---|---|---|
| `0x80003190` | 1 to 4 | 256 words |
| `0x80003390` | 5 to 8 | 256 words |

Each sample is 24-bit, carried as two 16-bit words because the host port is
16 bits wide. So the ColdFire holds a complete 8-track stem set, 16 samples
deep, every 363 µs. Nothing on the DSP has to change to capture it.

🟡 Not yet read: whether the track LEVEL knob and the ColdFire-side delay are
applied before or after this point. The ColdFire's delay routine consumes
this block and sends the processed result back to the DSP, so the point just
before that send-back is the post-delay tap. Falsifier: sweep LEVEL and the
delay on one track and dump the 64 words; if they do not change, the tap is
upstream of both.

### 2.2 The recorders can already capture per track

✅ `docs/firmware/PARAM_PAGES.md`, hardware-confirmed by Bryan T on
2 Sep 2026. A track recorder's SRC3 source offers `-, T1…T8, MAIN, CUE`. Eight
recorders with SRC3 set to T1 through T8 is an 8-track capture with no
modification at all.

🟡 The recorder's mixer reads three sources with independent gain ramps.
INAB and INCD come from the input-capture ring at `0x80005760`; SRC3 set to a
track comes from the read-back block in 2.1. This reconciles the two
`RTOS_FORK.md` entries that name different sources for "the recorder's audio":
they describe different sources of the same mixer. Falsifier: a recorder with
SRC3 = T1 and INAB = INCD = off must reproduce the T1 block of 2.1 sample for
sample.

### 2.3 The firmware writes WAV files itself

✅ `docs/firmware/SAMPLE_SAVE.md`. The writer at `0x40020f04` builds a 44-byte
header, walks the sample pool in 3,072-byte pieces, converts through the
16-bit or 24-bit converter, and writes through a 64 KB buffered file API.
It accepts recorder buffers as sources. The file API underneath has been used
from a detour to create files on the card, on hardware, by octamax.

### 2.4 Card I/O does not stop audio

✅ octamax validated a bank load from the card while the sequencer ran. The
storage stack is asynchronous: a command queue, an interrupt per sector, an
RTOS event on completion. The discipline the firmware already follows is
buffer in DRAM, flush later.

---

## 3. The numbers

All arithmetic on measured inputs. Frame = 16 samples at 44,100 Hz, so
2,756.25 frames per second.

| quantity | value |
|---|---|
| raw stem data in DRAM, 8 tracks | 1,024 bytes per frame, 2.82 MB/s |
| on card, 8 tracks, stereo, 24-bit | 2,116,800 B/s, 2.02 MiB/s, 121 MiB per minute |
| on card, 8 tracks, stereo, 16-bit | 1,411,200 B/s, 1.35 MiB/s, 81 MiB per minute |
| sectors per second at 24-bit | 4,134, one sector interrupt every 242 µs |
| sample pool | 14,602 blocks × 6,144 B = 85.56 MiB |
| pool split eight ways, 24-bit stereo, no samples loaded | 42 seconds per track |

Two conclusions follow without any further measurement:

- **Capacity, not bandwidth, is why this cannot be done with the stock
  recorders alone.** Forty-two seconds of eight tracks fills the RAM the
  samples also need. Streaming exists to make the card the store, not the RAM.
- **The card must sustain about 2 MiB/s for as long as the song lasts.** The
  ATA specification's PIO mode 4 ceiling is 16.7 MB/s. That is a
  specification figure. What this driver reaches, through an interrupt per
  512-byte sector on a 264 MHz ColdFire that is also running the sequencer,
  the recorder mixer and the delay, is **unmeasured** (section 5).

---

## 4. Three ways to do it

### A. Stock, offline

Eight recorders, SRC3 = T1 to T8, record, then save each buffer with the
stock writer. Works today by hand. Limits: 42 seconds, and eight manual
saves. Worth stating because it is the baseline every other option is
measured against, and because it is the fixture for measurement 2 in
section 5.

### B. Stream the stock recorders

Keep A's recorders recording in a loop. A background task walks each
recorder's block chain behind the write position, appends drained blocks to
eight open files, and returns the blocks to the pool.

- Reuses: the recorder mixer, the pool page walk `0x4009499c`, both
  converters, the writer's header and chunk loop, the file API.
- New: the drainer task, block recycling behind the write head, a header
  fix-up at stop (seek exists at `0x4001660c`).
- Risk: the pool's block rows are the recorder's own bookkeeping. Recycling a
  block the recorder still owns is a corruption with no error message.
  The loop point is a hard cut inside the frame, which the drainer must not
  straddle.

### C. Tap the read-back block directly (recommended)

Hook the frame path at the point where the ColdFire has both cores' blocks
in DRAM. Copy 1,024 bytes per frame into a ring of our own, pack to 24-bit,
and let a background task drain the ring to eight files.

- Reuses: the file API, the writer's header layout, the 16-bit and 24-bit
  converters if their argument shape fits, the DRAM platform's detour and
  runtime mechanism (`docs/remixer/PLACEMENT.md`).
- New: one per-frame copy, one ring, one drainer task, one header fix-up.
- Leaves the eight recorders free for the user.
- Needs a DRAM placement for the ring. `PLAN.md` item 6, measuring
  `0x46000000` to `0x47502c10` with samples loaded and the recorder running,
  is the prerequisite. A ring of 4 MiB holds 1.5 seconds of card stall at
  24-bit, which is the budget a slow card gets before samples drop.

Why C over B: the audio is already sitting in DRAM in the shape we want, so
the capture is a memcpy, and nothing we add touches the pool's bookkeeping.
B becomes the fallback only if the read-back block turns out to be upstream
of something the wish needs, such as the delay.

Either way the file side is the same: eight WAV files, header written with
placeholder sizes, sizes patched at stop. A single 16-channel file is a
variant of the same writer, not a different design.

---

## 5. What must be measured, in order

Each item names the instrument, the cost, and what would falsify the
proposition. Do not skip 1; it is the one number that decides whether this
is real.

1. **Card write throughput, on hardware.** One flash. A detour at a menu
   hook writes 32 MiB through `0x400166b8` in 64 KB pieces while the
   sequencer plays, and reports frames elapsed and whether audio dropped.
   octamax's file-creating detour is the template. Falsifier: under about
   2.5 MiB/s sustained, streaming eight 24-bit tracks is not real on this
   card path, and the proposition drops to 16-bit or to fewer tracks.
   Nothing in any of the four repos measures this today. Do not estimate it.

2. **The read-back block's content.** Port or hardware, no flash needed on
   the port. Set up option A's fixture, put a known signal on T1 with an
   audible FX2, and dump the 64 words at `0x80003190`. Falsifier: anything
   other than T1 after FX2. On the port this needs the DSP frame engine
   running from boot; in every run so far the block has been zero because
   the port started the DSP cold at transport start
   (`docs/firmware/RTOS_FORK.md` §10.16).

3. **The tap's position relative to LEVEL and the delay.** Same fixture,
   sweep both. Decides where in the frame routine the hook goes.

4. **DRAM for the ring.** `PLAN.md` item 6, unchanged.

5. **ColdFire headroom.** No figure exists. The port counts about 64k
   instructions per frame under emulation, but that is the emulator's
   count, not a cycle budget. Measurement 1 gives the first real data
   point: whether the sequencer dropped audio while the card was busy.

6. **Execute the stock writer under the port.** `SAMPLE_SAVE.md` item 1.
   Confirms the header builder before its layout is copied.

7. **The RIFF size field.** Needs no tools. Read bytes 4 to 7 of any `.wav`
   the unit saved and compare with the file size minus 8. If they differ by
   8, the stock writer is off by 8 and ours should not copy the mistake.

---

## 6. What this is not

- Not a change to the DSP. The stems are already delivered.
- Not a change to the recorders. Option C does not touch them.
- Not on `PLAN.md`. The remixer's work order stands; this is a survey for the
  people who asked.
- Not a claim that it works. Nothing has been built, flashed or timed.
  Measurement 1 is where that starts.

---

## 7. Questions back to the thread

- Eight stereo files, eight mono pairs, or one 16-channel file?
- 24-bit or 16-bit? The difference is a third of the card bandwidth.
- Should recording start and stop with the sequencer, or with a key?
- Which cards do people use? Measurement 1 has to run on each.
