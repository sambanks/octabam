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
| O5 | the rest of the memory; the serial stream | `ctest` rtos + the oracle diff | ✅ 8 compared fields; route A's 4831 serial bytes matched byte for byte (❌ its account of *why* route A has the extra memory was wrong — corrected in O7) |
| O6 | the eDMA and the frame clock; the sequencer | the M6c fidelity gate (`scripts/o6_gate.sh`) | ✅ 5 compared fields: 400 frames, 28 ticks, the trig at frame 344 track 0 bytes `0x08`/`0x18`, and the bank/pattern four -- byte-identical to route A |
| O7 | the card, the mount, the project load | route A's ATA command log EQUALS the port's | ✅ all 6,189 commands identical line for line, 30,467 sectors read, 297 written (was "a prefix"; O7b closed the gap) |
| O7b | why the port loaded twice | name the task and PC, and make the oracle reproduce it | ✅ `sys`'s media case reloads a NAMED project; the split is `strlen(name)` = 0 vs 3, a harness ordering race. Route A reproduces the port's 12,373 with `--names-early` |

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

### ~~O6 — the eDMA and the frame clock~~ ✅ DONE (8 Sep 2026)

See `COLDFIRE_PORT.md`. The gate is `scripts/o6_gate.sh` (stage one card image
with route A's own staging, run both, diff strictly), and it passes: 400
frames, **28 ticks**, the trig at **frame 344 on track 0**, bytes `0x08` then
`0x18`, bank/pattern identical.

❌ **This entry's own gate value was stale, and so was `RTOS_FORK.md` §8.4's.**
The byte is `0x08`/`0x18`, not `0xd3`, and there are FIVE transport-start
writes (tracks 0, 1, 2, 4, 7), not six. Route A and the cold tool agree on
today's numbers; 🟡 the EMAC fix of 7 Sep is the likely cause and is inferred,
not measured.

Four things later milestones should know:

1. **The DSP host port needs route A's two stand-in replies** (`0x20000004`
   reads `0x0000`, `0x2000001c` toggles). Without them the frame handler
   spins forever on the DSP's handshake — 352 M instructions, one frame
   taken, no eDMA, and it reads as a broken frame model.
2. **A defect in the port's own memory model can present as a crash with no
   output at all.** `Region::contains` overflowed at `0xffffffff`; the fix
   came with a bounds guard that stops the MACHINE, an auto-map ceiling, and
   line-buffered stdout. Read `run ended:` — and now, if it says nothing at
   all, suspect the buffering before the firmware.
3. **`SATS` and `movel #imm,%macsr` are on the M6c path and nowhere else**, so
   O1..O5 and the whole project load ran without ever meeting them.
4. **The EMAC gate that passed since O2 covered one corner of the unit.** Five
   fields were wrong — the accumulator number (inverted in the load form), An
   sources, the operand-half bits, the parallel load's addressing modes, and
   the accumulator's **48-bit `>>24` alignment**, which is the one that
   survived everything else and was worth exactly one LSB per subtract. If a
   port result is off by one, suspect where the truncation happens.

<details><summary>the entry it replaces</summary>

### O6 — the eDMA and the frame clock — UNBLOCKED, NEXT (the original)

**The code is written and unit-gated; its FIDELITY gate can now run.** Do
not re-do the model. What O6 still needs is the rest of the live-call
surface, translated from `emu_rtos.py`: `start_transport_live` (line 1312),
`poke_trig` (1379), `install_trig_log` (1441), and `select_bank_live`
(1210) — `callAsMain`/`postMessage`/`loadProjectLive` already exist and are
the pattern. Then: load `OCTABAM/ONEAUX` (or `out/_testproj`), turn the
frame clock on the way route A's sequencer path does (AFTER the load, not
from boot — `--frame` from boot wedges, see below), poke a trig, run 400
frames, and compare byte `0xd3` at `0x46104d15[0]` at frame 344 with 28
ticks. The oracle is `tools/emu_frames.py --project out/_testproj --frames
400 --start --internal-clock --poke-trig 2` (RTOS_FORK.md §8). ⚠️ The
first thing to read on any early stop is the load report's `load run
ended:` line — O7's "stall" was an ILLEGAL that looked like one.

</details>

### ~~O7b — why the port loads twice~~ ✅ DONE (8 Sep 2026)

**It was the harness, not the firmware.** `sys`'s media case (`0x4006203a`)
answers a mount with "if a project is NAMED, load it" — `0x4002574c` is
`if(strlen(0x100f8378)) post LOAD PROJECT`, and `0x40013db0` is `strlen`. Both
emulators run that path identically and split on one value: the name is
written by the time this port's case runs (`strlen` = 3) and not by the time
route A's does (`strlen` = 0), because route A's mount tail runs ~200 samples
longer. ✅ Told to write the name first (`--names-early`), **route A
reproduces the port's 12,373 commands exactly**.

❌ The 🟡 hypothesis in the entry below — SYS's reset-time "select bank 0"
going to the card — is **retracted**. The select-bank case is not on this path.

The port now waits for that case's join point before naming the project, so
the order is a choice rather than a race, and its load is **byte-identical to
route A's, command for command** (6,189 / 30,467 / 297). `--names-early` takes
the other order deliberately: ⚠️ two loads, and arguably what HARDWARE does,
since the unit has a project named long before a card goes in. Nothing on
hardware has been measured either way — that is the open question this leaves.

Three things worth carrying:

1. **`--watch-pc` now exists on BOTH emulators** and answered this in two
   runs: registers plus the top of the stack at each hit, so a hit on a callee
   names its caller and its arguments.
2. **`--cmd-log` now exists on route A too**, in the port's own first-field
   format, so the two logs diff line for line.
3. ⚠️ **The silent-instrument trap, third instance.** `_watch_report()` was
   missing from route A's `--load-project` branch, so `--watch-pc` on a load
   run printed nothing whether the address fired twice or never — the exact
   question O7b asks. Fixed. Check the OTHER branches before trusting a
   silent watch.

<details><summary>the entry it replaces</summary>

### O7b — why the port loads twice — (the original)


Route A's load ends at 6,189 ATA commands at any budget; the port's runs to
12,373 with route A's log as an exact prefix. Find which task and PC issue
command 6,190 (`--ata-trace` carries the PC; raise or re-arm its 200,000-
access cap), find the same site in route A, and say why one runs it and the
other does not. 🟡 The hypothesis is SYS's reset-time "select bank 0"
(RTOS_FORK.md §7) going to the card in the port and not in route A. Not a
blocker for O6 (the load's first half is identical and the part pointer
agrees), but it decides which emulator is telling the truth about the load.

</details>

<details><summary>the BLOCKED entry it replaces</summary>

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

</details>

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
### ~~O7 — the card and the project load~~ ✅ DONE (8 Sep 2026)

**Most of it is built and gated; the mount does not complete.** Do not re-do
the card model — pick up at the missing wake-up.

Built: `card.{h,cpp}` (route A's `AtaCard`, gated in `test_periph`),
`Rtos::attachCard` (the INTRQ rules), `mapCardMemory`, `callAsMain`,
`postMessage`, `requestCardMount`, `setNames`, `loadProjectLive`, and
`--card/--mount/--set/--project` on the CLI. ⚠️ The FAT16 image builder is
deliberately NOT ported: route A builds the image in Python, the port reads
the same `.img`, so both look at identical media.

Two findings that are worth more than the code:

1. ✅ **`0xfc0a4039` bit 3 must read CLEAR.** Unmodelled it answers all-ones,
   the driver decides there is no card, and the mount issues **zero ATA
   commands with no error anywhere**. Route A keeps it in `EXTRA_OVERRIDES`.
2. ❌ **O5's "route A grows memory through an auto-mapping hook" is
   retracted.** `emu_card.attach` maps those four spans EXPLICITLY; the hook
   is only installed by the menu render helpers, which never run on the
   golden path. `mapCardMemory` now adds them, and the port's auto-mapped
   count falls from **20,348,051 to 4**. See `COLDFIRE_PORT.md`.

**THE MOUNT NOW SUCCEEDS** (8 Sep 2026, second session). Four defects, all
measured:

1. ✅ **INTRQ is not instantaneous, and the firmware depends on that.** The
   port asserted it on the same instruction as the command write, so the ISR
   ran, streamed, and SIGNALLED the event before the driver reached the WAIT —
   which then blocked forever on a signal that had already happened. Route A
   survives only by accident of granularity (burst-boundary delivery). A real
   CF card takes tens of microseconds, so `m_ataLatency` (1 sample) is the
   physical behaviour. **The port's finer granularity EXPOSED a race route A's
   coarse bursts hide** — the usual lesson inverted.
2. ✅ **`mvzw %a0,%d0`** at `0x40017c10`: the V4e effective-address reader had
   no `An` direct. Same family as O4's `ff1`.
3. The park must test **the PC alone**, as route A does — `!anyPending()` as
   well never comes true once the card is live.
4. `callAsMain`'s budget must survive preemption (the step count is dominated
   by the other tasks running underneath the borrowed call).

**Where it stops now:** card ready = **1**, `LOAD PROJECT` posted, **1,407**
ATA commands / **10,695** sectors read / **297 written — the written count
matches route A exactly**, and one ATA interrupt arrives per sector. ⛔ The
load then STOPS rather than running slowly: 30,000 ms of emulated time gives
the same 1,407 commands as 6,000. It ends with the **engine task cycling at
`0x400165dc`** and the in-flight word (`0x46c8c58a`) clear. Route A's targets
are 6,189 / 30,467 / 297. ~~**That stall is the next thing to chase.**~~

**✅ THE STALL WAS A FAULT (8 Sep 2026, third session).** The V4e layer
refused `mov3ql #-1,%a0@+` at `0x4009d8d0` ("only Dn is reached by this
firmware" — ❌ retracted), the firmware took a real line-A exception, its
panic handler printed `EXCEPTION VEC:0A ADDR:4009D8D0` over the panel UART
and then polled TXEMP forever, which the UART model never set. Fix =
MOV3Q to every alterable destination (`writeEaLong`); TXEMP is reported
too, which is what made the fault legible. **Now: 12,373 commands / 60,677
sectors / 562 written, and route A's whole 6,189-command log is an exact
prefix.** ✅ **CLOSED by O7b:** the extra
6,184 commands were a SECOND project load, triggered by `sys`'s media case
because the harness had already written the project name; the port now waits
for that case and issues route A's 6,189 line for line. The 🟡 "second bank
parse" reading was wrong. `COLDFIRE_PORT.md` has the instrument-by-instrument account and
the attribution. Instruments added: `--cmd-log FILE`, a true PC ring, and
the load report's `load run ended: TIME|FAULT|ILLEGAL` line — **read that
line before calling anything a stall.**

The instruments that found all of this are in the tree and off by default:
`--ata-trace`, `--periph-trace`, `--pc-ring N`, `--peek`, and the
acknowledged-vector log (which vector went to which handler, always on).

**Route A's targets, re-measured today on `OCTABAM/ONEAUX`:** 6,189 commands,
30,467 sectors read, 297 written, `saved_bank=1`, `final_bank=0`. ⚠️
`PART_PTR` reads `0x400e21e0` **before any load** (it is the bank blob's
base), so it is NOT on its own evidence of a load; the work order's
`0x4017d520` below is from a different project.

**No regression:** oracle diff 8 compared fields, zero disagreements; `ctest`
6/6; `make check` green.

<details><summary>the original entry</summary>

### O7 — the card and the project load *(Opus, large)*

**Translates:** `tools/emu_card.py` (FAT16 + the ATA task-file model at
`0x90000000`, completing through vector `0xb6`), `Rtos.request_card_mount`,
`load_project_live`, `select_bank_live`, `seq_select_live`, `stage_project`.

**Gate:** the mount reads real ATA IDENTIFY/READ; the load reaches **6,189
ATA commands / ~30,467 sectors** and writes `PART_PTR = 0x4017d520` from
`0x40087d44` (`RTOS_FORK.md` §5 M6b). ⚠️ The load ends on bank A in route A
and on the saved bank on hardware (§7): the port must reproduce **route A**
first (the oracle), and the discrepancy stays documented as route A's.

</details>

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

**Model routing (8 Sep 2026, after the Fable credit ran out mid-session):**
- **Opus** for O6's live-call translation, O7b's measurement, and any
  milestone whose oracle exists — the work is translate-and-diff, and Opus
  found and fixed O7's fault end to end (cmd-log diff → PC ring → TXEMP →
  panic text → MOV3Q) without judgment calls.
- **Fable** only for a BLOCKED PR where the oracle itself is in question
  (route A cannot do it, or the two disagree and hardware must decide), for
  O8's DSP join, and for the roundup/merge pass at the end of a run. Do not
  spend it on translation.
- Whatever the model: **no claim without the instrument line that produced
  it**, and "stall" is not a finding until `load run ended:` says TIME.

Nothing here needs a flash, the card, or the user.
