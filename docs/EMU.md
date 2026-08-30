# Local ColdFire emulator — Tier-0 bring-up

The workbench emu of `PLAN.md` §5. Goal: an iterate-with-a-cycle loop for
ColdFire/UI work (a menu patch, a cave) without a flash. This page is the
Tier-0 record — how far the real firmware boots under emulation and what it
needs on the way. `tools/emu_bringup.py` is the harness; re-run it to
reproduce every number here.

Markers as in `CHIP.md`: ✅ measured (here: observed in the emulator and
cross-checked against `objdump cfv4e` disassembly), 🟡 inferred + falsifier.

## The core is not the problem ✅

**Unicorn 2.1.4 with `ctl_set_cpu_model(UC_CPU_M68K_CFV4E)` executes this CPU
correctly.** Point-checked before trusting it: `mvz`/`mvs` extend right, and
EMAC `macl`+`movclrl` gives the exact product (32769 × −32767 = `0xC0000001`)
— the instructions r2 and the default plain-68k core both mangle
(`docs/EXTERNAL.md`). The pruned archaeology `emu_*.py` harnesses ran the
default core; the model flag is the fix, and the reason a boot is now
possible at all.

**With SP and SR seeded, the image runs ~7,000,000 instructions with zero
illegal-instruction faults**, through the whole early hardware init, and
stops exactly at the RTOS multitasking handoff. No decode wall anywhere in
between.

## What the boot needs, in order ✅

Seed the reset state the (absent) vector preamble would set — **SR before A7**,
or the supervisor/user stack banks swap and A7 lands in the wrong one:

```
SR = 0x2700   (supervisor, IRQs masked)   A7 = 0x48000000
```

RAM windows are `docs/ARCHITECTURE.md` §7; the stack grows down from
`0x48000000` into the `0x46000000` region.

**Peripheral MMIO** is modelled by callback, not backed by RAM, so every
access is logged — the log is the register map. Default read = all-ones,
which satisfies every "wait until bit SET" poll the boot uses. The boot map
(first touch of each register, from the harness):

| region | what it is (🟡 unless noted) | notes |
|---|---|---|
| `0xfc0c4000` | clock/PLL config | **load-bearing** ✅ — see below |
| `0xfc0a4066/69` | serial/UART-ish | writes `0x43`,`0x33` |
| `0xfc064000..01c` | a serial/timer module | heavy init, status polled at `+4` |
| `0xfc048018..05b` | another module | writes `0x1b`,`0x06` |
| `0xfc088000/02` | serial shift-out (LCD? ✅ shift-done in bit 2) | write datum, poll bit 2, 8×; ran 896× clean |

**One register's value is load-bearing, not just its presence:** the firmware
reads `0xfc0c4000`, takes the top byte as the PLL multiplier, computes
`sysclk = (reg>>24) × 12 MHz`, and **halts (`bra *` at `0x4000fa8c`) unless it
equals 264 MHz**. So the top byte must be 22 (`0x16`) — the harness returns
`0x16000000`. (entry read `0x40000418`; gate `0x4000fa78`.) This is the
pattern to expect: most peripherals only need to be "present", a few gate the
boot on a specific reply, and each announces itself as a halt you then decode.

## Async completion flags ✅

The boot polls flags that an interrupt handler — or the second DSP core —
would set, shaped `move.w (abs),d0 ; [mvz] ; cmpi.[wl] #imm,d0 ; bne self`.
Observed: word@`0x0` and word@`0x2000`, each awaited `== 0xffff`, each after a
kick subroutine (🟡 plausibly the two DSP cores' boot handshake, or a
memory-region test). The harness auto-satisfies them: a watchdog spots the
spin, decodes the read address and compared immediate, and writes it —
**at the LOAD width (`move.w`, 2 bytes), not the `cmpi.l` width**, or the low
word reads back wrong. A memset is told apart from a poll by a climbing write
counter (a bounded loop makes progress; a poll does not), so long BSS clears
(e.g. the ~90k-iteration one at `0x40000530`) are not mistaken for spins.

## The boundary: `trap #0`, the RTOS handoff ✅

Execution stops at `trap #0` (`0x40000e46`). It is preceded by
`movew #0x2000,%sr` (drop the interrupt mask) and followed by `bra *` (the
safety net if the scheduler ever returns) — the textbook "start multitasking:
enable interrupts, trap into the scheduler." This is the Tier-0/Tier-1
boundary named in `PLAN.md` §5.

Two facts for whoever crosses it:
- **Unicorn's CFV4E treats VBR as a no-op register** (`UC_M68K_REG_CR_VBR`
  reads back 0 with a deprecation warning) and does **not** auto-dispatch the
  trap — the `UC_HOOK_INTR` hook fires with `intno = 32` and the CPU
  otherwise faults. Crossing the boundary means dispatching the exception by
  hand: push the frame, fetch the vector, set PC.
- **VBR is loaded from the runtime variable `[0x400b9668]`** at `0x40000db6`
  (`movec %a0,%vbr`), and the table is built right after (default handler
  `0x40000d74` written to every slot). So the vector base is known at run
  time from that variable, which sidesteps the no-op register read.

## The fork ahead — do not pick it silently

Reaching the menu code past the trap is a design decision, not more of the
same grind:

- **A. Emulate the RTOS.** Hand-dispatch `trap #0`, drive a periodic timer
  interrupt for preemption, let the real scheduler run the real tasks. Most
  faithful; the most work; the display and input still have to be modelled or
  hooked on top.
- **B. Detour harness.** Skip the scheduler. Set up a plausible task context
  and call the UI functions directly — `FUN_40064c18` (menu open), the draw
  path, feed keycodes to the key handler — stubbing RTOS calls. This is the
  `emu_image.py`-shaped fallback in `PLAN.md` §5, and the cheaper route to the
  stated goal (walk a patched menu, test a cave) because it never needs the
  scheduler. It cannot catch anything that only emerges from real task
  interleaving — but menu-patch testing does not need that.

For the workbench's purpose (a text UI to iterate menu/cave patches without a
flash) **B is very likely the right first cut**, with A as a later fidelity
upgrade if something needs it. Either way the screen is read by hooking the
decoded draw path (`docs/MAINMENU.md` §7, `PARAM_PAGES.md`) rather than
emulating an LCD, and keys are injected at the software layer.

## Reproduce

```sh
pip install 'unicorn>=2.1'          # the DEFAULT m68k core is plain-68k; the
tools/emu_bringup.py                 # CFV4E model is what decodes this CPU
```

Prints the instruction count, the stop reason (the `trap #0` boundary), the
auto-pokes applied, and the peripheral boot map.
