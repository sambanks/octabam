# Chip, cycles and memory: the current numbers

Every row carries a confidence marker; a retracted value is kept beside
the current one.

- ✅ measured: on hardware, or read off the part or the firmware
- 🟡 inferred: fits the evidence, not directly tested; falsifier stated
- ❌ retracted: was believed, now known wrong

## 0. The machine model

FX1 and FX2 are two effect slots on every track, run back to back in the
same per-track chain: `FX1 → FX2 → gain → bookkeeping` (`DSP.md` sections 5-6).
Both slots of a track run on the core that track lives on.

```
        ONE CHIP: DSP56721
   ┌──────────────────┐   ┌──────────────────┐
   │      CORE 0      │   │      CORE 1      │
   │   tracks 5–8     │   │   tracks 1–4     │
   │  track n: FX1→FX2│   │  track n: FX1→FX2│
   │  own P memory    │   │  own P memory    │
   └────────┬─────────┘   └─────────┬────────┘
            └──── shared 64 K ──────┘   (Y:0x30000–0x3FFFF, section 3)
```

FX1 and FX2 differ in exactly three ways ✅: order (FX1 runs first, so an
FX1 send taps the dry signal); slot size (FX1 gets 3,072 words of Y, FX2
16,384, which is why reverbs are FX2-only); which byte holds the id (FX1
`r6+$1b`, FX2 `r6+$1c`). Both slots share one dispatch table: six `jsr
(r2)` sites, all in `P:0x0041e`, all indexing `X:0x215`/`X:0x235`.

| resource | scoped to | spent when |
|---|---|---|
| program space (P) | per core | once at load; the same cost whether 1 track or 8 use the effect |
| cycles | per core | every frame, per track, per slot: up to 8 effect calls per core |
| Y memory | per track, per slot | allocated always, used or not |

The two menus, decoded from the chooser lists at `0x400d6060` (FX1) and
`0x400d6090` (FX2) ✅:

```
FX1 (11): NONE FILTER EQUALIZER DJ-EQ PHASER FLANGER CHORUS SPATIALIZER
          COMB COMPRESSOR LO-FI
FX2 (15): the same 11, plus DELAY, PLATE REV, SPRING REV, DARK REV
```

The three reverbs and the delay are FX2-only on stock, so taking the
reverbs as the donor region costs FX1 nothing (❌ `git show 3ceba41:docs/history/BUS.md`'s "FX1 can still
select PLATE REV by name"). Removing an effect from a menu frees nothing;
the space is the effect's code, and taking it costs that effect in both
slots, which is why a harvested id is null-stubbed on both. FX1's ten
effects are the reclaimable pool: 3,384 words, the same in both payloads.
FX1 effects draw from the same per-core cycle budget as FX2, and a fresh
part defaults FX1 = FILTER.

## 1. The silicon

| | | |
|---|---|---|
| CPU | Freescale ColdFire MCF54454VR266, 32-bit big-endian, 266 MHz | ✅ board photo (an MKI board reads `MCF54454`; an earlier note said `MCF5445A`) |
| CPU clock tree | crystal 24 MHz → VCO 528 → CPU 264 MHz, internal bus 132, FlexBus 66 | ✅ from the image + MCF54455RM (below) |
| Audio DSP | Freescale Symphony DSP56721 (`DSPB56721AG`) | ✅ board photo |
| DSP cores | two DSP5636x cores, 200 MHz / 200 MIPS each (the part's maximum) | ✅ datasheet; ✅ 199.9 MHz = 4,532 cycles/sample on this board, measured 22 Sep 2026 (section 2). ❌ 183.456 MHz / 4,160 (inferred from the payload's register writes, until 22 Sep 2026) |
| External memory controller | none; all DSP memory is on-chip | ✅ datasheet |
| Shared DSP memory | 8 blocks × 8 K words = 64 K words at `$030000`, reachable by both cores; P/X/Y alias there | ✅ reference manual + hardware |
| ColdFire RAM | 128 MB SDRAM | ✅ `docs/contributing/PLACEMENT.md` |
| Storage | CompactFlash (FAT16/32) | ✅ |

❌ "Two separate DSP chips": two cores of one part. ❌ "Y:0x30000-0x3FFFF is
external memory, and slower": there is no external memory.

### The ColdFire's clock tree ✅

`PCR` (`0xFC0C4000`) is written with `0x16777731` at all four sites that
touch it (`0x400e165c`, `0x16d0`, `0x173c`, `0x17a8`): PFDR = 22, OUTDIV1 =
1, OUTDIV2 = 3, OUTDIV3 = 7. The boot at `0x40000418` reads PCR back,
multiplies its top byte by 12,000,000, checks the answer is 264,000,000 and
keeps it at `0x400b9654`. That stored number is the CPU clock: the UART
baud setup at `0x40010f76` loads it, shifts it right one, and divides by 32
× baud (the internal bus clock clocks the UARTs, RM section 32); 132 MHz / (32 ×
31250) = 132, an integer.

| | | |
|---|---|---|
| crystal (f_REF) | 24 MHz | 🟡 f_VCO ÷ PFDR |
| f_VCO | 528 MHz | 🟡 CPU × (OUTDIV1+1) |
| CPU (f_SYS) | 264 MHz | ✅ the firmware's stored constant, the VR266 rating |
| internal bus (f_SYS/2): UARTs, PIT, DSPI | 132 MHz | ✅ the UART's shift + RM |
| FlexBus (FB_CLK) | 66 MHz | ✅ f_VCO ÷ (OUTDIV3+1), RM Eqn. 8-4; the RM's own ceiling |

Every divider constraint the manual imposes holds for this word.

🟡 **The PIT clock.** The firmware sets `PCSR = 0x0b36` (prescaler 2048)
and `PMR = stored/409600 − 1 = 643` at `0x400005a8`. Fed the CPU clock
that is a 5 ms tick, which is what the emulators model (`--pit-clock
264e6`); fed the bus clock the chip uses, 2048 × 644 / 132 MHz = 9.99 ms,
a 100 Hz tick. Event order, which the gates compare, is unaffected; every
wall-clock figure in the port's records would be a factor of two out. Not
reviewed; the falsifier is a hardware measurement of the unit's tick rate.

## 2. Cycles

| | | |
|---|---|---|
| per core, per sample @ 44.1 kHz, datasheet clock | 200 MIPS ÷ 44,100 = 4,535 | ✅ arithmetic; ✅ this board's: 4,532 measured (next row) |
| per core, per sample, this board | 4,532 (199.9 MHz): probe 55 (branch `probe55`, 22 Sep 2026), core 1's timer 0 free-running at CLK/2, its per-frame advance (36,258) printed as an amplitude against a fixed reference, read from a MicroBook capture by `tools/harness/clock_probe.py` (gain-independent) | ✅ hardware. ❌ 4,160 / 183.456 MHz (the PLL at its reset default `0x2B60C2` = EXTAL × 195/24, inferred from the payload's register writes, until 22 Sep 2026). What sets the clock is not located |
| measured ceiling for FX work | ~2,350 with 4× FX1 FILTER as environment | ✅ hardware, burn probe, two sweeps |
| spare with the R46 reverb + 4× FILTER + running sequencer | 704 (breakup at p3=22 × 32; p3=23 = the high-pitch squeal, the deep-overrun signature) | ✅ hardware |
| the R46 reverb's true cost | ≈1,650/sample (2,356 − 704); `cycle_count.py` prices it 1,384, so the pricer reads ~270 low on the reverb (and ~264 high on the delay) | ✅ two consistent sweeps |
| spare with the R46 reverb + 2× FILTER | 1,088 (p3=34 × 32) | ✅ hardware |
| one FX1 FILTER's true cost | 192 cycles/sample ((1,088 − 704)/2) | ✅ hardware; ❌ the earlier ~260 inference |
| total DSP-usable budget | ≈3,120 cycles/sample (three sweeps agree: 1,652 + 4×192 + 704 = 3,124; 964 + 768 + 1,392 the same) | ✅ triangulated |
| safe planning number | ~500 on top of the current reverb in a 4-FILTER bank; ~900 with 2 | 🟡 sweep minus a contention margin |
| stock's own share | ≈1,410 (4,532 − 3,120) | ✅ by subtraction. ❌ ≈1,040 (on the 4,160 clock, until 22 Sep 2026) |
| the historic "1,392 spare" | the 7 Aug bank's spare (ceiling 964 + 1,392 = 2,356, consistent) | ✅ then; superseded as a headline |
| ❌ "the budget is 1,080" | the load one probe build happened to survive, never a ceiling | |
| ❌ "FILTER credit", +768 on top of 3,120 (12–15 Sep 2026) | the four environment FILTERs are inside the 3,120 (the sum above), so adding them back double-counted; removed from the pricer | |

The datasheet's 200 MIPS is the ceiling of the silicon. It cannot say what
stock already uses, what the real frame deadline is, or what memory
contention costs; only the burn probe measures what is left after stock.

### The burn knob is a cycle meter

The instrument behind the hardware rows above (`make burn`, `BURN` on
SEND's second slot, `24 × BURN` = spare cycles/sample) and its first
measurements: `tools/harness/README.md` "The burn knob".

### Static counts

`tools/build/cycle_count.py` counts words in the sample loop, no
contention stall: a floor. `dsp_host`'s per-core meter (`-meter`;
`rig_render.py` writes `meter.txt`) counts executed instructions per block
for a whole layout: a second floor, per block, inits included, no stall;
it reads BusVerb at ~1,130 instructions/sample where the static count is
1,652 words (multi-word instructions count once). The ColdFire port's
stopwatch (`--dsp-stopwatch`, `git show 3ceba41:docs/history/COLDFIRE_PORT.md` O13) reads the firmware's own
dispatch in the meter's unit and agrees within 2 % (BusVerb 1,109 under the
firmware, 1,130 on the meter). Only the burn sweep measures the ceiling.
`make cycles` prints the live per-module figures and the worst load a core
can be asked for.

Words are not cycles on this chip (probe 57, branch `probe55`, 22 Sep
2026: core 1's timer 0 around a 1,000-iteration one-instruction DO loop on
T1's FX1, printed as an amplitude and read by `clock_probe.py --bench`):

| instruction | cycles per iteration |
|---|---|
| `move x0,a` | 2.00 ✅ |
| `move x:(r0),a` | 2.00 ✅ |
| `move x:(r7+$15),a` (one-word displaced) | 3.98 ✅ |
| `move x:(r7+$70),a` (two-word displaced) | 6.01 ✅ |

A station's whole-proc timer window is not usable for its absolute cost:
probes 59/61 (8 nops × 125 and × 1,000 iterations) differed by one frame
(72,512 cycles), not by their instruction counts — the window is
pre-empted by whole frames of the unit's other audio work. Probe 56's
per-station numbers (LP 464, VOWL 685, LADR 797, ISO 1,010, TAPE 887, JUNO
1,260 cycles/sample) carry that pre-emption and are not separable from it
❓; the burn sweep and the pricer with the per-form costs above are the
instruments.

## 3. DSP Y memory

Swept end to end on hardware (`git show e8edc940:dsp/ymemprobe.asm`), per
core:

| Y range | what | |
|---|---|---|
| `0x00000–0x00794` | system + loaded modules | ✅ |
| `0x00795–0x00FFF` | free | ✅ |
| `0x01000–0x03FFF` | 4 × FX1 slots, 3,072 words each | ✅ |
| `0x04000–0x0BFFF` | 2 × FX2 slots, 16,384 words each | ✅ |
| `0x0C000–0x2FFFF` | absent (reads silence) | ✅ |
| `0x30000–0x3FFFF` | 64 K words, 4 more FX2 slots | ✅ |
| `0x40000+` | absent (freezes) | ✅ |

The FX2 allocator table (`DSP.md`), stride `0x4000`:

```
FX1:  0x1000  0x1C00  0x2800  0x3400      stride 0xC00  =  3,072 words
FX2:  0x4000  0x8000  0x30000 0x34000     stride 0x4000 = 16,384 words
```

✅ `0x30000-0x3FFFF` is the shared memory (DSP56720RM section 1.4.13: "eight 8K ×
24 words memory blocks for a total of 64K shared words … starting from
$030000"; Ch. 3: "accessible by both DSP cores"). Words, not bytes. The
split into `0x30000` (payload A) / `0x38000` (payload B) is a convention,
not a hardware wall (❌ `git show 3ceba41:docs/history/BUS.md`'s "the two DSPs are a hard boundary").

✅ P, X and Y alias in this region, confirmed on hardware: `git show 93a787fc:dsp/alias_probe.asm`
wrote a tagged word through Y and read it back through X and P at four
addresses across the window. ❌ "X:0x30000 and Y:0x30000 do not alias" (an
inference); ❌ "BusDelay may use its full 32,768 words" (the window is not
free ground). Zero wait states as X or Y (1 as P). Contention is per 8 K
block: no bus contention when the two cores access different blocks. A
second cross-core channel exists, the ICC (section 1.4.14): each core can raise
an interrupt in the other, with write-data and poll-data registers.

Per-core P/X/Y extents are configurable via OMR, and stock runs the
default map ✅ (Ch. 3):

| map | MS | MSW1 | MSW0 | Program | X | Y |
|---|---|---|---|---|---|---|
| Fig 3-2 default | 0 | – | – | 8K | 36K | 48K |
| Fig 3-3 | 1 | 1 | 1 | 16K | 36K | 40K |
| Fig 3-4 | 1 | 1 | 0 | 24K | 36K | 32K |
| Fig 3-5 | 1 | 0 | 1 | 32K | 36K | 24K |
| Fig 3-6 | 1 | 0 | 0 | 36K | 32K | 24K |

Every row totals 92K words; `MS` is OMR bit 7, `MSW1:MSW0` bits 22:21, all
reset to 0. Nothing writes OMR in either payload (the two OMR-class
instructions are `andi #$fc,mr`); the Y sweep is Fig 3-2's 48K to the
word; payload A's P code ends at `0x01fdf`, 33 words short of `0x2000`, so
program space is the wall by a setting, not silicon. Fig 3-6 is ruled out
(stock's X modules reach `0x08d98`). Shared RAM is program-addressable in
every map. Switching the map is an untested lever (`modules/send/README.md`).

### What is in the shared window (static analysis)

| range | what | evidence |
|---|---|---|
| `0x30000-0x30047` (72 words) | stock's per-frame parameter staging, copied X→`Y:0x1b8` and written back every frame | `do #<$48` loops at `P:0x0a4` (read) and `P:0x366` (write) |
| `0x30000-0x300AA` (171 words) | the DSP host-port loader + ESAI setup, payload A, boot-time (the ESAIs carry audio, 8-slot network mode; `DSP.md` section 6c) | module dump |
| `0x31000-0x31031` (50 words) | bootstrap A | `DSP.md` |
| `0x32000-0x32039` (58 words) | bootstrap B | `DSP.md` |
| `0x38000-0x38012` (19 words) | payload B's entry stub, `jsr`s into `0x30082`/`0x3008a` (stock cross-core code sharing) | module dump |
| `0x38000-0x3800F` (16 words) | a per-frame mailbox: core 1's idle loop swaps it with its own `Y:0x1f0`/`0x280` (payload B `P:0x4b-0x56`), core 0 reads it (`P:0x9b-0xa2`), core 1 restores it before dispatch (`P:0x172`); it sits inside BusDelay's LineL, which survives because of the restore | disassembly, 29 Sep 2026 (🟡: not watched at runtime) |
| `0x30000-0x37FFF` | zeroed at init | `P:0x040` |
| `0x38000` | referenced in a DMA setup (`M_DCR2`) | `P:0x098` |
| X data tables | ~20 lookup tables uploaded to both DSPs at boot | `TABLES.md` |

The boot loader occupies `0x30000` as P; init zeroes `0x30000-0x37FFF`;
the same words are then staging and FX2 buffer. A raw word scan finds
values, not addresses (`0x3a667` disassembles as `teq x1,a r6,r7`);
disassemble before believing.

## 4. DSP program memory

| | | |
|---|---|---|
| the donor region (PLATE + SPRING + DARK, contiguous) | 2,724 words | ✅ |
| reachability sweep | payload A 95.8 %, B 98.5 % | ✅ `tools/build/dsp_reach.py` |
| free pool elsewhere | none | ✅ |
| reclaimable | 3,384 words held by ten stock effects, at the cost of those effects | ✅ |

`make bus REMIX=<name>` prints the live ledger (used / FREE per payload). Relocating the
project's code is cheap (assembled with `-org`); relocating stock code is
not (binary, absolute branch targets), so more space means taking a
neighbour's whole module (`stock.harvested`, `docs/contributing/MODULES.md`).

## 5. Slots, tracks and parameters

| | | |
|---|---|---|
| tracks per core | 5-8 → payload A / core 0; 1-4 → payload B / core 1 (❌ an earlier probe reading, 1-4 → A) | ✅ marker-flash test |
| FX slots per track | FX1 (3,072 words) + FX2 (16,384 words) | ✅ |
| reverb/delay FX2-only | FX1's 3,072 words are too small | ✅ |
| FX1 is not idle | the dispatcher calls it every frame; a fresh part defaults FX1 = FILTER | ✅ |
| parameters per effect | 12: 6 page-1 knobs, 6 page-2 slots. Any slot may carry any count (`DSP.md` section 6, "Page 2") | ✅ |
| unassigned tracks | id 0 is aliased to SEND in a bus remix, to the firmware's NONE otherwise | ✅ |
| `r7` state block | `$00–$83` usable; `$84–$8a` is host-owned and cannot hold state across calls (per-call scratch there is fine; BusDelay uses `$84`–`$88`) | ✅ bisected |

Persistent state need not live in `r7`: a probe build parked LFO and
damping state in the instance's own Y region.

## 6. Closed

- Do the two cores share `Y:0x30000–0x3FFFF`? Yes (section 3).
- The 32-step fault: bisected on hardware, two instances of the same
  effect on one bank corrupt audio after ~5.45 s at any address (one
  `SharePrb` + three `Send`s clean at every ADDR and INC; `SharePrb` +
  `BusVerb` clean; two `SharePrb`s noisy). The probe has neither role lock
  nor housekeeping; one server per bank is a design rule. ❌ "A single word
  written to `Y:0x34000` from payload A corrupts that track's audio":
  falsified by that bisect (its ADDR = 0 is `0x34000`).
- Assembler traps: `AGENTS.md` "Traps that have already cost real work".
