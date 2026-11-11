# `euclid-fill` — EUCLID FILL

Author: [ilia-murzinov](https://github.com/ilia-murzinov). Rhythm math matches
filter [EUCLID](../euclid/README.md) ([repeat98](https://github.com/repeat98)).

A standalone Euclidean **sample-trig + p-lock** fill page. Hold a **TRACK**
key and press **PAGE**: a window opens (no title band), a stock SETUP-style
3×2 dotted grid (A=PULSE B=ROT C=LANE / D=DEST E=DEPTH; **F** empty), and a
live pattern grid (4×16 hollow/filled squares for all ≤64 steps; last row
= length mod 16). **LANE** selects whether A/B and the grid edit the **TRIG**
rhythm or the **PLOCK** rhythm for the current DEST. **YES** writes TRIG →
sample-trig mask 0 and PLOCK → locks on the chosen DEST (trigless-lock bits
on plock-only steps); **NO** or TRACK+PAGE again closes. Bare **PAGE** stays
stock (step banks) and does **not** close the window.

**Layout tip (HW, CX EUCL52, Ilia 2026-11-10):** `WINW=109` @ `WINX=0`
(19px for T5–8), no `WFRAME`, 1px top+bottom `RULE`, DEST = PAGE+PARAM
(no PMTR caption). Do not “center” or widen back over the track types.

Not the DSP [EUCLID](../euclid/README.md) effect (filter/amp modulation).
This module only edits sequencer trigs. It does not grow
`PROJECT > CONTROL > SEQUENCER`, so it coexists with SCALE QUANTIZER.

Rhythm names, ranges, and the TRIG PULSE default match filter EUCLID; length
is sourced from pattern length (not a knob). Encoders **A** / **B** / **C** /
**D** / **E** map to the five filled cells.

## Controls

| control | does |
|---|---|
| TRACK + PAGE | open / close (bare PAGE does not close) |
| TRACK (while open) | switch to that track's params / YES target |
| LEFT / RIGHT | unused (all steps visible) |
| A | PULSE of the focused lane |
| B | ROT of the focused lane |
| C | LANE — TRIG ↔ PLCK |
| D | DEST — page-1 flat; same name as LFO PMTR |
| E | DEPTH — 0..127, lock span around Part |
| F | empty |
| CUE | random placement of exactly PULSE hits on the focused lane |
| YES | write TRIG mask + current DEST locks (trigless where needed) |
| NO | close |

PAGE / UP / DOWN / LEFT / RIGHT / PROJ / PART / AED / ARR are **omitted**
from `EF_KEYS` (not listed — a `0` swallows; a `-1` row still clears the
sub-map). `ef_page` only toggles on TRACK+PAGE; bare PAGE is stock even
while open. Soft dialog keeps the layer so knobs stay locked (`ef_ask`);
user/orphan close pops it (`ef_layer_on`). LEVEL does nothing.

Targets are the track keys held when the window opened. If none were
held, the current audio track is used. Selecting a track while open
retargets YES to that track and loads its per-track params. DEPTH and
PLOCK PULSE/ROT are remembered **per DEST** on that track. D/E stay live
even when LANE is TRIG (no auto-focus switch). Slots + DEST tables live in
DRAM and in `euclid.work (bank + per-DEST depth/plock + per-track LANE)` (STORE client, `EF_VER` 3) on SAVE PROJECT /
bank write. Multi-target YES writes each target's own stored params.
**Pattern length** shows in the title gutter (`LEN n`), not as a row.
Defaults: TRIG PULSE 5, DEST = AMP VOL, ROT/DEPTH/PLOCK PULSE 0, LANE = TRIG.

Write-only: open / track switch load bank Euclid params only — the grid
never mirrors live sample trigs. Edits outside FILL are not re-read;
YES overwrites from PULSE/ROT (or a CUE mask).

**CUE** keeps **PULSE** as density on the focused lane and only randomizes
*which* steps are on. Changing **PULSE** leaves free mode and returns to
Euclidean. PULSE / ROT / CUE with sample trigs already present open stock
**ARE YOU SURE?** only when LANE is TRIG. Dialog YES unlocks knobs/CUE
only; fill is a separate YES.

**DEST** matches LFO SETUP PMTR targets. **0..29** page-1 lock flats
(**AMP XVOL** skipped). On **CX OSC**, **30..34** SETUP knobs stack in DRAM.

**DEPTH** (0..127): at 0, YES clears that DEST's locks for the path in
use (TRIG: reshape to trig set; PLOCK: clear on hits/misses). Non-zero:

- **DEST = PTCH:** in-scale around Part PLAYBACK PTCH. Bare note trigs
  without a plock hit carry the last plock pitch (else Part).
- **DEST = AMP VOL:** unipolar below Part AMP VOL.
- **Any other DEST:** uniform `[Part−DEPTH .. Part+DEPTH]` clamped 0..127.

**LANE = TRIG:** YES writes DEST/DEPTH locks on the sample-trig steps
and syncs that DEST's plock recipe to the TRIG rhythm (lock layer = trigs).
**LANE = PLCK:** independent plock rhythm; plock-only → trigless (+0x10);
miss / PULSE 0 clears this DEST only (other DEST locks stay). PULSE 0 also
drops orphan trigless bits when no other DEST remains on the step. To erase
TRIG-baked locks, zero that DEST's PLCK PULSE and YES on **PLCK** (TRIG YES
with DEPTH > 0 re-applies and re-syncs the recipe).


YES writes **only** the selected DEST's lock bytes (plus the TRIG mask).
A later fill with another DEST leaves earlier locks alone.
