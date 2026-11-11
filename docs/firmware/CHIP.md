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

### The instruction-form register

A DSP form ships if a stock payload runs it or a row here approves it.
The precedent grep is `out/dsp/payload_*.asm`
(`tools/build/dsp_disasm_all.py`); a form with no site there gets a row
only by PR, with the hardware evidence in the row: probe, image, date,
what was measured, what would falsify it, and the confidence marker the
evidence earned. A form without a row does not ship
(TRAPS.md #trap-chip-form). Forms a payload runs are not listed here; the
payloads are their record.

A form here is an instruction's disassembled text with its immediates,
addresses, displacements and branch targets blanked, its registers, memory
spaces and addressing mode kept, and its word count, so a short and a long
encoding are two forms (`tools/build/dsp_forms.py` lists a module's forms
with no stock site). ⏳ marks a row pending its hardware test: the form
ships, and the row names the test that settles it.

| form | used by | evidence |
|---|---|---|
| `add x0,a x:(r1)+,x0` (1w) | MODULATION (#1080), e.g. `add x0,a x:(r1)+,x0` | ⏳ pending hardware test (Sam, 10 Nov 2026): MODULATION with MIX up, through its five modes, on a unit. Assembled and disassembled to the same text; bit-identical to the code before under dsp_host (`make verify-ident MOD=modulation`, 13 settings). Falsifier: a wedge or wrong output on the unit. |
| `ble L` (2w) | MODULATION (#1080), e.g. `ble func_03b9e2` | ⏳ pending hardware test (Sam, 10 Nov 2026): MODULATION with MIX up, through its five modes, on a unit. Assembled and disassembled to the same text; bit-identical to the code before under dsp_host (`make verify-ident MOD=modulation`, 13 settings). Falsifier: a wedge or wrong output on the unit. |
| `cmp x0,a #N,x0` (1w) | MODULATION (#1080), e.g. `cmp x0,a #$0,x0` | ⏳ pending hardware test (Sam, 10 Nov 2026): MODULATION with MIX up, through its five modes, on a unit. Assembled and disassembled to the same text; bit-identical to the code before under dsp_host (`make verify-ident MOD=modulation`, 13 settings). Falsifier: a wedge or wrong output on the unit. |
| `move a,x:(r3)+ a,y0` (1w) | MODULATION (#1080), e.g. `move a,x:(r3)+ a,y0` | ⏳ pending hardware test (Sam, 10 Nov 2026): MODULATION with MIX up, through its five modes, on a unit. Assembled and disassembled to the same text; bit-identical to the code before under dsp_host (`make verify-ident MOD=modulation`, 13 settings). Falsifier: a wedge or wrong output on the unit. |
| `move x:(r7+N),y0` (2w) | MODULATION (#1080), e.g. `move x:(r7+$45),y0` | ⏳ pending hardware test (Sam, 10 Nov 2026): MODULATION with MIX up, through its five modes, on a unit. Assembled and disassembled to the same text; bit-identical to the code before under dsp_host (`make verify-ident MOD=modulation`, 13 settings). Falsifier: a wedge or wrong output on the unit. |
| `move y0,n5` (1w) | MODULATION (#1080), e.g. `move y0,n5` | ⏳ pending hardware test (Sam, 10 Nov 2026): MODULATION with MIX up, through its five modes, on a unit. Assembled and disassembled to the same text; bit-identical to the code before under dsp_host (`make verify-ident MOD=modulation`, 13 settings). Falsifier: a wedge or wrong output on the unit. |
| `move y1,x:(r1)+` (1w) | MODULATION (#1080), e.g. `move y1,x:(r1)+` | ⏳ pending hardware test (Sam, 10 Nov 2026): MODULATION with MIX up, through its five modes, on a unit. Assembled and disassembled to the same text; bit-identical to the code before under dsp_host (`make verify-ident MOD=modulation`, 13 settings). Falsifier: a wedge or wrong output on the unit. |
| `mpy x0,y1,a x:(r0+n0),b` (1w) | MODULATION (#1080), e.g. `mpy x0,y1,a x:(r0+n0),b` | ⏳ pending hardware test (Sam, 10 Nov 2026): MODULATION with MIX up, through its five modes, on a unit. Assembled and disassembled to the same text; bit-identical to the code before under dsp_host (`make verify-ident MOD=modulation`, 13 settings). Falsifier: a wedge or wrong output on the unit. |
| `move b,x:(r1+N)` (2w) | KEYBUS (#1065), `move b,x:(r1+$37f60)` | ⏳ pending hardware test: `octabam` with KEYBUS on a unit, CHARACTER's KEY T2–T8 ducking. The nearest run form is BusVerb's `move a,x:(r7+N)` (image 88 era, Sam's MKII); this one differs in the source and index registers. Under dsp_host: `verify_keybus` (the store lands at X:$37F60 + track). Falsifier: a wedge, or the key words staying 0 on the unit. |
| `add x0,a x:(r3)+,x0` (1w) | MODULATION (before #1080), e.g. `add x0,a x:(r3)+,x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `andi #N,ccr` (1w) | MODULATION (before #1080), e.g. `andi #$fe,ccr` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `clr a x:(r0),x0` (1w) | MODULATION (before #1080), e.g. `clr a x:(r0),x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `clr a x:(r0+n0),x0` (1w) | MODULATION (before #1080), e.g. `clr a x:(r0+n0),x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `clr b y0,y1` (1w) | MODULATION (before #1080), e.g. `clr b y0,y1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `cmp x1,a` (1w) | MODULATION (before #1080), e.g. `cmp x1,a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `div x0,a` (1w) | MODULATION (before #1080), e.g. `div x0,a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `lua (r1+N),r3` (1w) | MODULATION (before #1080), e.g. `lua (r1+$1),r3` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `lua (r3+N),r3` (1w) | MODULATION (before #1080), e.g. `lua (r3+$2),r3` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `lua (r4+N),r1` (1w) | MODULATION (before #1080), e.g. `lua (r4+$1),r1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `lua (r4+N),r3` (1w) | MODULATION (before #1080), e.g. `lua (r4+$e),r3` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `lua (r4+N),r5` (1w) | MODULATION (before #1080), e.g. `lua (r4+$17),r5` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `mac x0,y1,a x1,x:(r3)+` (1w) | MODULATION (before #1080), e.g. `mac x0,y1,a x1,x:(r3)+` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move a,x:(r0+n0)` (1w) | MODULATION (before #1080), e.g. `move a,x:(r0+n0)` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move a,x:(r1)` (1w) | MODULATION (before #1080), e.g. `move a,x:(r1)` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move a,y:(r5)` (1w) | MODULATION (before #1080), e.g. `move a,y:(r5)` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move a1,n2` (1w) | MODULATION (before #1080), e.g. `move a1,n2` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move a1,x:(r7+N)` (2w) | MODULATION (before #1080), e.g. `move a1,x:(r7+$42)` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move n1,a` (1w) | MODULATION (before #1080), e.g. `move n1,a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move n2,a` (1w) | MODULATION (before #1080), e.g. `move n2,a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move n2,b` (1w) | MODULATION (before #1080), e.g. `move n2,b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move n2,x0` (1w) | MODULATION (before #1080), e.g. `move n2,x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move n3,a` (1w) | MODULATION (before #1080), e.g. `move n3,a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move n3,x0` (1w) | MODULATION (before #1080), e.g. `move n3,x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move n3,x1` (1w) | MODULATION (before #1080), e.g. `move n3,x1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move n3,y1` (1w) | MODULATION (before #1080), e.g. `move n3,y1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move n4,b` (1w) | MODULATION (before #1080), e.g. `move n4,b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move n6,x0` (1w) | MODULATION (before #1080), e.g. `move n6,x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move p:(r5)+,y0` (1w) | MODULATION (before #1080), e.g. `move p:(r5)+,y0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move p:(r5),b` (1w) | MODULATION (before #1080), e.g. `move p:(r5),b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move p:(r5),x0` (1w) | MODULATION (before #1080), e.g. `move p:(r5),x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move r4,r3` (1w) | MODULATION (before #1080), e.g. `move r4,r3` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move r6,r5` (1w) | MODULATION (before #1080), e.g. `move r6,r5` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move r7,r4` (1w) | MODULATION (before #1080), e.g. `move r7,r4` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move r7,r5` (1w) | MODULATION (before #1080), e.g. `move r7,r5` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x0,n2` (1w) | MODULATION (before #1080), e.g. `move x0,n2` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x0,n6` (1w) | MODULATION (before #1080), e.g. `move x0,n6` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x0,x:(r1)` (1w) | MODULATION (before #1080), e.g. `move x0,x:(r1)` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x0,x:(r3)` (1w) | MODULATION (before #1080), e.g. `move x0,x:(r3)` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x0,x:(r5)` (1w) | MODULATION (before #1080), e.g. `move x0,x:(r5)` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x0,x:(r7+N)` (2w) | MODULATION (before #1080), e.g. `move x0,x:(r7+$45)` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x0,y1` (1w) | MODULATION (before #1080), e.g. `move x0,y1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x1,x0` (1w) | MODULATION (before #1080), e.g. `move x1,x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x1,y1` (1w) | MODULATION (before #1080), e.g. `move x1,y1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x1,y:(r5)` (1w) | MODULATION (before #1080), e.g. `move x1,y:(r5)` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r0),b` (1w) | MODULATION (before #1080), e.g. `move x:(r0),b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r0),x0` (1w) | MODULATION (before #1080), e.g. `move x:(r0),x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r0+n0),b` (1w) | MODULATION (before #1080), e.g. `move x:(r0+n0),b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r1)+,y1` (1w) | MODULATION (before #1080), e.g. `move x:(r1)+,y1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r1),b` (1w) | MODULATION (before #1080), e.g. `move x:(r1),b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r1)-,y1` (1w) | MODULATION (before #1080), e.g. `move x:(r1)-,y1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r1+N),b` (1w) | MODULATION (before #1080), e.g. `move x:(r1+$1),b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r3)-,x0` (1w) | MODULATION (before #1080), e.g. `move x:(r3)-,x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r4),a` (1w) | MODULATION (before #1080), e.g. `move x:(r4),a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r4+N),a` (1w) | MODULATION (before #1080), e.g. `move x:(r4+$1),a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r4+N),x0` (1w) | MODULATION (before #1080), e.g. `move x:(r4+$15),x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r4+N),x1` (1w) | MODULATION (before #1080), e.g. `move x:(r4+$17),x1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r4+N),y0` (1w) | MODULATION (before #1080), e.g. `move x:(r4+$1),y0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r4+N),y1` (1w) | MODULATION (before #1080), e.g. `move x:(r4+$1),y1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r5),a` (1w) | MODULATION (before #1080), e.g. `move x:(r5),a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r7+N),x0` (2w) | MODULATION (before #1080), e.g. `move x:(r7+$40),x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move x:(r7+N),x1` (2w) | MODULATION (before #1080), e.g. `move x:(r7+$47),x1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move y0,y1` (1w) | MODULATION (before #1080), e.g. `move y0,y1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move y1,n3` (1w) | MODULATION (before #1080), e.g. `move y1,n3` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move y:(r5),x0` (1w) | MODULATION (before #1080), e.g. `move y:(r5),x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move y:(r5)-,b` (1w) | MODULATION (before #1080), e.g. `move y:(r5)-,b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move y:(r5)-,x0` (1w) | MODULATION (before #1080), e.g. `move y:(r5)-,x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `move y:(r5)-,x1` (1w) | MODULATION (before #1080), e.g. `move y:(r5)-,x1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `mpy x0,y1,a x:(r0),b` (1w) | MODULATION (before #1080), e.g. `mpy x0,y1,a x:(r0),b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `mpy x0,y1,a x:(r0),x0` (1w) | MODULATION (before #1080), e.g. `mpy x0,y1,a x:(r0),x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `mpy x0,y1,a x:(r0+n0),x0` (1w) | MODULATION (before #1080), e.g. `mpy x0,y1,a x:(r0+n0),x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `mpy x0,y1,a x:(r3),x0` (1w) | MODULATION (before #1080), e.g. `mpy x0,y1,a x:(r3),x0` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `mpy x0,y1,a x:(r3),x1` (1w) | MODULATION (before #1080), e.g. `mpy x0,y1,a x:(r3),x1` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `or x0,a` (1w) | MODULATION (before #1080), e.g. `or x0,a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `teq a,b` (1w) | MODULATION (before #1080), e.g. `teq a,b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `teq y1,a` (1w) | MODULATION (before #1080), e.g. `teq y1,a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `teq y1,b` (1w) | MODULATION (before #1080), e.g. `teq y1,b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `tge x0,a` (1w) | MODULATION (before #1080), e.g. `tge x0,a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `tgt x0,a` (1w) | MODULATION (before #1080), e.g. `tgt x0,a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `tgt x1,a` (1w) | MODULATION (before #1080), e.g. `tgt x1,a` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |
| `tmi x1,b` (1w) | MODULATION (before #1080), e.g. `tmi x1,b` | 🟡 run on Sam's MKII in MODULATION many times (owner report, 10 Nov 2026; the module's proof, image 88, 27 Sep 2026: a fourth MODULATION beside the reverb). Falsifier: a unit fault traced to the form. |

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
| stock FX2 costs, idle-pass counting on the chip (Jannik Aßfalg's MKII, 1.40C, 12 Oct 2026) | DJ EQ 342/330, LO-FI 311/301, SPRING 299/288, CHORUS 295/285, FILTER 285/276, DARK 257/248, PLATE 249/241, PHASER 242/234, EQUALIZER 193/187, FLANGER 147/142, COMB 128/124, COMPRESSOR 102/99, SPATIALIZER 80/78, DELAY ~0 (core 1 / core 0, the dearest of as-picked, all-min, all-max; peaks 40-100 above). Busy = frame − passes × one pass (20.0 cycles core 0, 14.48 core 1) | ✅ hardware, a different method. Conflicts with the rows above: FILTER 276-285 on FX2 here against 192 on FX1; stock's share ~960 (core 0) / 510 (core 1) here against ≈1,410 by subtraction, which would leave ~3,570 on core 0, not 3,120. Not reconciled. Bryan T (12 Oct): the core 1 / core 0 ratio is 1.03-1.04 for every effect, which an error in core 1's 14.48 would explain (DJ EQ's 331 emulated instructions match core 0's 330) |
| ❌ "FILTER credit", +768 on top of 3,120 (12–15 Sep 2026) | the four environment FILTERs are inside the 3,120 (the sum above), so adding them back double-counted; removed from the pricer | |

The datasheet's 200 MIPS is the ceiling of the silicon. It cannot say what
stock already uses, what the real frame deadline is, or what memory
contention costs; only the burn probe measures what is left after stock.

### ColdFire access costs on a unit

Bryan T, 26 Oct 2026, one unit: DTIM-timed loops at 132 MHz, measured
inside the ColdFire's share of the frame interrupt, with the OS's cache
settings (CACR `0xA50CE100`, ACR0 `0x4007E020`). ✅ hardware.

| Operation | ns |
|---|---|
| register op; on-chip SRAM load/store; cache hit | ~2.9 |
| timer register read | 30 |
| uncached SDRAM store | 36 |
| USB controller register read | 45 |
| `cpushl`, clean line | 46 |
| uncached SDRAM load | 69 |
| cached miss, load or store | ~80-83 |
| `cpushl`, dirty line | 80 |

- SRAM is 12-28x cheaper than SDRAM. Cache plus push costs about the same
  as uncached stores, so caching a transmit buffer does not help.
- `ot_emu` charges one step per instruction, with no cache and no memory or
  peripheral timing (`FAILURE_MODES.md` records the same for the meter's
  one-cycle uncached SDRAM access). A change can be cycle-identical in the
  port and several percent worse on the unit.
- Envelope (main plus REC MATRIX, IN ABCD; mean ColdFire share of the frame
  interrupt): one recording buffer about 6 points, USB streaming about 12.
  Five buffers with streaming work. Six with streaming drop frames (about
  2,700/s against 2,756) and IN overruns, at any ring size.

### The burn knob is a cycle meter

The instrument behind the hardware rows above (`make burn`, `BURN` on
SEND's second slot, `24 × BURN` = spare cycles/sample; retired 14 Oct
2026, a temporary diagnostic, not a shipping feature) and its first
measurements: `tools/harness/README.md` "The burn knob (hardware, retired
14 Oct 2026)". The measurements stand; the tool that made them does not.

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
default map ✅ (Ch. 3; confirmed on the unit 25 Oct 2026: P above `0x1fff`
holds no written word on either core, `modules/pextprobe`):

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
| `0x38000-0x38012` (19 words) | payload B's entry stub, `jsr`s into `0x30082`/`0x3008a` (stock cross-core code sharing), boot-time: payload B's own init zeroes `0x37F00-0x3FFFF` (B `P:0x040-0x04a`) right after it, and nothing executes there again | module dump |
| `0x30000-0x37FFF` | zeroed at init | `P:0x040` |
| `0x37F00-0x37F0F` in every octabam image (`0x38000-0x3800F` in stock) | the per-frame mailbox from core 1 to core 0, 16 words: B writes it (`P:0x04b-0x056` in its frame loop, `P:0x172-0x179` at frame end), A reads it into `y:$280` (`P:0x09b-0x0a2`, after the `M_DCR2` setup at `P:0x099`). `0x37F00` lies only in payload A's bank-track-4 FX2 slot, where no stock effect writes past `+0x3DA2`; B's boot zero loop covers it (`DSP.md` section 5) | disassembly; port census; `dsp_host` sentinels |
| X data tables | ~20 lookup tables uploaded to both DSPs at boot | `TABLES.md` |

The boot loader occupies `0x30000` as P; init zeroes `0x30000-0x37FFF`;
the same words are then staging and FX2 buffer. Payload B's entry stub at
`0x38000-0x38012` is the first 19 words of BusDelay's LineL; it runs once at
boot and B's init zeroes it before any effect runs, so LineL owns those words
afterwards. B's init zero loop clears `Y:0x3F00-0xBFFF` and `0x37F00-0x3FFFF`
in every octabam image (`DSP.md` section 5). A raw word scan finds
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
| `r7` state block | `$00–$83` usable; `$84–$8a` is host-owned and cannot hold state across calls (per-call scratch there is fine). ❌ retracted 5 Oct 2026: "BusDelay uses `$84`–`$88`"; its highest raw slot is `$83` (slot census of `modules/busdelay/delay_server.asm`; `CHANGELOG.md` image 41) | ✅ bisected |

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
- Assembler traps: `contributing/TRAPS.md` "Traps that have already cost real work".
