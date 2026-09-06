# The RTOS fork (emulator route A) — scope

Scoped 6 Sep 2026. Status: **M6a/M6b/M6c/M6d done (6 Sep 2026)** —
`tools/emu_rtos.py` runs the firmware's own scheduler: the handoff trap
dispatched by hand, PIT0 ticking, eleven tasks created and each run once,
tasks posting to each other through the kernel, and now a real card mount
plus a real LOAD PROJECT reaching the firmware's own correct project
pointer for real, matching the cold proof's read count. §7 carries a
**retraction**: PR #103's "track-select watcher" reading of the load's end
state was wrong — the bytes are the current *bank*, the run ends on bank A
because the engine's own reset-time "select bank 0" is applied by `sys`
after the file's `BANK=1` was parsed, and whether hardware orders it the
same way is the open question, with a one-press falsifier. §5 carries both measured results and what M6a corrected
in §2 (the task table was wrong in five rows). `EMU.md` has the history of
route B (detours) that this replaces for the paths that need real task
interleaving.

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
| 4 | `0x460d4f80` | `0x4005593c` | `0x460d4780` +0x800 | sys | key-repeat timer (was "UI" — retracted, §9) |
| 3 | `0x460d59d4` | `0x40056c40` | `0x460d51d4` +0x800 | sys | **UI** (was "❓ (new)" — this is the real queue_receive(UI_QUEUE), §9) |
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
- **M6b — waits become real.** *(mechanical once M6a exists — held; the one
  loose end below is M6d's, not M6b's)* PIT1 (source 44) and **ATA
  completion through vector `0xb6`** (`Rtos.attach_card`) were pulled
  forward into M6a because the gate needed them; `emu_card.attach(...,
  cold_hooks=False)` leaves the `0x40000818`/`0x40015786` hooks out. The rest
  landed 6 Sep 2026: `Rtos.request_card_mount` and `Rtos.load_project_live`
  drive a real mount and a real LOAD PROJECT through the real `sys` and
  `engine` tasks — no `engine_run_once`, no hand-run init list. Measured:
  the mount alone reads real ATA IDENTIFY/READ commands and the project load
  reaches **6,189 ATA commands / 30,467 sectors**, matching M4's cold proof
  (~30,955 sectors) to within 1.5%, and the engine writes PART_PTR to
  route B's own known-good value (`0x4017d520`, confirmed against a fresh
  `emu_card.load_project()` run on the same image) from a real dispatch site
  (`0x40087d44`). **Then misread, then corrected (§7 retraction)**: the
  engine's final state is bank B because the project file says `BANK=1`
  (`0x80000002` is the current BANK, not the track; `0x400e21e0` and
  `0x4017d520` are bank A's and bank B's blobs, not "empty" and "correct").
  Under route A the LOAD PROJECT handler's own first step — a reset to
  bank A that posts "select bank 0" to `sys` — is consumed by `sys` after
  the engine has already parsed `BANK=1`, so the run ends on bank A. Real
  cross-task ordering, not a load failure; whether hardware orders it the
  same way is an open question with a one-press hardware falsifier (§7).
  Exit gate: `load_project_live` reports the bank the engine parsed from
  the file (the load reached its finish line) beside the bank the run
  ended on.
- **M6c — the sequencer under the real scheduler.** *(judgment)* Frame IRQ
  on vector `0x41`, the forced tick through `INTFRCH`, transport started by
  the real UI path or by the M5 detour. Exit gate — **the fidelity check for
  the whole fork**: M5's one-trig test (`out/_testproj`, `--poke-trig 2`)
  must land the same byte in `0x46104d15[0]` at the same frame (344, `0xb6`)
  under route A as it does cold. If it doesn't, the difference *is* the
  pre-emption M5 could not model, and it needs reading before anything is
  built on it. **Done 6 Sep 2026 — gate passed** (same byte `0xd3`, same
  track, 344 frames after the start frame, 28 ticks, under route A as
  cold; the `0xb6` above was the historical byte, `0xd3` is today's cold
  reference). Three things stood in the way and §8 has each measured: the
  frame source is re-armed by the eDMA completion ISR (the eDMA block is
  now modelled), a forced interrupt is not subject to the mask (reference
  manual, §17.2.3), and the load leaves the *sequencer* on bank A by the
  same ordering §7 flagged (re-selected through the load's own last step).
- **M6d — input.** **Done 6 Sep 2026, and the premise above was wrong** — §9
  has the retraction and the measurements. Key events do NOT arrive via a
  post to `0x4005593c`'s queue: that task doesn't consume a queue at all,
  and `UI_QUEUE` (`0x460d1664`) only carries state-change notices (posted
  by e.g. FW_TRANSPORT itself) to a different, previously-unidentified task
  (`0x40056c40`). PLAY/REC/STOP instead dispatch through a per-key jump
  table at `0x400d2d54`, called directly — the same shape as the FX2
  shortcut in `MAINMENU.md`. `tools/emu_rtos.py`'s `press_play_live()` /
  `press_rec_live()` call PLAY/REC through their own firmware handlers
  (`call_as_main`, confirmed non-blocking by disassembly); `press_play_live`
  reproduces M6c's fidelity gate exactly (frame 344, byte `0xd3`) — the
  `--sequencer --via-key` CLI flag runs that regression. REC starts the
  transport the same way PLAY does on a project with no recorder-configured
  track, and leaves the record-arm byte (`0x800066a0`) untouched — arming a
  track's recorder for real is still open, needing a project with a track's
  machine set to a recorder (the same gap `EMU.md`'s M5 section already
  flagged), which is what makes Bryan's recorder test reachable without RAM
  pokes (`EMU.md` M5, "path B") and is M6e's job, not this one's. (PR #103's
  hand-off of a "track-select contest" to this milestone stays withdrawn —
  §7 retraction; there is no UI mechanism in it.)
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

## 7. What requests the mount — found 6 Sep 2026, and the race it left open

**The engine's own LOAD PROJECT handler (opcode 4, table at `0x40084870`,
index 4 → `0x40085336`) does not mount the card.** It goes straight into
file-loading calls (`0x4009000c`, `0x40090334`, …). The mount call
(`0x40061648(1)`, what route B calls by hand) lives in a **different, larger
dispatch** belonging to the **`sys` task itself** (`0x46c7bed8`,
`0x40061a94`): its own queue receive at `0x40061cd8` (`0x40000d00` on
`0x460d17ae`), a **78-entry** table at `0x40061cfa` (index = `msg[0]-1`,
range-checked against 77 at `0x40061cea`), decoded in full 6 Sep 2026.
`table[15] = 0x40061f7c` is the case that checks `0x460d1cb8` (card ready)
and calls `FW_CARD_INIT` if it's clear — reached with `msg[0]=16`, and it
also requires `msg[1]` nonzero (`tstb a2@(1)` at `0x40061f82`, else it
returns having done nothing).

**A card-detect hardware interrupt exists and was traced but is NOT this
path.** Vector `0xaf` (INTC1 source 47, handler `0x4001e594`) is a real,
correctly-configured interrupt (`icr[47]=4`, unmasked, confirmed live in the
emulator) whose own state machine — traced instruction-by-instruction 6 Sep
2026 — reads/acks a block at `0xfc0b0144`/`0xfc0b01ac`/`0xfc0b01bc` nobody
had met (`0xfc0b01bc` is a start/busy register: write `0x00010001`, poll
until bits 0/16 clear, then bits 1/17 of a re-read gate two further posts to
the **storage** queue `0x460bb3a0` — modelled as a constant `0x00020002`
reply, `MEDIA_KICK`/`MEDIA_KICK_VAL` in `emu_rtos.py`) — but in every traced
firing it exits without ever reaching `sys`'s table[15] or posting anything
that leads there (`0x460bb40c`/`0x460bb408`, the flags gating those two
storage-queue posts, read zero every time; unproven whether that's because
nothing preceded the interrupt with the right setup, or because this ISR
handles a different condition than "mount an already-present card"). **Not
resolved**: what real event sends `sys` message `[16, 1]`. Likely a UI
action (this reads like "user opened the load-project screen" or similar),
not a boot-time automatic. `Rtos.request_card_mount()` sends that message
directly, bypassing whatever the real trigger is — legitimate for driving
the mount (§ risk below), same as route B's `card_init()` already does by
calling `FW_CARD_INIT` directly.

**`call_as_main` is unsafe for anything that can genuinely block**, found by
crashing it: main (priority 0) is the kernel's only always-ready task (§4,
idle) — the block path's downward scan has nothing to fall back to if main
itself goes non-ready. Borrowing main's context to call `FW_CARD_INIT`
directly (mirroring route B) produced exactly that: main blocked on a real
ATA wait, nothing else was ready either, and the scheduler dispatched a
garbage TCB (`rte ... would return to user mode`, current-TCB pointer
pointing at `TOP_PRIO`, not a task). **Fix, and the actual mount path**:
`Rtos.request_card_mount()` posts `sys` a message instead (`post_message`,
the kernel's `0x40000c3c` primitive, provably non-blocking — a post/signal
can never itself wait) and lets `sys`'s own real task context do the
blocking. `FW_SET_PROJECT_EXISTS` has the identical hazard *conditionally*:
harmless (near-instant, no card touched) when no card is mounted, but once
one is, it does real FAT lookups (`0x40025230`) and blocks — found the same
way, same fix (drop it; it's a route B diagnostic never used to gate the
load, `load_project_live` doesn't call it).

**With the mount driven this way, real ATA activity follows immediately**:
`IDENTIFY`/`READ` commands, PIT1 firing (the storage delay timer), and
`0x460d1cb8` going ready. Posting `FW_POST_LOAD_PROJECT` (opcode 4, exactly
as route B builds it) afterward drives the engine into genuine file reads —
**6,189 commands, 30,467 sectors** in one run, matching M4's cold proof
(~30,955 sectors, all sixteen banks) to within 1.5%. The engine writes
`PART_PTR` (`0x46c82456`) to `0x4017d520` from `0x40087d44` — independently
confirmed as the *correct* value by running route B's own
`emu_card.load_project()` against the same card image cold.

**Retraction (6 Sep 2026, correction pass on Fable): the "track-select
watcher" story that shipped in PR #103 was wrong, and so was PR #102's
"empty sentinel".** What was measured then (the addresses, the timings, the
fact that reposting the load never wins) stands; what it *meant* was
misread by trusting the cold path's frozen value as ground truth and by
not cross-checking a constant this repo had already named. The corrected
reading, every step of it re-measured:

- **`0x80000002` is the current BANK** (`emu_card.FW_CUR_BANK`, already
  named there), and `0x80000004` the current PATTERN. The engine's LOAD
  PROJECT handler parses the project file's `BANK=` and `PATTERN=` keys
  (strings at `0x400b39be`/`0x400b4c8b`, atoi at `0x40087d0a`, clamped
  0–15 at `0x40087d1e`) and writes them there (`0x40087d26`, `0x40087d82`).
- **`PART_PTR = 0x400e21e0 + bank × 635,712`** is the current bank's blob
  in RAM (`0x40087d34`–`0x40087d44`, and `0x4000faf0(bank)` copies 585,088
  bytes from it into SRAM at `0x1001614e` — that is the bank switch). So
  `0x400e21e0` is **bank A**, `0x4017d520` is **bank B**
  (`0x400e21e0 + 635,712` exactly). Neither is empty; nothing here is
  per-track.
- **The RIG project saves `BANK=1`** (`[STATES]` in `project.work`). The
  engine ending on bank B is therefore the *saved* state, and route B's
  `0x4017d520` was right for that reason — not because the cold path is
  ground truth, but because it happens to freeze at the engine's value.
- **The "select bank 0" message is posted by the engine itself.** The
  static message at `0x400d64b9` is opcode 21 (`sys` table index 20 =
  `0x40062288`, "select bank msg[1]"), and both sites that post it
  (`0x4000a150`, `0x40009638`) write the bank byte from a register first —
  it was never a hard-coded 0. Call chain, measured off the stack at the
  post: `0x40085336` (LOAD PROJECT, opcode 4) → `0x400909d8` at
  `0x4008534c` → `0x40025aa2…` → the pattern-load routine → post. That is
  the handler's **first step: a reset to bank A / pattern 1**, before any
  file is read. It runs twice (samples 12,407 and 13,535 in the trace),
  then the files are read, then `BANK=` is parsed (13,838) and PART_PTR
  goes to bank B.
- **`sys` consumes those queued resets whenever it next runs.** The first
  it consumed within one sample (12,408; bank already 0, so a no-op). The
  second pair it consumed at 14,405 — *after* the engine had parsed
  `BANK=1` — and switched the working bank back to A (`0x400622aa`,
  `0x400622b8`). That is the whole "race": the engine's own reset-time
  request, applied late by the task it was sent to, overriding the saved
  bank the engine had set in the meantime.

Two things that looked like evidence for the old story and were not: the
posts recurring "throughout the run" were the reset step of *each* load
attempt (the tool was reposting the load); and "reacts to the track
changing" was the case handler's own guard (`cmpl` current bank against
the request at `0x40062296` — it only writes when they differ), which
made the no-op consumes invisible and the late one look reactive.

**Why `sys` applied the second pair late — measured.** It was not
starved: between the posts (13,535/13,539) and the consume (14,405) the
scheduler dispatched `sys` fifteen times, alternating with the engine's
ATA-wait wakeups, every time into `0x400934d0` — the p2c↔sys exchange
that M6a's dispatch log already showed as a ping-pong. `sys`'s queue is
FIFO; the two "select bank 0" messages sat behind a run of p2c traffic
and were serviced ~870 samples after they were posted, by which point the
engine (blocking and resuming on ATA reads throughout) had reached the
`BANK=` parse (13,838). So the emulator's ordering is a plain consequence
of queue depth and round-robin at priority 1, not of anything the tool
does. **Whether hardware orders it the same way is the open question, and
it is the right kind for route A**: a cross-task ordering whose answer
decides whether the unit comes up on the saved bank after LOAD PROJECT.
The hardware observable is one button press — load the RIG project and
read the bank indicator. If the unit comes up on **B**, the emulator's
p2c traffic or its timing knob is unfaithful here and M6c gains a second
calibration point; if it comes up on **A**, the firmware really does
apply its own stale reset and route B has been hiding it. Recorded as
the falsifier; not resolved in this pass. **M6c found the same ordering
has a second victim (§8.3):** the load's last step copies the bank byte
into the *sequencer's* own playing-bank byte, so the reset arriving
mid-handler leaves the sequencer on bank A too — press PLAY after the
load and see whether the saved pattern runs; that is the second
observable of the same one-press test.

**A diagnostic rule found the hard way in this pass:** never call
`Rtos._sr()` (or anything that runs `emu_start`) from inside a Unicorn
hook callback. It is re-entrant, undefined, and silently derails the run
— one trace logged a single post instead of six before this was spotted.
Read registers directly in hooks; read SR only between bursts.

**Where this leaves M6b's exit gate.** `Rtos.load_project_live` returns
`(mounted, posted, saved_bank, final_bank, elapsed_ms)`: `saved_bank` is
the bank the engine parsed from the file and wrote to PART_PTR (None if
the load never got that far), `final_bank` is where the run ended. The CLI
passes on `saved_bank` being set — the mount and the load work, for real,
through real tasks, at M4's read-count scale — and prints the two side by
side, naming the stale-reset ordering when they differ. The "M6d
inherits a UI-screen contest" hand-off in PR #103 is withdrawn; there is
no UI mechanism in this story.

```sh
make emu-rtos PROJECT=/absolute/path/to/OCTABAM_RIG
.venv/bin/python3 tools/emu_rtos.py --project <dir> --set OCTABAM --name RIG --load-project --ms 6000
.venv/bin/python3 tools/emu_rtos.py --selftest      # the SR-read trap, pinned
```

Diagnostics that found everything above and stay in the tool: `--trace`
(every trap, dispatch, irq, create), `--starvation` (burst-end PCs per
task), `--watch-calls A,B` (entries with caller and first argument),
`--watch-mem ADDR,LEN` (every write, with task and PC), `--watch-pc A`
(registers at an instruction), and in Python directly: `Rtos.last_block`
(O(1), tcb → its most recent block) and `Rtos.blocks` (the full log).
`emu_bringup` and `emu_frames` are untouched; `emu_card` gained the one
flag.

## 8. M6c — the fidelity gate, and the three things that stood between it and route A (Fable review, 6 Sep 2026)

`out/_testproj` is a symlink to a project **freshly saved on the unit
6 Sep 2026** (`OCTABAM_RIG_20260906_cleared`, `~/octa/backups/`): a cold
run against it (`tools/emu_frames.py --project out/_testproj --frames 400
--start --internal-clock --poke-trig 2`) lands track 1's live nibble at
**frame 344, byte `0xd3`** — the frame this document's M5 claim named; the
byte differs from the `0xb6` written down at the time and the cold number
measured today is the reference, not the historical one.

**Retraction of this section's previous text (Sonnet's M6c pass).** Both
hypotheses were wrong, and the "whole-image literal scan found no second
unmask site" claim was false: the re-arm is a literal `moveb %d1,0xfc04801d`
with `d1 = 1` at `0x40004bc2`, in a *different* handler. The frame handler
masks source 1 at entry on purpose; the source is re-armed by **state 7 of
the eDMA completion interrupt**, and the eDMA block was simply not modelled,
so the chain the frame handler kicks never completed and the unmask never
came. Everything below is measured unless marked.

### 8.1 The frame exchange is a DMA chain, and the re-arm is its last state ✅

The chip is the MCF5445x family (`docs/CHIP.md`: MCF54454; the register map
below matches `MCF54455RM` rev 5 chapter 17 for the INTC and chapter 19 for
the eDMA, and the `Intc` docstring's "MCF547x" was wrong). INTC0 at
`0xfc048000` (vectors `64+source`), INTC1 at `0xfc04c000` (`128+source`);
eDMA control at `0xfc044000` (CINT `+0x1c`, SSRT `+0x1e`, CDNE `+0x1f`),
TCDs at `0xfc045000`, 32 bytes per channel (SADDR `+0`, NBYTES `+8`, DADDR
`+0x10`, CITER `+0x14`, BITER `+0x1c`, CSR `+0x1e`; CSR START `0x1`,
INTMAJOR `0x2`, MAJORELINK `0x20`, MAJORLINKCH bits 8–12, DONE `0x80`).
INTC0 sources 8..23 are eDMA channels 0..15 (vector table dumped live:
sources 8, 9 and 15 all go to `0x40004840`).

The frame handler (`0x4000aad0`, INTC0 source 1, level 5) masks itself
(`SIMR := 1` at `0x4000aada`), kicks channel 1 with CSR `0x621` (START,
link → 6; channel 6's `0x720` links → 7; channel 7's `0x0002` raises source
15), clears `0x46104d3a`/`0x46104d3e` and runs the per-track work. The
completion handler `0x40004840` is a jump table at `0x400ab61a` on the
state word `0x46104d3e`: states 0–5 each SSRT channel 1 then channel 0
(sources 9, 8 — the 256-byte control transfers over the host port); state
5 drops to IPL 5 and calls `0x400031a0`, the ColdFire's per-frame EMAC
routine (~7,400 instructions; it STARTs channel 2, a memory-to-memory copy
from the delay ring `0x4f502c10` linked to channel 3, and polls channel 3's
DONE at `0x400035a8` — the "64k+ instructions" read earlier was this poll
never ending); then the DONE check → `0x40004b44` → state 7, and **state 7
(`0x40004bc0`) is the CIMR unmask of source 1.** One frame is the sequence
15, 9, 8×5, 7.

The model (`class Edma`) moves no data — audio is out of route A's scope,
§1 — and gets the one thing that matters right, completion *timing*, by
what a transfer touches: a CSR.START of a channel whose SADDR or DADDR is
in the DSP host-port window (`0x20000000`–`0x20001000`) is the frame's
audio stream and completes, chain and all, at the DSP's next frame
boundary; an SSRT and a memory-to-memory START complete at once. Each of
the three wrong versions on the way produced a specific, reproducible
symptom worth keeping: instant completion re-raised source 15 before state
0 had acknowledged it and the ISR spun forever in state 6; a one-frame
latency applied to channel 2 as well held `0x400031a0` in its DONE poll
forever; completing "kick + 16 samples" instead of "at the next boundary"
gave an 18.5-sample frame period (every sixth frame dropped). With the
boundary rule the period is **16.0 samples exactly**, the exchange takes
about two samples of the sixteen, and a frame costs ≈63.8k instructions —
`ips × 16`, which is what the `ips` knob promises.

**Exact clock.** The quantum accounting M6a uses (charge the burst's
requested count) over-charged frame work about 2.1× — an interrupt ends a
burst early and the whole quantum was still billed. `Rtos.exact_clock()`
counts executed instructions with a code hook and charges those; frame
mode turns it on. Slower, and the right number.

### 8.2 The sequencer tick is a forced interrupt that is never unmasked — and does not need to be ✅

With frames running, transport started and the clock internal, the
sequencer still did nothing: 400 frames, **zero** ticks (cold: 28). The
frame handler's countdown (`0x46107570`, decremented by `tempo24 << 4` per
frame, `0x4000ad50`) expired and forced INTC0 source 32 (`orl #1,
0xfc048010` at `0x4000ae00`) exactly as the M5 write-up says, but INTC0 had
the source **masked**: the sequencer init (`0x400a1050`) installs vector
`0x60` → `0x400a1e0c` and writes ICR 32 := 3 at `0x400a10a4`, and nothing
in the image ever unmasks it — all fifteen CIMR sites read (values 1, 8, 9,
15, 22, 26, 27, 28, 33, 34, 36, 37, 43 and the two ISR re-arms of source
1), no IMRH/IMRL write anywhere, no INTC0 base address ever loaded into a
register, and the pre-handoff boot's INTC writes are ICR/CIMR 27 and
ICR/CIMR 43 only. The other forced sources (34, 36, 37 and the kernel's
own 43) *are* unmasked explicitly. The reference manual settles it,
verbatim (MCF54455RM rev 5, §17.2.3): *"The assertion of an interrupt
request via the interrupt force register is not affected by the interrupt
mask register."* The `Intc` model now ORs INTFRC into the pending set
regardless of IMR (ICR 0 still never delivers). Result: 28 ticks in 400
frames, at frames 1, 16, 30, 45, 59, 73, … — the same count as cold, with
the tick clock advancing `2,646,000` every fourth tick as EMU.md describes.
The kernel's explicit unmask of 43 is belt and braces, not evidence.

Also needed, and easy to forget because cold has the same switch:
`--internal-clock`. The project saves CLOCK RECEIVE set (the Rytm is
master); with it set the frame handler takes the external-clock path
(`0x4000acbc`) and the countdown never moves.

### 8.3 The load leaves the SEQUENCER on bank A — §7's ordering has a second consequence ✅

Ticks alone did not land the trig. The step handler (`0x4009d1e8`) was
called once, scheduled every track three frames out, and never came back;
cold calls it at frame 0 and again at frame 345, and the frame-0 trig path
schedules the event that fires at 344. The difference is two bytes:
**`0x800065bd` is the sequencer's own playing bank and `0x800065be` its
playing pattern** — `FW_START_TRACK` (`0x4009b5c8`) and the step handler
both index the bank blob by them (`bank × 635712 + 0x400e21e0`, `pattern
× 36568`). Cold has (1, 0), the file's `BANK=1` / `PATTERN=0`; route A had
(0, 0), so the sequencer was walking bank A's empty pattern record while
`0x80000002` and `PART_PTR` said bank B.

Who writes them: one setter, `0x400a0570` (bank, pattern, …), reached
through `0x400a1030(bank, pattern)`, and the LOAD PROJECT handler's **last
step** is exactly `0x400a1030(0x80000002, 0x80000004)` at `0x40025b16`.
Cold calls it with (0, 0) twice during the load and (1, 0) at the end.
Route A calls it with (0, 0) at the end (sample 55,047 of the run) —
because the handler blocks on real card reads, `sys` runs in those waits
and applies the engine's own reset-time "select bank 0" (§7) *before* the
handler reaches its last step, which then reads a bank byte of 0. The
`sys` select-bank case (`0x40062288`) sets `PART_PTR`, copies the blob
(`0x4000faf0`), writes `0x80000002` and the UI mirror `0x100b14ce`, and
does **not** touch the sequencer bytes — so re-selecting the bank through
`sys` (M6b's `select_bank_live`) fixed the bank and not the sequencer.

The tool now does what the load's own last step does, after the bank is
what the file says: `Rtos.seq_select_live(bank, pattern)` calls
`0x400a1030` through `call_as_main` (plain stores plus `0x40009e00`; never
blocked). Both are M5-detour moves §5 allows for M6c, and both compensate
for the same unfaithful-or-not ordering §7 already flagged. **The hardware
falsifier from §7 now has two observables**: after LOAD PROJECT, which
bank does the unit show — and does PLAY run the saved pattern? If the unit
comes up on B playing pattern 1, the emulator's `sys` timing (the p2c
traffic ahead of the reset message, or the engine's card-wait length) is
what is unfaithful, and `load_project_live` should end where the unit
does without help.

### 8.4 The gate

**Passed, 6 Sep 2026.** Route A (real tasks, real mount and load, the
sequencer re-selected onto the file's bank and pattern through the load's
own last step, internal clock, transport by the M5 detour, `--poke-trig
2`, 400 frames) against cold (`emu_frames.py`, same project, same flags):

| | cold (M5) | route A (M6c) |
|---|---|---|
| ticks in 400 frames | 28 | 28 (frames 1, 16, 30, 45, 59, 73, …) |
| transport-start writes | `0x10` on tracks 0, 1, 1, 2, 4, 7 | the same six, same order |
| the trig | track 0, byte **`0xd3`**, 344 frames after the start frame | track 0, byte **`0xd3`**, 344 frames after the start frame |

Frame numbering differs by one between the two tools (cold counts the
first frame after the start as 0, the route-A script counted it as 1; the
CLI reports frames since the transport-start frame, so its number is
comparable to cold's directly). Same byte, same track, same distance from
the start — with the sequencer's tick pre-empting the frame handler for
real, the interleaving M5 could not model changed nothing in this test.
That is the result §5 asked for and no more: one trig, one project, one
tempo; the `ips` risk in §6 is closed only to the extent that the trig
frame did not move at the default knob.

Regressions with every change above in place: the M6a gate passes
(`--until-gate --project out/_testproj --ms 1000` — it needs the card and
the 1 s budget; without `--project` the run faults at once on an unmapped
read of `0x100fff04` from `0x4001fa4e`, on HEAD too, a pre-existing gap
in the no-card mapping, noted not fixed), `make verify` is identical to
the trusted baseline (254 PASS), `--selftest` passes. Frame mode stays
opt-in; the eDMA and INTFRC rules are always on and changed nothing in
M6a/M6b's runs (forced source 43 was already unmasked; no other INTC0
force is written outside frame mode).

Reproduce:
```sh
.venv/bin/python3 tools/emu_rtos.py --project out/_testproj --set OCTABAM --name RIG \
  --sequencer --internal-clock --poke-trig 2 --frames 400 --ms 20000
```

## 9. M6d — the real key path, and a retraction of the milestone's own premise (6 Sep 2026)

The scope in §5 assumed the task named "UI" (`0x460d4f80`, entry
`0x4005593c`) blocks in the kernel's queue-receive against whichever queue
it reads, and that feeding a message there is how PLAY/REC reach the
firmware's own path. **Both halves were wrong**, found by disassembling the
task's own entry rather than reasoning from its name — the family of bug
this project keeps re-learning (`CLAUDE.md`'s "disassemble what you
assemble").

### 9.1 `0x4005593c` is not a queue consumer ✅

Its entry (`scripts/disasm.sh emac 0x4005593c 80`) is fourteen instructions:
a counting-wait (`0x400007a4`) on `0x46c7e0e2`, then a loop that waits on it
again and calls `0x4001387c` — a 136-slot countdown-timer scan (decrement
each of 136 four-byte counters; on one reaching zero, clear its bit in a
bitmap at `0x460b a9ae` and call a handler through `0x400136a8`). That is a
**key-repeat timer**, not an input queue. Nothing in the loop names
`0x40000d00`/`0x40000d1a` (queue receive) or `0x460d1664` (`UI_QUEUE`, see
9.2). `0x46c7e0e2` is signalled once per key-scan interrupt tick
(`0x40055cb8`, an INTC1 handler measured decrementing a separate countdown
`0x400c0cf0` and posting to two OTHER queues every second tick) — so this
task's real job is advancing key-repeat, on a fixed schedule, regardless of
what keys are down.

### 9.2 The real `UI_QUEUE` consumer, and why the wrong TCB looked right ✅

A literal-address scan of the raw image (`out/raw/section_3_MAIN_OS.bin`)
for the four bytes of `0x460d1664` finds it in six places: one `queue_init`
call (`0x40040b70`, ring buffer `0x460d4fd4`, size `0x80`) and five posts —
FW_TRANSPORT's start case (`0x4009c506`, msg `*0x400abaca`), a tick-boundary
notice (`0x400a4dd2`, msg `*0x400abacb`), and the key-scan ISR's periodic
post (`0x40055cd6`, msg `*0x400a727a`, every second tick alongside a post to
`SYS_QUEUE`) — but **no receive**. The receive is inside `0x40056c40`
(TCB `0x460d59d4`, prio 3, created by `sys` — the row §2 could only mark
"❓ (new)"): `pea 0x460d1664; jsr 0x40000d00` at `0x40056c72`, return value
dereferenced and its first byte compared against 1 (the opcode
FW_TRANSPORT's start case posts) before running clock-related follow-up
work on `0x46104ca8`/`0x46104cac`.

The queue's **ring buffer** (`0x460d4fd4`) sits 0x54 bytes past
`0x460d4f80` — the key-repeat TCB from 9.1. That adjacency, not any real
relationship, is almost certainly why the earlier "by neighbourhood" pass
named `0x460d4f80` "ui": it is next to the queue's storage, not the task
that reads it. `tools/emu_rtos.py`'s `TASK_NAMES` swapped the two labels to
match (`0x460d4f80` -> `"keyrepeat"`, `0x460d59d4` -> `"ui"`).

### 9.3 Physical keys don't use this queue at all ✅

A second literal scan, for the addresses of two candidate key handlers,
finds them as consecutive longs in a jump table at `0x400d2d54`:
`0x400d2dc0` = `0x4000a274` (**REC**), `0x400d2dc4` = `0x4000a200`
(**PLAY**), `0x400d2dc8` = `0x4000a1e0` (**STOP**, inferred from its shape
— checks `0x80000029`, then `0x40033968`, then tail-calls one of two
`0x4009fxxx` targets — not run in this pass). Walking the table from its
start (`0x400d2d54`) shows eight distinct entries before a run of the
default handler `0x4000184c` — almost certainly the eight **track keys** —
then a second populated run (indices 13–31 of the table) holding PLAY/REC/
STOP among other function keys, then `0x400019f4` filling every remaining
slot to the table's end. This is a keycode-indexed jump table, called
directly (`action(edge)`) the same way `MAINMENU.md`'s FX2 shortcut and
page-key handler work — not a message queue.

Both PLAY (`0x4000a200`) and REC (`0x4000a274`) were disassembled end to
end, including everything they call (`0x400a013c`, `0x400a030c`,
`0x400a14a4`, `0x400a10c8`, `0x40033968`, `0x4009b290`): no reference to any
blocking kernel primitive (`0x40000818` event wait, `0x400007a4` counting
wait, `0x40000d00` queue receive) anywhere in the chain, only plain
subroutines, memory reads/writes, and non-blocking posts (`0x40000c3c`).
Both are safe under `call_as_main`, the same conclusion M6c already reached
for `FW_TRANSPORT`/`FW_START_TRACK` — unsurprising, since PLAY's own
handler tail-calls `FW_TRANSPORT` after some clock-sync bookkeeping gated
on CLOCK RECEIVE (`0x80000028` bit 0), and REC's reaches it too through
`0x400a030c` when nothing is already armed.

### 9.4 Measured, against `out/_testproj` (6 Sep 2026)

- **`0x80000029`** (the byte PLAY's handler tests first, `beqs` a bare `rts`
  if clear) is **already `0x01`** right after a real `load_project_live` —
  no setup needed to exercise PLAY through its real handler.
- **`press_play_live()` reproduces §8.4's fidelity gate exactly**: transport
  running (`0x800065b8` 0->1), then `FW_START_TRACK` ×8, then the same trig
  — track 0, byte `0xd3`, 344 frames after the start frame — as both cold
  and M6c's direct `FW_TRANSPORT` call. `--sequencer --via-key` on the CLI
  runs this as a regression.
- **`press_rec_live()`** on this project (no track's machine set to a
  recorder) also starts the transport (`0x800065b8` 0->1) and leaves the
  record-arm byte `0x800066a0` at 0 through two presses — consistent with
  there being nothing to arm. Confirms the mechanism reaches real firmware
  code; does **not** answer what REC does on a recorder-configured track —
  that project doesn't exist yet (same gap `EMU.md`'s M5 section flagged),
  and closing it is M6e's job.

What would falsify this: a project with a track's machine set to a recorder
and RSRC armed, run through `press_rec_live()`, showing `0x800066a0`
actually change — the one thing this pass could not test.
