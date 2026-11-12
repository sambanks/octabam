# `seq` - SEQ

Author: [ilia-murzinov](https://github.com/ilia-murzinov). Rhythm math matches
filter [EUCLID](../euclid/README.md) ([repeat98](https://github.com/repeat98)).

The name **SEQ** is from the SEQ submenu on Digitakt II and Digitone II —
a dedicated window, not a PROJECT menu entry.

Hold a **TRACK** key and press **PAGE**: SEQ opens for that track — title
SEQ, LEN gutter, stock 3×2 (A=PULSE B=ROT C=LANE / D=DEST E=DEPTH; **F**
empty), and a 4×16 step grid (hollow / solid) for all ≤64 steps. **LANE**
selects whether A/B and the grid edit the **TRIG** rhythm or the **PLOCK**
rhythm for the current DEST. **YES** writes TRIG → sample-trig mask 0 and
PLOCK → locks on the chosen DEST (trigless on plock-only steps). **NO**
closes. Bare **PAGE** stays stock and does not close SEQ.

**Proof.HARDWARE** on author's MKII (CX EUCL93, 11 Nov 2026): dual LANE /
write-only YES / LOCK_COLL + floor / PLCK overwrite / TRIG reshape keeps
other DEST (TL promote).

Not the DSP [EUCLID](../euclid/README.md) effect (filter/amp modulation).
This module only edits sequencer trigs. It does not grow
`PROJECT > CONTROL > SEQUENCER`, so it coexists with SCALE QUANTIZER.

Rhythm names, ranges, and the TRIG PULSE default match filter EUCLID; length
comes from pattern length (not a knob).

## Controls

| control | does |
|---|---|
| TRACK + PAGE | open SEQ on that track |
| TRACK (while open) | switch to that track's params / YES target |
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
sub-map). Soft dialog keeps the layer so knobs stay locked (`ef_ask`);
user/orphan close pops it (`ef_layer_on`). LEVEL does nothing.

Hold TRACK + PAGE opens SEQ on that track. Selecting another track while
open retargets YES and loads that track's per-track params. DEPTH and
PLOCK PULSE/ROT are remembered **per DEST** on that track. D/E stay live
even when LANE is TRIG (no auto-focus switch). Slots + DEST tables live in
DRAM and in `euclid.work` (bank + per-DEST depth/plock + per-track LANE)
(STORE client, `EF_VER` 4) on SAVE PROJECT / bank write. **Pattern length**
shows in the title gutter (`LEN n`), not as a row. Defaults: TRIG PULSE 5,
DEST = AMP VOL, ROT/DEPTH/PLOCK PULSE 0, LANE = TRIG.

Write-only: open / track switch load bank SEQ params only — the grid never
mirrors live sample trigs. YES overwrites from PULSE/ROT (or a CUE mask).
When a step's last lock is cleared, orphan trigless bits drop and stock's
plock LED bitmap is rebuilt (`0x400339d8`).

**CUE** keeps **PULSE** as density on the focused lane and only randomizes
*which* steps are on. Changing **PULSE** leaves free mode and returns to
Euclidean. PULSE / ROT / CUE with sample trigs already present open stock
**ARE YOU SURE?** only when LANE is TRIG. Dialog YES unlocks knobs/CUE
only; writing the pattern is a separate YES.

**DEST** matches LFO SETUP PMTR targets. **0..29** page-1 lock flats
(**AMP XVOL** skipped). On **CX OSC**, **30..34** SETUP knobs stack in DRAM.

**DEPTH** (0..127): at 0, YES clears that DEST's locks for the path in
use (TRIG: reshape to trig set; PLOCK: clear on hits/misses). Non-zero:

- **DEST = PTCH:** in-scale around Part PLAYBACK PTCH (silent steps /
  PLCK misses fall back to Part).
- **DEST = AMP VOL:** unipolar below Part AMP VOL.
- **Any other DEST:** uniform `[Part−DEPTH .. Part+DEPTH]` clamped 0..127.

**LANE = TRIG:** YES writes DEST/DEPTH locks on the sample-trig steps
and syncs that DEST's plock recipe to the TRIG rhythm. Only **this DEST**
is reshaped — other DEST locks stay; if a step loses its note trig but
still holds another DEST, it becomes trigless so those locks remain
audible. **LANE = PLCK:** independent plock rhythm; plock-only → trigless
(+0x10); miss / PULSE 0 clears this DEST on every step in range —
including note trigs — so a PLCK YES **overwrites** locks previously placed
from TRIG for that DEST (other DEST locks stay). PULSE 0 also drops orphan
trigless bits when no other DEST remains on the step.

YES writes **only** the selected DEST's lock bytes (plus the TRIG mask).
A later YES with another DEST leaves earlier locks alone.

Manual site: [`docs/site/usage/seq.md`](../../docs/site/usage/seq.md).
