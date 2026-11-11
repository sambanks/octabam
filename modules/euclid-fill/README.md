# `euclid-fill` — EUCLID FILL

Author: [ilia-murzinov](https://github.com/ilia-murzinov). Rhythm math matches
filter [EUCLID](../euclid/README.md) ([repeat98](https://github.com/repeat98)).

A standalone Euclidean **sample-trig** fill page. Hold a **TRACK** key and
press **PAGE**: a window opens (no title band), a stock SETUP-style 3×2
dotted grid (A=PULSE B=ROT / D=DEST E=DEPTH; **C** and **F** empty), and a
live pattern grid (4×16 hollow/filled squares for all ≤64 steps; last row
= length mod 16). **YES** writes the rhythm onto the held track(s)'
sample-trig mask and optional locks on **one** chosen page-1 knob; **NO**
or TRACK+PAGE again closes. Bare **PAGE** stays stock (step banks) and
does **not** close the window.

**Layout tip (HW, CX EUCL52, Ilia 2026-11-10):** `WINW=109` @ `WINX=0`
(19px for T5–8), no `WFRAME`, 1px top+bottom `RULE`, DEST = PAGE+PARAM
(no PMTR caption). Do not “center” or widen back over the track types.

Not the DSP [EUCLID](../euclid/README.md) effect (filter/amp modulation).
This module only edits sequencer trigs. It does not grow
`PROJECT > CONTROL > SEQUENCER`, so it coexists with SCALE QUANTIZER.

Rhythm names, ranges, and the PULSE default match filter EUCLID; length is
sourced from pattern length (title only — not a knob). Encoders **A** / **B**
/ **D** / **E** map to the four filled cells.

## Controls

| control | does |
|---|---|
| TRACK + PAGE | open / close (bare PAGE does not close) |
| TRACK (while open) | switch to that track's params / YES target |
| LEFT / RIGHT | unused (all steps visible) |
| A | PULSE |
| B | ROT |
| C | empty |
| D | DEST — page-1 flat; same name as LFO PMTR |
| E | DEPTH — 0..127, lock span around Part |
| F | empty |
| CUE | random placement of exactly PULSE hits (not Euclidean) |
| YES | write the current bar + DEST locks on the targets |
| NO | close |

PAGE / UP / DOWN / LEFT / RIGHT / PROJ / PART / AED / ARR are **omitted**
from `EF_KEYS` (not listed — a `0` swallows; a `-1` row still clears the
sub-map). `ef_page` only toggles on TRACK+PAGE; bare PAGE is stock even
while open. Soft dialog keeps the layer so knobs stay locked (`ef_ask`);
user/orphan close pops it (`ef_layer_on`). LEVEL does nothing.

Targets are the track keys held when the window opened. If none were
held, the current audio track is used. Selecting a track while open
retargets YES to that track and loads its per-track params (PULSE / ROT /
DEST / DEPTH / free mask). DEPTH is also remembered **per DEST** on that
track (0 until set): scrolling DEST reloads it; editing DEPTH or YES
stores it. Slots + the DEST-depth table live in DRAM and in `euclid.work`
(STORE client) on SAVE PROJECT / bank write, restored on load and
power-up. Multi-target YES writes each target's own stored params.
**Pattern length** shows in the title (`T1 16`), not as a row. Defaults:
PULSE 5, DEST = AMP VOL, ROT/DEPTH 0.

On open / track switch, if the track already has sample trigs in the fill
range (manual, paste, or a prior fill), those bits seed the grid (`ef_free`)
so the squares match the sequencer. Empty tracks keep the Euclidean
PULSE/ROT preview. There is no live pad sync while FILL is open — close
and reopen (or switch track) to re-seed after editing trigs on the
sequencer.

**CUE** keeps **PULSE** as density and only randomizes *which* steps are
on (uniform k-subset). **ROT** still shifts that mask. Changing **PULSE**
leaves free mode and returns to Euclidean.

**PULSE / ROT / CUE** with sample trigs already in the fill range open
stock **ARE YOU SURE?** (YES unlocks edit; NO cancels). Trig rewrite is
only the next fill YES. **DEST** / **DEPTH** stay editable without a
prompt.

**DEST** matches LFO SETUP PMTR targets: **PAGE** / **PARAM**
(`AMP` over `VOL`, `SRC` over `PTCH`, …). **0..29** are page-1 lock flats (PLAYBACK /
LFO / AMP / FX1 / FX2 × 6); **AMP XVOL** is skipped. On **CX OSC**,
**30..34** (`SRC CAR` / `MOD` / `SYMM` / `FDBK` / `PWM`) are listed too —
YES stores them per step in `ef_cx_bank` / `ef_cx_bits` so later fills
(FOLD, or another SETUP dest) do not erase earlier CX SETUP locks.
**CX OSC** (`HAVE_EF_CX`) applies those slots into CURVALS SETUP each
sequencer step while the pattern plays.

**DEPTH** (0..127) is how far locks may sit from the Part value. At 0,
YES clears that DEST's locks on the fill range. Non-zero:

- **DEST = PTCH:** in-scale range around Part PLAYBACK PTCH. DEPTH 127 =
  ±24 semitones (±2 octaves) on FM/SY; sample tracks ±12. Degrees use
  `(ROOT + base_st + delta) mod 12` against SCALE QUANTIZER. Sample:
  `raw = 64+5·st`; FM/SY (`"FM",1` / `"SY",1`): `raw = 64+st`. No
  quantizer / SCALE OFF: no pitch locks.
- **DEST = AMP VOL:** unipolar below Part AMP VOL — `Part − r·DEPTH/127`,
  never louder than the AMP page volume.
- **Any other DEST:** uniform pick in `[Part−DEPTH .. Part+DEPTH]`
  (clamped to 0..127).

YES writes **only** the selected DEST's lock bytes on steps 0..n−1. A
later fill with another DEST leaves earlier locks alone (pitch, then
volume, then an FX knob, …).

FUNC + PAGE (SCALE SETUP) and PAGE alone stay stock.

## Measured

- Not yet: the fill writer follows the bank-blob + battery-mirror + dirty
  recipe from ERASE_EMPTY_TRIGLESS_LOCKS; the window stack follows TUNER.
- `make check REMIX=euclid-fill` builds and boots under the ColdFire port.
- `tools/verify/verify_euclid_fill.py` checks the Euclidean bit pattern
  against the same `(i·k) % n < k` law as `modules/euclid/control.c`, plus
  the CUE/`ef_rng` d1-clobber hang model, DEST/DEPTH / in-scale PTCH math,
  and the per-track DRAM bank.

## On the unit

Prior RAND VEL / RAND PTCH page: author BUILD **34** (`minimal` remix),
CF, MKII, 16 Oct 2026. **DEST / DEPTH** and **per-track select** not yet
unit-confirmed on this tip.

## Gates

`tools/verify/verify_euclid_fill.py` (stage `image`) — fast, no port:

- Euclidean bit patterns (`(i·k) % n < k`, same as filter EUCLID)
- UI contract on `euclid_fill.s`: no title, stock 3×2 (A/B/D/E =
  PULSE/ROT/DEST/DEPTH, C/F empty), dotted grid, 4×16 hollow/filled
  pattern squares (all ≤64 steps), arrows unbound, no invert,
  LEVEL noop, PULSE default 5, DEST default VOL, length via
  `ef_sync_len`, single-DEST lock writer, per-track `ef_bank` / follow-UI
