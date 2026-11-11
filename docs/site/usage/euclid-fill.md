A Euclidean fill for sample trigs and per-destination p-locks. Hold a TRACK
key and press PAGE: a window opens (stock 3×2 grid with PULSE / ROT / LANE /
DEST / DEPTH, F empty, LEN on the left, and a 4×16 grid of hollow/filled
squares for every step up to 64). YES writes the **TRIG** rhythm onto the
held tracks' sample-trig mask, and locks for the current DEST from that
DEST's **PLOCK** rhythm. Steps that get a lock without a sample trig become
trigless locks. CUE places a random k-subset with density PULSE on the
focused lane.

This edits sequencer trigs; it is not the DSP EUCLID effect. It leaves
PROJECT > CONTROL > SEQUENCER alone, so it coexists with SCALE QUANTIZER.

## Access

Hold a TRACK key and press PAGE. Targets are the track keys held when the
window opened; with none held, the current audio track. Selecting a track
while the window is open retargets YES to that track and loads its saved
params. TRACK + PAGE again closes it, as does NO. Bare PAGE never closes
Euclid (stock step banks while open). FUNC + PAGE (SCALE SETUP) stays stock.

## Operation

- Pattern length shows as `LEN n` in the left gutter; it is not a knob.
- Window title stays **EUCLID** on both lanes (LANE is only the C cell).
- **LANE** (C) selects what A/B and the grid edit: **TRIG** (sample trigs)
  or **PLCK** (locks for the current DEST). DEST and DEPTH always work,
  even while LANE is TRIG — they do not steal focus.
- Each DEST keeps its own PLOCK PULSE/ROT (and DEPTH), like a stack of
  fill recipes. Scroll DEST to load that DEST's plock rhythm into the
  working knobs when LANE is PLCK.
- On open (and track switch), the TRIG grid mirrors existing sample trigs
  when any are present. Empty tracks stay on the Euclidean PULSE/ROT
  preview.
- PULSE / ROT / DEST / LANE / free mask / per-DEST DEPTH and PLOCK rhythms
  persist in `euclid.work` (bank, per-DEST depth/plock incl. free mask, per-track LANE).
  Defaults: TRIG PULSE 5, DEST = AMP VOL,
  ROT/DEPTH/PLOCK PULSE 0, LANE = TRIG.
- DEST matches LFO SETUP PMTR (PAGE / PARAM). 0..29 page-1 flats (AMP XVOL
  skipped); on CX OSC also 30..34 SETUP slots (stackable in DRAM).
- DEPTH 0 clears that DEST's locks on the fill range when the plock lane
  is active (PULSE > 0). Non-zero: PTCH in-scale; AMP VOL unipolar below
  Part; else `[Part±DEPTH]`.
- YES with PLOCK PULSE 0 writes **trigs only** and leaves existing DEST
  locks alone. With PLOCK active: plock hits get locks; plock-only steps
  get a trigless lock; PTCH on a note trig without a plock hit carries the
  last plock pitch (else Part) so stock restore-at-next-trig does not snap.
- CUE randomizes the focused lane only. PULSE / ROT / CUE on TRIG with
  existing sample trigs open ARE YOU SURE?; PLOCK edits do not.

## Controls

| Control | Does |
|---|---|
| TRACK + PAGE | open / close |
| TRACK (while open) | switch to that track's params / YES target |
| A | PULSE of the focused lane |
| B | ROT of the focused lane |
| C | LANE — TRIG ↔ PLCK |
| D | DEST |
| E | DEPTH |
| F | empty |
| CUE | random placement of exactly PULSE hits on the focused lane |
| YES | write TRIG mask + current DEST locks (and trigless where needed) |
| NO | close |
