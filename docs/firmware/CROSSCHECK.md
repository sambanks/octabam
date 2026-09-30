# Cross-check: STEM REC against seven references

**Date.** 22 Sep 2026. **Scope.** Every stock-firmware claim in the 70
commits of branch `stem-rec-poc` (STEM REC): `docs/firmware/STEM_REC.md`,
`modules/stems/`, the STEM REC spec and plan, and their entries in
`FAILURE_MODES.md`, `FLASHPLAN.md`, and `PLAN.md`.

**Method.** A census script pulled every 8-digit firmware address from the
lines those commits added (1,893 addresses) and looked each one up in seven
references. Where a reference said something different, the stock image
decided it: `out/raw/section_3_MAIN_OS.bin`, base `0x40000400`, SHA-256
`164f3122…af0a84e`, disassembled with `objdump -m m68k:cfv4e`. Where
behavior mattered, the ColdFire port (octabam's emulator of the unit) ran
it. A reference is a lead, never evidence on its own.

Markers: ✅ read from the image or measured under the port. 🟡 inferred,
with the test that would settle it. ❌ a claim of ours that was wrong.

## The references

| Ref | Repo | Head | Addresses shared with us |
|---|---|---|---|
| M | octabam `main` (Sam and others, since the branch point) | `5b03d11` | 204 |
| E | markandrus/octemu (a QEMU-based emulator of the unit, with a symbol file) | `8700018` | 146 |
| O | mxldyn/octamax | `7d9debc` | 63 |
| L | nordseele/octalab | `e0dc56d` | 33 |
| K | emuyia/ems-octakit (Octakit) | `c6d3f39` | 23 |
| S | bkkbrls-del/midisc | `b2ac27e` | 3 |
| B | bryantysinger/octa-bt-pt | `e970dd0` | 2 |

306 of our addresses appear in at least one reference. Most agree: the
kernel's routines and task table, the file layer's function table and its
open, write, and close, the transport word, the frame routine, and the
clock. octemu is the most useful check, because it's an independent
emulator that names each address with a short description.

## What changed

Each item is its own commit on branch `crosscheck`.

### ❌ STEM REC recorded T3, not T1 (fixed)

The read-back block holds each track's post-effects audio for one frame.
Stock puts track k (0-based) at k × 0x80 in it. The NEIGHBOR machine's
handler says so (`0x4000466c`): it reads "the previous track" at
`0x80003190 + half × 0x400 + (k − 1) × 0x80`, and it refuses tracks 1 and
5, as the manual says. octemu's RECEIVE machine, checked on hardware, uses
the same layout.

Our section 9.2 had placed T1 at `0x100`, the third slot. The test
project's template has NEIGHBOR machines on T2 and T3, so both copied T1,
64 and 128 samples later. The 12 Sep fit found T3's copy. A new port run
confirmed the chain: slot `0x00` matches the test kick exactly (−74 dB
residual), and the next two slots are the same signal, delayed.

**Fix.** `T1_OFFSET = 0x00` in `stems.s` and `verify_stems.py`. The test
project now sets T2 and T3 to silent tracks, and a new check fails if any
core-1 slot other than T1's has sound. **The staged Flash 13 image (tag 27,
`e1596682…`) is withdrawn: rebuild it from this branch.**

### ⚠️ Stock saves by itself about 1 s after every STOP

Section 7.5 already knew that every buffered file read and write passes
through one unlocked buffer, `0x4ecd3000`. It said no second concurrent
user was known. The cross-check found one, with an automatic trigger:

1. A timer (DTIM1) runs at 120.0 Hz, and every second tick posts a message
   to the UI task: a 60 Hz tick.
2. While the sequencer is stopped, the UI task counts those ticks. On the
   61st, it asks the engine task to save every dirty bank other than the
   current one.
3. The engine task writes those `.work` files through the same unlocked
   buffer.

STEM REC writes its take right after STOP, on a task of the same priority.
If another bank has unsaved edits, the two writes can overlap, and either
file can end up with the other's bytes. The loser can be the user's bank
file. This is read from the code, not observed (🟡). Octakit hooks the same
save decision (`0x40022c1c`).

**What changed.** STEM_REC.md 7.5a. FLASHPLAN's do-not now says: save the
project before a take, and don't load or save anything while a take is
being written. A new FAILURE_MODES entry says what it would look like.
**Resolved for STEM REC** by the streaming build (spec
`2026-09-22-stem-rec-streaming-design.md`): STEM REC writes through the raw
file routines from its own buffers and never touches `0x4ecd3000`.

### ⚠️ The STEM REC row may not appear

STEM REC adds its CONTROL row the way the bus screen did: count 6 → 7 and
a repointed row array. That worked on the unit for the bus screen (tags
85–90), and failed on tag 16 with correct bytes in the image. The failure
is still open in FAILURE_MODES, with no known cause. Our port tests call
the menu action directly and never open the menu. main's port can now draw
the screen and take keys; this branch's can't. FLASHPLAN now flags it.

### Corrections that don't change the design

| Where | What we said | What the image shows |
|---|---|---|
| 3.5, 11.4 | The UI task is `0x40056c40`, priority 3 | The UI task is `0x40061a94`, priority 1: its start-up falls into the UI queue loop at `0x40061cd2`. `0x40056c40` is a 60 Hz housekeeping task. The conclusions still hold. |
| 7, 7.7–7.9 | Task `0x4001ee30` is "the storage task's real-time sample streaming" | It's the USB mass-storage worker: USB code and the card interrupts post its queue. Static samples stream through the locked raw read `0x400180c8`. The conclusion about `0x4ecd3000` stands. |
| 8.0 | Mount state 2 is "believed USB disk mode" | Yes, and in state 2 the file layer's mkdir and write are `moveq #-1` stubs, and its open resolves only existing paths. A take armed there fails at the open. Nothing is written. |
| 8.3 | `0x460e76a0` is "an unrelated flag" | It's the USB disk mode flag. All four accesses are in that mode's code; octemu measured it live. |

### Checked and agreed

- **The existence test.** octamax calls `*(0x46c823fa)` "the load's real
  open". ✅ It takes the file lock, resolves the path, and returns 0, 1
  (file), or 2 (folder). It opens nothing. Our use is right.
- **The stock PIO write race (11.7).** octemu found the same race
  independently. Its two addresses for it are each `0x400` low (a slip);
  its other addresses match ours. octemu infers that a real card's program
  time hides the race on hardware, but that inference leaves out the
  preempting frame interrupt our trace shows. No one has measured the
  timing on a unit.
- **The DMA path.** octemu doesn't model DMA either, so no emulator has
  run the WRITE DMA path that Yves's UDMA card takes. FLASHPLAN already
  says so.
- **The DRAM platform.** octalab ran an image built by octabam's remixer on
  an MKI (11 Sep 2026): the loader, a unit in the platform reserve, and a
  module. STEM REC stands on that platform.
- **The read-back gain.** T1 sits about 24 dB below its source (1/15.5 on
  its own slot). Still measured, still unexplained.

## Still open

- 🟡 **The collision in 7.5a, observed.** Run the port with a second bank
  dirty, a take, and STOP, with a write watch on `0x4ecd3000` by task.
- 🟡 **The CONTROL row on the menu.** Open CONTROL in main's port
  (`ot_emu --live`) before the flash. This needs main's port built in WSL.
- 🟡 **Why T1 sounds for only 64 samples in the test project.** Something in
  the template's part gates it after four frames. The takes under the port
  are therefore mostly silence.
- 🟡 **The WRITE DMA path**, which Yves's card takes. Read on 22 Sep 2026
  (STEM_REC.md 11.8): no counterpart to the PIO race, since the hardware
  moves every sector and nothing is shared with the interrupt. Still never
  run by any emulator or watched on a unit.

## For the other repos

These are errors in the references, not in our work. They're listed so
they can be passed on.

- **main `docs/firmware/KERNEL.md`:** the UI task is `0x40061a94`
  (priority 1), not `0x40056c40`; `0x40000d1a` is inside the queue receive,
  whose entry is `0x40000d00`.
- **main `tools/emu/emu_rtos.py`:** calls `0x800066a0` `REC_ARM`. octemu
  reads it as the arranger-active flag (its arranger advance is gated on
  it). Not settled here.
- **octemu `src/board/ot-ata.c`:** the write-race comment names
  `0x40014848` and `0x4001494a`; the routine is at `0x40014c48`, and the
  decrement at `0x40014d4a`.
- **octamax `NOTES.md`:** `0x4001b724` is the existence test, not "the
  load's real open".
