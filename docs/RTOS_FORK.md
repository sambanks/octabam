# The RTOS fork (emulator route A) — scope

Scoped 6 Sep 2026. Status: **not started**; feasibility **measured**, kernel
**decoded**, plan below. `EMU.md` has the history of route B (detours) that
this replaces for the paths that need real task interleaving.

Confidence markers as in `CHIP.md`: ✅ measured in the emulator or read
byte-exact from the image, 🟡 inferred, ❓ open (with how to close it).

## 1. What it is, and what it buys

Every emulator milestone so far (`EMU.md` M1–M5) runs firmware code **cold**:
a function is called against the warm machine, or an interrupt handler is
pushed a fake frame and run to its `rte`. Nothing ever runs the firmware's
own scheduler, so nothing ever runs *two* pieces of firmware in the order the
firmware would run them. Three things are out of reach that way:

- **Task interleaving.** The engine task, the storage task, the UI task and
  the voice task all block on kernel queues and wake each other. Route B
  stepped one task at a time by hand (`engine_run_once`) and satisfied every
  wait with a hook. Anything that depends on *which* task runs *when* — a
  key press reaching the engine, the engine posting to the DSP task, the
  recorder-arm action being staged and then promoted by the tick (M5's
  "path B", `EMU.md` M5) — cannot be driven cold without re-implementing the
  kernel's ordering by hand, one case at a time.
- **Pre-emption at the frame boundary.** M5's one un-modelled thing: the
  tick is a forced interrupt the frame handler raises, and on hardware it may
  pre-empt the frame handler mid-way. Only a real interrupt model shows that.
- **Real waits.** Route B's card model completes ATA commands from a hook on
  the event wait because the ATA interrupt is never taken. Under route A the
  interrupt fires, the handler streams the sector, the kernel wakes the
  storage task. Same for the two PIT timers.

What it does **not** buy: audio. The DSP side stays in `dsp_host`; the frame
handler's host-port handshake stays faked as in M5.

## 2. The kernel, decoded ✅

The whole scheduler is about 0x200 bytes at `0x40000550`–`0x40000760`. Read
6 Sep 2026 with `scripts/disasm.sh emac`; every address below is byte-exact.

**TCB layout** (`0x400005fc` builds it, `0x40000550`/`0x4000056e` save and
restore it):

| offset | field |
|---|---|
| `+0x00` / `+0x04` | next / prev in the priority's circular list |
| `+0x08` | pointer to the priority level's list head, `0x800068dc + 4·prio` |
| `+0x0c`–`+0x4b` | saved `d0–d7, a0–a7` (`moveml`; **`a7` at `+0x48`**) |
| `+0x4c` | ready flag (1 = on a ready list) |
| `+0x50` | cleared at create; unread here |

`ARCHITECTURE.md` §4's "SP at 0x38" is wrong: the `moveml d0-sp` block starts
at `+0x0c`, so `a7` is at `+0x48` (create writes it there, `0x4000062c`).

**Globals:** current TCB `0x800068fc`; top-priority pointer `0x800068d8`
(points *into* the `0x800068dc[8]` array of list heads; higher index = higher
priority; the scheduler takes the head of the list it points at, and the
block path scans downward for the next non-empty level, `0x40000852`);
`0x80006900` is a scratch slot for `a0` on entry.

**Scheduler entry `0x40000550`** — one handler for **two vectors**: `trap #0`
(vector 32) and the **PIT0 timer interrupt (vector 171)**; the boot writes
`0x40000550` into both slots at `0x400005d8`/`0x400005dc`. It masks
interrupts, saves all registers into the current TCB, takes the head of the
top ready list, clears the reschedule bit (`0xfc04c010 &= ~0x800`), **re-arms
PIT0 with `0xb3f`**, sets the cache control, restores the new task's
registers with `moveml a0@(12),d0-sp` and `rte`s into it. A freshly created
task's "saved context" is an exception frame on its own stack —
`[0x407c][SR 0x2000][entry PC]` with `0x400006e4` (task exit) as the return
address under it (`0x4000061c`–`0x40000626`).

**Primitives** (all `jsr` targets, so every caller is findable with the
literal scan): create `0x400005fc(tcb, entry, prio, stack, size)`; make-ready
`0x4000063c(tcb)`; unlink `0x4000068c(tcb)`; event wait `0x40000818(event)`
(count > 0: consume and return; else park the current TCB in the event,
unlink it, `trap #0`); queue post `0x40000c3c(queue, msg)` (ring at
`queue+0x14`, mask `+0x10`, head `+0x18`; wakes the waiter at `+0x0c` and
raises its level); event signal `0x40000888`; semaphore take/give
`0x40000a94`/`0x400009f4` (used by the delay helper); queue init
`0x40000bd4`; task exit `0x400006e4`. Vector install `0x40000d50(vec, fn)`
(the frame handler goes on vector `0x41` at `0x4001fbf8`); the default
handler `0x40000d74` is a trampoline that calls one settable pointer
`[0x460ba970]` (set by `0x40000da4`) and `rte`s.

**Tasks — eight** ✅ (seven `create` sites plus the boot's main task; entries
and priorities read from the pushed arguments):

| prio | TCB | entry | stack | what (🟡 by neighbourhood) |
|---|---|---|---|---|
| 6 | `0x46c7fb0c` | `0x40005540` | `0x46c7ea20` +0x1000 | voice / DSP mailbox task |
| 5 | `0x460bcc2c` | `0x4001ee30` | `0x460bc42c` +0x800 | storage (FAT/ATA) |
| 4 | `0x460d4f80` | `0x4005593c` | `0x460d4780` +0x800 | UI |
| 2 | `0x460fab80` | `0x40091d18` | `0x460fabd4` +0x2000 | ❓ |
| 2 | `0x460ffd44` | `0x400921c4` | `0x460fdd44` +0x2000 | ❓ |
| 1 | `0x460ddde4` | `0x4008445c` | `0x460d9de4` +0x4000 | **engine** (the 46-opcode dispatcher, `EXTERNAL.md` §6) |
| 1 | `0x46105508` | `0x40098a5c` | `0x4610555c` +0x2000 | ❓ |
| 0 | `0x46c7ae84` | `0x4001f834` | top `0x46c7becc` | **main** — runs the init list, then parks |

At the handoff only main is on a ready list (measured: level 0, one TCB);
the current TCB `0x46c7ae30` is the pre-multitasking context that the first
`trap #0` saves and never resumes. The other seven are created by main's
init list — the same list `card_init` runs by hand today.

**Interrupt controllers — two** ✅. INTC0 at `0xfc048000` takes vectors
`64 + source`: the DSP frame handler is source 1 (vector `0x41`, level 5,
`0x4001fc30`) and M5's forced tick is `INTFRCH` bit 0 (`0xfc048010`, source
32, vector `0x60`). INTC1 at `0xfc04c000` takes vectors `128 + source`: PIT0
is source 43 (ICR `0xfc04c06b` := level 1; vector 171 = `0x2ac/4`) and the
ATA interrupt is source 54 (vector `0xb6`). **VBR is `0x40000000`** — the
image's own first KB is the vector table (`[0x400b9668]`), which is why the
no-op `movec` never mattered. At the handoff exactly two slots are
non-default: 32 and 171, both `0x40000550`.

**The time-slice** ✅: PIT0 at `0xfc080000`, prescaler 2¹¹ (PCSR `0x0b36`
at init, `0x0b3f` on every switch), PMR `264,000,000 / 409,600 − 1 = 643`
→ **5.0 ms per tick = 220.5 samples = 13.8 audio frames**. PIT1
(`0xfc084000`, PCSR `0x0b3a`, PMR 2014) is the storage layer's delay timer
(`0x40020c7c`, waits ≥ 15,000 units on a semaphore).

## 3. Feasibility — measured 6 Sep 2026 ✅

A synthetic spike (`rte_spike4.py`, in the session scratch; four cases) on
Unicorn 2.1.4's CFV4E core:

| case | result |
|---|---|
| `trap #0` dispatched by hand in the `UC_HOOK_INTR` hook (push frame, set SP/SR/PC), handler's `rte` popped by hand | **PASS** |
| same, `rte` left to the core | FAIL — the core raises intno **256** at `rte` and does not execute it |
| an interrupt raised by hand at an arbitrary instruction (frame for vector 171, jump to handler), `rte` popped by hand | **PASS** |
| same, native `rte` | FAIL, as above |

So the whole exception mechanism is ours to run, and it works: dispatch in
the INTR hook, `rte` = pop `[fmt/vec][SR][PC]` and set the three registers
plus `SP += 8`. Three details that cost the first three spike versions:
- **`SR` must be written before `A7`** — Unicorn banks `a7` on the S bit, so
  a stack pointer written in user state vanishes when S is set (the harness
  already does it in that order, `emu_bringup.boot`).
- The core **never dispatches natively**, even with the table at 0 — the
  hook fires on the same `trap` forever.
- For a trap the hooked PC is the trap instruction itself: the frame's
  return PC is `pc + 2`. For an interrupt raised between instructions the
  return PC is the current PC.

`_run_until`'s existing shims (ISA_C ops, misaligned `movem`, EMAC-with-load)
all work by letting the burst stop on the exception and fixing it up after
`emu_start` returns; the INTR hook already sees those (`intno` 4 etc.) and
must keep letting them through unchanged.

## 4. Design

One new module, `tools/emu_rtos.py`, on top of `emu_bringup` (unchanged) and
`emu_card`'s card model (kept; its wait hook becomes optional).

**Time is counted in samples, not instructions.** The two hardware clocks the
firmware cares about are fixed ratios of the sample clock: a frame interrupt
every 16 samples, a PIT0 tick every 220.5 samples. The one free parameter is
**instructions per sample** — how much ColdFire work fits between events
(264 MHz × 16/44,100 = 95,782 cycles per frame; at a guessed CPI of 1.5 that
is ~64k instructions). It is a knob with a default, not a truth, and the
plan's fidelity gate (§6) is what checks whether it matters.

**The run loop** replaces `emu_frames`' `run_frame`/`Clock`: a priority
queue of pending events in sample time (frame IRQ, PIT0, PIT1 expiry, ATA
completion, forced `INTFRC` bits), and bursts of `emu_start(count=…)` sized
to the next event. At a burst end an interrupt is delivered if its level
exceeds the SR mask (else it stays pending); delivery = push the ColdFire
frame with the vector, jump to `[VBR + 4·vector]`. Resolution is the burst,
which is fine: events are thousands of instructions apart.

**The INTR hook** does three things: vector 32 → dispatch to `[VBR+0x80]`;
intno 256 → `rte` pop; anything else → return (the existing shims handle it
after the burst, as today).

**Peripheral models** (all small, all register-level): PIT0/PIT1 (PCSR with
PIF write-1-clear and the enable/interrupt bits, PMR, a count that expires
into an event); INTC0/INTC1 (ICR levels, IMR masks — the injector consults
them, `INTFRC` writes become pending events); the DSP host port as in M5
(ping index, command register). ATA is the existing model, completing by
raising vector `0xb6` instead of finishing inside the wait hook.

**Idle** ❓: what the kernel does when *no* task is ready is not read yet
(the block path scans down to level 0, where main lives, and main parks —
whether it parks by blocking or by spinning decides whether an "idle" level
must be modelled). Read `0x4001f834`'s tail before M6a.

## 5. Milestones, and which model each wants

Sam asked (6 Sep) to be told when the judgment work is done so a cheaper
model can take the mechanical parts. Tagged accordingly.

- **M6a — first real context switch.** *(judgment)* The INTR dispatcher,
  the `rte` pop, the PIT0 model and the event loop; boot to `trap #0`, let
  the dispatcher take it, and run until all eight tasks have been created and
  every one has run at least once. Exit gate: the task table above matches
  what the emulator observes; `emu_bringup`'s cold path is untouched
  (`refhash`-style: M1–M5 outputs identical with route A off).
- **M6b — waits become real.** *(mechanical once M6a exists)* PIT1 model;
  ATA completion through vector `0xb6`; retire `emu_card`'s `0x40000818`
  hook (keep it behind a flag). Exit gate: the RIG project loads through the
  real storage and engine tasks with the hook off, part bytes identical to
  M4's proof.
- **M6c — the sequencer under the real scheduler.** *(judgment)* Frame IRQ
  on vector `0x41`, the forced tick through `INTFRCH`, transport started by
  the real UI path or by the M5 detour. Exit gate — **the fidelity check for
  the whole fork**: M5's one-trig test (`out/_testproj`, `--poke-trig 2`)
  must land the same byte in `0x46104d15[0]` at the same frame (344, `0xb6`)
  under route A as it does cold. If it doesn't, the difference *is* the
  pre-emption M5 could not model, and it needs reading before anything is
  built on it.
- **M6d — input.** *(mechanical)* Feed key events into the UI task's queue
  (the post primitive against whichever queue `0x4005593c` blocks on — to be
  read in M6c) so PLAY and the REC-arm action run the firmware's own path.
  This is what makes Bryan's recorder test reachable without RAM pokes
  (`EMU.md` M5, "path B").
- **M6e — use it.** *(judgment)* The recorder-arm trace for Bryan; the tick
  pre-emption question; whatever the kit/parts work needs.

Rough sizes, from M4/M5 as the yardstick: M6a and M6c one session each,
M6b and M6d one each on the cheaper model, M6e open.

## 6. Risks, each with the measurement that closes it

- **Instructions-per-sample is a guess.** Close: M6c's gate. If the trig
  frame moves with the knob, the firmware has a real data-dependent timing
  path and the knob needs calibrating against a hardware observable (the
  PIT/frame ratio is fixed; a candidate is the number of frames the bank
  loader takes on hardware, which Bryan's or Sam's unit could time).
- **Speed.** ~64k instructions per frame × 2,756 frames per emulated second
  is ~180M instructions per second of audio; Unicorn does tens of millions
  per second, so expect **3–5× slower than real time**. Acceptable for
  seconds-long tests; a bank load (~35 s cold) will be minutes.
- **Hooks that assume a single thread.** The draw capture, the message and
  sprintf hooks, the ATA completion — all written for cold detours where
  nothing else runs. Under route A a hook can fire in any task. Most are
  read-only observers and don't care; `_emulate_rts` (the wait hook) does,
  which is why M6b retires it.
- **Peripherals the tasks poll that nobody has met.** The MIDI UART, the
  panel scan, the DSP host port beyond the ping. The stall detector in
  `_run_until` exists for exactly this; each one found is a small model.
- **The kernel's idle behaviour** ❓ (§4).
- **The card image is written by the storage task** now, not by a hook: the
  log-append path that once wiped an image (`EMU.md` M4) runs for real. Keep
  images disposable.

## 7. First step

Read `0x4001f834`'s tail (idle), then build M6a against the raw image with
the card attached, stopping at "eight tasks created, each ran once". Nothing
in `emu_bringup`, `emu_card` or `emu_frames` changes until M6c's gate
passes.
