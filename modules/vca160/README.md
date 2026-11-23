# `vca160` — VCA160

A per-track compressor modelled on the dbx 160 compressor/limiter (1976),
built from its schematic and its manual. Set a threshold and a ratio and
play: attack and release follow the music, as on the 160. KEY takes the
detector from any track, so a kick on one track can duck a bass on another
in two knobs. It has an id of its own and takes no stock effect's id; its
code runs in a given-up effect's words (PLATE REV in `remixes/test/vca160`).
KEY reads [KEYBUS](../keybus/README.md), which every remix with VCA160
carries.

Author: MaMarko (Marko Brajković, [braikomarko-hub](https://github.com/braikomarko-hub)): the idea, the listening and the tests on the unit.
**The code was written by Claude (Anthropic)**: engine, calibration, integration and gates.

**The name.** VCA160 says what it is: a VCA compressor after the 160. It was
called **dB666** in the author's own images (aCiDtRacK) before it came to
this repository. Its BRAIN store id keeps that name (below).

dbx is a trademark of Harman, and OverEasy is dbx's name for the 160A's soft
knee. This module is not affiliated with or endorsed by dbx or Harman; the
names below only say which unit it is modelled on. No text, artwork or logo
of the original is reproduced: the README describes the circuit in its own
words, and the model takes specifications, part values and laws only
(`THIRD_PARTY.md`).

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | THRS | 0–127, default 96 | THRESHOLD: −50 dBFS (0) … 0 dBFS (127), RMS — the 160's 10 mV … 3 V span (49.5 dB), its top at full scale |
| 1 | 1 | RATI | 0–127, default 50 | COMPRESSION: k = 0.992 × RATI/100 up to 100 (0 = 1:1, 50 = 2:1, 75 = 4:1, 100 = 120:1, the 160's "infinity"); 101…127 carry on to k = 2 (127 = −1:1, the 160A's negative compression: louder in, quieter out) |
| 1 | 2 | OUT | bipolar, default 64 | OUTPUT GAIN (R80): −20 … +20 dB |
| 1 | 3 | KEY | OFF, T1…T8 | the detector's source: OFF = this track (the 160's own input), T1…T8 = that track's block mean square from KEYBUS (the 160's detector input jack) |
| 1 | 4 | MIX | 0–127, default 127 | dry/wet: 127 is the 160 alone, 0 an exact passthrough |
| 2 | 6 | KNEE | HARD / OVER | HARD = the 160; OVER = a 10 dB-wide soft knee after the 160A's |

Stereo-linked like two 160s strapped for "true RMS power summing": one
detector on (L² + R²)/2, one gain on both channels.

## How it works

The 160's character is its detector: dbx's true-RMS module (RMS 208, M2 on
the schematic; David Blackmer's log-domain RMS, US 3,681,618, one of the
patents printed on the schematic). Attack and release are not knobs on a 160:
they are that detector's single time constant. The manual gives the release
as 125 dB/s, which fixes it at τ = 10·log₁₀(e)/125 = 34.7 ms. The same τ
gives attack times near the manual's: 63 % of the reduction in about 16, 7
and 3 ms at 10, 20 and 30 dB over the threshold (the manual: 15, 5 and 3 ms).
THRESHOLD and COMPRESSION act in dB on the detector's output and drive a VCA
(dbx 200, M1) with the difference: ratio 1/(1 − k) for a fraction k of the
dB over the threshold. A tone 10 dB over comes out 5.0 dB over at 2:1,
2.6 dB at 4:1, 0.1 dB at 120:1 and 10 dB under at −1:1.

## The key

KEY T1…T8 reads [KEYBUS](../keybus/README.md)'s mean-square word for that
track, X:$37F68 + track, once a block. KEYBUS's hook at the stock
dispatcher's per-track site rewrites all eight every block with the mean of
(L² + R²) / 2 over the track's 16 input frames, the input the 160's RMS
detector needs. The words are in the shared window, so a VCA160 on T5 can
key from T1. A word is at most one block old, and one 24-bit store is
atomic, so a reader never sees half a word.

VCA160 itself has no hook and writes nothing outside its own state, so it
sits beside SIDECHAIN_COMPRESSOR, CHARACTER's KEY and the bus servers.

## Cost

66 words of table. The sample loop is 159
cycles a sample by `cycle_count.py`'s static count; eight instances on one
core (FX1 and FX2 on its four tracks) are 1,272, under the 3,120 the build
budgets for modules. The code has no branch on a knob, so its cost does not
depend on the settings. The key's mean square is KEYBUS's cost, paid by
every image with KEYBUS (its README).

## In a remix

- **FX id.** `0x1b` is preferred (a free id: `schema.FREE_FX2_IDS`), with no
  `replaces`, so a remix may move it (`registry.assign_ids`). BBD and DISTORX
  prefer `0x1b` too. Where several modules prefer one id, `assign_ids` gives
  it to the first by key and moves the rest to the lowest free id, and a Part
  stores the id. A remix that must keep the ids its projects were saved with
  pins them with `Remix.ids`: a remix carrying DISTORX whose projects had
  dB666 on `0x1b` and DISTORX on `0x06` sets
  `ids={"VCA160": 0x1b, "DISTORX": 0x06}`.
- **BRAIN.** The manifest declares `store=Store("octabam.db666")`, the store
  id it had as dB666, so the defaults and templates saved under that name
  keep applying (`tools/remix/brain.py` `fx_store_id`; `brain.lock` records
  it). The page layout hash is the same as dB666's.
- **KEYBUS.** VCA160 `requires` KEYBUS, so a remix that selects VCA160
  selects KEYBUS too.

## How it differs from COMPRESSOR and SIDECHAIN_COMPRESSOR

Stock COMPRESSOR, and SIDECHAIN_COMPRESSOR on top of it, is a compressor
with ATTACK and RELEASE knobs; VCA160 models one particular unit whose
character is that it has neither.

| | COMPRESSOR / SIDECHAIN_COMPRESSOR | VCA160 |
|---|---|---|
| method | stock's compressor (a detector with ATTACK and RELEASE knobs, RMS on page 2) | the 160's true-RMS detector: one time constant, 34.7 ms; attack and release follow the programme |
| ratio | stock's range | 1:1 … 120:1 (the 160's "infinity") and on to −1:1 (the 160A's negative compression) |
| knee | stock's | HARD (the 160) or OVER (a soft knee after the 160A's) |
| parallel | MIX | MIX (0 is an exact passthrough) |
| key | SIDECHAIN_COMPRESSOR: T1–T8 as audio, a base-width key filter (KBAS, KWID), key gain, a key listen (MON) | T1–T8 as a level: KEYBUS's mean-square word per track a block; no filter, no listen (the 160's detector takes a level, not audio) |
| knobs | 6 on page 1 + RMS and 5 key controls on page 2 | 5 on page 1 (THRS RATI OUT KEY MIX) + KNEE |

In short: COMPRESSOR is the tool to shape a transient by hand; VCA160 is
a "set threshold and ratio and play" compressor with a sound of its own,
and a pump from the kick in two knobs (KEY, THRS).

## Gate

`tools/verify/verify_vca160.py`: the generated source; the module against
`vca160_ref.fixed()` bit for bit (every knob at its ends, the OVER knee, KEY
from planted KEYBUS words, every KEY T1–T8 on eight words that all differ,
KEY out of range, a split block, LFO-dirty page words, two stereo renders
with L ≠ R); the passthroughs; the manual's attack and release; the ratios;
the key; silence; and the instruction forms with no stock site.
`tools/verify/verify_keybus.py` checks that KEYBUS's tap writes each track's
mean-square word bit for bit against `vca160_ref.tap()`.

## Limits

- The soft knee's width (10 dB) is a choice: the 160A's own curves are not
  published.

## Files

| file | what |
|---|---|
| `manifest.py` | the module and every constant |
| `vca160.tmpl.asm` | the DSP code with `@NAME@` constants |
| `generate_asm.py` | writes `vca160.asm`; `--check` |
| `vca160_ref.py` | the 160 in float (`VCA160`), the module bit for bit (`fixed`) and KEYBUS's mean-square word (`tap`) |
| `brain.lock` | the BRAIN store id and layout, as `brain.py lock` writes it |

## Sources

- dbx 160/161 manual and schematic (dbx Inc., c. 1976): the controls, the
  specifications (attack, ratio 1:1–120:1, threshold 10 mV–3 V), Figs. 4–5.
- dbx 160A cut sheet (Harman): release 125 dB/s, −1:1, OverEasy.
- D. E. Blackmer, US 3,681,618, printed on the schematic: the RMS
  detector.
