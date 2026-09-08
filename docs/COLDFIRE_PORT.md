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
| T1 FLEX on slot 1 with `KICK.WAV` staged (`stage_card.py --audio`), `TSMODE=0` | the ColdFire rendering a sample into the 512-word block |

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
- **Audio out.** ~~The ESAI path is untraced.~~ Traced in O9: input proven to
  the ColdFire's capture buffers, output silent because no track ever starts
  under either emulator (the trig → voice path, oracle-side).

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
