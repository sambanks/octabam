# The plan: end state, resource ledger, and work order

Written 8 Aug 2026, after a full re-evaluation of where every resource goes.
**This is the cold-start document — read it before `XBUS.md`**, which is now
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
| Reverb | voiced, confirmed by ear, shimmer excised. Not growing yet |
| Delay | **`delay_server.asm` is an untested first draft.** Treat as unwritten |
| Next | **BongDelay**, then FX1 consolidation, then the 8-line tank |

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
- **OMR memory map** (`CHIP.md` §3): Fig 3-3 doubles P, 8K → 16K, **+8,192
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

### 1. BongDelay — the delay you can route

**Why it is first: it is the only thing that can spend payload B's 2,600
words, and it is the one feature the machine has never had.**

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
- Render locally, no flash: `DEV=1 XBUS=1 python3 tools/build_bus.py` then
  `python3 tools/send_probe.py --mem out/dsp/mem_dev_A.mem --layout DS`.

Current parameters (`build_bus.py`): `TIME` p0, `FDBK` p1, `TONE` p2,
`PING` p3, `MIX` p4, `VRBW` p5, `VRBD` p8 — 7 of 12 used.

### 2. FX1 consolidation — where payload A's space comes from

The trick ChonVerb already ran: replace near-duplicates with one engine plus a
MODE select.

| cluster | stock | one engine | freed **per payload** |
|---|---|---|---|
| PHASER + FLANGER + CHORUS + COMB | **1,052** | ~400-500 🟡 | **~550-650** |
| EQUALIZER + DJ EQ | **627** | ~300 🟡 | **~325** |

All four in row 1 are the same structure — a short modulated delay with
feedback, differing in length, modulation and allpass-vs-comb. They are also
the effects most in need of a 2026 rewrite.

**~900 words freed takes payload A from 527 to ~1,400**, which is what makes
step 3 affordable rather than marginal.

**FILTER is the outlier**: 727 words, the largest, the default FX1 effect, and
~260 cycles — far more than a biquad should cost, which `CHIP.md` reads as a
large fixed per-call overhead. Highest value, highest risk; it is the effect
people actually rely on.

✅ **Taking the three reverbs cost FX1 nothing** — they were never on its menu
(both chooser lists decoded 8 Aug). FX1's ten effects are the whole pool.

### 3. Eight tank lines — the reverb's next audible step

Modal overlap 0.157 → ~0.31. Costs ~450-500 words unrolled 🟡 against
payload A's 527 today — which is why step 2 comes first. **Roll the tank loop
in the same pass** (265 instructions doing 66 instructions' work) and move the
per-line state to absolute Y, since `r7` is full; the two have the same fix.
Gate: bit-identical to the unrolled build at four lines, with the single-`nop`
control that proves the comparison is not blind.

---

## The one thing that needs hardware

**A `BURN=1` flash, then sweep from the front panel.** It answers **the real
FX1 worst case** — four *different* heavy FX1 effects, one per track, plus the
bank — which decides whether step 3 fits. Once the build is on the card every
further configuration is a knob sweep with **no further flash**.

`Y:0x34000` is no longer part of this trip: ❌ retracted 8 Aug, it was
falsified by our own v107 bisect (`CHIP.md` §6).

**Sequence it with the delay, not before it** — step 1 needs no hardware, and
the sweep informs step 2/3.

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
python3 tools/build_bus.py                    # plain, flashable
XBUS=1 SPEC=1 python3 tools/build_bus.py      # specialized -- the real image
DEV=1  XBUS=1 python3 tools/build_bus.py      # local render, NEVER flash
BURN=1 python3 tools/build_bus.py             # cycle meter on p3

python3 tools/verify_menu.py                  # ColdFire menu tables
python3 tools/verify_burn.py                  # burn probe is inert when off
python3 tools/cycle_count.py                  # per-effect cycles
```

Bump `BUILD_TAG` in `tools/build_bus.py` before wrapping any `.bin` — the tag
is displayed on the panel, and three debugging rounds were once lost to not
knowing which firmware was on the unit.
