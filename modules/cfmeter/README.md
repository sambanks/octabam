# `cfmeter` — CF METER

A probe. It measures, on the unit, how long the ColdFire's frame interrupt
takes and how much time main's idle loop gets (with
[CF METER IDLE](../cfmeter-idle/README.md)), and, on core 0, how long the
DSP waits for each frame, whether the ESAI underran or overran, and the
frame period; it prints the numbers as audio on track 8. It is the
instrument for pricing ColdFire voice engines such as
[SYNTH MACHINE](../synth/README.md) (the synth renders inside the frame
interrupt) and for reading the DSP's load during normal play, where the
burn sweep (`docs/firmware/CHIP.md` section 2) has to break the unit to
read it.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | BURN | 0–127, default 0 | read on track 8 only: 2 µs of busy-wait per step at the start of every frame interrupt |
| 1 | 1 | MEM | 0–127, default 0 | read on track 8 only: MEM KB read after the burn, one longword per 16-byte line, timed into slot 7 |
| 1 | 5 | SRC | 0–127, default 0 | the region MEM walks: 0 the OS image in cached SDRAM (`0x40000400`), 1 the same through the uncached alias (`0x48000400`), 2 on-chip SRAM (`0x80000000`, 32 KB, MEM clamped to 31); other values read as 0 |
| 1 | 4 | SPAN | 0–127, default 0 | what slot 7 prints: 0 BURN (or the walk when MEM is set); 1 the two HC poll loops' time per frame; 2 the level-6 eDMA handler's time landing inside the frame interrupt, per frame; 3 and above all of that handler's time per frame (each counts / 4, mean over the segment) |
| 1 | 2 | DBRN | 0–127, default 0 | 24 × DBRN DSP cycles per sample, burnt by the insert before its sample loop (SEND's burn form) |

## Line fills

MEM and SRC price one cache line in each memory the voice path can touch,
the question Bryan T's takes left open (each voice runs at CPI ~4.4 against
the port's instruction count, and USB contention is ruled out,
`docs/firmware/ARCHITECTURE.md` "ColdFire time per frame on a unit"). The walk runs inside the frame
interrupt after the burn, so it adds to the ISR like BURN does, and it
reads only: the OS image, its uncached alias, or the SRAM.

ns per line = slot 7 × 4 × 7.58 / (MEM × 64). The same number comes from
slot 3's rise over the MEM 0 reading; the two must agree.

Procedure, on a near-empty project, transport stopped (ISR 119 µs on
Bryan T's unit, so ~240 µs of frame is free): T8 FX2 = CF Meter, then for
SRC 0, 1 and 2 in turn, MEM 8, 16, 32, 64 (SRC 2 stops at 31), an 8 s
`rec` each (a host stream open or not: the evening takes found no USB
contention on the voice path, so one state is enough). Expected: SRC 0 at
MEM 8 mostly hits (the data cache is 16 KB), MEM 32 and 64 all misses; SRC
1 every line a bus read; SRC 2 the SRAM's single-cycle reads. A frame is
362.8 µs: if slot 3 reaches ~340 µs, lower MEM. Put MEM back to 0 before
saving the project (it is a Part knob); a freeze at a high MEM clears on a
power-cycle. Not run on a unit.

## The HC polls and the nested level-6 time

SPAN splits the frame interrupt's span into what Bryan T's takes could
not: its two true waits and the interrupt that nests inside it. The ISR
polls the host port's HC bit twice per frame (`movew 0x20000004,%d0 /
tstb / blt` at `0x4000ab26` and `0x4000a90c`); SPAN 1 prints their summed
duration per frame. The level-6 eDMA handler `0x40004840` (channels 0, 1
and 7: the 7-state frame transfer, `docs/firmware/KERNEL.md`) lands inside
the frame interrupt whenever it fires before the `rte`; SPAN 2 prints the
handler time that landed inside, per frame, SPAN 3 all of it. ISR mean −
SPAN 1 − SPAN 2 is the ISR's own instructions and stalls. The two UART
handlers (level 6 as well) are not timed. Not run on a unit.

## Open

- Whether DTIM3 runs at 132 MHz on the unit (slot 5 answers it).
- Interrupts shorter than the idle loop's threshold (2 × its shortest
  step + 8 counts) count as idle time.
- The DSP slots on the unit: a poll's cost in cycles (the `dbrnD` takes,
  `remixes/test/cfmeter/README.md`), whether TUE/ROE hold between frames
  as the manual says (0 and 0 in every 4 Oct take), and timer 0 on core 0
  (probe 55 ran it on core 1). ESAI_1 reads flagged every frame on the
  unit as in the emulator: a sticky bit on an unused port, inferred.
- Slots 8..15 read core 0 only; CF METER on tracks 1..4 prints zeros
  there (payload B has no spin store and no ESAI).

## How it works

- **Clock.** DMA timer 3, `0xfc07c00c`. The firmware sets `DTMR3 =
  0x000b` at `0x400209c0` (enabled, internal bus clock, prescaler 1,
  reference `0xffffffff`) and timestamps with it at `0x4000169a`. At the
  132 MHz bus clock one count is 7.58 ns; slot 5 prints the frame period
  in counts, which checks that rate against 16 / 44,100 s.
- **Frame interrupt, entry.** Main installs vector `0x41` with `pea
  0x4000aad0` at `0x4001fbf8`; the build rewrites the operand to `m_isr`.
  `m_isr` stamps the entry, busy-waits BURN × 2 µs (BURN = T8's FX2
  page-1 slot 0, read from the live lane `0x80000a20`) while T8's live
  FX2 id (`0x80000ed3`) is CF METER's `0x0e`, and enters the stock
  handler.
- **Frame interrupt, exit.** Every exit of the stock handler runs its
  epilogue at `0x4000d9a6` (`moveml`, `lea`, `rte`); `m_tail` replaces it:
  duration = exit − entry into a sum, a count and a maximum, then the
  epilogue. USB's audio producer (`0x4000d9a0`, the instruction before)
  is inside the measured span.
- **Publisher.** In `m_tail`, every 125 ms (16,500,000 counts): eight
  values into a table, the displayed slot k advanced through 0..15. Every
  frame, while T8's live FX2 is CF METER: N_k (0 for k ≥ 8) into T8's FX2
  page-2 lane bytes `+0x38/+0x39` (word `$c`), 8192 into `+0x3a/+0x3b`
  (word `$d`) and k into `+0x3c/+0x3d` (word `$e`). The copier
  `0x4000cae8` delivers them to the DSP record
  (`docs/firmware/PARAM_PAGES.md` section 5c, section 6).
- **The DSP meter.** The insert (`meter_out.asm`, FX2 id `0x0e`, 204
  words) runs on T8, which is core 0. Once per frame (one step of
  `x:$415`, the housekeeping at `P:0x549`) it reads the spin count core
  0's wait for the next frame stores at `P:0x92` (`x:$3f81`: the polls of
  `M_DSR2` at `P:0x4b-0x53`), the ESAI status register (`x:$ffffb3`; TUE
  bit 14, ROE bit 7) and ESAI_1's (`y:$ffff93`), and timer 0 (`x:$ffff8c`,
  free-running at CLK/2 from init, probe 55's setting), into min / max /
  count slots of its r7 block. When k reaches 8 the slots are copied to
  the print copy and reset, so each printed window is the 2 s before slot
  8. TUE and ROE hold until the status register is read (the DSP56300
  family manual: cleared by a read of SAISR followed by the next transmit
  writes / receive reads) and stock reads it only at boot, so one read
  per frame sees every event since the last (inferred from the manual;
  not measured on the unit). DBRN burns 24 × DBRN cycles per sample
  before the sample loop: the spin count must fall by it, which
  calibrates a poll's cost in cycles.
- **Readout.** The insert writes L = value / 2 and R = word `$d` / 2 as a
  square wave that flips sign every block, replacing the track's audio;
  value is word `$c` for k < 8 and its own slot for k ≥ 8. N = 8192 ×
  rms(L) / rms(R), whatever the gain after the slot.

| k | N |
|---|---|
| 0 | 0 (sync) |
| 1 | 8192 (reference; L/R = 1) |
| 2 | idle counts / segment × 16384 (0 without CF METER IDLE) |
| 3 | frame interrupt, mean duration, counts / 4 |
| 4 | frame interrupt, longest in the segment, counts / 4 |
| 5 | frame period (segment / interrupts), counts / 4 |
| 6 | the idle loop's shortest step, counts |
| 7 | BURN, counts / 4; with MEM set, the walk's mean duration per frame; with SPAN set, the HC polls or the eDMA handler (SPAN above), counts / 4 |
| 8 | core 0 spin count, min over the window (polls) |
| 9 | core 0 spin count, max |
| 10 | frames with ESAI TUE set |
| 11 | frames with ESAI ROE set |
| 12 | frames with ESAI_1 TUE or ROE set |
| 13 | frame period on timer 0, min, counts / 4 (CLK/2: 9,064 nominal) |
| 14 | frame period on timer 0, max, counts / 4 |
| 15 | frames in the window (5,512 nominal) |

A late frame (the DSP arrives at the wait after `M_DSR2` passed its
value) waits for the ring to come round again: slot 9 jumps by a whole
frame's polls. Values clamp at 32,767.

`tools/harness/cfmeter.py` decodes a capture (a WAV, T8 on USB channels
15/16 by default) or the port's `--block-dump`; a cycle is 2 s, and the
decoder needs two sync edges, so a take is 6 s at least.
