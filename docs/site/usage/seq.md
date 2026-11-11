A Euclidean fill for sample trigs and per-destination p-locks. Hold a TRACK
key and press PAGE: a window opens (stock 3×2 grid with PULSE / ROT / LANE /
DEST / DEPTH, F empty, LEN on the left, and a 4×16 grid of hollow/filled
squares for every step up to 64).

This edits sequencer trigs; it is not the DSP EUCLID effect. It leaves
PROJECT > CONTROL > SEQUENCER alone, so it coexists with SCALE QUANTIZER.

## Access

Hold a TRACK key and press PAGE. Targets are the track keys held when the
window opened; with none held, the current audio track. Selecting a track
while the window is open retargets YES to that track and loads its saved
params. TRACK + PAGE again closes it, as does NO. Bare PAGE never closes
Euclid (stock step banks while open). FUNC + PAGE (SCALE SETUP) stays stock.

## Lanes

**LANE** (C) selects what A/B and the grid edit:

| LANE | A / B / grid | What YES does |
|---|---|---|
| **TRIG** | sample-trig PULSE / ROT | Rewrites note trigs; reshapes **only the current DEST** onto those notes; syncs that DEST's PLCK recipe to the TRIG rhythm |
| **PLCK** | this DEST's PLOCK PULSE / ROT | Leaves the note pattern; rewrites **only this DEST's** locks (trigless where there is no note); clears this DEST on misses - including on notes |

DEST and DEPTH always apply on YES, even while LANE is TRIG - they do not
steal focus. Scroll DEST to load that DEST's plock recipe into A/B when
LANE is PLCK. Each DEST keeps its own PULSE / ROT / DEPTH (and free mask).

Write-only: open / track switch load bank Euclid params only - never
re-read live sample trigs into the grid. **YES** bakes from PULSE/ROT
(or a CUE mask) and overwrites the track.

## Examples

### 1. Trig fill with pitch on the notes

1. LANE = **TRIG**, set PULSE / ROT, DEST = **PTCH**, DEPTH as wanted.
2. **YES** - notes land; PTCH locks sit on those same steps; this DEST's
   PLCK recipe is synced to the TRIG rhythm.

### 2. Stack a second DEST without touching the notes

1. LANE = **PLCK**, DEST = **AMP VOL**, set a different PULSE / ROT.
2. **YES** - VOL locks write on that plock rhythm (trigless where there is
   no note). Notes and PTCH stay.

### 3. Regenerate trigs - keep other DEST locks

You have notes with PTCH + VOL. Change TRIG PULSE (DEST still PTCH) and
**YES**:

![TRIG YES reshapes only PTCH; VOL survives as trigless where notes drop.](../../img/seq/trig-reshape.png)

- **PTCH** (current DEST) is cleared on silent steps and rewritten on the
  new notes.
- **VOL** (other DEST) is **kept**. Where a note disappears but VOL remains,
  the step becomes **trigless** so VOL stays audible.

### 4. Regenerate the same DEST from PLCK - overwrite the TRIG bake

You baked PTCH on the notes from TRIG. Switch to LANE = **PLCK**, DEST =
**PTCH**, change ROT, **YES**:

![PLCK YES clears TRIG-baked PTCH on note misses; other DEST stacks stay.](../../img/seq/plck-overwrite.png)

- **PTCH** is cleared on every miss - including on notes that still fire  - 
  then written on the new PLCK hits (trigless if no note).
- Other DEST stacks (VOL, …) are untouched.

### 5. Clear one DEST

LANE = **PLCK**, that DEST's **PULSE = 0**, **YES**. Clears this DEST over
the fill range and drops orphan trigless bits when nothing else remains on
the step.

## DEPTH

At 0, YES clears that DEST for the path in use. Non-zero:

- **PTCH** - in-scale around Part PLAYBACK PTCH (misses fall back to Part).
- **AMP VOL** - unipolar below Part AMP VOL.
- **Any other DEST** - uniform `[Part±DEPTH]` clamped 0..127.

DEST matches LFO SETUP PMTR (PAGE / PARAM). 0..29 page-1 flats (AMP XVOL
skipped); on CX OSC also 30..34 SETUP slots (stackable in DRAM).

## Persistence and CUE

PULSE / ROT / DEST / LANE / free mask / per-DEST DEPTH and PLOCK rhythms
persist in `euclid.work` (STORE client). Defaults: TRIG PULSE 5, DEST =
AMP VOL, ROT / DEPTH / PLOCK PULSE 0, LANE = TRIG.

CUE randomizes the focused lane only (density = PULSE). PULSE / ROT / CUE
on TRIG with existing sample trigs open **ARE YOU SURE?**; dialog YES only
unlocks knobs - fill is a separate YES. PLOCK edits do not prompt.

When a step's last lock is cleared, orphan trigless bits drop and the
plock LED bitmap refreshes (empty note trigs stop blinking yellow).

## Controls

| Control | Does |
|---|---|
| TRACK + PAGE | open / close |
| TRACK (while open) | switch to that track's params / YES target |
| A | PULSE of the focused lane |
| B | ROT of the focused lane |
| C | LANE - TRIG ↔ PLCK |
| D | DEST |
| E | DEPTH |
| F | empty |
| CUE | random placement of exactly PULSE hits on the focused lane |
| YES | write TRIG mask + current DEST locks (and trigless where needed) |
| NO | close |
