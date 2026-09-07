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

## What is NOT here yet

- **The MCF5445x peripherals.** INTC0/1, both PITs, the eDMA with its
  completion-timing rules, DSPI, the UARTs, FlexBus/ATA and the card. All are
  modelled in route A's Python, commented rule by rule with each failure mode
  recorded — that is the specification, and translating it is the bulk of the
  mechanical work.
- **The DSP side.** `dsp56kEmu` is already vendored, already patched for the
  shared window (`tools/dsp56300.patch`), and `tools/dsp_host` already runs both
  cores. Joining them needs the host-port protocol, which was decoded on
  7 Sep 2026 from the tape recorder (`emu_rtos.py --tape`): per frame the
  ColdFire alternates the cores, writes `0x81`, sends a destination/count pair
  to `0x2000001c`, then DMAs — 336-word per-track records plus a 128-word and a
  64-word block per core, with one 64-word block read back.
- **Audio out.** The ESAI path is untraced.

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
