# STEM REC: proof of concept design

Status: design agreed with Yves on 10 Sep 2026. Nothing built, nothing
flashed.

This is the first step of `docs/proposals/MULTITRACK_TO_CARD.md`, option C.
It records one track, T1, to the card while the sequencer plays. The
proposal says what the firmware already does and why this approach was
chosen. This page says what we build first and how we check it.

Confidence markers as in `docs/firmware/CHIP.md`: ✅ measured, 🟡 inferred
with a falsifier stated, ❓ not known yet and must be found before the code
that depends on it is written.

---

## 1. Scope

**In the POC:**

- One track, T1, stereo, 16-bit, 44,100 Hz, one WAV file.
- Start and stop from one row in MAIN MENU > CONTROL.
- Recording stops when the sequencer stops, or after 15 seconds.
- An octabam module, `modules/stems/`, and a remix, `remixes/stems.py`.
  `make image REMIX=stems` produces the flashable image.

**Not in the POC.** Section 12 lists these as TODO items: the key
combination, T2 to T8, 24-bit, seconds in the name, a tail after stop,
screen feedback, and the remixer integration.

---

## 2. User workflow

1. Open MAIN MENU > CONTROL and select **STEM REC**.
   - If the sequencer is stopped, the recorder arms. Recording starts on the
     first frame the sequencer plays.
   - If the sequencer is running, recording starts at once.
2. Recording stops when any of these happens:
   - The sequencer stops.
   - 15 seconds have been recorded.
   - STEM REC is selected again. Selecting it while armed cancels the arm.
3. The file is `AUDIO/YYMMDD-HHMM/T1.wav`. If the firmware has no routine
   that creates a folder, the file is `AUDIO/YYMMDD-HHMM.wav` instead.
   `YYMMDD-HHMM` is the stock recording name, with no seconds.

The POC shows nothing on screen. You know it worked when the file is on the
card.

---

## 3. States and the menu row

| state | meaning | who moves it on |
|---|---|---|
| IDLE | nothing happens | the menu action |
| ARMED | waiting for the sequencer to start | the frame hook, or the menu action (cancel) |
| RECORDING | the frame hook copies T1 into the ring; nothing is written to the card | the frame hook, or the menu action (stop) |
| FINISHING | the task writes the take: the header with its final sizes, then the ring, then it closes the file (section 6) | the task, when done |

The RECORDING and FINISHING rows were revised on 12 Sep 2026: the first
design wrote during RECORDING and patched the sizes at FINISHING, which the
file layer does not allow (section 6).

The state is one aligned 32-bit word, so every read and write of it is a
single instruction. The menu action and the frame hook write it. The task
writes only IDLE: after FINISHING, or after an error (section 7).

**No race with the hook.** The menu action runs in the UI task, and the
hook can interrupt it between reading the state and writing it. So the
action masks interrupts (`move.w #0x2700,%sr`) for its few instructions:
read the state, pick the new one, write it, and when arming, reset both ring
indexes and the frame count. The hook never sees a half-made change. The
indexes are only reset from IDLE, when the task is done with the ring.

**The menu action**, by state:

| state | sequencer stopped | sequencer running |
|---|---|---|
| IDLE | go to ARMED | go to RECORDING |
| ARMED | go to IDLE | not reachable: the hook moves ARMED on at the first frame |
| RECORDING | go to FINISHING | go to FINISHING |
| FINISHING | ignored | ignored |

**The row** uses the mechanism of `modules/menushortcut`: the CONTROL list
descriptor at `0x400cbd54` holds the count at `+0x00` and the row array
pointer at `+0x18`. The build copies the six stock rows into the module,
appends one ACTION row, repoints the pointer and sets the count to 7
(`docs/firmware/MAINMENU.md` sections 2 to 5).

**Conflict.** `menushortcut` rewrites the same two words, so the ledger
refuses both modules in one remix. The `stems` remix leaves `menushortcut`
out. Making CONTROL rows shareable is a TODO (section 12).

---

## 4. The tap

**The hook site** is `0x40004b12`, the only call site of the per-frame
routine `0x400031a0`, inside the audio interrupt at level 5. The stock bytes
are `jsr %pc@(0x400031a0)` and `move.w #0x2700,%sr`, eight bytes
(`modules/cfprobe/manifest.py`, ✅). The hook runs once every frame: 16
samples, 362.8 µs.

`cfprobe` hooks the same site, so the ledger refuses both in one remix.
`cfprobe` is a measurement probe and does not belong in the `stems` remix.

**Per frame, the hook does this, in this order:**

1. Read the state word. In IDLE and FINISHING it goes straight to step 4.
2. Read the transport word.
   - ARMED and the transport is running: set RECORDING, clear the frame
     count.
   - RECORDING and the transport is stopped: set FINISHING.
3. In RECORDING: copy T1's samples into the ring, add one to the frame
   count, and set FINISHING when the count reaches the limit (section 7).
4. Run the two displaced instructions: call `0x400031a0`, then
   `move.w #0x2700,%sr`.

The copy runs before the stock routine. That routine is the ColdFire delay
and reads the same block. Whether it changes the block in place is not
known (proposal section 5, item 3). Copying first records T1 as the DSP
delivered it.

**The source.** ✅ `docs/firmware/DSP.md`: the block at `0x80003190` holds
four per-track post-FX2 blocks of 64 halfwords for tracks 1 to 4, and the
buffer is double: `0x80003190 + ping * 0x400`. Each 24-bit sample crosses
the 16-bit host port as two halfwords. The DSP computes the first with
`mpy` by `0x8000`, which puts the sample's top 16 bits in it.

🟡 So the 16-bit sample is the first halfword of each pair, and T1 is the
first 64-halfword block. Falsifier: under the port, put a known signal on
T1 and dump the block. If the first halfwords are not the signal's top 16
bits, or the signal is not in the first block, this reading is wrong.

❓ **Which ping half holds the current frame.** The stock routine
`0x400031a0` reads the right half. Read how it chooses before writing the
hook.

**Packing.** The hook copies every other halfword: 32 halfwords per frame,
64 bytes, left and right interleaved. That is the 16-bit stereo frame the
file needs, still big-endian. If the falsifier above fails, the fallback is
a plain 128-byte copy and packing in the task.

**Cost.** In RECORDING: one state read, one transport read, 32 halfword
moves, one add and two compares. Section 10 counts the instructions under
the port.

---

## 5. The ring

| quantity | value |
|---|---|
| frame size in the ring | 64 bytes |
| ring size | 4 MiB, 4,194,304 bytes |
| ring holds | 65,536 frames, 23.8 s |
| one POC recording | 41,344 frames, 2,646,016 bytes, 15.0 s |

**The ring holds a whole POC recording.** The POC cannot overflow the ring,
even if the card stops accepting writes for the entire recording. That is a
crash-safety choice (section 8), and the size still works for the
eight-track version: at eight tracks and 16-bit the ring takes 1,411,200
B/s, so 4 MiB absorbs 3.0 s of card stall. Kept raw for 24-bit, 1.5 s, as
the proposal planned.

**Layout.** One writer, one reader. The hook advances the write index, the
task advances the read index. Each is an aligned 32-bit word that only its
owner writes, so no lock is needed. The indexes are free-running byte
counts. The bytes in the ring are `write - read`, which is never ambiguous
between full and empty. An index becomes an address by masking it with
`size - 1`, because the size is a power of two. 64 KB divides 4 MiB and 64
bytes divides 64 KB, so a 64 KB chunk never crosses the end of the ring.

**Overflow guard.** Before a copy, the hook checks that the frame fits
behind the read index. If it does not, it drops the frame and sets
FINISHING. In the POC this path is unreachable (see above), but it costs
one compare and it stays for the eight-track version.

**Placement: the free top of the platform's reserve.** Any remix with DRAM
code already gives up 1,707 pages (10,487,808 bytes) of the audio page
arena to the platform (`tools/remix/arena.py`, `PLATFORM_PAGES`). The
platform build links the runtime at the base of that reserve and puts the
loader's packed staging copy right above it
(`tools/remix/platform_build.py`). Everything from the end of the staging
copy to the ceiling is unused. For the `stems` remix the runtime is one
small unit, so nearly all of the 10 MiB is free.

The ring and the stack go at the top of the reserve:

```
ceiling - 4 MiB - 8 KB   stack, 8 KB
ceiling - 4 MiB          ring, 4 MiB
ceiling                  end of the reserve
```

This costs no sample memory beyond what the platform already takes.

**The build change.** The platform build learns one new request: a DRAM unit
can ask for an uninitialised region of a given size and alignment at the
top of the reserve, and gets its address as a link symbol. The build refuses,
by name, when runtime + staging copy + every such region do not fit under
the ceiling. The loader does not clear these regions, which is fine: the
ring and the stack need no initial contents, and the task fills its own
stack pattern at creation. This changes the build, so `scripts/refhash.sh
check` must show all 26 existing configurations bit-identical (section 10).

The alternative, a `schema.ArenaReserve` of its own (685 pages), needs no
build change but costs 4.0 MiB more sample memory. It is kept as the
fallback if the build change proves awkward.

---

## 6. The writer task

**Updated 13 Sep 2026.** Phase A answered every ❓ in this section, and one
design choice changed. The answers, with their evidence, are in
`docs/firmware/STEM_REC.md`: task creation (section 3), the sleep (section
4: `0x40020c7c` is a real sleep, in microseconds, on a shared timer that
holds one waiter), the name and the path (section 5), the folder routine
(section 6), two tasks on one card (section 7). The change: the task writes
a take only after it stops, header first, and never seeks (STEM_REC.md
7.10). The paragraphs below that the change retracts are marked ❌.

**Creation.** The first time STEM REC is selected, the menu action creates
the task with the stock task-create routine. The action runs in the UI
task, and the firmware already creates tasks from a running task: `sys`
creates the storage, UI and one more task after start-up
(`docs/firmware/RTOS_FORK.md` section 3, ✅ measured under the port). If
creation fails, the state stays IDLE and nothing else runs.

- Priority 1, the engine task's level. That is below the UI (3) and the
  storage task (5), so the UI stays responsive and the storage task serves
  our requests and stock's in turn.
- Stack 8 KB, at the top of the platform's reserve (section 5). It is filled
  with a pattern at creation so the peak can be read later (section 10).

❓ The task-create routine and its arguments. The port hooked `create` to
measure the eleven tasks, so the routine is known to the port. Its
arguments are not written down.

**The loop, as built.** The task sleeps 10 ms with `0x40020c7c`, without
waiting if the shared timer is busy. It writes nothing while a take runs.
Once the hook has set FINISHING:

1. If no frame was recorded, it sets IDLE and creates no file.
2. It builds the name `YYMMDD-HHMM` from the clock and the path
   `<set>/AUDIO/<name>/T1.wav`, creates the folder, and refuses a file that
   already exists (status EXISTS). Then it opens the file in `"w"`.
3. It writes the 44-byte header with its final sizes, then the ring from
   the read index, in runs of at most 64 KB that never cross the ring's end.
   Each run is swapped to little-endian in place, with `byterev` and
   `swap.w`, and written straight from the ring. No staging copy, no seek.
4. It closes the file and sets IDLE.

❌ **The loop as first designed, retracted 12 Sep 2026.** It streamed the
take during the recording and patched the two sizes at stop with a seek.
The buffered layer's seek does not flush, and close sets the file's length
to the write position, so every take would have been cut to 44 bytes
(STEM_REC.md 7.10, measured under the port on 13 Sep 2026). The first
design, kept for the record:

1. **RECORDING or FINISHING, no file open.** If the state is FINISHING and
   no frame was recorded, set IDLE and create no file. Otherwise read the
   clock and build the
   name with the stock name builder `0x400819fc`. Create the folder. Open
   `T1.wav` with an absolute path. Write the 44-byte header with the two
   size fields set to 0.
2. **At least 64 KB in the ring.** Swap the 64 KB to little-endian in place
   in the ring, with `byterev` and `swap.w`, then write it straight from the
   ring. No staging copy, no second buffer.
3. **FINISHING.** Write what is left. Seek to byte 4 and write
   `36 + data size`; seek to byte 40 and write the data size. Close the
   file. Set IDLE.

❌ An earlier version of this page named the "delay helper" `0x40020c7c` as
the sleep. Read on 10 Sep 2026, it is not one: it takes a lock at
`0x460bcda8` and programs a hardware timer (`0xfc084000`), a timed hardware
wait. ❓ The kernel's own tick delay, the call that blocks the calling task
for N ticks, is still to be found.

🟡 Task creation, read on 10 Sep 2026: `0x400005fc(tcb, entry, prio, stack,
size)` builds the task's first stack frame, links the TCB to the ready slot
for `prio`, and returns 1. It does not appear to make the task runnable by
itself; the routine right after it, `0x4000063c(tcb)`, masks interrupts and
updates the highest-ready word, which looks like the start call. ❓ The TCB
size and the start call, from one of stock's own create sites.

**The header** is the stock writer's layout (`docs/firmware/SAMPLE_SAVE.md`
section 3): channels 2, rate 44,100, byte rate 176,400, block align 4, 16
bits. One difference: the RIFF size at byte 4 is `36 + data size`, as the
RIFF specification says. The stock writer computes `44 + data size`, which
looks eight bytes too large (SAMPLE_SAVE.md, 🟡). Data size is always a
multiple of 4, so no pad byte is needed.

**The file API.** ✅ `docs/firmware/SAMPLE_SAVE.md` section 5, named
independently by ems-octakit and octamax: open `0x40016864`, write
`0x400166b8`, seek `0x4001660c`, close `0x4001677c`, project directory
`0x40025230`, sprintf `0x40013a08`. octamax created files with it from a
detour on hardware.

🟡 The signatures, from Octakit's C runtime (`runtime/persistence.c`), which
runs them on hardware:

```
int32 open (FileObject *obj, const char *path, const char *mode,
            uint8 *buffer, uint32 buffer_size)     <0 = error
int32 write(FileObject *obj, const void *src, uint32 len)   1 = success
int32 seek (FileObject *obj, uint32 offset)         <0 = error
int32 close(FileObject *obj)                        <0 = error
```

The file object is 24 bytes. Octakit uses a 512-byte buffer. Two
behaviours matter here:

- **`"w"` does not truncate.** Octakit opens an existing file with `"w"` and
  checks its size before patching a record in place. ❌ "So seek-then-write
  works, which is how the header sizes get written at stop" is retracted:
  close sets the length to the write position, so a seek back cuts the
  file (STEM_REC.md 7.10).
- **The same property is a hazard.** A second recording in the same minute
  would open the first one's file and overwrite its start. So after opening,
  the task reads the file object's logical length (word 4, per Octakit's
  comment at `persistence.c` line 910). If it is not zero, the task closes
  the file, writes error EXISTS to the status word, and sets IDLE. The
  earlier recording stays intact. ❌ Retracted: open clears word 4 (`+16`,
  at `0x40016884`), so it is 0 for every file. The task asks the file
  layer's exists pointer `0x46c823fa` before it opens, and refuses with
  EXISTS. ✅ Measured under the port: a second take in the same minute is
  refused, and the first take stays byte-identical (STEM_REC.md 11).

❓ **The folder-creation routine.** Not located. If none can be called, the
file goes to `AUDIO/YYMMDD-HHMM.wav` (section 2).

❓ **Whether the FAT layer is safe to call from two tasks at once.** The
ATA layer has a lock (`0x460bae18`, `docs/remixer/EMU.md`). The FAT layer
above it is unmapped (`docs/history/COVERAGE.md`).

**Rules that keep the task away from stock's state:**

- **Absolute paths only. Never change directory.** The FAT layer keeps the
  current directory as global state, and the project load changes it
  (`docs/remixer/EMU.md`, "The set name is an absolute path").
- **Our own file object and our own I/O buffer.** The stock save uses a
  global buffer at `0x460263e0`. Borrowing it would corrupt a stock save made
  during a recording.

---

## 7. Stops and errors

**Normal stops:**

- **The sequencer stops.** The hook sees the transport word change and sets
  FINISHING. Audio after that frame, such as delay and reverb tails, is not
  recorded.
- **The limit.** `MAX_FRAMES = 41344`, 15.0 s. The hook sets FINISHING when
  the frame count reaches it.

**Errors.** One rule: a file never contains a silent gap, and the file is
always closed.

- **The ring would overflow.** Unreachable in the POC (section 5). The hook
  drops the frame and sets FINISHING.
- **Open, write or close returns an error, or the card is full.** The
  task closes whatever is open, writes the error code to a status word, and
  sets IDLE. The status word can be read under the port. On the unit it is
  not shown.
- **The card aborts a write command.** ✅ Measured under the port, 13 Sep
  2026 (STEM_REC.md 11.4): the stock driver's write command waits for the
  card's DRQ bit at `0x40014cf4` with no error check and no timeout, so the
  writer task spins there forever, holding the file layer's lock. The rule
  above cannot hold for this case: nothing returns to the task. It is a
  stock limitation, because the stock sample save goes through the same
  routine. Recovery is a power cycle. Whether a real card ever answers a
  write this way is not measured.
- **The stock PIO write's race.** ✅ Found under the port, 14 Sep 2026
  (STEM_REC.md 11.7). The stock routine that issues WRITE SECTORS sends the
  first sector, then updates the card handler's data pointer and sector
  count, with interrupts enabled. An interrupt in between leaves the
  handler waiting forever at level 5, which freezes the unit: the port's
  first 15-second take did that, on one of its 2,653 single-sector writes.
  On a write of more than one sector it can instead write a sector twice,
  silently.
  This breaks the rule above from inside stock code, so the module patches
  the routine (`stems_ata_first`, a detour at `0x40014cfe`) to update both
  first. The patch changes every PIO write, stock saves included. A card
  that reports DMA takes the stock DMA path, where the patch never runs.
- **STEM REC selected during FINISHING.** Ignored.

**Known limitations of the POC:**

- **Power off, or a card pulled, during a take or before its write ends.**
  The take is written only after it stops, so nothing of it is on the card
  until the write ends. ❌ "The header sizes are written only at stop, so
  the file reads as empty. The audio is in the file and a repair tool can
  recover it" described the first design and is retracted (section 6).
- **Loading a project during a recording.** Not detected. Do not do it.

---

## 8. Crash safety

Yves's requirement: limit the ways this can crash the unit. What the design
does about it:

1. **Nothing runs until STEM REC is selected.** No boot hook besides
   octabam's existing loader. The task does not exist until the first
   select. In IDLE the frame hook costs one word test and one branch.
2. **The menu action cannot race the hook.** It changes the state with
   interrupts masked (section 3).
3. **The interrupt code calls nothing.** The frame hook makes no calls, uses
   no RTOS service and touches no card state. It is straight-line code with
   bounded loops. A crash in an interrupt at level 5 hangs the unit, so this
   is the code that gets the most checking under the port.
4. **The ring cannot overflow** in the POC (section 5).
5. **Every file API result is checked.** Any error closes the file and
   returns to IDLE (section 7). The exception is a card that aborts a write
   command: the stock driver never returns (section 7).
6. **The task never touches stock's global file state**: no directory change,
   no shared buffer (section 6).
7. **The 8 KB stack is generous, not tight.** The peak is measured under the
   port. Shrinking it waits until the peak is known on hardware as well.
8. **The card must be mounted.** 🟡 `0x460d1cb8` reads 1 after the card
   mounts (`docs/remixer/EMU.md`, cold init). The menu action refuses to arm
   when it is 0. Falsifier: under the port, the word is 1 with a card and 0
   without one.
9. **Recovery does not depend on us.** The bootloader is never written by an
   OS update, so the Startup Menu can always reflash a stock image
   (`docs/remixer/FLASHING.md`).
10. **Test on a card you can lose.** Concurrent card access is the least
   known part (section 6). Back up the card, or use a spare, for the first
   flash.

---

## 9. What must be found first

In this order. Each is a read of the image or a run under the port, and each
blocks the code named beside it.

| # | unknown | blocks | how |
|---|---|---|---|
| 1 | which ping half holds the current frame | the tap | read `0x400031a0` |
| 2 | the transport-running word | ARMED and the sequencer stop | read the PLAY and STOP paths, `FW_TRANSPORT` `0x4009c506` (`docs/firmware/RTOS_FORK.md` section 9) |
| 3 | T1's position and word layout in the block | the packing | port: known signal on T1, dump the block |
| 4 | the TCB size and the start call after `0x400005fc` | the task | one of stock's create sites |
| 5 | the kernel's tick delay and the tick period | the loop | the blocking primitives `0x40000818`, `0x400007a4`, `0x40000d00`, and a stock task loop that sleeps |
| 6 | a folder-creation routine | the folder | search the FAT layer and the file browser |
| 7 | the FAT layer's locking | crash safety | read the open and write paths for a lock |

---

## 10. Verification

Everything here runs under the ColdFire port before any flash. The port
writes to its emulated card image, and the image can be read back
(`docs/remixer/EMU.md`: a project load writes 300 sectors of the firmware's
log).

1. **The tap.** A fixture project with a known signal on T1. Dump the
   read-back block for a few hundred frames. This settles unknowns 1 and 3,
   and confirms the block holds live audio at all: every earlier run read
   zeros because the DSP started cold at the transport start. RTOS_FORK
   section 10.47's `--pre-roll` is meant to fix that.
2. **The hook's cost.** Count its instructions per frame in each state.
3. **The whole path.** Build the `stems` image and load the fixture. Call
   the menu action directly, the way the port already calls the PLAY handler
   (`press_play_live`). Start the sequencer, run 10 s, stop. Read `T1.wav`
   from the card image and check:
   - every header field;
   - data size = frames recorded x 64;
   - every sample equals the first halfword of its pair in the dumped block.
4. **The 15 s limit.** Run 20 s. The file must hold exactly 41,344 frames.
   ✅ Run 14 Sep 2026 (`verify_stems.py --long`): it froze the unit before
   the PIO write fix, and with the fix the file holds all 41,344 frames and
   equals the ring byte for byte (STEM_REC.md 11.7).
5. **The stack peak**, from the fill pattern.
6. **The overflow guard.** Build with a tiny ring and stall the task. The
   file must close cleanly and hold gap-free audio up to the drop.
7. **An error from the card.** Make the port's write fail. The task must
   close and return to IDLE. ✅ Run 13 Sep 2026, and it cannot: the port's
   refused write hangs the writer inside the stock driver (section 7). The
   verifier records that fact instead.
8. **The gates.** `make check REMIX=stems`. The placement in section 5
   changes the build, so first `scripts/refhash.sh save` on the tree before
   the change, then `scripts/refhash.sh check` after it: all 26 existing
   configurations must stay bit-identical.

## 11. The flash

One flash, on a backed-up or spare card, in this order:

1. A project with Flex machines only. Record 15 s. Listen for dropouts
   while recording. Open the file in a DAW. Compare with what the port
   predicts.
2. The same with a static machine playing, which streams from the card while
   we write to it. The take is written after it stops, so stop it with STEM
   REC while the sequencer plays on: then the write and the stream overlap.
3. Arm while stopped, then press PLAY. Then stop with the sequencer, then
   with STEM REC.

Any new failure goes into `docs/remixer/FAILURE_MODES.md` the moment it is
seen.

---

## 12. TODO, after the POC

- **The remixer integration.** A row in the TUI remixer. CONTROL rows that
  several modules can share, so `stems` and `menushortcut` fit in one
  remix. `stems` in one image with Octakit and MIDI SCENES. A schema
  building block for a module's own task, if the POC's task needs build
  support.
- **The key combination**, for the MKI and the MKII, checked against stock
  and against Octakit's combinations.
- **T2 to T8**, then **24-bit.**
- **The card throughput measurement** (proposal section 5, item 1), before
  eight tracks. The POC writes 176,400 B/s. Eight tracks at 24-bit need
  2,116,800 B/s.
- **Seconds in the name**, so two recordings in one minute do not collide.
- **A tail after stop**, to keep delay and reverb decays.
- **Screen feedback**: armed, recording, saved, error.
- **Writing during the take**, so a power cut leaves a readable file. It
  needs a way to finish the header that the buffered layer allows: its seek
  does not flush and its close cuts the file to the write position
  (STEM_REC.md 7.10).
- **The length limit**, raised from 15 s once the POC holds on hardware.
- **Sector-aligned data.** The 44-byte header puts every audio write 44
  bytes past a sector boundary. A `JUNK` chunk that pads the header to 512
  bytes would align them, which Octakit does for its own writes. Measure
  whether it matters, and check that the Octatrack's own WAV reader skips
  the chunk, before adopting it.
