# `vca160` — VCA160

A per-track compressor modelled on the dbx 160 compressor/limiter (1976),
built from its schematic and its manual. Set a threshold and a ratio and
play: attack and release follow the music, as on the 160. KEY takes the
detector from any track, so a kick on one track can duck a bass on another
in two knobs. It has an id of its own and takes no stock effect's id; its
code runs in a given-up effect's words (PLATE REV in `remixes/test/vca160`).

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
| 1 | 3 | KEY | OFF, T1…T8 | the detector's source: OFF = this track (the 160's own input), T1…T8 = that track's level from the bus (the 160's detector input jack) |
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

## The side-chain bus

A `DspHook` at the stock dispatcher's per-track site (SIDECHAIN_COMPRESSOR's
`sctap` site) runs `dbt_tap` for every track, every block, with the track's
16 frames at X:$00–$1F. Each track has a record of four words in its core's
half of the shared window:

| tracks | records (BEAT COUNT LAST LEVEL each) | LEVEL words |
|---|---|---|
| T1–T4 | payload B (core 1), Y:$3FFF0–$3FFFF | $3FFF3, $3FFF7, $3FFFB, $3FFFF |
| T5–T8 | payload A (core 0), Y:$37FF0–$37FFF | $37FF3, $37FF7, $37FFB, $37FFF |

Both cores read the whole window, so a VCA160 on T5 can key from T1.

**The tap sums a track's block only while a VCA160 keys it.** Every word has
one kind of writer, so the two cores cannot undo each other:

| word | written by | what |
|---|---|---|
| BEAT | each VCA160 whose KEY names the track (OFF branches over the store) | its own heartbeat, +1 a block |
| COUNT, LAST | that track's tap only | the BEAT it saw last; blocks left awake |
| LEVEL | that track's tap only | the block's mean square, or 0 asleep |

The tap reads BEAT: changed since LAST → LAST = BEAT, COUNT = 8, sum; the
same → COUNT − 1 and sum while COUNT was above 0; else LEVEL = 0 and return.
A KEY turned on reads 0 for its first one or two blocks (0.36–0.73 ms,
against the detector's 34.7 ms: not heard); a KEY turned off keeps the tap
running 8 more blocks after the last beat it saw, plus up to one by the two
cores' order (about 3 ms). Two VCA160 keying one track only make BEAT
change more often.

A VCA160 on either core reads the one LEVEL word its KEY names, once a
block; one 24-bit store is atomic, and a word is at most one block old.
The tap uses a, b, r0, r1, x0 — inside the set stock reloads after this site
— and replays the displaced `move x:>$208,r6` after its address arithmetic,
where it fills the AGU gap. The sum is one `mac` with its parallel load per
sample word (32 a block). It leaves r0 at $21 awake, or in the shared window
asleep; no stock setup routine reads r0 before writing it.

The records sit at +$3FF0 of T8's and T4's FX2 slots, above every stock
effect's extent (DARK REV's +$3DA2), in Y:0x37F00..0x3FFFF, which payload B's
boot zero loop clears.

## Cost

326 words of code on each payload (the tap's 43 included) and 66 of table.
The sample loop is 159 cycles a sample by `cycle_count.py`'s static count;
eight instances on one core (FX1 and FX2 on its four tracks) are 1,272,
under the 3,120 the build budgets for modules. The code has no branch on a
knob, so its cost does not depend on the settings.

The tap is paid by every image that carries VCA160, and `cycle_count.py`
does not price it (it is reached from the dispatcher, not from the effect).
Counted from the listing: about 8 cycles a sample a core when no track is
keyed, about 11 with one keyed track, about 19 with all four. The effect's
side adds a heartbeat and a branch a block, about one cycle a sample per
instance.

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
- **Not beside SIDECHAIN_COMPRESSOR or KEYBUS.** Both hook the same
  dispatcher site; the ledger refuses the pair and the manifest declares the
  `conflicts`. So VCA160 cannot join `octabam` or `octabam-verbs`, which
  carry both. It cannot sit beside DELAY SERVER either: its line covers
  payload B's words from 0x38000 up, the records at $3FFF0–$3FFFF included.
- No `window` placement is declared; the build checks window homes against
  `Claims.dsp_ranges`.

## How it differs from COMPRESSOR, SIDECHAIN_COMPRESSOR and KEYBUS

Stock COMPRESSOR, and SIDECHAIN_COMPRESSOR on top of it, is a compressor
with ATTACK and RELEASE knobs; VCA160 models one particular unit whose
character is that it has neither.

| | COMPRESSOR / SIDECHAIN_COMPRESSOR | VCA160 |
|---|---|---|
| method | stock's compressor (a detector with ATTACK and RELEASE knobs, RMS on page 2) | the 160's true-RMS detector: one time constant, 34.7 ms; attack and release follow the programme |
| ratio | stock's range | 1:1 … 120:1 (the 160's "infinity") and on to −1:1 (the 160A's negative compression) |
| knee | stock's | HARD (the 160) or OVER (a soft knee after the 160A's) |
| parallel | MIX | MIX (0 is an exact passthrough) |
| key | SIDECHAIN_COMPRESSOR: T1–T8 as audio, a base-width key filter (KBAS, KWID), key gain, a key listen (MON) | T1–T8 as a level: one mean-square word per track a block over a bus, computed only while a VCA160 keys that track; no filter, no listen (the 160's detector takes a level, not audio) |
| knobs | 6 on page 1 + RMS and 5 key controls on page 2 | 5 on page 1 (THRS RATI OUT KEY MIX) + KNEE |
| in one image | — | not with SIDECHAIN_COMPRESSOR or KEYBUS; beside stock COMPRESSOR, yes |

In short: COMPRESSOR is the tool to shape a transient by hand; VCA160 is
a "set threshold and ratio and play" compressor with a sound of its own,
and a pump from the kick in two knobs (KEY, THRS).

**KEYBUS** (`modules/keybus`) publishes every track's block peak of
|(L + R) / 2| at X:$37F60 + track, from the same dispatcher site, for
CHARACTER's KEY and VOID. VCA160's tap publishes another quantity: the
block's mean square, the input the 160's RMS detector needs, and only while a
VCA160 keys that track. Reading KEYBUS's peak instead would change the
sound (a peak is not a mean square). One key bus for both (KEYBUS publishing
a mean square as well, or a shared stub like SC KEYBUS BRIDGE) would let
VCA160 sit beside CHARACTER's KEY.

## Gate

`tools/verify/verify_vca160.py`: the generated source; the module against
`vca160_ref.fixed()` bit for bit (every knob at its ends, the OVER knee, KEY
from either half, every KEY T1–T8 on a bus whose eight words all differ, KEY
out of range, a split block, LFO-dirty page words, two stereo renders with
L ≠ R); the passthroughs; the manual's attack and release; the ratios; the
key; silence; the tap and its BEAT/COUNT/LAST handshake against
`vca160_ref.tap()`; and the instruction forms with no stock site.

## Limits

- The soft knee's width (10 dB) is a choice: the 160A's own curves are not
  published.
- The tap's `mac x0,x0,a x:(rN)+,x0` has no stock site (the gate lists it).
- The two cores' writes to the bus are kept apart by having one kind of
  writer per word; the gate runs one core at a time.

## Files

| file | what |
|---|---|
| `manifest.py` | the module, the hook, the bus words, every constant |
| `vca160.tmpl.asm` | the DSP code with `@NAME@` constants (`@ROFF@` per payload: the half's first record less four words for each track before it) |
| `generate_asm.py` | writes `vca160.asm`; `--check` |
| `vca160_ref.py` | the 160 in float (`VCA160`) and the module bit for bit (`fixed`, `tap`) |
| `brain.lock` | the BRAIN store id and layout, as `brain.py lock` writes it |

## Sources

- dbx 160/161 manual and schematic (dbx Inc., c. 1976): the controls, the
  specifications (attack, ratio 1:1–120:1, threshold 10 mV–3 V), Figs. 4–5.
- dbx 160A cut sheet (Harman): release 125 dB/s, −1:1, OverEasy.
- D. E. Blackmer, US 3,681,618, printed on the schematic: the RMS
  detector.
- Zac-Kyoti, SIDECHAIN_COMPRESSOR (MIT): the dispatcher hook site and the
  shared-window region.
