# REPITCH

Status (16 Sep 2026): third implementation, **working on the user's MKII**
(image OCTABAM81: pitch and length follow the tempo, no stretch). Released
to the user as **Octapitch v1.0** (`Octapitch_v1.0.bin` / `.syx`, version
string `OCTAPITCH`): the same MAIN OS as image 81, only the container's
version field differs. Image 80
(the second) drew the panel right but pitched the sample while keeping its
tempo, and sounded time-stretched: the voice renderer still moved the
sample at the old speed (`docs/remixer/FAILURE_MODES.md`). The first showed
a blank TSTR value. Markers as in `CHIP.md`: ✅ measured, 🟡 inferred.

**MKI: the same image, untested there.** The MKI and MKII run one OS: the
1.40C download we build from is the shared file (zip SHA256 `370c55a3…`,
`FLASHING.md`), and its MAIN OS (SHA256 `164f3122…`) is the one octalab
reads and runs on an MKI through this remixer's loader
(`vendor/refs/octalab-notes`). What differs between the models is the
panel: two keymap tables (`0x400bfbf6`, `0x400c01f4`) and which keys exist.
REPITCH binds no key; its controls are the SRC SETUP page and the audio
editor's ATTR page, reached the same way on both. 🟡 So nothing in it is
model-specific; falsified by any difference on an MKI.

## What it does

A track on REPITCH follows the project tempo by playback speed, without
grains: `speed = project_BPM / sample_BPM`, like a turntable (Ableton's
Re-Pitch). A 120 BPM loop at 120 BPM plays untouched; at 90 BPM it plays at
0.75, a fourth lower and 4/3 as long; the change follows the tempo live.
Pitch and length move together. Nothing is time-stretched.

- **Where it is chosen.** SRC SETUP `TSTR` on STATIC and FLEX shows it as
  `RPCH` (a fifth value). The sample's own `TIMESTRETCH` attribute (audio
  editor, ATTR) shows it as `REPITCH` (after BEAT) and applies when SETUP
  TSTR is `AUTO`, exactly as stock's NORMAL/BEAT do.
- **To the renderer it is OFF.** The voice renderer resolves REPITCH to 0
  and plays dry, forwards and in reverse; only the increment (and so both
  the pitch and the rate the sample is consumed at) carries the tempo.
- **PTCH is off.** The PTCH word is not applied (LFO and note transposition
  included) and the PTCH knob on the SRC page draws empty. RATE still
  applies (tape stops keep working).
- **Limits.** The speed is clamped to 2x, stock's own ceiling (PTCH +60).
  A sample without a tempo in the firmware's range (30..300 BPM, BPMx24
  720..7200) plays as stock. PICKUP is not offered REPITCH: its descriptor is
  untouched (a pickup buffer has no attributed tempo of its own, and stock
  forces pickups onto the grain path).
- **Storage.** The raw values below; both the part (SETUP) and project.work
  (`TSMODE=4`) store 4 verbatim (✅ the project parser at `0x40086c5a` does
  not clamp). A stock OS loading such a project sees an unknown value
  (🟡 SETUP: a blank value and granular playback; ATTR: `ERROR`).

| raw | SETUP (STATIC/FLEX) | ATTR TIMESTRETCH | stock |
|---:|---|---|---|
| 0 | OFF | OFF | yes |
| 1 | AUTO | -- | yes |
| 2 | NORM | NORMAL | yes |
| 3 | BEAT | BEAT | yes |
| 4 | RPCH | REPITCH | new |

## The ground (✅ measured from 1.40C unless marked)

**Page descriptors** (`PARAM_PAGES.md`): STATIC `P = 0x400d301c`, FLEX
`0x400d31ae`, PICKUP `0x400d3664`. TSTR is slot 10: count `P+0x9a+40`,
formatter `P+0xca+40` (`0x4003b6a4`), widget `P+0xfa+40` (`0x40046c28`).
PTCH is slot 0 with the knob `0x400479b4`.

**Widgets.** The select family (`0x40046f10` 2, `0x40046d9c` 3, `0x40046c28`
4, `0x40046ab4` 5 positions) share one body and differ in a `cmp #N-1`
bound and a 17x7 icon table (`0x400be2f2`, `0x400be2fa`, `0x400be306`,
`0x400be316`); a value past the bound returns having drawn nothing. The
five-position one is referenced by nothing in stock. The label is
`sprintf`ed into an 8-byte stack buffer (`sp+40`, the return address at
`sp+48`) and centred at the cell's x+9. The knob `0x400479b4` draws only
its frame for a negative value (`0x40047a0e`).

**The PLAYBACK SETUP window** is screen record `0x400bb7c8` (open
`0x400584d0`, draw `0x4003c830`); its editor is `0x4003a474(slot, delta)`.

**TSTR resolution** (`0x40007d7c`, in the voice renderer): SETUP TSTR from
the per-track record `0x80000510 + 48·t` byte 28; `AUTO` (1) takes the bound
sample's `TSMODE` (settings `+0x110`); a PICKUP (voice `+20` = 4) with 0
gets 2; a loop region under 6,144 frames gets 0. The result is voice
`+24` (voices `0x800049d8 + 168·t`, bound settings pointer at `+8`, machine
at `+20`). (The `TIMESTRETCH_PIPELINE.md` notes of 31 Jul call voice `+0x18`
a channel count; it is this resolved TSTR. Their addresses are 0x400 low:
they assumed the image loads at `0x40000000`.)

**The voice renderer** (`0x40007960`, called once per track and chunk by the
increment builder at `0x400041c4` with the chunk's output samples `d3` and
the source frames the DSP will consume `d7 = increment x d3`) reads the
resolved TSTR at nine sites (✅ scanned, `repitch_probe`), each as
zero/nonzero or against BEAT (3); what each does is read in objdump, the
position advance measured under the port:

| site | nonzero does |
|---|---|
| `0x40007ede` | sets the 64-bit position ratio from project tempo / sample tempo (dry: 1/1) |
| `0x40008210`, `0x400089de` (reverse) | takes the sample's tempo and its reciprocal (`+0x116`, `+0x118`) in place of the playing rate; they differ, so the chunk is read in pieces (🟡 the grain splice) |
| `0x400081b2`, `0x4000898a` (reverse) | sets voice `+3` when project tempo x rate exceeds twice the sample's (🟡 a stretch beyond 2x) |
| `0x4000886c`, `0x40008e42` (reverse) | **advances the sample position by the chunk's OUTPUT samples** through that ratio, where OFF advances it by the frames consumed (`d7`) |
| `0x400082a8`, `0x4000847e` | only for 3 (🟡 BEAT's transient handling) |

So the renderer's position moves at project / sample tempo for every
nonzero TSTR, whatever the increment. The project tempo it reads is
`fp-80`, from `0x80001824` (latched from `0x80001818` every frame,
`0x4000caa6`) scaled by voice `+38`.

**The playback increment** (Q26, `0x04000000` = 1.0) is built per track by
`0x40004008` (the table `0x400d6434` serves STATIC, FLEX and PICKUP), stored
at state `+36` (states `0x80004898 + 40·t`) and shared by the ColdFire
source supplier and the DSP voice command. The per-frame loop calls each
builder twice and the second call passes the recompute flag `0x10`
(`0x4000d518`), so the increment follows its inputs every frame. Inputs:
PTCH word at record `+0` (`0x4000` neutral, 0.2 semitone per raw step, one
octave per table half: +60 = 2.0, -60 = 0.5), RATE word at `+6` (applied
below `0x7f00` when the RATE mode byte `+27` is 0). The project tempo the
builder reads is `0x8000181c`, latched every frame from `0x80001814`
(`0x4000ca9a`), which both UI tempo setters write (`0x4009c7c4`,
`0x4009c708`).

**The audio editor ATTR page** draws with `0x4006e450`; TIMESTRETCH (row 2)
prints `OFF`/`NORMAL`/`BEAT` for 0/2/3 and `ERROR` otherwise
(`0x4006e6ec..0x4006e722`). Its value keys step `0 -> 2 -> 3` up
(`0x4006ee42`) and `3 -> 2 -> 0` down (`0x4006ef76`). A sample loaded
without a `.ot` gets NORMAL and a tempo from its length, or the project
tempo if it is short (`0x40095ee0`); the ATTR tempo editors clamp to
720..7200 (`0x40098ec0..`).

## The patch (`modules/repitch/`)

| site | what |
|---|---|
| `0x4000406a` `rate_gate` | resolves REPITCH for the track the builder is on (SETUP 4, or AUTO and TSMODE 4, not a PICKUP, with a tempo in range) and parks the sample's BPMx24 in d3 (free from the builder's entry to `0x40004176`) |
| `0x4000409e` `pitch_gate` | the PTCH word is replaced by neutral `0x4000` when d3 is set |
| `0x40004100` `rate_hook` | the finished increment x project / sample, exact (quotient and remainder), clamped to `0x08000000` |
| `0x40007d96` `tstr_resolve` | the renderer resolves REPITCH to 0: every site above takes OFF's path, forwards and backwards (stock's next line still makes a PICKUP's 0 a 2) |
| `0x4006e71c`, `0x4006ee56`, `0x4006ef7c` | ATTR TIMESTRETCH: `REPITCH`, BEAT -> REPITCH, REPITCH -> BEAT |
| STATIC/FLEX slot 10 | count 4 -> 5, formatter `tstr_fmt` (`RPCH`), widget -> `0x40046ab4` |
| STATIC/FLEX slot 0 | widget -> `ptch_widget`: the knob with value -1 on a REPITCH track (UI track `0x80000000`) |

## Tests

- `python3 tools/verify/verify_repitch.py [REMIX]` (in `make verify`): the
  hook contracts, the page drawings, and with `OT_PROJECT` the playback
  cases.
- `out/emu/ot_repitch_stock_test [--patched IMAGE]`
  (`tools/harness/repitch_probe.cpp`, also under CTest): the stock facts
  above (the nine renderer readers among them), and on the built image
  every hook through the firmware's own code. The resolution runs from
  `0x40007d96` to `0x40007dc0` on both images for TSTR 0..5, STATIC, FLEX
  and PICKUP and three previous values: the patched image with REPITCH
  equals stock given OFF, register for register. The increment check runs
  the builder from `0x4000406a` to `0x40004108` on both images for 9,000
  combinations (two tracks, FLEX and PICKUP, TSTR 0..4, TSMODE 0/2/4,
  sample tempos in and out of range, project tempos 30..300 BPM, three PTCH
  and two RATE values): 8,520 are bit-identical to stock and 480 equal
  stock's neutral-PTCH increment x project / sample, clamped.
- `.venv/bin/python3 tools/verify/verify_repitch_ui.py`: PLAYBACK SETUP
  draws `OFF AUTO NORM BEAT RPCH` on the five-position icons for STATIC and
  FLEX; the PLAYBACK page drops exactly the PTCH dial for SETUP REPITCH and
  for AUTO with a REPITCH sample, and keeps it otherwise; the audio
  editor's ATTR page (`0x4006e450`) prints TIMESTRETCH 0/2/3/4/5 as `OFF
  NORMAL BEAT REPITCH ERROR`.
- `python3 tools/verify/verify_repitch_reference.py`: the offline
  variable-speed reference (not firmware).

Playback under the port (`verify_repitch.py --project`, a generated 440 Hz
loop attributed 120 BPM, a live change to 90 BPM at frame 2000; ✅ 16 Sep
2026): the pitch from zero crossings, the SPEED from every write to T1's
sample position (voice `+68`), in frames per output sample.

| case | pitch Hz | speed | resolved | image 80 |
|---|---|---|---|---|
| stock-off (FLEX, OFF) | 440.05 -> 440.00 | +1.0007 -> +1.0004 | 0 | same |
| stretch (FLEX, NORM: the control) | 440.03 -> 440.01 | +1.0007 -> +0.7503 | 2 | same |
| repitch (FLEX, RPCH) | 440.01 -> 331.16 | +1.0007 -> +0.7503 | 0 | speed -> +1.0004, resolved 4 |
| auto (FLEX, AUTO + sample REPITCH) | 440.01 -> 331.27 | +1.0007 -> +0.7503 | 0 | speed -> +1.0004 |
| ptch (FLEX, RPCH, PTCH +24) | 440.03 -> 330.04 | +1.0007 -> +0.7503 | 0 | speed -> +1.0004 |
| static (STATIC, RPCH) | 440.01 -> 330.09 | +1.0007 -> +0.7503 | 0 | speed -> +1.0004 |
| reverse (FLEX, RPCH, RATE full reverse) | 440.04 -> 330.12 | -1.0007 -> -0.7503 | 0 | speed -> -1.0004 |

The stretch control is what makes the speed column mean something: a real
timestretch keeps the pitch and slows the position, REPITCH moves both, and
image 80 moved the pitch alone. The pitch readings sit up to 1.3 Hz off 330
where the port's block-boundary steps land on a zero crossing (a ramp loop
shows those steps at unity speed on OFF too); the speed does not see them.

What none of this sees: the LCD's pixels (the page tests capture text and
bitmap calls) and hardware timing.

## Retracted

- "STATIC/FLEX grow to five values, PICKUP from three to four" (first
  implementation): PICKUP is no longer touched.
- "The patched test executes all five formatter values": true, and it could
  not see the blank value, which is the widget's (`FAILURE_MODES.md`).
- "Full Flex playback at three tempos" validated the tempo each run loaded
  with, not a change while playing, and not the SETUP editor; both are
  covered now.
- "FLEX and STATIC on REPITCH measure 440 Hz before and 330 Hz after" (image
  80) as evidence that REPITCH played: the pitch was right and the sample
  position still advanced at 1.0, which the unit played as a timestretch.
  "After the change the tone shows the port's block-boundary glitches and
  level dips; a stock run pitched down by PTCH shows the same": the dips
  after the change were REPITCH skipping a quarter of every chunk. The
  port's own block-boundary steps are real (a ramp loop shows them at unity
  speed on OFF), which is what made the attribution look safe.
- "`0x40007ede` and `0x40008210` select the dry or grain path": they are two
  of nine sites that read the resolved TSTR.
