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

## What is NOT here yet

- **The rest of the peripherals.** The eDMA with its completion-timing rules
  (three wrong versions in route A, each with its own reproducible symptom),
  DSPI, the UARTs, FlexBus/ATA and the card. All are modelled in route A's
  Python, commented rule by rule with each failure mode recorded — that is the
  specification, and translating it is the bulk of the mechanical work.
- **The run loop that uses them**: interrupt delivery, the burst scheduler and
  the handoff dispatch, i.e. route A's `Rtos` class. The models are ready for
  it; nothing calls them yet.
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
