A Euclidean fill for sample trigs and per-destination p-locks. Hold a TRACK
key and press PAGE: a window opens (stock 3x2 grid with PULSE / ROT / LANE /
DEST / DEPTH, F empty, LEN on the left, and a 4x16 grid of hollow/filled
squares for every step up to 64).

This edits sequencer trigs; it is not the DSP EUCLID effect. It leaves
PROJECT > CONTROL > SEQUENCER alone, so it coexists with SCALE QUANTIZER.

## Access

Hold a TRACK key and press PAGE. Targets are the track keys held when the
window opened; with none held, the current audio track. Selecting a track
while the window is open retargets YES to that track and loads its saved
params. TRACK + PAGE again closes it, as does NO. Bare PAGE never closes
SEQ (stock step banks while open). FUNC + PAGE (SCALE SETUP) stays stock.

## Lanes

**LANE** (C) selects what A/B and the grid edit:

| LANE | A / B / grid | What YES does |
|---|---|---|
| **TRIG** | sample-trig PULSE / ROT | Rewrites note trigs; reshapes **only the current DEST** onto those notes; syncs that DEST's PLCK recipe to the TRIG rhythm |
| **PLCK** | this DEST's PLOCK PULSE / ROT | Leaves the note pattern; rewrites **only this DEST's** locks (trigless where there is no note); clears this DEST on misses - including on notes |

DEST and DEPTH always apply on YES, even while LANE is TRIG - they do not
steal focus. Scroll DEST to load that DEST's plock recipe into A/B when
LANE is PLCK. Each DEST keeps its own PULSE / ROT / DEPTH (and free mask).

Write-only: open / track switch load bank SEQ params only - never re-read
live sample trigs into the grid. **YES** bakes from PULSE/ROT (or a CUE
mask) and overwrites the track.

## Examples

Step numbers below are **1-based** (same as the unit). Black = lock on a
note. Hatched = trigless lock. White = no lock. Inverted cells on the 3x2
panel are the knobs that matter for that example.

### 1. Notes only (no DEST locks)

Empty track. LANE = **TRIG**, DEST = **PTCH**, **DEPTH = 0**, set PULSE,
**YES**:

![TRIG DEPTH 0 writes notes and clears PTCH.](../../img/seq/notes-only.png)

Notes land. Current DEST locks are cleared because DEPTH is 0.

### 2. Notes with pitch on the same steps

1. LANE = **TRIG**, set PULSE / ROT, DEST = **PTCH**, DEPTH non-zero.
2. **YES** - notes land; PTCH locks sit on those same steps; this DEST's
   PLCK recipe is synced to the TRIG rhythm.

### 3. Stack a second DEST without touching the notes

You already have notes + PTCH. Switch to LANE = **PLCK**, DEST =
**AMP VOL**, set a different PULSE / ROT, **YES**:

![PLCK writes only VOL; notes and PTCH stay.](../../img/seq/stack-vol.png)

VOL locks write on that plock rhythm (trigless where there is no note).
Notes and PTCH stay.

### 4. Regenerate trigs - keep other DEST locks

You have notes with PTCH + VOL. Keep DEST = **PTCH**, change TRIG PULSE,
**YES**:

![TRIG YES reshapes only PTCH; VOL survives as trigless where notes drop.](../../img/seq/trig-reshape.png)

- **PTCH** (current DEST) is cleared on silent steps and rewritten on the
  new notes.
- **VOL** (other DEST) is **kept**. Where a note disappears but VOL remains,
  the step becomes **trigless** so VOL stays audible.

### 5. Regenerate the same DEST from PLCK - overwrite the TRIG bake

You baked PTCH on the notes from TRIG. Switch to LANE = **PLCK**, DEST =
**PTCH**, change ROT, **YES**:

![PLCK YES clears TRIG-baked PTCH on note misses; other DEST stacks stay.](../../img/seq/plck-overwrite.png)

- **PTCH** is cleared on every miss - including on notes that still fire -
  then written on the new PLCK hits (trigless if no note).
- Other DEST stacks (VOL, FILTER, ...) are untouched.

### 6. Clear one DEST

LANE = **PLCK**, that DEST's **PULSE = 0**, **YES**:

![PLCK PULSE 0 clears PTCH; notes and other stacks stay.](../../img/seq/clear-dest.png)

Clears this DEST over the fill range. Notes stay. Orphan trigless bits drop
when nothing else remains on the step.

### 7. CUE then YES

1. Focus the lane you want (TRIG or PLCK).
2. Set **PULSE** to the hit count you want.
3. Press **CUE** - places exactly that many hits at random on the focused
   lane (and only that lane).
4. Press **YES** to bake.

On TRIG, if the track already has sample trigs, PULSE / ROT / CUE first
open **ARE YOU SURE?**. Dialog YES only unlocks the knobs - the fill is a
separate YES.

### 8. Switch track while open

Hold another TRACK key while SEQ is open: YES retargets that track and the
panel loads that track's saved SEQ params from `euclid.work`. The previous
track is not rewritten until you YES it again.

### 9. Write-only gotcha

The live pattern on the track is **not** pulled into the grid when you open
SEQ or switch tracks. The grid always shows the saved bank recipe. Edit
PULSE/ROT (or CUE), then **YES** to overwrite the track. If you expect "what
I see on the trigs" to appear in the grid without YES, that is not this
module.

### 10. CX OSC SETUP destinations

On a CX OSC track, DEST can also target SETUP slots **CAR / MOD / SYMM /
FDBK / PWM** (LFO PMTR 30..34). Same TRIG/PLCK rules: TRIG locks them onto
notes; PLCK can stack them trigless; PLCK miss clears that DEST even on
notes.

## DEPTH

At 0, YES clears that DEST for the path in use. Non-zero:

- **PTCH** - in-scale around Part PLAYBACK PTCH (misses fall back to Part).
- **AMP VOL** - unipolar below Part AMP VOL.
- **Any other DEST** - uniform `[Part+/-DEPTH]` clamped 0..127.

DEST matches LFO SETUP PMTR (PAGE / PARAM). 0..29 page-1 flats (AMP XVOL
skipped); on CX OSC also 30..34 SETUP slots (stackable in DRAM).

## Persistence and CUE

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
| TRACK + PAGE | open / close |
| TRACK (while open) | switch to that track's params / YES target |
| A | PULSE of the focused lane |
| B | ROT of the focused lane |
| C | LANE - TRIG / PLCK |
| D | DEST |
| E | DEPTH |
| F | empty |
| CUE | random placement of exactly PULSE hits on the focused lane |
| YES | write TRIG mask + current DEST locks (and trigless where needed) |
| NO | close |
