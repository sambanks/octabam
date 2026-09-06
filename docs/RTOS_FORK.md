# The RTOS fork (emulator route A) — scope

Scoped 6 Sep 2026. Status: **M6a done (6 Sep 2026)** — `tools/emu_rtos.py`
runs the firmware's own scheduler: the handoff trap dispatched by hand, PIT0
ticking, eleven tasks created and each run once, tasks posting to each other
through the kernel. §5 carries the measured result and what it corrected in
§2 (the task table was wrong in five rows); M6b is next. `EMU.md` has the history of route B (detours) that
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
raises its level); queue receive `0x40000d1a` (what most tasks block in);
event signal `0x40000888`; counting wait `0x400007a4` (decrement, or park
and `trap #0` at `0x40000810`); queue init `0x40000bd4`; task exit
`0x400006e4`. **`0x400009f4` is a lock, not a semaphore** (corrected 6 Sep
under M6a by reading it): owner TCB at `+0`, waiter list `+4`/`+8` chained
through `TCB+0x50`, a contended take unlinks the caller and traps at
`0x40000a78`; unlock `0x40000ab4` hands the lock to the first waiter, makes
it ready, and **traps into the scheduler itself** if the waiter outranks the
top pointer; `0x40000a94` is try-lock and `0x400009e4` the lock init. The
serial-link driver wraps this lock at `0x40010db0`/`0x40010d90`.

**A reschedule is a forced PIT0 interrupt** ✅: signal (`0x400008ea`) and
post set **INTFRCH bit 11 of INTC1** (`0xfc04c010`) — source 43, vector 171,
the scheduler entry, which clears the bit. It can only land once the
primitive restores the caller's SR, one to three instructions later. Make-
ready (`0x4000063c`) does NOT force; it only raises the top pointer, so after
main creates its tasks nothing switches until the first real tick (measured:
the first switch is the first tick after the creates, sample 8,812).

Vector install `0x40000d50(vec, fn)` writes `[VBR + 4·vec]`; the default
handler `0x40000d74` is a trampoline that calls one settable pointer
`[0x460ba970]` (set by `0x40000da4`, from `0x40040b88`) and `rte`s. **The
kernel init `0x40000db0` refills all 256 slots with the trampoline**, so
handlers installed before it (the UART driver's, `0x40010faa`, during the
boot) are gone at the handoff and re-installed by main.

**Tasks — eleven** ✅ (MEASURED 6 Sep 2026 under the real scheduler, by a
hook on `create`; the earlier "eight" came from the five `jsr` create sites
the literal scan finds — the other five sites call through a register and
were missed, so two rows were absent and two were credited to main that a
later task creates):

| prio | TCB | entry | stack | created by | what (🟡 by neighbourhood) |
|---|---|---|---|---|---|
| 6 | `0x46c7fb0c` | `0x40005540` | `0x46c7ea20` +0x1000 | main | voice / DSP mailbox task |
| 5 | `0x460bcc2c` | `0x4001ee30` | `0x460bc42c` +0x800 | sys | storage (FAT/ATA) |
| 4 | `0x460d4f80` | `0x4005593c` | `0x460d4780` +0x800 | sys | UI |
| 3 | `0x460d59d4` | `0x40056c40` | `0x460d51d4` +0x800 | sys | ❓ (new) |
| 2 | `0x460fab80` | `0x40091d18` | `0x460fabd4` +0x2000 | main | ❓ |
| 2 | `0x460ffd44` | `0x400921c4` | `0x460fdd44` +0x2000 | main | ❓ |
| 2 | `0x460e0e38` | `0x4009203c` | `0x460dee38` +0x2000 | main | ❓ (new; ping-pongs with sys) |
| 1 | `0x460ddde4` | `0x4008445c` | `0x460d9de4` +0x4000 | main | **engine** (the 46-opcode dispatcher, `EXTERNAL.md` §6) |
| 1 | `0x46105508` | `0x40098a5c` | `0x4610555c` +0x2000 | main | ❓ |
| 1 | `0x46c7bed8` | `0x40061a94` | `0x460d6de4` +0x2000 | main | **sys** (new): serial + SPI start-up, then creates storage, UI, p3 |
| 0 | `0x46c7ae84` | `0x4001f834` | top `0x46c7becc` | boot | **main** — runs the init list, then parks in `bras .` at `0x4001fc9c` |

At the handoff only main is on a ready list (measured: level 0, one TCB);
the current TCB `0x46c7ae30` is the pre-multitasking context that the first
`trap #0` saves and never resumes. Main's init list — the same list
`card_init` runs by hand on route B — creates seven; the eighth-to-tenth
come from sys once its serial-link traffic and a three-frame SPI exchange
(`0x4001c398`) are done. **Idle is main**: it never blocks, so level 0 is
never empty and no idle task exists (closes §4's ❓).

**Interrupt controllers — two** ✅. INTC0 at `0xfc048000` takes vectors
`64 + source`: the DSP frame handler is source 1 (vector `0x41`, level 5,
`0x4001fc30`) and M5's forced tick is `INTFRCH` bit 0 (`0xfc048010`, source
32, vector `0x60`). INTC1 at `0xfc04c000` takes vectors `128 + source`: PIT0
is source 43 (ICR `0xfc04c06b` := level 1; vector 171 = `0x2ac/4`) and the
ATA interrupt is source 54 (vector `0xb6`). **VBR is `0x40000000`** — the
image's own first KB is the vector table (`[0x400b9668]`), which is why the
no-op `movec` never mattered. At the handoff exactly two slots are
non-default: 32 and 171, both `0x40000550`.

**Every vector install site** ✅ (literal scan of `jsr 0x40000d50`, 6 Sep):

| vector | source | handler | installed at | what |
|---|---|---|---|---|
| `0x41` | INTC0 1 | `0x4000aad0` | `0x4001fc02` (main) | DSP frame |
| `0x47` | INTC0 7 | `0x4001fca0` | `0x4001f81c` | halt path (`SR 0x2700`, `bras .`) |
| `0x5a` | INTC0 26 | `0x400106ec` | `0x400110ae` | serial block ❓ |
| `0x5b` | INTC0 27 | `0x400109bc` | `0x40010faa` (UART init `0x40010efc`, 312,500 baud) | **serial link `0xfc064000`**, level 6: RX callback + TX ring drain |
| `0x5c` | INTC0 28 | `0x40010b88` | `0x40010d6e` | serial block `0xfc068000`, RX only |
| `0x60` | INTC0 32 | `0x400a1e0c` | `0x400a109c` | M5's forced sequencer tick |
| `0x61`/`0x62` | INTC0 33/34 | `0x40055cb8`/`0x400409f4` | `0x40040482`/`0x4004044c` | ❓ |
| `0x64`/`0x65` | INTC0 36/37 | `0x40092bf4`/`0x4009228c` | `0x40092f10`/`0x4009268c` | ❓ |
| `0xac` | INTC1 44 | `0x40020d38` | `0x40020c5e` | PIT1, the storage delay timer |
| `0xaf` | INTC1 47 | `0x4001e594` | `0x4001e01a` (next to the storage create) | ❓ |
| `0xb1` | INTC1 49 | `0x4001c244` | `0x4001c2fc` | counter + ack of `0xfc0bc008` |
| `0xb6` | INTC1 54 | `0x40015304` | `0x40016128` (ATA init `0x400160f8`, main) | **ATA**: one sector per interrupt, signal at count 0 |

**Masking** 🟡: the firmware never writes IMRH/IMRL (no reference in the
image); it unmasks only through the byte register CIMR (`+0x1d`, value =
source, `0x40` = all) and sets ICRn at `+0x40+n`. Since the unit takes
interrupts, a CIMR write must also clear IMRL's MASKALL bit — modelled so,
inferred from that alone.

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

**Two more Unicorn facts, measured under M6a (6 Sep 2026):**
- **Reading SR through the API at a burst boundary corrupts the condition
  codes.** A `cmpl`/`bne` pair split across two `emu_start` calls branches
  correctly on its own, and still does if D2 is read in between — but a
  `reg_read(SR)` in between returns SR with Z clear and installs it, and the
  `bne` is then taken. It cost a session: the serial driver's unlock
  (`0x40000ac8`) compared owner and current, equal, and skipped the release,
  and the next take deadlocked the task on its own lock — once in ~50
  iterations, because the pending tick had shrunk the bursts to 32
  instructions. `emu_rtos` reads SR by executing `movew %sr,%d0` from a
  trampoline (`0x47ef0800`), which flushes the flags through the
  translator's own path; `tools/emu_rtos.py --selftest` pins it. Writing SR
  (a push or a pop) is fine.
- **`UC_HOOK_MEM_WRITE` fires on MMIO-mapped windows**, so the boot's 7,886
  peripheral writes can be logged (hook installed from the first PLL read's
  reply callable) and replayed to seed the models. One rule: an all-ones
  value in that log is a read-modify-write of the stub's all-ones reply, not
  the firmware's choice (PIT0's `PCSR |= 9` arrives as `0xffff`); skip it.

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

**Idle** ✅ (read 6 Sep, before M6a): main parks in `bras .` at
`0x4001fc9c` and never blocks, so level 0 is never empty and there is no
idle path to model. The loop treats a PC parked there as "advance the sample
clock to the next timer expiry" (`idle skips` in the report).

**What M6a met that the scope did not list** — each modelled from the
firmware's own use, all in `emu_rtos.py`: the serial link at `0xfc064000`
(status bit 0 receive-ready, bit 2 transmit-ready, data `+0xc`, mask `+0x14`;
a 2,048-byte transmit ring drained by vector `0x5b` — 4,831 bytes go out
during start-up) and its twin at `0xfc068000`; the DSPI at `0xfc05c000` as a
loopback FIFO (sites wait for 2 or 3 received frames); a test-mode magic
word read at `0x1ffffe` (`0x4003232c`, expects `0xdcba`; zero = normal); a
settings-reset loop that clears four bytes past the 1 MB SRAM window
(`0x4001f298`). Three seeding subtleties: the transmit interrupt arrives at
the handoff still armed with the trampoline as its handler (the cold boot
took no interrupts, hardware drained the ring during the boot) — cleared at
attach; the vector slot is refilled by main (`0x40010efc`); PIT1 is the
storage delay timer and must be wired to source 44 or the delay helper
never returns.

## 5. Milestones, and which model each wants

Sam asked (6 Sep) to be told when the judgment work is done so a cheaper
model can take the mechanical parts. Tagged accordingly.

- **M6a — first real context switch.** ✅ **DONE 6 Sep 2026** *(judgment)*
  `tools/emu_rtos.py`: the handoff trap dispatched post-burst (the boot's
  own INTR hook stops the burst; no second hook), `rte` popped by hand, PIT0
  and both INTCs as register models seeded by replaying the boot's logged
  writes, interrupts injected between bursts with two speeds (4,096
  instructions, or 32 while a source is pending under a raised mask),
  INTFRC writes ending the burst at once, idle skipping at main's spin.
  Gate: `--until-gate` exits 0 at **205 ms emulated** — ten creates match
  the table above field by field including the creator, all eleven tasks
  ran, first switch boot → main. The cascade after the first tick is strict
  priority: voice, p2a, p2b, p2c, p1b, engine, sys, each to its first real
  wait. Measured rate **~1.5 M instr/s** (23 s wall per 400 ms emulated at
  the default `--ips`), so ~60× slower than real time under load; idle time
  is free. Sensitivity: at half and double `--ips` the creation order and
  the task set are identical; the interleaving shifts by one dispatch of the
  creator (a tick lands between two creates) and the sys↔p2c ping-pong
  starts one slot apart — tick phase against init length, as expected. M1–M5
  unchanged: `make verify` and the M4 card load reproduce their step-0
  captures with route A off (`emu_card.attach(..., cold_hooks=True)` is the
  default; `emu_bringup`/`emu_frames` untouched).
- **M6b — waits become real.** *(mechanical once M6a exists)* Pulled
  forward into M6a because the gate needed them: the PIT1 model (generic
  `Pit`, wired to source 44) and **ATA completion through vector `0xb6`**
  (`Rtos.attach_card`: INTRQ per sector, cleared by a status read, over
  `emu_card`'s untouched card model); `emu_card.attach(cold_hooks=False)`
  leaves the `0x40000818`/`0x40015786` hooks out. **Still open**: the mount
  itself — under route A the storage task parks on its queue (`0x460bb3a8`)
  and the card sees **zero commands** in 2 s; nothing has asked for a
  mount. Find what posts it (card-detect on `0xfc0a4039`/`0xfc0a403a`? a
  UI/sys request after start-up? `0x4001e594` on vector `0xaf`, installed
  beside the storage create, is the first suspect). Exit gate unchanged:
  the RIG project loads through the real storage and engine tasks, part
  bytes identical to M4's proof.
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

## 7. Next step

M6a is done (§5). Next is M6b's open item: find what requests the mount
and let it happen under the real tasks, then the RIG load. Reproduce M6a:

```sh
make emu-rtos PROJECT=~/octa/backups/PRESETS_20260905_pretag16/OCTABAM_RIG
.venv/bin/python3 tools/emu_rtos.py --project <dir> --set OCTABAM --name RIG --ms 400 --until-gate
.venv/bin/python3 tools/emu_rtos.py --selftest      # the SR-read trap, pinned
```

Diagnostics that found everything above and stay in the tool: `--trace`
(every trap, dispatch, irq, create), `--starvation` (burst-end PCs per
task), `--watch-calls A,B` (entries with caller and first argument),
`--watch-mem ADDR,LEN` (every write, with task and PC), `--watch-pc A`
(registers at an instruction). `emu_bringup` and `emu_frames` are untouched;
`emu_card` gained the one flag.
