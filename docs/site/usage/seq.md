**Euclidean sample trigs and p-locks.** Hold a **TRACK** key and press
**PAGE**: SEQ opens for that track. Stock 3×2 knobs (PULSE / ROT / LANE /
DEST / DEPTH; F empty), LEN on the left, and a 4×16 step grid (hollow =
off, solid = on) for every step up to 64.

Edits sequencer trigs only. Not the DSP **EUCLID** effect. Leaves
`PROJECT > CONTROL > SEQUENCER` alone, so it coexists with SCALE QUANTIZER.

## Access

Hold a **TRACK** key and press **PAGE** — SEQ opens on that track.

- **NO** closes the window.
- Bare **PAGE** stays stock (step banks) and does not close SEQ.
- **FUNC + PAGE** (SCALE SETUP) stays stock.
- Hold another **TRACK** while SEQ is open: YES retargets that track and
  the panel loads its saved SEQ params from `euclid.work`.

## Operation

**LANE** (C) picks what A / B and the grid edit:

| LANE | A / B / grid | YES |
|---|---|---|
| **TRIG** | sample-trig PULSE / ROT | Rewrites note trigs; reshapes **only the current DEST** onto those notes; syncs that DEST's PLCK recipe to the TRIG rhythm |
| **PLCK** | this DEST's PLOCK PULSE / ROT | Leaves the note pattern; rewrites **only this DEST's** locks (trigless where there is no note); clears this DEST on misses — including on notes |

DEST and DEPTH always apply on YES, even while LANE is TRIG. Scroll DEST
to load that DEST's plock recipe into A/B when LANE is PLCK. Each DEST
keeps its own PULSE / ROT / DEPTH (and free mask).

The grid is **write-only**. Open and track-switch load the bank SEQ recipe
only — they never pull live sample trigs into the grid. **YES** writes from
PULSE / ROT (or a CUE mask) and overwrites the track.

## Examples

Step numbers in the diagrams are **1-based** (same as the unit). Black =
lock on a note. Hatched = trigless lock. White = no lock. Inverted cells
on the 3×2 are the knobs that matter for that example.

### Notes only (no DEST locks)

Empty track. LANE = **TRIG**, DEST = **PTCH**, **DEPTH = 0**, set PULSE,
**YES**:

![TRIG DEPTH 0 writes notes and clears PTCH.](../../img/seq/notes-only.png)

Notes land. Current DEST locks are cleared because DEPTH is 0.

### Notes with pitch on the same steps

LANE = **TRIG**, set PULSE / ROT, DEST = **PTCH**, DEPTH non-zero, **YES**.
Notes land; PTCH locks sit on those same steps; this DEST's PLCK recipe is
synced to the TRIG rhythm.

### Stack a second DEST without touching the notes

You already have notes + PTCH. Switch to LANE = **PLCK**, DEST =
**AMP VOL**, set a different PULSE / ROT, **YES**:

![PLCK writes only VOL; notes and PTCH stay.](../../img/seq/stack-vol.png)

VOL locks write on that plock rhythm (trigless where there is no note).
Notes and PTCH stay.

### Regenerate trigs — keep other DEST locks

You have notes with PTCH + VOL. Keep DEST = **PTCH**, change TRIG PULSE,
**YES**:

![TRIG YES reshapes only PTCH; VOL survives as trigless where notes drop.](../../img/seq/trig-reshape.png)

- **PTCH** (current DEST) is cleared on silent steps and rewritten on the
  new notes.
- **VOL** (other DEST) is **kept**. Where a note disappears but VOL remains,
  the step becomes **trigless** so VOL stays audible.

### Overwrite one DEST from PLCK

You placed PTCH on the notes from TRIG. Switch to LANE = **PLCK**, DEST =
**PTCH**, change ROT, **YES**:

![PLCK YES clears PTCH on note misses; other DEST stacks stay.](../../img/seq/plck-overwrite.png)

- **PTCH** is cleared on every miss — including on notes that still fire —
  then written on the new PLCK hits (trigless if no note).
- Other DEST stacks (VOL, FILTER, …) are untouched.

### Clear one DEST

LANE = **PLCK**, that DEST's **PULSE = 0**, **YES**:

![PLCK PULSE 0 clears PTCH; notes and other stacks stay.](../../img/seq/clear-dest.png)

Clears this DEST over the pattern length. Notes stay. Orphan trigless bits
drop when nothing else remains on the step.

### CUE then YES

Focus the lane (TRIG or PLCK), set **PULSE** to the hit count you want,
press **CUE** (places exactly that many hits at random on that lane only),
then **YES** to write.

On TRIG, if the track already has sample trigs, PULSE / ROT / CUE first
open **ARE YOU SURE?**. Dialog YES only unlocks the knobs — writing the
pattern is a separate YES.

### Write-only gotcha

The live pattern on the track is **not** pulled into the grid when you open
SEQ or switch tracks. The grid always shows the saved bank recipe. Edit
PULSE / ROT (or CUE), then **YES** to overwrite the track.

### CX OSC SETUP destinations

On a CX OSC track, DEST can also target SETUP slots **CAR / MOD / SYMM /
FDBK / PWM** (LFO PMTR 30..34). Same TRIG / PLCK rules: TRIG locks them onto
notes; PLCK can stack them trigless; PLCK miss clears that DEST even on
notes.

## DEST and DEPTH

DEST matches LFO SETUP PMTR (PAGE / PARAM). **0..29** page-1 flats
(**AMP XVOL** skipped); on CX OSC also **30..34** SETUP slots (stackable in
DRAM).

**DEPTH** (0..127): at 0, YES clears that DEST for the path in use.
Non-zero:

- **PTCH** — in-scale around Part PLAYBACK PTCH (misses fall back to Part).
- **AMP VOL** — unipolar below Part AMP VOL.
- **Any other DEST** — uniform `[Part±DEPTH]` clamped 0..127.

## Persistence

PULSE / ROT / DEST / LANE / free mask / per-DEST DEPTH and PLOCK rhythms
persist in `euclid.work` (STORE client). Defaults: TRIG PULSE 5, DEST =
AMP VOL, ROT / DEPTH / PLOCK PULSE 0, LANE = TRIG.

CUE randomizes the focused lane only (density = PULSE). PLOCK edits do not
prompt.

When a step's last lock is cleared, orphan trigless bits drop and the
plock LED bitmap refreshes (empty note trigs stop blinking yellow).

## Controls

| Control | Does |
|---|---|
| TRACK + PAGE | open SEQ on that track |
| TRACK (while open) | switch to that track's params / YES target |
| A | PULSE of the focused lane |
| B | ROT of the focused lane |
| C | LANE — TRIG / PLCK |
| D | DEST |
| E | DEPTH |
| F | empty |
| CUE | random placement of exactly PULSE hits on the focused lane |
| YES | write TRIG mask + current DEST locks (and trigless where needed) |
| NO | close |
