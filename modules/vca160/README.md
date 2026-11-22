# `vca160` — VCA160

A per-track insert modelled on the dbx 160 compressor/limiter (1976), built
from its schematic and its manual, with an id of its own and a side-chain KEY
from any track over a light bus (a four-word record per track). It takes no
stock effect's id; its code runs in a given-up effect's words (PLATE REV in
`remixes/test/vca160`).

Author: MaMarko (Marko Brajković, [braikomarko-hub](https://github.com/braikomarko-hub)): the idea, the listening and the tests on the unit.
**The code was written by Claude (Anthropic)**: engine, calibration, integration and gates.

**The name.** VCA160 says what it is: a VCA compressor after the 160. Until
it was contributed here it was called **VCA160** in the author's own images
(aCiDtRacK, from October 2026), and DBX 160 before that (up to ACIDV73MP).
The rename changes names only: the module directory, the key (`DB666` →
`VCA160`), the chooser's names (`dB666` → `VCA160`, `d666` → `V160`) and the
files; the assembled DSP words are the same.

dbx is a trademark of Harman, and OverEasy is dbx's name for the 160A's soft
knee. This module is not affiliated with or endorsed by dbx or Harman; the
names below only say which unit it is modelled on. No text, artwork or logo
of the original is reproduced: the README describes the circuit in its own
words, and the model takes specifications, part values and laws only
(`THIRD_PARTY.md`).

The 160's character is its detector: dbx's true-RMS module (RMS 208, M2 on
the schematic; David Blackmer's log-domain RMS, US 3,681,618, one of the
patents printed on the schematic). Attack and release are not knobs on a 160:
they are that detector's single time constant. The manual gives the release
as 125 dB/s, which fixes it at τ = 10·log₁₀(e)/125 = 34.7 ms, and the same τ,
unchanged, gives attack times near the manual's ("Measured"). THRESHOLD and COMPRESSION act in
dB on the detector's output and drive a VCA (dbx 200, M1) with the
difference: a hard knee, ratio 1/(1 − k) for a fraction k of the dB over
threshold.

## FX id

`0x1b` preferred (a free id: `schema.FREE_FX2_IDS`), no `replaces`, so no
stock effect is taken and a remix may move it (`registry.assign_ids`).
BBD and DISTORX prefer `0x1b` too. Where several modules prefer one id,
`assign_ids` gives it to the first **by key** and moves the rest to the
lowest free id, and a Part stores the id: a project saved on one image opens
its VCA160 slots on whatever the next image puts on that id.

The rename moves the key past DISTORX's in that order. In the author's
images, dB666 (`DB666` < `DISTORX`) kept `0x1b` and DISTORX took `0x06`;
with the key `VCA160` and no pin, DISTORX would take `0x1b` and VCA160
`0x06`, and every saved project would swap the two effects. A remix that
must keep the old ids pins them: `ids={"VCA160": 0x1b, "DISTORX": 0x06}`
(`Remix.ids`). Up to image ACIDV81 (28 Oct 2026) the author's remix ran it
on EQUALIZER's `0x0c` (`replaces="EQUALIZER"`).

BRAIN files an effect's stored defaults and templates under its store id,
`octabam.<module directory>` (`tools/remix/brain.py` `fx_store_id`), so the
rename moves them from `octabam.vca160` to `octabam.vca160`: records saved
under the old name are kept on the card and not applied (BRAIN.md 7.7
rule 1), and a project saved with the old name reports the id as MOVED in
BRAIN's ABOUT, PROJECT tab. The page layout hash (the keys and counts of the
twelve slots) is unchanged.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | THRS | 0–127, default 96 | THRESHOLD: −50 dBFS (0) … 0 dBFS (127), RMS — the 160's 10 mV … 3 V span (49.5 dB), its top at full scale |
| 1 | 1 | RATI | 0–127, default 50 | COMPRESSION: k = 0.992 × RATI/100 up to 100 (0 = 1:1, 50 = 2:1, 75 = 4:1, 100 = 120:1, the 160's "infinity"); 101…127 carry on to k = 2 (127 = −1:1, the 160A's negative compression: louder in, quieter out) |
| 1 | 2 | OUT | bipolar, default 64 | OUTPUT GAIN (R80): −20 … +20 dB |
| 1 | 3 | KEY | OFF, T1…T8 | the detector's source: OFF = this track (the 160's own input), T1…T8 = that track's level from the bus (the 160's detector input jack) |
| 1 | 4 | MIX | 0–127, default 127 | dry/wet: 127 is the 160 alone, 0 an exact passthrough |
| 2 | 6 | KNEE | HARD / OVER | HARD = the 160; OVER = a 10 dB-wide soft knee after the 160A's (the width is assumed: the 160A's curves are not published) |

Stereo-linked like two 160s strapped for "true RMS power summing": one
detector on (L² + R²)/2, one gain on both channels.

## The side-chain bus

A `DspHook` at the stock dispatcher's FX1 entry — the site SIDECHAIN_COMPRESSOR
hooks (`sctap`), proven on an MKI — runs `dbt_tap` for every track, every
block, with the track's 16 frames at X:$00–$1F. Each track has a record of
four words at its core's half of the shared window:

| tracks | records (BEAT COUNT LAST LEVEL each) | LEVEL words |
|---|---|---|
| T1–T4 | payload B (core 1), Y:$3FFF0–$3FFFF | $3FFF3, $3FFF7, $3FFFB, $3FFFF |
| T5–T8 | payload A (core 0), Y:$37FF0–$37FFF | $37FF3, $37FF7, $37FFB, $37FFF |

**The tap sums a track's block only while someone listens** (29 Oct 2026,
the author's rule: what nobody hears is not computed). Every word has one
kind of writer, so the two cores cannot undo each other:

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
change more often. (A first form of 29 Oct, one WANT word refilled by the
effect and counted down by the tap, could lose the refill when the two
cores' writes crossed: found by an independent review before it ran.)

A VCA160 on either core reads the one LEVEL word its KEY names, once per
block; one 24-bit store is atomic, and a word is at most one block old.
The tap uses a, b, r0, r1, x0 — inside the set stock reloads after this site
— and replays the displaced `move x:>$208,r6` after its address arithmetic,
where it fills the AGU gap. The sum is one `mac` with its parallel load per
sample word (32 a block). It leaves r0 at $21 awake, or in the shared window
asleep; no stock setup routine reads r0 before writing it (all 13 checked).

Cost, counted from the listing at about one cycle a word, four for a taken
branch, three for `jsr` and `rts`, not measured: asleep about 33 cycles per
track per block, awake about 77. Per core, for its four tracks, cycles a
sample:

| what the tracks do | before 29 Oct | now |
|---|---|---|
| nobody keys any track | ~23 | **~8** |
| one track keyed (a kick pumping a bass) | ~23 | **~11** |
| all four keyed | ~23 | ~19 |

About 0.75 % of a core before and 0.27 % now when nobody keys (against
≈3,120 usable cycles a sample, CHIP.md). It is paid by every image that
carries VCA160, and `cycle_count` does not price it (it is reached from the
dispatcher, not from the effect). The effect's side adds a heartbeat and a
branch per block, about one cycle a sample per instance.

SIDECHAIN_COMPRESSOR's tap copies the track's audio
instead, to offer audio-rate keys and a key listen, which the 160's RMS
detector does not need. The records sit at +$3FF0 of T8's and T4's FX2
slots, above every stock effect's measured extent (DARK REV's +$3DA2), in
Y:0x37F00..0x3FFFF, which payload B's boot zero loop clears. Until 26 Oct 2026
the (then single) words sat at Y:$33FF8 / $3BFF8 (the last $202 words of each half, measured by
SIDECHAIN_COMPRESSOR as never written by stock code); the demand loader's
window code (DLCOPY from 0x33DC3) now stops payload A's boot zero loop below
them, so they moved.

The ledger refuses VCA160 beside SIDECHAIN_COMPRESSOR and beside KEYBUS (the
same hook site, and a declared `conflicts` for each), so it cannot join
`octabam`, which carries SIDECHAIN_COMPRESSOR, and beside DELAY SERVER, whose line covers payload B's
words from 0x38000 up, the records at $3FFF0–$3FFFF included (so no bus remix).
No `window` placement is declared; the build checks window homes against
`Claims.dsp_ranges`.

## Measured

✅ `tools/verify/verify_vca160.py` in `dsp_host`, the code as the build
places it, 29 Oct 2026, as `verify_db666` in the author's fork (the same DSP
words; the LEVEL words planted with `-pokey`; the tap is run on its own,
below):

- **Bit-exact** against `vca160_ref.fixed()`: defaults, every knob at its
  ends, the OVER knee, KEY from T1 (payload B's half) and T7 (payload A's), KEY
  out of range, a split block, LFO-dirty page words.
- **The manual**: attack to 63 % of the reduction 15.8 / 6.7 / 2.8 ms for
  10 / 20 / 30 dB over threshold at infinity:1 (the manual: 15 / 5 / 3 ms);
  release 123 dB/s (125).
- **Ratios** on a tone 10 dB over threshold: 2:1 → +5.04 dB, 4:1 → +2.56,
  120:1 → +0.08, −1:1 → −10.00.
- **KEY**: a −6 dBFS word on T1 ducks a −30 dBFS tone by −18.63 dB, the float
  law's figure exactly; an empty word does nothing.
- Below threshold at OUT 0 dB, and at MIX 0, the output is the input exactly;
  silence comes out as zeros.
- **Cost** (measured again 22 Nov 2026 in this tree): 338 words of code on
  each payload (the tap's 45 included; `dsp_asm` at P:$800,
  `tools/build/dsp_forms.py` `assemble_words` with the payload's `subst`) +
  66 words of table; 160 cycles a sample by `REMIX=test/vca160 python3
  tools/build/cycle_count.py` (a static floor), plus the tap (above). For
  comparison, stock COMPRESSOR: 103.1 cycles a sample in the cycle model
  (`docs/contributing/CYCLE_SCAN.md`, a different instrument) and 2.18 % of a
  core on a unit (`docs/contributing/COSTS.md`). Worst core: 8 instances
  (FX1 and FX2 on its four tracks) = 1,280 static, about 1,800 with the
  ~1.4 that COSTS.md measured between static counts and the unit
  (inferred), against about 3,120 usable cycles a sample (CHIP.md). The
  code has no branch on a knob, so its cost does not depend on the
  settings (no `max_per_core`).
- **Instruction forms** (`verify_vca160`, after `verify_distorx`): 105 used,
  88 with a stock site. Of the 17 without one, 14 (Tcc forms,
  `mac x0,x0,a`, the P table reads) ran on the owner's MKI in every
  acidtrack image; `beq` and `bra` have stock sites (the report's normaliser
  does not match stock's labels); **`mac x0,x0,a x:(rN)+,x0`, the tap's
  sum, has none**: it runs whenever a KEY names a track, so it ran in the
  author's use above (T1 keyed; by ear, not a recorded test of that form). The bus stores use stock's
  forms (`(rN)+`, `(rN)-`).
- **The tap and the handshake** (`verify_vca160`, dbt_tap run as the proc in
  dsp_host with the block at X:$00, 29 Oct 2026): asleep it writes LEVEL 0
  and leaves COUNT and LAST alone; a new beat sets LAST and COUNT = 8 and
  LEVEL = `vca160_ref.tap()` of the block, bit for bit; the same beat counts
  down and keeps summing (LEVEL again bit-exact after 9 blocks); the tenth
  sleeps; a beat that changes while counting refills. The effect: KEY T1
  steps T1's BEAT once a block; KEY OFF writes no BEAT (sentinels kept).
  Not run: the two cores together (dsp_host runs one); the single-writer
  layout is the argument for that.

## How it differs from COMPRESSOR, SIDECHAIN_COMPRESSOR and KEYBUS

CONTRIBUTING.md asks a module that overlaps an accepted one to say what
differs. Stock COMPRESSOR, and SIDECHAIN_COMPRESSOR on top of it, is a
compressor with ATTACK and RELEASE knobs; VCA160 models one particular unit
whose character is that it has neither.

| | COMPRESSOR / SIDECHAIN_COMPRESSOR | VCA160 |
|---|---|---|
| method | stock's compressor (a detector with ATTACK and RELEASE knobs, RMS on page 2) | the 160's true-RMS detector: one time constant, 34.7 ms, from the manual's 125 dB/s; attack and release follow the program (measured above: 15.8 / 6.7 / 2.8 ms at 10 / 20 / 30 dB over) |
| ratio | stock's range (not measured here) | 1:1 … 120:1 (the 160's "infinity") and on to −1:1 (the 160A's negative compression) |
| knee | stock's (not measured here) | HARD (the 160) or OVER (a soft knee after the 160A's) |
| parallel | MIX | MIX (0 is an exact passthrough, `verify_vca160`) |
| key | SIDECHAIN_COMPRESSOR: T1–T8 as audio, a base-width key filter (KBAS, KWID), key gain, a key listen (MON) | T1–T8 as a level: one mean-square word per track per block over a bus, computed only while a VCA160 keys that track (about 8 cycles a sample per core asleep, 11 with one key; counted, not measured); no filter, no listen (the 160's detector takes a level, not audio) |
| knobs | 6 on page 1 + RMS and 5 key controls on page 2 | 5 on page 1 (THRS RATI OUT KEY MIX) + KNEE |
| in one image | — | not with SIDECHAIN_COMPRESSOR (the same dispatcher hook, `conflicts`); beside stock COMPRESSOR, yes |
| cost on a unit | COMPRESSOR 2.18 % a slot (COSTS.md); SIDECHAIN_COMPRESSOR not read | not read yet (see "Open") |

What was measured is VCA160's side (the 160's attack and release law, the
ratios, the key); the difference in sound is by ear, on the owner's unit.

In short: COMPRESSOR is the tool to shape a transient by hand; VCA160 is
a "set threshold and ratio and play" compressor with a sound of its own,
and a pump from the kick in two knobs (KEY, THRS).

**KEYBUS** (`modules/keybus`) publishes every track's block peak of
|(L + R) / 2| at X:$37F60 + track, from the same dispatcher site, for
CHARACTER's KEY and VOID. VCA160's tap was written before KEYBUS reached
this tree and publishes another quantity: the block's mean square, the input
the 160's RMS detector needs, and only while a VCA160 keys that track.
Reading KEYBUS's peak instead would change the sound (a peak is not a mean
square), so VCA160 keeps its own tap and declares the conflict. One key bus
for both (KEYBUS publishing a mean square as well, or a shared stub like
SC KEYBUS BRIDGE) would let VCA160 sit beside CHARACTER's KEY; that is a
design choice for the maintainers, not part of this module.

## On the unit

All on the author's MKI, by ear, under the earlier name dB666:

- **Remix `acidtrack`, on EQUALIZER's id**, from 11 Oct 2026 (first flash)
  to image ACIDV81 (28 Oct 2026): the side-chain ducking heard clearly from
  the first flash (KEY on the kick), then hours of live use, with the bus at
  today's +$3FF8 words in ACIDV79 (27 Oct) and ACIDV81. `make check
  REMIX=acidtrack` (the tap inside the real dispatcher, under the ColdFire
  port) passed on the author's tree. That form had no AGU nops, no BEAT
  handshake and no one-cycle sum.
- **This form, on its own id `0x1b`**: the DSP source is byte-identical to
  the one this module is added with (unchanged in the author's fork since
  29 Oct 2026). It is in his acidtrack images, among them ACIDF07B (on the
  unit from 18 Nov 2026) and ACIDF08 (from 19 Nov), as DISTORX's evidence
  records. The author's report of 22 Nov 2026: in use practically since it
  was written, usually on T5 and T6 with KEY on T1 (the kicks), also on the
  master and on single tracks; no clicks, noise or hangs. T5 and T6 are on
  core 0 and T1 on core 1, so that use reads T1's record across the cores,
  in payload B's half of the shared window (the bus table above).
- Not measured on a unit: the ducking against the model's attack and
  release, the slot cost and the tap's (`test/vca160-meter` is the image
  for that). `test/vca160` itself has not run on a unit.

## Open

- Its slot cost on a unit (LOAD METER, defaults and `dear`), and the tap's.
- A recording of the ducking on the unit, against the model's attack and
  release.
- Instruction forms without a stock site (`verify_vca160` lists them).
- The soft knee's real width; the 160A's own curves are not published.

## Gates

`tools/verify/verify_vca160.py`: generated source, bit-exact on eight
settings (the bus planted with `-pokey`), the passthroughs, the manual's
attack and release, the ratios, the key, silence, every knob.

## Files

| file | what |
|---|---|
| `manifest.py` | the module, the hook, the bus words, every constant |
| `vca160.tmpl.asm` | the DSP code with `@NAME@` constants (`@ROFF@` per payload: the half's first record less four words for each track before it) |
| `generate_asm.py` | writes `vca160.asm`; `--check` |
| `vca160_ref.py` | the 160 in float (`VCA160`) and the module bit for bit (`fixed`, `tap`) |

## Sources

- dbx 160/161 manual and schematic (dbx Inc., c. 1976): the controls, the
  specifications (attack, ratio 1:1–120:1, threshold 10 mV–3 V), Figs. 4–5.
- dbx 160A cut sheet (Harman): release 125 dB/s, −1:1, OverEasy.
- D. E. Blackmer, US 3,681,618, printed on the schematic: the RMS
  detector.
- Zac-Kyoti, SIDECHAIN_COMPRESSOR (MIT): the dispatcher hook site and the
  shared-window region, measured on an MKI.
