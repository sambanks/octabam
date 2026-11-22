# Review follow-up, 29 September 2026

Rebased from the reviewed `2fbc9981` onto `2a7082bc` before validation.
The PR is intended for review and merging; the earlier draft wording was stale.

## Fixture independence

The previous UI gate fails with `sample pool opened` after changing its input
fixture to THRU and moving the selected track/bank. The selection had never
landed. Both gates now prepare their own project copy: machine types, routing,
main/cue levels, mute/solo masks, scene mute state, AMP/LFO settings, transport
and trig masks are explicit. The input project is never modified. The panel
gate starts with ordinary FLEX and must select Analog BD through panel events.
It checks the signature before reporting a browser failure. LEFT from the engine
pool returns to the stock machine chooser on ANALOG BD; RIGHT opens the engine
pool again. Both sides use the stock header chevrons. The panel gate also
visits FLEX through the same horizontal navigation.

The reviewer's exact silent-main fixture was unavailable. The adversarial
fixture did not reproduce that original failure, so its cause is not claimed
as located. The new gate reads the actual stereo MAIN pair (ESAI channels 2/3),
after transport starts, instead of accepting any nonzero byte in the complete
capture. Both MAIN channels and T1/T5 post-FX output pass on the prepared copy.

## DSP forms and retired synthesis

The 808's repeated shift is now stock `asl #$10,a,a`; its accumulator loop
uses stock `do a`. The desk harness uses `do n7` directly. Exact-render output
and block-state hashes pass all eight cases (1,835,008 frames). No reference
hash was updated. Combined engine/glue size is 992 words.

The unused ColdFire oscillator/noise/filter implementation, tables and its
800-sample comparison tests are removed. ColdFire retains descriptor defaults,
LPF labels and control transport. All eight tracks now send DSP records; the
native gate exercises both ping buffers and every sample-offset split.

## Loader buffers

`platform_build.preboot_layout` records each actual pre-boot destination and
packed staging extent in `layout.json`, normalizes cached/uncached aliases,
and rejects overlap with the linked runtime, packed runtime, other pre-boot
buffers, or the arena boundary. Five unit tests cover these refusals and the
unchanged no-preboot case. The 24 refhash configurations are bit-identical to
the rebased upstream baseline; all 35 other remix images are identical.

## Source signature audit

The stock source renderer table at `0x400d6434` dispatches STATIC, FLEX and
PICKUP to `0x40004008`, THRU to `0x40004424`, NEIGHBOR to `0x4000466c`, and
the inactive source to `0x400047f0`. All source records begin with four
32-bit header fields; arbitrary audio follows them.

The decisive second signature half is DSP word 2: the **high half of the
ring-start field**, not sample data. FLEX's producer writes its modulo-64
ring position at `0x4000411e`; THRU uses its bounded ring position, and
NEIGHBOR/inactive write zero. Consequently this word cannot be `0x0909`
for a valid stock record. FLEX's first field also packs segment lengths
(`0x40004246`/`0x40004252`), so the old claim that its high half is always
zero was too strong and has been removed. This audit concerns valid stock
source records, not already-corrupted transport memory or future modules
that deliberately adopt a conflicting record format.

## Stock project load and emulator claim

A disposable AB project loaded under pristine 1.40C with DSP enabled. Stock
kept FLEX and `AB\x01`, but clamped the setup values to stock FLEX ranges
(ACCNT/LPF/LOW/HIGH: 1/1/1/3 in the fixture). This is not lossless backward
compatibility; keep a separate project copy for firmware without the module.

On macOS, stock boot and a complete project load/panel script also passed
with the opcode-cache bounds guard removed and out-of-range writes logged.
None occurred. The old crash claim is retracted and the unrelated emulator
change removed. No failing platform/configuration has been reproduced.

## Initial review validation (before the level follow-up)

The final engine browser uses the same header chevrons as STATIC/FLEX.
The native ABI gate checks the chooser's stock and Analog BD title branches;
the panel gate checks LEFT to the machine column, FLEX/AB horizontal
navigation, YES selection, NO cancellation, and the reopened model highlight.
Octemu and the final panel gate used identical MAIN OS bytes, SHA256
`3ea2f9a2b86a6dd5796abd8aaca292a8324c09effa418ee346ca7adc7c89e414`.

- `make check-shared` over the ten-remix cover: 13 module gates passed.
- `OT_PROJECT=<standard fixture> make check-remix REMIX=analog-bassdrum`:
  passed on the final browser build, including real MAIN output and all four
  image module gates. The separate adversarial-fixture AB panel/audio gates
  also pass. Using the deliberately silent THRU fixture for the general
  `verify_set` instead fails its T1 chain-audio assertion in bank 4; it is not
  suitable as an unmodified general audio fixture.
- `make accept` over the same cover: one passed, four failed, five blocked.
  Analog BD's functional/cycle checks pass; its generic pressure stages are
  blocked because that FX pricer does not price source engines. CF METER,
  EUCLID and MINIVERB lack pressure profiles. Tape Echo's assembly comparison
  is blocked by the author's unrecorded GCC version.
- `usb-io-main-ab` and `usb-io-main-cue-abcd` fail USB counter-overrun checks;
  `bottleservice` misses the expected USB MIDI event; `mods` reports zero
  measured pitch in all seven REPITCH cases despite correct speed/increment
  resolution. Those remix images are byte-identical to upstream. These are
  recorded failures, not evidence of a green repository-wide acceptance run.

The full reach plan finished with five of six top-level gates passing; only
its aggregate acceptance command failed. No hardware qualification is inferred
from these local runs.

## Browser-only selection and default levels

The gain figures in this section describe the 29 September revision.
On 30 September both source outputs were raised by 12.04 dB; see README.md
and CPU.md for current levels and the exact output/state checks.

The follow-up removes the page-2 MODEL control (label, enable bit and value
widget). Its former encoder is intercepted before stock's parameter write;
merely hiding the knob would still let that writer overwrite the engine id.
The id remains in the same stored byte, and only the engine browser edits it.
Other controls keep their existing positions and saved values.

Actual defaults previously gave 808/909 first-500-ms RMS levels of
−18.88/−32.25 dBFS. A fixed 0.215 post-desk trim brings the 808 to −32.23 dBFS;
the first-100-ms RMS differs by 0.24 dB. This affects existing 808 patches too.
The 909 output is unchanged. The trim follows the original 24-bit limiter,
so the drive, EQ and envelope states remain exact. The original golden hashes
are retained: a verified untrimmed render supplies the exact integer-scaled
reference for every shipping 808 sample. All eight reference/state cases pass.

The rendered PLAYBACK SETUP page was also inspected: the former MODEL
position is blank, and ACCNT, LPF, LOW and HIGH retain their positions.
The capture used the current image hash recorded in CPU.md.

## Validation after the level follow-up

Rebased onto upstream `98edd284c92e493c538889ee7e745198c9c5f58c` before
running the reach plan, using the standard project fixture for both
`OT_PROJECT` and `STRESS_SOURCE`.

- `make emu-cf`: passed.
- `python3 tools/verify/verify_docs.py`: 44 modules / 36 remixes, passed.
- `make test-acceptance`: 90 tests passed.
- `scripts/refhash.sh check`: all 24 configurations/reports identical to a
  fresh baseline on that upstream revision.
- `python3 tools/verify/image_identity.py --base upstream/main`: all 35
  other remix images identical; only Analog BD changed.
- `make check-shared` for the ten-remix reach cover: all 14 gates passed,
  including original audio/state hashes, exact shipping 808 trim and actual
  default-level comparison.
- Analog BD's `make check-remix` and cycle checks passed, including all four
  image module gates, real MAIN audio and the full panel event script.
  The UI image hash matches the current CPU.md benchmark image exactly.
- Four current-image full-chain cases passed: eight 808s and alternating
  808/909s with both slots occupied by DJ EQ, on each core; CPU.md records
  the measured peaks and limits.

The aggregate ten-remix acceptance result is **3 passed, 2 failed, 5 blocked**:
Bottleservice, USB MAIN AB and USB MAIN/CUE ABCD passed. USB TRACKS AB failed
its counter-overrun assertion (39 overruns); MODS/REPITCH reported zero pitch
in its playback cases despite correct speed/increment resolution. Both failed
remix images are byte-identical to upstream. Analog BD's functional and cycle
checks passed, but its generic pressure stages are blocked because the FX
pricer does not support source engines; the dedicated full-chain measurements
above cover the stated layouts. CF METER, EUCLID and MINIVERB lack pressure
profiles. Tape Echo's assembly comparison remains blocked by its author's
unrecorded GCC version. This is not a green repository-wide acceptance run.

The reach plan completed five of six top-level gates successfully; its
aggregate acceptance command returned exit 2.

## Output gain and current validation, 30 September 2026

Both source outputs now have +12.04 dB gain relative to the preceding
revision. The 808 balancing coefficient is 0.86 and the 909 has an exact
integer ×4 stage after its original limited desk sample. Neither changes
internal state. Default peaks are −7.31/−1.59 dBFS (808/909); 500 ms RMS
is −20.19/−20.21 dBFS. The 909's output stores limit overloads at full scale.
Current standalone and complete eight-track costs are recorded in CPU.md.

The branch was rebased onto octabam main `3c9c8d0d66` before running:

| Command | Result |
|---|---|
| `make emu-cf` | Passed with this worktree's fresh port build |
| `python3 tools/verify/verify_docs.py` | Passed: 45 modules / 35 remixes |
| `make test-acceptance` | Passed: 105 tests |
| `scripts/refhash.sh check` | Passed: all 24 configurations/reports identical to a baseline saved from pristine current main |
| `make check-shared REMIXES="analog-bassdrum octatrick"` | Passed, including original hashes, exact scaled output/state and nominal levels |
| `python3 tools/verify/check_shards.py --jobs 2 analog-bassdrum octatrick` | Analog BD passed every per-remix/image gate; octatrick failed its USB-input assertion with 13 underruns, 0 overruns, 0 reprimes |
| `python3 tools/verify/image_identity.py --base upstream/main --remixes octatrick --reports` | Passed: image and build report identical |
| `python3 tools/harness/benchmark_analog_bd.py` with the two cases and arguments recorded in CPU.md | Passed: both 900-frame eight-track runs delivered controls and stereo audio on every track |

The required QUICK reach command was `OT_PROJECT=<fixture> make reach
BASE=upstream/main RUN=1 KEEP=1 JOBS=2`. Four of its five top-level gates
passed; the sharded check returned nonzero for octatrick. The exact image
used by its failed USB check was additionally compared against a pristine
main build with the same BUILD=79 flags: both SHA256 values are
`862df46eccb178477fabb4561cc0da05613b782989346a2b2a40e639a6f27a4d`.
The PR does not change that failing image. The aggregate reach run is not
reported as green. The prior strict-pressure and hardware limits remain.
