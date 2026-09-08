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
9. **A fixture edit goes into EVERY part of EVERY bank, and two cards must
   differ on the host port before a DSP-side "identical" counts.** The load
   applies bank 1 part 1; the transport start applies the saved bank's
   pattern part (O9d). `ot_project.py set-fx` / `stamp-slot` write all
   eight parts; `--block-dump` + `tools/scratch/blockdump.py diff` is the
   check. Three O9c retractions came from skipping both.

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
| O8 (1-4) | the DSP cores behind the host port | ctest `dsp` (the firmware's upload lands the image's bytes) + M6a and O6 with `--dsp` | ✅ 50/50 + 58/58 bootstrap words, 26,221 + 25,408 payload words at upload time; M6a 8 compared fields; O6 5 compared fields (400 frames, 28 ticks, trig at 344) with the cores live. Step 5 open |
| O8a | the ESAI rate | the falsifier: bank B gets taken | ✅ the port's ESAI ran 8× slow (a per-SLOT clock fed a per-sample count); the rate is the firmware's own 4160 instructions/sample; a ninth vendored DMA defect found on the way. Bank B 850 of 2,400 blocks (was 0) |
| O8b | the host-port burst time | `ESAI frames per host frame` reads 16, O6 still 5/5 | ✅ FlexBus 66 MHz × 4 clocks/word from `PCR` and `CSCR2` in the image: 16 on 382 of 399 (was 0 of 399), O6 5/5, M6a 8/8 |
| O9b | the trig → voice path | a THRU track trigged with `--audio-in tones` puts audio on TX0; O6 5/5 | ✅ four findings, none the trig path: the main gain table is filled only by sys command 4 (`--main-level`); MACSR S/U is bit 6 and means 16-bit rounding on the read-out in fractional mode (CFPRM); the frame interrupt is the DSP's bank word (the firmware halts on a mistimed read); the vendored AGU's modulo pre-decrement underflowed out of the buffer (eleventh vendored defect). TX0 slots 1-4 carry the mix on 6,213 of 6,399 frames; 400 frames, 28 ticks, O6 5/5 |
| O9 (half) | the ESAI path | audio in: the read-back carries what the ESAI receives; the clock walk: 16 on 399/399 | ✅ tones on RX0 come back in eDMA ch 7's 128-word blocks (50,298 non-zero words / 400 frames, 9 without); ✅ O8b's 0.27 % walk was `rep` iterations counted once per call — 399/399 and 1599/1599 now. ❌ Audio OUT silent: the ring never gets a non-zero write; the trig never becomes a voice, and route A agrees — see O9b below |

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

### O8 — the DSP cores and the host port — 🟡 BUILT THROUGH STEP 4 (8 Sep 2026, branch `coldfire-o8-dsp`)

**The two real cores sit behind the host port (`--dsp`), the firmware boots
them itself, a ctest verifies the upload byte for byte, the M6a and O6 gates
both pass with the cores live (`DSP=1 scripts/o6_gate.sh`), and the eDMA moves
the frame blocks (870,400 words in, 307,200 back over 400 frames, none late).
✅ **The outbound frames carry content and track the sequencer** — 40,853
non-zero words, rising across the trig at frame 344 — and they reach DSP
memory. ❌ **The inbound direction is zeros in every frame band**: the DSP
computes silence, and why is open on the audio-in path (O9's ground).** Step 5 — `verify_twocore`'s layouts rendering identically
when driven by the firmware — is not started; `COLDFIRE_PORT.md` says what it
needs. Do not re-do any of the join.

What later milestones must know:

1. ❌ **The host-port readings in ARCHITECTURE.md §6 were wrong** and are
   corrected there: the window is the HI08 host-side register file at a 4-byte
   stride on a 16-bit port, `0x81` is ICR INIT|RREQ, `0x8c` a host command,
   the ready bit is TXDE|TRDY. And one DSP word rides each 16-bit bus cycle
   (the tape's block counts are half their byte counts) — a longword eDMA
   access is two words.
2. **The shared window is ONE memory for P, X and Y of both cores**, and the
   firmware needs it (core B's entry is written by core A's upload). `dsp_host`
   keeps its two-way window and is a different machine on that point.
3. **Nine things the vendored DSP emulator does that the firmware cannot live
   with** are in `tools/dsp56300.patch` (DO loops nested in one call, JIT-only
   interrupt dispatch, a masked interrupt starving the peripherals, the ESAI
   blocking on an empty ring, a PC past P memory as a garbage pointer, a fast
   interrupt never reaching its vector's PC, the ring-buffer DMA modes and a
   12-bit DCOL, the host DMA's disabled initial trigger and 200-instruction
   receive throttle, and — found 8 Sep by the ESAI-rate falsifier — a
   dual-counter DMA that never reloaded its counters at the block end, so
   the ESAI-in ring walked its destination through all of memory and into
   the ESAI's own TCR). Every one was found by an instrument — stack sample, `lldb
   -k`, `--dsp-trace` — after presenting as a silent hang or a bare crash.
   Regenerate the patch with `git -C vendor/dsp56300 diff`; `make check` only
   sees it after `cmake --build vendor/dsp56300/build`.
4. **With the cores attached, a burst into the host port completes when the
   DSP has drained it**, not at once (route A's rule stands without them): the
   completion interrupt is what lets the frame handler issue the next block.
5. 🟡 The inter-core mailbox at Y:$FFFFD3/D4 and $FFFFD6/D7 is inferred from
   the two payloads' wait loops and modelled symmetrically.
6. **The DSP lands a block at its own address, not the one the host names**
   (dest `0x6080` → X:0x4080, consistently 0x2000 apart; 🟡 a bank select).
   A `--dsp-peek` of the host's address reads zeros and looks like an empty
   frame — count non-zero words at the move (`--block-log`) instead, and take
   any DSP-side note at the drain's completion, never at the eDMA kick, where
   it lags a whole block.
7. The idle fast-forward is on by default and validated by A/B (`--dsp-no-idle`);
   a sequencer run with the cores costs ~25 minutes either way.
8. The build is native now (`/opt/homebrew/bin/cmake`); the x86 cmake had been
   building `out/emu` under Rosetta.

<details><summary>the scoping entry it replaces</summary>

### O8 — the DSP cores and the host port — ⛔ SCOPED, NOT BUILT (8 Sep 2026, the original)

**The join is fully decoded and no DSP is wired yet.** `COLDFIRE_PORT.md` has
the account; the headline is that ✅ **the firmware boots the DSPs ITSELF,
during the ColdFire boot, and the bytes are captured**: `0x40001e50` (called
once from the boot at `0x4000050c`, instruction 4,270,944) uploads a 50-word
bootstrap to `P:0x31000` and a 58-word one to `P:0x32000` through
`0x20000014/18/1c`, and those 50 words disassemble as an **HDI08 bootstrap
loader** that echoes each host word back — the far side of the handshake O6 had
to fake. So the join needs no `.mem` dump: wire the window to a real HDI08 and
the firmware programs the cores.

**Do these in order** (details and the byte lanes in `COLDFIRE_PORT.md`):

1. Link `dsp56kEmu` into `ot_emu`, two cores, shared-window patch (mechanical —
   `tools/dsp_host` already does it).
2. Wire the window: `0x14/18/1c` → `HDI08::writeRX` (bits 23:16, 15:8, 7:0 —
   low byte of each halfword only), `0x20000008` → HSR, `0x20000004` → the
   busy/status byte, `0x20000000` `0x81`/`0x8c` = start/swap, chip select at
   `0xFC0A400C`.
3. **First real gate, and it is self-checking:** let the firmware's own upload
   run and compare the DSP's `P:0x31000` against the captured words
   (`--hostport-log`).
4. Make the eDMA MOVE data — route A's model deliberately moves none — so the
   frame exchange carries the 336/64/32-word records `docs/DSP.md` names.
5. Only then the milestone's own gate: `verify_twocore`'s layouts rendering
   identically when driven by the firmware.

⚠️ **Step 5 is a bigger jump than it reads.** `verify_twocore` drives the effect
ABI directly (`r0`/`r6`/`r7`/`n7` + `proc`); the firmware drives whole FRAMES
through the packer at `0x4000d3fc`. Nothing has yet checked that the firmware's
per-track records can carry the knob values the harness passes by hand. That is
the judgment this milestone was reserved for.

⚠️ **And two instruments were lying about all of this before they were fixed**
(both returned a confident zero for something that runs): the PC watch could not
see the boot, and `--periph`'s log is capped at 4096 accesses — full long before
the DSP init. Fixed, and `--hostport-log` added. **A zero from an instrument is
not a measurement until you know the instrument can see the thing.**

</details>

### ~~⚠️ Read this before step 5 or O9: the ESAI rate is an unmeasured knob~~ ✅ SETTLED (8 Sep 2026, branch `coldfire-esai-rate`)

Two findings, both in `COLDFIRE_PORT.md` O8 "the ESAI rate":

1. ❌ **The port's ESAI ran EIGHT TIMES SLOW.** The vendored clock's "cycles
   per sample" is per SLOT (`Esai::execTX` advances one slot per call), and
   `DspPair` passed the per-sample count straight through against the
   payload's eight slots. That, not any rate knob, is why the 0x80f0 bank
   never came. Fixed: one slot per `ips / 8`; the report now prints ESAI
   frames per host frame (0x8c to 0x8c), which the ring needs to be 16.
2. 🟡 **The rate is the firmware's own arithmetic, 4160 instructions per
   sample, not 4535.** The payload routes EXTAL into the ESAI chains (Port H
   `0xaa0000`) at ÷512, never writes PCTL, so the core runs the reset PLL
   (EXTAL × 8.125): 512 × 8.125 = 4160 whatever the crystal (22.5792 MHz
   and 183.456 MHz if fs = 44.1 kHz and the manual's block diagram is
   right). `CHIP.md` and `PLAN.md` carry it beside the datasheet's 4535.
   Falsifiers: a PCTL write, PINIT = 0, a crystal that is not 22.5792 MHz.

**Gate (8 Sep):** ✅ **Passed, and the falsifier turned up the next thing.** Same O6 run,
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

### ~~O8b — the host-port burst time~~ ✅ DONE (8 Sep 2026, branch `coldfire-esai-rate`)

`COLDFIRE_PORT.md` O8b has the account. The port's host frame was 80–96
samples because route A's completion rule rounded each of six serial bursts up
to the next 16-sample boundary. A burst now completes at **kick + words ×
2.673e-3 samples**, still behind the drain gate, and the frame is 16 samples
again: **ESAI frames per host frame 16 on 382 of 399** (was 0 of 399), O6 with
the cores 5/5, M6a 8/8, `ctest` 7/7, no-cores O6 unchanged.

Three things later milestones must know:

1. **The burst time is the chip's, derived from two register words in the
   image, not a knob**: `CSCR2 = 0x180` (WS = 0, 16-bit port) written by the
   DSP loader over the boot's `0x1180` (WS = 4), and `PCR = 0x16777731` giving
   **FB_CLK = 66 MHz**; a no-wait-state transfer is four FB_CLK cycles (RM
   Figs 20-16/20-18). One DSP word = 60.6 ns. The corroboration is that the
   exchange then fills **49%** of the frame period and would fill **98%** at
   the boot's wait states, which is why the loader reprograms it.
2. **`CHIP.md` §1 now carries the whole ColdFire clock tree** (crystal 24 MHz,
   VCO 528, CPU 264, bus 132, FlexBus 66), measured from the image. The step
   that settles it is the UART baud setup shifting the stored clock right one
   before dividing — read the stored 264 MHz as the VCO instead and every
   figure halves.
3. ⚠️ **A consequence recorded but NOT acted on: route A's PIT clock is the
   CPU clock where the hardware uses the bus clock, so the modelled RTOS tick
   is 5 ms where the unit's is ~10 ms.** Both emulators share the knob and the
   gates compare order, so no diff can see it; every wall-clock figure in
   these records (`gate at 204.95 ms`, `28 ticks in 400 frames`) is a factor
   of two out if it holds. `CHIP.md` §1 has the evidence and the falsifier.
   **It is a claim about what the firmware means and it moves every recorded
   timing number — it wants a deliberate pass of its own, not a quiet edit.**

🟡 Residual: 17 host frames of 399 take 17 ESAI frames rather than 16, a 0.27%
drift in the DSP's clock (never 15, so drift not jitter). ✅ Ruled out: the DSP idle fast-forward (`--dsp-no-idle` is
identical), the frame clock (the interval is exactly 16.000 samples on all
399) and the ESAI rate (a transmit frame is 4160.3 instructions, one sample).
It is the PHASE between the two that walks, one sample per 23.5 frames, always
one way. 🟡 Candidate: the read-back pull runs a core outside the sample
budget (`runCoreUntil`). **Hand it to O9** — an audio path resamples by
exactly this error.

### ~~O9 — audio out~~ 🟡 HALF DONE (8 Sep 2026, branch `coldfire-o9`)

`COLDFIRE_PORT.md` O9 has the account. Instruments: `--audio-out`,
`--audio-in FILE|tones`, `--dsp-map`, `--dsp-writes` (a tenth vendored patch:
a write hook), `stage_card.py --audio`, and the `audio (O9)` / ring-write
report lines. Three things later milestones must know:

1. **The DSP's budget is spent in the DSP's own instruction counter**, not
   in interpreter calls: a `rep` advances the counter once per iteration and
   the ESAI clock reads that counter. That was O8b's residual (0.27 % ≈ 208
   surplus instructions per 66,560-instruction frame).
2. **The frame's audio topology is measured** (the table in `COLDFIRE_PORT.md`
   O9): eDMA ch 7 back = the eight input slots × 16 samples (proven by
   content); ch 1 back = 256 words per core, 🟡 the core's track mix; the
   512-word block the ColdFire sends core 0 each frame is the two read-backs
   forwarded. ❌ `DSP.md`'s "0x80003190 = read-back, 256 words" is half the
   story and is corrected there.
3. **Nothing starts a track under either emulator.** A poked trig changes
   one word of a voice record and nothing follows; a staged FLEX sample is
   read in full from the card and never rendered; a file trig in A01 does not
   fire. Route A on the same card does the same. Do not look for this in the
   DSP: the ring's write count is the instrument, and it reads zero because
   its input is zero.

### ~~O9b — the trig → voice path~~ ✅ DONE (8 Sep 2026, branch `coldfire-o9b`)

`COLDFIRE_PORT.md` O9b has the account. Four things later milestones must know:

1. **Post sys command 4 (SET MAIN LEVEL) after every emulated load** —
   `--main-level 64` on the port, `set_main_level_live` on route A. Without it
   the main gain table `0x80003c60` is zero and every voice renders silent.
2. **MACSR S/U = 0x40, and in fractional mode it selects 16-bit rounding on
   the accumulator read-out** (CFPRM ch. 6). `v4e.cpp accRead` is the manual's
   pseudocode now. Any EMAC claim made before 8 Sep at MACSR `0x60`/`0x70`
   sites is suspect on the port side; route A (QEMU) had it right.
3. **With the cores, the frame interrupt is the DSP's bank write** (payload A
   P:0x73), not the 16-sample timer; the firmware reads the bank id with no
   ready check and halts on a data word. `--frame-timer` keeps the old model.
4. **The vendored AGU could leave a modulo buffer on a pre-decrement from the
   base** (`agu.h`, fixed, patch regenerated). `make check`'s bit-identity
   gates say whether any shipped effect was rendered on it.

### O9d — the comparison fixture measured the wrong track, then the comparison itself ✅ DONE, O9c GATE PASSED (8 Sep 2026, branch `coldfire-o9d`)

`COLDFIRE_PORT.md` O9d. O9c's three closing claims (a THRU track's TX0 is
a pre-FX2 monitor; the page-2 select never crosses; the tap must be the
recorder) are ❌ RETRACTED: every O9c FX2 fixture edited bank 1 part 1
while the transport start applies the SAVED bank's pattern part, so T2's
FX2 was SEND in every run — and T2 has no input in the port anyway (its
FX1 FILTER is closed, as `rig_render` said). With the effect on T1 in every
part, page 1 AND page 2 cross and TX0 changes. New instrument
`--block-dump` (+ `tools/scratch/blockdump.py`); new tool
`ot_project.py set-fx`. **The O9c gate PASSES on T1 (stock image, EQUALIZER):** the port's T1
read-back against `rig_render` on the same chain input, flat page
−125.6 dB residual at a −11.906 dB scale, boosted page −95.7 dB with the
stem pre-scaled by that k and no fit. The parameter words on the DSP are
dsp_host's word for word (page 2 included); the pre-FX track gain k is the
one thing the harness does not model (`tools/scratch/o9d_compare.py`).

**Rule 9, from this:** a fixture for the port goes into EVERY part of EVERY
bank (`set-fx`, `stamp-slot`), and a DSP-side "identical" between two cards
is void until `--block-dump` shows the cards differed on the host port.

### O9c — the audio comparison (O8's step 5) *(Opus)* — 🟡 MOSTLY DONE (8 Sep 2026, branch `coldfire-o9c`) — ⚠️ its closing claims are retracted in O9d

`COLDFIRE_PORT.md` O9c has the account. Done and measured: the input map
(RX0 0/1 = A/B, 2/3 = C/D, moved by the project's `DIR_AB`/`DIR_CD`; 4–7 not
received, the firmware's own `RSMA = 0x0f`); the output map (the mix on ring
words (2,3) and (4,5), read ring-aligned off DSR2 because the ESAI slot
counter rotates against DMA2's index per run — an instrument artefact caught
and fixed); the THRU baseline (flat −11.1 dB, 155-sample latency, full-scale
limited); and **the parameter path end to end** — a part's FX2 page byte
reaches the effect's coefficient block on the DSP (FILTER BASE 40 → X:0x2c0
word 7). ⚠️ Two "never reaches the DSP" readings on the way, both retracted;
the corrected finding is that it does.

**The gate — a THRU track's FX rendering bit-identical to `dsp_host` — is
not passed**, but it is no longer a locate: it needs a non-transparent part
setting (a page-2 select; `stamp-slot` writes page 1 only today) and the
gain structure between the two paths reconciled (port: main → track →
−11.1 dB THRU; `dsp_host`: r6 poke, no mixer). Draft PR carries the
measurements; the gate work is the finish.


**Gate:** the port, driven by the firmware, renders `verify_twocore`'s
layouts and the WAV matches `dsp_host`'s render of the same layout to the
bit for the THRU path (the FX chain is the same code). **Needs first:** the
slot map (which RX0 slot is input A/B/C/D, which TX0 slot is main/cue L/R —
eight single-tone runs with `--audio-in FILE.wav`, or a spectral pass on
`out/o9/o9b_frames.wav`), and a project where the track's FX2 is the effect
under test. The FLEX sample path (a staged `KICK.WAV` is read from the card,
the 512-word block stays zero) is a separate locate with `--coverage`.

### O9b — the trig → voice path *(the original entry)*

**Gate:** with `--audio-in tones` and a THRU track trigged, TX0 carries the
tones (`--audio-out` WAV non-zero on some slot; `non-zero writes into the
ESAI-out ring` > 0). **Where to start:** route A, not the port — a note trig
that the sequencer fires (`FW_LIVE_NIBBLE` byte `0x08`/`0x18` at frame 344)
must reach a voice: `RTOS_FORK.md` §10.14's control reached `0x46104d26`
through the recorder masks and the arm caller `0x40005ff0`; the note trig's
equivalent is unlocated. Instruments that exist: `--watch-calls`,
`--watch-mem`, the block log's per-block non-zero counts (a rendering voice
shows as ≥ 16 non-zero words per frame in the 512-word block), and the port's
write map for the DSP side once the ColdFire sends anything. **Falsifier for
"the emulators cannot start a voice":** the same project on the unit plays
(it does — it is Sam's rig), so this is a fidelity gap, not firmware
behaviour; the question is which peripheral or flag the voice start waits on.

### O10 — FLEX playback + the recorder loop under the port ✅ DONE (8 Sep 2026, branch `coldfire-o10`) — the port does NOT reproduce the click

`COLDFIRE_PORT.md` O10. ❌ "a FLEX voice never renders in either emulator"
is retracted for the port: the voice's audio is in the 84-word track
record (a list of `(count,0,0x40000,tag)` segments — parse it, do not
window it), and a FLEX slot plays sample-exact (`kick.wav<<8`, −100 dB,
TSMODE 0). The capture pairs are measured (RX0 slot 2 → the ColdFire's A/B
at +0x80). Bryan's fixtures (route A's `make_seam_fixtures.py`, staged as
cards, `--audio-in tones`): 128/RLEN 4 for 32 passes, 128/MAX, 120/RLEN 4
and the `--self` shape are ALL one continuous sine to −104 dB at the voice
tap — the play trigs and the arms share the fractional step grid, so the
recording-level −1 seam route A found never reaches the played stream.
Analysers: `tools/scratch/o10_recloop.py`, `o10_continuity.py`,
`o10_seam.py`, `o10_phase.py`. **Open:** where the hardware click lives is
outside what the port models (its trig/arm timing is idealised; the RTOS
tick is 2× off in both emulators; the DSP/ESAI phase is the port's). The
one falsifier the port can still run is a fixture whose play grid differs
from the arm grid (`r4_128_off`, play trigs at 4/8/12/16) — result in the
port doc.

### ~~O10 — the recorder with real input~~ *(the original entry)*

The inputs reach the ColdFire's capture buffers now. Bryan's click
(`octabam-seam-patch-falsified`) wants content injected at the source and the
pool blocks read across the arm: the RECTRIG fixture with `--audio-in tones`
(or a WAV) and `--block-log`, reading the packed pool blocks
(`RTOS_FORK.md` §10.16's write path `0x400068e4`). No DSP voice needed to
RECORD; playing it back does.

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
