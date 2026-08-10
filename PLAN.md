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
| On the unit | **`OCTABAMR14`** (tag 33) — 8-line ChonVerb w/ bloom + shimmer v3, SPEC, XBUS, auto-gain w/ `$0c` fix. **Hardware-confirmed as voiced, 10 Aug** |
| Where effects live | ChonVerb on **tracks 5–8** (5 = position-0 housekeeper), BongDelay on **tracks 1–4**, Send anywhere ✅ measured |
| Reverb | eight-line, confirmed on hardware. Remaining work is voicing residue + the knob-publish gap below |
| Delay | **`delay_server.asm` (514 words) has never knowingly executed on hardware or in any emulator** — payload B cannot boot in `dsp_host`. Prime suspect for the 9 Aug stall. Treat as unwritten until its first deliberate run |
| Flash gate | **Passed/overtaken** — the diagnostic trip flashed R13-equivalent and Sam confirmed "working as voiced". The "excellent" bar below still governs *voicing* sign-off |
| Next | page-2 publish decision (fix path vs cut slots) → **BongDelay first deliberate run** → voicing residue (page-1 knob tuning, PLATE ear pass, TIME→decay refit, wet makeup gain, shimmer decision) |

⚠️ **10 Aug hardware findings:** (1) ✅ measured — **page-1 knobs publish
and work; page-2 continuous slots do not** (SHMR/DIFF/WIDTH/PRE/→DEL pinned
at their deliberate defaults; MODE, a select, works). Decision open: fix
the page-2 publish path vs cut dead slots. (2) Page-1 knob feel needs a
**tuning pass** against the R13 engine (ranges/curves — Sam, 10 Aug).
(3) MIX at 100% is much quieter than dry — inherent (wet spreads the same
energy over seconds; the straight crossfade measured −7 dB) and now has
ear evidence; queue a **wet makeup gain** voicing pass. Cheapest form is
~1 word (`asl` on the wet path) but payload A has 4 words free.

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
  free (region)     178 (LFO roll, 10 Aug)    1998
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

✅ Region numbers re-measured 10 Aug 2026 (post-LFO-roll build): **payload A
used 2,546 of 2,724, FREE 178** — the LFO-block roll landed 10 Aug (lines
2–7 in one loop over a 24-word P table, proven bit-identical against the
unrolled engine incl. a 600-block MOD=127 A/B; the session's lesson is the
m5 line-modulo invariant, documented at the roll site). **Payload B used
726, FREE 1,998.** `verify_burn` PASSES again — the BURN hardware sweep is
unblocked, and the wet-makeup words exist now.

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
  words**, costing `Y:0xA000-0xBFFF`. Patches the boot path. 🟡 Also the only
  known route to a local render of the delay (see the DEV note below).
- **Code in the shared window**: P/X/Y alias at `0x30000-0x3FFFF` ✅ and stock
  already runs code there ✅, so up to 64K is program-addressable at 1 wait
  state. 🟡
- FX1 consolidation (step 4) frees ~550–650 per payload as a side effect, but
  is its own project, not a lever to pull for the reverb.

### Cycles — NOT the constraint, per core, 4,535/sample

✅ 1,392 spare measured 7 Aug 2026 on a 964-cycle bank **with four FX1 FILTERs
already running** (worst case, no derating needed). `make cycles`, 9 Aug:
bank is now **1,334** (reverb 1,133 + delay 163 + 2 sends), growth 370 since
the measurement, so **room for new work: 1,022 cycles/sample.**

⚠️ **FX1 cycles are paid ×4 per core.** A 300-cycle FX1 effect costs 1,200
cycles/core — which does not fit in 1,022. *This*, not program space, is the
ceiling on FX1 ambition. Only a re-run of the burn sweep re-measures the spare
itself; the probe builds again (✅ 9 Aug, `make check` green) and flies with
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
~60–70 of payload A's 95 free words, plus sample-loop cycles.

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
  if the ear asks for it — costs a few words per mode, A has 154.
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
  delay. Deliverable: a written per-slot on-unit test (drive each knob,
  observe a slot-keyed audible change), executed during the flash trip.

### 3. BongDelay — the delay you can route

**Second, unchanged in rationale: the only thing that can spend payload B's
~2,600 words, and the one feature the machine has never had — but it competes
with nothing, so nothing is lost by finishing the reverb first.**

✅ **The stock delay is DOWNSTREAM of the FX2 insert** (measured by ear,
`fcf22fd`) — its output can never be tapped. **delay→reverb exists only
through BongDelay's `→VERB` cross-send**, already built. That is the goal.

Budget: **1,998 program words**, **~3,200 spare cycles**, **65,536 words =
1.49 s**. A flagship budget: multi-tap, ping-pong, per-tap filtering, tape
wow/flutter, diffused feedback, reverse.

Traps, all already paid for once:
- ⚠️ **`→DELAY` and `→REVERB` are SEPARATE knobs** (`x:(r6+0)` vs `x:(r6+1)`).
  Driving the wrong one renders silence.
- ⚠️ **The DELAY accumulator has no auto-gain.** Build it in from the first
  draft — the reverb's `$0c` collision shows what happens when it is bolted
  on and shares state loosely. Same 1/N table, same parity indexing.
- ⚠️ **X:0x30000 vs Y:0x30000 aliasing is unresolved risk under BongDelay**
  (`docs/CHIP.md`) — settle it before committing a memory map.
- **AGU modulo is no longer mandatory.** A manual compare-and-wrap is ~4-6
  cycles/sample — the only way to a single 1.49 s line.
- 🟡 **No local render path**: `dsp_host` boots payload A only, and the DEV
  hatch no longer fits both servers. The OMR lever would bring it back —
  price that against flying blind before deep voicing work on the delay.
- Current parameters (`build_bus.py`): `TIME` p0, `FDBK` p1, `TONE` p2,
  `PING` p3, `MIX` p4, `VRBW` p5, `VRBD` p8 — 7 of 12 used, and the
  parameter-delivery gap (step 2) caps how many more are worth adding.

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
3. 🟡 **`BURN=1` probe missed the trip but is UNBLOCKED** — the 10 Aug
   LFO roll freed the words and `verify_burn` passes again. FX1's cycle
   budget remains unmeasured until the next flash carries it.
4. ✅→🟡 **Parameter-delivery protocol — MEASURED, 10 Aug:** the split is
   exactly as §2 predicted. **Page-1 knobs (p0–p5) publish and work** (Sam:
   "just need tuned" — that's a voicing item, not a delivery one). MODE
   (page-2 *select*) was proven live 5 Aug. **Page-2 continuous slots do
   not publish from the panel** — SHMR, DIFF, WIDTH, PRE, →DEL all pinned
   at their defaults (the SHMR-stuck-at-48 mechanism). 🟡 remaining:
   decide fix-the-publish-path (PARAM_PAGES §3's probe groundwork) vs cut
   the dead slots — several are likely redundant post-R13 anyway, and the
   defaults they pin at were chosen deliberately (DIFF 64, WIDTH 127,
   PRE 0, SHMR 0, →DEL 0), so the engine is fully usable meanwhile.
5. 🟡 **Shimmer depth publish** — SHMR is a page-2 continuous slot, so
   presumed dead on the panel; folded into item 4's enumeration.
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
  964-cycle bank; `cycle_count.py` now subtracts bank growth (1,022 today).
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
  identically to hardware; the delay renders not at all — OMR lever).

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
```
