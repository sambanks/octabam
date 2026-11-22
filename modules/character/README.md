# `character` — CHARACTER

The station that dirties or tightens a track: fold, saturate, tilt,
compress, width, mix.

On id 0x17 (stock LO-FI keeps 0x1c), FX1 only: an FX2 instance runs as a dry pass
(`Claims(fx1_only=True)`, `verify_character.py`); the FX2 chooser hides the
row. The chain is fixed: fold → saturate → tilt → compress → width → mix,
distortion before dynamics. The saturation and compressor laws are
JClones' (MIT; TapeHead, DaTube, OInflator, AC1), re-derived here (Sources,
below). Defaults are a bit-exact passthrough (DRV 0, FOLD 0, TONE 64, COMP
0, MIX 127, WDTH 64; KEY SELF, KLVL 64): a part that stored LO-FI runs
this. A part's stored bytes are stock LO-FI's until `ot_project.py
stamp-defaults` writes ours.

**SLOTS** (build setting, store `octabam.character`): `FX1` (default) or `FX1+FX2`. With `FX1+FX2` an FX2 instance runs the station live and the FX2 chooser lists it; a remix pins it (`settings={("octabam.character", "SLOTS"): Pin("FX1+FX2")}`). `tools/verify/verify_stations_fx2.py` renders the FX2 instance against the FX1 instance, bit for bit (`remixes/test/stations-fx2`). A remix with the bus keeps the default: its cycle budget is priced with the stations on FX1.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | DRV | 0–127, default 0 | the saturator's drive (SAT picks the character). DRV 0 skips the stage, bit-exact. Since 23 Sep 2026 (Sam: "much too subtle") DRV also drives the curve's input by G = 1 + 3·DRV/128 (+12 dB at 127), on top of each mode's own law, with the output scaled per mode: TAPE ×1 (TapeHead's trim already holds its small signal at unity and its smoothstep compresses the rest; with 1/G on top a loop sat 18 dB under dry at DRV 127), TUBE ×(1+d)/G, INFL ×1/G |
| 1 | 1 | FOLD | 0–127, default 0 | a wrap-and-reflect wavefolder, 1 → 48× into the fold at a held level; first fold on a pad at ~24 |
| 1 | 2 | WDTH | bipolar, default 64 | mid/side: 64 untouched, 0 mono, 127 double sides. TXTR's slot until 22 Sep 2026 (TXTR removed after a squeal on the unit when it was touched on the master, unreproduced on the harness) |
| 1 | 3 | COMP | 0–127, default 0 | JClones AC1's console channel law: `Lv = K × level`; `gr = (Lv²/2 − 1)² + a·Lv` clamped at 1 — a dip around Lv = 1 whose depth is `a = 0.75 − 0.675·COMP/128`; makeup `1 / (1 − 0.3375·COMP/128)`. GLUE (slow, soft-kneed; 0.5 / 500 ms, K = 3) on the master BY POSITION, COMP (fast; 0.5 / 63 ms, K = 4; the release coefficient is 3024/2^23, written as 50 ms until 21 Sep 2026) on every other track; no knob for the choice. One feedforward detector on the mono key, the gain applied to both channels. COMP 0 skips the stage bit-exactly |
| 1 | 4 | TONE | bipolar, default 64 | a tilt after the saturator in every mode, drawn −64..+63: 0 flat and bit-exact, + bright, − dark: +3.5 dB above / −6 dB below the 1.2 kHz pivot at 127, the mirror at 0. It was RET, the bus return level, from 13 to 20 Sep 2026 (on T8 by dispatch position the last live engine's wet entered at the front of the chain and the hosts were stamped quiet; degraded on the unit, clean under the port, `docs/contributing/FAILURE_MODES.md`, removed) |
| 1 | 5 | MIX | 0–127, default 127 | out = x + MIX·(w − x); MIX 127 is 127/128 |
| 2 | 6 | SAT | TAPE / TUBE / INFL | TAPE = TapeHead: a state-variable split at TONE, the low and band parts through a cubic smoothstep, the top clean; drive 0.8× → 8× from a 17-word P table. TUBE = DaTube: u − u^P with the negative half driven twice as hard, level-compensated (a per-block division); the curve is a 17-pair P table. INFL = OInflator: a signed cubic, DRV is its Effect |
| 2 | 7 | KEY | SELF / T1–T8 | the compressor's key (29 Sep 2026; T2–T8 added 7 Nov 2026). SELF: the track's own mono input, per sample. T1–T8: the peak of \|mono\| (mono = (L + R) / 2) over a block of that track's input, × KLVL/64, held across the block into the same attack / release smoother. Two sources, chosen at build: with KEYBUS in the remix (modules/keybus), its key word for that track, X:$37F60 + track in the shared window (the peak of \|mono\| over the track's block, written each block by KEYBUS's dispatcher hook on the track's own core; the same read on both cores, so one window copy serves both). Without it, T1 from the BusDelay host's peak (`y:$990`, a count at `y:$991` that has not moved for 4 blocks reads as silence) and T2–T8 as SELF. No host and no tap: T1 is SELF (the `; NOBUS_KEY` line of `character.asm`). On the master (T8) KEY is ignored. A KEY byte above 8 reads as SELF |
| 2 | 8 | KLVL | 0–127, default 64 | scales the keyed track's level, 64 = unity |

Page layout history: 16 Sep 2026 put MIX bottom right and SAT top left.

## Open

- KEY's latency across cores: not measured under the port.
- LMC1 COMP (a feedback console comp) was built on 13 Sep 2026, +125 words
  over, and kept as a draft.

## Sources

The laws, from [JClones/JSFXClones](https://github.com/JClones/JSFXClones)
(MIT); licences in `THIRD_PARTY.md`:

| stage | source | the law |
|---|---|---|
| TAPE | TapeHead | Chamberlin SVF at 2.1 / 3.7 / 5 kHz; `ss(v) = 1.5v − 0.5v³` clipped ±1 on the LP and BP bands, the HP band passed at −1.157; drive 0.8x..8x = `0.8·10^((D−1)/9)`; trim 0.7. Here TONE (page-1 slot 4) sweeps the split 2.1→5 kHz |
| TUBE | DaTube | `x *= drive+0.5`; `y = x + (d/2)((1−x) − (1−x)^P)` for x>0, `x + d((1+x)^P − (1+x))` for x<0, P = ln10+1; 3 Hz DC remover. Here one table `T(u) = u − u^P`, the sign selects d/2 vs d |
| INFL | OInflator | `x *= 0.5`; `gr = clamp(2c·\|x\| + (1−c))`, `y = (1 − \|gr·x\|)(gr·x)·2e + (1−e)x`; ×2. No table, no division; Effect on DRV |
| GLUE / COMP | AC1 | level = \|x\| smoothed 0.5 ms / 500 ms; `gr = (Lv²/2 − 1)² + Lv·a`, `a = 0.75 − (Comp−1)·0.075`, clamp ≤ 1; a polynomial gain per sample, no table |
| (draft) COMP | LMC1 | feedback console comp: sidechain HP 340 Hz → LP 4 kHz → ×gr → square → 2.5 / 25 ms smoother → √; hard knee, `gr = (L/thr)^−3.077` (≈4:1), −40 dB floor; ported as the power per block: one division + a 33-entry table of r^−1.538 |

FUZZ (SAT's third slot before INFL) and TRNS were retired 13 Sep 2026.
Not ported: TubeDriver (`t/(t+bias)`, a division per sample); the full
SatBuss (13 one-poles and a feedback mesh); a reduced SatBuss (the √2
squarer + the rational soft clip as a table + an 8 Hz DC block) would keep
its harmonic signature without the bloom.
