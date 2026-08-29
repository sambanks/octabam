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
- **BongDelay** — a multi-mode delay: CLEAN, PITCH (a once-per-repeat
  harmoniser), GRAIN (a granular cloud), REVERSE — with tape-style
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
make modules              # the module index and the available remixes
make bus REMIX=<name>     # build a selection (default: chongbong)
```

What ships today is four modules: `chonverb`, `bongdelay`, `send`, and
`tempo-sync` — the last being a ColdFire patch rather than an effect, and the
worked example of changing what the firmware *does*.

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

They ship together in the `mutables` remix (1,764/2,724 words with SEND;
`warped` carries WarpFold alone). Built entirely against the manifest
contract; the build's three-source special-casing was generalized the same
day under the refhash gate (bit-identical before any module existed), and
`verify_menu` now derives its expectations from the selected remix instead of
a hand table. All three are **not yet flashed** — every MODE select and knob
publish rides the standing on-unit reconfirm. Known tool gaps: `make cycles`
is remix-blind (still prices the chongbong engines whatever REMIX says;
by inspection the inserts are ~80/~90/~190 cycles/sample worst 🟡), and
send_probe's layout charset is still hard-coded RDS. — inserts render
through dsp_host directly.

Three things follow that are worth knowing before editing anything:

- **The build refuses to start when two selected modules collide** on an FX2
  id, a ColdFire cave, a hook site or a core-private Y word, and names both.
  `tools/remix/ledger.py`; the negative tests are in `make check`. The shared
  64K window is **not** covered yet — its extents are not established well
  enough to write down, so `CLAUDE.md`'s ownership notes remain the map.
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
FREE 30.** The older "A 55 / B 1" figures in this file predated the freeze
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

Cycles are not the current constraint, with one caveat. The number
`make cycles` prints is a **single-core floor**: it sums reverb + delay +
sends on one core, but on hardware no core ever pays both engines. The
delay's worst path (GRAIN, ~2,000 cycles by the tool's count) plus sends
runs against core 1's ~2,150 🟡 *derived* spare — a thin paper margin, while
the unit runs every mode clean; only the burn sweep can measure the real
ceiling.

- ⚠️ **FX1 cycles are paid ×4 per core** — a 300-cycle FX1 effect costs
  1,200 cycles/core. *This*, not program space, is the ceiling on FX1
  ambition.
- ⚠️ **Only the `BURN=1` hardware sweep can re-measure the real per-core
  spare, and the probe currently does not build**: the plain layout overruns
  the region (2,734 > 2,724 — 10 words short; an older ~70-word figure
  predates the delay shrinking). `verify_burn` reports
  SKIPPED in `make check` until words are found.
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

⚠️ Sequence FX1 ambition after the burn sweep (§3) — its real ceiling is
cycles ×4, and the spare has never been measured per core.

### 3. Unblock the burn probe

Find ~10 words in the plain layout so `BURN=1` places, flash it once, and
sweep the real per-core cycle ceiling from the front panel. Everything in §2
prices off that number.

---

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

`make bus-plain` (both servers on both cores) and `make burn` do not
currently build — both layouts overrun the donor region; the burn overrun is
work-order §3.
