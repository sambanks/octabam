# The ColdFire port — work order for unattended sessions

> **Read `docs/COLDFIRE_PORT.md` first**: what exists, what was measured, and
> the rule that governs everything here — **route A (`tools/emu_rtos.py`) is
> the oracle.** A disagreement between the two emulators is a finding, not a
> nuisance; the one to trust is whichever can point at a firmware constant
> that only makes sense one way, and until someone has, neither is.

This file is the queue. Each milestone below is **self-contained**: it names
the route A code it translates, the gate that decides whether it is done, and
the stop condition. A session takes ONE milestone, on its own branch, and
opens a PR only when its gate passes. If the gate cannot be made to pass, the
session writes what it measured into the milestone's entry here, opens the PR
as a draft titled with the milestone and "BLOCKED", and stops. It does not
start the next one, and it does not loosen the gate.

## Standing rules (they are not advice)

1. **Write the gate before the code, and watch it fail.** O2 did this for the
   EMAC and O3 for the peripherals. A gate that has never failed proves
   nothing (`tools/verify_bus.py`'s selftest exists for exactly this reason).
2. **Translate, do not redesign.** Route A's Python is the specification,
   comment for comment, including every ⚠️ and every "inferred". If a rule
   looks arbitrary, it is arbitrary in the firmware too; carry the comment.
3. **Encodings come from `m68k-elf-as -mcpu=5475` / `objdump -m m68k:cfv4e`
   on the real image**, never from a reading of the manual. Paste the
   listing beside the handler.
4. **Numbers in docs carry a confidence marker** (✅ measured, 🟡 inferred,
   ❌ retracted), and a retraction is propagated to every place that repeated
   the old number.
5. **Git:** branch, PR, merge. Never commit to main (O3 was committed to main
   by mistake and had to be moved; do not repeat it).
6. `ctest` in `out/emu` must stay green. `make check` must stay green.
7. **Before trusting an agreement, check the two machines are the same
   machine.** O5's gate passed on its first run and the agreement was an
   artefact: the port answered all-ones where the oracle answered zero, and
   the bytes that would have disagreed were being dropped on the floor. A
   knob sweep run on an instrument that cannot see the thing measures the
   instrument (`CLAUDE.md`, the `send_probe` THD entry).
8. **Ask nothing of the user mid-milestone.** Everything a milestone needs is
   in this file, `COLDFIRE_PORT.md`, `RTOS_FORK.md` and the route A source.
   If it is genuinely not, that is a BLOCKED PR, not a question.

## How to run the oracle

```sh
# the golden file (regenerate only if route A itself changes):
.venv/bin/python3 tools/emu_rtos.py --project out/projects/OCTABAM_ONEAUX \
    --set OCTABAM --name ONEAUX --tree out/_oracle_tree --until-gate --ms 1000 \
    --golden out/oracle/m6a.json
# the port's own report, same shape (grows milestone by milestone):
./out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --golden out/oracle/port.json
# the diff:
python3 tools/ot_emu/oracle.py out/oracle/m6a.json out/oracle/port.json
```

`out/oracle/m6a.json` as generated 7 Sep 2026: **10 tasks created, 11 ran,
first switch `0x46c7ae30 → 0x46c7ae84`, gate at 204.95 ms, 50 dispatches
recorded.** Those are route A's own measured numbers (`RTOS_FORK.md` §5).

⚠️ Route A needs a project attached to reach the gate (`--project`): without
a card it faults reading `0x100fff04` in main's settings path. That is a
route A fact, not the port's problem; the golden command above already does it.

## Done

| | what | gate | agrees with oracle |
|---|---|---|---|
| O1 | boots to the RTOS handoff | reaches `trap #0` | ✅ same PC `0x40000e46`, same two auto-pokes |
| O2 | the EMAC (fractional, `msac`, A-line dispatch) | `ctest` emac | ✅ hardware's three cases |
| O3 | PIT + INTC models | `ctest` periph, 14 rules | (wired in by O4) |
| O4 | the run loop: the kernel runs | `ctest` rtos + the oracle diff | ✅ 6 compared fields (❌ was written "8/8": the diff counted 2 it never compared); 10 created, 11 ran, 204.88 ms vs 204.95 |
| O5 | the rest of the memory; the serial stream | `ctest` rtos + the oracle diff | ✅ 8 compared fields; route A's 4831 serial bytes matched byte for byte |

## Queue

### ~~O4 — the run loop~~ ✅ DONE (8 Sep 2026)

See `COLDFIRE_PORT.md`. Three things future milestones should know:
**32-bit peripheral accesses must arrive whole** (`read32`/`write32`, or
Musashi splits them and a status register reads as garbage); **a deasserted
interrupt line must be withdrawn**, not left queued; and **the gate compares
first-run ORDER, not resumed PCs** — those track the `ips` knob, measured.
DSPI and the UARTs moved here from O5 because the gate needed them.

<details><summary>the original entry</summary>

### O4 — the run loop: interrupts delivered, the handoff dispatched *(Opus)*

**Translates:** `Rtos.step`, `_deliver`, `_candidates`, `_masked_pending`,
`_next_expiry`, `_push`, `_pop`, `_handle_trap` (the intno 32 / 256 halves
only), `_tick_timers`, and the idle rule at `MAIN_SPIN` — `tools/emu_rtos.py`
lines ~860–1042. Plus `Rtos.__init__`'s seeding of PIT0 and the INTCs from the
boot's logged peripheral writes (`install`, "seeded from N boot writes").

**Design, fixed by route A and not up for revision:**
- Time is counted in **samples**; the instruction budget per sample (`ips`,
  default 3990) is a knob. A burst runs until the next timer expiry, an
  INTFRC write (which must end the burst *inside* the instruction — hook the
  INTC's force callback to stop the run loop), a `trap #0`, or an `rte`.
- **Interrupt delivery** = push a 4-word frame (`0x4000 | vec<<2`, SR,
  return PC), set SR to `(sr & ~0x8700) | 0x2000 | level<<8`, jump to
  `[VBR + 4*vec]`, VBR = `0x40000000`. **SR before A7** (the bank swap).
- `trap #0` from a task = a blocking primitive: push the frame with return
  `pc+2` and SR `(sr | 0x2000) & ~0x8000`, jump to `[VBR + 0x80]`. Record
  `(sample, current TCB, trap pc, caller, object)` from the stack the way
  `_handle_trap` does (the lock primitive's trap at `0x40000a78` sits under
  12 bytes of saved registers).
- `rte` (Musashi will execute it natively — but route A pops by hand because
  Unicorn would not; **decide by measurement** which is right here: run both
  ways on the first `rte` and compare the popped PC/SR).
- Idle: a PC parked at `MAIN_SPIN` (`0x4001fc9c`, `bras .`) with nothing
  pending advances the sample clock to the next timer expiry.
- Task bookkeeping for the oracle: hook the create site (`CREATE`) and the
  scheduler's `rte` (`SCHED_RTE = 0x400005a6`) to record `created` and
  `dispatches` with the current TCB (`[0x800068fc]`).

**Gate:** `ot_emu --golden` produces `created`, `ran`, `first_switch`,
`dispatches`, `gate_ms`; `oracle.py` reports **zero disagreements** against
`out/oracle/m6a.json`. The dispatch order must match exactly; the sample
times within one PIT period.

**Known hazards, from route A's own history (`RTOS_FORK.md` §3):** reading SR
at a burst boundary through Unicorn's API corrupted the CCR — Musashi has no
such defect, but verify by comparing the CCR across a burst boundary with a
`cmpl/bne` pair split across it. Memory-write hooks on MMIO fire. `call_as_main`
is unsafe for anything that blocks (main is the only always-ready task).

**Stop condition:** the oracle diff is zero, or a disagreement is reproduced
and written into this entry with the two emulators' values side by side.

</details>

### ~~O5 — the remaining peripherals~~ ✅ DONE (8 Sep 2026)

See `COLDFIRE_PORT.md`. Three things O6 and O7 must know:

1. **Route A does NOT fault on unmapped memory in the golden configuration.**
   `_prime_menu` installs a hook that maps a zero page and returns True, and
   it stays installed; route A's region list goes 9 → 15 by the M6a gate. The
   port now grows the same way (`Machine::setAutoMap`, 4 KB pages, zeroed).
   Before concluding anything from a difference, check whether the two
   machines answer an unmapped address the same way — for months they did not.
2. **The serial count is a clock artefact; the serial STREAM is not.** The
   ring drains in bursts (5731 bytes at ips 3900/3990, 4831 at 4100 and up),
   and every one of those streams shares route A's 4831 as an exact prefix.
   The gate compares bytes over the common length.
3. **`oracle.py` used to count fields it never compared.** It now prints a
   `REPORTED` line for `gate_ms`, `pit0_fired` and `serial_sent`. When a
   milestone adds a field, compare it or expect to see it listed there.

The port still auto-maps **20.3 M accesses** on the way to the gate, almost
all of them a 64 MB clear at `0x42000000` and a 10.8 MB clear at `0x4f502c10`.
That is not a defect — route A covers the same spans — but O7's card is what
would make the two machines allocate from the same place, and it is worth
re-checking the span list once the project loads.

### O6 — the eDMA and the frame clock — ⛔ **BLOCKED on O7** (8 Sep 2026)

**The code is written and unit-gated; its FIDELITY gate cannot run.** Do not
re-do the model — take O7, then come back and run M6c.

`periph.{h,cpp}` now carries `Edma`, translated rule for rule, and
`rtos.{h,cpp}` carries the frame clock (INTC0 source 1 as a LATCH, eDMA
sources 8..23, the boundary fed from `tickTimers`, and the latch cleared on
the CPU's interrupt ACKNOWLEDGE — `Machine::readIrqUserVector`, which is
where route A clears it). `test_periph` gates 19 assertions: all three
completion rules, each of route A's wrong versions, the ch1→ch6→ch7 chain as
one boundary event, CINT/CDNE, replay, and "no INTMAJOR, no line". ✅ The
gate was watched FAILING first, on route A's own "completes at once" version
— the four paced assertions, and only those.

**What blocks it.** O6's gate is M6c, which needs a loaded project, a started
transport, a poked trig and the trig log — that is O7 *plus* the live-call
machinery (`call_as_main`, `start_transport_live`, `poke_trig`,
`install_trig_log`). There is no intermediate oracle comparison, and this was
checked rather than assumed:

- ✅ Route A **cannot be run with the frame clock on from boot at all.** A
  bare `Rtos(frame=True)` faults on unmapped memory immediately (nothing has
  primed the auto-map hook), and priming it leaves route A's own `Rtos` state
  unusable (`self.pc` is None). Its sequencer path turns the frame clock on
  only *after* the load, which is exactly what the O7 dependency is.
- ✅ The port with `--frame` from boot is **identical to frame-off through
  100 ms** (21 dispatches, 0 tasks either way), then wedges between 100 and
  205 ms: dispatches frozen at 40 from 205 ms through 400 ms while PIT0 keeps
  firing (41 → 80), **exactly 1 frame interrupt taken, 0 eDMA transfers
  started, 0 tasks created.** The mask is respected — no frame is delivered
  before 100 ms.
- 🟡 **Inferred, not measured:** the wedge is the frame ISR self-masking and
  waiting for a DSP exchange that never starts, because nothing drives the
  host port (O8) and the eDMA chain is only kicked from the sequencer path
  (O7). **Nobody has established that the port's frame model is right in the
  configuration that matters** — the unit gate covers the rules, M6c covers
  the fidelity, and only M6c decides.

✅ **No regression:** with the frame clock off (the default, as in route A)
nothing changed — the oracle diff is still 8 compared fields with zero
disagreements, `ctest` 6/6, `make check` green.

**To unblock:** land O7, then run M6c and compare against `RTOS_FORK.md` §8.

<details><summary>the original entry</summary>

### O6 — the eDMA and the frame clock *(Opus, but read §8.1 first)*

**Translates:** `class Edma` — the TCD register file, `SSRT`/`CINT`/`CDNE`,
`START`/`INTMAJOR`/`MAJORELINK`, and the **three completion rules** whose
wrong versions each produced a specific reproducible symptom (`RTOS_FORK.md`
§8.1): a host-port-window transfer completes *at the DSP's next 16-sample
boundary, as a whole chain*; an `SSRT` completes at once; a memory-to-memory
`START` completes at once. Plus the frame interrupt (INTC0 source 1, vector
`0x41`) as a **latched edge** at every 16-sample boundary, and the forced
tick through `INTFRCH`.

**Gate:** M6c's fidelity gate — `out/_testproj` (or the ONEAUX project with a
poked trig) lands **the same byte `0xd3` in `0x46104d15[0]` at frame 344**
after transport start, with 28 ticks in 400 frames. `RTOS_FORK.md` §8.
Requires the project load (O7) — so O6 and O7 may be one session.

</details>

### O7 — the card and the project load *(Opus, large)*

**Translates:** `tools/emu_card.py` (FAT16 + the ATA task-file model at
`0x90000000`, completing through vector `0xb6`), `Rtos.request_card_mount`,
`load_project_live`, `select_bank_live`, `seq_select_live`, `stage_project`.

**Gate:** the mount reads real ATA IDENTIFY/READ; the load reaches **6,189
ATA commands / ~30,467 sectors** and writes `PART_PTR = 0x4017d520` from
`0x40087d44` (`RTOS_FORK.md` §5 M6b). ⚠️ The load ends on bank A in route A
and on the saved bank on hardware (§7): the port must reproduce **route A**
first (the oracle), and the discrepancy stays documented as route A's.

### O8 — the DSP cores and the host port *(Fable — judgment)*

Join `dsp56kEmu` (both cores, the shared-window patch) to the machine
through the host-port protocol decoded on 7 Sep 2026 (`COLDFIRE_PORT.md`
"What is NOT here yet"). Gate: `tools/verify_twocore.py`'s layouts render
identically when driven by the firmware instead of by `dsp_host`'s
hand-rolled calls. Not to be started unattended.

### O9 — audio out *(Fable)*

The ESAI path, untraced. Not to be started unattended.

## Running it overnight

One session per milestone, in a terminal left open:

```
/loop Take the next milestone in docs/COLDFIRE_WORKORDER.md that is not done and not BLOCKED. Work on a branch named for it. Follow the standing rules. Open a PR when its gate passes, or a draft PR titled BLOCKED with the measurement. Then stop.
```

Use **Opus** for O6 and O7. Switch to Fable for O8 and for any BLOCKED PR.
Nothing here needs a flash, the card, or the user.
