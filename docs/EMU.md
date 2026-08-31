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

## Milestone 1 — boot-and-inspect, wired into the workbench ✅

`emu_bringup.boot(image)` returns a warm machine; `read_menu_tree(uc)` walks
the MAIN MENU tables (`docs/MAINMENU.md`) out of its RAM. `make remix`
(the remix workbench, `tools/remix/tui.py`) now has an **`e`** key: it boots
the *built* image (`out/mainos_bus.bin` — byte-compatible with the raw
section), confirms it reaches the RTOS handoff with no fault, and shows the
menu tree with any patched-in entry highlighted. This is the crow-flies form
of the no-flash gate: a cave that breaks early init **faults here instead of
on the unit**, and a menu-table patch is visible before a flash. It needs
`unicorn` in the interpreter that runs the TUI; without it the view degrades
to an "unavailable" message and the rest of the workbench is unaffected.

Boot is ~4 s: execution runs in native bursts (`emu_start` with a count),
with a per-instruction hook turned on only to pin a loop's bounds when a
stall is suspected. A stall is a PC confined to a small window across several
bursts; a bounded loop (memset) is told from a flag-poll by an event-driven
write counter that only a store advances.

## Milestone 2 — the live screen, via the detour harness ✅

The firmware's *actual* menu now renders as text, navigable, out of the warm
machine — `render_menu(r, cursor)` returns the real renderer's output as
`(x, y, string)` tuples, and `make remix` → `e` shows it in a framed LCD with
up/down moving the cursor and the submenu preview following, as on the unit.

**The capture primitive** is `FUN_40012bd8` — the "draw string at (x,y)" call
every renderer funnels through (189 call sites; the list drawer `FUN_40037590`
and the PERSONALIZE renderer `FUN_40068e00` both reach it). ColdFire cdecl,
args on the stack at callee entry; **passive capture needs only `x`, `y`,
`str`**, all on the stack / in RAM, so the hook is self-contained:

```
FUN_40012bd8(font, canvas, x, y, count, char *str)
  sp@(12)=x  sp@(16)=y  sp@(24)=str        (font 0x400ba876, canvas=window+36)
```

**The detour recipe** (the draw code runs in a task the boot never reaches, so
we call it directly against the warm machine):

1. Boot to the handoff (heap + window system are up).
2. Install the string-capture hook at `FUN_40012bd8`, plus a map-on-fault
   hook: a cold detour skips some setup, so a formatter can hold one stale
   pointer — map a zero page under it so its `strlen` reads `""` and the real
   row labels still render instead of faulting the whole draw.
3. **`ctl_flush_tb()`** — the draw fns were JIT-cached during the boot splash
   *without* the hooks, so a hook added afterward never fires on the cached
   block until the translation cache is flushed. (This cost a real debugging
   session: the loop ran but the string primitive "wasn't called" — it was,
   the cached block just wasn't instrumented.)
4. Call `FUN_40064c18` (menu open) — allocates the window from the heap.
5. Set `[0x400cbf40]=1` (tree state) and **`[0x400cbd9c]=6`** (the visible-row
   clamp; a cold detour leaves it 0, and the row loop bound is
   `min(clamp, count)`, so 0 draws nothing).
6. Poke `[0x400cbd98]` = cursor row, then call `FUN_40064d7c` (draw). The
   selected row and the right-pane submenu preview follow the cursor.

The line pitch is 7 px and the origin is bottom-left-ish (the list drawer
steps y DOWN per row), so `layout_screen` maps larger-y to higher rows.
Selection highlight is a separate XOR-rect op `FUN_40012254` (`mode<0`) — not
captured as text yet.

**The FX2 dials page renders too** — `render_fx2(r)` detours to the EFFECT 2
SETUP window (`FUN_4005996c`) for track 5 and captures the chooser + param
row; it lists the *built remix's own effects* (`ChonVerb77`, `BongDelay77`,
`Send`). `make remix` → `e` → `f` shows it. (The effect's specific dial
*values* — the reverb's SIZE/MODE — need the effect assigned to the track,
i.e. a loaded project or a poked part-record; the chooser + param labels
render without one.)

**What is still not live: item-level descent inside the menu.** The MAIN MENU
is a fixed two-pane widget (categories left, the selected category's submenu
right), so moving the cursor already *previews* every submenu — but selecting
a submenu ITEM (to reach a param page, or PROJECT▸SAVE) needs the real key
handler `FUN_40064e64`, whose keycodes are position-dependent, and the
selection highlight is an XOR rect (`FUN_40012254`), not text. Repointing the
display at a submenu descriptor directly does NOT work: the firmware computes
the row x from 2-pane state that a cold repoint leaves unset, so the labels
land at a bogus x (`0x80003003`). Driving the key handler + capturing the XOR
highlight is the next increment.

## Both FX param pages, with the effect assigned ✅ (31 Aug 2026)

`render_fx2(r, track, effect_id)` and `render_fx1(r, track, effect_id)` render
the real FX2 / FX1 parameter pages — the effect's actual knob rows, not a
default. `make remix` → `e` → `f` (FX2) / `1` (FX1); left/right cycle the
effect. FX2 with `0x07` shows ChonVerb's knobs (SHMR/MODE/DIFF/SHFT/GATE/RATE/
HP/LP/IN); FX1 shows the stock effects (FILTER's BASE/WDTH/ENV/ATK/DEC/…, EQ's
FRQ/GN/…) — our inserts are all FX2, so the FX1 tables are stock.

**How the effect resolves.** The page draws the descriptor `table[id]` where
`id` is a per-track byte in the project Part: FX2 at `PART + PAT*0x18b2 +
track + 0x8ed88`, FX1 at `+0x8ed80` (`PART = *(u32*)0x46c82456`, `PAT =
*(u8*)0x100b14cf`). Our boot loads no project, so `PART` is null — `_prime_part`
maps a zeroed scratch Part and points the DB pointer at it, then `assign_fx2`/
the FX1 path write the id byte. In the BUILT image the id→descriptor tables
are patched (`build_bus.py`), so `0x07` is ChonVerb; in the raw image those
slots are NONE. (`0x06`/BongDelay aliases to SEND in the payload-A SPEC image
and renders empty — it lives on payload B.)

**Both SETUP windows** wrap the stage+draw: FX2 `FUN_4005996c` (drawer
`FUN_40037590`), FX1 `FUN_40059afc` (drawer `FUN_4003792c`). Calling one after
assigning the id is the whole recipe.

**Values.** A knob's displayed value is a byte at `PART + PAT*0x18b2 +
track*30 + slot + 0x8f084` (`set_fx2_value`), and the canonical writer is
`FUN_40054cd8(track, flat, value)` with `flat = 24 + slot` for FX2 page-1.
The value itself draws as a dial GRAPHIC, not text, so it is not captured by
the string hook — the audio side (`render_reverb`, the `v` audition view) is
where knob values are heard. Editing a value in the page + reading it back as
text is the remaining nicety.

## The RTOS fork — still open, still not forced

Milestone 2 took route **B** (detour) and it carries the workbench: a menu- or
cave-patch is visible and walkable without a flash. Route **A** (emulate the
RTOS — dispatch `trap #0` via VBR `[0x400b9668]`, drive a timer tick, run the
real scheduler) remains the later fidelity upgrade, the only one that could
show behaviour emerging from real task interleaving. Nothing built so far
needs it.

## Reproduce

```sh
make emu-setup                       # uv sync --extra emu -> .venv with unicorn
make remix                           # then press e to boot the built image
.venv/bin/python3 tools/emu_bringup.py [image]   # or the CLI directly
```

The emulator's one dependency (`unicorn`, with QEMU's CFV4E core — the DEFAULT
m68k core is plain-68k and cannot decode this CPU) lives in the uv-managed
`.venv` as the optional `emu` extra (`pyproject.toml`). `make remix` prefers
`.venv/bin/python3` and falls back to bare `python3`, where the emulator view
reports itself unavailable and the rest of the workbench is unaffected.

The CLI prints the boot outcome (the `trap #0` boundary), the auto-pokes, the
MAIN MENU walked from booted RAM, and the peripheral boot map. In the
workbench, `e` does the same against `out/mainos_bus.bin` and highlights what
the selection's patches added.
