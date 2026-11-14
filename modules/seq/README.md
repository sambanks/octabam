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

**Proof.HARDWARE:** author's MKII, `CX CJ.RMX`, 14 Nov 2026. All six
reported checks passed: PLCK **PULS** 0 clears only that destination;
all three **[FUNC]** + **[BANK]** clear rows act immediately and return to
SEQ, and **[NO]** cancels; **"ARE YOU SURE?"** stays above SEQ with knobs
locked until answered; stock TRACK shortcuts work; **[CUE]** + **[TRACK]**
cues without randomizing while bare **[CUE]** randomizes the focused lane;
and with SCALE off, pitch locks match the Part's PLAYBACK PTCH. This report
covers those interactions on MKII. It does not claim audio testing or MKI
behavior. The port gates also pass: `verify_seq`, `verify_seq_func_bank`
and `verify_seq_scenarios`.

Historical hardware report: author's MKII, CX EUCL93, 11 Nov 2026,
dual LANE, write-only YES, LOCK_COLL + floor, PLCK overwrite and TRIG
reshape preserving other destinations. That report predates these changes.

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
| CUE | hold = stock cue; release alone = random PULSE hits on the focused lane; CUE+TRACK = cue that track |
| TRACK (stock) | double-tap QUICK ASSIGN; FUNC+TRACK mute; TRACK+PLAY/STOP/BANK as stock |
| FUNC + BANK | clear menu (LISTPOP over SEQ): CLEAR DEST / CLEAR ALL DEST / CLEAR ALL+TRIGS |
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

- **DEST = PTCH:** SCALE ON = in-scale around Part PLAYBACK PTCH; SCALE OFF
  = that Part PTCH on every hit (trigless when PLCK). Silent / PLCK misses
  fall back to Part.
- **DEST = AMP VOL:** unipolar below Part AMP VOL.
- **Any other DEST:** uniform `[Part−DEPTH .. Part+DEPTH]` clamped 0..127.

**LANE = TRIG:** YES writes DEST/DEPTH locks on the sample-trig steps
and syncs that DEST's plock recipe to the TRIG rhythm. Only **this DEST**
is reshaped — other DEST locks stay; if a step loses its note trig but
still holds another DEST, it becomes trigless so those locks remain
audible. **LANE = PLCK:** independent plock rhythm; plock-only → trigless
(+0x10); miss / PULSE 0 clears this DEST on every step in range —
including note trigs — so a PLCK YES **overwrites** locks previously placed
from TRIG for that DEST (other DEST locks stay). PULSE 0 uses the same
clear helper as DEPTH 0 (stale free/CUE masks ignored) and drops orphan
trigless bits when no other DEST remains on the step.

YES writes **only** the selected DEST's lock bytes (plus the TRIG mask).
A later YES with another DEST leaves earlier locks alone.

**FUNC + BANK** while SEQ is open opens a three-row LISTPOP for wiping
pattern data without a new Euclidean fill:

1. **CLEAR DEST** - this DEST's locks only; sample trigs stay; that DEST's
   DEPTH / PLOCK PULSE / ROT / free mask → 0.
2. **CLEAR ALL DEST** - every SEQ DEST on the track; sample trigs stay;
   all per-DEST params → 0.
3. **CLEAR ALL+TRIGS** - row 2, then wipe sample trigs; TRIG PULSE 5 /
   ROT 0.

Class-5 SEQ soft-closes while the list is up (stacking SEQ on top hid the
menu on hardware). A NO-only layer sits above LISTPOP so one NO closes and
restores SEQ. List YES runs the clear immediately (no second SEQ YES) and
restores SEQ. BANK again does the same. Outside SEQ the chord is stock
**TRACK TRIG EDIT** on MKII (`0x4007c0d0`) / PATTERN SETTINGS on MKI
(`0x40058a64`).

### FUNC+BANK hook (MKII / BRAIN)

MKII FUNC-held keys live in a table pointed from FUNC's sub-map
(`PARTS.md` MKI site `0x40058a64` is not the MKII path). On CX, **BRAIN**
SymbolRefs the MKII FUNC keys pointer (`0x400bfa36`) to a DRAM clone
`brain_func_keys`, so a ROM press patch at the stock table never runs.
SEQ Detours TRACK TRIG EDIT entry `0x4007c0d0` instead: SEQ open → clear
LISTPOP; else stock. MKI still SymbolRefs the ROM FUNC+BANK press field.
Port (`--mkii`, remix `cx`): CLEAR DEST labels; one NO / list YES / FUNC+BANK
again restores SEQ. FUNC+BANK is Detour/SymbolRef only (no EF_KEYS BANK) so
the list does not toggle open/closed on a single chord.
`verify_seq_func_bank.py` and `verify_seq_scenarios.py` cover the cases.

Manual site: [`docs/site/usage/seq.md`](../../docs/site/usage/seq.md).
