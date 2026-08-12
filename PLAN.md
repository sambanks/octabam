# The plan: end state, resource ledger, and work order

Rewritten 9 Aug 2026 after a holistic re-review (the 8 Aug plan is at
`git show 7d1dd0b:PLAN.md`; the review found one shipped-in-source defect it
had missed, two stale open items, and one defect class it had only half seen).
**This is the cold-start document — read it before `docs/XBUS.md`**, which is
the *architecture* record rather than the plan.

---

## Start here

The goal is unchanged: **better effects for the Octatrack**. What has changed
since 9 Aug: **the full R13 stack is on hardware and confirmed by ear** —
Round 13's bloom voicing, the 8-line engine, SPEC, the relocated buffers and
the bus auto-gain all run on the unit as voiced (10 Aug). Getting there took
a three-flash diagnostic detour whose root cause was a wrong assumption, not
a defect: **the track↔core mapping is inverted from every earlier document**
(payload A / ChonVerb serves tracks 5–8, payload B / BongDelay serves 1–4 —
measured via the MrkVerb32 marker flash, kept deliberately for the
delay→reverb series topology).

| | state |
|---|---|
| On the unit | **`OCTABAMR15`** (tag 34) — R14 + LFO roll + wet makeup. **MIX confirmed by ear; BongDelay confirmed working, 10 Aug** |
| Where effects live | ChonVerb on **tracks 5–8** (5 = position-0 housekeeper), BongDelay on **tracks 1–4**, Send anywhere ✅ measured |
| Reverb | eight-line, confirmed on hardware. DONE FOR NOW (11 Aug, see step 1); the knob-publish gap is CLOSED (10 Aug reconfirm — see step 2) |
| Delay | ✅ **FIRST HARDWARE RUN 10 Aug (R15): BongDelay WORKS** — echoes on tracks 1–4, first execution of payload B code anywhere (dsp_host cannot boot it). v1 scope; voicing unstarted. ✅ 12 Aug (evening): the harness is back — `make render-delay` renders BongDelay locally, **`→VERB` delay→reverb CONFIRMED in the emulator** (the morning's "zero output" was a SPEC-dump mislabel, retracted — see step 3). Rig is confident. ✅ Later the same evening: **v2 stage 1 (CLEAN) LANDED** — mode-dispatch spine + manual wrap, proven bit-identical to v1 (`make verify-delay`, 11/11); see 3.1. ⚠️ **Stage 2 PITCH's first ear pass FAILED the splice** (12 Aug late) — the full-overlap window fix landed (`e6f5359`), the 4× widening is retracted, and the CASCADE IS GONE (`cf5d73a` — every repeat shifted once, not *n* times; the measured octave ladder is gone). ✅ **STAGE 3 FREEZE** (`6aac927`, loop length = TIME) and ✅ **STAGE 4 TAPE** (`3fc25ba`, wow+flutter in the loop, WOW knob) LANDED. PITCH is still not voiced; TAPE's loop saturation is deliberately deferred. See 3.1 |
| Flash gate | **Passed/overtaken** — the diagnostic trip flashed R13-equivalent and Sam confirmed "working as voiced". The "excellent" bar below still governs *voicing* sign-off |
| Next | **Flash the R16+R17+R18 batch (tag 37)** — R16 SHMR fix + selects + GATE; R17 shimmer crossfade/chorus; R18 Valhalla uplift (single-octave shimmer, lerp heads, BIG decay ceiling, driven-line presence, GATE=0 bypass fix) — all ear-passed locally, none flashed. On-unit: step-2 knob reconfirmation protocol, then voicing residue (pad forwardness, 6-9k crest, shifter-input HP, page-1 tuning, PLATE ear pass, TIME refit) → BongDelay voicing. See VOICING.md R18 |

✅ **RESOLVED 10 Aug (on-unit reconfirm): page-2 PUBLISHES.** The earlier
"not publishing" report was a misdiagnosis (wrong tag + track↔core
inversion during the chaotic trip). Per-knob: MODE steps, PRE reached the
DSP (before its R16 retirement to GATE), DIFF/WIDTH move; SHMR was silent
because the DSP read the wrong offset ($b where the panel publishes $c —
R16 reads $c OR $b, unflashed); →DEL silent pre-R16. Page-1 knobs publish
and work. Remaining 10 Aug findings: (2) Page-1 knob feel needs a
**tuning pass** against the R13 engine (ranges/curves — Sam, 10 Aug).
(3) MIX at 100% is much quieter than dry — inherent (wet spreads the same
energy over seconds; the straight crossfade measured −7 dB) and now has
ear evidence; queue a **wet makeup gain** voicing pass. Cheapest form is
~1 word (`asl` on the wet path); payload A is at FREE 32 (11 Aug).

---

## The principle that decides everything: SYMMETRY

**FX2 bus servers are asymmetric. FX1 inserts cannot be.**

ChonVerb exists only on core 0; BongDelay only on core 1. That is what
specialization bought. But an FX1 insert must run on *any* of the 8 tracks, so
it must exist in **both** payloads — and program space is **per core**.

```
                    payload A (core 0)        payload B (core 1)
                    tracks 5-8 ✅MEASURED     tracks 1-4 ✅MEASURED
  carries           SEND + ChonVerb           SEND + BongDelay
  free (region)     4 (12 Aug, delay          1353 (12 Aug late, v2
                    auto-gain)                stage 2 PITCH)
  free (above code) 33                        609  🟡 inferred, never loaded
  ---------------   -----------------------   -----------------------
  spendable on      ChonVerb growth           BongDelay, and NOTHING ELSE
                    + any FX1 work
  FX1 work costs    <-- from BOTH payloads, so capped by A's side -->
```

**Two consequences, and they are the whole plan:**

1. **Payload B's ~2,600 words can only ever be spent on the delay.** No FX1
   redesign can reach them. The delay's budget competes with nothing.
2. **FX1 redesign and the delay never touch the same pool**, so there is no
   resource reason to sequence one before the other.

---

## The resource ledger, end state

### Program space — the binding constraint, per core, 8,192 words

✅ Region numbers from the build report, 12 Aug 2026 (delay auto-gain):
**payload A used 2,720 of 2,724, FREE 4** — the delay auto-gain's writer-side
changes cost A 28 words (send +9, reverb +19) on top of 11 Aug's 2,692/32,
which R16–R18 had already run down from the 178 the LFO-block roll freed on
10 Aug (roll: lines 2–7 in one loop over a 24-word P table, proven
bit-identical against the unrolled engine incl. a 600-block MOD=127 A/B; the
session's lesson is the m5 line-modulo invariant, documented at the roll
site). **A is effectively FULL** — the wet-makeup `asl` (~1 word) still
fits; anything else waits on the reverb-side LFO-block roll lever below.
**Payload B used 726, FREE 1,998** — 12 Aug (v2 stage 1, delay 514 → 559):
**used 771, FREE 1,953** — 12 Aug (auto-gain, delay +65 / send +9): **used
845, FREE 1,879** — 12 Aug late (v2 stage 2 PITCH, delay +526): **used
1,371, FREE 1,353** — 12–13 Aug (stages 3/4/4b/5/5b–5e/6, delay 1,371 →
**2,375**): **used 2,596, FREE 128** — 13 Aug (5f optimisation, delay →
2,360): **used 2,581, FREE 143.**

⚠️ **PAYLOAD B IS NO LONGER ROOMY, and this is the entry that says so.**
Every stage costed itself against "~1,000 free" and that figure went stale
under them: BongDelay is 2,375 words, a 4.6× growth over v1's 514, and B's
slack is down to **128**. Stage 5's "the roll is MANDATORY, it does not fit
unrolled" reasoning now applies to *any* further mode — and r7 is full at
the same time, so the next feature needs both the Y state table and words
that do not exist. **Program space has become a design driver on payload B
for the first time**, which retires the "specialising the payloads frees
1,998 words for nothing" framing for B specifically. A is unchanged at
FREE 4.

⚠️ `verify_burn` is **SKIPPED again as of the R16–R18 builds** — the BURN=1
layout no longer fits payload A (DELAY SERVER 2,794 > 2,724 words), so the
BURN hardware sweep is re-blocked until words are found (the LFO-block roll
of the delay side, ~150–200 words 🟡, is the listed lever). The 10 Aug
"PASSES again / unblocked" claim held only until R16 landed.

| | payload A | payload B |
|---|---|---|
| stock code below the effects | ~2,001 | ~1,455 |
| **10 FX1 effects** (the reclaimable pool) | **3,384** | **3,384** |
| our donor region (PLATE+SPRING+DARK) | 2,724 | 2,724 |
| free above the code | 33 | 609 🟡 |

The ten FX1 effects, with sizes (identical in both payloads):

    FILTER 727   LO-FI 537   DJ EQ 345   CHORUS 329   FLANGER 289
    EQUALIZER 282   COMB 277   SPATIALIZER 261   COMPRESSOR 180   PHASER 157

**Space levers, in order of preference — do not pull until A is tight again:**
- **Roll the eight LFO blocks** (`lf3e..lf4a`, ~310 source lines of eightfold
  near-copies): the tank roll precedent says ~1/8 the words, so **~150–200
  freed** 🟡 inferred from line counts, priced by the build report when tried.
  Per-line rate multipliers become an 8-entry table — the same shape as the
  tank's state table, and unlike the levers below it needs no boot patching.
- **OMR memory map** (`docs/CHIP.md` §3): Fig 3-3 doubles P, 8K → 16K, **+8,192
  words**, costing `Y:0xA000-0xBFFF`. Patches the boot path. Scoped 12 Aug:
  - ⚠️ **On core 0 it EVICTS TANK LINES 6-7** — ChonVerb's eight lines are
    Y:0x4000-0xBFFF at 4K each (reverb_server.asm:683), so the Y cost is not
    an abstract pool shrink; it reopens the done-for-now reverb (re-layout +
    re-voice). Treat core-0 OMR as reverb work, not a build flag.
  - 🟡 **OMR is per-core: core 1 alone can take Fig 3-3** (+8,192 P for the
    delay) with no tank cost — BongDelay's lines live in the shared window,
    not private Y. Contingent on nothing else on that core using
    Y:0xA000-0xBFFF (legacy dual-class FX2 ids are the suspect).
  - ✅ **It buys nothing locally**: dsp_host has no 8K wall and no OMR model
    (P is flat 0x80000 words, dsp_host.cpp:391) — which also means NO OMR
    risk can be de-risked in the emulator; each unknown is a flash (min two:
    OMR-only, then a marker module above 0x2000).
- **Code in the shared window**: P/X/Y alias at `0x30000-0x3FFFF` ✅ and stock
  already runs code there ✅, so up to 64K is program-addressable at 1 wait
  state. 🟡
- FX1 consolidation (step 4) frees ~550–650 per payload as a side effect, but
  is its own project, not a lever to pull for the reverb.

### Cycles — NOT the constraint, per core, 4,535/sample

✅ 1,392 spare measured 7 Aug 2026 on a 964-cycle bank **with four FX1 FILTERs
already running** (worst case, no derating needed). `make cycles`, 12 Aug
(late): **room for new work: −232 cycles/sample** (819 on 11 Aug post-R18;
v2 stage 1's wrap → 777, delay auto-gain → 770, PITCH → 352, GRAIN → −232,
GRAIN 5e → −952, **5f optimisation → −616**). ⚠️ **THE PRINTED NUMBER HAS GONE NEGATIVE, and the model is what
broke first, not the chip.** It sums reverb + delay + two sends on ONE
core; on hardware ChonVerb is payload A (tracks 5–8, core 0) and BongDelay
is payload B (tracks 1–4, core 1), so no core ever pays both. The delay's
worst path (GRAIN, **1,595** after the 5f optimisation pass; 1,931 before)
plus two sends is ~1,635 against core 1's ~2,150 🟡 spare — a **24% margin**,
recovered from the 9% the split left. It was 42% before GRAIN existed, so
the trend still points one way and the burn sweep is still the only thing
that can re-measure the ceiling, and the server-role lock means it is charged ONCE per
bank however many tracks select it. Treat −952 as "the single-core model
has outlived its usefulness", not as an overrun — and note that the burn
sweep is now the ONLY thing that can re-measure the real per-core ceiling,
which raises the priority of unblocking it. ✅ **The mode-fork model was generalised to N paths, 12 Aug
(`3fc25ba`)**: BEGIN..first MID is the always-run dispatch and each MID..next
is one mutually exclusive alternative, so three modes are priced as
dispatch + WORST alternative (dispatch 14w, PITCH 524w, TAPE 193w) instead
of every engine summed. It also stopped under-charging the dispatch, which
moved the delay 762 → 769 before TAPE counted at all. ⚠️ The PITCH
drop is a MODEL change as much as a cost: the tool now prices the delay's
mode fork at its worst path (~450 cycles in PITCH mode), and the bank model
is the pre-XBUS single-core one — on hardware the PITCH cost lands on
CORE 1's ~2,150 🟡 spare, not on core 0 where FX1 competes. The printed
number is the honest single-core floor; the burn sweep remains the only
re-measure.

⚠️ **FX1 cycles are paid ×4 per core.** A 300-cycle FX1 effect costs 1,200
cycles/core — which does not fit in 819. *This*, not program space, is the
ceiling on FX1 ambition. Only a re-run of the burn sweep re-measures the spare
itself; the probe NO LONGER BUILDS (re-blocked 11 Aug: the plain layout
overruns by 70 words — see the §ledger above) and cannot fly until words are
found; it was briefly green on 9 Aug and would have flown with
the next trip.

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

### 1. Finish ChonVerb — the ear items, in dependency order

**✅ DONE FOR NOW — Sam's call, 11 Aug 2026**, after the R18 ear pass and
the Discord demo set (`out/demo_sources/discord/`, shimmer + gate on real
material). "Done for now" is a voicing verdict, not a closure: still open
if a future round reopens the file are the pad's last forwardness, the
6–9 k crest, the shifter-input HP, the TIME refit (1.3), the PLATE ear
pass, and 1.4's gain-structure measurement. **Tags 35–37 plus the LP
default change (10333c6) remain UNFLASHED** — the flash bar in "what
excellent means" below still gates the trip. Work order moves to
BongDelay (section 3).

The reverb is structurally right: eight driven lines, correct FWHT
normalisation, all lines written and read, distinct modes, linear until the
top ~4 dB. What remains is that **what you hear of the tail is not yet what
the tank does** — and the items below are ordered so each measurement is made
on top of the previous fix, not through it.

#### 1.1 Per-line decay gains — ✅ BUILT AND VERIFIED, 9 Aug 2026 (third
#### attempt; the first two self-oscillated, and both prior theories of why
#### are retracted below)

The defect was real: `$1e` was ONE decay gain for all eight lines, so equal
gain *per pass* was unequal decay *per second* — measured ~63 dB/s spread at
ROOM's defaults (−48.9 longest line to −110 shortest), an eight-line tank
decaying into a two- or three-line one. That *is* the tail that starts lush
and turns metallic.

**What shipped**: Jot's `g_i = g^(T_i/T_0)` linearised about the loop-neutral
point — `stored_i = a + r_i·($1e − a)` with **`a = 1/√8 = $2D413C`**, primed
per block after the TIME fold into Table B's second word (the dead
has_allpass slot), read by the write-back loops at the same instruction
count. 63 program words in the per-block path, ~0 cycles/sample (bank 1332,
headroom 1024). Payload A FREE 158 → 95.

**The accounting that finally made it work — measured, not derived:**
- ❌ **"mpy doubles" is FALSE in this toolchain.** Two independent in-situ
  measurements: `$1e` peeked at three TIME values fits `TIME_val·md`
  exactly (plain product, three-point exact), and the first failed build's
  peeked gains solve to k=1.0002 for a genuine signed mpy. Every derivation
  built on the doubling — the 0.5 anchor, the "hidden factor F", both
  stability theories — was wrong at the root. ⚠️ **Hardware risk, for the
  BURN trip checklist**: if silicon's fractional mpy shifts left where the
  emulator's does not, every decay constant is 2× off on the unit. The
  8-line engine has never run on hardware; check decay times first.
- The line's per-pass multiplier is the stored word itself, so the loop is
  `diag(stored_i)·H8`, ‖H8‖ = √8 — and the uniform engine was **already
  norm-stable** (max `$1e` = 0.3252, radius ≤ 0.92). Loop-neutral is stored
  = 1/√8 = 0.3536, and `$1e` = TIME_val·md ≤ 0.4999·0.6505 = 0.3252 can
  never reach it, so `stored_i` (a weighted average of `a` and `$1e`) stays
  strictly below neutral: **radius ≤ 0.952 at every knob in every mode,
  guaranteed by norm alone.** Runtime peek confirms: gains 0.3159..0.3366,
  exactly as computed.

❌ **RETRACTED (both 9 Aug, hours apart):** (1) "stored 0.5 is neutral, the
gains are free and provably stable" — 0.41–0.48×√8 > 1, it simply exceeded
the norm; (2) **"asymmetry itself is the trigger** and the tank needs a
normalized FWHT first (1.1a)" — falsified by the same measurement: the
"proven-stable uniform 0.4336" control that theory rested on was a *derived*
$1e value, and the real one is 0.3251. Uniform 0.42 explodes exactly like
the asymmetric builds did. There is no knife-edge; there was an arithmetic
error. The planned FWHT surgery (1.1a) is **unnecessary and cancelled** —
an exact-compensation refactor would not have changed the loop anyway.

**Verification (all measured 9 Aug):**
- Stability: 3 modes × TIME {0,64,127} × SIZE corners, −26 dB click, no
  growth anywhere (quiet source, per the gate — hot sources mask instability
  in the clip limit-cycle).
- Equalisation: predicted per-line decay now −48.9..−46.9 dB/s (2 dB/s
  spread, was 63); rendered envelope decay-rate drift over the first second
  improved from −63→−37 dB/s (pre) to −46→−33 (post), early tail density
  audibly retained, tail runs 5 dB deeper before its floor. Residual drift
  is consistent with per-line damping — step 1.2's item, HF-only.
- `make check` green including verify_slots; disassembly of the new block
  verified instruction-by-instruction (genuine `mpy x0,y1` = 2000c0, no
  mpysu in the signed path).

🟡 Still open here: the ~3% r₀ shortfall (r₀ = 2·frac₀ = 0.966, not 1.0)
uniformly shortens decay slightly — folds into TIME calibration at
re-voicing. Per-mode anchors are possible later (a is one immediate) but
the norm argument holds for the global one.

⚠️ A NEW assembler-trap datum from the debugging, now in CLAUDE.md: dsp_asm
silently downgrades any `mpy` operand order it doesn't know to **mpysu**
(second operand unsigned) — 23 sites in the shipping engine, all audited
safe. `mpy x0,y1` and `mpy y0,x0` encode signed. Disassemble any new mpy
whose second operand can go negative.

#### 1.2 Per-line damping — ✅ MEASURED 9 Aug 2026, and CLOSED as not
#### warranted. Two new findings came out instead.

The hypothesis: one damping coefficient for all eight lines, applied per
pass, should rotate the tail's spectrum (short lines go dull first) even
after 1.1 equalises broadband decay.

**Measured** (band-split FFT envelopes, 93 ms windows, raw dsp_host output,
quiet click, ROOM/PLATE/BIG at LP 100 and 64, MOD on and off):

- **LF (150–1k) and MF (1–4k) decay at near-constant rates post-1.1** — the
  bands that carry the tail's energy show no audible-scale rotation. This is
  the plan's own falsification clause: matching rates → close the item.
- **HF (4–12k) is non-uniform, but NOT from per-line damping.** Its late
  envelope is dominated by two separate mechanisms, isolated by controls:
  1. **AP-modulation scatter shelf.** The always-on in-loop allpass
     modulation (fixed depth `$200000`, deliberately never zero) scatters
     MF energy into HF at ~25 dB conversion loss, producing a hard shelf
     ~25 dB below the band's start that then tracks the MF tail. Measured:
     zeroing the depth in a scratch build removes the shelf entirely.
     **This is a 1.3 voicing lever**: depth trades tail smear (the thing it
     exists for) against HF floor. Not a defect.
  2. **A residual slow HF floor (~−18 dB/s) with ALL modulation off** — HF
     decaying slower than MF, impossible for circulating energy, i.e.
     recirculating truncation noise, sitting ~55 dB below the tail's
     broadband level. Known-noise item; harmless at listening levels.
- The genuine per-line HF rotation is not separable above those two floors
  in the mixed output.

**Cost check that seals it**: table A has NO spare per-line word (all six
live — offset, fraction, d1 carry, damp state, LO state, line output), so
per-line coefficients need a 7-word stride across every table writer,
~60–70 payload-A words (FREE was 95 when this was priced; 32 now — this
  item no longer fits without finding words), plus sample-loop cycles.

**Revisit condition**: only if 1.3's ears say the naked tail's top end turns
sparse/metallic as it decays. The spec for that case, so it need not be
re-derived: `c_i = a + r_i·(c − a)` with anchor `a = 1.0` ($7FFFFF) — the
same weighted-average form as 1.1, short lines pulled toward no-damping.
Safe by 1.1's norm argument (damping is pure loss; the gain bound
`max_i(gain_i)·√8 ≤ 0.952` does not depend on it), and the multiplies are
plain products (1.1's accounting).

#### 1.3 Re-voice the modes — Sam's ears, VOICING.md rules

Blocked on 1.1 (and 1.2's measurement) because voicing against a tank whose
decay is about to change is voicing the wrong tank — the reason the 8 Aug
re-voice was deferred. Judged by ear, level-matched, A/B/A/B, wet-only,
rounds logged to `docs/VOICING.md`.

In scope:
- Per-mode constants generally, at eight lines.
- **Lines 4-7 tap fractions are still derived, not voiced** (one shared
  interleave scale per mode in `$6c`). Give them their own per-MODE values
  if the ear asks for it — costs a few words per mode (A had 154 free when
  written; 32 now).
- **The shimmer decision** (Sam, 9 Aug: decide after re-voicing). It is
  built, 130 words, clean in isolation, `SPEED=0` provably off, and fits
  A's 154. Judge it *inside* the re-voiced tank, then ship or hold. If it
  ships, its depth knob's hardware publish check joins the flash checklist.
- **BIG's ringing: re-measure before believing it.** The old open item
  ("~30 dB more HF, decay scale exactly 1.0") predates FWHT renormalisation
  (BIG's `$1e` is now 0.60) and per-mode damping — its premise is stale.

#### 1.4 Quality items that survive re-voicing

- **Clip knee at ~0.6–0.7 FS inside the feedback loop.** Round 9 settled
  what it is NOT: the engine is linear to the measurement floor below
  −6 dBFS, and the output sum is ruled out. The FWHT's three unscaled
  intermediate stores are the leading candidate but the derived loop gain
  does not close (2×`$1e` against √8 implies divergence, and it decays) —
  **measure the internal gain structure before touching anything.**
- Tank saturation above ~0.35 FS (older item, likely the same knee — fold
  into the same measurement).

#### What "excellent" means here, so it can be called done — and it gates the flash

Not "bigger". A reverb is finished when a long tail decays without a metallic
signature, when a dense source does not turn to granular hash, and when the
three modes are genuinely different spaces rather than one space at three
lengths. Ear judgements, logged in `docs/VOICING.md`, are the acceptance
test — not the word count. **Sam flashes when this bar is met, not before.**

### 2. Guardrails — cheap insurance against the bug classes that keep recurring

Done 9 Aug (this session) unless marked:

- ✅ **`$0c` slot collision fixed** — the md_* tap scale clobbered the bus
  auto-gain 1/N every block; auto-gain multiplied by ~0.75 instead of 1/N.
  Moved to `$6c`. Verified: insert render bit-identical, send render +2.87 dB
  = exactly 1/0.71875. ⚠️ Consequence for past judgements: **no post-8-line
  emulator render ever had working auto-gain**, and the unit has never had
  any — re-derive any multi-send balance conclusion from after this fix.
- **`verify_slots` in `make check`** — static check that no r7 slot is
  written from two unrelated sections of `dsp/reverb_server.asm`. Third bug
  of the family ($83 garbage → freeze, $84+ → hang, $0c → clobber); the
  check would have caught this one at commit time.
- **Doc propagation** — REVERB.md's front half described the deleted
  four-line engine (ER, HALL, 2048-word in-loop APs); `render_reverb.py`
  help listed four modes. Fixed. The stale-plan items are folded into this
  rewrite: the input-diffuser complaint was **already fixed** by Direction A
  (taps 179/293/419/547 = 4.1–12.4 ms, Dattorro-scale), and BIG's ringing
  premise is stale (see 1.3).
- 🟡 **Parameter-delivery protocol — design before the trip, not at it.**
  A slot can draw a knob and publish nothing, and `dsp_host` pokes `r6` so
  everything looks live locally. This caused the old shimmer to run stuck
  half-on in every build anyone ever heard, and **it caps how many usable
  parameters any effect can have** — close it before designing a 12-knob
  delay.

  ✅ **RESOLVED 10 Aug (R16): page-2 publish WORKS — the "doesn't publish"
  finding was wrong.** On-unit reconfirm (Sam): MODE steps, PRE swooshes
  (reaches the DSP), DIFF/WIDTH move but subtle, SHMR + →DEL silent. The
  descriptor was never the problem (it is byte-equal to stock DARK's working
  page-2 knobs). Two real issues surfaced instead, neither a publish gate:
  - **SHMR read the wrong offset** (`$b`); the panel publishes slot 6 to
    `$c`'s knob field. `$b`-only was dead on the unit while a local render
    has an obvious +12 shimmer (octave-up −7.3→−1.1 dB, dominates the tail).
    ✅ **R16 reads SHMR from `$c` knob OR'd with `$b`** — assembled, `make
    check` green, local-verified; confirm on unit.
  - ✅ **Companion low-byte fields → 4-step SELECTS (R16).** WIDTH
    (mono/narrow/normal/wide) and →DEL (off/.25/.5/.75) now publish. Smooth
    knobs there read near-boolean on hardware; selects are the page-2 budget.
  - ✅ **DIFF works** (Sam confirmed audible).
  - ✅ **PRE → replaced by GATE (R16).** PRE worked (clean 90 ms pre-delay,
    proven) but 93 ms is buffer-capped and not worth a knob (Sam). The `$e`
    slot is now **GATE — a gated reverb** (Phil-Collins slam): 0 = off, up =
    hold time before the wet slams shut. Envelope keyed on the tank input,
    fast attack + ~20 ms release, per-sample wet multiply. Voiced by ear
    (Sam: release "perfect" between 15/25 → 20 ms). ~104 cycles against the
    measured spare (819 as of 11 Aug).
    The pre-delay was removed to free the r7 state slots ($29/$30/$62).

  **R16 batch is flash-ready.** SHMR reachable + WIDTH/→DEL selects + GATE
  (new gated-reverb feature). Remaining page-2 polish is voicing (shimmer
  character — Sam: "sounds not good"), for after the flash confirms it.

  ⚠️ **New DSP trap from the GATE work (now in CLAUDE.md):** a logical/asr
  op on an accumulator leaves the extension byte stale, and the next
  `move a,x:` SATURATES the store to full scale. A hand-rolled sign-mask
  select pinned the gate open and disassembled correctly. Fix: use the
  conditional-transfer ops (`tmi`/`teq`), which also keep the loop branch-free.

  ✅ **The original reconfirmation protocol was EXECUTED 10 Aug** (on-unit,
  R15): MODE stepped, PRE swooshed, DIFF and WIDTH moved, SHMR and →DEL were
  silent — which localized the failures to the DSP-side reads, not publish,
  and produced the R16 fixes (SHMR reads `$c` OR `$b`; WIDTH/→DEL became
  4-step selects; PRE retired, its slot is GATE). The "doesn't publish"
  finding is retracted and that item is CLOSED.

  **What replaces it — the tag-37 flash checklist (execute on the next
  flash, on a track confirmed to be ChonVerb — tracks 5–8):**
  1. **MODE** (control; known-good select): step 0→1→2, hear ROOM→PLATE→BIG.
     If MODE does nothing, the track isn't ChonVerb — stop and fix that.
  2. **SHMR** (slot 6, R16 `$c`-OR-`$b` fix): 0 → ~100. Expect an octave-up
     sheen growing on the tail. This is the R16 fix's on-unit confirm.
  3. **GATE** (slot 10, `$e` knob — NEW in R16): with drums, up from 0.
     Expect the tail to chop off after the hold (higher = longer hold,
     measured 11 Aug in the emulator). GATE=0 must be a true bypass (R18).
  4. **WIDTH select** (slot 9, `$d` low): step 3→0, image collapses to mono.
  5. **→DEL select** (slot 11, `$e` low): step up with a delay on the bus;
     dry starts feeding the BongDelay send. Still never heard on-unit.
  6. **LP boot default**: fresh part should boot bright (LP=127,
     commit 10333c6).

### 3. BongDelay — the delay you can route

**Second, unchanged in rationale: the only thing that can spend payload B's
~2,600 words, and the one feature the machine has never had — but it competes
with nothing, so nothing is lost by finishing the reverb first.**

✅ **The stock delay is DOWNSTREAM of the FX2 insert** (measured by ear,
`fcf22fd`) — its output can never be tapped. **delay→reverb exists only
through BongDelay's `→VERB` cross-send**, already built. That is the goal.

✅ **`→VERB` CONFIRMED (emulator), 12 Aug 2026 (evening, same day the
morning's finding below was recorded) — delay wet reaches the
reverb, and the direction is the designed one: delay → reverb, never the
reverse.** Measured via `--layout RDS` with SEND's `→REVERB` knob at 0, so
the *only* route into ChonVerb was BongDelay's cross-send: VRBW=127 filled
the reverb at −14.0 dBFS; the VRBW=0 control was digital silence (−180 dB).
Local echo is also structurally confirmed: impulse taps at exactly 5,184
samples (TIME=40 → 40·128+64), decaying through FDBK. Hardware confirm
still rides the next flash.

**The 12 Aug "zero output in every layout" finding is RETRACTED — the delay
was never instantiated.** The disassembly-first rule found it in one step:
the stale dump's DELAY dispatch entry *equalled* SEND's. That dump was a
`SPEC=1` build (`make render` sets SPEC), and under SPEC payload A carries
no delay — `build_bus.py` deliberately aliases id 0x06 to the SEND client,
which is a dry passthrough. Every "delay" measurement on 12 Aug measured a
SEND. The "valid for DELAY SERVER's own code" reasoning was wrong: the
delay's code was not in the dump at all. `send_probe.py` now refuses to run
a D layout against a dump whose DELAY entry is the SEND alias, so this
class of silent mislabel dies loudly instead of measuring.

**A real DEV-only memory collision was found and fixed on the way** (it
blew up the RDS layout even with a genuine delay): the DEV build placed the
delay's 32K lines at payload A's Y base 0x30000, but payload A's half of
the shared window is fully owned — ChonVerb's relocated buffers at
0x30000/0x34000 and the bus scratch at 0x36000–0x3608f (0x36085+ added by
the delay auto-gain: DELAY counts + the delay's 1/N table). LineR's write
pointer crossed the parity word, all four ACC buffers and both role locks
every 16,384 samples. Fix: under DEV the delay is substituted to its
**shipping address 0x38000** (payload B's half, unused in a single-core
dsp_host run), making the DEV delay byte-identical to the one that ships —
including the never-housekeep gate, covered by SEND's election exactly as
on hardware. The DS THD even improved (−35.2 → −36.8 dB): the historical
numbers had the scratch corruption folded in.

Harness: **`make render-delay`** builds the hatch (`DEV=1 XBUS=1` — NOSHIM
was load-bearing for a few hours on 12 Aug, until the same evening's
placement change below made room for the full-shimmer reverb again) and
renders `--layout DS`. Falsifier for the →VERB claim: it is emulator-only;
if hardware's cross-core timing differs, the on-unit check is →DEL/→VERB
routed audio on tracks 1–4 feeding a track-5 ChonVerb.

Budget: **1,353 program words, ALL of them renderable** (1,953 before the
12 Aug auto-gain commit, 1,879 before stage-2 PITCH) — the DEV placement
change landed 12 Aug evening (delay at P:0x04000 outside the donor region,
see traps), so the hatch no longer caps the delay — **~2,150 spare cycles
with four FX1 FILTERs /
~3,200 without** 🟡 (derived from the 7 Aug sweep, never separately
measured on this core), **32,768 words of line = 0.74 s stereo / 1.49 s
mono in hand**, plus the private-Y 32K 🟡 counted in the pool but never
claimed.

#### 3.1 BongDelay v2 — design sketch (proposed 12 Aug 2026, ratify by ear)

**The reference decision.** Microcosm-adjacent — a **pitch/granular delay
feeding ChonVerb over `→VERB`** — replaces Round 11's "Supermassive-style
diffused feedback" placeholder (VOICING.md; the placeholder predates
shimmer and Sam flagged it for reconsideration). Two reasons it fits THIS
box: in-loop diffusion is partly redundant with an 8-line shimmer reverb
sitting immediately downstream, and the risky machinery for the pitch
direction (crossfaded variable-rate lerp heads, their truncation floor) is
already de-risked by shimmer v3. Granular-into-reverb *is* the Microcosm
topology; the routing half is measured, today.

**The spine, shared by every mode** (the ChonVerb pattern: one engine +
MODE select):
- Stereo lines at Y:0x38000, manual compare-and-wrap (frees the layout
  from AGU modulo; ~4–6 cycles).
- Feedback loop with TONE one-pole (exists) and the PING crossfeed matrix
  (exists); saturation stage in the loop 🟡 optional, voice it.
- **Auto-gain from the first draft** (1/N table, parity indexing — the
  `$0c` lesson, non-negotiable).
- Warm-up tag idiom (`$2e0000`), new per-track state in the **Y state
  table** (r7 `$00-$83` is full).
- `→VERB` wet/dry sends (exist, confirmed); MIX with a wet-makeup pass at
  voicing (the reverb's −7 dB lesson).

**Modes, in build order** (each lands only when renderable + ear-passed;
each stage is a separate commit gated by `make check`):
1. **CLEAN** — v1's behavior as mode 0, bit-identical through the new
   spine (the `verify_roll` gate pattern: refactor first, prove
   equivalence, THEN add). ~0 new words beyond the mode dispatch.
   ✅ **LANDED 12 Aug 2026 (evening).** The spine is real: MODE select
   read (page-2 slot 7, r6+$c bits 8-15, ChonVerb's exact idiom; unknown
   values run CLEAN; `DMODE=n` is the local override — dsp_host cannot
   drive companion fields) and AGU modulo replaced by manual wrap
   (per-sample phase AND; exact because both line bases are
   0x4000-aligned). **Bit-identical: `make verify-delay`
   (tools/verify_delay.py), 11/11 PASS** — sensitivity + nop-relocation
   controls, then TIME 0/127, PING 0/64/127, FDBK+TONE high, split=7, and
   DMODE=3 (nonexistent mode) ≡ CLEAN. New blocks disassembled from the
   emitted image (every mpy is the signed 2000c0). Cost: 514 → 559 words
   (+45); payload B FREE 1,998 → 1,953; hatch FREE 69 → 24, which made the
   DEV placement change stage 2's opener — ✅ **and it LANDED the same
   evening**: the DEV delay now assembles at P:0x04000 outside the donor
   region (`build_bus.py` DEV_DELAY_P; the module record is appended to
   the .mem dump — the payload has 6 bytes of record slack, measured, and
   dsp_host boots the dump). Verified bit-identical in-region vs relocated
   (3 corner renders), full gate re-run 11/11 vs v1 through the new flow,
   THD unchanged (−36.8). The hatch no longer caps the delay, and NOSHIM
   is back to optional (full-shimmer hatch: 2,692 of 3,053, FREE 361).
   The descriptor-side MODE select is deliberately deferred to stage 2 (a
   one-value select draws a dead knob), and **bus auto-gain is NOT in the
   spine commit** — it is a behavior change, measured like the reverb's
   `$0c` fix rather than bit-compared, and lands as its own gated commit
   before PITCH.
   ✅ **BUS AUTO-GAIN LANDED 12 Aug 2026 (the gated commit).** The delay-bus
   mirror of v121: SEND's `→DELAY` tap and the reverb's `→DEL` send register
   once per block in `$985/$986` (parity-indexed, reset by all three
   housekeeping copies — the delay's copy was silently MISSING even the
   `$983` reset since v121; healed, though it is dead code in live builds
   because the XBUS gate keeps payload B from housekeeping) and write
   `asr #3`; the delay looks up 1/N (table at `$988-$98f`, bus scratch,
   because both line buffers fill its entire half-window) and shifts back
   up 3. **Measured (the gate):** N ∈ {1,2,3,5,7} sends at 0.3 FS all
   render −26.1 dBFS / −36.1 dB THD; before, level grew with N and hit the
   rail (7 sends: −13.4 dBFS at −10.2 dB THD). Single-send level-identical
   before/after (net-unity round trip); RDS still −36.8 THD. Every new mpy
   disassembled from the emitted image (`mpy x0,y1,b` = 2000c8, signed).
   Cost: payload A 2,692 → **2,720 of 2,724, FREE 4** (send +9, reverb
   +19 — A is now effectively FULL; next words come from the delay-side
   LFO-block roll or not at all); payload B 771 → **845, FREE 1,879**;
   cycles 777 → 770/sample room (stage 1's wrap had already taken 819 →
   777). ⚠️ Surfaced, pre-existing, NOT fixed here: the delay's `→VERB`
   send is an unregistered full-scale writer into the REVERB accumulator,
   so the reverb's auto-gain gives it an effective ×8/N_sends — ×8 when
   one SEND is registered, ×1 with none. Belongs to the `→VERB` voicing
   pass; noted in XBUS.md's ledger entry.
   ⚠️ New trap instance, caught by the `$30000` census guard: a MODE
   override of 3 << 16 SPELLS `$30000` — the payload-A base literal — and
   the blanket payload substitution would rewrite it to `$38000` (mode
   0x38). Both `MODE=` and `DMODE=` now emit DECIMAL immediates
   (build_bus.py); for the reverb this was latent-only since the HALL cut
   capped MODE at 2.
2. **PITCH** — dual crossfaded lerp heads on the feedback tap, interval as
   a low-byte SELECT: +12 / +7 / −12 / ±detune 🟡 (~200–300 words,
   ~60–100 cycles). Each repeat shifts; through the reverb this is the
   Crystal/Hedra territory.
   ✅ **LANDED 12 Aug 2026 (late) — ear pass pending.** MODE 1 = PITCH:
   per line, a Q11.12 age accumulator (persistent, wraps mod 2048 samples)
   plus two heads a half-window apart reading the DELAY LINE ITSELF at lag
   `min(TIME,14335) + age` — no separate shift buffer exists or fits (both
   line buffers fill the half-window), and line-reading is the topology
   GRAIN inherits. Window was shimmer v3's verbatim (age-trapezoid 640/256,
   smoothstep, silent upper half — two copies not four) ❌ **replaced by a
   full-overlap crossfade in `e6f5359`, see the ear pass below**; reads are
   lerped
   (frac = age's low 12 bits); shifted taps land in $79/$7a so TONE, PING,
   FDBK, MIX and →VERB are mode-blind — every repeat re-shifts (the climb
   is the point here, unlike the reverb's cascade cut). Steps: +12=+$1000,
   +7=+$800, −12=−$800, det=±$24 (±15.2 cents, L up / R down — the one
   select where the lines differ). **Descriptor landed with it** (the
   stage-1 rule): MODE select count 2 (slot 7), PTCH select count 4
   (slot 9, companion low byte); defaults 0/0, in range; `DINT=n` local
   override mirrors DMODE. **Measured:** 438.75 Hz in → +12 ladder
   869/1731/3453/6899/13789 Hz (each repeat re-shifted), +7 stacks
   654/977/1472/2205 (1.5ⁿ), −12 descends 223/116/55, detune spreads
   ±15 c around f; ping-pong puts even orders on R, odd on L; splice
   sidebands ±21.5 Hz (window lap rate) at −14 dB. CLEAN bit-identical
   through the dispatch (`verify-delay` vs pre-stage-2 HEAD, 11/11 incl.
   DMODE=3→CLEAN). Every emitted mpy signed (2000c0/c8), abs/neg checked.
   Cost: delay 624 → 1,150 words (→ **1,086 after `e6f5359`**, the
   branchless window being 64 words cheaper); payload B used 845 → 1,371 →
   **1,505 after stages 2b/2c/3/4, FREE ~1,000**; ~450 cycles/sample in PITCH mode only (CLEAN path
   unchanged;
   `cycle_count` now prices the mode fork at its WORST path via MODEFORK
   markers instead of refusing or summing both engines).
   ✅ **EAR PASS RUN 12 Aug 2026 (late), and it FAILED the splice** — then
   one fix landed and one theory was retracted. Sam on the octave ladder:
   "climbed up in octaves and got kind of glitchy metallic". Bisected with a
   single-generation render (FDBK=0, one shifted echo): the dirt is in the
   **shifter itself**, not in the ladder compounding it — which turned the
   question into a measurement.
   - ✅ **FULL-OVERLAP WINDOW (`e6f5359`)**. The trapezoid switches heads
     almost rectangularly: measured splice sidebands every 43.1 Hz in a
     slowly-decaying ladder (−18.7, −20.9, −26.8, −28.3, −33.4…). Replacing
     it with a complementary triangle + smoothstep collapsed the higher
     orders 20–25 dB (first pair −18.7/−20.9 → −26.0/−33.7) and is
     **branchless: −64 words**. Ear: "bit better", still "robo".
   - ❌ **WIDENING THE WINDOW 4× IS RETRACTED** (built and reverted the same
     evening). The theory — that the residual pair and the carrier offset
     were a lattice displacement scaling with window length — is falsified:
     at **every** window length the octave arrives as **two equal lines one
     lap apart with nothing at 2f**. That is suppressed-carrier AM: the two
     heads sit half a window (93 ms) apart on the line, so a steady
     partial's relative phase between them is fixed (158° here) and they
     cancel once per lap. Widening only moved the cancellation 43.1 → 10.8
     Hz — buzz became flutter ("robo and fluttery") — and cost half the
     PITCH delay range. A ramp sweep at C=8192 (R=512/1024/2048/4096)
     showed the trade is 1-D with no good point: ripple 6.3/10.3/12.6/13.5
     dB against off-carrier energy −8.7/−10.3/−14.5/−35.6 dB. On melody the
     two extremes read as "twinkly robot" and "artificial".
   - ✅ **STAGE 2b, GRAIN JITTER — LANDED (`cf5d73a`)**, ear "a bit less"
     robo. The defect is **periodicity**, not window shape, so the fix is
     to scatter each grain's source position (0–1023 samples, 23-bit
     xorshift, period 2^23−1) latched at each head's own wrap — inaudible
     because the full-overlap window's gain is exactly 0 there, which makes
     the window fix a **prerequisite** rather than just a cleanup. Measured:
     modulation peak/total −2.0 → −7.7 dB, i.e. the cancellation depth is
     now random per grain instead of identical; the carrier cluster recentres
     on the true octave. +96 words, 11 new r7 slots ($18–$23, the delay's own
     block — not the reverb's full one). `make check` + verify-delay 11/11
     green. This is GRAIN's (stage 5) mechanism with fewer heads and no
     SPRAY knob.
   - ✅ **STAGE 2c, NON-CASCADING — LANDED (`cf5d73a`), and it is the change
     that moved the needle.** Until it, the shifted taps WERE the loop's
     taps, so repeat *n* had been through the shifter *n* times and carried
     *n* generations of splice artifact — that compounding, not the splice,
     is most of what an ear calls "machine" (ChonVerb hit exactly this and
     its shimmer cut its own cascade for the same reason). The loop now
     recirculates the CLEAN tap and the shifter sits on the OUTPUT only,
     substituted into the wet AFTER both lines are written, so nothing
     shifted can re-enter the feedback. Measured at FDBK 60: the +12 ladder
     (869/1731/3453/6899 Hz) is **gone**, replaced by one cluster at the
     true octave. Every repeat is shifted exactly once — a fixed-interval
     harmoniser on the delay output. ⚠️ **The Crystal climb is deliberately
     gone**; if it is ever wanted back it belongs on a select, not as the
     only topology.
   - **The framing this produced, and it is the real result of the session:**
     a Microcosm-style device is not a clean shifter — it is artifacts made
     **dense and aperiodic** until they read as texture, mixed under dry and
     washed into reverb. Judging PITCH naked, dry, full-wet and single-
     interval is the harshest possible exposure of exactly the artifact
     granular design exists to hide. `send_probe.py --dvrbw` now drives the
     delay's `→VERB` send from the CLI so the delay→reverb topology is one
     command.

3. **FREEZE** — 2-state select. ✅ **LANDED 12 Aug 2026 (`6aac927`)**, and
   the sketch's "stop line writes" turned out to be the wrong mechanism:
   the pointers must keep running or the reads stall. What shipped instead
   **substitutes the line write** — while held, each line writes back the
   raw tap it just read instead of `x_in + fb*FDBK`. Read at `wr−TIME`,
   written at `wr`, so the region copies itself forward one lap every TIME
   samples: **the loop length IS the TIME knob**, and the gain is exactly 1
   (a copy, not a multiply) so a frozen line can neither decay nor grow.
   Input, FDBK and PING are bypassed while held; MIX, `→VERB` and the PITCH
   heads keep working, so the dry plays over it and **FREEZE+PITCH is
   shifted reads over held material** — the texture hold. Branchless via
   Tcc (`tne`). Select at page-2 slot 11 (`r6+$e` low, count 2, default
   RUNNING); `DFRZ=n` is the local override.
   **Verified by measurement, not by ear**: with a source that stops before
   the freeze engages, consecutive TIME-length windows are BIT-IDENTICAL
   (max sample diff 0) at constant level across seconds, where the same
   render unfrozen decays to nothing. Cost: 1,267 → 1,287 words (+20),
   ~12 cycles/sample.
   ⚠️ **The knob is UNEXERCISED locally and cannot be**: `dsp_host` cannot
   change a parameter mid-run, so the flag was toggled by a scratch build
   keyed off its own block counter. Slot 11 rides the on-unit reconfirm
   checklist like every other select — the SHMR wrong-offset bug is what
   that checklist exists for.
4. **TAPE** — ✅ **LANDED 12 Aug 2026 (`3fc25ba`)**, MODE 2. Two LFOs
   (phase accumulator → triangle → smoothstep, the window machinery reused)
   sum into a signed sample offset that displaces **the loop's own read**:
   wow ~0.80 Hz, flutter ~7.3 Hz, depth from the new **WOW knob** (page-1
   slot 6, r6+$b). The read is LERPED — an integer-only moving read is a
   zipper, the truncation floor that cost the first shimmer.
   **The modulation is in the LOOP, unlike PITCH's**, so every repeat
   accumulates more drift — and that is safe here in the way PITCH's cascade
   was not: a smooth lag modulation has no splice, so there is nothing to
   compound. **This mode cannot sound robotic for the same reason PITCH
   did.** The two rates are deliberately not in a small integer ratio, so
   they never lock into one mechanical cycle (the periodicity lesson applied
   before it could bite).
   ⚠️ **A bound that is load-bearing, not taste**: wow ≤ 31.75 samples,
   flutter ≤ 3.97, summing to 35.7 against TIME's floor of 64 — so the lag
   can never reach 0 and wrap onto the sample about to be written (a whole
   lap old: a full-scale discontinuity once per LFO cycle). Any depth
   increase must re-check that sum.
   Measured: a 220 Hz burst's tail drifts smoothly on a ~1.25 s cycle over
   roughly ±10 cents, no steps. 39 multiplies in the emitted image, all
   signed. Cost: 1,287 → 1,505 words, 193w on the TAPE path.
   ✅ **LOOP SATURATION LANDED (`44e9b7f`, stage 4b)**: `y = w − w³/3` on
   what each line is about to be written, so it is in the loop and every
   repeat is saturated again. Small-signal gain is EXACTLY 1 and the curve
   is monotonic with |y| ≤ |w|, so it adds no loop gain and cannot
   self-oscillate at any FDBK — unlike a pre-gain clipper, which would also
   fold back above unity. **No DRIVE knob on purpose**, for the same reason
   the LFO depth has a ceiling: the safe version is the one the panel cannot
   knock into a bad regime. Measured with WOW=0 so the wobble's sidebands
   could not be miscredited: THD −24.6 dB at 0.9 FS, −39.5 at 0.3, −41.3 at
   0.1 (= CLEAN's floor, i.e. transparent when quiet); CLEAN flat at −41.4
   at every level. Slot 10 is still free if the ear asks for DRIVE.
5. **GRAIN** — the flagship, and the honest answer to "it doesn't sound like
   a Microcosm": density is the mechanism, not a better two-head shifter.
   ✅ **LANDED 12 Aug 2026 (`23fb336`), AND ITS EAR PASS PASSED FIRST TIME**
   — the only BongDelay mode that has. Verdict (Sam), on his own melody
   source at TIME 40 / FDBK 45 / MIX 110 / +12, level-matched, against a
   CLEAN baseline and a SPRAY=0 control: **"spray killed robo and 127 was
   good as well."** That closes the stage-2 defect with the mechanism it
   was diagnosed for — the "robo" was PERIODICITY, and four grains each
   re-randomising at their own wrap make the cancellation aperiodic. BOTH
   ends of the knob pass, so SPRAY is a character control, not a
   find-the-one-value knob. Round logged in `docs/VOICING.md`.
   The spec below was written before the build and held up; what changed
   in contact with the code is marked.
   - ✅ **THE ROLL IS MANDATORY, not an optimization.** PITCH costs 524
     words for 4 head evaluations (~131 each), so 4 grains × 2 lines
     unrolled is **1,048 words against payload B's 942 free — it does not
     fit.** Rolled, the body is one evaluation (~131 words) plus loop
     overhead: ~150–200 total, run 8×. Precedent: the tank roll and the LFO
     roll.
   - ✅ **N MUST BE EVEN.** With the full-overlap triangle window, grains
     staggered by 1/N sum to: N=2 → 1.0000 (flat), **N=4 → 2.0000 (flat)**,
     N=3 → 0.21 dB ripple, N=5 → 0.03 dB. The even counts are exactly flat
     because the grains pair up complementarily (0&2, 1&3). An odd count
     puts a ripple **at the grain rate** — a periodic amplitude modulation,
     which is exactly the artifact class stages 2b/2c existed to remove.
     Take N=4 and scale the sum by 1/2.
   - **Mechanism**: one shared base age + per-grain quarter-cycle offset
     (so a single age advance serves all four); per-grain scatter latched at
     ITS OWN wrap (stage 2b's machinery, and the window is 0 there so the
     jump stays silent); lerped reads; **output-only, never in the loop**
     (stage 2c). Per-line scatter tables keep L and R decorrelated while the
     window gains are computed once and reused.
   - **What the build changed**: the roll is THREE emissions, not one —
     a builder (`do #4`, fills an 8-record interleaved table) plus one
     reader per line, because a single 8-iteration loop would have needed
     the line base and write pointer staged per record. The table is 32
     words at `$34..$53` (not ~13: 4 words × 8 records), and only the
     eight SCATTERS persist — every other field is rebuilt each sample, so
     boot garbage there cannot survive one sample. Per-grain WRAP
     DETECTION needs no stored previous age at all: `prev = (age + step) &
     mask` by construction, so recomputing it is exact and costs less than
     eight more words. The PRNG was DUPLICATED rather than hoisted —
     hoisting would spend CLEAN's and TAPE's cycles on a number they never
     read, and words are the thing payload B has. `m4` set per block and
     restored at `dry:` as specced.
   - ✅ **Gate extended FIRST (`5277d68`)**, the stage-1 pattern: PITCH
     (+12 and detune) and TAPE (WOW=100, and WOW=127 FDBK=127) are now
     bit-compared too, each with its OWN sensitivity control (the
     reference in that mode must differ from CLEAN, or the case is
     vacuous). GRAIN then landed **21/21 against the pre-GRAIN engine** —
     CLEAN, PITCH and TAPE all bit-identical despite the shifted-output
     substitution being refactored to a per-block flag. The unknown-mode
     fallback moved to DMODE=5, since 3 is an engine now.
   - **Cost, measured**: 343 words (1,561 → 1,904); GRAIN's path is 289w +
     609 of roll = **~898 cycles/sample**, more than double the ~400
     estimate, making it the delay's worst path (834 → 1,211). It fits on
     core 1's ~2,150 🟡 spare and only one DELAY SERVER runs per bank (the
     role lock), so it is charged once — but see the cycle ledger: the
     printed single-core headroom is now NEGATIVE.
   - ⚠️ **The fork's cycle model compared alternatives by WORDS**, which
     was only correct while every alternative was straight-line. It would
     have priced PITCH's size with GRAIN's roll depth. `cycle_count` now
     attributes each roll to the alternative containing it and compares by
     CYCLES; reduces exactly to the old formula when nothing is rolled.
   - ⚠️ **WOW (slot 6) and FRZE (slot 11) WERE NEVER ENABLED.** Stages 3
     and 4 named, defaulted, counted and implemented both and neither was
     added to `ACTIVE_PARAMS` — which IS the panel's enable bitmap, so on
     hardware they would have drawn no knob at all: TAPE's depth and
     FREEZE itself pinned to their defaults with no way to move them.
     `verify_menu` keeps its own copy of the list and was missing the same
     two slots, so it could not see it. The inverse of the PARAM_PAGES
     trap. Fixed here; page 2 is now full and correct — **WOW(6) MODE(7)
     VRBD(8) PTCH(9) SPRA(10) FRZE(11), three knobs and three selects,
     which is the hardware budget exactly.**
   - **Still unheard**: FREEZE + GRAIN (the texture hold) and GRAIN through
     the `→VERB` send (the delay→reverb wash the whole framing assumes).
     Also measured, for the next round and not against this one: GRAIN's
     L/R correlation is **0.00** against the reference granular's **+0.51**
     — ours is WIDER, not narrower. If it ever reads as "no centre" the
     lever is PING or correlating the two lines' scatter, not the window.
   ---
   **Stages 5b–5e, 12–13 Aug 2026 — the voicing pass, driven entirely by
   Sam's ears against a reference granular on his own melody.** Each one was
   a structural finding, not a knob turn, and three of the four came from a
   single sentence of feedback:
   - ✅ **5b, ROLLING INTERVALS (`e7990aa`).** GRAIN applied ONE fixed
     interval, so every repeat came back the same pitch; the reference has
     "musical random sounding pitched repeats". **Decided by measurement,
     against my own recommendation**: I argued for simultaneous per-grain
     intervals; single-series harmonicity said 0.952 dry / 0.780 reference /
     0.806 our fixed GRAIN — four simultaneous transpositions would put the
     reference far BELOW ours, and 0.03 apart says one at a time, varying.
     **Why it works without a cascade is stage 2c's doing and nobody had
     noticed**: the loop recirculates the CLEAN tap while the shifter reads
     the line at TIME lag, so a changing interval means each repeat is
     shifted by whatever is current as it passes the read head — different
     pitches per repeat, no compounding. Rate measured against TIME: 1-in-4
     holds 170 ms = **1.05× TIME**, one interval per repeat; 1-in-8 held 3.5
     repeats ("changing pitch every now and then"), every-wrap changed 2.5×
     WITHIN a repeat (warble). The criterion is hold ≈ one repeat, and it is
     measurable — which is why the right value was derivable rather than a
     taste call.
   - ✅ **5c, MIX CROSSFADES + SPRAY WIDENED (`9491e41`), and a WRONG
     DIAGNOSIS.** Sam: "sounds nothing like a granular, just a slightly
     effected verb". I gave two causes; **one was invented**. I claimed a
     unity dry was swamping it, reasoning from `out = dry + wet*MIX` in the
     source — but send_probe's `-inmask` feeds the SENDS only, so a server's
     own track is silent, MIX=0 renders −240 dBFS and every `--pick D`
     render was ALREADY 100% wet. The real cause was duller: those renders
     were `--pick R`, the reverb's output. ⚠️ What survived is a genuine
     HARDWARE defect — on the unit the effect is an insert and the track
     really carries audio, so the wet could at best EQUAL the dry and a
     texture mode could never dominate. MIX now crossfades, written as
     `dry + MIX*(wet−dry)` so it needs no 1−MIX slot. **And the harness
     could not see it**, so `send_probe --inall` was added (feed every live
     slot): measured dry remaining 100% / 53% / 7.1% at MIX 0/64/127, where
     the old code read 100% at all three. SPRAY went 0..1023 samples (23 ms,
     "a flam, not a cloud") to 0..8191 (186 ms); GRAIN got its own
     SPRAY-derived lag base so range is spent only when scatter is used.
   - ✅ **5d, DENSITY (`9995afb`) — and the flat-sum rule was the defect.**
     Sam: "still a lot more of the melody lines playing". Four grains
     windowed to sum to exactly 1.0 are GAPLESS, so the output is a
     continuously shifted melody, not a cloud of fragments. **The
     N-MUST-BE-EVEN rule was inherited from PITCH, where ripple was the
     defect, and is exactly wrong here: in a granular THE GAPS ARE THE
     TEXTURE.** Grains now drop out, decided at their wrap. DENSITY is the
     WOW knob (TAPE-only, so GRAIN reuses it — the same dual meaning
     REVERSE gives PTCH). Measured: rms −9.4 dB and near-silent 10 ms
     windows 0% → 13% across the knob.
   - ⚠️ **AND 5d SHIPPED A BUG THAT AN EAR CAUGHT IN ONE PASS** — see the
     new trap in CLAUDE.md. Both scatter latches test ONE `N` flag from the
     wrap comparison and had been separated by nothing but moves; the
     density gating put `clr`/`tst` between them, so line R re-scattered
     EVERY SAMPLE. A read position that jumps every sample is broadband
     noise: Sam heard "a noise wash on the right" immediately. R's zcr
     10888 → 744 against L's 739 once the flag was parked and restored.
     ⚠️ **And I misdiagnosed it first**, concluding "this predates today's
     changes" from a bisect in which every point was built from the CURRENT
     source. A bisect that does not vary the thing it claims to vary is not
     a bisect.
   - ✅ **5e, THE SCHEDULE/RATE SPLIT (`265d409`) — the grain core
     redesigned.** Sam: "still jumping around in a not very musical
     fashion". Narrowing the interval set helped "somewhat"; the rest was
     structural. ONE accumulator drove both the window envelope and the read
     position, which forced three things at once: every grain shifted by the
     same interval and they all jumped TOGETHER (a step, not a morph);
     **UNISON WAS STRUCTURALLY UNREACHABLE** (rate 1.0 means the age never
     advances, so the grain never wraps and never re-scatters — the set had
     no unison in it because it COULD not, and "mostly at pitch, some
     shifted" is most of what makes a cloud musical); and grain SIZE was
     welded to the pitch ratio. Now a schedule phase drives only the
     envelope while each grain accumulates its own read offset at its own
     rate. Record `[rate, mute, offset, gain]` × 8 = **exactly the 32 words
     the old table used**, so a core redesign cost no r7 space. The offset
     is Q14.9 and carries its own lerp fraction — with per-grain rates there
     is no shared sub-sample position. ⚠️ **Load-bearing bound**: a +12
     grain traverses 2048 samples over its 2048-sample life, so the offset
     resets to 2048 + scatter and the lag ceiling subtracts 3072; at full
     SPRAY GRAIN's max TIME is ~116 ms. Select 0 pins every grain to +12,
     the nearest thing to the pre-split engine, kept reachable for A/B.
   - ✅ **EAR PASS ON THE SPLIT, 13 Aug: "yeah it was good" (Sam).** The
     direction is settled; GRAIN's mechanism is done. What remains on it is
     voicing (defaults, set weighting, grain SIZE) and COST.
   - ✅ **5f, OPTIMISATION PASS (`ce31594`): 1,931 → 1,595 cycles/sample,
     BIT-IDENTICAL.** The rolled builder was doing four times a sample what
     it needed to do once. Three invariants lifted — the candidate rate, the
     candidate mute per line, and the offset's reset form per line — all
     reading only per-sample-constant state, so all four iterations computed
     identical values. Correct for a second independent reason worth
     keeping: the grains sit at exact quarter offsets of the schedule, so
     their wraps are 512 samples apart and **at most one grain wraps per
     sample** — one candidate is all that can ever be consumed. Plus the
     wrap flag moved to y0 (a register restore is a word cheaper at each of
     six sites). Builder body 234 → 127 words; margin on core 1 **9% → 24%**.
     ⚠️ **Not taken, and priced so nobody re-derives it**: grains 0/2 and
     1/3 have complementary window gains, so two smoothsteps would do
     instead of four — but it needs the loop restructured to 2 iterations of
     2 grains, saving ~60 cycles for ~100 words against payload B's 143.
     A bad trade until words appear.
6. **REVERSE** — ✅ **LANDED 12 Aug 2026 (`2cb04a7`), MODE 4**, and the
   estimate held: **174 words**, the cheapest mode, precisely because the
   crossfade machinery already existed. Two complementary heads half a
   segment apart, windowed and smoothstepped so g0+g1 == 1 exactly and each
   restart lands where that head's gain is 0.
   **THE READ IS EXACT — the only moving read in the file that is.** The
   segment-local index is `p = phase*S/2^23`, which is what a fractional mpy
   of the phase by S computes, so p advances by exactly 1 per sample and
   every read lands on a whole sample: NO LERP, where PITCH and TAPE both
   need one. That is also why **S must be a power of two** — the phase step
   is 2^23/S and only a power of two makes it an integer.
   `read = wr − (LAG0 + 2p)`; the 2 is the write pointer running away from
   the read at 1 sample/sample, so the address decreases by exactly 1.
   ⚠️ **The size ceiling is the LINE, not taste**: playing S samples
   backwards takes S samples during which the write advances S, so the
   buffer must hold 2S of history and a 16,384-word line caps S at 4096
   (93 ms). SIZE reuses the PTCH select (4096/2048/1024/512) — one select,
   two meanings, because MODE already says which is in force and page 2 has
   no spare slot. Output-only (stage 2c): a reverse read HAS a splice, and
   recirculating it would compound one per repeat.
   **Verified by measurement, not by "it makes sound"**: a 200→4000 Hz chirp
   with a silent tail, TIME high so the tail is pure wet — CLEAN's tail
   rises monotonically (15 rising 10 ms steps, 2 falling), REVERSE falls
   within each segment and jumps up at the boundary (13 falling, 8 rising),
   a sawtooth no forward read can produce, period ~46 ms = half the 93 ms
   segment, which is the two heads swapping dominance.
   ⚠️ **r7 IS NOW FULL**: `$62` was the last free slot ($32..$62 fully
   allocated; `$84+` hangs the unit). REVERSE reuses GRAIN's per-sample
   scratch, sound only because the mode alternatives are mutually exclusive
   within a sample. **A seventh mode needs the Y state table, not r7.**

All costs 🟡 inferred from shipped analogues (shimmer 130 words, gate ~104
cycles); price each stage by the build report when it lands, and stop
adding modes when the ear says the box is full, not when the words run out.

**Stage 1's refactor gate is now permanent tooling**: `make verify-delay
CAND=<file> [REF=<file>]` proves any future delay engine bit-identical to
the shipping one, with the same two controls as `verify_roll` (a blind
harness and a placement-lucky candidate both fail loudly). `DLSRC=` swaps
the delay source per build exactly as `RVSRC=` does the reverb's.

**PAGE 2 IS FULL, and three slots carry two meanings.** As of stage 5e the
delay draws every slot the hardware allows — three knobs and three selects,
which is the budget exactly (DSP.md section 9):

| slot | field | CLEAN / PITCH / TAPE | GRAIN | REVERSE |
|---|---|---|---|---|
| 6 | `$b` knob | WOW (TAPE depth) | **DENSITY** | — |
| 7 | `$c` high | MODE — CLEAN / PITCH / TAPE / GRAIN / REVERSE (count 5) |||
| 8 | `$d` knob | →VERB DRY |||
| 9 | `$d` low | PTCH interval | **interval SET** | **SIZE** |
| 10 | `$e` knob | SPRAY (scatter depth) |||
| 11 | `$e` low | FREEZE |||

Dual meanings are deliberate: MODE already says which is in force, and a
knob that does nothing in three modes is worse than one that does something
in all five. ⚠️ Every one of these rides the on-unit reconfirm checklist,
and **six of them have never been touched on hardware** — WOW, SPRA and
FRZE were only enabled on 12 Aug (they had been named, defaulted and
counted but left out of the enable bitmap, so they drew no knob at all),
and MODE is a 5-way select where the unit has only ever seen a 3-way.

**Parameters — no new UI mechanism.** Everything is the existing knob-page
descriptor system (MODE-as-stepped-select is shipped tech: ChonVerb MODE,
WIDTH/→DEL selects). Today: TIME p0, FDBK p1, TONE p2, PING p3, MIX p4,
VRBW p5, VRBD p8. Free: knob fields 6/7/9/10/11 plus low-byte companions.
Proposed: **MODE** (select), **PITCH interval** (select — near-boolean
knobs read badly on hardware, the WIDTH lesson), **SIZE** (grain/window
knob), **SPRAY** (knob), **FREEZE** (2-state select). ⚠️ Every new slot
rides the on-unit reconfirm checklist — a slot can draw a knob and publish
nothing, and dsp_host pokes r6 so publish gaps are invisible locally.
⚠️ Selects need their descriptor fields exact (the PARAM_PAGES.md
sequencer-stall trap).

**Traps this design walks past** (all documented, none new): mpy operand
order for any new multiply whose second operand can go negative —
disassemble every new mpy site; grain envelopes and freeze switching via
Tcc, never hand-rolled sign masks (A2 staleness); no new label may prefix
an existing one; recirculating pitch reads sit on the truncation floor —
lerp mandatory, judge wet-only early; the hatch had 69 words of margin and
stage 1 spent 45 of them — closed the same evening by the DEV placement
change (delay at P:0x04000, out of region): the render loop now carries
payload B's full budget, so no stage outgrows it.

**What is deliberately OUT of v1**: Microcosm's phrase-looper/slicer layer
(a product in itself), multi-tap rhythm patterns (cheap, add later if the
ear asks), in-loop diffusion (redundant with the reverb until proven
otherwise by ear).

Traps, all already paid for once:
- ⚠️ **`→DELAY` and `→REVERB` are SEPARATE knobs** (`x:(r6+0)` vs `x:(r6+1)`).
  Driving the wrong one renders silence.
- ✅ **The DELAY accumulator auto-gain LANDED 12 Aug 2026** (the gated
  measured commit after stage 1 — see 3.1). Every DELAY-bus writer registers
  in `$985/$986` and writes `asr #3`; the delay divides by the count (1/N
  table at `$988-$98f` in the bus scratch) and shifts back. Measured: 1–7
  sends all render −26.1 dBFS / −36.1 dB THD where before, 7 sends hit the
  rail at −10 dB THD; single-send is level-identical. The gain lives in the
  delay's own `r7+$7f`, alone (the `$0c` lesson).
- ✅ **X/Y/P aliasing in the shared window is SETTLED — they DO alias**
  (`docs/CHIP.md`, alias probe build 27). Lay out BongDelay's memory map
  knowing X:0x30000 and Y:0x30000 are the same storage.
- **AGU modulo is no longer mandatory.** A manual compare-and-wrap is ~4-6
  cycles/sample — the only way to a single 1.49 s line.
- ✅ **Local render path RESTORED 12 Aug 2026 (evening): `make render-delay`.**
  Two traps closed the same session: `make render`'s `SPEC=1` dump has NO
  delay (id 0x06 → SEND alias; `send_probe` now dies on it), and the DEV
  delay must live at its shipping Y base 0x38000 — payload A's half of the
  window is fully owned (ChonVerb buffers 0x30000/0x34000, bus scratch
  0x36000). See the `→VERB` item above.
- ✅ **The hatch cap is GONE — DEV placement change LANDED 12 Aug (late
  evening), stage 2's opener.** History, kept so the numbers can't
  un-retire: `DEV=1 XBUS=1` alone overran the region by 153 words after
  R16–R18, `NOSHIM=1` bridged it for a few hours, and stage 1's +45 left
  24 words — the ~583-word in-region cap was effectively reached. Now the
  DEV delay assembles at **P:0x04000, outside the donor region entirely**
  (`build_bus.py` DEV_DELAY_P): dsp_host has NO 8K P wall (flat 0x80000
  words, no OMR model — measured 12 Aug), the payload has no room for a
  new module record (6 bytes of slack, measured), so the record is
  **appended to the .mem dump**, which is the only thing dsp_host boots.
  The DEV image carries a dangling dispatch to 0x04000 — one more reason
  it is never flashed; on hardware the delay ships in-region in payload B,
  unchanged. Verified: in-region vs relocated bit-identical (3 corner
  renders), full verify_delay 11/11 vs v1 through the new flow, THD
  −36.8 unchanged. Consequences: the delay's render budget is payload B's
  full 1,953, NOSHIM is optional again (full-shimmer hatch 2,692 of 3,053,
  FREE 361 — a truer downstream sink for →VERB listening), and OMR stays a
  hardware-only lever for a delay past 1,953 (asymmetric core-1 Fig 3-3 is
  the variant that costs no tank lines).
- ⚠️ **`make bus-plain` no longer builds at all** (12 Aug evening): the
  no-flag layout packs SEND + full-shimmer reverb + delay into one
  2,724-word region and overruns it by 506 words (3,230; it was already
  over at 3,185 BEFORE stage 1's +45 — this broke with R16–R18's growth,
  not with v2, and nobody noticed because nothing exercises it). Distinct
  from verify_burn's 2,794-word skip, which is the BURN probe layout.
  XBUS/SPEC (`make bus`) and the hatch (`make render-delay`) are the live
  configurations; treat bus-plain as historical unless something needs it.
- Current parameters (`build_bus.py`): `TIME` p0, `FDBK` p1, `TONE` p2,
  `PING` p3, `MIX` p4, `VRBW` p5, `MODE` p7 (select, count 2), `VRBD` p8,
  `PTCH` p9 (select, count 4), `FRZE` p11 (select, count 2, stage 3),
  `WOW` p6 (knob, stage 4) — **11 of 12 used** (MODE's count is now 3:
  CLEAN/PITCH/TAPE), and the parameter-delivery gap (step 2) caps how many more
  are worth adding. ⚠️ Both new selects ride the on-unit reconfirm checklist — a slot
  can draw a knob and publish nothing, and dsp_host cannot drive companion
  fields at all (`DMODE=`/`DINT=` are the local overrides).

### 4. FX1 consolidation — turning 12,288 stranded words into capability

The trick ChonVerb already ran: replace near-duplicates with one engine plus
a MODE select.

| cluster | stock | one engine | freed **per payload** |
|---|---|---|---|
| PHASER + FLANGER + CHORUS + COMB | **1,052** | ~400-500 🟡 | **~550-650** |
| EQUALIZER + DJ EQ | **627** | ~300 🟡 | **~325** |

All four in row 1 are the same structure — a short modulated delay with
feedback — and the effects most in need of a 2026 rewrite. **FILTER is the
outlier**: 727 words, the default FX1 effect, ~260 cycles (a large fixed
per-call overhead, `docs/CHIP.md`). Highest value, highest risk.

⚠️ The real FX1 ceiling is **cycles ×4 per core** (see the ledger), and only
the `BURN=1` hardware sweep re-measures the spare. Sequence FX1 ambition
after that trip.

✅ Taking the three reverbs cost FX1 nothing — they were never on its menu
(both chooser lists decoded 8 Aug). FX1's ten effects are the whole pool.

---

## The hardware trip — HAPPENED 9–10 Aug, diagnostically, and mostly paid off

The trip was forced early by the "R13 is dead" chase (three flashes: R13,
the MrkVerb32 marker probe, R14) rather than gated on "excellent" — but it
delivered most of the checklist. Status per item:

1. ✅ **v121 auto-gain with the `$0c` fix is on the unit** (R14). The
   >3-sends break should be gone — worth one deliberate multi-send test.
2. ✅ **The 8-line engine runs on hardware, decays as voiced by ear**
   (10 Aug). ⚠️ The *numeric* RT60 sweep against local renders is still
   worth one knob pass — "sounds as voiced" makes the 2×-off mpy scenario
   very unlikely but has not measured it.
3. ❌ **`BURN=1` probe missed the trip and is RE-BLOCKED (11 Aug)** — the
   10 Aug LFO roll briefly made `verify_burn` pass, then R16–R18 growth
   pushed the plain layout over the region (DELAY SERVER 2,794 > 2,724, 70
   words). FX1's cycle budget remains unmeasured until words are found and
   a flash carries the probe.
4. 🟡 **Parameter-delivery — 10-Aug finding CHALLENGED, 10 Aug.** The trip
   reported page-2 continuous slots (SHMR/DIFF/WIDTH/PRE/→DEL) pinned at
   defaults, MODE (a select) working — read as "the §2 split confirmed."
   A same-day investigation could not reproduce any gate: the cloned
   descriptor is byte-for-byte equal to **stock DARK REV's** working page-2
   knobs (count 128, `P+0x12a`=0x40032814, enable 1); the DSP engine
   responds to every page-2 value poked into r6 (dsp_host sweeps); the read
   code is unchanged since 4 Aug; and `DSP.md` §9 recorded these five knobs
   "confirmed by ear and eye" on 4 Aug — a direct contradiction. Both
   descriptor-level fix-theories (`0x12a`, count) are falsified by stock.
   **Page-1 knobs publish and work** (Sam: "just need tuned" — voicing, not
   delivery). ✅ CLOSED same trip: the per-knob reconfirm ran on-unit 10 Aug
   (MODE stepped, PRE swooshed, DIFF/WIDTH moved; SHMR/→DEL silent for
   DSP-read reasons fixed in R16). The "pinned at defaults" observation was
   a misread from the chaotic trip; page-2 publishes. See step 2.
5. ✅ **Shimmer depth publish — cause found, fix built (unflashed).** SHMR
   was silent on-unit because the DSP read `$b` while the panel publishes
   `$c`'s knob field — a wrong read offset, not a publish gate. R16 reads
   `$c` OR `$b`; on-unit confirm rides the tag-37 flash checklist (step 2).
6. ✅ **Tag discipline restored** — BUILD_TAG was stuck at 31 across both
   working and dead flashes (exactly the ambiguity it exists to prevent,
   and it cost this trip a session); now 33, bumped per wrap. Card
   workflow: cp → cmp → rm-old → sync → eject, kill `._` sidecars.

**New, from the trip itself:** the track↔core inversion (see Start here);
the MARKER=1 staged-audible-marks mechanism (committed, reusable — point it
at BongDelay next); and MIX-at-100% loudness, queued as a voicing item.

**Legacy-project FX2 ids — checked 10 Aug, closed by analysis (one 🟡).**
A saved project can still dispatch a stock FX2 id the replaced chooser no
longer offers. "Alias them all to SEND" does NOT work: `X:0x215/0x235`
serve FX1 and FX2 from the same entries (measured, `DSP.md` — id source
`r6+$1b` vs `$1c` is the only difference), so aliasing would break those
effects on FX1 — the donor null-stub design exists precisely because of
this. It is also unnecessary: every big-buffer stock FX2 effect is already
handled (three reverbs null-stubbed, Echo Freeze dispatch is the stock
no-op passthrough). The survivors are dual FX1/FX2 shallow effects
(dynamics/EQ class) — 🟡 *inferred* to make no FX2-slot buffer writes.
Falsifier: legacy project, COMPRESSOR stored on an FX2 slot of tracks 5–8,
listen for tank corruption while ChonVerb plays. If that ever fails, the
fix is ColdFire-side id sanitization at publish, not the DSP tables.

`Y:0x34000` is not part of this trip: ❌ retracted 8 Aug, falsified by our
own v107 bisect (`docs/CHIP.md` §6).

---

## Retraction ledger — kept so the numbers cannot un-retract themselves

Full narratives live in VOICING.md and the commit log; these are the claims
that must not come back:

- ❌ "Tail confirmed non-zero, 7.90 s to −60 dB" — measured a **divergence**;
  the metric scores a rising tail as a magnificent one. Per-second envelopes
  only.
- ❌ "ROOM's ER prominence is voicing, not a fault" — it was a fault (six-tap
  flutter echo); ER is **removed**, the short input diffuser replaced it.
- ❌ "The engine is grossly nonlinear (−21.8 dB)" — single point of a curve;
  swept, it is linear below −6 dBFS with a clip knee in the top ~4 dB. (This
  retraction itself retracted an earlier "saturation ruled out" — the sweep
  is the arbiter, both one-liners were wrong.)
- ❌ "Cycle spare is 1,392 for new work" — that spare was measured on a
  964-cycle bank; `cycle_count.py` now subtracts bank growth (819 as of 11 Aug).
- ❌ "Y:0x34000 is a blocker" — falsified by our own v107 bisect.
- ❌ "PLATE confirmed clean by A/B" (8 Aug) — PLATE was unreachable; the mode
  dispatch compared MSB-aligned short immediates and modes 1-2 fell through
  to BIG. Fixed `2da90f0`.
- ❌ "Per-line decay gains are free and provably stable" (9 Aug spec,
  `7d1dd0b`) — built and falsified the same day: the 0.5 anchor was not
  neutral. Working now (third attempt, anchor 1/√8) — see 1.1.
- ❌ "Per-line asymmetry self-oscillates the unnormalized H8 tank; normalize
  the FWHT first" (9 Aug, `5d91a94`) — retracted the same day it was
  written. Its "proven-stable uniform 0.4336" control was a DERIVED `$1e`;
  the measured one is 0.3251, and uniform 0.42 explodes exactly like the
  asymmetric builds. Root cause of the whole cascade: **"mpy doubles" is
  false in this toolchain** (measured, three-point exact) — the multiplier
  is the stored word itself and the tank was norm-stable all along.
- ⚠️ Standing hardware caveat from the same finding: if silicon's fractional
  mpy DOES shift left where the emulator's does not, every decay constant is
  2× off on the unit — the 8-line has never been flashed; check decay times
  first thing on the BURN trip.
- ⚠️ Standing correction, same family: post-8-line multi-send renders before
  9 Aug had auto-gain clobbered by `$0c`; the unit has never had auto-gain.
- ❌ "The PITCH splice artifact is a lattice displacement that scales with
  window length; widen the window" (12 Aug, built and reverted the same
  evening) — falsified by its own measurement: at EVERY window length the
  octave arrives as two equal lines one lap apart with nothing at 2f
  (suppressed-carrier AM from the two heads' fixed relative phase), so
  widening moved the artifact 43.1 → 10.8 Hz (buzz → flutter) and cost half
  the PITCH delay range. The defect is periodicity, not window shape. The
  full-overlap window fix from the same session stands (measured, `e6f5359`).
- ❌ "BongDelay produces zero output in every layout; →VERB unconfirmed
  either way" (12 Aug morning, `7a2859c`) — the dump was a `SPEC=1` build
  in which the DELAY id is aliased to the SEND client; every "delay"
  measurement that morning instantiated a SEND. Retracted the same day by
  the disassembly the entry itself called for (dispatch entry DELAY ==
  SEND). The delay code was never in the dump; nothing about the delay was
  measured. →VERB is now CONFIRMED in the emulator (step 3).
- ⚠️ Standing correction from the same session: every pre-12-Aug DEV-hatch
  delay render (incl. `2f35107`'s numbers) ran the delay at Y:0x30000,
  where its LineR write pointer swept the bus scratch and ChonVerb's
  relocated buffers every 16,384 samples. Single-server DS layouts survived
  it (measured THD −35.2 vs −36.8 clean); multi-server layouts did not.

---

## Open, and unchanged by any of this

- **Duplicate instances of one effect corrupt audio after ~5.45 s**, any
  address, mechanism unestablished. One server per bank is a design rule; no
  product configuration has this.
- **Payload B's "609 free above code" has never been loaded** 🟡 — verify
  before spending it.
- **Emulator/device gap, parameter delivery** — step 2's protocol closes it.
- **Emulator/device gap, per-core layout** — ✅ closed 8 Aug (`make render`
  builds `SPEC=1`; dsp_host boots payload A, so the reverb renders
  identically to hardware) and ✅ the delay half closed 12 Aug: `make
  render-delay` renders BongDelay at its shipping Y base 0x38000 — and
  since the 12 Aug placement change with the full-shimmer reverb, no word
  cap, and no NOSHIM (the delay runs from P:0x04000 via the .mem dump;
  step 3).

---

## Build commands

```sh
make bus                    # specialized, cross-core -- THE image
make bus-plain              # both servers on both cores
make render                 # build DEV + render the bus locally, no flash
make burn                   # cycle meter on p3
make image BUILD=002        # repack as a flashable .bin, version-stamped

make check                  # bus + cycles + verify, everything without hardware
make cycles                 # per-effect cycles against the measured budget
make verify                 # ColdFire menu tables; burn probe inert when off
make reverb IN=loop.wav ARGS='--sweep SIZE=0,64,127 --wet'
make verify-delay CAND=dsp/delay_new.asm   # bit-identity gate for delay refactors
```
