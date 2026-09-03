# The plan: end state, resource ledger, and work order

**This is the cold-start document — read it before `docs/XBUS.md`**, which is
the *architecture* record rather than the plan. The full development log —
every dated decision, retraction and ear-pass this file used to carry — lives
in git history (`git log --follow -- PLAN.md`); this file states where the
project stands and what is genuinely open.

---

## Where the project stands

**Feature-complete and hardware-confirmed.** Both effects, the cross-core
bus, and every parameter on both pages of both effects are live, lawful and
audible on the unit.

What ships:

- **ChonVerb** — an eight-line FDN reverb (ROOM/PLATE/BIG), shimmer, a gated
  mode, mid/side width, and a MOD speed select. Hosted on a track **5–8**
  (payload A / core 0); any track can send into it. `docs/REVERB.md`.
- **BongDelay** — a multi-mode delay: CLEAN, GRAIN (a pitched granular
  cloud, v5: Nimbus's readers, four per line, ±2 octaves on RATE; the
  harmoniser since PITCH mode was retired 3 Sep 2026), REVERSE — with tape-style
  wow/flutter modulation (DPTH/RATE), drive (DRV, doubling as GRAIN's
  scatter depth) and a FREEZE hold available in **every** mode. (MODE still
  counts five positions; the former TAPE slot aliases CLEAN now that the
  tape character is global.) Hosted on a track **1–4** (payload B / core 1);
  any track can send into it. Its wet can be sent on into the reverb over
  the bus (`-VRB`, p4, default 0) — the delay→reverb series topology the
  stock hardware has no path for.
- **The send bus** — any track can select SEND and drive `→DELAY` /
  `→REVERB` (two separate knobs — driving the wrong one renders silence).
  Auto-gain divides by registered client count, so eight senders drive a
  server as hard as one.
- **Both effects are RETURNS with a unity dry passthrough** (v5, 23 Aug
  2026): a server track outputs its own dry untouched plus the wet, fed by
  the other tracks' sends; its audio reaches the *engine* only through `IN`
  (default 0 — an exact passthrough). v4's wet-only output, which muted any
  audio on the host track, is retired: Sam hit it in the field and called it.

- **Tempo sync (R56, 24 Aug 2026, ON THE UNIT, confirmed)** — two ColdFire *code*
  caves (the project's first): one publishes the project tempo into two
  dead parameter words of any track hosting one of our servers; the other
  is BongDelay TIME's display formatter. **TIME is a free dial with a
  sticky snap**: near a division (1/32T … 1/4) it snaps, holds that
  division through tempo changes, lets go when the knob moves; the panel
  prints "1/8" while held, ms otherwise. Plus a per-block TIME slew for the
  crackle. R53 proved cave + DSP on hardware; R54 the divisions; R55/R56
  slew, snap and labels confirmed on the unit the same evening; levels may want tuning. Lessons in `docs/DSP.md` §6c
  (never init-build tables in Y through `(r1)+` — R48–R50 killed every
  voice). `docs/PARAM_PAGES.md` §7 decodes the formatter ABI.

**Hosting is bank-bound; serving is not.** Either effect serves all eight
tracks over the bus, but each can only be *hosted* on its own core's bank —
and picking one on the wrong bank runs a SEND instead (the absent server's
id is deliberately aliased to SEND on that payload). The track↔core mapping
is **measured, and inverted from what you'd guess**: payload A runs the high
tracks. Host the reverb on track 5, the delay on tracks 1–4.

---

## How the repo is organised: modules and remixes

**A module is one contribution; a remix is a named selection of them.**
`modules/<name>/manifest.py` declares what a module is — its menu entry, its
twelve parameter slots, its DSP source, its ColdFire caves — and
`remixes/<name>.py` selects a set. `remixes/chongbong.py` is the shipping
image and the reference every refactor proves itself against.

```sh
make remix                # the remixer: compose a selection interactively
make modules              # the module index and the available remixes
make bus REMIX=<name>     # build a selection (default: chongbong)
```

What ships today is four modules: `chonverb`, `bongdelay`, `send`, and
`tempo-sync` — the last being a ColdFire patch rather than an effect, and the
worked example of changing what the firmware *does*.

**What a remix does to the STOCK effects (made explicit 2 Sep 2026).** Every
image replaces the FX2 chooser wholesale, but only three stock effects are
*consumed* — PLATE, SPRING and DARK REV, whose code is the donor region.
The other eleven (FILTER, EQ, DJ EQ, PHASER, FLANGER, CHORUS, SPATIALIZER,
COMB, COMPRESSOR, LO-FI, the Echo Freeze DELAY) keep their code, descriptor
and dispatch in every image and had merely lost their chooser row. A remix
now keeps any of them by listing it by key (`tools/remix/stock.py`), in
chooser order, at zero cost — the build writes the row and the cursor
position and nothing else — and the composer shows a STOCK FX2 group, the
consumed three, and the hidden count. `remixes/restored.py` is chongbong
plus the seven that can sit beside the servers; the other four allocate a
per-track instance buffer on the addresses the servers hardcode and the
ledger refuses them beside one. Past seven rows the list relocates and the
panel scrolls — ⚠️ inferred from stock's fifteen-row list, unflashed.
`docs/MODULES.md` "Keeping STOCK effects in the chooser". Later the same
day the rig learned to **render them**: knobs read from the stock
descriptors, audio from a dump of the pristine image through `dsp_host`.
Ten of eleven render, each a bit-exact dry pass at neutral settings;
DELAY cannot (ColdFire-side). FLANGER looked broken until eight
instruction probes cleared the emulator and the cause turned out to be the
harness: hardware puts the audio block at X:0 and stock effects scratch
right above it, while `dsp_host` defaulted to X:0x80 — fixing that also
cleaned five other stock renders that had passed as "credible". LO-FI
needed the project's first patch to the vendored emulator
(`tools/dsp56300.patch`, MPYRI) and still passes at +6 dB at zero settings
(open, needs a hardware A/B). Worth knowing: stock code exercises both
instructions and conventions our own modules never did.

Making them first-class exposed a latent id collision: the DSP dispatch
tables are shared between FX1 and FX2, and Rungs (`0x0c`) and Nimbus
(`0x0d`) sat on EQUALIZER's and DJ EQ's ids from 29 Aug, so every local
image since ran Rungs where FX1 selected EQUALIZER, and chongbong aliased
FX1's EQ and DJ EQ to SEND. Never flashed (tag 77 predates it). Both moved
(`0x17`, `0x1a`); the schema refuses stock ids; the shipping image differs
from before in exactly those four ids' entries, byte-diffed.

The first **outsider modules** landed 29 Aug 2026 — three Mutable-
Instruments-flavoured per-track **inserts** (no bus role, placed in BOTH
payloads, run on any track, several at once — the class the servers cannot
be):

- `warpfold` — Warps-ish ring mod / wavefolder (322 words). MIX=0 bit-exact
  null, DRV=0 fold identity at −96 dB, ring sidebands on the predicted
  carrier to 0.3%.
- `ripple` — Ripples-ish driven SVF, LP/BP/HP, Q≈30 (347 words). LP slope
  −13.8 dB measured where 2-pole theory says −14.4; the all-knobs-at-127
  bomb decays clean.
- `rungs` — Rings-ish 8-mode modal resonator, STRING/BELL/GLASS partial
  tables + STRUCT stretch (880 words). Partials land within 0.15% of the
  series; DAMP spans T60 ~0.1–9 s (hyperbolic in the knob — a voicing item).

A fourth followed the same day — `nimbus`, a Clouds-ish granular texture
(500 words): four grains over a continuously-recorded 743 ms line, POS/SIZE/
DENS/MIX and a freeze. It gets its **own** remix because it owns the
per-core FX2 buffer region `Y:0x4000–0xBFFF`, so it cannot share a core with
ChonVerb's tank — a pair the ledger now refuses by name. Its window found a
new trap, now in `CLAUDE.md`: **reading `a0` exposes the fractional left
shift that reading `a1` hides**, so an `a0`-based integer scale is 2× the
multiplier; the wrong one assembled and made plausible granular noise while
running the window at double rate, and only a DC gate caught it. The musical
freeze renders locally via `NFRZAT=n`, the `DFRZAT`-shaped lever.

Two more followed, both zero-buffer inserts:

- `streamz` — Streams-ish **vactrol lowpass gate** (255 words): the envelope
  opens a filter and an amplifier together, so quiet is dark *and* quiet.
  LPG/VCF/VCA. Release measured 26–731 ms against a 20–700 ms design; the
  coupling itself measured as a spectral centroid of 9,880 Hz on loud
  material against 2,620 Hz on the same material quiet.
- `bodeshift` — Warps-ish **Bode frequency shifter** (391 words), UP/DOWN/
  WIDE plus feedback. Built against a float model *first*, which caught the
  sideband sign convention before a line of assembly was written. Measured on
  the DSP: wanted sideband at unity, suppression 41.5/29.6/18.7 dB at
  440 Hz/1 kHz/5 kHz (the model says 40.8/29.2/18.6), shift frequency exact
  to 0.00 Hz across the knob, and feedback stable at maximum with 0.95 FS in.

All five ship together in the `mutables` remix (2,410/2,724 words with SEND;
`warped` carries WarpFold alone). Built entirely against the manifest
contract; the build's three-source special-casing was generalized the same
day under the refhash gate (bit-identical before any module existed), and
`verify_menu` now derives its expectations from the selected remix instead of
a hand table. **None of the six is flashed** — every MODE select and knob
publish rides the standing on-unit reconfirm, and that is the only gate left.

Both tool gaps this paragraph used to list are now CLOSED: `make cycles` is
remix-aware (measured costs in the ledger below, and they were dearer than
the inspection estimates this paragraph once carried — Rungs 238 against a
guessed ~190), and `send_probe`'s layout alphabet is derived from the
manifests, so an insert renders with `--direct` rather than by hand.

Three things follow that are worth knowing before editing anything:

- **The build refuses to start when two selected modules collide** on an FX2
  id, a ColdFire cave, a hook site or a core-private Y word, and names both.
  `tools/remix/ledger.py`; the negative tests are in `make check`. As of
  29 Aug it also refuses two modules that both own the **per-core FX2
  instance buffer region** `Y:0x4000–0xBFFF` (ChonVerb's tank, Nimbus's
  line) — declared, not scanned, because a scan cannot tell an address from
  a mask. The shared 64K window is still **not** covered — its extents are
  not established well enough to write down, so `CLAUDE.md`'s ownership
  notes remain the map.
- **A module's `priority` is byte-load-bearing.** The donor region is packed
  in that order.
- **Refactors of the build prove themselves with `scripts/refhash.sh`** — 23
  configurations, artifacts *and* build reports, bit-identical. Save a
  baseline on a tree you trust before starting. Every commit of the remix
  work passed it, and it caught things reading the diff did not.

`docs/MODULES.md` is the contributor guide.

---

## The principle that decides everything: SYMMETRY

**FX2 bus servers are asymmetric. FX1 inserts cannot be.**

ChonVerb exists only on core 0; BongDelay only on core 1. That is what
specialization (`SPEC=1`) bought. But an FX1 insert must run on *any* of the
8 tracks, so it must exist in **both** payloads — and program space is per
core. Two consequences:

1. **Payload B's free words can only ever be spent on the delay.** No FX1
   redesign can reach them.
2. **FX1 work and delay work never touch the same pool**, so there is no
   resource reason to sequence one before the other.

---

## The resource ledger

### Program space — per core, 8,192 words; donor region 2,724 words/payload

The build report is the live ledger — `make bus` prints it. Current build
(29 Aug 2026): **payload A used 2,650, FREE 74; payload B used 2,694,
FREE 30 — and since BongDelay v5 (3 Sep 2026, PITCH mode retired, GRAIN pitched) B used 2,404, FREE 320 (v5.1: 2,154 words).** The older "A 55 / B 1" figures in this file predated the freeze
and roll work; both payloads are still effectively full, and new work needs
a lever first.

**Space levers, in order of preference:**

- **The reverb LFO-block roll is built and PARKED, not available.**
  `modules/chonverb/reverb_lforoll.asm` frees 51 words ✅ measured, but fails
  `verify_roll` on the TIME=127 SIZE=127 DIFF=127 wet case — the only one
  that drives the allpass hard. Bisected: the shared triangle stash is
  innocent, loop order is irrelevant, the table is right; the remaining
  suspect is the AP section's indexed writes, and it needs a state probe,
  not more reading.
- **OMR memory map** (`docs/CHIP.md` §3): Fig 3-3 doubles P, 8K → 16K,
  **+8,192 words**, costing `Y:0xA000–0xBFFF`. On core 0 it **evicts tank
  lines 6–7** (ChonVerb's eight lines are `Y:0x4000–0xBFFF` at 4K each), so
  core-0 OMR is reverb re-layout work, not a build flag. 🟡 OMR is per-core:
  core 1 alone can take Fig 3-3 with no tank cost — contingent on nothing
  else on that core using `Y:0xA000–0xBFFF`. ⚠️ No OMR risk can be de-risked
  locally: `dsp_host` has no 8K wall and no OMR model; each unknown is a
  flash.
- **Code in the shared window**: P/X/Y alias at `0x30000–0x3FFFF` ✅ and
  stock already runs code there ✅, so up to 64K is program-addressable. 🟡
- **FX1 consolidation** (work order §2) frees ~550–650 per payload as a side
  effect, but is its own project.

### Cycles — per core, 4,535/sample ✅ arithmetic (200 MIPS ÷ 44.1 kHz)

Cycles are not the current constraint. `make cycles` is **remix-aware since
29 Aug 2026** and prints a **WORST ONE CORE** figure derived from the
selection: four FX2 slots, at most one server (the design rule, and what
SPEC enforces), inserts unlimited because nothing stops all four tracks
choosing the same one. Measured this way:

| remix | worst core | what fills it |
|---|---|---|
| chongbong | **1,817** | 1× delay (v5, pitched GRAIN) + 3× send (was 2,432 with the v2 GRAIN delay) |
| mutables | **1,376** | 4× BodeShift (the dearest insert) |
| nimbus | **1,308** | 4× Nimbus |
| verbonly | **1,444** | 1× reverb + 3× send |

against ~3,125 usable after stock's own ~1,410. Per-module: reverb 1,384,
delay 1,757 (GRAIN v5, pitched, four per line, 3 Sep 2026; was 2,372 with the v2 GRAIN), Nimbus 327, BodeShift 344, Rungs 238,
Streamz 154, WarpFold 101, Ripple 93, send 20.

The old headline summed reverb + delay + sends onto one core — a load no
core ever pays. That composition is still printed, labelled as the legacy
basis, because the 7 Aug hardware spare was measured against it and
re-baselining the comparison would break the only hardware anchor there is.
⚠️ Every figure here is a static count: exact for the code, blind to
memory-contention stalls, and the wall is a **cliff**. Only the burn sweep
measures the real ceiling.

- ⚠️ **FX1 cycles are paid ×4 per core** — a 300-cycle FX1 effect costs
  1,200 cycles/core. *This*, not program space, is the ceiling on FX1
  ambition.
- ✅ **The flashable burn probe BUILDS — `make burn` places it** (payload A
  FREE 46, B FREE 9) with `p3` as the burn knob at 32 cycles/step. This
  paragraph claimed the opposite until 30 Aug 2026 and an entire work-order
  item was priced on it. What is blocked is only `verify_burn`'s **alias-probe
  diagnostic**, which needs the non-XBUS *plain* layout where the delay
  overruns — and that figure has rotted twice (2,794 → 2,734 → **2,766 today**,
  42 words over), so read it from `verify_burn`'s own NOTE rather than from
  any document.
- **Priced cycle lever**: GRAIN 4 grains → 2 returns ~300 cycles for ~100
  words, at the voicing cost of half the simultaneous voices.

### Y memory

| | |
|---|---|
| FX2 per server, pooled | **65,536 words = 1.49 s** (2 private slots + half the shared window) |
| FX1 slots | 3,072 each × 4 = **12,288 per core, allocated used or not** |

**FX1's 12,288 words are currently stranded** — only an FX1 effect can reach
them, and stock's inserts use a fraction. Owning FX1 turns that into real
capability: 70 ms lines per track — doublers, short slaps, wide chorus.

---

## Work order

### 1. Voicing polish — ear items, none blocking

- **"Clipping on both effects" (24 Aug 2026) — RESOLVED UPSTREAM, measured
  on the unit the same evening** via the EVO4 + MIDI CC rig
  (`tools/level_cap.py`, `tools/ot_midi.py`): the dry mix was flat-topping
  with every send at zero. Causes, in order: AMP VOL ≈ +12 dB on two
  source tracks + hot sample GAINs (pre-FX clip), then a master compressor
  flattening the sum at full scale. With gains at 0 dB / VOL 64 and the
  mix rebalanced (peak −17.6 dBFS), sends swept 0→127 on both effects and
  both at once: **no clipping at any step** (reverb +5.4 dB RMS at full
  send, delay +1.5, both −14.4 dBFS peak). BIG swept separately: clean at full send (−14.9 dBFS peak). The BIG knee (0.25–0.5 FS in)
  is unreachable from a sane mix (senders ≈ 0.13 FS); the old drums hit
  0.41 FS. Open ear item only: the delay return is ~4 dB quieter than the
  reverb at equal send. **Capture E closed the same evening**: three senders
  (two of them 10–15 dB quieter) at full send dropped the wet by 4.8 dB vs
  the loud sender alone — the 1/√N law to the dB (1/N predicts −9.5). Design
  property to know: a quiet sender turns the loud sender's reverb down.
- **R58 (tag 77, ON THE UNIT 24 Aug — hardware-ratified: lean 8.0 -> ~4.4 dB, wet +3.8 dB, no clipping): PING
  balance + delay return makeup** — wet x1.5 both channels, +0.75*PING*wet
  on R; lean 7.9 -> 4.4 dB at defaults, PING 0 untouched, no bus-level side
  effects. `docs/VOICING.md` R58. Hardware ear-ratify on next flash.
- **Full MIDI-driven hardware voice pass DONE (24 Aug 2026 evening,
  Sam's set, R57)** — see `docs/VOICING.md`. No clipping at any page-1
  setting or stacked extreme on either effect; modes span ~3.6 dB; pitch
  exact on real material; GRAIN scatter / wow / REVERSE / FREEZE all
  hardware-verified (freeze seamless by Sam's ear). Open: the **TONE CC-42
  publish quirk** (lands in the Part but reaches the DSP only while T3's
  FX2 page is on screen — docs/MIDI.md).
- **Per-mode gain structure.** The modes are 7–9 dB apart at the output
  (`docs/TESTPASS.md`: ROOM −23.0 / PLATE −24.9 / BIG −16.1 dBFS at
  defaults), and an input sweep (in this file's git history) put BIG across
  the clip knee at a 0.25–0.5 FS input while PLATE never reached it. The
  honest fix is per-mode headroom, set from measurement. Interim practice:
  back BIG off by hand.
- Reopeners from the reverb's "done for now" call, live only if a listening
  round asks: the pad's last forwardness, the 6–9 k crest, the TIME refit,
  a PLATE ear pass.
- GRAIN texture: the density gate only subtracts energy, so sparse always
  costs level (the reference manages loud AND sparse). Needs makeup gain on
  the surviving grains, which does not exist yet.

### 1b. DYNAMIC DONOR REGIONS — measured feasible, 3 Sep 2026

**Sam's framing, and it is the right one: if the goal is to mix and match all
effects freely, dropping any stock effect should give you its words.** Today
only three can be harvested — the donor region is exactly PLATE + SPRING +
DARK REV — and every other stock effect answers "what does this cost?" with a
number you cannot spend. That is a property of THIS BUILD, not of the
machine, and the difference had been showing up as UI copy nobody could make
read straight ("dropping it frees none").

**The two facts that make it possible are measured** (`tools/dsp_reach.py`
disassembly of payload A, against the module records and the spans in
`docs/DSP.md` §8):

- **The thirteen DSP effects are CONTIGUOUS**, `P:0x007d1..0x01fdf`, **6,158
  words**, with no other module between them:

  | | | | | |
  |---|---|---|---|---|
  | `007d1` FILTER 727 | `00aa8` SPATIALIZER 261 | `00bad` EQUALIZER 282 | `00cc7` PHASER 157+41 | `00d96` FLANGER 289 |
  | `00eb7` CHORUS 329 | `01000` PLATE 594 | `01252` SPRING 1063 | `01679` DARK 1067 | `01aa4` COMPRESSOR 180 |
  | `01b58` LO-FI 537 | `01d71` DJ EQ 345 | `01eca` COMB 277 | | |

  The current 2,724-word donor region is the middle third of that run.
- **Every one is SELF-CONTAINED.** No control flow leaves an effect's own
  span, and nothing enters one but its own dispatch entry. The single
  apparent exception is PLATE's `do #<$6,>$1267` — a loop END address, which
  is exclusive, so it is its own boundary rather than a jump into SPRING.
  (⚠️ PHASER is the known irregular one: its true extent runs 41 words past
  its record into four small blocks, `docs/DSP.md` §8. Its span is the true
  one above.)

**So the ceiling is 6,158 words against today's 2,724 — 2.26×** — and
anything between: drop CHORUS and the region grows *downward* from PLATE
because CHORUS is its neighbour.

**What it costs, and this is the new decision it forces.** Today an unlisted
stock effect keeps working — its code, descriptor and dispatch stay stock, so
an old project that selects it still runs it, and leaving it out costs only a
chooser row. A stock effect *harvested for its words* is gone: its dispatch
must go to the null stub, exactly as the donors' do. So a stock effect stops
having two states and gains three — **listed** / **unlisted but intact** /
**harvested** — and the remixer has to make that choice legible, because it
is the first one in this tool that actually takes something away.

**The work, in order:** ✅ containment sweep on payload B — **all twelve
self-contained there too**, and B carries the same thirteen effects at
different bases (`P:0x00591..0x01d9f`, the same 6,158 words); ✅ per-effect
spans in `stock.p_spans()`, *derived* from the module map by record-size
fingerprint rather than written down, so a firmware whose layout differs
raises instead of being written over; ✅ `Remix.harvest`, defaulting to the
three reverbs; ✅ `build_bus.py` places into the harvested run; ✅ every
harvested effect the placer reached is nulled and the survivors keep their
algorithm, by SPAN rather than by a hand-written donor list; ✅ selftest
asserts contiguity in both payloads and that every shipped remix harvests a
run; ✅ **refhash 26/26 bit-identical**.

✅ **EVERY RUN IS PLACEABLE, not just the largest** (3 Sep 2026). The build
refused a non-contiguous harvest, so `stock.region_of` handed it the biggest
run alone and every other run was given up and then left empty — Sam, from
the budget map: *"when I remove the modulation it shows free space. But when
I remove some reverb it only shows the free reverb space."* Two adjacent
effects (EQ+PHASER, 489 words) simply vanished behind the reverbs' 2,724.
Now `stock.regions_of()` groups the harvest into runs and the placer
first-fits each module into a run it fits — assembling once per candidate,
since a module's origin is an argument. Proven: STREAMZ placed into
SPATIALIZER's isolated 261-word opening renders **bit-identical** to the
same module in a single 2,724-word run. `bothslots` goes 3,342 → 3,880
usable words. ⚠️ The residual cost of a gap is **fragmentation** — a module
is one code stream and must fit ONE run — so the budget names the largest
opening beside the total, the map draws a bracket per run instead of one
across the wall, and `consumed_at`'s single-stream arithmetic is gated to
the one-run case rather than left to be quietly wrong. ✅ refhash 26/26
bit-identical (the single-run report wording, failure text included, is
frozen for exactly this reason).

✅ **And the remixer composes it.** `h` harvests the highlighted stock
effect, `⌁` marks it, `consumed_at`/`region_words`/`placeable` all take the
selection's own harvest, and the Budget's `held by` row follows
(`Chorus, Plate, Spring, Dark — 3,053 words; drop Chorus for 329 more`). The
run is kept contiguous at the KEYSTROKE, naming what is in the way, and the
resource line offers `h harvests them` only on the two effects that could
legally join.

⬜ **Left, and it is the interesting half now:** nothing has been *flashed*,
and harvesting a non-reverb has never run on hardware. The measurement says
each effect is self-contained; what it cannot say is whether anything
outside the DSP — a ColdFire path, a descriptor, the allocator table — cares
that CHORUS's algorithm is gone. The cheapest real test is a card with
`harvest=("CHORUS", ...)` and CHORUS left off both choosers, listening for
anything but silence on its id.

⚠️ **One constraint found the hard way: the build report's donor names must
be ONE WORD.** `state.measure()` reads `KEPT STOCK: (\S+)` and splits on
`/`, so `PLATE REV/SPRING REV/DARK REV` truncates the whole list at the
first space. The report is API — refhash hashes it and three verifiers parse
it — so the first word is emitted, exactly as the old lowercase donor keys
produced.

### 2. FX1 consolidation — turning the stranded pool into capability

The trick ChonVerb already ran: replace near-duplicates with one engine plus
a MODE select.

| cluster | stock words | one engine | freed **per payload** |
|---|---|---|---|
| PHASER + FLANGER + CHORUS + COMB | **1,102** (PHASER's true extent is 207, past its 157-word record — `DSP.md`) | ~400–500 🟡 | **~550–650** |
| EQUALIZER + DJ EQ | **627** | ~300 🟡 | **~325** |

All four in row 1 are the same structure — a short modulated delay with
feedback. **FILTER is the outlier**: 727 words, the default FX1 effect, ~260
cycles. Highest value, highest risk. ✅ Taking the three reverbs cost FX1
nothing — they were never on its menu; FX1's ten effects are the whole pool.

✅ **FX1's chooser is COMPOSED since 3 Sep 2026** — `Remix.fx1` is FX1's row
list exactly as `modules` is FX2's: list, unlist, reorder, stock effects and
ours alike. The list is rebuilt in the cave with its three `lea` refs
repointed, the viewport literal at `0x40059be6` sized to it, and FX1's own
id and cursor tables written (`docs/MODULES.md`). It costs no words; the
bill is cycles, and `make cycles` prices FX1's four slots, so the trade is
visible before it is made. Emulator-verified, **unflashed**;
`remixes/bothslots.py` is the worked example. That is orthogonal to the
consolidation below, which is about freeing FX1's own words.

⚠️ Sequence FX1 ambition after the burn sweep (§3) — its real ceiling is
cycles ×4. Note the spare HAS been measured per core since 23 Aug 2026
(704 with the reverb + 4× FILTER, 1,088 with 2×, one FILTER = 192 —
`docs/CHIP.md` §2); the sweep is to re-measure it against whatever bank FX1
work would actually run in.

### 3. Flash the burn probe and sweep the ceiling

**Not blocked — `make burn` builds a flashable image today.** Flash it once
and sweep the real per-core cycle ceiling from the front panel with `p3`
(32 cycles/step). Everything in §2 prices off that number, so this is one
flash away rather than a hunt for words.

(The *only* thing needing words is `verify_burn`'s alias-probe diagnostic in
the plain layout, which is a local check, not the measurement.)

### 4. Piggyback on that flash: can the STOCK delay run downstream of our reverb?

Cheap experiment, no new engine, and it would buy a routing the hardware has
no path for. **Everything about it is hardware-only** — the mechanism is
entirely CPU-side, so no local test can say anything.

**What is settled.** The stock Echo Freeze Delay is applied *downstream of the
FX2 insert* (measured here by listening test) and lives on the ColdFire as DMA
over SDRAM rings at `0x4F502C10` (`docs/EXTERNAL.md`, Bryan T). So the signal
order for "our reverb into the stock delay" is already the right way round.
The reverse — stock delay into our bus — is **impossible and now known to be
so physically**: those rings are outside the DSP's 18-bit external address
range, so no DSP code can ever read them. Delay→reverb stays BongDelay's
`→VERB`.

**The crack — now ✅ MEASURED, 31 Aug 2026, by disassembling it here.** The
audio path does not read the FX2 id field at all (all 18 references to it are
UI/menu code). What the delay actually gates on, at `0x40003230`:

```
a2 = 0x80001b87 + 64*track                  ; 0x400031e0..e6
mvzb (a2),d0 ; moveq #8,d1 ; cmp ; bne      ; the gate
mvsb (fp),d0 ; moveq #7,d2 ; cmp ; bne      ; a SECOND condition, fp =
                                            ; 0x80000eb4 + 8*[0x800000e0]
```

So the gate byte is **offset +7 of a 64-byte per-track record based at
`0x80001b80`**, and that record is filled by the frame builder at
`0x4000d13c..46` in an eight-iteration per-track loop (`a3 += 64`), with
offsets 6–7 coming from a staging word at `0x80000128 + 512*bank +
64*track + 32`.

**The consequence, and it is what makes the experiment worth a flash: the gate
byte is a PER-FRAME COPY in shared RAM, not the FX2 id itself.** The DSP
dispatch reads the id from the instance table (`r6+$1c`); the CPU delay reads
this staged copy. They are different storage fed from the same source — so a
cave running between the builder's write and the delay's read can set one
without touching the other. That is precisely the decoupling step 2 was meant
to test, and it is now established statically rather than on the unit.

⚠️ The **second condition** (`0x80000eb4 + 8*bank == 7`) is unexplained;
`0x80000eb4` is machine-type storage in the timestretch work. It may gate
which TIME path runs rather than whether the delay runs at all — the two
branches lead to two different time derivations, not to a bypass. Read it
before assuming.

✅ **Closed one of Bryan's open threads while in there:** the writer of the
staged TIME word at `0x80005fa0` is this same routine, at `0x40003284..88`,
copying a word from the *other* per-track record at `0x80001a00 + 96*track`.

**The experiment.** If that byte is decoupled from the dispatch id, a ColdFire
cave — infrastructure we already fly — can set it for a track whose FX2 slot
is running ChonVerb, giving **reverb → stock delay in series on one track**.
Steps, cheapest first:

1. ✅ **DONE** — the gate, its record and its filler are decoded above.
2. Pick the hook window. It must be **after** the frame builder fills the
   record (`0x4000d146`) and **before** the delay routine reads it
   (`0x40003230`), on the same frame. Find a site in that window whose stock
   bytes can be replayed.
3. Write the cave: force record+7 to 8 for the chosen track. Flash, select
   ChonVerb on that track, and listen for repeats. The standing rule applies
   — assert the stock bytes, replay what you displace.

⚠️ **Before spending the flash, settle the second condition** (the `==7`
above) statically; if it turns out to gate the delay's existence rather than
its time source, step 3's cave needs to satisfy both.

**Known unknowns before spending a flash on step 3.** The delay's TIME comes
from a staged word at `0x80005fa0` whose writer is unmapped, so the delay may
run with no controllable time; and a track hosting ChonVerb has no free
parameter slot to put a delay control on. Treat a first result of "it makes
delayed sound at some arbitrary time" as success for the experiment and a
separate problem for the design.

### 5. The remixer and a local ColdFire emulator (decided 31 Aug 2026)

**The aim is an iterate-with-a-cycle loop for ColdFire/UI work** — the class
of change that today costs a flash per attempt. Two backlog items merge into
one tool, under one architectural rule: **the emulator is a headless library;
the TUI is a shell around it.**

```
┌─ remix ─────────────┐ ┌─ emulated OT ──────────┐
│ [x] chonverb        │ │  MAIN MENU             │
│ [x] bongdelay       │ │  > PROJECT             │
│ [x] tempo-sync      │ │    REVERB    ← new row │
│  build ▸ check ▸    │ │  (arrows/enter = keys) │
└─────────────────────┘ └────────────────────────┘
```

**Why it is tractable now** (all measured, 31 Aug 2026):

- Unicorn 2.1.4 exposes QEMU's `UC_CPU_M68K_CFV4E` model and **executes this
  CPU correctly** — `mvz`/`mvs` extended right, EMAC `macl`/`movclrl`
  produced the exact predicted product (32769 × −32767 = `0xC0000001`).
  The archaeology-era `emu_*.py` harnesses (recoverable,
  `git show 9e1c028^:tools/emu_image.py`) ran the default plain-68k core;
  the model flag removes their one real limitation.
- The memory map is already decoded (`docs/ARCHITECTURE.md` §7), the DSP
  MMIO handshake at `0x20000000` down to the ready bit and frame swap, and
  the unit officially boots to DEMO with no CF card — so the DSP and ATA
  can be stubbed on day one.
- The MAIN MENU table system is decoded (`docs/MAINMENU.md`), so the first
  customer — a dedicated REVERB/DELAY menu entry, the two-write patch of
  MAINMENU.md §5 — has a concrete test to run.

**Tiers, with the risk stated:**

1. **Tier 0 — headless boot to the main loop.** Map SDRAM/RAM windows, load
   the image, hook every unmapped access and log it; the stub list builds
   itself. ⚠️ The open risk is the RTOS tick: the vector table (`0x400`
   preamble) is an un-extracted open front and interrupt injection in
   Unicorn m68k is manual. Days if it cooperates, a swamp if not — and the
   fallback is the detour-style harness (emu_image.py shape, CFV4E model),
   which covers the menu patch without booting anything.
2. **Tier 1 — the text UI.** Do NOT emulate the LCD or key matrix. Read the
   screen by hooking the decoded draw path (window ctor `FUN_4005829c`,
   list drawer `FUN_40037590`, sprintf `0x40013a08`) into a windows+strings
   model; inject keys at the software layer (the `[PAGE]` keycode-`0x1b`
   precedent). Not pixel-faithful — menu-walking faithful.
3. **TUI shell** (upgrades the `make remix` composer): remix pane + build
   pane land first and are useful with no emulator; the emu pane plugs in
   when Tier 1 does. Schedules deliberately uncoupled.
4. **Audio stays out.** The voicing loop (render → afplay → ear) is already
   right and does not move into a pane. A dual-core `dsp_host` (two vendored
   56300 cores + the shared window — the only tool that could ever show a
   bus race locally) is acknowledged as the next bet after this, not part
   of it.

**The prize is not the interactive toy:** a headless
`boot / inject_key / read_screen` API means `verify_menu`-style checks can
*walk the patched firmware* under `make check` — an automated no-flash gate
for every ColdFire cave, present and future.

**Tier-0 bring-up is underway and de-risked** (`docs/EMU.md`,
`tools/emu_bringup.py`, 31 Aug 2026): with SP+SR seeded and MMIO modelled,
the real image executes **~7,000,000 instructions with zero decode faults**,
through all early hardware init, and stops exactly at the RTOS handoff
(`trap #0`, `0x40000e46`). The one load-bearing peripheral value is decoded
(the clock register must report a 264 MHz sysclk or the boot halts); async
completion-flag spins are auto-satisfied.

**Milestone 1 is shipped**: the emulator is a library (`boot()` +
`read_menu_tree()`), wired into the remixer — `make remix`, press
**`e`** to boot the *built* image, confirm it reaches the handoff with no
fault, and see the MAIN MENU walked from RAM with any patched-in entry
highlighted. That is the crow-flies no-flash gate: a cave that breaks early
init faults in the emulator, not on the unit. ~4 s per boot (native bursts).

**Milestone 2 is shipped too**: the **live screen**. `render_menu(r, cursor)`
calls the firmware's own menu draw against the warm machine and captures it as
`(x,y,text)` (the detour route — `ctl_flush_tb` + open + state/viewport pokes +
draw); `make remix` → `e` shows a framed LCD with up/down navigating the main
menu and the submenu preview following, as on the unit — on the *built* image,
so a patched-in entry renders as the firmware would draw it. Recipe and the
JIT-cache gotcha are in `docs/EMU.md`.

The **FX2 dials page** renders too (`e` → `f`): the EFFECT 2 SETUP window,
listing the built remix's own effects (`ChonVerb77`, `BongDelay77`, `Send`)
and the param row.

**Milestone 3 is shipped (31 Aug 2026): the track-centric remixer.** The
curses TUI is retired; `make remix` now runs `tools/remix/app.py` (Textual,
in the same `.venv` extra as unicorn), organized the way an Octatrack user
thinks. Home is a RIG of eight tracks: assign any effect the track can host
(servers by payload — A serves T5-8, B serves T1-4, now DECLARED in the two
server manifests; inserts anywhere), dial its manifest-named knobs on the
real page-1/page-2 layout, render and hear it, A/B renders. EVERY effect
renders locally (`tools/remix/audition.py`): ChonVerb via `render_reverb`,
BongDelay via a staleness-checked DEV hatch build, inserts via a per-insert
scratch image — and `send_probe --set NAME=VAL` now drives any knob of any
module through its own `knob_map()`. The 12 Aug SEND-alias trap is guarded
for every module (a `--pick` of an absent insert dies instead of rendering a
plausible dry passthrough). The composer groups modules by category with
track ranges, phrases its panel as the FX2 menu the unit will show, and
builds/checks the LIVE selection; the emu view caches its boot until the
image changes and follows the rig's selected track. Follow-ups landed the
same day: esc stops audio, Rich-markup escaping, per-knob docs + select
labels in the manifests with `?` help overlays, the audition journal
(`out/_audition/log.jsonl`), and the terminal-ANSI theme. The manual is
`docs/REMIXER.md`.

Remaining toward full fidelity: item-level menu descent and live dial *values*
(same detour shape — drive the real key handler `FUN_40064e64`, capture the
XOR-highlight `FUN_40012254`, and assign the effect to the track) and, only if
something needs task-interleaving behaviour, route **A** (emulate the RTOS:
dispatch the trap via VBR `[0x400b9668]`, drive a timer tick). Nothing built so
far needs A; `docs/EMU.md` keeps it on the table.

Not pursued: a gearmulator-style full-machine port with plugin packaging.
`dsp_host` already runs on that project's DSP core; the ColdFire half above
is the slice of that road worth having.

---

### 6b. Per-mode knob NAMES — DONE 3 Sep 2026, emulator-proven

**A MODE select now renames the knobs around it.** BongDelay's MDEP/MRAT read
SCAT/DENS in GRAIN, and the modulation station's FDBK/DLY read RES and
RING/PTCH in PHSR and COMB. `ModeView` in the manifest is the single
declaration; the remixer's UNIT pane follows it, `send_probe --set` accepts
the aliases, and `tools/mode_names.py` emits a MODE formatter that rewrites
the descriptor's 6-byte name fields (`E+0x4e`) before printing its own word.

No new hook: PLAN §6's formatter cave is already called with the value when
the page draws that slot. `tools/verify_modenames.py` (in `make check`) calls
each formatter on the emulated ColdFire and reads the names back — 12 checks
on the rig, including that a mode which does not rename a slot RESTORES its
own name, and that an out-of-range value clamps to mode 0.

⚠️ Inferred, not measured: the rename lands on the next redraw if the panel
draws names before formatting MODE, and the descriptor is shared by every
track running that effect. (The rig's clone window is FULL since the
returns' BUS-mode renames, 3 Sep 2026: label formatters and the FX1 list
overflow into the second zero run at `0x400d24d0`, ~1.6 KB spare there.)

⬜ **Per-mode DEFAULTS are the other half and are NOT on the unit.** The
remixer applies them the moment MODE changes; doing it on the box means
writing the part's parameter bytes when the encoder moves, which nothing here
does live (`ot_project.py` writes parts offline, on a card). That is the next
ColdFire job, and it wants the part-write path PLAN §4 started decoding.

### 6. On-device labels for the mode selects — DONE 2 Sep 2026

**Every stepped select now prints its words on the unit.** WarpFold's MODE
draws `FOLD RING BOTH` where it drew `1 2 3`; the twelve labelled selects the
manifests had authored all along are load-bearing at last.

`Param.labels` was written, schema-checked against `count`, and then never
read by the build — the refhash gate *proved* it was never read. This is the
pass that changed that (`tools/build_bus.py`, the section after the cave
patches).

**How.** Every per-slot "A" formatter (`P+0x0ca`) has one signature —
`void fmt(char *buf, int value)` — and `0x4003c14c` (ON/OFF) proves the shape
that matters: **the label IS the format string**. So a labelled select is a
small cave: bounds-check the value, index a `.word` offset table, overwrite
the value slot with the pointer, and tail-`jmp` into `sprintf`. 40 bytes of
code plus 2 bytes and a string per label — 54 to 82 bytes each, **386 bytes
for the shipping remix's six**, with 2,330 bytes of cave left.

**Only "A" moves.** B stays `0x40047254`, the CHORUS.TAPS tick widget the
clone pass already chose, so this changes *what is printed*, not *how it is
drawn*. `verify_menu` used to pin A to stock's `0x4003c718`; it now requires
B and `0x12a` (the invariant it was actually written for, 17 Aug 2026) and
allows A to be stock's or a cave address.

**The bytes are emitted, not assembled** (`tools/label_fmt.py`). A CavePatch
carries *pinned* bytes so the build needs no m68k toolchain, and twelve caves
whose contents vary with the labels cannot be hand-pinned — so `emit()`
produces them and `verify()` re-derives them through `m68k-elf-as -mcpu=5407`
whenever one is on PATH. All twelve match byte-for-byte.

**Verified without a flash.** `tools/verify_labels.py` (in `make check`)
*calls* each formatter on the emulated ColdFire and compares what it printed
with the manifest — the same method `stock_labels.py` uses, and the only
honest one, because the words are printed rather than stored. It also feeds
each select an **out-of-range** value: a part stores the raw byte, so a saved
project can hand a select a value past its count, and the formatter clamps to
label 0 rather than indexing off the end of its table (value 200 → `ROOM`).

⚠️ **The page render cannot show this** — knob *values* draw as dial graphics
the string-capture hook cannot read (`docs/EMU.md`), so the emulator proves
it by calling the formatter, not by photographing the screen. Still
**UNFLASHED**: what is unverified on hardware is the buffer length behind
`buf` (our longest label is 5 chars, `1/16T`; stock's longest is 4) and
whether anything else consults A where the B widget's count matters.

Confinement, measured on the shipping build: **296 bytes differ from the
pre-§6 image, all of them inside the cave region — zero anywhere else.**

### 7. Putting the unit back — CLOSED 2 Sep 2026

**Item 2 is done and item 1 is moot.** `restock` is the remix: thirteen of
the fourteen stock effects, **including SPRING REV and DARK REV**, plus SEND.

What was wrong: `build_bus.py` repointed all three donor ids to the null stub
**unconditionally**, so a build that placed 250 words silenced 2,724 words'
worth of reverb, and the answer to *"why can I never get the stock verbs
back?"* was "you cannot, ever". The code stream is contiguous from PLATE
upward, so the written span is `[base_a, cursor)` and a donor whose record
starts at or after the cursor **still holds its own code**. It now keeps
those, and reports which: `donor ids taken (PLATE) ... KEPT STOCK:
SPRING/DARK`.

The three reverbs are now ordinary listable stock rows (`tools/remix/
stock.py`), so the remixer offers them like any other effect. Two guards
make that safe:

- the **build** refuses a donor row whose words this selection took, by name
  — only the placement knows where the cursor stopped, so nothing predicts
  it; and
- the **ledger** refuses a reverb beside a module with fixed Y buffers.
  `buffer=True` on all three is **measured, not assumed**: each reads
  `x:>$213` — the host's bump allocator — within ~25 words of its entry
  (PLATE `0x01018`, SPRING `0x01267`, DARK `0x01692`; payload A
  disassembly), exactly like the four stock effects already flagged.

Item 1 (the fallback requirement) was never the real blocker: SEND costs one
row and 215 words, which only ever takes PLATE — the *smallest* reverb,
because the region packs from PLATE upward. So the minimum image costs one
reverb, not three, and no schema change was needed.

Bit-identity: the two shipping layouts (`bus`, `plain`) are **unchanged**.
Four of the 26 refhash cases moved — `render` and the three `xbus-*probe`
diagnostics — and every diff is the intended one: a build that placed few
words no longer silences reverbs it never touched.

⚠️ **UNFLASHED**, and it is NOT "flash the stock OS back" — that is what the
official installer does, and it is simpler. This is the same image with our
chooser edits reverted, which is only interesting if some ColdFire cave is
worth keeping.

## The flash backlog

**What is on the unit is tag 77 / R58, 24 August 2026** — 134 commits ago.
Everything since is unflashed: the delay's R59–R62 quality pass, the
stepped-select labels, stock effects listable beside ours, the insert card,
a module on FX1, a donor region beyond the three reverbs, the BamSep26 rig
(three stations, BongDelay v5) — and, since 3 Sep 2026, **the returns**:
the engines' wet published stereo and four deep, returned at the master by
the character station in BUS mode (RVRB/DLY on the CRSH/RING knobs), the
hosts going quiet only while a return is live. `docs/BUS.md` "The returns";
`tools/verify_returns.py` is its gate, and `make verify-bus` came back 19/19
across the edit — with no return in the rig nothing changed, to the bit.

**`docs/FLASHPLAN.md` is the schedule** — three images, ordered so the
cheapest and safest goes first, each shaped to stack independent claims whose
failures stay distinguishable, and each with what would falsify it. The
platform work needs no flash at all: refhash proves a default selection is
bit-identical, which is what that gate is for.

## Open items and standing caveats

- **Cross-core bus: three defects found and fixed, all hardware-confirmed**
  (clear-vs-read → four buffers; rotation-read jitter → per-core tracking,
  seeded at init; clear-vs-write → clear the next-block buffer). Standing
  caveats, from `docs/XBUS.md`: the fix assumes the cores are **rate-locked**
  🟡 (unverified; the symptom of drift would be a slow return of the artifact
  over minutes); **a single clean configuration proves nothing** — these
  artifacts relocate, so any "fixed" claim needs a track × mode sweep; **no
  local test is evidence** — `dsp_host` is single-core. The free diagnostic
  lever: **change what is on track 5** (core 0's position-0 housekeeper).
- **FREEZE renders locally since 23 Aug 2026**: `DFRZAT=n` (DEV-only,
  build_bus.py) engages the freeze after n post-warm blocks, so a render
  can capture real material mid-flight — the repro lever that found and
  then verified the v6 seam-click fix. (The old blocker stands for a
  freeze toggled MID-render more than once; one engage per render is what
  the hook does.)
- ✅ **"the workbench" was a name nobody reviewed, and it is now "the
  remixer"** (Sam raised it 3 Sep 2026; done the same day). It had arrived
  with the 31 Aug redesign and spread to the doc, the pane copy, the `?`
  overlay and about eighty comments — a second vocabulary for a tool the
  project already calls a remix everywhere else (`make remix`, `remixes/`,
  `tools/remix/`, the `Remix` dataclass). `docs/REMIXER.md` is the manual.
  `WORKBENCH_SOURCES`, `WORKBENCH_THEME` and `out/_audition/workbench.json`
  are still read, so nobody's shell profile or sample folder silently stops
  working. ⚠️ The blanket substitution rewrote *this entry* into "'remixer'
  is a name nobody reviewed ... the thing is a remixer" — a rename cannot be
  applied to the text discussing the rename, and that is the one place to
  check by hand afterwards.
- **BACKLOG (Sam, 3 Sep 2026): the docs over-name the MKII and it reads as a
  restriction.** Sam: it works on MK1 and MK2 — they are the same machine
  apart from a few buttons, and `docs/` already records that both run the
  **same 1.40C image, hash-verified**. So every "MKII" that is really just
  "the Octatrack" should say so. ⚠️ Keep the one distinction that is honest:
  everything here has only ever been *tested* on an MKII, so the claim is
  "the OS is the same, so it should run" (inferred) rather than "verified on
  MK1" (not measured). Sweep `README.md` and `docs/` and say it once, in the
  right place, instead of hedging in a dozen.
- ✅ **A freshly flashed unit keeps drawing the PREVIOUS effect's controls —
  CAUSE FOUND, 3 Sep 2026, and it is not a defect.** The per-part FX1/FX2 ids
  live in the PROJECT (`bank##.work`, `PART+0x009` and `PART+0x011`, eight
  bytes each — one per track), not in the OS, so they survive a flash and
  resolve against the new image's tables. The unit is faithfully drawing the
  effect the project still asks for; what changed underneath it is which
  effect that id names. ⚠️ **Which also means a flash test that starts from
  an old project is not a test of anything** — half the tracks are running
  whatever the last image left there.
  `tools/ot_project.py testproj SRC DEST REMIX` copies a project and stamps
  every bank, part and track with an id the image implements, current parts
  **and** their saved copies, checksums recomputed and read back.
  `docs/FLASHPLAN.md` step 0b.
  ⬜ Still open, and a smaller question than it looked: whether the panel
  should RE-STAGE a page when the image under it changed, or whether "the
  project asked for id 0x12 and got what 0x12 now is" is the right answer.
- **Duplicate instances of one effect corrupt audio after ~5.45 s**, any
  address, mechanism unestablished. One server per bank is the design rule;
  no product configuration has this.
- **Payload B's "609 free above code" has never been loaded** 🟡 — verify
  before spending it.
- **Legacy-project FX2 ids**: every big-buffer stock FX2 effect is handled
  (reverbs null-stubbed, Echo Freeze dispatch is a stock no-op); the
  survivors are dual FX1/FX2 shallow effects, 🟡 *inferred* to make no
  FX2-slot buffer writes. Falsifier: a legacy project with COMPRESSOR stored
  on an FX2 slot of tracks 5–8 — listen for tank corruption while ChonVerb
  plays.
- ✅ **The hardware-mpy caveat is CLOSED**: silicon decay-vs-TIME matches the
  emulator within 13% at three points (`docs/CAPTURE.md`), so the emulator's
  plain-product mpy semantics hold on the unit.

---

## Gates and rules

- `make check` is the floor — never claim an effect works because it
  assembled. The traps that bite silently are in `CLAUDE.md`; disassemble
  what you assemble.
- Refactors prove themselves bit-identical before they land:
  `make verify-roll CAND=…` (reverb), `make verify-delay CAND=…` (delay),
  `make verify-bus` (bus layouts, stamp-first).
- **A slot can draw a knob and publish nothing** — `dsp_host` pokes `r6`
  directly, so publish gaps are invisible locally. Every new or moved
  parameter rides an on-unit reconfirm before it is trusted
  (`docs/PARAM_PAGES.md`).
- Flash discipline: bump `BUILD` every flash, power-cycle before judging
  anything, recovery path read first — `docs/FLASHING.md`.
- Voicing is judged by ear, level-matched, A/B/A/B, wet-only, logged in
  `docs/VOICING.md`. A reverb is finished when a long tail decays without a
  metallic signature, a dense source does not turn to granular hash, and the
  modes are genuinely different spaces — not when the word count runs out.

---

## Build commands

```sh
make bus                    # specialized, cross-core -- THE image
make modules                # the module index and the available remixes
make bus REMIX=verbonly     # a reduced selection (no delay, no caves)
make render                 # build DEV + render the bus locally, no flash
make render-delay           # the delay hatch -- all 3 servers real, renders BongDelay
make image BUILD=002        # repack as a flashable .bin, version-stamped

make check                  # bus + cycles + verify, everything without hardware
make cycles                 # per-effect cycles against the measured budget
make verify                 # ColdFire menu tables (burn probe SKIPs -- see above)
make reverb IN=loop.wav ARGS='--sweep SIZE=0,64,127 --wet'
make verify-delay CAND=modules/bongdelay/delay_new.asm   # bit-identity gate for delay refactors
```

`make bus-plain` (both servers on both cores) does not build — that layout
overruns the donor region. `make burn` **does** build and is flashable; only
`verify_burn`'s plain-layout alias probe is blocked.
