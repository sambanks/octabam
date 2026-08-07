# Chip, cycles and memory — the current numbers

One page, because these have moved a lot and stale copies of them have cost
real work. **Every row carries a confidence marker.** Where a number was
retracted, the old value is kept alongside it — knowing what a figure used to
be is how you spot a doc that hasn't caught up.

- ✅ **measured** — on hardware, or read off the part
- 🟡 **inferred** — fits the evidence, not directly tested; falsifier stated
- ❌ **retracted** — was believed, now known wrong

Last updated 7 Aug 2026 (build 27).

---

## 0. The machine model, because this is the easy thing to get wrong

**FX1 and FX2 are not chips, and not cores. They are two effect *slots* on
every track**, run back to back in the same per-track chain: `FX1 → FX2 → gain
→ bookkeeping` (`DSP.md` §5–6). Both slots of a given track run on whichever
core that track lives on.

```
        ONE CHIP: DSP56721
   ┌──────────────────┐   ┌──────────────────┐
   │      CORE 0      │   │      CORE 1      │
   │   tracks 1–4     │   │   tracks 5–8     │
   │                  │   │                  │
   │  track 1: FX1→FX2│   │  track 5: FX1→FX2│
   │  track 2: FX1→FX2│   │  track 6: FX1→FX2│
   │  track 3: FX1→FX2│   │  track 7: FX1→FX2│
   │  track 4: FX1→FX2│   │  track 8: FX1→FX2│
   │                  │   │                  │
   │ 4535 cyc/sample  │   │ 4535 cyc/sample  │
   │ own P memory     │   │ own P memory     │
   └────────┬─────────┘   └─────────┬────────┘
            └──── shared 64 K ──────┘   (Y:0x30000–0x3FFFF, ✅ §3)
```

**FX1 and FX2 differ in exactly three ways** — nothing else:

1. **Order.** FX1 runs before FX2, so an FX1 send taps the *dry* signal.
2. **Slot size.** FX1 gets 3 072 words of Y, FX2 gets 16 384. That, and only
   that, is why reverbs are FX2-only.
3. **Which byte holds the id.** FX1 reads it from `r6+$1b`, FX2 from `r6+$1c`.

> **Both slots share ONE dispatch table.** Six `jsr (r2)` sites, all in
> `P:0x0041e`, all indexing `X:0x215`/`X:0x235`. "FX1 takes the id from
> `r6+$1b`, FX2 from `r6+$1c` — that is the *only* difference between the
> slots." (`DSP.md:238`) ✅ measured

### The three resources, and how they differ

| | scoped to | spent when | ours |
|---|---|---|---|
| **Program space** (P) | **per core** | once at load — same cost whether 1 track or 8 use the effect | 2 724 words, **11 free** |
| **Cycles** | **per core** | **every frame, per track, per slot** — up to 8 effect calls per core | **~1 392 spare** |
| **Y memory** | **per track, per slot** | allocated always, used or not | 16 384 per FX2 slot |

The one that catches people is the middle row. Program space is paid **once**;
cycles are paid **per track per slot per frame**. Eight tracks running ChonVerb
cost one copy of the code and eight times the cycles.

### The two menus, read off the image (8 Aug 2026)

✅ **Measured, not inferred** — decoded from the chooser lists at `0x400d6060`
(FX1) and `0x400d6090` (FX2):

```
FX1 (11): NONE FILTER EQUALIZER DJ-EQ PHASER FLANGER CHORUS SPATIALIZER
          COMB COMPRESSOR LO-FI
FX2 (15): ...the same 11, plus DELAY, PLATE REV, SPRING REV, DARK REV
```

**The three reverbs and the delay are FX2-ONLY on stock.** Two consequences:

1. ❌ **RETRACTED: `BUS.md`'s "FX1's chooser is untouched and can still select
   PLATE REV, SPRING REV or DARK REV by name."** It cannot — they are not in
   its list. So **taking the three reverbs costs FX1 nothing at all**, and the
   "three stock reverbs for a better one" trade is only ever paid on the FX2
   menu, which we replace wholesale anyway. The null-stub silencing stays as
   insurance (both slots share one dispatch, so a stored id outside the menu
   would still reach the code), but it is defending a path the UI cannot walk.
2. **FX1's 10 real effects are exactly the reclaimable pool** — 3,384 words,
   the same in both payloads. That is the entire budget any FX1 redesign has
   to work with, and it is what `XBUS.md`'s FX1 section should be priced
   against.

### So: can we delete the stock effects "off FX2"?

**No — and this is the thing you're remembering.** There is no FX1 pool and no
FX2 pool. Every effect exists once, in the DSP's program memory, and both menus
point at the same implementations through that single dispatch table.

- Removing an effect from the **FX2 menu** frees **nothing**. The menu is just a
  list of ids on the ColdFire.
- The space is the effect's **code**, and taking it costs that effect in
  **both** slots.

That is exactly why the build **silences PLATE REV, SPRING REV and DARK REV on
FX1**: we overwrote their code with ChonVerb, so if their ids still dispatched
normally, selecting one on FX1 would run our hardcoded-base engine a second,
uncontrolled time. CHORUS was a donor until v98 and is now byte-identical to
stock, so FX1 gets its chorus back.

⚠️ **This has a live consequence for the cycle headroom.** FX1 effects draw
from the *same* per-core budget as FX2. The 1 392 spare was measured with
whatever FX1 effects were assigned at the time — and a fresh part defaults
FX1 = FILTER. Every FX1 filter you turn on eats into that figure.

---

## 1. The silicon

| | | |
|---|---|---|
| CPU | Freescale ColdFire **MCF54454VR266**, 32-bit big-endian, 266 MHz | ✅ board photo (an MKI board reads `MCF54454`; our note said `MCF5445A` — same family, likely a misread digit) |
| Audio DSP | Freescale Symphony **DSP56721** (`DSPB56721AG`) | ✅ board photo |
| DSP cores | **Two** DSP5636x cores, **200 MHz / 200 MIPS each** | ✅ datasheet |
| External memory controller | **None.** No EMC on this part — all memory is on-chip | ✅ datasheet block diagram |
| Shared memory | **8 blocks × 8 K words = 64 K words at `$030000`**, reachable by *both* cores; P/X/Y alias there | ✅ reference manual + hardware |
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

### Why the datasheet cannot answer this

It gives exactly one cycle number: **200 MIPS per core → 4 535 cycles/sample at
44.1 kHz**. That is the ceiling of the *silicon*. Three things it cannot tell
us, and all three sit between that figure and anything spendable:

1. **What stock already uses.** Voice playback, sample streaming and
   interpolation, FX1, frame plumbing, DMA orchestration — that is a property
   of Elektron's firmware, not of the part. No datasheet knows it.
2. **What the real deadline is.** A freeze means the DSP missed its *frame*
   deadline, which may sit below 100 % of the core — the frame ISR needs its
   own margin. So the usable budget is at most 4 535, probably less.
3. **Memory-contention stalls.** "200 MIPS" assumes one instruction per cycle
   with no stalls. Real code doing X and Y accesses with AGU interlocks runs
   below that, by an amount that depends on the code.

**Datasheet = the ceiling of the chip. The burn probe = the ceiling of what is
left after stock.** Only the second is spendable, and only the second can be
measured from here.

Rough split implied by our measurements (big error bars, but the shape holds):
of 4 535 cycles/sample, stock's own per-track work takes **under ~1 550**, four
FX1 FILTERs take **over 640**, our FX2 bank takes ~957 static, and 1 392 was
still spare on top of all of it.

📄 **The reference manual HAS now been read** — `DSP56720RM.pdf`, 575 pages,
at `downloads/datasheets/` (gitignored; third-party). Extract with
`pdftotext -layout`; `file` misreports it as 27 pages. It settled §3's memory
questions without a flash. What it still has and we have NOT used: Ch. 3's five
OMR-selectable memory maps (`MS`, `MSW0`, `MSW1`), which set the per-core X/Y/P
extents — read those before trusting any *internal* extent.

### "Spare" is only meaningful attached to a configuration

⚠️ **1 392 is spare on top of whatever happened to be assigned during that
sweep — not an untouchable reserve.** Everything on the core draws from the
same budget: stock's per-track voice work, **all four tracks' FX1 effects**,
and our FX2 bank. A fresh part defaults FX1 = FILTER, so a realistic kit is
paying for four FX1 effects the sweep may not have included.

**Budget against the worst realistic case per core**, not the bare one:

    4 tracks playing  +  an FX1 effect on each  +  the FX2 bank (957 static)

### The burn knob is a reusable CYCLE METER, not a one-shot test

This is the part worth keeping. `BURN` sits on ChonVerb in any `BURN=1` build,
so **any configuration can be measured, on demand, with no flash**:

1. Set up the configuration you care about.
2. Sweep `BURN` up until it breaks.
3. **`16 × BURN` = cycles/sample spare in that configuration.**

And the *difference* between two configurations is the **cost of the change** —
which is the only way to price stock effects at all, since they are binary and
instruction count is not cycles (`v97` moved instructions up 508 → 512 while
cycles fell 735 → 731).

So the cost of a stock FX1 effect is directly measurable: sweep with it
assigned on all four tracks, sweep without, take the difference. If a
configuration freezes at `BURN = 0`, that configuration is already over budget
and that is a finding in itself.

### Measured: the ceiling, and what the stock FX1 FILTER costs

| configuration | result | spare |
|---|---|---|
| FILTER on all four tracks | froze at `BURN = 87` (16× scale) | **1 392** ✅ |
| FILTER disabled everywhere | froze at `BURN = 76` (32× scale) | **2 432** ✅ |

**Four FILTERs cost 1 040 cycles/sample — about 260 each.** That is ~23 % of a
core for four of them, and much more than a filter looks like it should cost.

**The two configurations reconcile to the same total, which is why these are
trustworthy** rather than two unrelated readings:

| | cycles/sample |
|---|---|
| FX2 bank (static) | 957 |
| 4 × stock FILTER | 1 040 |
| burn at the freeze | 1 392 |
| **accounted** | **3 389** |
| stock's own per-track work (by difference, of 4 535) | **~1 150** |

Two consequences, and the first is the important one:

**1 392 is the CONSERVATIVE number, not the optimistic one.** It was measured
with the heaviest FX1 config already running, so it is a worst case that needs
no further derating. Design the delay against it.

**Turning FX1 filters off is worth ≥ 640 cycles** — a real design lever if
anything ever needs more than 1 392.

⚠️ **The probe's range is now the limiting factor, not the chip.** The burn tops
out at `16 × 127 = 2 032` and the filters-off configuration sailed past it, so
**the absolute ceiling is still unmeasured**. Raising the scale to `32 ×` (max
4 064) would find it. Not needed for design — 1 392 worst-case is the number
that matters — but it is the only reason §2's "~2 150" is still a range.

**Establish the worst-case number before designing the delay**, so the
algorithm is designed against a real budget rather than a bare-config one.

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

✅ **`0x30000–0x3FFFF` IS the shared memory — settled from `DSP56720RM.pdf`,
not inferred.** §1.4.13: *"eight 8K × 24 words memory blocks for a total of 64K
shared words and is located starting from $030000"*, and Ch. 3: *"The shared
memory blocks occupy addresses from $030000 to $03FFFF (including $03FFFF),
**accessible by both DSP cores**."* 8 × 8 192 = 65 536 — **words, not bytes**,
which was the whole ambiguity in the block diagram.

❌ **"The two DSPs are a hard boundary."** `BUS.md`'s founding constraint is
dead. There is 64 K both cores address; the split into `0x30000` (payload A) /
`0x38000` (payload B) is **a convention we chose**, not a hardware wall. A true
8-track bus and cross-core sends are both back on the table.

✅ **P, X and Y ALIAS in this region — CONFIRMED ON HARDWARE**, 7 Aug, build 27.
The manual says *"the Program, X, and Y memory addresses are mapped into same
physical location"*; `dsp/alias_probe.asm` wrote a tagged incrementing word
through Y and read it back through **X** and through **P**, at four addresses
across the window. Every one agreed. The window is uniform.

⚠️ **THE WINDOW IS NOT EMPTY — the DSP bootstraps live in it.** `DSP.md:22`/`:27`:
bootstrap A loads to **`P:0x31000`** (50 words) and bootstrap B to
**`P:0x32000`** (58 words). Both sit inside `0x30000-0x3FFFF`, and since P and
Y are the same words there, **`delay_server`'s payload-A buffer
(`0x30000-0x37FFF`) covers both of them.** Harmless once booted — they have
already run — but nothing may assume that region is scratch.

(The probe's own ADDR=0 is base+0x1000, i.e. `0x31000` on payload A: it has been
writing over bootstrap A's first word all along, and reading it back through P.
That is also the strongest single piece of evidence for the aliasing — if P and
Y were separate memories, `P:0x31000` would still hold a bootstrap instruction,
not our counter.)

❌ **"X:0x30000 and Y:0x30000 do not alias."** Commit `0f93639` reached that by
inference — *if they aliased, stock would corrupt itself whenever a reverb sat
on track 3*. The manual states the hardware directly and wins. One premise of
that argument is false; the likeliest is the claim that stock stages per-frame
parameters at `X:0x30000` at all.

❌ **"BongDelay may use its full 32 768 words."** Retracted with it. The window
is not ours to assume.

✅ **Zero wait states as X or Y** (1 as P) — so this memory is *not* slow, and
`DSP.md:449`/`744`'s "walks external memory, which is slower" is wrong twice
over: not external, not slower.

✅ **Contention is per 8 K block, and that is a design lever.** *"No bus
contentions occur when the two DSP cores access different 8K × 24 SRAM blocks
simultaneously."* Keep each core's buffers in different 8 K blocks and
arbitration costs nothing.

✅ **A second cross-core channel exists: the ICC** (§1.4.14). Each core can
raise a maskable or non-maskable interrupt in the other, with write-data and
poll-data registers for exchange. Worth remembering if the shared window ever
proves unusable.

✅ **Per-core P/X/Y extents are configurable via OMR — and stock runs the
DEFAULT map. ANSWERED, Ch. 3 read 7 Aug 2026.**

| map | MS | MSW1 | MSW0 | Program | X | Y |
|---|---|---|---|---|---|---|
| Fig 3-2 **default** | 0 | – | – | **8K** | 36K | **48K** |
| Fig 3-3 | 1 | 1 | 1 | 16K | 36K | 40K |
| Fig 3-4 | 1 | 1 | 0 | 24K | 36K | 32K |
| Fig 3-5 | 1 | 0 | 1 | 32K | 36K | 24K |
| Fig 3-6 | 1 | 0 | 0 | 36K | **32K** | 24K |

Every row totals **92K words**: the three spaces are one pool OMR redistributes,
traded word for word. `MS` is OMR bit 7, `MSW1:MSW0` bits 22:21, all reset to 0.

Three independent confirmations that stock is on Fig 3-2:
- ✅ **Nothing writes OMR** in either payload. Disassembling every P module
  finds two OMR-class instructions, both `andi #$fc,mr` — the *mode* register,
  not OMR.
- ✅ The hardware Y sweep above (`0x00000-0x0BFFF` present, `0x0C000` absent) is
  Fig 3-2's 48K to the word.
- ✅ Payload A's P code ends at **`0x01fdf`, 33 words short of `0x2000`** —
  8,159 of the default map's 8,192. **That is why program space is the wall,
  and it is a setting, not silicon.**

❌ **Fig 3-6 is ruled out**: it drops X to `0x0-0x7FFF` and stock's X modules
reach `0x08d98`.

✅ **Shared RAM appears in the PROGRAM column of all five figures.** The
`0x30000-0x3FFFF` window is program-addressable in every configuration, not
just as X/Y. See `XBUS.md` for both levers this opens and their falsifiers.

## 3a. What is actually IN the shared window (mapped 7 Aug, static analysis)

Two free passes over `out/raw/section_3_MAIN_OS.bin`: which modules **load**
into `0x30000-0x3FFFF`, and which words in P code **reference** it. Remember P,
X and Y are the same physical words here, so a P module and an X buffer at the
same address are the same memory.

| range | what | evidence |
|---|---|---|
| `0x30000-0x30047` (**72 words**) | **stock's per-frame PARAMETER STAGING.** Copied X→`Y:0x1b8` and written back every frame | disassembled: `do #<$48` loops at `P:0x0a4` (read) and `P:0x366` (write) |
| `0x30000-0x300AA` (171 words) | DSP **host-port loader + ESAI setup**, payload A, boot-time | module dump |
| `0x31000-0x31031` (50 words) | **bootstrap A** | `DSP.md:22` |
| `0x32000-0x32039` (58 words) | **bootstrap B** | `DSP.md:27` |
| `0x38000-0x38012` (19 words) | payload **B's entry stub** — `jsr`s into `0x30082`/`0x3008a` | module dump |
| `0x30000-0x37FFF` | **zeroed at init**, all 32 768 words | disassembled at `P:0x040` |
| `0x38000` | referenced in a **DMA** setup (`M_DCR2`) | `P:0x098` |

**`X:0x30000` staging is CONFIRMED, not folklore.** `DSP.md` claimed stock
"copies 72 words to `y:0x1b8`"; the loop is `do #<$48` = 72, and there is a
matching write-back. Since X and Y alias here, that is `Y:0x30000-0x30047` too.

**The window doubles up on purpose.** The boot loader occupies `0x30000` as P;
init then zeroes `0x30000-0x37FFF`; the same words are then staging and FX2
buffer. Boot code is disposable and stock reuses its address space — which is
why nothing breaks.

**Payload B's stub calls into payload A's code**, at `0x30082`/`0x3008a`. That
is stock already doing cross-core code sharing through this window, in
production, today.

⚠️ **Method caveat:** a raw word scan finds *values*, not addresses. `0x3a667`
looked like a reference and disassembles as `teq x1,a r6,r7` (opcode `03a667`).
Anything from that pass must be disassembled before it is believed.

### Who uses what

| | |
|---|---|
| ChonVerb | `Y:0x4000–0xBFFF` — 32 768 words, **hardcoded**, both payloads (different cores, so no collision) |
| BongDelay | `Y:0x30000–0x37FFF` (A) / `Y:0x38000–0x3FFFF` (B) — 32 768 words each ⚠️ **COLLIDES AT BOTH BASES**, see §3a. Untested first draft; do not assume it works |
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

~~**Do the two cores share `Y:0x30000–0x3FFFF`?**~~ **ANSWERED — yes**, from
the reference manual, no flash needed (§3). What is still open is what to *do*
with it: a true 8-track bus and cross-core sends are now possible, and the
per-8K-block contention rule says how to lay it out.

~~**What else lives in the shared window?**~~ **MAPPED — see §3a.** It is
heavily used by stock, at both of `delay_server`'s bases.

~~**The 32-step fault.**~~ **CLOSED — not a product issue.** ✅ Bisected on
hardware, 7 Aug:

| configuration | result |
|---|---|
| one `SharePrb` + three `Send`s | **clean** at every ADDR and INC |
| `SharePrb` + `ChonVerb` on one bank | **clean** |
| **two `SharePrb`s** on one bank | **noise after ~5.45 s**, regardless of address |

So it needs **two instances of the same effect**, and the address is
irrelevant — different target words on each track failed identically. Every
configuration the product actually uses is clean.

That fits the probe's known gap: `BUS.md` has **role locks "so duplicates fail
safe"**, claimed by both real servers via `bus_claim` and released each block by
`send_client`. `dsp/shared_probe.asm` has neither lock nor housekeeping, so two
copies each behave as if they own the bank. **Mechanism never established, and
it does not need to be** — one server per bank is a design rule, not an
accident. Re-open only if duplicate servers ever become desirable.

❌ **RETRACTED: "a single word written to `Y:0x34000` from payload A corrupts
that track's audio after ~5.45 s."** This paragraph stood here until 8 Aug 2026
and `XBUS.md` imported it as **risk 1, "the only unknown here that can
invalidate the whole memory plan."** It was already dead when it was written.

**The v107 bisect directly above falsifies it, and covers the exact address.**
`dsp/shared_probe.asm`'s `ADDR = 0` *is* `0x34000` (`move #>$34000,y0 ; 0: FX2
slot 4 base, A's half`), and the row **"one `SharePrb` + three `Send`s → clean
at every ADDR and INC"** therefore includes a single instance writing that very
word. ✅ **One instance at `Y:0x34000` is clean on hardware.**

The two builds that "reproduced" it are rounds 1 and 2, and commit `04a24cf`
says so in as many words: *"I had also misread my own evidence: rounds 1 and 2
BOTH had two instances running, which is why I attributed to the write address
what was always about duplication."* The fault was always duplication; the
address never mattered.

**What is still true** is only the row above: two instances of the same effect
corrupt audio after ~5.45 s at any address, mechanism unestablished, and no
product configuration has that. **`Y:0x30000–0x37FFF` is not blocked**, and the
memory re-plan can proceed.

**The lesson is the propagation, not the measurement.** The retraction was
correct, was written down, and reached only the commit message — so a claim
this file still asserted went on to become the top-ranked blocker in the
planning doc. When a bisect kills a hypothesis, delete the paragraph the
hypothesis lives in, not just the sentence that stated the conclusion.

**Assembler traps.** `dsp_asm` has no reject path — it emits the nearest
encoding. Accumulator-to-accumulator `CMP`/`CMPM`/`TFR` all mis-encode
(`cmp b,a` → `maxm a,b`, `tfr a,b` → `rnd b`); `MPY` with an operand pair the
56300 cannot encode becomes `mpysu`. `ADD`/`SUB`/`MOVE` are fine in that form.
**Disassemble every hand-written block.**
