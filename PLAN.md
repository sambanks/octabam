# The plan: end state, resource ledger, and work order

Written 8 Aug 2026, after a full re-evaluation of where every resource goes.
**This is the cold-start document — read it before `docs/XBUS.md`**, which is now
the *architecture* record rather than the plan.

---

## Start here

The goal is unchanged: **better effects for the Octatrack**. What has changed
is that we now know where every resource lives and what each one can and
cannot be spent on.

| | state |
|---|---|
| On the unit | **`ChonVerb31`** — no specialization, **no v121 auto-gain** |
| Built, not flashed | specialization (`SPEC=1`), bus auto-gain (v121), the `DEV=1` render hatch |
| Reverb | **eight-line, and it is the only engine** — `dsp/reverb_server.asm`. Decays correctly; ER balance per mode is the open voicing item (step 1.2). The four-line source is **deleted**: `git show c1ce08d:dsp/reverb_server.asm` |
| Delay | **`delay_server.asm` is an untested first draft.** Treat as unwritten |
| Next | **Finish ChonVerb**, then BongDelay, then FX1 consolidation |

⚠️ **The unit's current build breaks above three simultaneous sends** — v121
fixed that and has never been flashed. Any hardware trip should carry it.

---

## The principle that decides everything: SYMMETRY

**FX2 bus servers are asymmetric. FX1 inserts cannot be.**

ChonVerb exists only on core 0; BongDelay only on core 1. That is what
specialization bought. But an FX1 insert must run on *any* of the 8 tracks, so
it must exist in **both** payloads — and program space is **per core**.

```
                    payload A (core 0)        payload B (core 1)
                    tracks 1-4                tracks 5-8
  carries           SEND + ChonVerb           SEND + BongDelay
  free (region)     494                       1998
  free (above code) 33                        609  🟡 inferred, never loaded
  ---------------   -----------------------   -----------------------
  spendable on      ChonVerb growth           BongDelay, and NOTHING ELSE
                    + any FX1 work
  FX1 work costs    <-- from BOTH payloads, so capped by A's 527 -->
```

**Two consequences, and they are the whole plan:**

1. **Payload B's ~2,600 words can only ever be spent on the delay.** No FX1
   redesign can reach them. The delay's budget competes with nothing.
2. **FX1 redesign and the delay never touch the same pool**, so there is no
   resource reason to sequence one before the other.

---

## The resource ledger, end state

### Program space — the binding constraint, per core, 8,192 words

✅ Measured 8 Aug 2026 by walking the module map (`tools/dsp_modmap.py`).

| | payload A | payload B |
|---|---|---|
| stock code below the effects | ~2,001 | ~1,455 |
| **10 FX1 effects** (the reclaimable pool) | **3,384** | **3,384** |
| our donor region (PLATE+SPRING+DARK) | 2,724 | 2,724 |
| P code ends at | `0x01fdf` | `0x01d9f` |
| **free above the code** | **33** | **609** 🟡 |

The ten, with sizes (identical in both payloads):

    FILTER 727   LO-FI 537   DJ EQ 345   CHORUS 329   FLANGER 289
    EQUALIZER 282   COMB 277   SPATIALIZER 261   COMPRESSOR 180   PHASER 157

**Untested levers, in order of preference — do not touch until 527 is tight:**
- **OMR memory map** (`docs/CHIP.md` §3): Fig 3-3 doubles P, 8K → 16K, **+8,192
  words**, costing `Y:0xA000-0xBFFF`. Patches the boot path. 🟡
- **Code in the shared window**: P/X/Y alias at `0x30000-0x3FFFF` ✅ and stock
  already runs code there ✅, so up to 64K is program-addressable at 1 wait
  state. 🟡

### Cycles — NOT the constraint, per core, 4,535/sample

✅ 1,392 spare measured **with the full bank plus four FX1 FILTERs already
running**, so it is a worst case needing no derating. 2,432 with FX1 empty.
A stock FILTER costs **~260 each**.

⚠️ **FX1 cycles are paid ×4 per core.** A 300-cycle FX1 effect costs 1,200
cycles/core. *This*, not program space, is the ceiling on FX1 ambition — and
it is what the burn sweep exists to measure.

### Y memory

| | |
|---|---|
| FX2 per server, pooled | **65,536 words = 1.49 s** (2 private slots + half the shared window) |
| FX1 slots | 3,072 each × 4 = **12,288 per core, allocated used or not** |

**FX1's 12,288 words are currently stranded** — only an FX1 effect can reach
them, and stock's inserts use a fraction (a chorus needs ~30 ms of a 70 ms
slot). Owning FX1 turns that into real capability: 70 ms lines per track,
enough for doublers, short slaps, wide chorus.

---

## Work order

### 1. Finish ChonVerb — spend the resources that were not there when it was designed

**Why it moved to first.** ChonVerb was designed against a budget that no
longer exists. Every structural compromise in it — four lines, an unrolled
tank, per-line state crammed into `r7` — was made when program space was the
wall and the cycle ceiling was believed to be 1,080. Both of those turned out
to be wrong, and the reverb is the effect that everything else feeds. It is
currently *good*. The resources to make it excellent are already measured and
sitting unspent.

**Almost all of it needs no hardware**, which is what makes it a sane first
step: the roll, the eight lines and the re-voicing are all built, rendered and
judged by ear locally. The one exception is shimmer's depth control, which has
to be confirmed on a real unit — fold that into step 2's trip rather than
making a flash of its own.

#### The dependency that used to put this last is gone

The old plan sequenced the eight-line tank *after* FX1 consolidation, on the
reasoning that eight lines cost ~450-500 words against payload A's 527. That
estimate looks pessimistic. Counted from the shipping source:

| block | instrs | per line |
|---|---|---|
| four taps, damped inside the feedback path | **101** | ~25 |
| feedback and write-back | **101** | ~25 |
| 4x4 Hadamard | **18** | — |
| *shimmer (excised by default — not in the shipping build)* | *71* | — |

So the tank's per-line work is **~50 instructions**, and eight lines unrolled
is **~+210-235 words** 🟡 — inside payload A's **494 free today**, with no FX1
work required first. The old figure appears to have doubled the whole 291-instr
tank *including the shimmer that is no longer built*.

⚠️ Instruction counts above are exact (counted from `dsp/reverb_server.asm`);
the **word** figure is inferred, because some DSP56300 instructions assemble to
two words. **Falsified or confirmed by the build's own region report** — build
it and read `FREE`. Do not spend this number twice before it is checked.

**Roll the tank first and the question stops mattering.** Rolled, the four-line
tank is ~60 words instead of 202, and **eight lines costs the same as four** —
the line count becomes a loop bound, which is data, not code. That both frees
~140 words *and* decouples the reverb's growth from FX1's pool permanently.

#### The real constraint is now cycles and voicing, not space

Eight lines roughly doubles the tank's cycle cost against **1,392 measured
spare** — comfortable, but it is the number to watch, and it is the same number
FX1 spends ×4 per core. Track it with `make cycles` every pass.

#### The work, in order

1. ✅ **Roll the tank loop** — *the four taps, done 8 Aug 2026.* The read /
   interpolate / damp / low-cut block was four copies of 25 instructions; it is
   now one `do #4` over a per-line state table in absolute Y at `base+0x7f00`,
   six words a line. `r7` is out of the per-line business, which is what makes
   eight lines possible at all — it is full (`$10..$83` used, `$84+` hangs) and
   eight lines want forty state words.

   **2,018 → 1,925 program words, payload A FREE 494 → 587**, at **+15
   cycles/sample** (763 → 778) — the loop pays a little arithmetic for indexing
   that a fixed `r7` displacement got for free. Cheap against 1,392 spare, and
   the point is that the *line count is now a loop bound*, so growing it costs
   data rather than code.

   **Gate met**: bit-identical across all four MODE characters plus the
   `TIME=127 SIZE=127 DIFF=127` wet case, with **two** controls — `HP=0` vs
   `HP=64` must differ (the render responds to a parameter) and one injected
   `nop` must relocate the module and render unchanged (a PASS is about audio,
   not about two builds placing the same). `make verify-roll CAND=...`,
   `tools/verify_roll.py`; `RVSRC=` in `build_bus.py` swaps the engine.

   🟡 **Still unrolled: the feedback/write-back section and the 4x4 Hadamard**
   (~101 and ~18 instructions). Those are *not* four copies of one block —
   lines 0 and 1 carry an in-loop allpass and lines 2 and 3 do not, and the
   input injection signs differ per line — so rolling them is a design
   decision, not a transcription, and **it is what step 2 below actually
   needs**. The natural shape is a per-line parameter row (allpass base, `0`
   meaning none; input sign and scale) read from the same state table.
   ⚠️ `make cycles` now prices a counted inner loop instead of refusing it; the
   `do` setup itself is charged a flat 5 and is still a floor.
2. 🟡 **Eight lines — decays correctly; one defect left, and it is audible.**
   *Structure built 8 Aug 2026; four defects found, three fixed 8 Aug.*
   The engine that was committed as done was **unconditionally unstable** and
   its "measured" tail was a divergence. Re-voicing waits on the output tap
   below — the tank is right, what you hear of it is not yet.
   8×8 FWHT (24 butterflies), 8 LFOs, 8×2048-word lines, per-line state table
   at `base+0x7F00`, Table B at `base+0x7F30`. Now the default engine in
   `dsp/reverb_server.asm`, and **the only** one — the four-line engine was
   deleted 8 Aug 2026 on Sam's instruction ("purge the 4 line completely").
   Recover it, if a reference A/B is ever wanted, with
   `git show c1ce08d:dsp/reverb_server.asm`. ⚠️ The four-line engine is still
   what is FLASHED (`ChonVerb31`); deleting the source did not change the unit.

   **2506 program words, 2718 of 2724 in the donor region — 6 free.** **1145
   cycles/sample** on core A (full bank 1346, 1392 spare). Cycles are not the
   constraint; program space is, exactly.

   ❌ **RETRACTED: "Tail confirmed non-zero (7.90 s to −60 dB ROOM)."** That
   number measured a **divergence**, not a tail. Rendered per-second, the
   committed engine sits near −52 dB for seven seconds, then explodes to
   −11.8 dBFS at second 8 and pins there for as long as you render. 7.90 s is
   when it blew up. The `tail to −60 dB` metric cannot tell a long decay from
   a runaway — it reports the last window above −60 dB **relative to the
   tail's own peak**, so a rising tail scores as a magnificent one. Do not
   accept that metric alone again; read the per-second envelope.

   **Fixed (measured):**
   - **Matrix normalisation.** The 8×8 Walsh-Hadamard has operator norm √8,
     but the four `md_*` decay constants were left at their 4-line (norm-2)
     values, so loop gain was ≈1.41 — unconditionally unstable. All four are
     now scaled by 2/√8. This alone stops the explosion.
   - **Input injection.** v4 injects the diffused input as
     `[+1, −1, −½, +½]`, the signs carried by the *choice* of `add`/`sub` at
     four inline sites. Folding those into a weight table moved the sign into
     the stored constant and every entry was primed **positive**, which points
     the drive straight down the all-ones direction — the Hadamard's own first
     row, the one mode that adds coherently every pass. Lines 4-7 were primed
     to weight **zero**, so half the tank was never driven: an "eight-line"
     tank that was four lines with four parasites. Now
     `[+1, −1, −½, +½, +½, +1, −1, −½]`, sum zero, all eight driven.

   - **Lines 4-7 were never written.** Step 4 advanced the write pointer in
     `a` — `move r5,a / add x0,a / move a,r5` — which is right exactly once,
     for the line 2 → 3 step. From line 3 on, `a` had already been reloaded
     with the `fb` value about to be stored, so `add x0,a` computed
     **`fb + 0x800`** and every write from line 4 onward went to an address
     made out of audio data. Lines 4-7 were still *read* every sample, so the
     tank circulated their frozen click-era contents forever. The address now
     lives in `b`, which is dead there — same instruction count, **zero extra
     words**.

     How it presented, because the shape is worth recognising again: a tail
     flat within 0.5 dB from second 1 to 12, broadband, indifferent to `TIME`,
     `SIZE`, `MOD` and `DIFF`, its *level* tracking the decay constant while
     its *duration* ignored it. It survived replacing the FWHT with the
     identity matrix and survived collapsing the decay gain to 0.15, which is
     what proved it was not the FDN. Autocorrelation of the tail peaked at
     **exactly 2048 samples** — one full line — because a buffer that is read
     but never written replays itself. Confirmed by `dsp_host -peeky`: 0 of 96
     words of line 4 changed between an 11.0 s and an 11.5 s render, against
     96 of 96 for line 0.

   ✅ **Now decays, and the modes are four different spaces.** Wet-only click,
   ROOM: `TIME=0` → −101.8 dBFS at 1 s, `TIME=127` → −86.5 dBFS at 1 s (it was
   −65 flat at every setting). Time to the −105 dB floor: **ROOM ~2 s, PLATE
   ~2.75 s, HALL ~3.5 s, BIG >5.75 s.** No clipping on the wet path; on a
   peak-1.0 source with dry the 8-line clips **576** samples against v4's
   **634**, so the level behaviour is not a regression.

   - **Each output channel carried ONE line, at 8× gain.** The FWHT transforms
     `$16..$19`/`$3a..$3d` **in place**, and the output stage sat *after* it,
     reading those same slots as "line 0..7" with sign patterns
     `L = +−+−+−+−` and `R = ++−−++−−`. Those are rows 1 and 2 of the
     Sylvester H8, and a Hadamard row applied to a Hadamard transform
     collapses it: `pᵀ(H₈d) = 8·d_k`. So **L was 8·d₁ and R was 8·d₂** — one
     delay line each, none of the eight-line averaging the block exists to do,
     and ~9 dB of stray level. v4 is correct only because its Hadamard ran
     inline on `$1a..$1d`, leaving the raw line outputs in `$16..$19`.

     Fixed by **moving the sums ahead of the FWHT** — the output never needed
     the mixing matrix, only the feedback does. Pure reordering, **zero extra
     words**. `y1` (MIX wet gain) stays loaded after the write-back, which
     clobbers it. Wet-only click RMS fell 6.3 dB to −66.5 dBFS, against v4's
     −67.9, and the tail floor came back to −116/−118 dB, matching v4's −116.

   ✅ **Now decays, and the modes are four different spaces.** Wet-only click,
   ROOM: `TIME=0` → −107 dBFS at 1 s, `TIME=127` → −91 dBFS at 1 s (it was −65
   flat at every setting). Time to floor: **ROOM ~1.5 s, PLATE ~2.5 s, HALL
   ~3.5 s, BIG >4.75 s.** On a musical source, wet-only, the 8-line now sits
   **2.1 dB** from v4 in RMS where it was 9.6 dB adrift.

   - **Lines 4-7 duplicated lines 0-3's tap lengths.** All eight read the same
     four MODE fractions `$74..$77`, so the tank had four DUPLICATE PAIRS —
     only four distinct delays, each doubled. Degenerate delays reinforce
     rather than add density, and the tail arrived as a coherent echo train:
     the **stutter** heard 8 Aug. It also means the "modal overlap 0.157 →
     0.31" this whole step was justified by never happened. A source comment
     admitted the shortcut and deferred it to re-voicing.

     Fixed by scaling `x1` **once** before lines 4-7 (one multiply buys four
     new lengths, since every line multiplies its fraction by it). 0.789 is
     chosen to *interleave*: the eight land at 488/571/618/667/723/781/846/989
     samples at SIZE max, every gap ≥47, no pair near a small-integer ratio —
     unlike a factor near 0.5, which would be free but puts every new line an
     octave below an old one. Paid for by hoisting the odd-forcing mask into
     `y1` (freed 10 words, cost 4), which is why the region now has **6 free**
     where it had 0.

     🟡 Still a *derived* set, not a voiced one. Step 1.4 should give lines
     4-7 their own per-MODE constants now that there is a little room.

   🟡 **Remaining, and it is voicing rather than a fault: ROOM's early
   reflections stick out.** Sam, 8 Aug, on a four-clip A/B: the glitches on a
   transient vanish in **PLATE**, the mode with no ER — *"glitches went away on
   4 ... still a bit of a thwack but that's been around for ages and is tuning
   rather than a fault."* The ER accumulator is **byte-identical to v4**, so
   nothing is broken; ROOM's ER level (`$6c` = 0.75, "STRONG") was simply
   balanced against the four-line tank. Two things moved under it: the
   output-tap fix dropped the tank ~9 dB relative to ER, and lines 4-7 now sit
   at 11-18 ms, overlapping the ER taps (4.5-21.3 ms) where v4's lines sat at
   14-22 ms. Re-balance ER per mode in step 1.4.

   **Ruled out** while chasing that, so it is not re-chased: saturation (both
   engines are linear to exact −10 dB steps, click and sustained loop), the LFO
   integer/fraction pairing (lines 4-7 do get proper adjacent pairs `$00/$01`
   … `$06/$07` — worth checking, since a past mispairing was "the loudest
   artifact ever measured in this engine"), and `$5a/$5b` stash-vs-ER-accumulator
   ordering (all eight LFO blocks finish well before the ER accumulator).

   🟡 **DEV=1 render hatch cannot fit both servers any more.** The 8-line
   reverb + send + delay overflows payload A even with the CHORUS donor.
   `render_reverb.py` and `make render` now build with `SPEC=1` (reverb on A,
   delay on B) — dsp_host only boots payload A, so it renders the reverb only.
   The delay's local render path is gone; the OMR memory-map lever (16K P)
   would bring it back.

3. **Shimmer — a new one, from scratch.** The old implementation was heard and
   **it was bad.** It stays excised, and `SHIMMER=1` is a reference for what
   not to repeat, not a starting point. Do not re-enable it and re-voice it.

   It was **71 instructions for a +12 pitch shift inside the feedback path** —
   which is the same story as the rest of this section. It was cheap because
   nothing could be afforded when it was written, and a pitch shifter done that
   cheaply, placed inside a feedback loop where its artifacts recirculate and
   compound, is the metallic sound. That budget no longer applies.

   Two things to change on the second attempt, both now affordable:
   - **Spend real instructions on the shifter itself** — proper overlapping
     windows with crossfaded reads, rather than whatever fits in 71 words.
   - **Reconsider the placement.** Inside the feedback path every artifact
     compounds on every pass. A shifted *parallel send into* the tank gives the
     same rising character without the loop multiplying its flaws.

   Two constraints carry over from the first attempt:
   - ⚠️ **It must be able to reach zero and actually turn off.** The old one's
     depth drew a knob and published nothing, so it ran stuck half-on. That is
     the parameter-delivery item below — a shimmer that cannot be switched off
     is a defect regardless of how it sounds. **Verify the slot publishes on
     real hardware**; `dsp_host` pokes `r6` directly, so every slot looks live
     in the emulator. Fold that check into step 2's `BURN=1` trip.
   - **Judge it at eight lines, not four.** Denser feedback is a different host
     for a pitch shift.

4. **Re-voice all four modes.** Tap ratios and diffusion were chosen for four
   lines; eight changes the echo density that every MODE constant was tuned
   against. `docs/VOICING.md` is the log, and the rule stands — judged by ear,
   level-matched, A/B/A/B, wet-only.
5. **Then spend what is left on quality, not size.** The open items in this
   document are the list: BIG's ringing HF, tank saturation above ~0.35 FS.

#### What "excellent" means here, so it can be called done

Not "bigger". A reverb is finished when a long tail decays without a metallic
signature, when a dense source does not turn to granular hash, and when the
four modes are genuinely different spaces rather than one space at four
lengths. Those are ear judgements, they belong in `docs/VOICING.md`, and they
are the acceptance test — not the word count.

### 2. BongDelay — the delay you can route

**Why it is second rather than first: it is the only thing that can spend
payload B's 2,600 words, and it is the one feature the machine has never had —
but it competes with nothing, so nothing is lost by finishing the reverb
first.** The reverb draws payload A; the delay draws payload B. Sequencing
between them is a choice about attention, not about resources.

✅ **The stock delay is DOWNSTREAM of the FX2 insert** (measured by ear,
`fcf22fd`). Every slot we can reach is upstream, so **its output can never be
tapped**. However good stock sounds, it cannot feed the reverb.
**delay→reverb exists only through BongDelay's `→VERB` cross-send**, which is
already built. That is the goal, and this is the only route to it.

Budget: **1,998 program words** (≈4× its current size), **~3,176 spare
cycles** (≈19×), **65,536 words = 1.49 s**. A flagship budget, not a
placeholder's: multi-tap, ping-pong, per-tap filtering, tape wow/flutter,
diffused or pitch-shifted feedback, reverse.

Traps, all already paid for once:
- ⚠️ **`→DELAY` and `→REVERB` are SEPARATE knobs** (`x:(r6+0)` vs
  `x:(r6+1)`). Driving the wrong one renders silence.
- ⚠️ **The DELAY accumulator never got v121's auto-gain.** Same fix as the
  reverb's; fold it into the re-scope or the bus breaks above three senders.
- **AGU modulo is no longer mandatory.** Power-of-2 alignment is what caps a
  line at 16,384 words; a manual compare-and-wrap is ~4-6 cycles/sample —
  unaffordable before, free now. It is the only way to a single 1.49 s line.
- Render locally, no flash: `make render`.

Current parameters (`build_bus.py`): `TIME` p0, `FDBK` p1, `TONE` p2,
`PING` p3, `MIX` p4, `VRBW` p5, `VRBD` p8 — 7 of 12 used.

### 3. FX1 consolidation — turning 12,288 stranded words into capability

The trick ChonVerb already ran: replace near-duplicates with one engine plus a
MODE select.

| cluster | stock | one engine | freed **per payload** |
|---|---|---|---|
| PHASER + FLANGER + CHORUS + COMB | **1,052** | ~400-500 🟡 | **~550-650** |
| EQUALIZER + DJ EQ | **627** | ~300 🟡 | **~325** |

All four in row 1 are the same structure — a short modulated delay with
feedback, differing in length, modulation and allpass-vs-comb. They are also
the effects most in need of a 2026 rewrite.

**~900 words freed takes payload A from 527 to ~1,400.** That is no longer
needed to make the reverb affordable — rolling the tank does that (step 1).
It is now headroom for FX1's *own* ambition, which is the point: FX1's
12,288 words of per-core delay memory are stranded until an FX1 effect exists
to reach them.

**FILTER is the outlier**: 727 words, the largest, the default FX1 effect, and
~260 cycles — far more than a biquad should cost, which `docs/CHIP.md` reads as a
large fixed per-call overhead. Highest value, highest risk; it is the effect
people actually rely on.

✅ **Taking the three reverbs cost FX1 nothing** — they were never on its menu
(both chooser lists decoded 8 Aug). FX1's ten effects are the whole pool.

> The eight-line tank used to be step 3 here. It is now part of step 1, where
> the numbers say it belongs.

---

## The one thing that needs hardware

**A `BURN=1` flash, then sweep from the front panel.** It answers **the real
FX1 worst case** — four *different* heavy FX1 effects, one per track, plus the
bank — which decides how much FX1 can afford. Once the build is on the card
every further configuration is a knob sweep with **no further flash**.

🔴 **BLOCKED as of 8 Aug 2026: the burn probe no longer builds.** `BURN=1`
splices `burn_block{1,2}.inc` into the reverb (~16 words) and the eight-line
tank leaves 6 free, so payload A overruns by 10. `SPEC=1` is not a way out —
the build guards SPEC-with-BURN, since both replace a server.

This was **hidden until the four-line engine was deleted**: `verify_burn.py`
pinned `RVSRC` to the four-line source, so `make verify` was green while
checking an engine the build no longer shipped — the same stale-fork trap as
the burn probe that once measured an engine we did not ship. The pin is gone;
`make check` now prints a loud SKIP naming the shortfall, and passes, because
the probe is in no shipping image and blocking local work on it would be
wrong. It must never read as "verified".

Three ways out, cheapest first: find ~10 more words in the reverb (the
odd-forcing hoist just found 10 the same way — `move #>$0800,b` appears 8
times at 2 words each and could come from an index register); shrink the burn
blocks; or wait for FX1 consolidation (step 3), which frees ~550-650 per
payload and makes the question disappear.

`Y:0x34000` is no longer part of this trip: ❌ retracted 8 Aug, it was
falsified by our own v107 bisect (`docs/CHIP.md` §6).

**Sequence it with the delay (step 2), not before it.** Step 1 needs no
hardware at all, and the sweep informs step 3. ⚠️ Whatever trip happens next
must carry **v121's bus auto-gain** — the build on the unit predates it and
breaks above three simultaneous sends.

---

## Open, and unchanged by any of this

- **BIG rings** — ~30 dB more HF than other modes with no shimmer; `md_big`
  sets the decay scale to exactly 1.000000 where others leave headroom.
- **Tank saturation above ~0.35 FS** — the only level limit left since v121.
- **Emulator/device gap: parameter delivery.** `-params` pokes `r6` directly,
  so every page-2 slot looks live locally while on hardware a slot can draw a
  knob and publish nothing. This caused the shimmer to run half-on in every
  build anyone ever heard. **It caps how many usable parameters any effect can
  have**, so it is worth closing before designing a 12-knob delay.
- **Emulator/device gap: per-core layout.** ✅ Closed 8 Aug — `render_reverb.py`
  and `make render` now build with `SPEC=1`, matching the shipping layout
  (reverb on A, delay on B). dsp_host boots payload A, so the reverb renders
  identically to hardware. The delay has no local render unless the OMR lever
  is pulled.
- **Duplicate instances of one effect corrupt audio after ~5.45 s**, any
  address, mechanism unestablished. One server per bank is a design rule; no
  product configuration has this.

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

**Bump `BUILD` on every flash** (`make image BUILD=002`). It is stamped into
the OS version field and shown on the panel; three debugging rounds were once
lost to not knowing which firmware was on the unit. Also bump `BUILD_TAG` in
`tools/build_bus.py` if you change what the effect names read.
