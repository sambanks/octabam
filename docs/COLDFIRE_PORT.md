# The ColdFire port (`tools/ot_emu`) — a headless Octatrack in C++

> **What this is for.** `tools/emu_rtos.py` (route A) runs the firmware's own
> scheduler and is the **oracle** every claim here is measured against — but it
> costs about 120× real time, models no audio, and stops at the DSP host port.
> `tools/dsp_host` runs both DSP cores at roughly real time and knows nothing
> of the ColdFire. This is the join: one process, both halves, fast enough to
> drive interactively. Deliberately **not** a plugin — no JUCE, no UI, no audio
> device. A library and a CLI you can script and intercept.

Confidence markers as in `CHIP.md`: ✅ measured, 🟡 inferred, ❌ retracted.

## Where it came from

Sam found `joelanders/gearmulator-md-mm` (7 Sep 2026), a full-system
Machinedrum / Monomachine emulator that runs its firmware in **real time** as a
plugin: a Musashi-based ColdFire, two DSP56303s over HI08, one deterministic
interleave scheduler paced by the mixer DSP's frame counter. It proves the
architecture on the cousin machine. What it does **not** give us is the
Octatrack's CPU: its Musashi is ColdFire **V2** (`MCF5206E`, ISA_A), with no
EMAC, none of the V4e instructions this firmware uses everywhere, and none of
the MCF5445x peripherals.

So we vendor the small piece that helps — `vendor/mc68k`, its submodule: a
standalone static library with Musashi, ColdFire mode, an HI08 host-port
register file and peripheral scaffolding, no JUCE anywhere — and write the rest
against route A as the specification. Licences: mc68k is GPLv3 and Musashi is
Karl Stenerud's; the same posture as `vendor/dsp56300`, which this repo has
vendored all along. **Tooling and patches are shared; built binaries are not.**

## Milestone O1 — boot to the RTOS handoff ✅ (7 Sep 2026)

```sh
make emu-cf                    # or: cmake -B out/emu -S tools/ot_emu && cmake --build out/emu -j8
./out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --profile --periph
```

**It reaches `trap #0`, and it agrees with the oracle:**

| | route A (`emu_bringup.boot`) | `ot_emu` |
|---|---|---|
| handoff PC | `0x40000e46` | `0x40000e46` ✅ |
| auto-poke 1 | loop `0x4000f9e2`, wrote `0xffff` to `0x0` | identical ✅ |
| auto-poke 2 | loop `0x4000fa02`, wrote `0xffff` to `0x2000` | identical ✅ |
| instructions | 10,000,000 (counted in 500k bursts) | 10,170,953 exactly |

**Speed, measured on this machine: 39.1 M instructions/s**, boot to handoff in
**0.26 s** — about **26× route A's ~1.5 M/s**. For scale, a 16-sample DSP frame
is ≈63,800 ColdFire instructions, so this is ≈613 frames/s against the 2,756
real time needs: **≈4.5× slower than real time today**, before the one obvious
optimisation below. Real time is genuinely in reach, which was the open
question when the port was scoped.

## Milestone O2 — the EMAC, and its gate ✅ (7 Sep 2026)

**The gate was written FIRST and watched to fail**, which is the whole
discipline: `tools/ot_emu/test_emac.cpp` encodes hardware's semantics from
`emu_bringup.emac_selftest` (fractional `macl 0xc00 x 0x200000` -> 3, the
negative operand -> -3, `msacl` SUBTRACTS -> -3) and reported all three FAIL
against an emulator with no EMAC before a line of it existed. It passes now.
`ctest` in the build dir runs it beside the vendored core's own ColdFire
timing, divide and HI08 tests: **4 tests, all passing.**

What the implementation had to get right, each of which is a defect Unicorn
shipped (`RTOS_FORK.md` §10.16):

- **Fractional mode is a signed product shifted LEFT ONE, upper 40 bits
  accumulated** — so `movclrl` yields `(a*b) >> 31`, not `>> 32`. Off by that
  one bit is what wrote 10,336 for Bryan's 20,672 and got explained away as
  "2-sample units" for a day.
- **MAC vs MSAC comes from bit 8 of the EXTENSION word**, never the opcode
  word. Reading it from the opcode is what made every `msac` add.
- The EMAC's whole state (four accumulators, their extension bytes, MACSR)
  lives in this layer, because Musashi's ColdFire state has none.

✅ **And one structural finding, measured the moment the gate ran:** every EMAC
opcode is `0xAxxx`, i.e. **A-line**, and Musashi routes A-line to
`m68ki_exception_1010` — a *different* path from the illegal-instruction
callback, with no callback of its own. So the V4e layer never saw them: the
test failed with D0 still holding the value the program's first instruction
loaded. The EMAC is dispatched from `Machine::run`'s own loop instead, reusing
the opcode fetch already made for the handoff check, which leaves the vendored
Musashi unpatched. `mov3q` (`a340`) rides the same path.

⚠️ Encodings for all of it came out of `m68k-elf-as -mcpu=5475`, listed in the
source beside each handler. ❌ **Retracted from O1's work list:** `byterev` and
`ff1` are **not** V4e — the assembler refuses them for `-mcpu=5475` and names
the parts that do have them (ISA_C). Nothing needs them.

### What had to be built, and what each cost

**1. The V4e instructions, as trap-and-emulate (`v4e.cpp`).** Musashi's opcode
tables are GENERATED, and ✅ the generator checked into the tree is **not** the
one that produced the checked-in tables: regenerating rewrites every handler
signature (the upstream fork threads a `m68ki_cpu_core*` through them, the
shipped generator does not), an 18,984-line diff. So the tables are frozen.
Instead, `m68ki_exception_illegal` calls the illegal-instruction callback
**first** and takes no exception if it returns nonzero, which makes that
callback a legal extension point: decode, execute, advance the PC over the
extension words, return 1.

Implemented so far: **MVS/MVZ** (`0111 rrr 1 oo eeeeee`, `oo` = MVS.B / MVS.W /
MVZ.B / MVZ.W) with a full effective-address reader. ✅ The encoding was pinned
against `m68k-elf-objdump -m m68k:cfv4e` on the real image, never against a
reading of the manual — the boot's own first two are
`4000043e: 73c1 mvzw %d1,%d1` and `40000440: 71c0 mvzw %d0,%d0`. That covers
**961,786 of the boot's 10.2M instructions**, and the boot needs nothing else.

⚠️ **Still to come**: `mov3q`, `byterev`, `ff1`, and the whole **EMAC**. The
EMAC is the one to be careful with — `RTOS_FORK.md` §10.16 is a week lost to
three defects in *Unicorn's* EMAC, each producing a confident wrong finding for
a day. `emu_bringup.emac_selftest` already encodes the measured contract
(`macl` fractional `0xc00 × 0x200000` → 3, negative → −3, `msacl` → −3) and
should be ported as a CTest **before** any EMAC handler is trusted.

⚠️ **And watch the cost model**: an exception round trip per instruction is
fine for moves scattered through the code, and may not be for the frame
builder, which runs EMAC in bulk (~7,400 instructions per frame). If it bites,
these handlers become the reference an opcode-table implementation is diffed
against.

**2. Byte-addressable peripheral overrides.** Musashi composes a 32-bit
peripheral read from two 16-bit reads, so an override stored whole and returned
per access is truncated to the access width. The PLL register read back
`0x0000ffff` instead of `0x16000000` and the firmware spun forever in its clock
check at `0x4000f9e8`. Overrides are per byte now.

**3. The stall detector and auto-poke, ported from route A field for field.**
A PC confined to a 64-byte window across four 500k bursts, with fewer than
2,000 stores in between, is a poll rather than a memset; `tryAutoPoke` then
looks for `move.w (abs),d0 … cmpi #imm,d0` around it and writes the immediate
to the flag **at the load width** — two bytes, not the compare's width, or the
low word reads back wrong. Both flags it finds match route A's exactly. These
are the places the emulator stands in for hardware nobody has modelled yet, and
the CLI prints them every run rather than hiding them.

## Milestone O3 — the first peripherals, gated ✅ (7 Sep 2026)

`periph.{h,cpp}`: the **PIT** and the **INTC**, translated from route A rule
for rule, with each rule's measurement or failure carried across rather than
summarised. `tools/ot_emu/test_periph.cpp` checks fourteen of them; `ctest`
now runs **5 tests, all passing** (emac, periph, and the vendored core's
timing, divide and HI08 tests).

The rules worth naming, because none is obvious and each was a silent failure
in route A first:

- **A FORCED interrupt ignores the mask** (MCF54455RM rev 5 §17.2.3). The
  sequencer tick is source 32, installed with ICR 3 and never unmasked
  anywhere in the image; masking it left route A running 400 frames with
  **zero ticks**. ✅ measured there, gated here.
- **CIMR clears MASKALL along with its source.** 🟡 inferred, and the reason
  is carried too: nothing in the image ever writes IMRH/IMRL (a literal scan
  found no site), the firmware unmasks only through CIMR, and the unit
  plainly takes interrupts.
- **A source with ICR 0 is never delivered**, whatever else is true.
- **PIT PIF is write-1-to-clear.** Treat the write as a set and the ISR
  re-enters forever.
- **The PIT prescaler input is a KNOB, not a fact** (264 MHz by default; off
  the 132 MHz bus clock every period is 2× longer). What pins it is the
  sequencer's own tick count, which is M6c's gate.

## Milestone O4 — the run loop: the kernel runs ✅ (8 Sep 2026)

`rtos.{h,cpp}`: the sample clock, the peripheral models installed and seeded,
interrupt delivery, and the loop. **The firmware's own scheduler runs**: ten
tasks created with the exact fields route A measured, eleven TCBs dispatched,
first switch boot → main, the M6a gate reached at **204.88 ms** against route
A's 204.95. `ctest` is **6 tests, all passing** (the new `rtos` one is route
A's M6a gate, self-contained).

**The oracle diff passes** (`tools/ot_emu/oracle.py`).

> ❌ **RETRACTED 8 Sep 2026: "8 of 8 fields".** The diff's summary counted
> every field in the golden, including three it has never compared —
> `gate_ms`, `pit0_fired` and (later) `serial_sent`, all of which track the
> `ips` knob. O4 actually agreed on **6 compared fields**: `handoff_pc`,
> `auto_pokes`, `created`, `ran`, `first_switch`, `dispatches`. The claim was
> inflated by the script, not by the port — nothing about O4's result changes,
> only what it is honest to say about it. `oracle.py` now counts only what it
> compared and prints a `REPORTED` line for the rest. Same defect as a watch
> that prints nothing: a gate that takes credit for fields it did not check
> (RTOS_FORK §10.3b).

### The one deliberate divergence from route A

Route A hand-rolls exception entry and exit because Unicorn's CFV4E will not
dispatch them — its VBR is a no-op and its `rte` never arrives. ✅ The vendored
Musashi does both: `m68ki_stack_frame_0000` carries the ColdFire 2-longword
frame (format `4 | A7[1:0]`, vector, SR, PC — MCF5206e UM 3.4) and
`m68ki_jump_vector` reads REG_VBR, which the firmware sets itself with a
`movec %a0,%vbr` at 0x40000db6 (checked: it reads 0x40000000 after a boot). So
this port lets the CPU take its own exceptions — the hardware mechanism rather
than a model of it — and the oracle is what proves the two agree.

### What it cost, each measured

- **32-bit accesses must arrive whole.** Musashi composes a longword from two
  16-bit halves unless the machine provides `read32`/`write32`, and a
  peripheral register is not two halves: the DSPI status word came back as
  `0x0000ffff`, so the firmware's `(SR >> 4) & 15 == 2` wait at 0x4001c504
  could never match and main parked there forever with **no task ever
  created**. The same class as the PLL truncation that stalled the boot in O1.
- **DSPI and the UARTs moved from O5 into O4**, because the gate cannot be
  reached without them — that wait above is on main's path to its init list.
  O5 shrinks accordingly.
- **A queued interrupt is not a level-sensitive line.** The core holds an
  injected vector until it is acknowledged, so a source that asserts and then
  deasserts before the CPU can take it — the PIT's PIF, which the scheduler
  clears at 0x40000588 while running at mask 7 — was still delivered
  afterwards, firing the handler again for an expiry that no longer existed.
  It showed as **twice the oracle's dispatches**, every other one resuming at
  the scheduler's own entry (0x40000550), because the stale interrupt landed
  in the one-instruction window before `movew #0x2700,%sr` raises the mask.
  Fixed by withdrawing a line that has gone away (`removePendingInterrupt`).
- ❌ **O2's retraction is itself retracted: `byterev` and `ff1` ARE used.** The
  assembler refuses them for `-mcpu=5475` and objdump prints `.short 0x04c2`
  rather than decoding it — but the firmware contains one at 0x4004098e, in
  the task-creation path, and the run loop stopped there. *A toolchain that
  will not assemble an opcode is not evidence the part lacks it; the image
  is.* Route A had already met this and written `_isa_c_shim`; its semantics
  (ff1 counts leading zeros and sets N and Z from the **source**) are what the
  port implements.

### What the gate can and cannot assert — measured, not assumed

The first version of the gate compared the resumed PC of every dispatch and
the whole dispatch sequence. ✅ **Both are functions of the `ips` knob**, which
route A itself calls a guess (`RTOS_FORK.md` §6). Swept on the same image:

| | pc[1] | pc[2] | dispatches | tail |
|---|---|---|---|---|
| ips 3990 | `0x4001fab6` | `0x400209ac` | 51 | …storage, **sys**, keyrepeat, ui |
| ips 3995 | `0x4001faae` | `0x400209a8` | 51 | …storage, **sys**, keyrepeat, ui |
| ips 4100 | `0x4001faae` | `0x4009acf0` | 49 | …storage, keyrepeat, ui |
| route A | `0x4001fab6` | `0x400209a4` | 50 | …storage, keyrepeat, ui |

Where a *preempted* task resumes, and whether one extra timer preemption slips
between two switches, both move with the clock. What does **not** move is the
order in which each task first runs — ✅ identical in the oracle and at both
clock settings:

```
main, voice, p2a, p2b, p2c, p1b, engine, sys, storage, keyrepeat, ui
```

which is route A's own documented cascade (strict priority after the first
tick). So that is the strict criterion, along with the created fields, the set
that ran, the first switch and each task's first-run time within one PIT
period; the resumed PCs and the preemption count are **reported as notes**.
The gate is still sharp: at ips 4100 it fails on first-run times.

## Milestone O5 — the rest of the memory, and what the oracle really does ✅ (8 Sep 2026)

O5 was written as "the remaining peripherals" and its list was nearly empty:
the UARTs and the DSPI had already moved into O4, leaving two memory spans
route A maps in `install` and a serial byte count to compare. Both were done
in minutes, **and the gate passed on the first run** — which, by the standing
rule that a gate which has never failed proves nothing, is where the milestone
actually started.

### The two maps, translated

`Rtos::install` now adds route A's own two spans, with its reasons:
`0x00010000+0x1f0000` so the test-mode magic word at `0x1ffffe` reads **zero**
(`0x4003232c` takes `0xdcba` as a test-mode flash), and `0x10100000+0x1000`
for the settings reset's off-by-four past the SRAM window. ✅ Both are visible
in the port's own access log: exactly **one read at `0x1ffffe`** (pc
`0x4003233e`) and exactly **four byte-writes at `0x10100000`**, which is the
off-by-four reproduced rather than assumed. Neither changed the gate.

> ❌ **RETRACTED 8 Sep 2026 (O7): the MECHANISM below is wrong.** The four
> spans are real and the measurement stands, but route A does **not** grow
> them through `_prime_menu`'s auto-mapping hook. That hook is installed only
> by the menu RENDER helpers (`menu_children`, `render_menu`, `render_fx2`,
> `render_playback`, `render_fx1`), **none of which run on the golden path** —
> so it is never installed there, and route A really does fault on unmapped
> memory. What actually maps the four spans is `emu_card.attach`, explicitly,
> with its own comment naming what lives in them (the PCM pool, the sector
> buffers, the delay rings, the on-chip SRAM around the boot's window). The
> two O5 added in `install` are route A's too. So the golden run has them
> because it has a **card**, which is also why route A faults at
> `0x100fff04` without one: that address is inside the card's own
> `0x100c0000+0x40000` map.
>
> **Why the difference matters, and it is not pedantic:** an explicit map has
> KNOWN BOUNDS. Route A faults on a wild pointer outside them; this port's
> auto-map absorbs it silently. O7 adds the four spans explicitly
> (`Rtos::mapCardMemory`), and with a card attached the auto-mapped count
> falls from **20,348,051 to 4** — the residual three addresses
> (`0x04020000`, `0x100a0000`, `0xffff0000`) are boot-time touches outside
> every map route A has, and so are places the two emulators still differ
> silently. That is the honest work list the auto-map was hiding.

### ⚠️ The finding: route A does not fault on unmapped memory, and this port was not the same machine

The port answers **all-ones** for an address in no region and drops the write;
Unicorn raises `UC_ERR_READ_UNMAPPED`. That difference was assumed to be
harmless because route A "always faults". It does not. `_prime_menu`
(`emu_bringup`) installs an unmapped-access hook that **maps a zero page and
returns True** — a workaround for a stale formatter pointer in the menu
render — and it stays installed for the rest of the run. So in the golden
configuration route A *grows*:

| | measured |
|---|---|
| regions after the boot | 9 |
| regions at the M6a gate | 15 |
| grown by `install`'s two explicit maps | `0x10000-0x1fffff`, `0x10100000-0x10100fff` |
| grown by the auto-map hook | `0x10000000-0x100affff`, `0x100c0000-0x100fffff`, `0x42000000-0x45ffffff`, `0x48100000-0x4fffffff` |

Those four are, page for page, the four spans this port was answering all-ones
for — **20,348,069 accesses** (14,073 read, 20,333,996 written). Their two
largest sources are both plain literal loops, disassembled rather than
inferred:

- `0x400209a4` is a `moveml`-based `bzero`, called on **64 MB at
  `0x42000000`** — precisely the gap between route A's two SDRAM regions.
- `0x40002fb4` is `lea 0x4f502c10,%a0` / `movel #705664,%d0` and a 16-byte
  clear loop: **10.8 MB**, both bounds hard-coded in the image.

✅ Without a project route A really does fault (`unmapped read 0x100fff04 at
pc 0x4001fa4e`), which is the behaviour its own note in the work order
describes — but the oracle is the golden configuration, and there it grows. So
the port now grows too, at route A's granularity (`addr & ~0xfff`, 4 KB): a
first touch allocates a **zeroed** page and the access proceeds. `19,385`
pages, 77 MB, on the run to the gate. `setAutoMap(false)` restores the
all-ones stub, and then the counter is a work list again.

### ⚠️ The serial byte count was an artefact of the missing memory

The count agreed at **4831** before the auto-map change and disagreed
(**5731** against route A's 4831) after it. The temptation is to read that as
the change breaking something. It is the opposite: the port's transmit ring
lived in memory that was being dropped, so the bytes were never counted.

The streams themselves are **identical**: route A's 4831 bytes are an exact
prefix of the port's 5731, and at ips 4100 the port's stream is byte-for-byte
route A's whole stream. The difference is one ~900-byte ring drain landing
either side of the gate, and it tracks the clock knob — the same shape as O4's
resumed PCs:

| ips | 3900 | 3990 | 4100 | 4200 | 4300 |
|---|---|---|---|---|---|
| bytes sent | 5731 | 5731 | 4831 | 4831 | 4831 |

❌ **Retracted the same day it was written:** an earlier sweep in this session
found 4831 at every `ips` and concluded the count was clock-independent. That
sweep was run on the all-ones machine, where the ring writes were being
discarded — it measured the absence of the memory, not a property of the
firmware. **A knob sweep on an instrument that cannot see the thing is not
evidence**, which is the `send_probe` THD lesson in a new costume.

So the gate compares the **bytes over the length both runs reached** — one
must be a prefix of the other — and reports the totals. That is 4831 bytes of
content instead of one integer, and it is clock-independent by construction.
`test_rtos` checks the same thing self-contained, as an FNV-1a over the first
4831 bytes (`0x208868fc`).

### The negative control

`test_rtos` boots a second machine with `Rtos::Quirks::clearTransmitInterrupt`
false — the one thing in `install` that changes which serial writes happen —
and **requires the count to move**. It goes 4831 → 0. Without that, the serial
comparison would be decoration.

**Gate:** `ctest` 6/6; the oracle diff reports **8 compared fields agree, 0
disagreements**; `make check` green.

## Milestone O6 — the eDMA and the frame clock ✅ (8 Sep 2026)

**The sequencer runs, and its trig is byte-identical to route A's.** With the
project loaded, the transport started through the real tasks and a trig poked
on track 1 step 2, 400 frames of the port produce exactly route A's log:

| | route A (the oracle) | `ot_emu` |
|---|---|---|
| frames since the transport start | 400 | 400 ✅ |
| sequencer ticks (vector `0x60`) | 28 | 28 ✅ |
| transport-start writes at frame 0 | `0x10` on tracks 0, 1, 2, 4, 7 | the same five, same order ✅ |
| the trig | frame **344**, track 0, bytes `0x08` then `0x18` | identical ✅ |
| saved / final / sequencer bank / pattern | 1 / 1 / 1 / 0 | identical ✅ |
| eDMA transfers started | 16,801 | 16,800 (reported, not compared) |

```sh
scripts/o6_gate.sh                     # stages ONE card image, runs both, diffs
python3 tools/ot_emu/oracle.py out/oracle/m6c.json out/oracle/port_m6c.json
# oracle: 5 compared field(s) agree
```

❌ **RETRACTED: `RTOS_FORK.md` §8.4's "byte `0xd3`" and its six
transport-start writes on tracks 0, 1, 1, 2, 4, 7.** Re-measured today, route
A **and** the cold tool (`emu_frames.py`, the same command §8.4 quotes) both
give **five** writes of `0x10` at frame 0 (tracks 0, 1, 2, 4, 7) and `0x08`
then `0x18` at frame 344. Two independent instruments agree, so the current
numbers are the reference. 🟡 The likely cause is the EMAC fix of 7 Sep
(§10.16): §8.4 was measured on 6 Sep, before it, and the byte the trig writes
is computed by an EMAC chain (below). Inferred, not measured — nobody has
re-run §8.4's exact tree on the stock library to confirm.

### The gate, and the shape of it

`--sequencer` on both tools walks the same steps, and every one of them is
route A's, including the two compensations it documents as compensations (the
bank switch and the sequencer re-select, which stand in for a load-ordering
defect the unit does not have — RTOS_FORK.md §7/§8.3): park at main's spin,
mount, load, switch to the file's bank through `sys`, re-issue the load's own
last step, clear CLOCK RECEIVE, **then** turn the frame clock on, start the
transport, poke the trig, and run 400 frames. `tools/ot_emu/stage_card.py`
builds the card image with route A's own `stage_project`, so both emulators
read byte-identical media — the FAT16 builder is still deliberately not
ported (O7).

`oracle.py` compares `m6c_trig`, `m6c_trig_words`, `m6c_ticks`, `m6c_frames`
and `m6c_bank` **strictly**. None of them tracks the `ips` knob the way the
dispatch PCs and the serial count do: a trig either fires on the frame the
other emulator fires it on or it does not.

### Five defects, and none of them was in the frame model

The eDMA and the frame latch were written in the previous session and gated
by `test_periph`'s 19 assertions; that model needed no change. What stood
between it and the gate was five other things, each measured:

**1. ✅ The DSP host port needs route A's two stand-in replies, and without
them the frame handler never returns.** `0x20000004` must read `0x0000`: the
handler writes 140 there at `0x4000ab1e` and then polls
`movew 0x20000004,%d0 / tstb %d0 / blts` — it waits for bit 7 of the low byte
to clear, which is the DSP's handshake. An unmodelled window answers all-ones
and the bit never clears. The port took **exactly one** frame interrupt,
entered `0x4000aad0`, and burned **352 M instructions** in that
three-instruction loop: 0 eDMA transfers, 0 ticks, 0 trigs. It reads as "the
frame model is wrong" and it is a missing peripheral reply. `0x2000001c` (the
ping index, read one instruction earlier) toggles 0/1. Both are route A's
`EXTRA_OVERRIDES`, "the DSP host port as M5 faked it", and both are stand-ins
for the DSP that O8 will put behind the window.

**2. ✅ `Region::contains` overflowed, and a legitimate unmapped write became
a 4 GB memory smash.** `(_a - base) + _size <= data.size()` in 32-bit
arithmetic: with the region at `0x00000000`, an access at `0xffffffff` gives
offset `0xffffffff`, and `0xffffffff + 1 == 0`, so the region claimed the
address. The frame handler reaches a `moveb %d0,%a0@-` with `a0 = 0` and the
emulator died inside Musashi with a bare SIGSEGV — **and printed nothing**,
because stdout redirected to a file is block-buffered. Three runs went into
that. Fixed, and with it three instruments that make the next one legible:

- `Machine::badWrite` stops the MACHINE, not the process, on a write the
  region model cannot honour, naming the address and the PC;
- `setAutoMapLimit` (default 65,536 pages = 256 MB) does the same for a
  runaway auto-map, naming the busiest unmapped-access PC — route A's own
  growth on the golden path is ~200 MB, so the ceiling is well clear of
  anything faithful;
- `main` sets **line-buffered stdout**. Same family as the panic printer O7
  could not finish.

**3. ✅ `SATS` (`0x4c80 | Dn`) was unimplemented**, and it is on the M6c path
only — the per-frame EMAC routine at `0x4000346a`, which the eDMA completion
handler's state 5 calls. The boot and the whole project load never meet it.
Semantics measured in route A's engine (six cases in `test_emac`): with V set,
a result whose sign bit is clear saturates to `0x80000000` and one whose sign
bit is set to `0x7fffffff`; with V clear the value is untouched.
⚠️ **Its flags disagree with the CFPRM and the port follows route A**: the
manual says N and Z are set from the result and V and C cleared, and route A's
engine updates **N only**. Nothing between the `sats` and the next
flag-setting instruction reads the CCR at the only site the firmware reaches.
What would falsify it: a firmware site that branches on Z or V after a SATS.

**4. ✅ `movel #imm,%macsr` (`a93c`) was unimplemented** — the frame handler's
own, at `0x4000aeda`. It fell into the MAC path, which consumed one extension
word instead of the immediate's two, and the instruction stream desynchronised
inside the handler. (That is what produced defect 2's write to `0xffffffff`.)

**5. ✅ THE EMAC HAD FIVE FIELDS WRONG, AND THE OLD GATE COVERED NONE OF THEM.**
Every case the O2 gate tested used acc0, two data registers, the long form and
no parallel load — the one combination in which all five are invisible.

- The **accumulator number** was read as ext bit 4 | ext bit 9. It is opcode
  **bit 7** (low) and ext **bit 4** (high) — and in the load form the low bit
  is **inverted** (`a498` is acc0, `a418` is acc1; route A's
  `_emac_load_shim` carries the same `((~op >> 7) & 1)`). The frame builder
  uses all four accumulators.
- An **address-register source** was read as the data register of the same
  number: `macl %a2,%d0` (`a08a`) multiplied d2.
- The two **operand-half bits** were applied to the wrong operands
  (`macw %d0u,%d1l` is ext `0x0040`: bit 6 is the FIRST operand's).
- The **parallel load** handled only `(An)+`. The frame routine at
  `0x40003738` uses `(An)` and `(d16,An)` as well, and the `(d16,An)` form is
  **six bytes** — skipping its displacement word desynchronised the stream
  and invented an opcode two instructions later.
- ⚠️ **And the one that survived all of those: the accumulator is 48 bits and
  holds the product at `>>24`, not `>>32`.** The port shifted each product
  all the way down before accumulating, which is right for one product and
  off by one LSB for a subtract whose discarded low bits are non-zero:
  `floor(-floor(q/2^24)/2^8)` is one less than `-floor(q/2^32)`. Route A's
  model (QEMU's EMAC plus `tools/unicorn_emac_fractional.patch`) accumulates
  at `>>24` and shifts down by 8 only when the accumulator is READ
  (`get_macf`). **That single bit was the whole remaining difference in the
  M6c gate**: the frame handler's `msacl` came out −15 where route A had −16,
  an `spl` floor two instructions later turned it into 1 instead of 0, and
  the sequencer's live nibble read `0x09` where route A reads `0x08` — on
  every write, on every frame. `movclrl` now returns `acc >> 8`, `movel
  Rn,%accN` writes `(int32)v << 8`, and the accumulate sign-extends from 48
  bits (`macsatf`), all as route A does.

`test_emac` now carries **23** assertions covering all of it, every one
watched failing first. ✅ Encodings from `m68k-elf-as -mcpu=5475`, listed
beside each rule; the accumulator alignment has a paired control (`macl` with
the same operands, which agrees under either model, so only the `msacl` case
is evidence).

### How the last bit was found, in order

Worth keeping, because none of it was reasoning:

1. `--watch-mem` on the port (route A's own flag, ported) said the live
   nibble is written at `0x4000b910` and `0x4000b9bc` in both.
2. objdump on the image: `0x4000b910` is `moveb %a2@,%a1@(0,%a3:l)` with
   `a2 = a0 + 62`, and route A's `--watch-pc` said `a0 = 0x80001798 + track`.
3. So the byte comes from `0x800017d6 + track`, and the only writer of that
   table is the frame handler's own loop at `0x4000aef6`:
   `msacl / movclrl %acc0,%d2 / addl #16,%d2 / spl %d3 / andl %d3,%d2 /
   moveb %d2,%a2@+`.
4. `--watch-mem` on both emulators for the two inputs: the frame timebase
   (`0x46104cf0`) is **identical** (`0x16800`, `0x21c00`, `0x2d000` written at
   `0x4000aec4`) and so are the per-track words at `0x80001904`. Two inputs
   the same and the output different leaves the arithmetic.
5. Reading route A's actual model — the patch and QEMU's `macmulf` /
   `get_macf` — gave the alignment, and the arithmetic predicts the sign of
   the error before the fix was written.

### No regression

`ctest` 6/6; the M6a oracle diff still reports **8 compared fields agree, 0
disagreements**; `make check` green.

## Milestone O7 — the card and the project load ✅ (8 Sep 2026; the stall was a fault)

The card model, its memory map and the live-call machinery are in and gated;
**the mount does not complete**, so the milestone's own gate (6,189 ATA
commands / 30,467 sectors) is nowhere near. What is measured:

**What works.** `card.{h,cpp}` is route A's `AtaCard` — the task file at
`0x90000000`, IDENTIFY/READ/WRITE/CFA-TRANSLATE, and the ATA rule that a task
file count of 0 means 256. ⚠️ **The FAT16 image builder is deliberately not
ported**: route A builds the image from a directory tree in Python, and that
is a build-time tool producing bytes, not machine behaviour — this port reads
the same `.img`, so both emulators are guaranteed to be looking at identical
media. `Rtos` carries `attachCard` (the INTRQ rules, one interrupt per
sector, cleared by a read of the STATUS register), `callAsMain`,
`postMessage`, `requestCardMount`, `setNames` and `loadProjectLive`.

**✅ The ATA host-status byte, without which nothing happens at all.**
`0xfc0a4039` bit 3 must read CLEAR. An unmodelled peripheral answers all-ones,
the bit is set, the driver concludes there is no card — and the mount request
posts, SYS runs the card case, and **zero ATA commands** are issued, with no
error anywhere. Route A carries it in `EXTRA_OVERRIDES` from the boot.

**✅ The card's four memory maps are what O5 misattributed** — see the
retraction in the O5 section above. With them, the auto-mapped access count
falls from 20,348,051 to **4**.

### ⚠️ THE MOUNT'S REAL DEFECT: INTRQ IS NOT INSTANTANEOUS, AND THE FIRMWARE DEPENDS ON THAT

✅ **Measured 8 Sep 2026, and it is the finding of the milestone.** The port
asserted INTRQ on the same instruction that wrote the ATA command. A PC ring
armed at the first command shows what that costs, in order:

```
0x40015a50   the driver writes the command
0x40015308   the ISR runs ON THE VERY NEXT INSTRUCTION
   ...       256 words streamed, byte-for-byte route A's
0x40000968   the ISR SIGNALS the event
0x40015a58   only now does the caller execute its next instruction
0x40000818   ... and call the RTOS event WAIT
0x40000550   the scheduler: nothing to run but main
0x4001fc9c   main's spin, forever
```

The signal arrives **before the waiter waits**, so the wait blocks on an event
that already happened. ⚠️ **Route A survives this only by accident of
granularity** — it delivers interrupts at burst boundaries, which happens to
give the caller time to reach the wait. A real CF card takes tens of
microseconds to fetch a sector, so a completion LATENCY is the physical
behaviour and instantaneous assertion is the artefact. `Rtos::m_ataLatency`
(1 sample, ~23 µs) books the assertion forward; `tickTimers` fires it.

This is the "a lock-step emulator cannot show you a race" lesson inverted: the
port's finer granularity **exposed** a race route A's coarse bursts hide.

### ✅ `mvz` takes an ADDRESS REGISTER source, and the storage stack needs it

With the latency in, the mount died at `unimplemented opcode 71c8 at
0x40017c10`. That disassembles under `m68k:cfv4e` as **`mvzw %a0,%d0`** (and
another at `0x40017c2c`): the V4e layer's effective-address reader handled
`Dn` but not `An` direct. Same family as O4's `ff1` — the image is the
evidence, not the toolchain.

### Where it stops NOW

With the latency, the `An` source, route A's own park condition (the PC alone —
requiring nothing pending as well never comes true once the card is live) and a
step budget that survives preemption, **the mount succeeds**:

| | port | route A |
|---|---|---|
| card ready (`0x460d1cb8`) | **1** | 1 |
| ATA commands | **1,407** | 6,189 |
| sectors read | **10,695** | 30,467 |
| sectors written | **297** | **297** ✅ |
| `LOAD PROJECT` posted | **yes** | yes |

The written count matches exactly, and one ATA interrupt arrives per sector
(10,994 for 10,695 sectors). ⛔ The load then **stops** rather than running
slowly: 30,000 ms of emulated time produces the same 1,407 commands as 6,000.
It ends with the engine task cycling at **`0x400165dc`**, with `main` and `sys`,
and the in-flight word (`0x46c8c58a`) clear. That is the next thing to chase.

<details><summary>the earlier stopping point, before the race was found</summary>

**⛔ Where it stopped.** With the card attached and the host-status
byte modelled, the machine parks at main's spin, the mount request posts, and:

| | |
|---|---|
| ATA commands issued | **1** (IDENTIFY) — route A's load issues 6,189 |
| ATA interrupts taken | **1**, and the line is left deasserted |
| card-ready (`0x460d1cb8`) | **0** — never set, so `LOAD PROJECT` is never posted |
| the machine afterwards | **idle**, not spinning: a profile over the mount window is indistinguishable from a boot-only profile |

So the IDENTIFY completes and its interrupt is delivered and acknowledged, and
then SYS is **blocked waiting for something that never arrives** — a missing
wake-up, not a wrong loop. (✅ It was the INTRQ race above.)

</details>

**Route A's own numbers for this project, re-measured today:** 6,189 commands,
30,467 sectors read, 297 written, `saved_bank=1`, `final_bank=0`. ⚠️ Note that
`PART_PTR` reads `0x400e21e0` **before any load** — it is the bank blob's base,
so a non-null `PART_PTR` is NOT evidence a project loaded. The work order's
`0x4017d520` is from a different project; the count pair is the gate that
travels.

**No regression:** the oracle diff is still 8 compared fields with zero
disagreements, `ctest` 6/6, `make check` green.

### ✅ THE "STALL" AT 1,407 COMMANDS WAS A LINE-A EXCEPTION, AND THE UART HID IT

Measured 8 Sep 2026, third session. The port ended the load with the engine
task cycling at `0x400165dc`, 1,407 ATA commands at 6,000 ms and at 30,000 ms,
and it was written up as a stall to chase. It was not a stall.

**How it was found, in order — each step an instrument, not a theory:**

1. `--cmd-log` dumps every ATA command in route A's own log order, and route
   A's log was dumped the same way. `diff` said the port's 1,407 were
   **byte-identical to route A's first 1,407**. So nothing the card did was
   wrong; whatever stopped the load stopped it *between* commands.
2. The PC ring was rewritten as a true ring (the last N instructions, not the
   first N — a stall asks what was running, not what the ISR did). The tail
   was a three-instruction spin at `0x4003afa0`:
   `moveb 0xfc064004,%d0 / movew %d0,%ccr / bpls` — **polling bit 3 of the
   panel UART's status, TXEMP,** which `Uart::read` never set (it reported
   TXRDY only, as route A's model does).
3. Setting TXEMP (a model that consumes every byte at once is always both
   READY and EMPTY; TXRDY-only describes a shift register with a byte stuck
   in it forever) turned the spin into a **`halt`** at `0x4003b108`, and the
   load report — which now names how its run ENDED, not just the counts —
   said `ILLEGAL -- unimplemented opcode 4ac8 at 4003b108`. Halt is the
   last instruction of a printer. `--serial-out` showed what it had printed:

   ```
   EXCEPTION
   SSP:4 VEC:0A
   FS:0 SR:2004
   ADDR:4009D8D0
   ```

   VEC:0A is the line-A exception. The firmware's own panic handler had
   named the faulting instruction; with TXRDY only it could never finish
   saying so.
4. `0x4009d8d0` is `mov3ql #-1,%a0@+` (`a158`), eight in a row clearing a
   structure. `v4e.cpp`'s MOV3Q handled **Dn only** — "only Dn is reached
   by this firmware" — and returned Unhandled for everything else, which
   the A-line dispatch turned into a real exception.

**The fix, attributed separately:** `writeEaLong` + MOV3Q to every
alterable destination. On its own it takes the load from 1,407 commands to
**12,373**, and the whole of route A's 6,189-command log is an exact prefix
of the port's. TXEMP on its own changes nothing about the load; it is the
change that made the fault *legible*. Both are kept.

**Why route A never saw it:** Unicorn's m68k implements MOV3Q natively, so
route A has no shim to get wrong, and it never reaches the exception
printer, so its identical TXEMP gap costs it nothing. "Route A does not have
it either" was true of both and evidence of neither — same family as the
`byterev`/`ff1` retraction in O4 (a toolchain that will not assemble an
opcode is not evidence the part lacks it; the image is).

**Gate:** `test_emac` now holds MOV3Q's memory forms (`#-1,%a0@+`,
`#1,%a0@+`, and the post-increment), watched failing on the old code.
`ctest` 6/6; oracle diff 8 compared fields, zero disagreements; the serial
stream 5,731 bytes identical.

> ✅ **CLOSED 8 Sep 2026 by O7b (below): it was the harness's project-name
> ordering, not a firmware divergence, and the two now issue the same 6,189
> commands line for line. The 🟡 "select bank 0" hypothesis below is
> RETRACTED.**

**⚠️ OPEN (superseded) — the port runs PAST route A's end, and that is a
divergence, not a budget.** Route A stops at 6,189 commands with `M6b load: PASS` at a
6,000 ms budget **and at a 12,000 ms budget** (re-measured 8 Sep 2026: same
6,189 / 30,467 / 297). The port's load runs on to **12,373 commands /
60,677 sectors / 562 written** and parks in main, the same total at 6,000
and at 20,000 ms. The extra 6,184 are 5,919 READs and 265 WRITEs over the
same FAT and bank sectors (2301, 2333, 22889 …) — the shape of a second
bank parse. 🟡 Inferred, not measured: the port performs a bank (re)load
that route A's SYS skips — route A ends "saved_bank=1, final_bank=0" with
SYS applying the engine's reset-time "select bank 0" (RTOS_FORK.md §7), and
in the port that select may be going to the card. Nothing on hardware says
which is right. **The next measurement is which task and PC issue command
6,190 in the port** (`--ata-trace` carries the PC; its 200,000-access cap
will need raising or arming at a command index), then the same site in
route A to see why it does not.

## Milestone O7b — why the port loaded twice ✅ (8 Sep 2026)

**It was a race in the HARNESS, not a difference in the firmware, and the two
emulators now issue the same 6,189 ATA commands line for line.**

```
diff <(cut -d'|' -f1 out/oracle/o7b_port_cmds2.txt) out/oracle/o7b_routeA_cmds.txt
# (no output)
6189 ATA command(s): 1 IDENTIFY, 5921 READ, 30467 sector(s) read, 297 written
```

### The mechanism, measured

The port's extra 6,184 commands were a **second, complete project load** — its
tail is its own head again, differing only in the writes the first pass had
already made. Both loads are issued by the `engine`, and both arrive the same
way: something posts LOAD PROJECT. So the question was who posts it twice.

✅ **`--watch-pc` on `0x40023c7c` (the post) and `0x40085336` (the engine's
LOAD PROJECT case) answers it directly.** The port hits each **twice**, route A
**once**. The port's second post comes from **`sys`**, with the return address
`0x4002576a` — a call site the image contains exactly once:

```
4006203a: jsr 0x40056600
40062040: jsr 0x40056744
40062046: tstl %d0
40062048: bnes 0x40062050      ; non-zero: do nothing
4006204a: jsr 0x4002574c       ; zero: "reload the current project"
40062050: ...                  ; the join point

4002574c: pea 0x100f8378       ; <- the PROJECT NAME
40025752: jsr 0x40013db0
40025758: addql #4,%sp
4002575a: tstl %d0
4002575c: bles 0x4002576c      ; nothing named: return
4002575e: pea 0x100f8378
40025764: jsr 0x40023c7c       ; post LOAD PROJECT
```

`0x40013db0` is **`strlen`** (`clrl %d0 / addql #1,%d0 / tstb %a0@(0,%d0:l) /
bnes / rts`). So `sys`'s media case says, in as many instructions: **a card
appeared — if a project is named, load it.**

✅ **Both emulators run that path identically, instruction for instruction,
and split on one value.** `--watch-pc` on `0x40062000`, `0x4006200c`,
`0x40062046`, `0x4006204a`, `0x40025752`, `0x4002575e` gives the same registers
at the same five sites in both (`d0 = 0`, then `2`, then `0`) — and then:

| | route A | `ot_emu` (before the fix) |
|---|---|---|
| reaches `0x40025752` (the `strlen`) | ✅ at sample 10,361 | ✅ at sample 10,210 |
| `strlen(0x100f8378)` returns | **0** — nothing named yet | **3** — `"RIG"` |
| reaches `0x4002575e` (the post) | ❌ never | ✅ |
| ATA commands | 6,189 | 12,373 |

The whole divergence is **whether the harness has written the project name by
the time `sys` next gets the CPU**. Route A's mount tail runs about 200 samples
longer, so its media case fires *before* `set_names`; this port's fired after.

✅ **The falsifier, run:** told to write the name first (`emu_rtos.py
--load-project --names-early`, a flag added for exactly this and off by
default), **route A reproduces the port's numbers exactly** — 12,373 commands,
60,677 sectors, 562 written — and its `--watch-pc` shows the same
`0x4002575e` → `0x40023c7c` from `sys` with `d0 = 3`. That is what turns this
account from a story into a measurement.

❌ **RETRACTED: the work order's 🟡 hypothesis that this was SYS's reset-time
"select bank 0" going to the card.** The select-bank case is not on this path
at all; the second load is a media-mount response, and the deciding value is a
string length.

### What the port does about it

Neither order is the firmware's — the firmware's rule is unambiguous and both
emulators agree on it. What differed was the harness, so the harness now
*chooses*:

- **Default (route A's order, and what the O7 gate measures):**
  `loadProjectLive` waits for `sys`'s media case to reach its join point
  (`g_mediaCaseJoin`, `0x40062050`) before writing the names, so the name is
  provably not yet set when the case runs. One load, 6,189 commands,
  byte-identical to route A's log.
- **`--names-early`:** write the names before requesting the mount. Two loads,
  12,373 commands. ⚠️ **This is arguably what HARDWARE does** — on the unit the
  project name is set long before a card goes in — so the flag is not a
  mistake to be avoided, it is the other real configuration. Nothing on
  hardware has been measured either way.

The load report now says which order ran and whether the media case was seen:

```
names after the mount; sys's media case ran before the name
```

### Instruments added

`--watch-pc ADDR[,ADDR…]` on the C++ port (route A's own flag: registers and
the top of the stack at each hit, so a hit on a callee names its caller and its
arguments), `--cmd-log` on **route A** (the counterpart of the port's, so the
two logs diff line for line), and the port's `--cmd-log` now carries the PC and
the task per command after a `|` — `cut -d'|' -f1` still reproduces the old
form exactly, so O7's diff method is unchanged.

⚠️ **And a third instance of the silent-instrument trap.** `_watch_report()` was
called from route A's M6c branch and (since 8 Sep) its plain branch, but **not
from `--load-project`** — so `--watch-pc` on a load run printed nothing whether
the address fired twice or never, which is precisely the question O7b exists to
ask. Fixed. `RTOS_FORK.md` §10.3b records this trap; this is its third
appearance, in the third branch.

### No regression

The O6 fidelity gate still reports **5 compared fields agree** (400 frames, 28
ticks, the trig at frame 344 with bytes `0x08`/`0x18`); the M6a oracle diff
still **8 compared fields agree, 0 disagreements**; `ctest` 6/6; `make check`
green.

## Milestone O8 — the DSP cores and the host port 🟡 BUILT THROUGH STEP 3 (8 Sep 2026)

**The two real DSP cores sit behind the host port (`--dsp`), the firmware boots
them itself, the boot's upload is verified byte for byte by a ctest, and the
M6a gate passes with the cores live. Steps 4 and 5 of the work order are open**
(what they stopped on is at the end of this section). The session before this
one decoded the join from the firmware's code (kept below, under "What runs, and
when"); this one wired it and measured what the wiring exposed — six things in
the vendored DSP emulator, one in the model of the shared window, and one in
this port's own first guess at the handshake.

### ❌ The host-port readings that had stood since ARCHITECTURE.md §6 — retracted

The window `0x20000000`–`0x20000fff` is the **HI08 host-side register file** of
whichever core the GPIO byte at `0xfc0a400c` selects: one byte register per
4-byte stride, in the LOW byte of the 16-bit access.

| offset | register | what the firmware does with it |
|---|---|---|
| +0x00 | ICR (RREQ 0, TREQ 1, HF0 3, HF1 4, INIT 7) | writes `0x81` = **INIT\|RREQ, an interface reset** — ❌ not "start the DSP" |
| +0x04 | CVR (HV 6:0, HC 7) | the loader clears it; the frame handler writes `0x8c` = **HC \| vector 0x0c → P:0x18, a host command**, and polls bit 7 until the DSP takes it — ❌ not "swap frame" |
| +0x08 | ISR (RXDF 0, TXDE 1, TRDY 2, HF2 3, HF3 4, HREQ 7) | the loaders spin on `& 6` = TXDE\|TRDY before every word and `btst #0` = RXDF for the echo — ❌ not "bit 6 = DSP ready" |
| +0x14/18/1c | TXH/TXM/TXL, RXH/RXM/RXL | bits 23:16, 15:8, 7:0; the write of TXL sends, the read of RXL takes |

✅ All from the firmware's own code (`0x40001d4c`, `0x40001b18`, `0x4000aad0`),
and confirmed by the join working: the vendored HDI08 answers those registers
and the firmware's upload runs to completion against it. ARCHITECTURE.md §6 and
DSP.md §1 are corrected in place.

### ✅ The gate, and it is self-checking: `ot_dsp_test` (ctest `dsp`, under a second)

The firmware boots with the pair attached; a step hook fires at the instruction
after each upload returns (`0x40001e96` for core 0, `0x40001edc` for core 1) and
compares DSP memory with the image's bytes, parsed independently (DSP.md §2: the
uploader's own walk, mirrored):

```
[PASS] core 0: the boot ROM took 50 words for P:0x31000 and jumped
[PASS] core 0: P:0x31000 holds the bootstrap the image carries  50/50 words
[PASS] core 1: the boot ROM took 58 words for P:0x32000 and jumped
[PASS] core 1: P:0x32000 holds the bootstrap the image carries  58/58 words
[PASS] core 0: the payload parses to its last byte  98 records, 79563 of 79563 bytes, jump 0x30000
[PASS] core 0: every payload record had landed where it names  26221/26221 words
[PASS] core 0: the host sent and took back exactly what the walk predicts  26569 sent (26569 predicted), 99 echoed (99 predicted)
[PASS] core 1: the payload parses to its last byte  91 records, 77061 of 77061 bytes, jump 0x38000
[PASS] core 1: every payload record had landed where it names  25408/25408 words
[PASS] core 1: the host sent and took back exactly what the walk predicts  25743 sent (25743 predicted), 92 echoed (92 predicted)
[PASS] core 0: left the bootstrap and is running the payload  pc 0x30010, no fault
[PASS] core 1: left the bootstrap and is running the payload  pc 0x57, no fault
```

Two mechanisms that cannot fake each other agree: the firmware's ColdFire-side
loader with its TXDE/RXDF polls and echo check, and the vendored DSP running
first the chip's bootstrap ROM (`DspBoot`: count, address, words, jump) and then
the firmware's own 50-word HDI08 loader, which reads a space word, echoes it,
reads an address into r0 and a count into b1, and `dor`-loops
`movep x:<<M_HORX,p/x/y:(r0)+` — disassembled with the vendored
`dsp56kDisassemble`, `out/oracle/o8_blob0.dis`.

⚠️ **Why the check runs at upload time and not at the handoff:** the first
version compared at the handoff and found 19 words of payload A at P:0x38000
reading zero. That range is core 1's entry stub, and core 1 had run it and then
cleared Y:0x38000.. as its delay buffer — the window is one memory (next
section). "Harmless once booted", as CHIP.md predicted; a gate has to look
before that.

### ✅ THE SHARED WINDOW IS ONE MEMORY, and the firmware depends on it

With P private per core (the vendored patch's dsp_host form: X with X, Y with
Y), core 1 jumped to its entry P:0x38000 — an address only core 0's upload had
written — found zeros, and ran off the end of P memory: the PC ring read
`7ffc1 7ffc2 … 7ffff`, then a fault at 0x80000. CHIP.md had this measured on
hardware already (`dsp/alias_probe.asm`: P, X and Y are the same words in
`0x30000`–`0x3FFFF`, reachable by both cores); the port now models it that way,
`Memory::setSharedWindow(lo, hi, all, hook)` in `tools/dsp56300.patch`, one
64K array behind both cores' P, X and Y, the hook dropping both cores' decoded
opcode for any word written there. `dsp_host` keeps its two-way window — it
renders bit-identically with it and, as DSP.md says, cannot answer aliasing
questions; that is now a documented difference between the two machines.

### ✅ Six things the vendored emulator does that the firmware cannot live with (nine by 8 Sep — the ninth, the DMA ring that never reloaded, is under "the ESAI rate" below)

Each one first presented as a hang or a crash with no diagnostic, and each was
found by an instrument, not by reading — recorded with the instrument:

1. **A hardware DO loop runs to completion inside one `execInterpreter()`
   call** (`do_exec` nests the loop). The 50-word loader polls the host port
   INSIDE a `dor`, so the call could never return to the ColdFire that had to
   feed it. *Stack sample:* `op_Dor_S → do_exec → op_Brclr_pp`, forever.
   Patch: with `setHostStepped(true)`, `do_exec` pushes the loop state and
   returns; the host applies `doLoopEnd()` after every instruction (the same
   test, on the same registers).
2. **Interrupts always dispatch through the JIT** when it is compiled in, even
   with the interpreter driving — `execInterrupt` reads `g_useJIT`, which is
   compile-time. `dsp_host` never takes a DSP interrupt, so it never met this.
   *lldb:* `EXC_BAD_ACCESS` in `funcCreate`, called from `execOp` with a
   garbage `this`. Patch: a host-stepped core interprets its interrupts, and
   `exec()` too.
3. **A masked pending interrupt starves the peripheral clock.**
   `execInterrupts()` returns early on a masked head and never re-hooks the
   peripheral exec, so a core that masks interrupts for a while — core A boots
   with `ori #3,mr` — freezes its own ESAI. *`--dsp-trace`:* the peripheral
   target clock stuck at 845,824 while the instruction counter ran to 4 M;
   SAISR at RDF\|ROE; 3 frames ever. Patch: service the peripherals under a
   masked head (a masked interrupt waits; the peripherals do not).
4. **The ESAI blocks on an empty input ring** (a condition-variable wait, meant
   for an audio thread). *Stack sample:* `EsxiClock::exec → Esai::execRX →
   RingBuffer::pop_front → ConditionVariable::wait`. No patch: the pair
   installs non-blocking callbacks — silence in, output frames counted — and a
   clock of ONE ESAI FRAME PER SAMPLE at the pair's own instructions-per-sample,
   so the DSP's audio clock and the ColdFire's sample clock cannot drift apart.
5. **A PC past P memory is a garbage member-function pointer** (the opcode
   cache is indexed by the PC into a table sized to P). *lldb:* the same
   `funcCreate` frame, from `execOp`, `this` = a DSP data word. The pair stops
   the core, records it as a fault, and prints the last 64 PCs — which is what
   found the window finding above.
6. **A fast interrupt never sets the PC to its vector** (the vector's two words
   run inline), so "HC clears when the PC lands on P:0x18" never fired and the
   frame handler polled HC forever: 0 frames, 0 ticks, `host commands 1`.
   Patch: an interrupt-taken hook (`setInterruptTakenHook`); HC and HCP clear
   from it.
7. **The DSP's own audio DMA silently moved nothing.** Core A's main loop
   (P:0x4b..0x53) polls DMA channel 2's source pointer for 0x8070 / 0x80f0 —
   the halves of a 256-word ring, X:0x8000.. → ESAI TX0, one word per TDE
   request (DCR2 `0xcc6220`: source mode DualCounterDOR2, destination fixed);
   channel 3 is the mirror for audio in (ESAI RX0 → X:0x8100.., DualCounterDOR3,
   DCO3 `0x23f` with DOR3 = −575). *`--dsp-trace`:* DSR2 stuck at `0x8000`
   while the ESAI put out 2,334 frames. The vendored `execTransfer` handles
   neither address-mode pair and, in a release build, reaches an
   `assert(false)` that is compiled out and returns "finished". Patch: the two
   pairs, one word per request over the dual-counter ring — and **DCOL is the
   low TWELVE bits of DCO, not eight**: `0x23f` with an offset of −0x23f only
   returns the pointer to its base if DCOL counts 0x23f words (the firmware's
   constants decide it, the way the reciprocal tables decided the EMAC). With
   it DSR2 sweeps the ring, core A sends the host its first word after the
   boot and core B its first three mailbox words, and both cores advance to
   their next waits (P:0x97, P:0x8d).
8. **The host DMA on the DSP side had two more.** Its receive requests are
   rate-limited to one word per 200 instructions (a throttle for a threaded
   host; a 672-word block at that pace is 30 samples, twice a frame), and a
   channel armed while its request condition already holds never fires —
   `checkTrigger` returns false unconditionally upstream — so core B's
   transmit DMA, armed with HTDE already set, never started and its 256-word
   read-back timed out word by word (`read-back words 256 (256 not in time)`,
   51 M instructions spent in the pull). The pair sets the rate limit to zero;
   the patch re-enables the initial trigger for a host-stepped core.

The patch file is regenerated with `git -C vendor/dsp56300 diff >
tools/dsp56300.patch`; `scripts/setup.sh` applies it; `dsp_host` is unchanged
by every part of it (its window form and its non-host-stepped mode are the
defaults).

### 🟡 The inter-core mailbox — inferred from both payloads' code

Core 1 parks at P:0x57 on `brclr #1,y:<<$ffffd3` and reads `y:<<$ffffd4`;
core 0 writes `movep r3,y:<<$ffffd7` and waits on `brset #1,y:<<$ffffd6`, then
sends `#2`. No vendored peripheral maps those, so the pair models a symmetric
one-register channel (transmit data at $D7, "still unread" at $D6 bit 1;
receive data at $D4, "one waiting" at $D3 bit 1) through a hook on unmapped
Y-side registers. The addresses are the firmware's; the bit semantics are
inferred from the two wait loops and nothing else. Core 0 has not sent a word
on it yet in any run — that happens on the frame-exchange path.

### ✅ M6a with the cores live, and the idle fast-forward validated

`ot_emu --dsp --ms 1000 --golden`: **the M6a gate passes** (10 created, 11 ran,
gate at 205.97 ms against 205.39 without the cores) and `oracle.py` reports
**8 compared fields agree** against route A. The boot sends the cores one word
after the handoff (`0x030000`); core 0 takes it and goes on running with its
ESAI ticking.

The cores are stepped in lockstep (1.14 instructions per ColdFire instruction
in the boot, 4535 per sample under the RTOS; both knobs, neither measured), and
a 20-second project load is 4 G instructions per core in an interpreter. So a
core found polling — eight instructions inside a three-word window, no hardware
loop open, no interrupt pending — is advanced to its next peripheral event the
way the chip's own `wait` is emulated (`idleStep`, the arithmetic is
`op_Wait`'s), then executes the poll once so it can see what changed. ⚠️ The
first version `continue`d without that execution, and the uploader waited for
an echo that a never-executed poll could not produce. ✅ **Validated by A/B**,
`--dsp` against `--dsp --dsp-no-idle` over the M6a run: ESAI frames 2688 / 2686
both, host words 26570 / 99 both, all 8 oracle fields agree between the two.

### Instruments added

`--dsp`, `--dsp-log FILE` (every host-side event: sel/icr/cvr/tx/rx/mail/
hc-taken, with the DSP due count), `--dsp-trace N` (a status line per core:
PC, SR, mode, pending, peripheral target, ESAI counts, SAISR/RCR/TCR/HSR/HCR),
`--dsp-no-idle`, `--dsp-verbose` (the vendored log lines, off by default: 3,260
per boot), `--edma-log FILE` (every kick with its whole TCD), the per-core PC
ring and fault in the report, `DSP=1 scripts/o6_gate.sh`. And the build is now
native: `/opt/homebrew/bin/cmake` — the x86 cmake at `/usr/local/bin` had been
building `out/emu` for Rosetta.

### ✅ The sequencer gate passes with the cores live

`DSP=1 scripts/o6_gate.sh` (the port with `--dsp`, the same staged card, the
same route A oracle): **400 frames, 28 ticks, the trig at frame 344 on track 0,
bytes `0x08` then `0x18` — 5 compared fields agree.** Over those frames core A
took 2,400 host commands and core B 1,200; the host wrote 6,400 words and took
back 500; the pair's event log shows the frame protocol the tape had recorded
(sel/icr/cvr/tx/rx/hc-taken), and the ColdFire's 16,800 eDMA kicks are in
`--edma-log` with their TCDs. Before the DMA fix (item 7 above) this run
stopped at frame 0 with 0 ticks; before the HC fix (item 6) at the first host
command.

### ✅ Step 4 — the blocks, decoded from the tape, and the lanes corrected

Route A's tape (`emu_rtos.py --tape`, the `hostw` and `edma` records) gives
the frame protocol per core, in order, and it decides the word width:

| host command | words to +0x1c before it | eDMA that follows | bytes | DSP count |
|---|---|---|---|---|
| `0x8c` (vector 0x18, "frame") | — | — | — | — |
| `0x89` (0x12, "DMA a block OUT") | `0x6600`, `0x1ff` | ch1 paced → ch6 → ch7 | 512+256+256 | 512 |
| `0x89` | `0x6600`, `0x0ff` | ch1 burst | 512 | 256 |
| `0x88` (0x10, "DMA a block IN") | `0x6080`, `0x29f` | ch0, NBYTES 0x150 × 4 | 1344 | 672 |
| `0x88` | `0x6800`, `0x03f` | ch0, 0x20 × 4 | 128 | 64 |
| `0x88` | `0x6000`, `0x07f` | ch0, 0x40 × 4 | 256 | 128 |
| `0x88` | `0x6400`, `0x1ff` | ch0, 0x100 × 4 | 1024 | 512 |

(two of the IN blocks repeat per frame, one per core, the GPIO byte toggling
between them; the DSP's handlers at P:0x588 / P:0x597 read the two words,
mask them to 16 bits, and arm DMA0 from HORX / DMA1 into HOTX for `count+1`
words.) **Every count is exactly half the byte count.** So one DSP word rides
each 16-bit bus cycle, a 32-bit eDMA access at +0x1c is two words (high
halfword first), and ❌ the pair's first lane model — the odd byte of each
halfword is the register, the even byte nothing — made every frame word 8
bits wide. The corrected rule: on this 16-bit port the odd byte is the
register the stride names and the even byte the register before it, so a
halfword at +0x1c lands TXM:TXL and sends, at +0x18 TXH:TXM, at +0x14 TXH.
The loader's byte-at-a-time upload is consistent with it (its `movew` at
+0x1c carries mm:ll, and TXM was already mm), and so is the DSP masking a
count sent by a single `movew` to 16 bits. The DSP words carry TXH stale
(0x03, the last upload byte) above the 16 payload bits. DSP.md's "336-word
records" were bytes: the record is 672 words.

`Rtos::installHostPortMover` then moves the data the eDMA carries: a block
whose DADDR is the window is pushed whole at the kick, halfword by halfword,
as the bus cycles the eDMA would make (the vendored HDI08's receive ring
holds it until the DSP's DMA0 drains it, a word per peripheral tick); a block
whose SADDR is the window is pulled at completion from the core the kick was
made against, running that core until each word is in HOTX (its DMA1 puts
them there one at a time, since HOTX is a single register). The block size
is NBYTES × the minor-loop count (CITER bit 15 = a minor link, count in bits
8-0), the RAM side contiguous. `--dsp-peek core:space:addr,len` reads DSP
memory after the run.

⚠️ **And one of route A's completion rules changes when the cores are
attached.** "A host-port burst completes at once" was right for a model that
moved nothing; with the DSP draining a real ring it let the frame handler issue
the next block's destination and count while the DSP was still taking the
previous block, and the DSP's handler read data words as its arguments: 7
frames in the window, the receive ring overflowing, 36 of 64 host commands
never taken. On the chip the completion interrupt fires when the DSP has taken
the last word, and that is what lets the handler continue — so with the pair
attached a burst INTO the port completes at the first tick the selected core's
receive ring is empty (`Edma::setCompletionGate`), and without it every rule is
route A's (the non-DSP O6 report is byte-identical before and after).

✅ **With the mover, the gate still passes and the blocks flow**: 400 frames,
28 ticks, the trig at frame 344 (`0x08`/`0x18`), 5 compared fields agree;
**2,400 blocks / 870,400 words to the DSPs, 1,600 blocks / 307,200 words
back, 0 not in time**, 60,820 ticks spent holding a burst for the DSP to
drain; per core 2,400 / 1,200 host commands taken, 204,800 / 102,400 read-back
words produced by the DSPs' own transmit DMA. 

### ✅ And the frames carry content — outbound. The DSP returns silence.

The counter that decides whether any of the above means anything
(`--block-log`, non-zero words counted at the moment of the move, not peeked
afterwards). Over the 400-frame run:

| direction | blocks | words | non-zero |
|---|---|---|---|
| ColdFire → DSPs | 2,400 | 870,400 | **40,853** |
| DSPs → ColdFire | 1,600 | 307,200 | **0** |

✅ **The outbound path is live and it tracks the sequencer.** Non-zero words
per 50 frames sit at 5,088 and rise to 5,100 across the trig at frame 344,
then 5,238 — the parameter frames change when the sequencer fires. The 672-,
128- and 64-word records carry 14, 30-33 and 11 non-zero words each: sparse,
which is what a parameter frame with most slots idle looks like. And the words
reach DSP memory: the landing peek reads `030004 030009 030800 … 030b40`
where the block ended.

❌ **The inbound path is zeros in every frame band, including after the trig**
— 0 of 307,200 words, with the pull never timing out, so the DSP genuinely put
zeros in HOTX rather than the port failing to collect them. Its own DMA1 is
sourcing from X:0x4700/0x4780/0x4800 and those hold zeros. The DSP is
computing silence, which is what a machine with no sample audio and a silent
ESAI input should compute. **What has NOT been established is why** — no
sample data reaching the DSP, or a voice that never starts, are both open and
both sit on the audio-in path that is O9's ground.

### ⚠️ The destination word is the host's, the address is the DSP's

`--dsp-peek` of X:0x6080 read zeros and briefly looked like "the frames are
empty". It was the instrument: **0x6080 is the address the HOST names, not the
one the DSP uses.** Measured, with the command's arguments snapshotted at the
command and both candidates peeked at the same instant:

```
cmd args 036080 03029f | DMA0 ddr 004320 dco 00029f | X@6080 000000 000000 | X@4080 030000 030000
```

The firmware sends dest `0x6080`, count `0x29f`; the DSP arms its DMA0 at
`0x4080` and the block lands there. Every block is the same 0x2000 apart:
0x6080 → 0x4080, 0x6000 → 0x4000, 0x6400 → 0x4400, 0x6800 → 0x4800.

✅ **The landing addresses are the payload's own bank pointers, exactly.** The
dispatcher at P:0x40 loads two banks and takes one per frame:

```
bank A:  r6 = $4000   r7 = $4080   r2 = $4400   r5 = $4600   r4 = $4800
bank B:  r6 = $2000   r7 = $2080   r2 = $2400   r5 = $2600   r4 = $2800
```

Every block landed on a bank-A pointer, and each host word is exactly the two
banks' addresses OR'd together (`0x4080 | 0x2080 = 0x6080`). 🟡 **Inferred,
not located:** that bits 14 and 13 are a bank select the DSP masks down to the
bank it is running. The masking instruction has not been found — the handler
at P:0x588 is the only write to DMA0's destination register in the payload and
it masks to 16 bits only, which would leave 0x6080. Falsifier: a run in which
the DSP takes bank B should land the same words at 0x2xxx.

### ✅ The bank is the audio ring's phase — and one half is never used

The dispatcher's bank choice is not a flag, it is a wait on the audio-out
DMA's own source pointer (P:0x4a, read from the payload):

```
P:0004a  clr   b
P:0004b  movep x:<<M_DSR2,a          ; where the audio-out DMA is playing from
P:0004c  cmp   #>$80f0,a
P:0004e  beq   ...                   ; -> bank B: r0 = $8000, r2/r5/r6/r7 = $2400/$2600/$2000/$2080
P:0004f  cmp   #>$8070,a
P:00051  beq   ...                   ; -> bank A: r0 = $8080, r2/r5/r6/r7 = $4400/$4600/$4000/$4080
P:00052  add   #<$1,b                ; else spin, counting the wait
P:00053  bra   P:0004b
```

That is a textbook double buffer: the audio ring is X:0x8000-0x80ff (DMA2,
`DOR2 = -255`, `DCO2 = 0xff`), and the DSP waits until the play pointer is
about to leave one half, then works into the other — `r0 = 0x8080` when the
pointer is at 0x8070, `r0 = 0x8000` when it is at 0x80f0.

⚠️ **In 400 frames it took bank A every time.** The only landing addresses in
the whole run are 0x4078, 0x4318, 0x45f8 and 0x4838 — the DSP never once saw
`DSR2 == 0x80f0`, so half of its double buffer is dead and the audio ring sits
in a fixed phase against the frame clock. That is a **timing knob nobody has
measured**: the pair drives the ESAI at one frame per sample at the same
instructions-per-sample the cores run at (`DspPair`'s `_ips`, defaulted from
`docs/CHIP.md`'s clocks), and neither that ratio nor the resulting ring rate
has been checked against anything. The parameter path does not care — it
passed every gate — but an audio comparison would be measuring a machine whose
output buffer alternation never happens. **Settle the ESAI rate before
believing any audio the port produces**, and treat "bank B is never taken" as
the falsifier for having got it right.

⚠️ **And DMA0 cannot be read at the eDMA kick to settle it** — a third
instance of the same lesson, and it nearly went into this document as a
finding. The command's two argument words and the CVR write all precede the
kick, but the CVR only *injects* the interrupt: at the kick the DSP has not
taken it, so its handler has not read the arguments, and DMA0 still holds the
PREVIOUS block's arming (measured: DCO0 always one block behind). That is not
a defect — the ring is a FIFO, so the arguments sit ahead of the data and the
DSP reads them first, arms, then drains. It does mean the armed value has no
readable moment in this model, and the destination has to be read from where
the pointer ends up.

⚠️ Two instrument lessons, both the project's usual family. **A peek after the
run cannot tell "nothing was sent" from "the DSP consumed it"** — count at the
move. And **a note taken at the eDMA kick lags a whole block**: read at the
kick, DCO0 still held the PREVIOUS block's count and it read as if the
firmware's destination were being ignored entirely. The note is taken at the
completion the drain gate holds, which is when the DSP-side state means
something.

### ✅ The ESAI rate, settled from the firmware's own constants (8 Sep 2026)

The "unmeasured knob" above had two halves, and the payload pins both.

**1. The port's ESAI ran eight times slow, and that is why bank B never
came.** The vendored clock's `setCyclesPerSample` is per SLOT, not per frame:
`Esai::execTX` advances `m_txSlotCounter` once per call and the frame
callback fires when it wraps, and `EsxiClock::updateCyclesPerSample`'s own
derivation halves the per-sample count with the comment "2 samples = 1 frame
(stereo)". `DspPair` passed `ips` (4535) straight through, so with the
payload's `TDC = 7` (eight slots) one audio frame cost 8 × 4535 instructions
— the 256-word ring at X:0x8000 advanced 16 words per 16-sample host frame
instead of 128, and the dispatcher's `DSR2 == 0x80f0` never arrived before
the next `0x8070`. ✅ Read from the vendored source, not inferred from the
symptom. The fix is one division: one slot per `ips / 8`, and a report line
that counts ESAI frames between consecutive `0x8c` host commands, whose
value the ring needs to be exactly **16**.

**2. The rate itself.** Payload A's setup (`out/dsp/payload_A.asm`,
`P:0x30024..0x3007f`, `tools/dsp_disasm_all.py`):

```
030024: movep #>$aa0000,x:<<$ffff98      ; PDRH: ETI1 ERI1 ETI0 ERI0 = 1
030026: movep #>$40,x:<<M_SAICR          ; SYN = 1
03002a: movep #>$f40f00,x:<<M_TCCR       ; THCKD TFSD TCKD; TPSR=1 TPM=0 TFP=0 TDC=7
03002c: movep #>$37d01,x:<<M_TCR         ; network, TSWS=$1f (32-bit slot), TE0
03002e: movep #>$f40f00,x:<<M_RCCR
03006d: movep #>$f00f00,y:<<M_TCCR_1     ; the second port: the same dividers, TSWS=$1e
```

`X:$FFFF98` on the DSP56720 is the Port H data register, whose top byte is
the **ESAI/EXTAL clock control** (DSP56720RM §8.2.2.4, Table 8-4): with
`ETI0`/`ERI0`/`ETI1`/`ERI1` set, *"the EXTAL clock can be used to generate
the ESAI transmitter/receiver clocks"* — the audio clock is derived from the
crystal, not from the core clock. The chain (RM Figure 9-3) is EXTAL → ÷2 →
prescale ÷1 (`TPSR = 1`) → ÷(TPM+1) = 1 → ÷(TFP+1) = 1 → bit clock; the frame
is 8 slots × 32 bits = 256 bit clocks. So

    fs = EXTAL / (2 × 256) = EXTAL / 512       (bit clock = EXTAL / 2)

🟡 The manual's prose says the *maximum* internally generated bit clock is
"Fsys/4", one ÷2 more than its own block diagram shows, and it is not
self-consistent (its stated minimum, Fsys/(2 × 8 × 256), counts only one). The
÷2 reading is the one the rest of the chip allows — see the PLL below; the
÷4 reading needs a 45.16 MHz crystal and a 367 MHz core, above the part's
200 MHz. **And the frame arithmetic does not depend on which**: the DSP's
instruction count per sample is fixed by the PLL alone.

**3. The core clock.** ✅ Neither payload, nor the 50-word bootstrap, writes
`PCTL` (`X:$FFFF7D` on this part — on the shared peripheral bus, not a
`<<` short address; grep `ffff7d` over both listings and `o8_blob0.dis`: no
hit). So the PLL keeps its reset value, RM §7.3.3.2: **`0x2B60C2` when
PINIT = 1** — `R = 11` (NR = 12), `OD = 1` (NO = 2), `F = 0xC2` (NF = 195),
`DF = 0`, PEN = 1:

    Fsys = EXTAL × NF / (NR × NO) = EXTAL × 195 / 24 = EXTAL × 8.125

(PINIT = 0 would be bypass, Fsys = EXTAL: ~512 instructions per sample, and
the burn probe has measured over 3,000 — so PINIT = 1.) Divide the two:

    Fsys / fs = 512 × 8.125 = **4160 instructions per sample, exactly**,
    520 per ESAI slot — whatever the crystal is.

With the ÷2 reading and fs = 44.1 kHz the crystal is **22.5792 MHz = 512 fs**
(the common audio crystal; `Fref` = 1.88 MHz sits just under the RM's 2 MHz
floor, and `Fvco` = 367 MHz inside 200–400) and **Fsys = 183.456 MHz**. 🟡
Inferred — no one has photographed the crystal or measured the SCKT pin;
either would settle it. What it would take to falsify 4160 itself: a
`PCTL` write we have not found (none exists in the uploaded code; a host
command could not reach it, the payloads have no such handler), or PINIT = 0.

❌ **4535 (200 MIPS ÷ 44.1 kHz) was the datasheet's ceiling, not this
board's clock.** `CHIP.md` and `PLAN.md` carry the 🟡 4160 beside it;
`DspPair` now defaults to 4160 per sample (ratio 4160/3990 in the boot) and
520 instructions per ESAI slot. Nothing measured on hardware changes — the
burn-probe ceilings were counted in instructions, and 4160 sits above every
one of them (`CHIP.md` §2: 3,120 static floor) with 1,040 for the stock
dispatcher instead of 1,415.

**The gate** — the same O6 run (`DSP=1 scripts/o6_gate.sh`, 400 frames) with
`--block-log`, and the falsifier is "bank B is taken": ✅ **Passed, and the falsifier turned up the next thing.** Same O6 run,
`--block-log`, cores live: **400 frames, 28 ticks, trig at 344 — 5 compared
fields agree**, M6a 8 compared fields agree, `ctest` 7/7, `make check` green,
and the landing addresses now split **bank A 1,193 / bank B 1,207** of 2,400
outbound blocks (`landed@2078/2318/25f8/2838` beside `4078/4318/45f8/4838`),
where every one of the 2,400 before was bank A. ESAI frames in = out
(1,870,163 / 1,870,161; before the DMA fix out fell behind in and the
transmitter died), and the read-back carries **196 non-zero words** where it
carried none.

❌ **But the new report line reads `ESAI frames per host frame (0x8c to
0x8c): min 160 max 194, exactly 16 on 0 of 399`** — not 16. The ring makes
5.5 passes between host frames, so the bank alternation is a *random* phase
against the frame clock, not the locked double buffer the dispatcher
expects. The DSP's clock is the firmware's; what is stretched is the PORT's
host frame period: the frame interrupt is a latch (`Rtos::tickTimers`,
"remembers ONE edge"), so a handler that outlives its 16 samples coalesces
the missed frames, and the handler spends its time inside the eDMA drain
gate (`65,327` gated waits over 400 frames; the same order before the
pacing fix, when it read 22 ESAI frames per host frame — the stretch was
there all along and no parameter gate can see it). Where the samples go —
the DSP's own per-frame work, the vendored HDI08's one-word-per-exec drain,
or the port's idle stepping — is the next measurement (stamped block log:
`kicked@`/`done@`/`at@` in samples). 🟡 Until it reads 16, no audio the port
produces has the chip's timing.

✅ **Measured, same day (stamped block log, `kicked@`/`done@` in samples):**
each of the frame handler's SIX serial host-port bursts is held to the *next
16-sample boundary* by route A's completion rule, so a frame costs **80–96
samples** (frame 200: pulls at 914840.6, bursts done at 914856.6, 914872.6,
914888.6, 914904.6, 914904.6, 914920.6, next frame at 914936.6). The 160–194
was that period counted on BOTH ESAI ports; the instrument now counts the
X-side port only. Not the DSP's clock, and not the drain — the drain finishes
inside a sample; the boundary rule holds it. `--dsp-drain-paced` (complete
when the DSP has drained the burst) ran ONE frame at **exactly 16** ESAI
frames per host frame and then the firmware's completion ISR lost an edge and
the port stalled at frame 2 with source 1 asserting untaken — route A's
"at once" symptom, reproduced with the cores. So the boundary rule stays the
default (the O6 gate passes with it, 5/5, and without the cores 5/5) and the
chip's own number is the open item: **a burst takes the FlexBus's cycle time
× its words** — `CSCR2 = 0x180` for the DSP window (`ARCHITECTURE.md` §6) and
the FlexBus clock give it, and 2,176 words per frame against 16 samples says
it is not small. Derive that, book each burst's completion at kick + words ×
t_cycle behind the gate, and the instrument should read 16 on 399 of 399.

### ✅ A ninth vendored-emulator defect, found by the falsifier: the receive DMA's ring never reloaded (8 Sep 2026)

The first run at the corrected pacing did not alternate banks — it took **zero
frames**: the frame handler's first 672-word push was never drained, the
read-back pulls came back "not in time", and core 0 sat at `P:0x97` (the
`HTDE` wait) with **`TCR = 000000` and DMA2 finished** (`DCR2 4c6220`,
`DSR2 8000`) long before the first `0x8c`. The transmitter was dead, so the
audio ring never moved and the dispatcher's bank wait could not end.

Nothing in either payload writes `TCR` after setup (grep `M_TCR` over both
listings: the two setup `movep`s only), and the vendored `Esai::reset` runs
only from the constructor. A `LOG` with the PC in
`writeTransmitControlRegister` said: **`Write ESAI TCR 000000 at pc 000097`**
— the idle loop, so not an instruction; a DMA. The widened `--dsp-trace`
(every channel's DSR/DDR/DCO/DCR) showed **`DDR3` wandering over the whole
24-bit space with `DCO3 = 0`**: `4f186a, ac3264, 0947e0, 665d5c, …` — the
ESAI-in ring's destination, which should cycle X:0x8100–0x833f.

The cause is in `DmaChannel::dualModeIncrement`: on the word that ends the
block it adds `DOR` and returns "finished" **without reloading `DCOL`/`DCOH`**.
For a channel the DSP re-arms itself (DMA2, mode 001, DE cleared) the arming
reloads them; for the firmware's ESAI-in channel — DMA3, `DCR3 = ac59c0`
(mode 101: line, DE **not** cleared), `DCO3 = 0x23f`, `DOR3 = −575` — nothing
re-arms, so after its first pass every received word added −575: the pointer
wrapped below zero into the peripheral space, sprayed silent samples across X
memory at a 575-word stride, and after **1,215,032 words** landed on
`X:$FFFFB5` = `TCR`. ✅ The arithmetic reproduces the observation: DMA3 moves
two words per RX frame here (trace: ΔDDR3 = −575 × 2 × Δframes mod 2²⁴), so
the hit falls at ~160,800 RX frames; the trace has it between 160,000 and
160,966. The firmware's own `DOR3 = −DCO3` is the constant that only makes
sense one way: a ring, i.e. **the counters reload at the end of the block**,
which is what `tools/dsp56300.patch` now does.

⚠️ **This was live in every O8 run**, spraying zeros through X memory at −575
per received sample — including the shared window and the parameter banks —
and the parameter gates could not see it (they compare the ColdFire's
sequencer, and the DSP never returned anything but silence). At the old
pacing the walk was eight times slower and the transmitter happened to
survive to frame 400; at the right pacing it died during the project load.
Same family as the seven before it: found by an instrument, not by reading.

### ✅ O8b — the host-port burst time is the FlexBus's own, and the frame is 16 samples again (8 Sep 2026)

The open item above ("the port's host frame is 80–96 samples") is closed, and
the number came out of the firmware's own constants rather than a knob.

**What the chip is programmed to do.** Two register words decide it, both read
off the image with `scripts/disasm.sh`:

| where | what | reading |
|---|---|---|
| `0x400e165c` (and three identical sites) | `PCR = 0x16777731` | PFDR 22, OUTDIV1 1, OUTDIV2 3, OUTDIV3 7 |
| `0x40001eee`, between a CSMR2 disable and re-enable, immediately before the ICR reset that starts an upload | `CSCR2 = 0x180` | **WS = 0**, AA = 1, PS = 1x (16-bit) |
| `0x400e0e0a`, the boot's own chip-select init | `CSCR2 = 0x1180` | **WS = 4** — the value the loader overwrites |

`CSAR2 = 0x20000000` at `0x400e0dfe` is what makes CS2 the DSP window, so
these are the DSP's own bus terms and nothing else's.

The clock tree they sit in is in `CHIP.md` §1 — crystal 24 MHz, VCO 528, CPU
264, internal bus 132, **FlexBus 66 MHz** — and the load-bearing step is that
the firmware's stored 264,000,000 is the CPU clock, which the UART's baud
setup proves by shifting it right one before dividing (a ColdFire UART divides
the internal bus clock). Read as the VCO instead, every figure below halves.

**The burst time.** RM Figures 20-16 and 20-18: a no-wait-state FlexBus
transfer is S0–S1–S2–S3, **four FB_CLK cycles**, and each wait state repeats
S1 once more. One DSP word is one 16-bit bus cycle (O8, above), so

    one word = 4 / 66 MHz = 60.6 ns = 2.673e-3 samples

✅ **And the constants only make sense one way** — the test this project keeps
coming back to. The frame exchange moves **2,944 words** (2,176 out, 768 back,
measured), which is **178 µs against the 363 µs frame period: 49% bus
occupancy**, half the frame for audio and half for everything else. At the
BOOT's `WS = 4` the same exchange is 357 µs — **98% of the frame**, which
cannot work. That is why the firmware reprograms the chip select before it
ever speaks to a DSP, and it is why the wait states go to zero on a port that
had four.

**What changed in the model.** `Edma::start` books a host-port burst at
`kick + words × 2.673e-3 samples` instead of at the next 16-sample boundary,
still behind the drain gate, so a burst takes **max(bus, DSP)**.
`--dsp-drain-paced` keeps the pure-drain rule for A/B, and without the cores
route A's boundary rule is untouched (its own gate still passes 5/5).

⚠️ **The honest reading of why that fixed it**: what was wrong was the
QUANTISATION, not the magnitude. The drain gate binds more often than the bus
does (1,014,303 gated waits against 65,327 under the boundary rule), so the
period is usually the DSP's drain — but the drain resolves to a fraction of a
sample where the boundary rounded every one of six serial bursts up to a whole
frame.

**The gate.**

| | boundary rule | bus time |
|---|---|---|
| ESAI frames per host frame | 160–194, **16 on 0 of 399** | **16–17, 16 on 382 of 399** |
| frames run / ticks / trig | 400 / 28 / 344 | 400 / 28 / 344 |
| oracle diff (O6, cores live) | 5/5 agree | **5/5 agree** |
| blocks landing in bank A / B | 1,193 / 1,207 | 1,550 / 850 |
| outbound non-zero words | 40,949 | 54,087 |

M6a with the cores 8/8, `ctest` 7/7, and the O6 gate without the cores
unchanged at 5/5.

🟡 **The residual: 17 host frames of 399 take 17 ESAI frames, a 0.27% drift**
(one every 23.5 frames, never 15, so the DSP's clock runs slightly fast rather
than jittering). ✅ **What it is not**: `--dsp-no-idle` reproduces the figure
EXACTLY (16 on 382 of 399, min 16 max 17), so the DSP's idle fast-forward is
ruled out; the host frame interval is **exactly 16.000 samples on all 399**
(measured off the block log's `kicked@` stamps), so the frame clock is not
drifting; and an X-side ESAI transmit frame measures **4160.3 DSP
instructions**, one sample, over the load. So both clocks are right and it is
their PHASE that walks, one sample every 23.5 frames, always in the same
direction. 🟡 The candidate — not yet tested — is that the read-back pull runs
a core OUTSIDE the sample budget (`runCoreUntil`, up to 200,000 instructions
until the DSP puts a word in HOTX), which advances the DSP's audio clock
during a pull; the falsifier is to bound the pull to the budget, or to count
ESAI frames inside pulls and see whether they account for the 17. **O9 is
where this has to be settled** — an audio path resamples by exactly this
error, and 0.27% is about five cents of pitch.

⚠️ **Not fixed by any of this, and not a regression: the read-back is still
silence.** Inbound non-zero words moved 196 → 9 with the new pacing, which is
a different phase of the same nothing — the DSP has no audio in. That is O9's
ground, unchanged.

### What step 5 needs

`verify_twocore` drives the effect ABI directly (`r0`/`r6`/`r7`/`n7` and a
`proc` call); the firmware drives whole frames through the packer at
`0x4000d3fc`, and with the mover those frames now reach the DSP's X:0x6080
records. Making the two render the same audio means (a) audio IN: the ESAI
receives silence here — the ColdFire's own audio path (the sample pool → the
DSP) is the eDMA/ESAI-in side, untraced; (b) audio OUT: the ESAI transmit
frames are counted, not kept; (c) a comparison of the firmware's per-track
records against the knob values the harness passes by hand. That is O9's
ground as much as O8's, and it was not started.

### No regression

`ctest` 7/7 (the new `dsp` gate included); `make check` green; the O6 gate
without `--dsp` unchanged (5 compared fields agree, the trig at frame 344);
the M6a oracle diff without `--dsp` 8 compared fields agree. The models are
seeded from the same 8,235 boot writes as before — a write the co-processor
owns is not replayed into them.

## Milestone O9 — the audio path: input proven, output silent, the clock walk closed (8 Sep 2026, branch `coldfire-o9`)

O9 was "the ESAI path, untraced". It is traced now, in both directions, with
instruments that stay in the tree; half of it works and the other half stops
at a place that is not the port's.

### The instruments

| flag | what |
|---|---|
| `--audio-out PREFIX` | every X-side ESAI TX0 frame a core puts out, eight slots, to `PREFIX_core<k>.wav` (24-bit, 44.1 kHz), with the transport start's frame index in the report |
| `--audio-in FILE.wav` / `--audio-in tones` | RX0's slots from the transport start on: the file's channels onto slots 0..n−1, or slot k = a sine at 500·(k+1) Hz, −20 dBFS |
| `--dsp-map FILE` | at every frame command, the count of non-zero words per 4K chunk of both cores' X and Y — where anything LIVES |
| `--dsp-writes FILE` | at every frame command, the count of NON-ZERO WRITES per 256-word region of both cores' X and Y since the last one — where anything PASSES THROUGH. Needs the tenth vendored patch: a write hook in `Memory::dspWrite` (one branch per write, unset by default) |
| report lines | `audio (O9)`: transport start frame, TX0/RX0 non-zero per slot, the DSP's own instruction counter and its surplus over interpreter calls; `shared window ... non-zero words now`; `non-zero writes into the ESAI-out ring` with the first one's address and value |
| `stage_card.py --audio SRC:CARDPATH` | a sample on the card (route A's own `--stage-audio`, exposed) |

⚠️ Two instrument corrections found on the way: `--dsp-peek` (and the map)
read the shared window through `Memory::get`, which answers 0 for any offset
past the core's own size BEFORE it looks at the window — so a peek at 0x30000+
was blind and read as "empty"; it reads the pair's array now. And the first
activity maps were taken at the frame command, where the window is always
zero (below) — a snapshot instrument cannot see a buffer that is consumed
inside the frame; the write map can.

### ✅ The clock walk of O8b is closed: `rep` iterations

O8b left 17 host frames of 399 taking 17 ESAI frames, a 0.27 % drift "always
one way". The cause was the budget's unit: `runDue` counted ONE per
interpreter call, while the ESAI clock reads the DSP's own instruction
counter, which a `rep` advances once per ITERATION (`DSP::rep_exec`). The
payload's `rep`s put the DSP's audio clock ahead of the ColdFire's sample
clock by the iteration surplus. The budget now spends the DSP's own counter
delta per call (idle steps included), and the report prints the surplus:

| | before | after |
|---|---|---|
| ESAI frames per host frame, exactly 16 | 382 of 399 | **399 of 399**, and **1599 of 1599** |
| surplus over interpreter calls, 400 frames | — | 83,398 = 208 per frame = 0.31 % of 66,560 |

The candidate O8b named (the read-back pull running outside the budget) was
wrong: the pull's instructions were already counted. ✅ Measured; the number
that only makes sense one way is the surplus per frame matching the drift.

### ✅ Audio IN works, end to end

With `--audio-in tones`, over 400 frames (the RIG fixture, T1 THRU trigged at
frame 344 by the poke):

- the ESAI-in ring X:0x8100–0x833f holds the sines (`--dsp-peek 0:X:8100`),
  DMA3 writing ~128 non-zero words per frame (the write map's `0X08200/0X08300`);
- core 0 copies 64 input words into the shared window each frame (`0X30000`
  non-zero writes 72 with tones, 8 without) and core 1 takes them (its
  `1Y00200` 66 vs 1); the frame command sees the window at zero every time,
  so the traffic is transient — written and consumed inside the frame;
- **the ColdFire gets the inputs back**: eDMA channel 7's 128-word block per
  frame (a ring of buffers `0x80005460..0x80005e60`, page-stepped) reads
  126–128 non-zero words = 8 slots × 16 samples, **50,298 words over 400
  frames against 9 without tones**. That is the input-capture staging Bryan
  inferred from count and shape (`EXTERNAL.md` §8) — measured by content now
  for channel 7; channel 6's fixed block at `0x80005e60` stayed zero and is
  still 🟡.

So O8's "the DSP computes silence" on the inbound direction was the absence of
input, not a defect: feed the ESAI and the read-back carries it.

### The frame's audio topology, measured from the block log

Per host frame, from the log's directions, sizes and addresses (✅), with
what each block carries (🟡 unless said):

| direction | eDMA ch | words | ColdFire side | carries |
|---|---|---|---|---|
| → DSP | 0 | 672 | `0x800021d0`/`0x80002c50` (A), `0x80001c90`/`0x80002710` (B), ping | 8 × 84-word track records (`DSP.md`); ~14 non-zero |
| → DSP | 0 | 64 | `0x80005460 + n·0x80`, rotating | a slot record (`DSP.md`); ~11 non-zero |
| → DSP | 0 | 128 | `0x80000110`/`0x80000310` (B), `0x80000210`/`0x80000410` (A) | per-voice records; ~30 non-zero |
| → DSP, **core 0 only** | 0 | 512 | `0x80003190`/`0x80003590`, ping | ✅ the two cores' 256-word read-backs of the previous ping, forwarded; **zero in every run** |
| ← DSP, each core | 1 | 256 | core 1 → `0x80003190`/`0x80003590`, core 0 → `0x80003390`/`0x80003790` | 🟡 the core's track output mix; **zero in every run** |
| ← DSP, core 0 | 6 | 128 | `0x80005e60`, fixed | unknown; zero |
| ← DSP, core 0 | 7 | 128 | `0x80005460..0x80005e60` ring | ✅ the eight input slots × 16 samples |

❌ `DSP.md`'s table has `0x80003190` as "read-back (DSP → CPU), 256 words":
the address is right, the direction is half the story — core 1's read-back
lands there and the ColdFire then sends 512 words FROM it to core 0. The
reading that fits (🟡): core 0 owns the ESAI, so tracks 1–4's mix goes core 1
→ ColdFire → core 0 to be summed into the output ring.

### ❌ Audio OUT is silent, and the place it stops is not the port's

TX0 is zero on all eight slots in every run, and the write hook says why in
the narrowest possible terms: **core 0 never writes a non-zero word into the
ESAI-out ring X:0x8000–0x80ff** during the run (186 writes at boot, the
payload's init; none after). Tried, all silent, all with the sequencer
running and the poked trig firing at frame 344:

| fixture | what it would have shown |
|---|---|
| the RIG as staged (T1 THRU, master track on), tones in | a THRU track passing the inputs, tracks 1–4 → core 1 → ColdFire → core 0 |
| the same, `MASTER_TRACK=0` | the master track was the gate |
| T5 THRU with a trig in A01 step 2, tones in, master on and off | a THRU on the ESAI core itself, no inter-core hop |
| T1 FLEX on slot 1 with `KICK.WAV` staged (`stage_card.py --audio`), `TSMODE=0` | the ColdFire rendering a sample into the 512-word block — ❌ the WRONG block (it is the forwarded read-backs); the sample goes into the track's 84-word record and, with the main level posted, it renders sample-exact (O10) |

What the instruments say about where it stops:

- the sample IS loaded: the card log shows 47 READ commands covering all 176
  sectors of `KICK.WAV` during the load, and the load does more work (forces
  6,488 vs 6,424) — but the 512-word outbound block and both 256-word
  read-backs stay zero before and after the trig;
- the trig reaches the DSP as ONE changed word in core 1's 128-word voice
  block (30 → 31 non-zero) and nothing follows on core 1 — no region of
  track size is written after frame 344 (`--dsp-writes`, frames 343/346/351/399
  compared) and core 1 never writes the shared window;
- the T5 file trig (A01, TRAC mask 0, step 2 — set after finding `pattern-trig`'s
  pattern index is 0-based, so the first attempt landed in A02) does not fire
  at all: the live-nibble log shows only the poked T1 trig. Whether file trigs
  fire under the emulators is untested beyond this (🟡);
- **route A does the same on the same card** (the O6 oracle on the KICK card:
  the same seven live-nibble writes, nothing at `0x80004f1c`), so this is not a
  port/oracle disagreement — it is a path neither emulator drives: the
  sequencer's trig never becomes a DSP voice. `FW_TRIG_WORDS` (`0x46104d26`)
  is zero in every plain-trig run, as it has been since M5 (`RTOS_FORK.md`
  §10.14's control shows the recorder masks reaching it).

Reading the dispatcher's output stage (P:0x1cb–0x203: per output channel,
16 squared samples, a peak, a one-pole envelope and a gain that ramps toward
0 or 0x80 on a threshold compare) says the ring is written by a
limiter-shaped stage — but that is reading, and the write hook says the
stage's input is zero, so nothing about it has been measured. Do not start
there.

**Gate for the remaining half (O9b), not passing:** a THRU track trigged
with `--audio-in tones` puts the tones on TX0 (the WAV carries them, the
ring's non-zero write count is non-zero). It waits on the trig → voice path
on the ColdFire, which is oracle-side work (route A first, `RTOS_FORK.md`
§10), not the port's.

### What the port can do NOW that it could not before

The recorder records the INPUTS, and the inputs now carry content all the way
into the ColdFire's capture buffers. Bryan's click question (the seam-patch
falsification, 8 Sep) asked for exactly "content injected at the source, the
packed pool blocks and the outbound flex stream read across the arm" — the
port can inject it at the ESAI, which is the true source, with the recorder
fixture (`~/octa/backups/RECTRIG_20260906_step9`). Playing the recording back
still needs the voice path above.

### Cost

A 400-frame sequencer run with the cores is **~1 minute wall** (51–61 s
measured, 1,600 frames in 56 s; the load dominates). The "~25 minutes" in the
O8 notes is stale.

### No regression

`ctest` 7/7; O6 with the cores 5/5 against the stored oracle; M6a with the
cores; `make check` — see the PR.

## Milestone O9b — the trig → voice path: audio out of the DSP (8 Sep 2026, branch `coldfire-o9b`)

O9 ended with "no track ever starts under either emulator". It did start; four
things between the trig and the ESAI were wrong, none of them the trig path,
and each was found by an instrument added for it. **Gate: a THRU track trigged
with `--audio-in tones` puts audio on TX0 — passes.** 400 frames, 28 ticks,
the O6 oracle's 5 fields agree, TX0 slots 1–4 carry the mix on 6,213 of 6,399
frames after the transport start (two stereo pairs, the second 3.7 dB lower),
no fault, no stall.

### 1. Coverage said the trig starts a voice; the voice rendered at gain zero

`--coverage FILE` (every ColdFire PC from the transport start, with counts;
`Machine::step` now counts instructions, which the PC watch's timestamps
needed too) and a diff of a trig run against a no-trig run: the trig's own
footprint is 124 PCs (the p-lock applier `0x4000c42c–0x4000c5a0`, an
armed-bitmask check at `0x4000bd14`, a compare, a counter), and one more
activity per frame from then on — a per-voice EMAC mixer at `0x40004444` that
sums four input-capture streams into stereo, 16 samples a call, with gains
from a voice record at `0x80000510 + 384·ping + 48·track` (byte 0 = routing
mode, word +2 = level). Its jump table took case 0 — all gains cleared — for
every voice because the record's level read 0.

The level is written mode:level by the frame builder (`0x4000cb2e`),
smoothed by an EMAC chain at MACSR `0xb0` (`0x4000cbfc`), then scaled by a
**main gain table at `0x80003c60`** in a second chain at MACSR `0x60`
(`0x4000ccae–0x4000ccfc`). ✅ That table is written by exactly two sys
commands — **command 4 = SET MAIN LEVEL** (`msg[1]` = 0..127, handler case
`0x40061e0a`, ten longwords of gain:(0x8000−gain) from the curve at
`0x400bcd90`) and command 68 (`127 − msg[3]`) — and NEITHER emulator's load
posts either: 0 writes to the table in the port and in route A. Every voice
was multiplied by zero. `--main-level N` posts command 4 after the load
(`Rtos::setMainLevelLive`, the same scratch-message path as select-bank); the
report prints the table's first entry (`0xbf7fc081` at 64). Route A got the
same post the same day (the parallel session's `set_main_level_live`).

### 2. MACSR S/U is bit 6, and in fractional mode it is not signed/unsigned at all

With the table filled the second chain still stored 0. Its inputs were right
(record `0x0100:0x7f00`, gain `0xbf7f:0xc081`); the port's `movclrl` returned
the products left-aligned and the firmware keeps the LOW words (`movclrl
acc0,d3; swap d3; movclrl acc1,d2; movew d2,d3`). ❌ The port had S/U as bit 4
(that is R/T) and read every accumulator out as `ACC[39:8]`. ✅ The CFPRM
(Rev. 3, ch. 6, MOVCLR pseudocode; `MOVE from ACC` says the same) for
`F/I = 1`:

    OMC,S/U,R/T == 000  → ACC[39:8] → Rx
    OMC,S/U,R/T == 001  → ACC[39:8] rounded by [7:0] → Rx
    OMC,S/U     == 01   → 0 → Rx[31:16]; ACC[39:24] rounded by [23:0] → Rx[15:0]

So at `0x60` the chip hands the 16-bit-rounded top of the accumulator back in
the LOW word, which is precisely what the chain keeps. `v4e.cpp`'s `accRead`
is now the pseudocode, every branch (integer signed/unsigned with OMC
saturation; fractional with OMC, S/U and R/T), and `g_macsrSigned = 0x40`.
QEMU (route A) has the S/U branch and `MACSR_SU = 0x40` already. `ctest`
7/7 before and after — the O2 self-test never exercised S/U. **The number
that only makes sense one way:** the record's mode byte survives the scaling
(`0x0100 × 1.0 → 0x0100` in the low word) only under this read-out; under
`ACC[39:8]` it is destroyed, which is why both chains cannot be satisfied by
any operand alignment (an experiment that was tried and reverted).

With that: `0x80000510` reads `0x01007f00` after the chain, outbound non-zero
words 43,222 → 177,690 per 400 frames, inbound 50,298 → 129,619, **the
ESAI-out ring gets non-zero writes and TX0 slots 1–4 carry the THRU tracks'
tones** — for 348 frames, then the firmware executed `halt`.

### 3. The frame interrupt is the DSP's bank word, not a timer

`0x4000ab40: halt` sits under `cmpl 0x800000e0,%d0; bcc`: the frame handler
reads the DSP's bank id from `0x2000001c` **with no ready check**
(`0x4000aafa`) and halts unless it is 0 or 1. Under silence the read-back
data words were 0 and a mistimed read passed by luck; with audio a data word
landed there (`0xffffd500`). So on hardware the interrupt that runs the
handler must be what announces the bank word. The port now raises the frame
edge when core 0 executes its bank write — payload A's `000073: movep
r3,x:<<M_HOTX`, once per ring half, `g_bankIdPc` — instead of the
free-running 16-sample timer (`--frame-timer` restores it). The DSP's first
bank id, written during the load and waiting at P:0x97 for the host, is
delivered where route A fires its first frame (one period after the frame
clock comes on) so the transport start keeps the oracle's phase; a ColdFire
idle skip ends at the edge (`tickSamples` returns the samples it advanced).
Measured: bank write → host take 0.002 samples, bank write → `0x8c` 0.004
samples, DSP frame-to-frame 16.00 (min 15.27, max 16.95). "ESAI frames per
host frame" now reads 16 on 395 of 399 with min 14 / max 17 — that is the
ColdFire's own latency jitter on the command, visible now that the edge is
the DSP's; the DSP's frames themselves are exact.

### 4. A modulo pre-decrement that left the buffer — the eleventh vendored defect

Then the DSP stalled 13–38 frames after the trig: core 0 at P:0xa3 waiting on
core 1's mailbox for a whole ring half, DMA2 finished un-re-armed (the
dispatcher only re-arms after catching `DSR2 == 0x8070/0x80f0`, a one-word
window), core 1 in a 196,608-iteration voice loop (`do y1,>$20b` at P:0x205
with `y1 = 0x030000` from the record's count field at Y:0x42). Instruments on
the way: `--dsp-writes`' per-word watch (`--dsp-watch core:space:addr`: the
last 16 writers with PC, the executed-PC ring, r0/r4/r6 and the area), a DSP
PC watch with a register dump (`--dsp-pcwatch core:pc[:fromExecuted]`), a
trace window (`--dsp-trace-from`), the interrupt-vector histogram in the
report, and a trap for the first `TCSR0.TE` with the PCs and address registers
before it. The chain, all measured:

- core 1 took **vector 0x54 = TIMER0 Compare 230,027 times**; neither payload
  writes a timer register. Payload B's word at P:0x54 is `move x0,y:(r4)+` and
  a fast interrupt runs the two words at its vector inline — with whatever r4
  the voice builder had, so the count field got a raw host word;
- TCSR0 was written with `0x0c2687` (an audio sample) by the interpolator's
  `move b,x:(r2)+` at P:0x1a78 with `r2 = 0xffff8f`;
- r2 came from `x:-(r2)` at P:0x1a66 with **r2 = 0 and m2 = 0x3f**: the
  vendored AGU (`agu.h updateAddressRegister`) holds r unsigned, the
  decrement underflowed to `0xffffffff`, the lower-bound test could not see
  it and the upper-bound test subtracted the modulo: **`0xffffbf` where the
  chip gives `0x3f`**. The next sixteen writes walked `0xffffc0–0xffffff` and
  the timer block.

Fixed in `agu.h` (the update is done relative to the buffer base in signed
arithmetic), `tools/dsp56300.patch` regenerated. ⚠️ `dsp_host` renders every
effect on this AGU and a `x:-(rN)` at the base of a modulo delay line is an
ordinary idiom, so the shipped effects were audited directly: `make check`'s
bit-identity gates cannot see a change common to both sides of a comparison,
but `send_probe --layout RS --wav` rendered with and without the fix is
**byte-identical** (529,244 bytes, `cmp`), and its peak/THD/spur lines match.
✅ No shipped effect was rendered on the underflow path.

Also in this milestone: the two cores are interleaved in 64-instruction
quanta (`stepCore`; `runCoreUntil` steps core 1 alongside core 0 inside a
pull) — hardware runs them in parallel, and a whole budget slice each in turn
could hold core 0's mailbox wait past the ring window. The stall's root cause
was the AGU, not this, but the interleaving stays as the nearer model.

### What the port can do now

`--dsp --main-level 64 --audio-in FILE|tones --audio-out PREFIX` renders the
firmware's own mix of the inputs through the DSP to a WAV. Step 5 of O8 (the
firmware driving `verify_twocore`'s layouts) is reachable: audio in, the
sequencer, the per-track records and the ESAI out all carry content. Open:
which input slot is which physical input and which output slot is main/cue
(a per-slot spectral pass or eight single-tone runs); the FLEX sample path
(a staged `KICK.WAV` is read from the card but the 512-word block stays zero
— the sample loader / voice start for FLEX is the next locate, with
`--coverage` and the block log as the instruments); the `0x8c` jitter.

## Milestone O9c — the slot map (started 8 Sep 2026, branch `coldfire-o9c`)

Eight runs, each with a 1 kHz tone at −20 dBFS on ONE of the eight RX0 slots
(`--audio-in out/o9c/tone_slotN.wav`, the RIG project, `--main-level 64`,
poked trig at step 2), reading TX0 per slot and the DSP's capture staging
block (`--dsp-peek 0:X:4700,128;0:X:2700,128`, the 128 words eDMA ch 7 takes
back each frame) at the end. ✅ Measured:

| tone on RX0 slot | lands in the capture block at | TX0 slot 1 / 2 / 3 / 4 |
|---|---|---|
| 0 | words 0,1 (+8k): pair at +0, L | −78 / — / −82 / — dBFS |
| 1 | words 2,3 (+8k): pair at +0, R | — / −78 / — / −82 |
| 2 | words 0,1 (+8k): pair at +0, L | **−35** / — / −39 / — |
| 3 | words 2,3 (+8k): pair at +0, R | — / **−35** / — / −39 |
| 4–7 | nowhere: the ESAI-in ring holds four words per sample (slots 0–3) | silence |

So: **TX0 slots 1/2 are one stereo pair and 3/4 a second, 3.7 dB lower**
(main and cue is the natural reading, 🟡 unmeasured which is which); the
capture block's pair at +0 — C/D in the ColdFire's own reading
(`RTOS_FORK.md` §10.18, "A/B at +0x80, C/D at +0") — is fed by RX0 slots 2
and 3 at full level, and **the +0x80 pair (A/B) is never written by the port's
DSP**; RX0 slots 0 and 1 reach the same +0 positions and the same outputs
**43 dB down**, which is not a THRU gain anyone would set. 🟡 Two readings,
neither measured: the A/B copy uses a gain that another never-posted sys
command sets (the family the main level belongs to — the project's `DIR_AB`
is 0, and the input-gain/direct paths are all ColdFire state), or the port's
ESAI delivers the pairs to the wrong half of the DSP's input stage. The
falsifier is a write watch on the +0x80 words of the staging block and a
`--coverage` diff between a slot-0 run and a slot-2 run: the code that
differs is the A/B path. RX0 slots 4–7 not reaching the ring is 🟡 the
vendored ESAI/DMA (the ring stride is 4 where the payload enables 8 slots);
it costs nothing today because the unit has four inputs.

✅ **Measured next (a write watch on word 64 of the staging block and a PC
watch at the copy's entry, `--dsp-pcwatch 0:55e`):** the +0x80 pair IS written
every frame, with zeros, by the copy at P:0x55a called three times a frame
from P:0x2df/0x2e2/0x2e6 — and its source for the +0x80 half is **the
ESAI-OUT ring, `r1 = 0x8080` with `n1 = 7`**: the pair is TX0 slots 0 and 7
of each output sample, which nothing in the port writes (the mix goes to TX0
slots 1–4). The other two calls read the ESAI-in ring (`r1 = 0x8280` and
`0x8282`, `n1 = 3`). So "A/B" in the ColdFire's capture block is not a raw
input pair at all on this path: it is whatever the DSP puts on output slots 0
and 7 — 🟡 the direct-monitoring / input-thru placement, which some ColdFire
state the emulated load never sets would switch on (the project's `DIR_AB`
is 0), the same family as the main level. The 43 dB-down leak of RX0 slots
0/1 into the C/D positions is still 🟡. And `RSMA = 0x0f` is the firmware's
own (payload A `P:0x30032`): four receive slots is the chip's configuration,
not the vendored ESAI's.

✅ **The input map, settled by the project's own direct levels.** A scratch
copy of the RIG with `DIR_AB=100` and `DIR_CD=100` (the mixer's direct
monitoring, 0 in the project) staged and run with the same single-tone files:

| tone on RX0 slot | TX0 slot 1 at DIR 0 | at DIR 100 |
|---|---|---|
| 0 | −77.9 dBFS | **−34.9** |
| 2 | −35.1 | −30.0 |

DIR AB moves slot 0 by 43 dB and DIR CD moves slot 2 by 5 dB, so **RX0 slots
0/1 are inputs A/B and 2/3 are C/D**, and the "43 dB down" leak was the direct
path at level 0 (🟡 a floor, or T1's INAB at a low setting in the part). The
direct level does NOT travel in the 64-word track record: its `+0x32` field
is the track LEVEL (the ColdFire writes `0x6c00` = 108 there every frame at
`0x80005492`), and the DSP's copy of that field at X:0x4632 is overwritten
with 0 by the staging copy at P:0x568 each frame — the pointer table at
X:0x202–0x209 is not decoded here and the reading of `x:(r0+0x32)` as a gain
at P:0x2f4 is left 🟡. **TX0 slots 0 and 7 stay silent at DIR 100 too**, so
the capture block's +0x80 pair (the ColdFire's A/B) still has no source in
the port; what places audio on those two output slots is the open item.

❌ **"TX0 slots 1–4" was an artefact, and so was "master track on pans it
right".** With the master track off the same tone came out on slots 0/2
instead of 1/3, yet a `--dsp-peek` of the ESAI-out ring showed it at **ring
words 2 and 4 in both runs**: the ESAI's slot counter and DMA2's ring index
are not in a fixed phase — the rotation between them differed between runs
and moved within a run (0..7 over 400 frames, as DMA2 is re-armed). The
ring is the truth; `--audio-out` now keeps each frame by RING WORD, reading
DSR2 at the frame's end (`(DSR2 − 9) & 7`, minus nine because the DMA has
already loaded the next frame's first word; checked against the peek), and
the report says "non-zero per RING WORD (slot + rotation min..max)". ✅ So,
in ring words per sample: **(2,3) is one stereo pair and (4,5) the other,
3.7 dB lower; 0, 1, 6, 7 are never written by the mix**, and the capture
block's +0x80 pair reads ring words 0 and 7 — which is why the ColdFire's
"A/B" is empty here: nothing in this project's state (DIR at 100, CUE 127
with main-to-cue, master track on or off — all tried) writes those words.
🟡 Which pair is main and which cue, and which physical output ring words
0/1/6/7 reach, is hardware's to say (the codec's slot assignment); the
WAV's channel order is now stable enough to compare against `dsp_host`.

### The THRU path's baseline, measured (the comparison's precondition)

T2 (THRU on C/D, FX2 = SEND, so no effect in the path), the RIG as staged,
main level 64, no trig needed (THRU tracks start at frame 0):

| probe on input C | ring word 2 | ring word 4 |
|---|---|---|
| sines at 60 / 300 / 4,000 / 12,000 Hz, −20 dBFS | −34.1 / −34.1 / −34.3 / −34.2 dBFS: **gain −11.1 dB, flat** | −37.4 (−3.3 dB below) |
| a full-scale kick (`out/test_audio/kick.wav`) | first output sample **155 samples** after the first input sample; peak −17.5 dB below the input; a least-squares scaled-copy fit leaves a residual only 2.3 dB under the output | −3.2 dB below |

So the THRU path is flat and linear at −20 dBFS and a **full-scale input is
limited** (the output stage at P:0x1cb–0x203 is a limiter; the kick loses
6 dB more than the tones and stops fitting a scaled copy) — any comparison
must keep the probe well under full scale. The 155-sample latency is 🟡
unexplained in parts: 128 of it is the input-capture lag the ColdFire side
also sees (`RTOS_FORK.md` §10.18), the rest the DSP's frame pipeline.
T1 (THRU on A/B, FX2 = BusDelay) passes the same kick at **−52 dB** — its
input level in the part is what the "43 dB down" leak was — so the RIG's T1
is not usable as the effect fixture without editing its machine page, which
the project tools do not do yet.

### The comparison, attempted: the effect runs, the knobs do not arrive

A fixture built from the tools: the RIG with **T2's FX2 = FILTER (stock id
0x04)** written into part 1 and its saved copy (`ot_project` internals,
checksum re-read), FILTER's WDTH stamped to 64 on T2 (`stamp-slot ... filter
WDTH 64 --track 2`; ⚠️ called from a shell loop it reported "no knob 'WDTH
64'" — call it plainly), staged and run with the five sines. Measured:

| | 60 / 300 / 1k / 4k / 12k Hz, ring word 2, relative to the FX2 = SEND baseline |
|---|---|
| FX2 FILTER, page all zero | +0.0 / −0.0 / −0.0 / −0.2 / −0.1 dB |
| FX2 FILTER, WDTH stamped 64 | +0.0 / −0.0 / −0.0 / −0.2 / −0.1 dB |

Flat both times. Not because the effect is skipped: a DSP PC watch on core 1
shows FILTER's init (payload B `P:0x591`) entered 3× at the load and its proc
(`P:0x59d`) every frame. ❌ **First reading, retracted: "the page byte never
reaches the DSP".** It does — the WDTH byte I stamped (64) lands in the
per-voice block at **X:0x4000 word 39 = 0x034000** (`0x40 << 8`), the one
word that differs between the WIDTH-0 and WIDTH-64 cards across every landed
block. The response was flat because **the page I stamped was an open filter**
(BASE 0), and WDTH does nothing to a steady sine through an open filter — a
test that could not see the thing (`send_probe` THD, again). ✅ The stamped
byte DOES cross via the ColdFire's page publish (`0x80000ec4/0x80000ecc`,
`DSP.md`; the RAM part page at `0x4017109e` reads `0x7f40007f` = BASE 127,
WDTH 64…). The remaining question is narrower: WDTH landed in the block but
FILTER's proc reads its coefficients from X:0x2c0/0x3a0, which did not change
— i.e. whether a *companion* field is unpacked to the proc's block, not
whether the page crosses.

❌ **RETRACTED 8 Sep 2026 (O9d): this was T2's FX1 path, not FX2's.**
`stamp-slot` stamps every part/track naming the module in FX1 OR FX2, T2's
FX1 is FILTER in every part, and the part that PLAYS had T2's FX2 = SEND
(the fixture had put FILTER only in part 1 — see O9d). X:0x4000 word 39 is
T2's FX1 WDTH (record = 32 words per track, FX1 page at +6, FX2 at +12), so
X:0x2c0 is the FX1 instance. The FX2 page path is proven in O9d, on T1.
~~✅ **Re-measured with BASE (page-1 slot 0, the cutoff): the parameter path
is proven end to end.** Stamping FILTER BASE to 40 on T2's FX2 lands
**0x28 in FILTER's own coefficient block at X:0x2c0 word 7** (the FX2
instance; X:0x3a0 is the FX1 instance, unchanged), which the WDTH-only card
does not have.~~ So a part's page byte travels: part data → the ColdFire's
`0x80000ecc` publish → the per-voice block at X:0x4000 → unpacked into the
effect's parameter block where its proc reads it. The 300 Hz…12 kHz response
is still flat at −34 dB because BASE 40 / WDTH 64 is a transparent band for
these tones (the mode/HP/LP that would attenuate live on page 2, a count-3
select the tools do not stamp yet), not because the parameter is missing.

**Where O9c stands:** the port renders the firmware's mix of real ESAI
inputs through both DSP cores, with each track's FX1/FX2 running and reading
its part's parameters — the machine O8's step 5 needs. The bit-exact
comparison against `dsp_host` is now a bounded job, not an unknown: it needs
(a) a part setting that makes the effect non-transparent, and (b) the gain
structure reconciled. Both are now measured facts, not locates:

- ❌ **RETRACTED 8 Sep 2026 (O9d)** — every measurement in this bullet was
  taken on T2, which in the port has NO INPUT (its FX1 FILTER at BASE 127 /
  WDTH 0 closes the path, exactly as `rig_render` said) and whose FX2 in the
  playing part was SEND, so "identical" was inevitable. Page-2 selects DO
  cross under the load (O9d: FILTER HP/LP on T1, record low byte 0→1, TX0
  changes). ~~**A page-1 FILTER setting cannot make it filter, and the page-2
  select that would does not reach the DSP under the load.**~~ Four page-1 (BASE, WDTH)
  combinations all give the same flat output; FILTER's response is gated by
  its page-2 HP/LP selects. `stamp-slot` DOES write page 2 (my earlier "page 1
  only" was wrong — it computes `P2_OFF + track·30 + 6 + slot−6` and the LP=2
  byte lands in the part), but a card with LP = 24 dB renders **identically**
  to LP = 0, and FILTER's coefficient block at X:0x2c0 is **byte-identical**
  between the two — so **the page-2 select never crosses to the DSP**, where
  a page-1 knob (BASE → X:0x2c0 word 7) does. ✅ **The locate, sharp now:**
  the per-frame packer forwards page-1 knobs positionally (`x:(r6+i)`,
  `DSP.md` §) but not the page-2 selects; on the real unit a page-2 select is
  applied when the effect is (re)selected / the part is applied, a path the
  emulated load does not run — the SAME family as the main level (sys command
  4) and the −1 per-track init bytes. So O9c's finish is not a `stamp-slot`
  feature; it is to drive that apply path after the load.

  ✅ **And the apply path is already located — it is the CC→page-2 work.**
  `modules/ccpage2` (PR #98, hardware-confirmed) had to replicate the
  firmware's page-2 editor `P2EDIT` (`0x4003a474`) exactly, and
  `docs/midi_re_cc.md` §7 has the whole publish path: a page-2 value reaches
  the DSP ONLY through the **live lane `0x80000830 + track*72 + 0x20 + slot2`**,
  which the copier `0x4000cae8` ships every frame — there is no DSP post; the
  Part store and shadow do not reach the DSP by themselves. ✅ Measured here:
  the emulated load leaves that lane byte **zero** even with the part carrying
  LP=2, which is exactly why the select does not cross. ⚠️ A `--poke` of the
  lane at the ccpage2 offset did NOT move stock FILTER's block (equal-length
  compare identical) — because ccpage2's `slot2` layout and counts are the BUS
  ENGINES' (`VERB_COUNTS`/`DLY_COUNTS`), and stock FILTER's page-2 lane offset
  is its own. The mechanism is known for the bus engines; the
  per-effect lane offset for a STOCK effect is not pinned (poking every byte
  of the copier window 0x80000898–0x800008af left FILTER's block unchanged),
  and `--poke` (added this milestone) is the lever once it is.

❌ **RETRACTED 8 Sep 2026 (O9d): a THRU track's TX0 output DOES carry its
FX2.** EQUALIZER on T1's FX2 (the track that actually has input in the port)
changes T1's read-back, the forwarded block and TX0 alike; on T2 nothing
could change because T2 renders nothing. The "reframing" below is the
fixture, not the firmware. ~~**But a bigger reframing, strongly supported: a
THRU track's TX0 output is a PRE-FX2 monitor, so the comparison cannot read
the effect there.**~~ Every
FX2 setting tried — page-1 BASE/WDTH across four combinations, a page-2 LP
select in the part, a live-lane poke — leaves the TX0 ring word 2 output
**flat/identical**, even though FILTER's proc runs every frame (`P:0x59d`)
and page-1 BASE provably reaches its coefficient block (X:0x2c0 word 7 =
0x28 for BASE 40). An effect whose input reaches it and whose output changes
nothing downstream is not in the measured path. So O9c's comparison tap is
wrong, not its parameters: a THRU track monitors its raw input, and FX2's
output goes to the bus / the recording, i.e. the **read-back block
`0x80003190`** (DSP→CPU, `DSP.md` §), not the ESAI monitor. ✅ **Confirmed with a second effect:** EQUALIZER (id 0x0c) on T2's FX2 with
extreme page-1 gains (0,127,0,127,64,127) renders **byte-for-byte the same
TX0 output as EQ with page 1 all zero** — 0.0 dB delta at 300 Hz and 8 kHz.
Two different inserts, extreme settings, no change at TX0: a THRU track's TX0
monitor does not carry FX2 output. The parameter path (page 1 proven, page 2
= the ccpage2 lane) stands; what O9c had wrong was where to listen. 🟡 Next:
the FX2 output goes to the recording / bus path — read the DSP-side read-back
source (`X:0x400` → `0x80003190`) with a recorder armed, or use a machine
that plays into FX2 (the FLEX loader). Both tie O9c's comparison to the
recorder path, i.e. to the same DSP-in-the-loop work Bryan's click needs.

⚠️ **Tool note:** `ot_project.py stamp-slot` crashes on a bare id
(`mod.params[slot]` index error when `mod` resolves but the slot is out of
its manifest range) — the EQ page-1 bytes here were written directly. Worth
a guard before the next fixture round.
- ✅ **The THRU monitor gain is the track's own input level, NOT the main
  level.** Sweeping `--main-level` 0/32/64/100/127 leaves the THRU output at
  −34.5 dB throughout (the gain table[0] goes `0x8000`→`0x80000000` and the
  monitor does not care). So the main gain table O9b had to post scales
  TRIGGED VOICES; a THRU track passes its input at its INAB level (−11.5 dB
  here for T2's part). `dsp_host` (`rig_render`) applies the effect to the
  stem at `--amp` with no mixer, so the comparison divides out a KNOWN
  constant per path — the THRU's INAB gain, not a main-level-dependent one.

`rig_render.py` on the same part (stock image, `--stem T2=`) rendered T2 at
−138 dBFS: its FX1 FILTER at BASE 127 / WIDTH 0 closes the path ~~where the
port's does not — a second disagreement, harness versus firmware-driven,
recorded here and not chased (the port is the one running the ColdFire)~~.
✅ **O9d: the port's does too** — T2's chain output in core 1's read-back is
316 rms against 3.0 M in its input record (−80 dB). The tone O9c heard at
TX0 was T1's. No disagreement.

**So the comparison's precondition is the parameter path, not a fixture.**
Next: watch the ColdFire's page publish for T2's FX2 slots (`--watch-mem`
on `0x80000ec4`/`0x80000ecc`, `--coverage` diff of a stamped against an
unstamped load), find what posts it, post it after the load the way the
main level is posted, then re-run the five sines — the FILTER response
against `dsp_host`'s is the gate.

## Milestone O9d — the comparison fixture was measuring the wrong track (8 Sep 2026, branch `coldfire-o9d`)

O9c ended on "a THRU track's TX0 is a pre-FX2 monitor; the FX2 page-2
select never crosses; the comparison tap must be the recorder". All three
were one fixture defect. What settled it was a new instrument — every
host-port block's CONTENT at the move (`--block-dump FILE`, binary;
`tools/scratch/blockdump.py summary|diff|wav`) — and the rule it enforces:
two runs that differ only in a part byte must differ somewhere on the host
port before any DSP-side "identical" means anything.

### ✅ The O9c EQ pair was byte-identical on the host port

Re-running O9c's EQUALIZER cards (page 1 extreme vs zero on T2's FX2) with
the dump: **every block of every class identical in all 250 frames** —
including the per-voice records that carry the pages. The EQ bytes were in
the card (bank 1 part 1 and its saved copy 5, slots 1/3/4/5) and in the
ColdFire's live lane after the load (`0x80000870` = `00 7f 00 7f 40 7f`,
`0x80000ecc[1] = 0x0c`) and never reached the DSP. Cause, measured with
`--watch-mem` on the id arrays and the lane:

- the LOAD applies **bank 1 part 1** (`0x40009384/0x4000938e` in `engine`
  at 43,401 samples: T1 FX1 = 0x12, T2 FX2 = 0x0c);
- the TRANSPORT START re-applies the **saved bank's pattern part**
  (`0x4000c40e/0x4000c41e` in `main` at 896,464: T1 FX1 = 0x1c, T2 FX2 =
  **0x09 = SEND**), and the load-time refresher `0x4000c19c`
  (`0x4017107a + bank·635712 + part·6322 + track·24` → lane
  `0x80000816 + track·72`, pre-image `0x80000a5c + track·64`) overwrites the
  lane and the pre-image from THAT part.

So every O9c FX2 fixture — FILTER on T2 in "part 1 and its saved copy", the
EQ pair, the page-2 LP card, the lane pokes — ran with T2's FX2 = SEND.
`stamp-slot` writes all eight parts of every bank, which is why its FILTER
BASE/WDTH bytes DID land — in T2's **FX1** (FILTER in every part), i.e.
X:0x4000 word 39 = T2's FX1 WDTH and X:0x2c0 = the FX1 instance.
`ot_project.py set-fx` now writes an id (+ pages) into all eight parts of
every bank for exactly this reason.

### ✅ The frame builder's record, decoded from the dump

Per-voice DSP record (`0x80000110`/`0x80000310` → core 1, `0x80000210`/
`0x80000410` → core 0; 128 halfwords = **32 per track**, one DSP word per
halfword): +0..5 AMP, +6..11 FX1 page 1, +12..17 FX2 page 1 (`value<<8`,
page-2 selects in the LOW byte of the same halfword — the "flag word" of
`DSP.md` §9), +27 = FX1 id, +28 = FX2 id. Assembled by the copier
`0x4000cae8` from the pre-image `0x80000a50 + track·64` (halfwords 12..29)
and the page-2 lane `0x80000830 + track·72`, then slewed (`0x4000cc20`,
MACSR 0xb0) and scene-modulated (`0x4000ccfc`, gain table `0x80003c60`,
scene buffer `0x80000ed4 + track·0x40`). The 672-halfword track records
(`0x80001c90` → core 1, `0x800021d0` → core 0; 4 × 84 words) carry the
**THRU audio**: words 8..38 even = 16 L samples (R zero for a mono input).

### ✅ With the EQ on the track that has input, everything moves

T1 FX2 = EQUALIZER in every part, page 1 `40 127 64 100 0 64` (B) against
`64 ×6` (A), tone on RX0 slot 2 at −20 dBFS:

| block class | A vs B |
|---|---|
| per-voice records → core 1 | differ from frame 2 (the page) |
| core 1 read-back `0x80003190/0x80003590` | differ from frame 9 |
| forwarded 512-word block → core 0 | differ |
| core 0 read-back, ch 6 block | differ |
| TX0 (`--audio-out`) | differs |

Same with FILTER on T1's FX2, page 1 BASE 100 / WDTH 0, **page-2 slots 6/7
= 1 (HP/LP 24 dB) against 0**: the record halfwords differ by exactly 0x0101
(the low byte), read-backs and TX0 differ. **Page 1 and page 2 both cross
under the emulated load; the THRU monitor carries FX2; the comparison tap is
TX0 (or the read-back, per track).** EQ's proc (payload B `P:0x972`, from
the X:0x235 table; init `P:0x96d`) runs every frame on core 1.

### ✅ Why T2 renders nothing, and where each tone lands

Tone on RX0 slot 2 → **T1's** 672-record (rms 3.0 M) → T1's read-back slot
(610 k) → TX0 −38 dBFS. Tone on RX0 slot 0 → **T2's** record (3.0 M) →
T2's read-back **316** → TX0 −102 dBFS: T2's FX1 FILTER (BASE 127 / WDTH 0,
in the part) closes the path, as `rig_render` said. 🟡 Which physical input
each THRU listens to is the part's INAB/INCD selects (`-, A B, A, B, A+B`;
T1's PB page `00 00 40 …`, T2's `00 01 7f …`) and is not decoded here; the
measured fact is slot 2 → T1's chain, slot 0 → T2's chain. The O9c DIR
measurement (RX0 0/1 = A/B on the DSP's direct path) is unaffected.

### What this leaves

The O9c gate (a THRU track's FX rendering bit-identical to `dsp_host`) now
has a working fixture on T1 and a decided tap; the remaining work is the
comparison itself: `dsp_host` with EQUALIZER at the same page on the same
tone, level-matched to the port's T1 read-back (the per-track chain output,
before the master mix), and the THRU gain structure (VOL, INAB, the −11 dB)
divided out.

### ✅ The comparison — O8's step 5 / the O9c gate — PASSES (T1, EQUALIZER, stock image)

T1's chain INPUT is the audio in its 84-word record (16 L samples per
frame, −11.2 dBFS) and its OUTPUT is its slot of core 1's read-back (the
per-track chain output, before the master mix); `tools/scratch/
o9d_compare.py extract|fit` pulls both out of a `--block-dump` and fits
lag, scale and residual. The same input goes through `rig_render` on the
stock image (`--project … --bank 2 --part 1 --stem T1=… --amp K`), which
takes T1's ids and all twelve knobs from the part. Measured, 300 Hz tone,
samples 1500..3900 of 4000:

| T1 | fit | residual |
|---|---|---|
| FX1 = stock 0x1c LO-FI, FX2 = EQ flat / boosted | −13 dB, lag −32 | −16.6 / −16.9 dB, gain stepping ±1.5 dB per period |
| FX1 = SEND, FX2 = EQ flat (`64 ×6`) | **−11.906 dB** (k = 0.253931 = 2130129/2^23), lag −32 | **−125.6 dB** |
| FX1 = SEND, FX2 = EQ boosted (`40 127 64 100 0 64`), stem × k | 0.000 dB, lag −32 | **−95.7 dB with NO fit** (the float pre-scale's rounding) |

Three things fell out on the way, each measured:

- **The parameter words the DSP sees are dsp_host's, word for word.** Core 1's
  per-instance block (`X:0x208` → 32 words per track, T1 at X:0x25d):
  +0..5 AMP `00 7f 7f 40 40 7f`<<16, +6..b FX1 page 1, +c..11 FX2 page 1
  `28 7f 40 64 00 40`<<16, +12..14 FX1 page 2 as `knob<<16 | companion<<8`
  (`7f0000 000000 400000`), +15..17 AMP page 2 (`010100 …`), +18..1a FX2
  page 2 (`003000 400100 000000` = the part's `0 48 64 1 0 0`), +1b/+1c the
  ids (`000900 000c00`). That is exactly `dsp_host`'s `setParams`
  composition (+$c/$d/$e knob|companion) — the DSP's unpack turns the
  record's low-byte packing into it.
- **The track gain is applied BEFORE the FX chain, and it is a constant**:
  k = 2130129/2^23 (−11.906 dB) for this part (AMP VOL 64, LEVEL 108;
  🟡 not derived from those — measured as the fit). `rig_render` at
  `--amp 1.0` drove the EQ 12 dB hotter than the unit does, and the stock
  EQ saturates there: the boost read +4.95 dB in the harness against
  +6.22 dB in the port until the stem was pre-scaled by k, after which the
  two agree to the rounding of the pre-scale.
- **Stock LO-FI (0x1c, the RIG's T1 FX1) is nonlinear**, which is what the
  "stepwise gain" of the first pass was; with FX1 = SEND it is gone.

So the port, driven by the firmware from the card, renders a THRU track's
FX chain as `dsp_host` does, to the bit for a linear page and to −96 dB
with a float pre-scale for a saturating one; the one thing `rig_render`
does not model is the pre-FX track gain k (its docstring's "AMP VOL … not
modelled"), and the comparison must feed it the stem at k. Falsifiers:
another effect (FILTER with page 2 live) or another track/core giving a
residual above −90 dB with the stem at its own k.

Instrument rule added to the port: **a DSP-side "byte-identical" between
two cards is not evidence until the host-port dump shows the cards differed
on the way in.** Three O9c retractions rode on skipping that check.

## Milestone O10 — FLEX playback renders, sample-exact; the recorder loop under the port (8 Sep 2026, branch `coldfire-o10`)

### ✅ "A FLEX voice never renders in either emulator" is retracted for the port

O9 staged `KICK.WAV` on T1's FLEX slot and watched the 512-word block to
core 0 and the read-backs; O9b/O9c repeated "the FLEX loader is unlocated".
Both watched the wrong block, and O9's run had no main level (O9b's root
cause A). The audio of a voice — THRU or FLEX — travels in the track's
84-word record (O9d). Fixture: the RIG with T1 = machine type 1 (FLEX) on
slot 1 in banks 1–2, all parts and mirrors, T1 FX1/FX2 = SEND, the kick
(`scripts/make_test_audio.py kick`, 16-bit mono) staged at slot 1's own
card path, `--poke-trig 2 --main-level 64`, no audio in:

- T1's record carries audio from frame 1 (the pattern's own step-1 trig),
  0 dBFS peak, retriggered at the poked trig (the kick restarts at record
  sample 5,528 = frame 345.5 for a trig at 344); the read-back and TX0 ring
  words 2–5 (both channels, a centred voice) carry it.
- With the slot's `TSMODE=0` the record IS the file: `kick.wav << 8`,
  residual **−100.2 dB**, k = 1.000, lag −16 samples (one frame). With the
  RIG's `TSMODE=2` (timestretch) the fit is −3.9 dB — grains, as expected.

So the ColdFire's sample renderer runs under the port from the card, sample
for sample; the card read (176 sectors) O9 saw was the load doing its job.

### ✅ The capture pairs, measured from the ch 7 blocks (corrects O9c)

Each ch 7 block is one page of the ColdFire's input-capture ring
(`0x80005460 + page·0x100`, 64 words): **+0 = the C/D pair, +0x80 = the A/B
pair**, 16 × (L,R) each, exactly RTOS_FORK §10.18's layout. A tone on RX0
slot 2 lands at **+0x80 (A/B, L)**; on slot 0 at **+0 (C/D, L)**. O9c's
"+0x80 is fed from TX0 ring words 0/7 and never written" is ❌ retracted —
it is written, from the ESAI-in ring, and carries what the DSP calls
RX0 slot 2. 🟡 The DSP's DIR path called slot 0 "A" (O9c); the two names
disagree by two slots, which is the receive ring's phase against the ESAI
slot counter (the same rotation O9c found on the transmit side). The
ColdFire's naming is what the recorder uses: **INAB records the +0x80 pair
= RX0 slot 2/3 in the port.** ✅ Stable, not a rotation: three runs with
different load lengths (20.0/20.5/21.0 s) all land the slot-2 tone in the
+0x80 pair — the receive ring's phase is fixed where the transmit side's
rotates (O9c), so the two-slot offset between the DSP's DIR naming and the
ColdFire's capture naming is a fixed fact of the port, 🟡 unmeasured on the
unit. `--audio-in tones` (500·(k+1) Hz on slot k)
sidesteps the question: the recorded frequency says which slot was taken.

### ✅ The track record's audio is a list of segments (corrects O9d's "words 8..38")

Decoded from the FLEX run (`tools/scratch/o10_recloop.py record_audio`):
an 84-word track record carries **16 stereo pairs in segments**, each a
4-word header `(count, 0, 0x40000, tag)` followed by `count` (L,R) pairs. A
THRU voice ships two empty headers then the 16 pairs at words 8–39 (what
O9d read); a FLEX voice ships `(15 pairs)(1 pair)`, `(14)(2)`, `(13)(3)`,
`(12)(4)`, `(11)(5)` — the split walks one sample per frame with the first
header's count (0x0f, 0x0e, …) and the tag word steps `0x040000 +
n·0x400000`. 🟡 What the split means (a source-position/interpolation
boundary the DSP consumes) is not decoded; what is measured is that parsing
the segments gives the voice's audio sample-exact (the kick fit above, and
the −104 dB below), and reading a fixed window does not — two "seams" were
found and retracted inside an hour before the parse (frame-periodic
residuals against a fitted sine are the tell).

### ✅ Bryan's 128 BPM / RLEN 4 loop under the port: sample-continuous for 32 passes

Fixture = route A's own (`tools/scratch/make_seam_fixtures.py` → `r4_128`:
16-step 1X A01, T1 = recorder trigs REC1/INAB at steps 2/6/10/14, RLEN 4,
T2 = FLEX on R1 with play trigs at the same steps, 128 BPM), staged as a
card, `--audio-in tones` (500·(k+1) Hz on RX0 slot k), `--main-level 64`,
8 bars = 42,000 frames (≈45 min wall), `--block-dump`.

- The recorder records **input A = the 1500 Hz tone on RX0 slot 2** (the
  +0x80 capture pair), and T2 plays R1 from the first play trig at step 2
  (record sample 5,056 = frame 316; the trig write is at frame 322) at
  −20 dBFS, the input's own level. Play trigs land every 20,672 samples.
- **One sine, fitted on passes 2–8, fits all 32 passes to −104.4 dB rms
  (24-bit rounding), maximum deviation 0.0% at every sample** — through
  every pass boundary and every retrigger, pass 9, 17 and 25 included.
  `o10_seam.py` (residual phase of the tone) and a per-sample residual at
  each trig agree. The voice's audio that reaches the DSP has no seam.
- This is CONSISTENT with route A's recording-level finding (§10.16.5: the
  ninth arm lands on the eighth recording's last sample), not against it:
  the play trigs walk the same fractional step grid as the arms
  (4 steps = 20,671.875 samples → 20,672 ×7 then 20,671), so a recording that
  starts one input sample early is also played one sample early, and the
  stream stays continuous. On this grid, at this tempo, with play trigs on
  the arm steps, there is no click by construction.
- 🟡 TX0 in this run sits at −75 dBFS (the RECTRIG project's levels) with a
  −18 dB residual against one sine in every pass alike — an instrument
  limit at that level (the O9c ring-rotation capture, the output stage), not
  a seam; the DSP chain's continuity was proven on the THRU comparison at
  normal levels. The voice tap is the decisive one here.

### ✅ Three more of Bryan's shapes, four bars each, same result

| fixture (`make_seam_fixtures.py`, 4 bars = 21,000 frames) | voice tap, one sine over every pass |
|---|---|
| RLEN MAX, 128 BPM, play trigs on the REC steps (his test 3) | −104.4 dB rms, max 0.00 % |
| RLEN 4, 120 BPM (his clean control) | −104.4 dB, 0.00 % (pass = 22,050) |
| RLEN 4, 128 BPM, `--self`: play trigs on T1, the recording track | −104.4 dB, 0.00 % (T1 plays and records a 1500 Hz tone; INAB records the inputs, not its own output) |
| RLEN 4, 128 BPM, play trigs OFF the record steps (4/8/12/16 against REC at 2/6/10/14) | −104.4 dB, 0.00 % from the first trig at step 4 (`r4_128_off`) |

And the read-back tap (the chain OUTPUT, T2's slot of core 1's 256-word
read-back, `o10_continuity.py --readback`) on the 8-bar run: −69 dBFS (the
RECTRIG part's own T2 level, 49 dB under the voice), residual −56 dB rms
and 0.5–0.7 % max **in every pass alike** — the DSP's arithmetic floor at
that level, nothing localised at any trig or boundary. ✅ Done: with T2's AMP VOL at 127 (the AMP page is the six bytes BEFORE
the track's FX1 row in `ot_project`'s P1_OFF layout — lane flat 12..17; the
`+0x1b` "level" byte did nothing to the read-back) the read-back rises to
−57.1 dBFS and the residual against one sine is −58.9 dB rms, **broadband**
(every harmonic below −100 dB relative: it is T2's FX1 FILTER's own
low-level noise, not distortion) and **proportional to the signal**, with a
single-sample −0.5 % dip (−103 dBFS absolute) at each retrigger and no phase
step anywhere. The DSP side of a retrigger is clean to that level.

**So the port does not reproduce Bryan's click at 128 / RLEN 4 with play
trigs on the record steps.** What the port cannot see, and where the click
can still live: the unit's own trig-to-arm timing (the RTOS tick is 2× off
in both emulators — `--pit-clock`, recorded in O8; the 0x8c jitter is real
but the port's frame-lock is idealised), the DSP-side retrigger of a FLEX
voice on a buffer being written (the port's DSP runs the real code, but its
ESAI/DMA phase against the ColdFire frame is the port's), and any hardware
path outside the host port. All four falsifiers the port can run — a play trig NOT on a REC step, RLEN
MAX, the sound-on-sound shape, the 120 control — came back continuous: with
both mechanisms on the same sample grid the played stream is the input
delayed by the arm-to-trig offset, and that offset never changes. Bryan's
click therefore needs the two to ROUND DIFFERENTLY on the unit (the pass is
20,671.875 samples at 128 BPM — a fraction; at 120 it is 22,050 exactly,
which is why 120 is clean), 🟡 inferred from the arithmetic, and the port
cannot show which side rounds which way because it rounds both the same.

✅ **Measured, the port's own timing of the two:** the play trig's sub-frame
nibble (`FW_LIVE_NIBBLE`) is `f` for passes 1–8 (frames 322, 1614, …, 9366),
`e` for passes 9–16 (10658 …), `d` for 17–24 (20994 …) — one sample earlier
every eight passes, in lockstep with the arm offset route A measured
(15 ×8 then 14, §10.16.5). Both derive from the frame builder's event
arithmetic, so in the port they cannot drift apart. 🟡 **What would make the
unit click on exactly Bryan's pattern:** a stage on one side that works in
2-sample units (stereo pairs). At 120 BPM a pass is 1,378 frames + 2
samples, so the nibble walks by two per pass and a 2-sample stage tracks it
exactly — clean; at 128 it walks by ONE every eight passes, which a 2-sample
stage cannot follow — one click per eight passes, i.e. every two bars,
starting at the ninth pass (Bryan: "~6th repeat" onset, clicks at RLEN 4,
16 and MAX alike, 120 clean). Hardware falsifier that costs one capture: a
tempo whose pass fraction walks by an ODD number of samples per pass but
not every eight (e.g. 125 BPM: 21,168 samples/pass exactly = clean
predicted; 130: 20,353.85 → walks; the prediction is click iff the
per-pass walk is odd), against a tempo with an even walk.

### Upstream check (8 Sep 2026, after a prior-art note from a parallel session)

joelanders/mc68k-md-mm PR #5 ("Expose shared HI08 command acceptance and
receive status", open, based on our pin 4a6d0d1) adds optional callbacks so
CVR HC follows DSP acceptance. The port already does exactly that on its own
side — `dsp.cpp` clears HC/HCP from the dsp56300 interrupt-taken hook (O8,
measured) and does not use mc68k's HI08 acceptance path — so the PR neither
changes what the port relies on nor duplicates code the port would drop.
Bump the pin when it merges; nothing to port. dsp56300/dsp56300 issue #5 is
the AGU modulo pre-decrement defect O9b fixed in `agu.h`; still open
upstream, our patch stands.

## Milestone O11 — the first hardware failure diagnosed under the port: the one-aux return (8 Sep 2026, branch `coldfire-o11-return`)

`FAILURE_MODES.md` "the one-aux return never reaches T8" (flash 6, tag 20):
sending AUX produced wet on T1 and T5, the engines' own hosts, and nothing
on T8; the local gate was green on exactly the property the unit falsified,
and the cause was guessed as a liveness stamp lost across cores. The port
runs the shipping remix (`make bus REMIX=bamsep27`) from a card with the
firmware driving both cores, so it can reproduce the unit.

### ✅ Reproduced, in the read-backs

Fixture: `ot_project.py rigproj` on the cleared RIG backup (every part of
every bank gets the rig: T1 CHARACTER + DELAY SERVER, T5 MODULATION + REVERB
SERVER, T8 CHARACTER in BUS mode as the return, SENDs with AUX 30–50), staged
as a card, a 300 Hz tone on RX0 slot 0 (T2's THRU input, AUX 40), 2,000
frames. Per-track read-backs (the chain outputs):

| | T1 (delay host) | T5 (reverb host) | T8 (return) |
|---|---|---|---|
| port, shipping image | prints wet from frame 500 (−43 dBFS L, −48 R) | prints the reverb from frame 200, rising to −53 | L −26 (the master mix's dry; T8 is the master), R only the reverb rising to −48 |
| `rig_render` (dsp_host), same part and stem | silent | silent | −58 L/R, the reverb, a tail |

The hosts printing their own wet IS the hardware symptom. A DSP write watch
on the return's stamp word (`Y:0x360d8`) showed only the clear-on-read
writes; a PC watch on the station's stamp instruction (`P:0x183b`) never
fired: the station never stamped.

### ✅ The cause, measured on the dispatcher: r7 has THREE blocks per track

The station pins itself to track 8 by `r7 & 0xff00 == $6700/$6800`. A PC
watch after its `move r7,a` read **r7 = 0x6a00** for track 8's FX1, every
frame, init and proc. A PC watch on both `jsr (r2)` sites of the stock
dispatcher (P:0x4d7 FX1, P:0x50d FX2 on payload A; P:0x2cc/0x302 on B) gave
the whole map on both cores:

| position | FX1 r7 | FX2 r7 |
|---|---|---|
| 0 (T5 / T1) | 0x6100 | 0x6200 |
| 1 (T6 / T2) | 0x6400 | 0x6500 |
| 2 (T7 / T3) | 0x6700 | 0x6800 |
| 3 (T8 / T4) | **0x6a00** | **0x6b00** |

A write watch on the counter `X:0x20a` names the three bumps per track:
P:0x4b4 (FX1), P:0x4ea (FX2) and **P:0x524, unconditional, after FX2**
(`move x:>$20a,b / add #>$100,b / move b,x:>$20a` at 0x518–0x524, identical
in the stock image), reset to 0x6000 at the frame start (P:0x379). So
**r7 = 0x6100 + 0x300·pos + 0x100·(fx−1)**. The harness had
`1 + 2·pos + (fx−1)` (dsp_host's r7probe comment; its "track 2 FX2 = 0x6400"
🟡 reads as position 1's FX1 under the real stride), which is right for
position 0 only. The return's pin and the send client's track-8 refusal
(`$6800`) were both derived from that model: they matched in `dsp_host`,
never on the unit — the gate was green and the unit was wrong for the same
reason. Not a cross-core race: the reverb host and the return share core 0.

Also seen on the way: the DSP holds THREE copies of the four per-instance
parameter blocks (X:0x25d, +0x80, +0x100; r6 cycles 0x2c3/0x343/0x3c3 for
the same instance across frames) — one instance, triple-buffered
parameters, not three instances.

### ✅ The fix, proven both ways

`character.asm` pins `$6a00/$6b00`; `send_client.asm` refuses `$6b00`;
`rig_render`, `verify_onebus` and `send_probe` pass `-r7 1 + 3·pos + (fx−1)`;
dsp_host's comment corrected (patch regenerated). Under the port with the
rebuilt image: the stamp instruction fires every frame, **T1 and T5 print
nothing for 2,000 frames, T8 returns** (R = the reverb building; L = the
master mix's dry plus the reverb, since T8 is the master and `rig_render`
does not model that routing). `make verify-onebus`: every property holds on
both cores — and with the r7 model fixed but the old pin it failed 10 of
25, which is the gate finally seeing what the unit saw. UNFLASHED; it is
the flash-7 candidate (stamp-defaults before play, as ever).

**What this milestone establishes:** a hardware failure the lock-step
harness could not show was reproduced and located in one session with no
flash, from the card, with the firmware's own dispatcher as the instrument.
The rule it leaves: **any module logic keyed on a dispatcher fact (r7, r6,
X:0x213, block addresses) is measured under the port, not modelled in
`dsp_host`.**

## Milestone O12 — the bus itself under the firmware: bit-identical to `dsp_host` (8 Sep 2026, branch `coldfire-o12-bus`)

O9c's gate, on the shipping rig's AUX bus instead of a THRU insert: T2 sends
AUX into the delay host on core 1, the return station on core 0 reads the
last live stage. Fixture: the one-aux rig (`rigproj`, image
`bamsep27` with the O11 pins), `MASTER_TRACK=0` so T8's read-back is the
return alone, `rig_render` fed T2's own chain input (the 84-word record's
audio) at the port's pre-FX gain k = 0.253931 (O9d). Three fixture facts
had to be learned first, each measured:

- **The send client mono-sums the block** (`x:(r0)` + `x:(r0+1)`, `asr #1`)
  before scaling by AUX. `dsp_host` writes a mono stem into BOTH channels;
  the port's THRU with a tone on one input is left-only, so every send
  deposited 6 dB less. With the tone on both inputs of T2's pair the
  steady-state return matched to 0.0 dB (−29.7 / −29.7 dBFS).
- **The ColdFire slews the knobs** (the 160-frame marker slew), so a send's
  AUX ramps from 0 after the transport start; `dsp_host` has the value from
  block 0. Under a steady tone the port's return simply runs ~4,000 samples
  behind the harness's envelope. A probe that starts after the slew (the
  kick from sample 4,000) removes it.
- **The delay's modulation LFO is history.** With MDEP 48 the repeats
  wander ±30 samples window to window between the two (the LFO's phase
  after thousands of frames of load versus block 0). MDEP 0 for the gate.

Not the cause, each checked on the way: the tempo (`--tempo 120` changed
nothing), the auto-gain (the delay reads count 1 and reciprocal 1.0 under
the port, PC-watched at `P:0x79e/0x7a8`; with one client both sides have
counts 1,1,1,0), the parameters (T1's DELAY SERVER page 1 and 2 words on
the DSP equal `rig_render`'s), the bus scratch (rotation, reciprocal table,
counts identical; the buffers 8 dB lower = the mono-sum above).

**Result, kick on both inputs after the slew, one client, MDEP 0:**

| | lag | scale | residual |
|---|---|---|---|
| T2's chain (SPECTRUM + SEND) | −32 | 0.000 dB | **−131 dB** |
| the return, samples 7,000–17,500 (the repeats) | −36 | 0.000 dB | **−120 to −200 dB** per window |
| the return, whole run | −36 | −0.04 dB | −23 dB (the onset window and the render's end edge) |

The 36 = the 32-sample record pipeline (O9d) + 4: four block-latency stages
on the bus (send→accumulator, accumulator→delay, delay→chain, chain→return,
each "two buffers back") at the firmware's 16-sample frame against
`dsp_host`'s 15-sample block. The bus's cross-core mechanism — the rotation
each core tracks privately, the four-deep buffers, the liveness stamps, the
chain buffer — produces the same words under the firmware's real ordering
of the two cores as under lock-step. BUS.md's "what only hardware can show"
(a return that flickers, repeats missing from the reverb) does not show
here either; 🟡 the port's core interleave is still not the chip's timing
(O8), so this is the strongest local statement, not a hardware one. The
reverb stage was not bit-compared (its allpass modulation is history, like
MDEP); its level matched within 1 dB in the both-engines run.

### 🟡 The reverb stage: level-matched, not bit-compared, and why (8 Sep 2026, later)

Same fixture with the reverb instead of the delay (T1's FX2 = SEND, one
client, MOD 0): the port's return is **deterministic** — identical to
−200 dB across load lengths and across core-interleave quanta of 1, 64,
1,000 and 100,000 instructions (`--dsp-quantum`, added for this; the delay
fixture is likewise quantum-independent) — so it is NOT a cross-core race.
Against `dsp_host` it is −7.5 dB residual with the envelope within ±3 dB
per window and one extra frame of lag (52 = 36 + 16: the reverb's
accumulator read crosses cores, one more block back).

The difference is in what T5's engine is GIVEN, not in the engine: the
DSP's per-instance block for T5 carries FX1 slots 2 and 5 and FX2 slot 2
as fractional, time-varying values (`0x321a`, `0x3f`, `0x28ad`) where the
part holds 0, 0, 0 — on Sam's RIG project. Ruled out by measurement:
the scene crossfader (poked to 0 at `0x460d16c8`: unchanged), the track's
LFO depths (zeroed in the part: unchanged), the pattern (the PATTERN= key
did not move the port off pattern 0 — 🟡 the loader's pattern source is
not that key). The pre-image `0x80000a50` for T5's FX2 slot 2 is written
0x7f00 by the load, 0 by the refresher and 0x6400 by the slew packer
(`0x4000d688`) at the transport start, none of them 0x28ad — the modulated
value enters between the pre-image and the block, i.e. in the frame
builder's slew/scene stage (`0x4000cc20`/`0x4000ccfc`, O9d), from per-track
state this project carries and the toolkit cannot yet read or clear.

The alternative fixture — the rig on the RECTRIG backup, which has none
of that (T5's words come out exact: `28 30 00 00 00 00`, `00 40 00 64 40
7f`) — cannot hear anything: its T2, set to THRU with the RIG's THRU page
bytes copied in, never gets the transport-start write (only tracks 0 and
5 do), so it renders silence. ✅ Sam: T1 and T2 are THRU on his projects
(drums and synths in), which is why the RIG-based fixture hears and the
RECTRIG-based one does not. **Toolkit gap (the way through, per Sam):
stamp a fresh project** — `ot_project` can set a machine type and a PB
page but not whatever else makes a THRU track start; that is the next
tool, and with it the reverb comparison is one run.

Tools: `rig_render --extra '<dsp_host args>'` (e.g. `-dumpy 36000,360d3,f`
to dump the bus scratch after a render, which is how the two scratches
were diffed word for word).

## What is NOT here yet

- **The rest of the peripherals.** The eDMA with its completion-timing rules
  (three wrong versions in route A, each with its own reproducible symptom),
  FlexBus/ATA and the card. (DSPI and the UARTs landed in O4 — the M6a gate
  could not be reached without them.) All are modelled in route A's
  Python, commented rule by rule with each failure mode recorded — that is the
  specification, and translating it is the bulk of the mechanical work.
- **The DSP side.** `dsp56kEmu` is already vendored, already patched for the
  shared window (`tools/dsp56300.patch`), and `tools/dsp_host` already runs both
  cores. Joining them needs the host-port protocol, which was decoded on
  7 Sep 2026 from the tape recorder (`emu_rtos.py --tape`): per frame the
  ColdFire alternates the cores, writes `0x81`, sends a destination/count pair
  to `0x2000001c`, then DMAs — 336-word per-track records plus a 128-word and a
  64-word block per core, with one 64-word block read back.
- **Audio out.** ~~The ESAI path is untraced.~~ ~~Traced in O9: input proven,
  output silent because no track ever starts.~~ O9b: THRU tracks pass the
  inputs to TX0 through the whole chain. ~~FLEX playback (the sample loader)
  is the open half.~~ ✅ O10: FLEX playback renders, sample-exact.

## The oracle, made concrete (7 Sep 2026)

`tools/emu_rtos.py --golden FILE` writes route A's M6a facts as JSON —
handoff PC, auto-pokes, every created task with its fields, which TCBs ran,
the first switch, the first 200 dispatches with their sample times, the gate
time. `out/oracle/m6a.json` is that file for the ONEAUX project: **10 tasks
created, 11 ran, first switch boot → main, gate at 204.95 ms** ✅.
`tools/ot_emu/oracle.py A B` diffs two such files field by field with no
tolerance except one PIT period on dispatch times, and reports a field the
port does not produce yet as MISSING rather than as a failure, so the port's
report can grow milestone by milestone. `docs/COLDFIRE_WORKORDER.md` is the
queue that uses it.

## The order to do it in

1. Port `emac_selftest` as a CTest, then the EMAC handlers. Nothing that
   computes should be trusted before that gate exists.
2. The peripherals, translated from route A, each with route A as the diff.
3. The DSP cores and the host port; audio last.

The rule that makes the rest delegable: **route A is the oracle.** Any
disagreement between the two emulators is a finding, not a nuisance, and the
one to trust is whichever can point at a firmware constant that only makes
sense one way (`RTOS_FORK.md` §10.16's reciprocal tables are the worked
example).
