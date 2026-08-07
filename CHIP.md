# Chip, cycles and memory — the current numbers

One page, because these have moved a lot and stale copies of them have cost
real work. **Every row carries a confidence marker.** Where a number was
retracted, the old value is kept alongside it — knowing what a figure used to
be is how you spot a doc that hasn't caught up.

- ✅ **measured** — on hardware, or read off the part
- 🟡 **inferred** — fits the evidence, not directly tested; falsifier stated
- ❌ **retracted** — was believed, now known wrong

Last updated 7 Aug 2026 (build 25).

---

## 1. The silicon

| | | |
|---|---|---|
| CPU | Freescale ColdFire **MCF5445AVR266**, 32-bit big-endian, 266 MHz | ✅ board photo |
| Audio DSP | Freescale Symphony **DSP56721** (`DSPB56721AG`) | ✅ board photo |
| DSP cores | **Two** DSP5636x cores, **200 MHz / 200 MIPS each** | ✅ datasheet |
| External memory controller | **None.** No EMC on this part — all memory is on-chip | ✅ datasheet block diagram |
| Shared memory | **8 blocks × 8 K = 64 K**, reachable by *both* cores via Shared Bus 0/1 through Arbiters 0–7 | ✅ datasheet block diagram |
| Storage | CompactFlash (FAT16/32) | ✅ official |

❌ **"Two separate DSP chips."** They are two cores of one part. `ARCHITECTURE.md`
is corrected; `BUS.md` still carries the old framing in places.

❌ **"Y:0x30000–0x3FFFF is EXTERNAL memory, and external is slower."** There is
no external memory. `DSP.md:449` / `DSP.md:744` still say otherwise.

---

## 2. Cycles

| | | |
|---|---|---|
| Per core, per sample @ 44.1 kHz | 200 MIPS ÷ 44 100 = **4 535 cycles** | ✅ arithmetic |
| **Measured ceiling for FX work** | **~2 150** (reverb alone) to **~2 350** (full bank) | ✅ hardware, build 23 |
| **Proven spare headroom** | **1 392 cycles/sample**, exactly | ✅ hardware, build 23 |
| Safe planning number | **~1 100–1 200** | 🟡 1 392 minus contention margin |
| Stock's own share | ~2 400, a bit over half the core | 🟡 by subtraction |

**How the ceiling was measured.** `dsp/burn_probe.asm` adds `16 × p3`
cycles/sample of pure nops, scaled by `n7` so the figure is per *sample*
regardless of the split. It froze at p3 = 87 → **87 × 16 = 1 392 cycles**
tolerated on top of whatever was already running.

**1 392 is the number to trust.** It is measured directly and needs no baseline.
The ~2 150 absolute figure adds a *static* instruction count to a *real*
hardware ceiling, which is slightly apples-to-oranges — real code contends for
memory where nops do not.

❌ **"The budget is 1080 cycles/sample."** 1080 was never a ceiling. It is the
load `stageprobe5` happened to *survive* (`REVERB_LOG.md`) and got written down
as a budget. Every design decision from the density pass onward was priced
against it. `tools/cycle_count.py` still prints `budget/DSP 1080`.

❌ **"There is not real headroom — do not spend it on more delay lines."**
Retracted. There are ~1 200 usable cycles.

### What the bank costs now

| | cycles/sample | |
|---|---|---|
| `reverb_server` (ChonVerb, with shimmer) | 758 | ✅ `tools/cycle_count.py` |
| `delay_server` (BongDelay, **placeholder**) | 163 | ✅ same |
| `send_client` × 2 | 36 | ✅ same |
| **full bank** | **957** | ✅ same |

These are **static** counts — words in the sample loop, no memory-contention
stalls modelled — so they are a floor. `tools/dsp_host` **cannot** measure
cycles: its `instructions/sample` is a constant divided by whatever frame count
you ask for.

**For scale:** the entire ChonVerb engine is 758 cycles. The spare 1 392 is
room for ~1.8 more complete reverbs on the same core. A good delay is ~200–300;
a correlation-search pitch shifter amortises to ~1/sample plus ~30–60.

---

## 3. DSP Y memory

Swept end to end on hardware (`dsp/ymemprobe.asm`, 3 Aug), per core:

| Y range | what | |
|---|---|---|
| `0x00000–0x00794` | system + loaded modules | ✅ |
| `0x00795–0x00FFF` | **free** | ✅ |
| `0x01000–0x03FFF` | 4 × FX1 slots, 3 072 words each | ✅ |
| `0x04000–0x0BFFF` | 2 × FX2 slots, 16 384 words each | ✅ |
| `0x0C000–0x2FFFF` | **absent** (reads silence) | ✅ |
| `0x30000–0x3FFFF` | **64 K words, 4 more FX2 slots** | ✅ |
| `0x40000+` | **absent** (freezes) | ✅ |

**The FX2 allocator table** (`DSP.md:1222`) — stride `0x4000` = 16 384 words:

```
FX1:  0x1000  0x1C00  0x2800  0x3400      stride 0xC00  =  3 072 words
FX2:  0x4000  0x8000  0x30000 0x34000     stride 0x4000 = 16 384 words
```

🟡 **`0x30000–0x3FFFF` is almost certainly the datasheet's 64 K shared block.**
8 × 8 192 = 65 536 = `0x10000`, exactly the span, and with no EMC on the part it
cannot be anything external. *Falsifier:* have one core write a word the other
core reads at the same address — `dsp/shared_probe.asm`, unresolved (§6).

### Who uses what

| | |
|---|---|
| ChonVerb | `Y:0x4000–0xBFFF` — 32 768 words, **hardcoded**, both payloads (different cores, so no collision) |
| BongDelay | `Y:0x30000–0x37FFF` (payload A) / `Y:0x38000–0x3FFFF` (payload B) — 32 768 words each |
| Bus scratch | `Y:0x900–0x980` — parity word, then 4 × 16-word accumulators and 4 × 16-word wet buffers |
| Per-instance base stash | `Y:0x795 + (r7>>8)` — one word per instance |
| SEND | **nothing.** A zero-footprint client; never touches its own slot |

**32 768 words is the hard ceiling per server** and ChonVerb is at it. That
lever is spent.

⚠️ **`Y:0x34000` is FX2 slot 4's allocator base**, and the second half of
BongDelay's pool. Writing a single word there from payload A corrupts that
track's audio after ~5.45 s — see §6.

---

## 4. DSP program memory

| | | |
|---|---|---|
| Our region (PLATE + SPRING + DARK, contiguous) | **2 724 words** | ✅ |
| Used by a normal build | 2 713 — **11 free** | ✅ build 25 |
| Reachability sweep | payload A 95.8 %, B 98.5 % | ✅ `tools/dsp_reach.py` |
| Free pool elsewhere | **none** | ✅ |
| Only reclaimable space | ~3 100 words held by nine stock effects — costs those effects | ✅ |

Placement, in address order: `SEND` 166 · `REVERB SERVER` 2 040 ·
`DELAY SERVER` 507.

**We take exactly three stock effects: PLATE REV, SPRING REV, DARK REV.**
CHORUS was a donor until v98 and is now byte-identical to stock. Relocating
*our* code is cheap (assembled with `-org`); relocating *stock* code is not
(binary, absolute branch targets), so more space means taking a neighbour's
whole module.

---

## 5. Slots, tracks and parameters

| | | |
|---|---|---|
| Tracks per core | **1–4 → payload A / core 0; 5–8 → payload B / core 1** | ✅ confirmed by probe, 7 Aug |
| FX slots per track | FX1 (3 072 words) + FX2 (16 384 words) | ✅ |
| Reverb/delay are FX2-only | FX1's 3 072 words are far too small | ✅ |
| FX1 is **not** idle | dispatcher calls it every frame; a fresh part defaults FX1 = FILTER | ✅ |
| Parameters per effect | **12** — 6 page-1 knobs, 3 page-2 knobs, 3 page-2 selects | ✅ `DSP.md` §9 |
| Menu | 3 entries: ChonVerb / BongDelay / Send. **No selectable NONE** | ✅ |
| Unassigned tracks | id 0 is aliased to **SEND**, so every unassigned track feeds the bus | ✅ |
| `r7` state block | `$00–$83` usable; **`$84–$8a` HANGS** (host-owned) | ✅ bisected |
| ChonVerb's `r7` | **full** | ✅ |

Persistent state does **not** have to live in `r7` — `dsp/cycleburn.asm` parks
LFO and damping state in the instance's own Y region, and `DSP.md`'s v27 build
proved absolute Y works where `r7+$84` hangs. There is exactly one server per
bank, so absolute-Y scalars cannot collide.

---

## 6. Open

**Do the two cores share `Y:0x30000–0x3FFFF`?** Unresolved. The block diagram
says a shared 64 K exists and the span matches exactly; our own evidence cannot
distinguish shared from core-local, because payload A uses `0x30000` and B uses
`0x38000` — different addresses either way. `dsp/shared_probe.asm` puts both on
the *same* address. **Now much less urgent:** with ~1 200 spare cycles you no
longer need cross-core sharing to afford a great reverb *and* a great delay.
What it would buy is a true 8-track bus.

**A single word written to `Y:0x34000` from payload A corrupts that track's
audio after ~5.45 s** (32 steps at 88 BPM), persistently. ✅ Reproduced across
two builds — including one whose writer never touched the audio buffer at all —
and ✅ ruled out as machine or project, since ChonVerb on the same track under
the same conditions is clean. Cause unknown. Matters beyond the probe:
BongDelay's buffer is `Y:0x30000–0x37FFF`.

**Assembler traps.** `dsp_asm` has no reject path — it emits the nearest
encoding. Accumulator-to-accumulator `CMP`/`CMPM`/`TFR` all mis-encode
(`cmp b,a` → `maxm a,b`, `tfr a,b` → `rnd b`); `MPY` with an operand pair the
56300 cannot encode becomes `mpysu`. `ADD`/`SUB`/`MOVE` are fine in that form.
**Disassemble every hand-written block.**
