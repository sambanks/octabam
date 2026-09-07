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

## Milestone O6 — the eDMA and the frame clock ⛔ BLOCKED on O7 (8 Sep 2026)

The model is written and unit-gated; its **fidelity** gate is M6c, which needs
a loaded project and a started transport — O7. `COLDFIRE_WORKORDER.md` carries
the full entry; the two things worth keeping here:

**The three completion rules, and watching the gate fail.** `Edma` was
implemented first with route A's own *wrong* rule — everything completes at
once — and the gate failed on exactly the four paced assertions and nothing
else, which is the symptom route A recorded ("re-raised source 15 before state
0 could ack it; the ISR spun in state 6"). Fixing `start` to book a paced
channel at the DSP's next 16-sample boundary turned all 19 green. The other
two rules (an `SSRT` is bus speed; a memory-to-memory `START` is a copy the
caller busy-waits for) complete at once, and a linked channel is a burst that
completes **with** its parent, so ch1 → ch6 → ch7 is one boundary event.

✅ A detail that fell out of writing the test: **ch1's CSR `0x621` has no
INTMAJOR.** Only ch7 raises a line, and channel 7 is INTC0 source 8 + 7 = 15
— exactly the source route A names for the end of that chain. The first
version of the test asserted a line for ch1 and was wrong; the model was
right.

**The frame latch is cleared on the interrupt ACKNOWLEDGE.** Route A clears
`frame_pending` as it pushes the frame, because it hand-rolls the push. This
port lets Musashi dispatch the exception, so offering a line and having it
taken are different events — the latch is cleared from
`Machine::readIrqUserVector`, the core's own acknowledge, which is the same
moment. It is a **latch, not a count**: a masked edge source remembers one
edge, and counting them delivered ~540 phantom frames back to back in route A.

### What was measured about the block, rather than assumed

- ✅ Route A **cannot run with the frame clock on from boot**: a bare
  `Rtos(frame=True)` faults on unmapped memory, and priming the auto-map hook
  leaves its own state unusable. So there is no intermediate oracle
  comparison for the frame clock — it is M6c or nothing.
- ✅ The port with `--frame` is identical to frame-off through 100 ms, then
  wedges: dispatches frozen at 40 from 205 ms through 400 ms while PIT0 keeps
  firing, **1 frame interrupt taken, 0 eDMA transfers started**. No frame is
  delivered before main's unmask, so the mask is respected.
- 🟡 The wedge is *inferred* to be the ISR waiting for a DSP exchange nothing
  starts (the host port is O8, the chain is kicked from the sequencer path in
  O7). **Whether the frame model is right in the configuration that matters
  is not established, and only M6c establishes it.**
- ✅ No regression with the clock off: the oracle diff is still 8 compared
  fields, zero disagreements; `ctest` 6/6; `make check` green.
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

**⚠️ OPEN — the port runs PAST route A's end, and that is a divergence, not
a budget.** Route A stops at 6,189 commands with `M6b load: PASS` at a
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
- **Audio out.** The ESAI path is untraced.

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
