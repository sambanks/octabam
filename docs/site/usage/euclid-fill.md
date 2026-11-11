A Euclidean fill for sample trigs. Hold a TRACK key and press PAGE, and a
window opens (stock 3×2 grid with PULSE / ROT / DEST / DEPTH and C/F empty,
LEN on the left, and a 4×16 grid of hollow/filled squares for every step
up to 64 — last row length = pattern length mod 16). YES writes the
rhythm onto the held tracks' sample-trig mask, with optional locks on one
chosen page-1 knob (same set as LFO SETUP PMTR). CUE places a random
k-subset with density PULSE.

This edits sequencer trigs; it is not the DSP EUCLID effect, which
modulates filter or amplitude. It leaves PROJECT > CONTROL > SEQUENCER
alone, so it coexists with SCALE QUANTIZER.

## Access

Hold a TRACK key and press PAGE. Targets are the track keys held when the
window opened; with none held, the current audio track. Selecting a track
while the window is open retargets YES to that track and loads its saved
params. TRACK + PAGE again closes it, as does NO. Bare PAGE never closes
Euclid (stock step banks while open). FUNC + PAGE (SCALE SETUP) stays stock.

## Operation

- Pattern length shows as `LEN n` in the left gutter; it is not a knob.
- On open (and when you switch track while open), the grid mirrors that
  track’s **existing sample trigs** — even if they were not written by
  Euclid. Empty tracks stay on the Euclidean PULSE/ROT preview. Edit
  trigs on the sequencer with FILL closed, then reopen to re-seed.
  Editing PULSE leaves free mode and returns to Euclidean.
- PULSE / ROT / DEST (and a CUE free mask) are kept per track. DEPTH is
  remembered per track × DEST (0 if never set): scrolling DEST shows that
  value. Edits and YES fills update it. All of that persists in
  `euclid.work` across SAVE PROJECT / reload / power-up. Defaults are
  PULSE 5, DEST = AMP VOL, ROT/DEPTH 0.
- Selecting a track switches the page to that track's params.
- DEST matches LFO SETUP PMTR targets on the focused track: **PAGE** /
  **PARAM** (e.g. `AMP` / `VOL`, `SRC` / `PTCH`), same rows as DEPTH. **0..29** are page-1 lock flats
  (**AMP XVOL** skipped). On a **CX OSC** track the list continues to
  **30..34** (`SRC CAR` / `MOD` / `SYMM` / `FDBK` / `PWM`); YES stores those
  per step in a DRAM bank (`ef_cx_bank`) so fills **stack** (PWM then
  FOLD, or CAR then PWM, keeps both). **CX OSC** applies the armed slots
  to PLAYBACK SETUP each sequencer step while the pattern plays.
- DEPTH (0..127) scales lock spread. At 0, YES clears that DEST's locks on
  the fill range and writes no new ones.
- DEST = PTCH keeps the in-scale path: range around Part PLAYBACK PTCH
  (±24 semitones FM/SY, ±12 sample at DEPTH 127). SCALE OFF or no
  quantizer: no PTCH locks.
- DEST = AMP VOL: locks stay at or below the AMP page VOL
  (`Part − r·DEPTH/127`) — never louder than the Part volume.
- Other DEST values: uniform pick in `[Part−DEPTH .. Part+DEPTH]`,
  clamped 0..127.
- YES only touches the selected DEST's lock bytes, so a later fill on
  another DEST leaves earlier locks alone (pitch, then volume, …).
- CUE keeps PULSE as density and randomizes which steps are on. Editing
  PULSE leaves free mode and returns to Euclidean.
- PULSE / ROT / CUE with sample trigs already in the fill range open
  **ARE YOU SURE?** (stock YES/NO): existing trigs will be cleared on the
  next fill. While it is up every knob is locked. YES unlocks
  PULSE/ROT/CUE; NO cancels. Trig rewrite is only the next fill YES.
- YES writes each target with **that track's** stored params. NO closes.

## Controls

| Control | Does |
|---|---|
| TRACK + PAGE | open / close |
| TRACK (while open) | switch to that track's params / YES target |
| LEFT / RIGHT | unused (all steps visible) |
| A | PULSE |
| B | ROT |
| C | empty |
| D | DEST |
| E | DEPTH |
| F | empty |
| CUE | random placement of exactly PULSE hits |
| YES | write the trigs and DEST locks on the targets |
| NO | close |

PAGE / UP / DOWN / LEFT / RIGHT are unbound on the key layer (PAGE
close is only the TRACK+PAGE detour, so stock step-bank PAGE still
works after a length change). LEVEL does nothing.
