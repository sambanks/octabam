# `load-meter` — LOAD METER

The frame interrupt's share of the ColdFire, each DSP core's busy time per
frame and the cost of each effect call, for BRAIN's PERFORMANCE screen
(`modules/brain`: BRAIN > PERFORMANCE).

The frame interrupt (vector `0x41`, handler `0x4000aad0`) runs about
2,756 times a second, every 362.8 µs. LOAD METER stamps its entry and its
epilogue on DMA timer 3's free-running count (132 MHz bus clock), sums each
interrupt's duration and keeps the longest, and every 0.5 s publishes the
window to `lm_stats` (also `LM_STATS`): `{seq, window, sum, count, longest}`
in timer counts. BRAIN's view shows the share, the average and longest run
in µs, the interrupts a second, and the peaks since the view opened.

| site | stock | stub |
|---|---|---|
| `0x4000aad0` | `lea %sp@(-252),%sp / moveml %d0-%fp,%sp@`, the handler's prologue | `lm_in`: the prologue replayed, the entry stamp |
| `0x4000d9a6` | `moveml %sp@,%d0-%fp / lea %sp@(252),%sp / rte`, the epilogue | `lm_out`: the duration summed, the window published, the epilogue replayed |

The sites are BOOT TRACE's entry and CF METER's epilogue: beside either, the
registry adds [HOOKS](../hooks/README.md), which replays the prologue and the
epilogue once and calls each module's routine (BOOT TRACE's note first at the
entry, so LOAD METER's stamp excludes it; LOAD METER first at the epilogue).
That pairing has run under Unicorn only (verify_hooks), not on a unit. The share counts the frame
interrupt alone: the other interrupts and the tasks are not in it.

## The DSP cores

Each core measures its own busy time per frame and core 0 publishes both
cores' figures to the ColdFire in bytes it already sends. It is always on,
on both cores, whatever the tracks hold: no FX slot and no effect id.

**The meter** (`dsp_meter.asm`, both payloads; `DspHook`s with the same
stock words on each, and core 0's publish on payload A alone):

| hook | A | B | stock | does |
|---|---|---|---|---|
| frame start | `P:$8c` | `P:$74` | `move r5,x:>$206`, just after the frame wait | timer 0 (CLK/2) stamped; period = the advance since the last start; timer 0 armed the first time (TRM, TE; no interrupt enable) |
| frame end | `P:$54b` | `P:$340` | `move #>$421,r6`, before the jump back to the wait | busy = the advance since this frame's start |
| publish | `P:$2ec` | none | `move x:>$205,r0`, just after the MAIN pack | core 0 writes the 17 bytes below |

The figures live in the shared window at `X:$37F10-$37F2F` (`Claims.dsp_ranges`;
inside payload A's bank-track-4 FX2 slot past where any stock effect
writes, and in the range payload B's boot loop zeroes): core 0's block at
`$37F10`, core 1's at `$37F18`, so core 0 reads core 1's figures. The core
switch is the per-payload base literal (`YBase.ALWAYS`); no modifier
register is written (the address registers used are ones the stock code
right after each hook relies on being linear).

**The path to the ColdFire.** Measured under the port with `--block-dump`
(11 Oct 2026): what the DSPs send each frame is core 0's 512-word pull
(channel 1, the 256-word read-back of the eight tracks; channel 6, 128
words of MAIN and CUE at `0x80005e60`; channel 7, 128 words of the inputs)
and core 1's 256-word read-back. Every word is audio, so there are no spare
words. The packer (`P:$55a`) stores each sample's low word as `(sample &
$ffff) << 8`, so the low byte of every low word is always zero. Core 0 adds
17 bytes there, in MAIN's first 17 longs, right after the packing: the
ColdFire pulls the block before core 0's frame ends (measured: bytes
written at the frame end never arrived), so the busy and period sent are
the last finished frame's:

| byte | holds |
|---|---|
| 0 | `$a5` |
| 1 | core 0's frame count, low byte |
| 2-4, 5-7 | core 0 busy, period (timer-0 counts, high byte first) |
| 8-10, 11-13 | core 1 busy, period |
| 14, 15 | reserved, zero (core 0's ESAI TUE and ROE frame counts until 13 Oct 2026: the words went to OTOP, which `octabam-bus` could not hold otherwise) |
| 16 | the sum of bytes 0-15, mod 256 |

`meter.s`'s `lm_scrub` (a detour at `0x4000d310`, the `tstl` before the
stock recorder reads MAIN) copies the bytes out and zeroes them, before the
recorder (`0x400068e4`), USB's audio producer and STEMS read the buffer: every
reader sees stock's bytes; it runs once per frame interrupt (its pass
count equals the interrupt count, `verify_load_meter` every), ahead of the
recorder's call at `0x4000d340` and USB's audio producer's at `0x4000d9a0`. STEM
REC reads MAIN from the transfer routine (`0x40004b12`), outside that
order, and needs none: the meter's bytes are only in the low byte of MAIN's
longs, which STEM REC never writes to a file (its 16-bit path keeps the top
16 bits, its 24-bit path shifts the low byte off). Either order gives the
same files; the two share `octabam` since 28 Oct 2026. A record whose magic, sum, period (20,000 to
60,000 counts; nominal 36,256) or busy (at most its period) is wrong is
counted as bad and changes nothing. CF METER's page-lane route (an FX2
insert printing values as audio) was the alternative; it takes a track and
a slot, which this meter must not.

**The screen** (BRAIN > PERFORMANCE, tabs LOAD and PROCS), a list scrolled by UP and DOWN. First a bar
per processor: `CFIRE` the frame interrupt's share now with its peak since open
as a mark, `DSP0` and `DSP1` each core's busy over its frame now with the
peak mark; then `WORST FRAME` (the longest single run of the frame interrupt
as a share of the 362.8 µs frame, `OVER` at 100%); then the cost of each effect call
(below), sorted. `-` = no sample yet, `?` = only bad records since the last
refresh. While the screen is closed nothing draws and the DSPs and the host
port carry the same traffic as with it open (`verify_load_meter` closed); the
scrub runs every frame either way.

**OTOP, the cost of each effect call.** Four more DSP hooks on the stock
dispatcher (`docs/firmware/DSP.md` section 5: one routine per payload, FX1
then FX2 for each track position, each with a pre-call, an init on a changed
id and the process call) stamp timer 0 before and after each slot's calls:
the start at `move a,x:>$20a` (A `P:$4b2` FX1, `$4e8` FX2; B `$2a7`, `$2dd`),
the end after the process call at `move x:>$213,b` (A `$4d8`, B `$2cd`) and
`move x:>$206,r0` (A `$50e`, B `$303`). Each core keeps the cost of the
frame's eight calls in dispatch order in X:`$37F40` (core 0) and `$37F48`
(core 1), its block + `$30` (the frame start hook resets the pointer, kept in the block's +4; the start stamp in +3); core 0 publishes one slot
a frame, round robin over the 16, as a second record after the meter's
(`$b4`, the slot, three cost bytes, their sum: bytes 17-22 of MAIN's low
bytes). The ColdFire keeps per slot `{last, sum, count, max}` in `lm_ot`
(also `LM_OT`; `lm_ot_reset` clears them when the screen opens). A slot is
sampled about every 6 ms. The figure is elapsed time on the chip's own timer
(CLK/2, 2 cycles a count), so cycles a sample = counts ÷ 8; a row's percent
is its share of the core's frame. Slot 0..7 are payload A's (tracks 5-8: FX1,
FX2 of the first position, then the next), 8..15 payload B's (tracks 1-4).
`SYSTEM A` and `SYSTEM B` are each core's mean busy time beyond its effects:
the stock mixer, AMP and everything else. The stamps read and write only
registers that are dead at the hook sites (`a` and `b` and `r2`, `r3`; the
start hook saves `a` through the displaced store) and no modifier register;
`verify_load_meter` compares USB's audio-out ring with the stamps in and
replaced by no-ops (`LM_NOOT`): byte-identical. They cost 101 words a
payload (257 in all with the meter). Measured only under the port, whose
timer moves in 1,024-count steps, so single calls read 0 or 1,024 and only
the means over many samples mean anything; nothing here has run on a unit.

Credit: the view and its rules (bounded reads, `-` and `?`, the refresh
counter, the zero-cost close) follow Hamish Renton's ([SamplesAndSnacks](https://github.com/SamplesAndSnacks)) LOAD
view design for the Machinedrum. The code here is octabam's.

**Payload room.** 193 words on each payload (257 with OTOP before the cost cells
were laid out from one per-core pointer and the ESAI counts dropped, 13 Oct
2026; 156 without OTOP). The remixes carrying LOAD METER are `octabam-bus` and
`octabam-inserts`: on `octabam-bus` payload A has 14 words free, payload B 575
(the build report, 13 Oct 2026). A remix it does not fit is refused by the
build's region fit, by name.

**Calibration.** `LM_BURN=N` builds put a DO loop of N one-cycle `nop`s
at each core's frame end, before the busy stamp: N core cycles plus the
DO's setup, a constant that cancels between two burns. Timer 0 counts at
CLK/2, so N cycles add N/2 counts to busy. Under the port one frame's
busy cannot show that: the vendored emulator updates its timers every
2,048 instructions (`dsp56kEmu/timers.cpp`, `m_timerupdateInterval`), so
timer 0 reads in 1,024-count steps. A first gate run compared single
frames and saw a 1,000-cycle and a 2,000-cycle burn both add about 1,024
counts: the step, not the model. `lm_scrub` sums each core's busy over the
open window (`lm_dsum`); the frame length is not a multiple of 2,048
instructions, so the mean resolves below the step, and the gate compares
means. It reports each rise's error against N/2. The port counts
instructions, the chip cycles; the chip's ratio is a hardware-round item.

## On a unit

First readings over USB (`tools/hw/load_meter.py`, vendor request `0xc0/0x57`),
24 Oct 2026, image A1 (`octabam-bus`, `BUILD=A1`), project `OCTAMX01` (BASE
layout: FX1 NONE, FX2 SEND at 0 on T1-T7; four stimuli on eight FLEX tracks,
one trig on step 1 of 64 steps), 10 s each, 21 published windows:

| | ColdFire share mean / max | longest frame-interrupt run | DSP 0 busy/period | DSP 1 busy/period |
|---|---|---|---|---|
| stopped | 24.2 % / 24.2 % | 106.7 µs (29 % of a frame) | 25.4 % | 18.5 % |
| playing (host START, 120 BPM) | 48.8 % / 49.4 % | 336.5 µs (93 % of a frame) | 25.4 % | 18.5 % |

Per effect slot the cost is 46-60 counts for an FX1 NONE and 432-497 counts
(1.2-1.4 % of a frame) for a SEND, 113 for slot A4 FX2; the DSP figures did not
move with the transport. The 93 % is the longest single run in the window: all
eight voices start on the same step. The meter reads timer counts; no
independent measurement of them has been made. Before the A1 image the
request returned a stale `lm_stats` (the window stuck for minutes, then jumping
100 windows) and an alternate request failed with 0 bytes
(`docs/contributing/TRAPS.md#trap-ep0-dma`).

## Hardware round

Every % and µs here is from the port, whose cycle table and timer are not
the chip's:
- timer 0's rate (CLK/2) and the nominal period 36,256 counts;
- busy and period per core against a known load (a burn, as `LM_BURN`);
- MAIN, CUE and USB audio bit-identical with the meter on (a recording of
  MAIN, the USB stream);
- the view's text widths on the unit's LCD.

## Frame count

Core 0 counts frames in `x:(r1+6)`, 24 bits, wrapping at 2^23 (a multiple of
16, so the OTOP slot index continues). Before the wrap, bit 23 of the count reached
`move a,n1` with A2 stale and the unit's frame interrupt stopped 8,388,607
frames (50.7 minutes) after power-up (docs/contributing/TRAPS.md#trap-frame-count). `LM_FRAME0=N` starts
the count at N in a gate build.

## Measured

Both DSP cores under the port (`verify_load_meter`, 12 Oct 2026, project
BRAINPRJ, the view open for 4 s of emulated time): 89,783 good records and 2 bad
(the first frames, before timer 0 is armed) out of 89,785 frame
interrupts; core 0 busy 20,480 of a 36,864-count period, core 1 17,421 of
36,028; the view read `DSP0 57%/ 60% M0`, `DSP1 51%/ 54%`. The mean busy
rose by 508 and 1,504 counts on core 0, 500 and 1,503 on core 1, for
1,000- and 3,000-cycle burns (expected 500 and 1,500: errors +1.6%, +0.3%,
-0.1%, +0.2%). USB's audio-out ring was byte-identical with the publish on
and off; 9.0 host commands per frame interrupt with the view open and
closed.

Under the port with `--frame` (the frame timer without the DSP cores, 11
Oct 2026, `verify_brain`'s `load` cases): windows published every 0.5 s,
2,758 interrupts a second, 22% share, 82 µs a run. The port's timing is not
the chip's; the numbers on a unit are a hardware-round item.

## Gates

- `tools/verify/verify_load_meter.py`: with both DSP cores under the port,
  the records arrive and pass, the view's DSP rows carry numbers, the
  scrub zeroes MAIN's byte every frame and runs once per frame interrupt,
  USB's audio-out ring is byte-identical with the publish on and off
  (`LM_NOPUB`), the closed view draws nothing and moves the same host
  traffic, nothing stock writes the claimed words but payload B's boot
  zero loop, and an injected burn (`LM_BURN` builds) raises each core's
  busy by N/2 counts.
- `tools/verify/verify_usb_load_meter.py`: the USB module's vendor request
  `0xc0/0x57` (wValue low 0, 1, 2: `lm_stats`, `lm_dsp`, `lm_ot`; 20, 48 and
  256 bytes) returns the meter's cells, equal to the same words peeked at
  the symbol, with seq rising, a 0.5 s window, plausible periods and busy,
  sampled slots; wValue 3 STALLs. `tools/hw/load_meter.py` reads them from
  a unit (`--watch`, or `--for N --json` for a summary over N seconds).
- `tools/verify/verify_brain.py` (BRAIN's gate) runs the PERFORMANCE screen on the
  `octabam-bus` remix, which carries this module.
- `tools/verify/verify_dsp_vectors.py`, `verify_two_core` and `make
  verify-bus` (audio bit-identity) for the DSP section.
