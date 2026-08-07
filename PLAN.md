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
| Reverb | voiced, confirmed by ear, shimmer excised. **Structurally still the four-line tank it started as** |
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

1. **Roll the tank loop.** 265 instructions doing 66 instructions' work. Move
   per-line state to absolute Y — `r7` is full (`$10..$83` used, `$84+` hangs),
   and the roll needs indexable state anyway. The two are one change.
   **Gate: bit-identical to the unrolled build at four lines**, with the
   single-`nop` control that proves the comparison is not blind.
2. **Eight lines.** Modal overlap 0.157 → ~0.31 — the density step people
   actually hear. Needs an 8x8 Hadamard; as a fast Walsh-Hadamard that is
   24 butterflies against the 4x4's 8, still adds and subtracts only.
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
