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
the falsifier; not resolved in this pass.

✅ **RESOLVED ON THE UNIT, 6 Sep 2026 (Sam, ~21:30): load OCTABAM_RIG →
the bank indicator reads B01, and PLAY runs the saved pattern.** Both
observables of the one-press test came back on the "emulator is
unfaithful" branch: the firmware does NOT apply its own reset-time "select
bank 0" after the `BANK=` parse. So the ~870-sample lag `sys` shows here
is the emulator's — the p2c traffic ahead of the reset in `sys`'s FIFO,
or the engine's card-wait length, is not what the hardware does. The two
compensating helpers (`select_bank_live`, `seq_select_live`) are now
known to be papering over an emulator defect, not a firmware behaviour;
the faithful fix is in the load's timing, after which both should be
deleted and `load_project_live` should end on bank B unaided. Not yet
done — this pass only recorded the measurement. **M6c found the same ordering
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

> ❌ **RETRACTED 8 Sep 2026 (milestone O6): the BYTE below is `0x08` then
> `0x18`, not `0xd3`, and there are FIVE transport-start writes, not six.**
> Re-measured on the same project with the same commands: route A
> (`--sequencer`) and the cold tool (`emu_frames.py`) both give five writes of
> `0x10` at frame 0 (tracks 0, 1, 2, 4, 7) and `0x08` then `0x18` at frame 344
> on track 0. The FRAME (344), the track and the tick count (28) are unchanged.
> 🟡 The likely cause is the EMAC fix of 7 Sep (§10.16) — the byte is computed
> by an EMAC chain in the frame handler — but nobody has re-run this section's
> exact tree on the stock library, so that attribution is inferred. The C++
> port reproduces the current numbers exactly (`COLDFIRE_PORT.md`, O6).

`out/_testproj` is a symlink to a project **freshly saved on the unit
6 Sep 2026** (`OCTABAM_RIG_20260906_cleared`, `~/octa/backups/`): a cold
run against it (`tools/emu_frames.py --project out/_testproj --frames 400
--start --internal-clock --poke-trig 2`) lands track 1's live nibble at
**frame 344, byte `0xd3`** (❌ the byte is retracted above) — the frame this document's M5 claim named; the
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

✅ **It does come up on B, playing (unit, 6 Sep 2026 — §7).** Both helpers
are therefore compensation for an emulator defect and are to be removed
once the load's timing is fixed; until then every `--sequencer` run
carries them, and the "re-selected through the load's own last step" line
in the tool's output is the reminder.

### 8.4 The gate

**Passed, 6 Sep 2026.** Route A (real tasks, real mount and load, the
sequencer re-selected onto the file's bank and pattern through the load's
own last step, internal clock, transport by the M5 detour, `--poke-trig
2`, 400 frames) against cold (`emu_frames.py`, same project, same flags):

| | cold (M5) | route A (M6c) |
|---|---|---|
| ticks in 400 frames | 28 | 28 (frames 1, 16, 30, 45, 59, 73, …) |
| transport-start writes | ❌ `0x10` on tracks 0, 1, 1, 2, 4, 7 | ❌ the same six, same order |
| the trig | ❌ track 0, byte **`0xd3`**, 344 frames after the start frame | ❌ track 0, byte **`0xd3`**, 344 frames after the start frame |

❌ **The last two rows are RETRACTED (8 Sep 2026) — see the note at the head of
§8.** Re-measured: FIVE transport-start writes of `0x10` (tracks 0, 1, 2, 4, 7)
and the trig is bytes **`0x08` then `0x18`** on track 0, still 344 frames after
the start frame, still 28 ticks. The two tools still agree with each other, and
the C++ port now agrees with both.

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

## 10. M6e (6 Sep 2026) — the recorder project exists, one claim of this section's own first pass is RETRACTED, and the arm path is still unlocated

The first pass of this section (PR #108) built the fixture and read one
result out of it. The fixture stands; the reading does not. Both are below,
with the controls that separate them — every number here is from
`--sequencer --internal-clock --poke-trig 2 --frames 400 --ms 20000`, the
M6c gate's own command, varying only the project.

### 10.1 The fixture ✅

The project §9.4 said didn't exist now does. The byte is a track's
**machine type**, one per track per part, and it now has a real home in the
toolkit rather than a scratch copy of the offsets:

```sh
python3 tools/ot_project.py machine-type <project> <bank> <part> <track> <type>
# and the emulator wrapper, which also writes the part's saved mirror:
.venv/bin/python3 tools/scratch/make_recorder_testproj.py out/_recproj [type]
```

`ot_project.set_machine_type` writes part N **and** its saved mirror N+4
(the "eight PART records, not four" rule) and fixes the bank checksum
through the existing `_bank_write`. Track 1 keeps its existing trig
(pattern 1 step 2 — the one M6c/M6d's gate fires at frame 344, byte
`0xd3`), so no on-disk trig edit is needed.

**Verified ✅**: loading the patched project through the real M6b path and
reading RAM back, all 8 tracks' machine types are `[4, 2, 0, 0, 0, 0, 0,
1]` where the source project reads `[2, 2, 0, 0, 0, 0, 0, 1]` — only track
1 changed, exactly as patched. File-offset math: RAM's `PART_PTR +
part*0x18b2 + 0x8eda2 + track` maps to file offset `PART_BASE +
part*PART_STRIDE + 0x2b + track` — a flat +9-byte IFF chunk-header shift,
the same shift `ot_project.py`'s `FX1_OFF`/`FX2_OFF` already carry relative
to their own RAM offsets (0 and 8).

⚠️ **The type NAMES are inferred, and the first pass wrote "4 (PICKUP1)" as
if measured.** `PARAM_PAGES.md` derives 0/1 = FLEX/STATIC, 2 = THRU, 3 =
NEIGHBOR, 4 = PICKUP from the five PLAYBACK descriptor pages' parameter
sets and says in as many words that the mapping is **not confirmed against
the dispatch order**. Read 4 below as "the value the inference calls
PICKUP".

### 10.2 What the trig test measures ✅, and what it does not ❌

With track 1 at type 4, its `FW_LIVE_NIBBLE` writes (`0x46104d15`) go from
**8 to 5**. That much reproduces exactly (re-run twice, 6 Sep).

The first pass called this "the first empirical confirmation that
machine-type dispatch genuinely branches for PICKUP". **It is not.** Two
things falsify that reading, neither of which needed new machinery:

| track 1's machine type | FW_LIVE_NIBBLE writes | |
|---|---|---|
| 2 (the project as shipped) | 8, incl. `0xd3` at frame 344 | the M6c gate |
| 3 — NEIGHBOR, in range | **8, identical to baseline** | a different valid type changes nothing |
| 4 — "PICKUP" | 5 | |
| 7 — **out of range** for the 0..4 dispatch `PARAM_PAGES.md` names | **5, identical to type 4** | |

An out-of-range machine type produces the same signature as the one under
test, so the measurement carries no PICKUP-specific information: it reads
**"type >= 4 / this track is not started"**, not "PICKUP branches".

And the writes that disappear are not only the trig's. They are:

```
   frame     0 track 0 byte 0x10        <- the transport-start write, GONE
   frame   344 track 0 byte 0xd3  x2    <- the trig, GONE
```

That frame-0 `0x10` is one of the **six start-frame writes in §8's own
fidelity table**. The track drops out at `FW_START_TRACK`, before any trig
exists — so nothing being measured here happens at trig dispatch at all.

**What would falsify the replacement reading**: a type-4 run in which the
track *does* start (say, once a recorder buffer is assigned to it) and the
trig then behaves differently from type 2's. That would make the difference
PICKUP-specific after all — and it is the same experiment as §10.5's next
step, which is why this is worth re-testing rather than closing.

### 10.3 §9.4's falsifier, run at last — and it was aimed at the wrong mechanism

§9.4 named the test exactly: *"a project with a track's machine set to a
recorder and RSRC armed, run through `press_rec_live()`, showing
`0x800066a0` actually change."* The first pass built half the fixture and
then ran the PLAY/trig test instead; §10 as written never mentioned REC.
Run now, on the type-4 project, `--via-rec`:

**Measured ✅**: pressing REC through its own firmware handler over a
running transport moves the record-arm word `0x800066a0` **not at all** —
`0x0` across the press, `0x0` after 400 frames, and `--watch-mem` over it
shows its only writes are eleven zero stores during the LOAD (pcs
`0x4002095e`, `0x4009ae56`, task `engine`), none at the press. Same on the
plain project. The run stays faithful while it does so: the baseline
control under the same flag keeps M6c's gate (8 writes, `0xd3` at frame
344), which is what makes the null readable.

**❌ But the null says nothing about the recorder, because REC is not what
arms one.** From the Octatrack manual: `[REC]` activates **GRID RECORDING
mode** — a sequencer mode — and *"once a record trig has been trigged by
the sequencer the track recorder will start to sample"*. Sampling is
initiated by a **recorder trig**, not by the transport REC key; the key's
role is only to make the sequencer honour those trigs. So §9.4's falsifier
expected a mechanism the key does not drive, `0x800066a0` is most likely
the grid/live record MODE state rather than an audio-recorder arm 🟡, and
"REC leaves it at 0" is the expected result on any project, recorder-
configured or not. It is now measured on both, and that is where its value
ends.

The lever is §10.5's first item. M6d's per-key jump table (`0x400d2d54`,
eight track-key entries) stays relevant for the `[TRACK]`+`[YES]` re-arm
gesture the manual describes, but the trig is the primary path.

⚠️ **Two orderings are known bad, and both fail on the PLAIN project too**
(so neither is a recorder finding): REC-then-PLAY delivers 400 frames with
**zero** `FW_LIVE_NIBBLE` writes — REC starts the transport itself, so PLAY
toggles it back off — and REC alone, with the tracks started by hand the
way `press_play_live` does, also gives zero. Only PLAY-then-REC keeps the
gate. `--via-rec` now does that, and the comment in `emu_rtos.py` says why.

### 10.3b Two instrument defects found while doing it — both silent

Neither changed a conclusion in the end, but either could have invented
one, and one of them is the exact shape of `CLAUDE.md`'s "a measurement can
be structurally blind to the thing you are using it to rule out".

- **`--watch-calls` and `--watch-mem` printed NOTHING unless `--trace` was
  also on.** Both hooks appended to `rt.calls` / `rt.mem_writes`; the CLI
  read neither. An address that never fired and one that fired every frame
  looked identical from the command line: silence. The CLI now prints a
  per-address entry count and the writes. ✅ **Re-derived with the working
  readout**, and §10.4's null survives it: `0x4000b800` **0**,
  `FUN_400977cc` **0**, `0x4000d2a0` **400**, one run, same command.
- **`0x800065b8` and `0x800066a0` are LONGWORDS, and were being read a byte
  at a time.** The transport start is a 4-byte store of 1 (`[0x800065b8] <-
  0x1 (4)` at pc `0x4009c3d4` in `main`, measured), so the *byte* at
  `0x800065b8` stays 0 while the 1 lands in `0x800065bb`. A byte read of
  either address reports "never changed" no matter what the firmware does.
  §9.4's "`0x800065b8` 0->1" is right about the word and would have read as
  a flat 0 to anyone checking it as a byte — which is how this surfaced.
  Both are read as words now.

### 10.4 The `0x4000b800` flag ✅ — and it is stronger than the first pass wrote

`watch_calls` on every candidate this session could name from the existing
docs — `FUN_400977cc`, `FUN_40097168`, the recorder TRIG branch
`0x40083544`, the QREC scheduler `FUN_40005178`, the arm caller
`0x40005ff0`, and the per-frame trig gate `0x4000b800` `EMU.md`'s M5
section names — logged **zero calls** across 400 frames, `0x4000b800`
included on the ORIGINAL project's own successful trig. `0x4000d2a0` fires
400/400 in the same runs, so the instrumentation works.

⚠️ Those zeros were originally read off a CLI that printed nothing either
way (§10.3b). They have since been **re-derived with a working readout** —
`0x4000b800` 0, `FUN_400977cc` 0, `0x4000d2a0` 400/400 in one run — so the
flag stands on a measurement now rather than on an absence of output.

The first pass concluded that address "is not reached via `jsr`". That
understates the instrument: `watch_calls` installs a `UC_HOOK_CODE` **at
the address**, so a zero count means that instruction **never executed, by
any route** — jsr, branch or fallthrough. `EMU.md`'s claim that
`0x4000b800` is the trig-write site is unconfirmed under route A, and the
write still happens on schedule, so some other code does it.

### 10.6 The pattern format, and an on-disk TRIG fixture that works ✅

The recorder-trig fixture needed the pattern format first, so that is now
measured rather than assumed.

**A bank is IFF.** Sixteen `PTRN` chunks (file stride `0x8eec`), each holding
eight `TRAC` sub-chunks (file stride `0x922`) for the audio tracks and then
eight `MTRA` for the MIDI ones, and after all sixteen patterns the eight
`PART` records at `0x8eed6`. The RAM strides are 8 and 9 less respectively
(`0x8ed8` per pattern, `0x91a` per track) because the chunk headers are
stripped on load.

⚠️ **A `PTRN`'s header is 8 bytes and a `TRAC`'s is NINE** — tag, length and
one pad, the same +9 the PART records carry. Read as 8 it is not obviously
wrong: every mask shifts one byte, still looks like a plausible trig
pattern, and a step you set lands eight steps away — which is exactly what
happened here (a step-2 trig written at +8 became steps 10 and 12 and simply
never fired inside a 400-frame window). Settled by loading the project and
reading the RAM record back: +9 matches byte for byte, +8 does not. Same
family as every other "verify by readback" rule in this file.

**A `TRAC` opens with 64-bit big-endian step masks at an 8-byte stride**,
bit (step-1). `mulsl #0x91a,%d7` with `d7` = track, at `0x4009d376` and its
siblings, is where the stride is measured from. What the sequencer does with
them (`--watch-pattern` over a live record, then `scripts/disasm.sh emac`):

| mask | consumer | what it does |
|---|---|---|
| `0x00` | `0x4009d41c` | the note/sample trig — the one `poke_trig` sets |
| `0x00\|0x08\|0x10\|0x18` | `0x4009d382..9a` | ORed into the "anything on this step" test |
| `0x20` | `0x4009d93c` | sets bit 12 of the per-track flag word at `0x46c7a6c0` |
| `0x28` | `0x4009d96e` | bit 13 |
| `0x30` | `0x4009d99a` | bit 14 |
| `0x38` | `0x4009d9f6` | bits 5+8 (else bit 5); only read when 12/13/14 fired |
| `0x40` | `0x4009d3d6` | gates a per-step byte at `+0x52` into a `x110250` timing calc |

`0x40`/`0x48` are **not** masks: they read as a run of `0xaa`, a
default-filled per-step byte array.

**The fixture** (`ot_project.py`, so it composes with the rest of the
toolkit rather than living in `tools/scratch/`):

```sh
python3 tools/ot_project.py pattern-trig <project> <bank> <pattern> <track0> <step> [mask]
python3 tools/ot_project.py pattern-diff <projectA> <projectB> <bank>
```

✅ **Proven end to end**: `pattern-trig out/_trigproj 2 0 0 2` — step 2, on
disk, no RAM poke anywhere — lands `0xd3` on track 0 at **frame 344**, the
same byte, track and frame as `--poke-trig 2`, which is M6c's own fidelity
gate. File -> card -> real LOAD PROJECT -> sequencer, with nothing poked.

✅ **SETTLED ON THE UNIT, 6 Sep 2026 — a recorder trig is masks `0x20`,
`0x28` and `0x30`, all three at once.** Procedure: a byte-exact copy of the
cleared baseline went onto the card as project `RECTRIG`; Sam loaded it on
bank A pattern A01, selected track 1, opened RECORDING SETUP 1
(`[FUNC]`+`[REC1]`), entered GRID RECORDING, pressed `[TRIG]` 9 once (red),
quick-saved (`[FUNC]`+`[PROJ]`), synced. `pattern-diff <baseline> <RECTRIG>
1`:

```
pattern  0 T1 mask 0x20: 0000000000000000 -> 0000000000000100  steps [9]
pattern  0 T1 mask 0x28: 0000000000000000 -> 0000000000000100  steps [9]
pattern  0 T1 mask 0x30: 0000000000000000 -> 0000000000000100  steps [9]
```

A whole-file byte diff of `bank01.work` shows exactly those three bits
(`+0x26`, `+0x2e`, `+0x36` from TRAC(0,0)) and the bank checksum
(`0x9b4d0`, `0x4c` → `0x4f`) — nothing else. These are the three masks the
format note above maps to bits 12/13/14 of the per-track flag word at
`0x46c7a6c0`. **Three masks for one trig** lines up with the manual's "a
recorder trig defaults to sampling from all three input sources": the
reading that `0x20`/`0x28`/`0x30` are REC1/REC2/REC3 respectively was
then half-measured the same evening: Sam held `[TRIG]` 9 in RECORDING
SETUP 1 and pressed the second source key to toggle REC2 off, saved, and
`pattern-diff` between the two saves shows **only `0x28` cleared** (file
byte `0x55` `01` → `00`, plus the checksum) — so **`0x28` = REC2 ✅
measured**, and `0x20` = REC1 / `0x30` = REC3 follow by order 🟡 (not
separately toggled). Second save: `~/octa/backups/RECTRIG_20260906_step9_noREC2`.
The returned project is
`~/octa/backups/RECTRIG_20260906_step9` (work + strd files only; its
`project.work` came back with `BANK=0`/`TRACK=0`, so unlike the baseline
this fixture does not meet §7's ordering at all) and `out/_recproj`
points at it. **`+0x8f385` stays what §10.5 says it is**: the part's TRIG
mode byte, not the trig.

⚠️ A run budget trap that cost one run: at 120 BPM a sixteenth is 344
frames, so **step 9 is at ~2,750 frames** — `--frames 400` (the gate's
budget, sized for step 2) ends 145 ms after the transport starts and never
reaches it; the run passes the gate and reports nothing, which looks like
"the recorder trig does nothing". Use `--frames 3000 --ms 30000`.

The paragraph below is the state before that measurement, kept for the
method: the emulator did not settle it. Setting step 2 in every candidate mask on the type-4 track
produces exactly one call to `0x40005ff0` (the "arm caller") where the same
run without the pokes produces none — but bisecting into halves gives one
call from *either* half, so that observable is not specific enough to name a
mask. `0x40005ff0`'s call site (`0x4000d35a`) explains why it is a weak
signal: the frame builder calls it whenever a track's live byte has any of
bits `0xd0` set, which the ordinary trig byte `0xd3` also satisfies.

**`pattern-diff` is what finishes this, and it needs the unit, not more
emulation**: save a project, add ONE recorder trig on the unit, save it
again under another name, run `pattern-diff` on the pair. The mask offset
and the step fall out with no reverse engineering at all. That is a
30-second job at the hardware and it is the cheapest measurement left in
this milestone.

### 10.5 Where this actually goes next

- **A RECORDER TRIG on the pattern.** This is the mechanism, per the
  manual (§10.3): the sequencer trigs it and the track recorder starts to
  sample. ⚠️ **Not `+0x8f385`** — that is the recorder SETUP page's TRIG
  *mode* (ONE/ONE2/HOLD), one of the twelve bytes at `0x8f382 +
  part*6322 + track*12`, and it lives in the PART, not the pattern. The
  fixture that writes a per-step trig is built and proven (§10.6); the
  open half is **which mask** the recorder's trigs live in, and
  `pattern-diff` against a pair of projects saved on the unit answers it
  in one command.
- **A recorder buffer assignment** (object ids 128-135, control records at
  `0x46c922c4 + id*44`, `EXTERNAL.md` §6) the way a STATIC track needs a
  sample slot (`ot_project.py`'s `set_track_slot`). Still not located; it
  is also what §10.2's falsifier needs.
- **Not** another round of `watch_calls` on addresses pulled from prose.
  Six were spent that way for six zeros.
- **The tick pre-emption question** in M6e's own scope is untouched. §8's
  gate is evidence it changed nothing *in that one test*, and no more.

Reproduce (both projects; `[type]` 3 and 7 are the controls of §10.2):

```sh
cp -R <a real project dir> out/_recproj
.venv/bin/python3 tools/scratch/make_recorder_testproj.py out/_recproj 4
.venv/bin/python3 tools/emu_rtos.py --project out/_recproj --set OCTABAM --name RIG \
  --sequencer --internal-clock --poke-trig 2 --frames 400 --ms 20000 [--via-rec]
# the control is the same command against out/_testproj
```

### 10.7 The recorder trig under emulation (6 Sep 2026, evening) — the path LIGHTS UP from a RAM poke, and the on-disk fixture never reached it

All runs: `--sequencer --internal-clock --frames 3000 --ms 30000` (step 9
needs ~2,750 frames — §10.6's budget trap), watches as named. The
fixture is `out/_recproj` (bank A, pattern A01, T1: note trig step 1 +
recorder trig step 9 = masks `0x20`/`0x28`/`0x30`).

**The fixture, five instruments, five nulls ✅ (measured):**

| watch | result over 3,000 frames |
|---|---|
| `FW_LIVE_NIBBLE` / `FW_TRIG_WORDS` | only the frame-0 start writes (T1, T6 ×2, T8 — bank A's step-1 trigs); `0x46104d26` never nonzero |
| eight arm-path candidates (`0x40005ff0`, `0x40097168`, `0x400977cc`, `0x40006dfc`, `0x40083544`, `0x4000b308`, `0x4000b800`) | 0 entries each; `0x4000c8e0` 24,000 = 8/frame, the frame builder |
| staged slots `0x800018be..e6`, immediate slot `0x46c7e9fa`, armed bitmask `0x8000184a` | no writes (the bitmask gets three zero stores at the run's last sample, `main` `0x4000bf22/30` — teardown) |
| per-track flag word `0x46c7a6c0..e0` | 120 writes, ALL zero (15 clears × 8 words, `0x4009e3cc`) |
| the three mask tests `0x4009d93c/96e/99a` | entered 160× each; the follow-on at `0x4009d9f6` (taken only when a bit was set) **0×** |
| `--watch-pattern 0x40` (reads of T1's mask rows) | rows `+0x04, 0x0c, 0x14, 0x1c, 0x24, 0x2c, 0x34` read **3× each** — low 32-bit halves only |

The disassembly (`scripts/disasm.sh emac 0x4009d900`) says what §10.6's
table called "sets bit 12" is the **test**: `andl %a0@(0,%a3:l),%d0` with
`d0` = the step bit, then `bset #13,%d3` on nonzero; the OR'd `d3` is
stored to `0x46c7a6c0` at `0x4009da12` only if nonzero. So a zero flag
word means the step bit never matched a mask row in RAM — the code
path is consistent with itself, and the question became whether the
sequencer ever evaluated step 9 of THIS pattern.

**Control: the same three masks poked into RAM at step 9 of the BASELINE
(bank B, pattern 0, T1), `--poke-trig 9 --poke-mask 0x20,0x28,0x30
--poke-mask-track 0` — everything fires ✅ (measured):**

```
frame  2756 track 0 byte 0x35  nibble 5  flags 0x30     <- the note trig, step 9 (344 x 8 = 2752)
[0x46c7a6c0] <- 0x7020  at pc 0x4009da12 in main         <- bits 12/13/14 (+ bit 5), the store above
watch-call : 0x4009d9f6 entered 1 time(s)
watch-call : 0x40005ff0 entered 1 time(s), callers 0x4000d35c   <- the arm caller, once
FW_TRIG_WORDS (0x46104d26) nonzero writes (245): (2757, 0, 0x7235), then (frame, 0, 5) every frame to 3000
```

`0x46104d26` — Bryan's anchor, zero in every run since M5 — goes
nonzero one frame after the trig (`0x7235`, then a steady `5` per frame).
The live byte carries flags `0x30` instead of the note trig's `0xd0`.
**This is path B** ([[octabam-emu-frames]]: staged → immediate →
`0x4000c8e0` word assembly → `0x46104d26` + arm caller), reached by the
sequencer's own recorder masks with no REC key and no machine-type change
— the M6e first pass was looking for it on the wrong track and with the
wrong lever. Two tool fixes on the way: `poke_trig`/`poke_mask` only knew
steps 1–8 (`bytes must be in range` at step 9), now 64; and
`--watch-mem` printed 12 writes and hid the rest.

**Why the on-disk fixture did not fire — settled ✅ (measured): bank A's
pattern A01 steps at ONE QUARTER the rate, and step 9 is ~11,000 frames
in, not 2,750.** The same three masks written ON DISK at step 2 of a copy
of the fixture (`pattern-trig … 1 0 0 2 0x20`, `0x28`, `0x30`; no RAM
poke) fire the identical chain — flag word `0x7020` at `0x4009da12`,
`0x4009d9f6` ×1, arm caller ×1 from `0x4000d35c`, `0x46104d26` `0x7257`
then `7`/frame — at **frame 1379**, which is 4 × 344 + 3. The read watch
agrees: T1's rows are read at 0, ~1379, ~2758 — three evaluations in
3,000 frames, one per step at that scale; the baseline under the same
watch reads its rows **9×**, one per 344-frame step. (The baseline's bank B pattern
steps at 344, which is where the 344-frame gate and the "step 9 ≈ 2,750"
arithmetic came from; the RIG's A01 evidently carries a 1/4× scale or
equivalent length setting — not located in the PTRN record, inferred
from the timing 🟡.) ✅ **Sam's own step-9 trig, landed** (`--frames
11500`, the unmodified `out/_recproj`): flag word `0x7020`, `0x4009d9f6`
×1, arm caller ×1 from `0x4000d35c`, `0x46104d26` `0x72d2` at **frame
11026** then `2`/frame — 8 × 1378.25, the same chain as the step-2 copy
and the RAM-poke control. The trig the unit wrote, through the file, the
card model, the real load and the real sequencer, with nothing poked.

**What this establishes (measured, one emulator, no hardware audio):**
a recorder trig on disk → card → real LOAD PROJECT → the sequencer's mask
tests → the flag word → the frame builder's arm caller → Bryan's trig
word, with nothing poked. That is the mechanism the recorder question
needs, reachable from a project file. Not yet measured: what the arm
caller does next (`0x40005ff0` ran once — its class-2 path, the sample-
slot control record, the DSP-side start), and whether the byte-`0x30`
live flag is what the DSP's recorder reads.

### 10.8 Past the arm caller: the trig becomes an ENGINE message, and the engine allocates the recorder buffer (6 Sep 2026, late — measured)

Runs on the step-2 copy of the fixture (`--frames 1600`), `--watch-calls`
over the arm caller's callees (static: `0x40005ff0` runs `0x40005ff0..
0x40006712`, calling only `0x40005c7c`, `0x40097168`, `0x40005304`) and
the engine's handlers.

**The arm caller posts an engine message.** `0x40005304` entered once,
from `0x400066b6` inside the arm caller; `0x40097168` (the machine==4
classifier) 0× — the track's machine is THRU (type 2), so the PICKUP
branch is not taken, and the recorder still arms. `0x40005304` is a
poster: an 8-byte record at `0x46104d52 + track*8` — opcode `0x22`,
byte 1 = 1, word 2 = track, long 4 = 1 (pending) — posted with
`0x40000c3c` to **`0x460d17ce`, the engine task's command queue** (the
same queue LOAD PROJECT and RELOAD BANK use, EMU.md; Bryan's "central
engine-command queue" is corroborated a second time). Not touched by the
trig: the sample-slot control record `0x80004f1c..+84` (0 writes) and
`0x800066a0` (only the load's zero stores — three fixtures now say that
word is not the recorder arm).

**The engine handles it.** Its dispatcher (`0x4008484e`: `queue_receive`
on `0x460d17ce`, opcode ≤ 45, 16-bit offset table at `0x40084870`, base
`0x40000400` for the raw image) sends opcode `0x22` to **`0x40085bde`**:

```
[1355822.8] [0x46104d52] <- 0x22   main   0x4000531a   <- the post (opcode, flag=1, track=0, pending=1)
[1355825.0] [0x46104d53] <- 0x0    engine 0x40085bee   <- 2.2 samples later: handler takes the flag
            0x40095a90(track)  from 0x40085c02          <- release the track's recorder state
            0x400948cc(track)  from 0x40085c0a          <- allocate a chain from the PCM pool
[1355975.2] [0x46104d56] <- 0x0    engine 0x40085c2c   <- 152 samples later: pending cleared
```

Both callees index **`track + 128`** — the recorder-buffer object ids
Bryan named — into the arena at `0x46c2e9c0` (strides `0x390a` /
`0x7214` per `(track+2)`), the table `0x461053a8[track]` and
`0x46c75e88`. `0x400948cc` reads the pool pointers `0x8000691c`/
`0x80006920` and returns **−5** when there is no room; the handler turns
−5 into a message to `sys` (`0x400d1662`, track in byte 1) — the "no
memory" path. Each also ran 16× more from `0x4009636c`/`0x40097132`
(load-time, 8 tracks × 2 🟡 by count, not timed).

**Opcode `0x25` (Bryan's "arm" opcode) ALSO ran once** — handler
`0x40085c88` → `0x40099680(1, track)` (the open/arm function, 290× in
the run, the rest from load-time sites `0x40023ad4/aee`, `0x4002585a`).
Whether that one post came at the trig or during the load is **not
timed** (the call summary has no timestamps) — the next run should
`--watch-mem` the `0x25` record and `--watch-pc 0x40085c88`.

**What this establishes:** recorder trig (disk) → sequencer mask tests →
flag word → frame builder → arm caller → engine opcode `0x22` → recorder
buffer released and re-allocated from the PCM pool, ~3.4 ms of engine
work, all under the real scheduler. **What it does not:** how the DSP is
told to start sampling (nothing here writes the host port), what the
`0x22`/`0x25` split means (start vs. arm?), and the loop-point click
([[octabam-recorder-control-path]]) — the click is in the recorder's
PLAYBACK block chain, which this milestone has only just reached the
allocation of.

### 10.9 At RLEN = MAX no length converter runs — and the tempo/setup words are refreshed every frame (6 Sep 2026, late — measured)

Runs E/F on the step-2 copy (T1's RECORDING SETUP as saved by the unit:
`INAB 1, INCD 1, RLEN 64 = MAX, TRIG 0, SRC3 0, LOOP 1 | FIN 0, FOUT 0,
AB 0, QREC 255, QPL 255, CD 0`), 1,600 frames, the trig at ~1,379:

- **None of the three length converters ran**: `0x4006e3b2` (truncating,
  `EXTERNAL.md` §6), `0x400060c4` (the pickup FOUT length) and
  `0x40006d48` — **0 entries each**, while the trig's `0x22` post, its
  handler and the `0x25` handler all ran once. So at MAX the arm computes
  no length, which is the primer's "at MAX the recording runs until the
  next record trig" seen from the code side. The converter question
  (§8.2 of `EXTERNAL.md`) therefore needs a fixed-RLEN fixture — built as
  `ot_project.py recorder-setup <proj> 1 1 0 RLEN 3` + `set-tempo <proj>
  128.0` (Bryan's own clicking default, 128 / RLEN 4 / 1×); run H.
- **`0x80001820` (= −2³¹/tempo24) is rewritten every 16 samples**, twice
  per frame, by `0x4000ac9a` and `0x4000cabc` in `main` — value
  `0xfff49f4a` = −745,654 = −2³¹/2880 ✓ (120 BPM). The tempo reciprocal
  is a per-frame publication, not a set-once word.
- **The live RECORDING SETUP page `0x80000cf4` is re-copied from staging
  every 2 frames** (`0x400208f2`, `main`): `0x01014000 0x00010000
  0x00ffff00` = exactly the twelve bytes above. So a change to those bytes
  in the part reaches the recorder within two frames — the "afresh on
  every arm" the primer describes has the fresh values available on
  every frame, whichever converter consumes them.
- `0x40099680` (open/arm, Bryan's opcode-`0x25` function) at the trig is
  entered from the `0x25` handler with `d0 = 0x80` — 290 entries over the
  run, the rest at load time from `0x40023ad4/aee` and `0x4002585a`.

### 10.10 Who posts opcode `0x25` — settled (run G, 6 Sep 2026, late — measured)

`--watch-pc 0x40000c3c` (the kernel post) with the return address and
stack args logged, step-2 fixture. In the trig window:

```
[1355822.8] post  ret 0x4000533c  queue 0x460d17ce  msg 0x46104d52   <- opcode 0x22, from the arm caller (0x40005304)
[1355823.8] post  ret 0x40006b1c  queue 0x460d17ce  msg 0x46105366   <- opcode 0x25, ONE SAMPLE LATER, same queue
[1355825.0] engine: 0x40085bde (0x22 handler)            ... 152 samples of release/allocate ...
[1355844.2] post  ret 0x400a4dde  queue 0x460d1664  msg 0x400abacb   <- the engine notifies the UI queue mid-handler
[1355975.2] engine: 0x40085c88 (0x25 handler) -> 0x40099680(1, track)
```

So both messages come from the frame builder's own pass, back to back:
the `0x25` is posted through `0x40005c7c`, called at `0x40006b18` inside
the function that runs `0x40006a2c..0x40006c30` — the one that clamps
`0x461053a8[track] = min(computed, 0x461053e8[track])` and copies four
state words (`+276..+288`, two of them `lsll`'d by `a2@(6) − 1`) from the
recorder-buffer record `0x100b14f0 + (128+track)×1096` (Bryan's arena)
into the live record. `0x40005c7c` is therefore "post a recorder command
to the engine" (it also flips `0x800065bc` and notifies `sys` when the
track changes); the queue argument it passes is the engine's, not `sys`'s
as its first `pea` suggested. The engine drains the two in order: `0x22`
(release + allocate) then `0x25` (open/arm, `0x40099680(1, track)`), with
a UI notice in between. Over the whole run the kernel post was called
320×: 176 to `sys`, 112 to `0x460d17ee` (the third engine-side queue),
29 to the UI queue, **3 to the engine's command queue** — the two above
plus one at load.

**Reading (🟡, from the code shape):** `0x22` = "(re)take the buffer",
`0x25` = "arm it with these parameters" — Bryan's opcode names hold.
Whether the `0x25` record carries the length is the next thing to read
(`0x46105366`'s bytes at the post — a `--watch-mem 0x46105366,0x20` run).

**Run I — the `0x25` record itself (measured):** built inside
`0x40005c7c` at `0x40005e08..1c` — `[0x46105366] = 0x25`, word `+2 =
0x0080`, long `+4 = 1` (pending) — and the engine's handler calls
**`0x40099680(1, 0x80)`**: flag 1, **object id 128 = track 0's recorder
buffer** (Bryan's ids 128–135). No length travels in the message; the
length lives in the buffer's state record (`0x100b14f0 + id×1096`, the
`+276..+288` words the frame builder copies at `0x40006ae2..0x40006b02`
just before posting), which is where the `arm()` floor-at-64 Bryan read
would see it. `0x40099680` = Bryan's open/arm ✅ by the call shape.

### 10.11 With a FIXED RLEN the arm caller takes the length path — and a THRU track no-ops at the sample-slot gate (runs H/J, 6 Sep 2026, late — measured)

**❌ RETRACTED 7 Sep 2026 (§10.13):** the measurements stand, both readings do not. The
record at `0x80004f1c` is the track's RECORDER state record, not a sample-slot
record, and bit 7 of the word is the sign of a TIMING byte, not "fixed RLEN" —
the fixture's 128 BPM flipped it, and RLEN 3 at 120 BPM arms exactly as MAX does.

Fixture: the step-2 copy with `recorder-setup … RLEN 3` (display 4) and
`set-tempo 128.0` — Bryan's default clicking case, 128 / RLEN 4 / 1×.
Confirmed in the run: `0x80001820 = 0xfff55556 = −2³¹/3072`, and the trig
lands at frame **1292** = 4 × 322.5 + 2 (344 × 120/128, the quarter-rate
pattern).

**H:** Bryan's trig word `0x46104d26` goes nonzero at 1292 (`0x72fe`,
then `14`/frame) — but **no `0x22` or `0x25` post, no engine handler, and
none of the three converters** ran in 1,600 frames. **J (3,200 frames,
every call site inside the arm caller under `--watch-pc`):** `0x40005ff0`
entered ONCE (`track 0, word 0x72fe`) and hit **`rts` at `0x40006712` in
the same sample with `d0 = −1`**, touching none of its eight call sites.
Nothing staged into `0x800018be..` either.

**Why — the trig word's low byte chooses the path.** At MAX the word was
`0x7257`/`0x7235`/`0x72d2`: low byte bit 7 CLEAR → `tstb %d7 / bgew
0x40006238` at `0x4000607a` is taken, past the slot check, to the branch
that posts `0x22` + `0x25` (§10.8/10.10). With RLEN fixed the word is
`0x72fe`: bit 7 SET → falls through to `0x40006080..a6`, which indexes the
**sample-slot control record** `0x80004f1c + track×84 (+672 by a bit of
`0x80004f18`)` and tests its byte `+2` — **zero for a THRU track**, so
`beqw 0x40006708` → return −1. EXTERNAL.md §6 had this gate from the code
read ("slot-valid … or the whole call no-ops at 0x40006708"); this is it
firing. Only past it comes the length arithmetic (`table[a3@(7)]`, `macl`
with `−[0x80001820]` at `0x400060c0..ca`, the `0x40006dfc` converter and
the `jsr arm` at `0x40006edc`).

So the primer's setup is not incidental: **a Flex machine pointed at the
recorder buffer is what makes that slot record valid**, and a fixed RLEN
needs it; a THRU track with a fixed-RLEN recorder trig arms nothing. (🟡
That THRU tracks cannot use fixed-RLEN recorder trigs on hardware follows
from the code but has not been tried on the unit.) Three FLEX fixtures
(machine type 0, T1 slot byte 128 / 129 / 0 — the encoding of "R1" in the
part's slot byte is unknown) are running to get past the gate and watch
the converter.

### 10.12 The FLEX fixtures no-op at the same gate — because route A never loads a sample (6 Sep 2026, late — measured, and the limit is the emulator's)

**❌ RETRACTED 7 Sep 2026 (§10.13):** no sample was ever the prerequisite. Route A
does not load samples (that measurement holds), but nothing on the recorder path
reads a sample slot; the "sample loader" milestone this section set up is void.

Three fixtures, machine type 0 (FLEX) on T1, slot byte 128 / 129 / 0, RLEN
3, 128 BPM, 1,600 frames each: **identical** to the THRU case — the arm
caller enters once with `0x72fe` and returns −1 at `0x40006712` in the
same sample; no post, no converter. And the decisive number: the
sample-slot control record `0x80004f1c..+84` received **0 writes in every
run, load included** — for all three slot bytes and for the THRU runs
before them.

**Why (measured by reading the tool, not the firmware):** `stage_project`
copies the project's `.work`/`.strd` files onto the emulated card and
**skips every `.wav` and `.ot`** (emu_rtos.py: `p.suffix.lower() not in
(".wav", ".ot")`). Nothing can populate a slot record if no sample exists
to load, and the recorder buffer's own record may need the same
initialisation. The 17 literal readers/writers of `0x80004f1c` include the
candidates `0x4000f5fe` (walks the records at stride 84 and reads a
`+0x23` field), `0x4004c294` (same stride) and `0x400971f6`; none of them
ran. So **the fixed-RLEN arm path is blocked in route A by an unmodelled
prerequisite, not by the fixture** — the same shape as CLAUDE.md's
"a measurement can be structurally blind": the null is real, the
instrument cannot see past it.

**Next (not tonight):** stage the slot-1 sample (`.wav` + `.ot`) on the
emulated card — the FAT16 model's capacity is the first thing to check —
and watch `0x80004f1c` during the load; if the record fills, re-run the
128/RLEN 4 FLEX fixture and the converter question answers itself
(`0x40006dfc` vs `0x4006e3b2`, the `macl` at `0x400060ca`, the `jsr arm`
at `0x40006edc`, and the length word in the buffer's state record). Also
worth one line to Bryan: on hardware, does a fixed-RLEN recorder trig on a
THRU track (no sample slot) record at all? The code says no.


**❌ RETRACTION of §10.12's framing (7 Sep 2026, 00:50, by a raw dump):**
the three "FLEX fixtures" were not FLEX. `ot_project.py machine-type`
takes a **1-based** track and I passed 0, so each call wrote the byte
BEFORE T1's machine-type slot (`+0x2a`, one of a run of three `108`s in
the part record — 108 → 0 or 1, a corruption of unknown effect) and left
T1's own byte untouched. Worse, that byte reads **0 in the cleared
baseline and in every fixture** (`+0x2b..+0x32` = eight zeros), while
§10.1's RAM readback of the same project reported `[2, 2, 0, 0, 0, 0, 0,
1]` — so **the file offset or the encoding of the machine-type byte is
unverified**: either the RAM word is derived at load (from the slot
assignment?) or §10.1's readback location was wrong. What survives from
§10.12: the sample-slot control record got 0 writes in every run, load
included, and the tool stages no samples — that finding does not depend
on the machine type. What does not survive: any statement about FLEX.
The setter now refuses track 0. A run with the slot-1 STATIC sample
actually staged (`--stage-audio`, new) is in flight to see whether the
record fills at all.

**Staged-sample run (7 Sep 2026, 01:00 — measured, and it ends the
night's thread):** the slot-1 STATIC sample (`Didnt U - Bass.wav` + `.ot`,
18 MB, project-local) staged on a 256 MB emulated card via
`--stage-audio`, same 128/RLEN 4 fixture. Card traffic rose by only
~1,085 sectors (32,000 vs 30,915 — directory and FAT, not 18 MB of
audio), the control record `0x80004f1c..+84` still got **0 writes**, none
of the three populator candidates ran, and the arm caller no-op'd at the
same gate. So having the file on the card is not enough: **route A's
LOAD PROJECT does not load samples**, presumably because the sample loader
is a different consumer (the `storage` task, a p2x task, or an on-demand
path after the DSP reports ready — none identified). That is the next
emulator prerequisite, and it is a milestone of its own, not a fixture
tweak: find who loads a slot (the writers of `0x80004f1c+2`, e.g.
`0x4000f5fe`'s stride-84 walk), what wakes it, and whether route A can
reach it. Until then the fixed-RLEN recorder path — and with it the
converter question and Bryan's 128/4 arithmetic in situ — is out of the
emulator's reach. The MAX path (§10.7–10.10) is fully reachable.


### 10.13 The "sample loader" was never the prerequisite: the gate is the track's RECORDER record, bit 7 is a timing sign, and the machine-type values are settled (7 Sep 2026 — measured, with two retractions of §10.11–10.12)

Resumed at §10.12's "find the sample loader". Instrumented before theorising
(the §8 rule): a load-only run watching BOTH banks of the record
(`0x80004f1c..+0x540`, not the 84 bytes every earlier watch covered), the
machine-type bytes of both bank blobs, and every candidate function; then
sequencer runs on fixtures built after reading the firmware's own slot
layout. Driver scripts lived in the session scratchpad (`slotprobe.py`,
`seqprobe.py`); the tool changes are in `tools/ot_project.py`.

**1. The machine-type file offset is right; the "file says 0, RAM says 2"
discrepancy of §10.12's retraction was bank A vs bank B ✅.** After the
load, bank A's blob (`0x400e21e0`) reads `[0,0,0,0,0,0,0,0]` for part 1 —
exactly `bank01.work` — and bank B's blob (`0x4017d520`) reads
`[2,2,0,0,0,0,0,1]`, which is `bank02.work`. §10.1's readback was taken
from bank B while the patch went to bank01. The machine-type writes seen
during the load are all the reset-to-defaults pass (`0x400056a6` /
`0x400209a4`, part init) then the file copy; nothing derives them. (Parts
5–8's RAM rows sit 2 bytes off the `part*0x18b2` formula — the mirror block
has a 2-byte gap; the file offsets the tool writes are unaffected.)

**2. The machine-type VALUES: 0 = STATIC, 1 = FLEX, 4 = PICKUP — by code
and by data ✅, contradicting `PARAM_PAGES.md`'s inferred 0/1 = FLEX/STATIC.**
The trig-side slot lookup `0x400050b8..0x400050fc` sends type 0 to the
STATIC arena (`0x100d5b30 + id×1096`, ids ≤ 128) and types 1 and 4 to the
FLEX arena (`0x100b14f0 + id×1096`, ids ≤ 135, i.e. including the recorder
buffers 128–135); `0x40099374`'s kind 0 / kind 1-or-4 split is the same
pair. And the RIG's bank B carries `128+` values (recorder buffers) in the
type-1 slot byte of T2–T7 and 1..128 values in the type-0 byte — only a
FLEX machine can play a recorder buffer. So every "FLEX fixture" of
§10.12 (type 0) was a STATIC fixture, and the baseline T1 under route A
has been STATIC-on-slot-1 all along.

**3. The per-track slot record is FIVE bytes, indexed by machine type ✅.**
`0x4000504e..0x4000507e`: `blob + part*0x18b2 + track*5 + machine_type +
0x8f04a` (34 literal readers of that base). File offset = part record
`+0x2d3 + 5*track + type`: byte +0 the STATIC slot, +1 the FLEX slot, +4
the PICKUP buffer, which the PICKUP setter `0x400972fc` forces to
`128+track` (own recorder). Slot bytes are 0-based (0 = slot 1, 128 = R1,
the file's `SLOT=129`). `ot_project.py track-slot` had only ever written
byte +0 (the STATIC slot); it now takes `flex|static|pickup`.

**4. `0x80004f1c` is the track's RECORDER state record, not a sample-slot
record ✅ — and nothing on the recorder path needs a sample.** Sixteen
84-byte records: two banks of eight, the bank bit per track in
`0x80004f18`, the OTHER bank being the one written. The writer is the arm
caller itself: word bit 7 clear → `0x40006238` → bit 4 (recorder trig) →
non-PICKUP → `0x40006714` → `0x40006262`/`0x40006268` fill the other
bank's record (header `0x00000101`: byte +2 = **1, pending**; +8 the
INAB/INCD/SRC bytes from the live setup page; +12 the source bits;
sentinels `0xf0000000` at +36..+44) → `0x400066b0` → `0x40005304` (post
`0x22`). The per-frame track function `0x400068e4` (25,600 calls in
1,600 frames = 8 tracks × 2 per frame, from the frame builder
`0x4000d342`/`0x4000d36e`) finds the other bank's state 1, sets it to **2**
and flips the bank bit (`0x400069de`/`0x400069e6`) in the same sample;
from then on the record carries the recording (`0x40007192`/`0x400072be`
counters, `0x40007738` positions). Measured on the FLEX-on-R1 fixture at
MAX: 3 writes of the load's own watch, then the full sequence above at
frame 1379. Every earlier watch of "`0x80004f1c..+84`" was bank 0 / T1
only, so it could not see the pending write (bank 1, `0x800051bc`), and
the ones that reported "0 writes, load included" were correct and blind at
once. What §10.11 called the sample-slot gate at `0x400060a6` is this
record's state byte: the bit-7 path is a follow-up on an EXISTING
recording (it posts through `0x40005c7c` with a length from the FOUT
table `0x400ab63a`, sets state 3 — Bryan's "pickup arm reads the FOUT
slot", EXTERNAL.md §6). The FLEX bind for a NOTE trig (`0x4000f450`,
3 calls from `0x4000d49e`) does fail on this fixture — R1's control
record has length +16 = 0 and pointer +20 = 0 after the load, and an
empty recorder buffer has nothing to play — but that is a separate
mechanism, off the recorder path, and probably what hardware does too.

**5. Bit 7 of the trig word is the SIGN OF A TIMING BYTE, not "fixed
RLEN" ❌ — the fixture's tempo change flipped it.** The word is composed
in the frame builder at `0x4000c99a..0x4000ca7a`: `0x800017d6[32 + 8*sub
+ track]` (the lane's timing byte) `| 0x210` `| (flag word & 0xf000)`.
That byte table is filled every frame at `0x4000aece..0x4000af22`: for
each of 62 lanes, `16 + (now − event_time) × (−1/tempo24)` in EMAC
fractional arithmetic, floored at 0 and truncated to 8 bits — measured
as +8 per frame (2-sample units) counting up toward the lane's scheduled
event. Two fixtures identical but for tempo: RLEN 3 at **120 BPM** → word
`0x7257` (byte `0x47|0x10`, positive), arm caller → `0x40006238` →
`0x40005304`, `0x22` and `0x25` handlers, the record filled, 3,997 record
writes; RLEN MAX at **128 BPM** → `0x72fe` (byte `0xfe|0x10`: the event is
still 4 samples ahead when the word is composed, a frame before the
sequencer's own EVT/FLAG update at `0x400a33f2`/`0x400a3426`), arm caller
→ `0x400060a6` → state 0 → `rts −1`. The 6 Sep fixture had changed BOTH
RLEN and tempo. §10.11's "with a FIXED RLEN the word has bit 7 set" is
withdrawn; §10.7's Sam-trig word `0x72d2` and the RIG's bank-B trig
(`0x72d3`, frame 345 — the same low byte as M6c's `0xd3` live nibble) are
negative too, so under route A those recorder trigs are DROPPED at the
state gate. Whether the unit drops them is the open question of this
section: a recorder trig at 128 BPM on a fresh project records on
hardware (everyone's default), so either the emulator's phase between
the tick-driven scheduler and the frame clock presents negative offsets
the hardware never does for a first trig, or hardware initialises the
record before it (🟡 both open; the falsifier is one emulator run with
`--watch-mem 0x46104d26,2` at each of several tempos on the unit's own
saved trig, against what the unit records at those tempos).

**6. The converter, answered at 120 BPM ✅:** with RLEN fixed the per-frame
site `0x40006dfc` (`d0 × 31,752,000` = 44,100 × 720, `macl` with the tempo
reciprocal, `+1 / asr 1` — samples per step, round-half-up) runs **twice
per frame for the whole recording** (2,443 entries over 1,221 frames);
at MAX it runs 0 times (control, same fixture). `0x4006e3b2`,
`0x40006d48`, `0x400060c4` and `0x40006edc`: 0 in both. The length itself
is not yet settled. The 7,400-frame run (RLEN 3 = display 4, 120 BPM,
trig at 1379) ended with the record still in state 2, its counters at
+24/+28 = `0xc00`, length +32 = 0, and R1's control record `+16` =
**11,025** = 44,100 × 720 / 2880 — the converter's per-step product at 120
BPM BEFORE its `+1 / asr 1` (one 16th is 5,512.5 samples; Bryan's sheet
rounds it to 5,513). No end of recording was seen in ~6,000 frames
(~96,000 samples, against 22,050 for four 16ths), so either the end is
tied to the quarter-rate pattern's own step length (4 × 22,064 = 88,256
samples, which the run should also have passed) or the stop lives in a
state this watch did not cover. 🟡 Next: watch the R1 control record and
the `0x40006dfc` operands per frame, on bank B (344-frame steps) once the
§5 drop is understood.

**7. Route A does not load samples, and it does not matter here (holds).**
`stage_project` still skips `.wav`/`.ot`; the load's 289 `0x40099680`
calls are the reset loops (136 FLEX + 129 STATIC ids from `0x40023a1c`/
`0x40023a38`) plus 24 from `0x4002585a` (one per `[SAMPLE]` entry), and the
card paths formatted are only the project files. The PCM pool init
`0x40096f24` does run (main init and again inside LOAD PROJECT at
`0x400853b8`; `0x46105408` = 1 after the load) and names the eight
recorder buffers, but their control records stay length 0 until a
recording writes them.

**Tools:** `ot_project.py track-slot <proj> <bank> <part> <track> <slot>
[flex|static|pickup]` (default flex); the MTYPE comment corrected. Fixtures
this session (scratchpad, rebuildable): `recproj_fxR1` = RECTRIG + T1 type 1
+ flex slot 129; `_maxR1` = + masks at step 2; `_r3t120` = maxR1 + RLEN 3;
`_maxt128` = maxR1 + 128 BPM; `_fxR1_128r4` = both; `_B_r3` = the cleared
RIG (bank B) + RLEN 3, poked at step 2.


### 10.14 The dropped trig is the emulator's: nothing re-locks the sequencer's step clock to the frame clock under route A, so the timing byte wanders — a compensation lever, and the tempo sweep that found it (7 Sep 2026 — measured)

Asked by §10.13 §5. Three measurements, then the lever.

**The tempo sweep (bank A, FLEX-on-R1, recorder trig on disk at step 2,
RLEN MAX; word = the first nonzero write to `0x46104d26`, arm = whether
`0x40005304` ran):**

| BPM | 100 | 110 | 115 | 120 | 125 | 128 | 135 | 140 |
|---|---|---|---|---|---|---|---|---|
| low byte | `1c` | `91` | `d6` | `57` | `15` | `fe` | `35` | `97` |
| arms | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |

The RIG's own bank B (T1 THRU, the trig poked at step 2): 100 → `10` ✅,
120 → `d3` ❌, 128 → `3e` ✅, 140 → `3d` ✅. Deterministic in tempo and
pattern, spread over the whole byte, and independent of the timer model:
128 BPM with the PIT clock at 240/250/280 MHz (tick 242/233/208 samples)
gives the identical `0x72fe` at the identical frame. So it is not the
timer's phase; it is the sequencer's own clock arithmetic against the frame
clock. The one exact `0x10` (bank B, 100 BPM) is what the byte should
always look like: 16 = "the event is at this frame".

**Where the two clocks meet.** The tick handler advances the step clock
`0x4610757c` by exactly 2,646,000 (= 44,100 × 60, one 1/96 note in
sample×tempo24 units) per tick at `0x400a1ea4`, 27 times in 1,400 frames,
and initialises it from the frame clock once at `0x4009c186`. The frame
builder derives NOW (`0x46104cf0`) from a base `0x46104cf4` plus the frame
counter and nudges the base by 16 per frame at `0x4000ad4a` (301 of 301
frames). The two re-lock sites never ran: the tick-side `0x400a1e92`
(frame base ← step clock) is gated on `0x80000028` bit 0 — the project's
CLOCK RECEIVE bit, which the load sets from the RIG file and
`--internal-clock` then clears — AND on `0x46104ca8` (0 throughout); the
frame-side `0x4000ae7a` (step clock ← frame base, bounded by fields of
the pickup track's per-track record) is gated on `0x80006686`, set only at
`0x400052d4`/`0x4009ba3a`/`0x4009f76c`/`0x400a13c8`, and never fired
(`--watch-pc 0x4000ae66`: 0 hits). With neither running, an event stamped
"step clock − 1 tick + n ticks" at `0x400a33e2` sits anywhere within a tick
of the frame that consumes its flag, and the frame builder's byte
(`16 + 8 × frames-to-event`, truncated to 8 bits) reads negative for about
half of all tempos. Which gate hardware satisfies — the CLOCK RECEIVE path
with a real MIDI clock, `0x46104ca8` from something the DSP or a timer
does, or the `0x80006686` request — is the fidelity question, and it is a
milestone (**M6f, sequencer clock lock**), not a knob. 🟡 Falsifier on the
unit: a recorder trig on the RIG at 120 BPM records (it will); the
emulator's `d3` says it would not.

**Sam's correction (7 Sep 2026, same hour): the unit is SLAVED to the Rytm,
and bank B runs at 121 BPM from its clock.** That is not a detail. The RIG
saves CLOCK RECEIVE set, which is exactly the bit `--internal-clock` clears
— and exactly the gate of the tick-side lock `0x400a1e92`; the other gate,
`0x46104ca8`, is written by the MIDI-clock receiver (`0x4000a21c`/`0x4000a294`
and neighbours, the level-4 framer's tick path). So on the rig the firmware
runs the external-clock lock every tick, and route A has never run the
sequencer in that mode at all: `--internal-clock` is a detour that switches
the lock off, and every sweep above is a measurement of the detour. Two
consequences. (1) The hardware test is not "120 BPM internal": run it as
the rig runs, slaved to the Rytm at 121, and it is not a falsifier of the
table above but the baseline M6f must reproduce. (2) **M6f = model external
MIDI clock** (0xF8 at 24 PPQN into the MIDI UART model, the level-4 framer,
`0x46104ca8` and the lock), run the RIG at 121 BPM with CLOCK RECEIVE as
saved, and read the timing byte — expected `0x10`-ish every time. The
internal-clock lock (whatever holds it on a unit running free) is the
second half of M6f and matters for Bryan if he runs internal; ask him.

**The lever.** `emu_rtos.py --arm-phase-fix` (`Rtos.arm_phase_fix()`): at
the arm caller's entry clear bit 7 of the word when the track's recorder
record is zero in both banks, and log it. Compensation in the
`select_bank_live` sense — it makes the trig arm as if its offset were
non-negative — and it goes when M6f lands. With it, at 128 BPM: MAX → arms
(`0x40005304`, `0x22`, `0x25`, the record filled, converter `0x40006dfc`
0 calls); RLEN 3 (display 4) → arms and `0x40006dfc` runs 1,017 times over
the 508 frames after the trig (2 per frame). **Bryan's 128 / RLEN 4
configuration is now reachable in situ**, one flag, every use printed.


**✅ HARDWARE RESULT (Sam, 7 Sep 2026, internal clock):** two projects
built from RECTRIG and put on the card by Claude — CLOCK RECEIVE off in the
file, tempo fixed in the file (120 / 128), ONE recorder trig on T1 at step 2
(the original step-9 trig removed, since it would have armed a recording of
its own), T2 a FLEX machine on R1 with note trigs at steps 10 and 14, direct
monitoring off so the only sound is T2 playing R1. First pass after loading,
Rytm into inputs A/B: **120 → sound, 128 → sound.** The emulator, on those
exact files, said 120 arms and 128 is dropped (`0x72fe`). So the drop is the
emulator's, on INTERNAL clock — the firmware's internal-clock lock (whatever
holds it on a free-running unit) is what route A lacks, and that is the
first half of M6f, ahead of external MIDI clock. `--arm-phase-fix` stands as
the compensation until then. (Sam's earlier observation on the first cut of
the fixture — "silent until 9/64, then sound" — was the step-9 trig doing
its own job and could not be scored; the test was redesigned in the hour.)

**M6f scoping notes (7 Sep 2026, read, not built — paused, see PLAN):**
MIDI IN is UART0 `0xfc060000` (not modelled; the harness has `0xfc064000`/
`0xfc068000` on INTC sources 27/28, so UART0 is source 26 with the same
`Uart` class and an RX queue). RX ISR `0x400106ec` drains status `+0x04`
bit 0 / data `+0x0c`; for `0xF8` it timestamps with the DMA timer counter
`0xfc07000c` (DTIM0, setup at `0x400a10aa`, unmodelled) into
`0x46c83466` (the interval) before handing the byte to the framer via
`0x460ba97c` → realtime `0x40001900` → table `0x400d2d98` → F8 estimator
`0x40005a48`, which sets `0x46104ca8` itself and needs `0x46c83466` ≤
1,881,600 counts to count the clock as running. PLAY under CLOCK RECEIVE
(`0x4000a214..`) also sets `0x46104ca8`, `0x46104cac = 961`, posts
`0x400d64bf` to sys. So the model is: `Uart` #3 + source 26, a DTIM0
counter at a known rate, an F8 injector every 60/(24·BPM) s, PLAY as
today. Estimated one to two sessions, most of it the timer rate and the
estimator's expectations.


### 10.15 Bryan's 128 / RLEN 4 in situ: the length the firmware writes is his sheet's 20,672, and the recording never ends in the emulator (7 Sep 2026 — measured)

Fixture `recproj_fxR1_128r4` (FLEX on R1, recorder trig on disk at step 2,
RLEN raw 3 = display 4, 128 BPM) with `--arm-phase-fix`, 7,000 frames,
three parallel probes (record fields per frame; call counts + engine
record; the per-track DSP command slot `0x46c80354`).

**The length.** From the arm on, twice per frame, the per-frame track
function calls `0x4000432c(track, slot, len)` (`0x40004352`) and writes
**`0x2860` = 10,336** into R1's control record `+16` (`0x46c938d4`). The
same run at 120 BPM (§10.13 §6) wrote **11,025**. Both are exactly half of
the sample counts Bryan's workbook gives for four 16ths — 20,671.875 →
**20,672** at 128 (round half-up, EXTERNAL.md §8) and 22,050 at 120 — and
this code's sample unit is two samples (the frame builder's timing byte
advances 8 per 16-sample frame, §10.13 §5), so the field is the sheet's
number in 2-sample units. 🟡 The unit is inferred from that rate, not
from a DSP read; the alternative (a half-length recording) would mean a
4-step trig records two steps on hardware, which nobody sees. The
converter is `0x40006dfc` (11,417 calls = 2/frame from the trig to the
end of the run, 0 at MAX), its `+1 / asr 1` the rounding the sheet
describes. **Bryan's arithmetic reproduces in the firmware, at his own
tempo and RLEN.**

**The end does not come.** State stays 2, `+32` stays 0, the position
counters `+24`/`+28` (written at `0x40007192`/`0x400072be`) grow for ~390
frames and then sit at `0xc00` = 3,072 for the remaining 5,300; the
end test at `0x40006e74..0x40006e90` (converter length − `+20` ≤ `+28` +
(16 − timing) + 15) can therefore never pass, the second `0x40005c7c`
post that ends a recording (`0x40006edc`) never happens, and the DSP
command slot `0x46c80354` is never written at all (arm included). The
counter arithmetic at `0x400070f0..0x40007192` walks a block chain in
`d6`-sized blocks against a budget in `sp(64)`; what stops it at two
blocks' worth is not read. 🟡 The likely shape is the §8 rule again: the
recorder's advance is paced by something the DSP reports (the read-back
block, the 168-byte per-track record's `+48/+52`), and route A has no
DSP. The engine side is quiet after the arm: `0x40095a90`/`0x400948cc`
17 calls each (pool init + the arm), `0x40085bde`/`0x40085c88` once,
`0x40005e48` never.

**So, for Bryan:** the length is measured; the end and the loop point are
not reachable until the recorder's position feed is modelled or the DSP
is. That is a fourth prerequisite beside M6f, and it is the one the
click question actually needs: the sub-frame end offset is computed at
`0x40006ea8` (`(d0 & 15) << 12 | 0x11d`) on the frame the end falls in.

### 10.16 The recorder never ended, the length was half, and the trig was dropped, because the EMULATOR halves every fractional multiply: stock Unicorn's ColdFire EMAC is wrong, and the fix retires three findings (7 Sep 2026 — measured)

**Where it started.** §10.15's resume line was "scope the recorder position
feed". Instrumenting the block walk instead of reasoning about it (hooks at
`0x40007178`, every iteration, `tools/scratch`-style driver) showed the
counters advancing **16 per 16-sample frame** — the unit is ONE sample, not
two — and the stall at `0xc00` was not a wait on anything: the walk's block
index estimate at `0x40007138` (`macl pos, sp(56)` → block) returned **1 at
position 0xc00** where the ±1 correction that follows can only fix an
estimate off by one, so "remaining in block" came out 0 and the advance
`d3` was 0 from then on. `sp(56)` is the recorder's block-table reciprocal:

| `0x80003c20 + 16·type` | reciprocal | block (samples) | bytes/sample |
|---|---|---|---|
| 0 | `0x00100000` | `0x800` = 2048 | 3 (mono 24-bit) |
| 1 (this recording) | `0x00200000` | `0x400` = 1024 | 6 (stereo 24-bit) |
| 2 | `0x000aaaab` | `0xc00` = 3072 | 2 |
| 3 | `0x00155556` | `0x600` = 1536 | 4 |

Every reciprocal is **2³¹ / block size**, so the firmware expects `macl` in
fractional mode (`MACSR = 0x20`, EXTERNAL.md §6) to return
`pos × recip >> 31` = `pos / block`. `0xc00 × 0x200000 >> 31 = 3`; the
emulator returned 1 (`>> 32`). The same idiom addresses the PCM pool at
`0x40095c46`, so a `>> 32` EMAC could not play a sample either — this is
not a recorder quirk, it is the arithmetic the whole firmware is written
against.

**Unicorn 2.1.4 measured** (`emu_bringup.emac_selftest`, and two scratch
micro-programs: `movel #0x20,%macsr; macl %d0,%d1,%acc0; movclrl %acc0,%d0`):

| operands | hardware (2³¹/N idiom, Bryan's counts) | stock Unicorn |
|---|---|---|
| `0xc00 × 0x200000` | 3 | **1** |
| `0x800 × 0x200000` | 2 | **1** |
| `127,008,000 × 699,050` (the RLEN 4 @128 converter) | 41,343 → `+1 >> 1` = **20,672** | 20,671 → **10,336** |
| `−0xc00 × 0x200000` | −3 | **0x1ffffe** (unsigned) |
| `macw 0x4000 × 0x4000` (1.15 fractional) | `0x20000000` | **`0x10000000`** |

The cause is in QEMU's `HELPER(macmulf)` (`qemu/target/m68k/helper.c`):
`product = (uint64_t)op1 * op2; product >>= 24;` with `get_macf` taking
`>> 8` — an UNSIGNED product `>> 32`. The MCF5445x's fractional mode is a
SIGNED 1.31 × 1.31 whose 2.62 product is shifted left one bit (the
redundant sign bit) before the upper 40 bits are accumulated, so `ACC[39:8]`
is the product `>> 31` (CFPRM §1.4.2 Figure 1-10 shows the 40-bit extended
product; the firmware's constants say where its top bit sits). The scale
factor is ignored in fractional mode on both. **`tools/unicorn_emac_fractional.patch`**
changes that one function (signed operands, `<< 1`); `scripts/build_unicorn.sh`
builds the m68k-only library into `.venv/lib/unicorn-emac/`, `emu_bringup`
exports `LIBUNICORN_PATH` to it, and `emu_rtos.py` refuses to run on a stock
EMAC unless `--stock-emac`. The build has to be the host's native
architecture: the x86_64 (Rosetta) build with Xcode 26's clang crashed on
its first `emu_start` (unpatched too; deployment target 10.15 and a Debug
build made no difference; the PyPI wheel from SDK 14.2 does not crash), the
native arm64 build passes every row above. 5,617 EMAC-site instructions
execute per sequencer frame (505 sites in the image, hooked and counted over
200 frames), so a Python-side shim was never an option.

**What the fixed EMAC changes, on the same fixtures, with NO `--arm-phase-fix`:**

| fixture | trig word | length written (`0x46c938d4`) | walk | end |
|---|---|---|---|---|
| `fxR1_128r4` (FLEX on R1, RLEN 4, 128 BPM) | `0x7210` — bit 7 CLEAR, armed on its own (§10.14 had it dropped) | **`0x50c0` = 20,672 = Bryan's** (was 10,336) | 16/frame, 21 blocks, no stall | record `+28` = `+32` = 20,672, state 0: **ended** |
| `r3t120` (RLEN 4, 120 BPM) | `0x7210`, armed | **`0x5622` = 22,050** (was 11,025) | same | `+32` = 22,050, ended; the last advance was clamped to 2 samples by the budget — the end lands mid-frame |

**Retractions, all of §10.13–10.15's own:**
- §10.15 "the field is the sheet's number in 2-sample units" — ❌ the unit
  is one sample; the field was half because the converter's `macl` was.
  "Bryan's arithmetic reproduces in the firmware" stands, now without the
  unit story: the firmware writes his 20,672.
- §10.15 "the recorder's position feed / the DSP is the prerequisite for
  the end" — ❌ there is no position feed: the ColdFire paces the recorder
  from its own frame clock (16 samples per call pair, `sp(148) − sp(144)`),
  and the read-back block (`0x80003190`, 8 tracks × 16 samples × L/R) is
  the recorder's AUDIO, not its position. Route A ends the recording with
  no DSP at all; the audio in it is zeros.
- §10.13 "the timing byte advances +8/frame (2-sample units)" and §10.14
  "nothing re-locks the sequencer's step clock to the frame clock, so the
  byte wanders" — ❌ the byte is a fractional EMAC product
  (`0x4000aece..af22`) and advanced 8 because the product was halved; at 16
  per 16-sample frame it is in samples. The tempo sweep under the fixed EMAC
  is below. `--arm-phase-fix` is compensation for an instrument defect and
  is retired (the flag stays, does nothing useful, and is logged if used).
- The M6f framing "model the sequencer clock lock" was built on the wander;
  see the sweep before keeping it.

**What survives untouched:** the record layout (§10.13), the arm caller and
its bit-7 gate, the converter identity `0x40006dfc`, the machine-type
values, the block chain and its allocator (`0x461053a8..e8`, free list
`0x80006920`/`0x8000691c`), the walk's segment list (up to four `(addr,
±len)` pairs per call at `sp(84)`, consumed at `0x400072d6..0x40007360` by
the PICKUP machine's own playback of the buffer — the recording write is
elsewhere).

**The tempo sweep, fixed EMAC, no lever** (bank A step 2, RLEN MAX, the
§10.14 fixtures, 2,200 frames each): **100 ✅ 110 ✅ 115 ✅ 120 ✅ 125 ✅
128 ✅ 135 ✅ 140 ✅** — every trig word `0x7210` (timing byte 16, bit 7
clear), every record in state 2 and counting. §10.14 scored the same eight
files 4/8 with the stock EMAC and hardware scored 120 and 128 both yes; the
emulator now agrees with the unit. **M6f as framed ("model the sequencer
clock lock") loses its premise**: the step-clock/frame-clock re-lock sites
(`0x400a1e92`, `0x4000ae7a`) still never run under route A, and that may
still matter for long-run drift or for the slaved rig, but it is not what
dropped the trigs. Falsifier for the remaining question: a long run (minutes)
comparing the trig frame against `bpm × frames` on the fixed EMAC.

**The end, measured** (`fxR1_128r4`, hooks at the end test `0x40006e8e`,
the sub-frame offset `0x40006ea8`, the end post `0x40006edc`, the arm post
`0x40006b18`; writes to the record's `+32` and the engine opcode
`0x46105366`):
- arm: frame 1291 (sample 913,561.5), engine opcode `0x25` / aux `0x80`,
  `+32` ← 0;
- end: frame 2582 (sample 934,216.5) — 1,291 frames later, with `+28` =
  20,656 = 20,672 − 16 and the frame's 16 still to come: the end test is
  `length − +20 ≤ +28 + (16 − timing) + 15`, i.e. **the end is decided one
  frame early, at frame granularity**, and the end post carries the full
  length (`+32` ← 20,672 through `0x40005c9c`, opcode `0x25` again). R1's
  control record `+16` reads 20,672 at the end.
- the sub-frame end offset at `0x40006ea8` (`(d0 & 15) << 12 | 0x11d` into
  the DSP command slot) **never runs for a FLEX recorder** — it is gated on
  `sp(128)` = PICKUP. So for Bryan's FLEX/recorder case the recording's
  length is exact (20,672) and its END is frame-granular: 20,672 = 1,292 × 16
  happens to be frame-aligned at 128 BPM, 22,050 at 120 is not (= 1,378 × 16
  + 2; the walk's last advance was clamped to 2 by the budget, §10.16 table).
  Where the *loop* restarts against the sequencer's 20,671.875-sample period
  — Bryan's "that 0.1275 samples is the problem" (relayed 7 Sep; our
  arithmetic makes the residue 0.125, ask which his sheet computes) — is the
  playback side, not read yet.

**Drivers** (`tools/scratch/recwalk.py`, `tools/scratch/recend.py`; needs the
fixed EMAC and the `recproj_*` fixtures rebuilt per §10.13's recipe).

#### 10.16.1 A second EMAC defect: MSAC accumulated with the wrong sign, so every trig's sub-frame offset was 0 (7 Sep 2026, later — measured)

Reading the frame builder's inputs for track 0's lane (`tools/scratch`
`fbprobe.py`, hooks at `0x4000aef6`/`0x4000af16`) with the `>> 31` fix in
place gave, in units of sample × tempo24 (tempo24 = 3072):

| frame | frame clock `0x46104cf4` | lookahead `0x46104cf0` | lane event | byte written |
|---|---|---|---|---|
| 1290 | 20,608 × t24 | 20,624 × t24 | **20,623.875** × t24 | 0 |
| 1291 | 20,624 × t24 | 20,640 × t24 | 20,623.875 × t24 | 0x00 (`d2` = 0xaf00) |
| 1293 | | | 41,295.875 × t24 (next event, +20,672) | 0 |

So the clocks are what §10.14 guessed at, now with units: the frame clock
advances `16 × tempo24` per frame (`0x4000ad4a`), the step clock
`0x4610757c` advances 2,646,000 = 44,100 × 60 per **24-PPQN tick**
(`0x400a1ea4`; one tick = 2,646,000 / tempo24 samples, a 16th = 6 ticks =
15,876,000 — the sheet's "samples in 360 beats"), and a lane event is a
step-clock value: exact, fractional in samples (20,623.875 = 4 steps ×
5,167.96875 + the start phase). The byte is `16 + floor((event −
lookahead) / tempo24)` computed by `msacl` (`0x4000aefc`: acc −= d1 × d5,
d5 = −2³¹/tempo24), so an event 0.125 samples before the lookahead gives
16 + floor(−0.125) = **15** = "fire in this frame at sample 15" — and the
emulator produced 0 and 0xaf00. Micro-test (`emac_test4.py`): with the
`>> 31` fix, `msacl` still ADDED its product. Cause: QEMU's `DISAS_INSN(mac)`
tests **opcode bit 8** for MAC-vs-MSAC; on ColdFire (and in every `msac` in
this image: `a001 0900`, `ac01 0900`, `a498 5901`) it is **bit 8 of the
extension word**. `tools/unicorn_emac_fractional.patch` now carries both
changes (`helper.c` and `translate.c`); `emac_selftest` checks `msacl` too
(0xc00 × 0x200000 subtracted → −3). The matrix after the fix matches
hardware's truncation of the guard bits (`floor`) in every row.

**Consequences for what was written above and in §10.13–10.14:** under the
old EMAC the byte was 0 while an event was ahead (a negative product where
hardware has a positive one, masked to 0) and became 16 the frame AFTER the
event passed (a positive product where hardware has −1..−16): every trig
fired at **offset 0 of the following frame**, so "nibble 0 at every tempo"
and "word 0x7210" in §10.16's tables are the emulator's, and the "timing
byte wanders / composed a frame early / negative" reading of §10.13–10.14
was two EMAC defects compounding. The firmware's own arithmetic, read from
the code and now executed correctly, is: **trigs fire at `floor(event)`
samples, events are exact multiples of 15,876,000 / tempo24 samples from
the start phase, and nothing accumulates** — the sub-sample residue never
walks. The measured trig words and the seam runs under the corrected EMAC
follow in §10.16.2.

#### 10.16.2 A third defect, this one the harness's own: the EMAC-with-load shim's trampoline was served STALE, so a shimmed `msacl ..,%acc1` ran as the previous `msacl ..,%acc0` (7 Sep 2026, later still — measured)

With the two Unicorn fixes in, the frame builder's byte was still wrong
(`0xff, 0xef, 0xdf, 0xcf` across the trig frames instead of `0x2f, 0x1f,
0x0f`), and the arm caller dropped every trig at 115/125/128/135/140 with
bit 7 set (`0x72f1`, `0x72bf`, `0x72df`, `0x729f`, `0x72f8`) while 100/110/120
armed (`0x7277`, `0x721d`, `0x7234`). A per-instruction trace of the lane
loop (`tools/scratch/fbtrace.py`) put the corruption at the SECOND `msacl`
of each lane pair: after `msacl %d1,%d5,%a0@+,%d2,%acc0` acc0 read 0x1f
(right), after `msacl %d2,%d5,%a0@+,%d1,%acc1` acc0 read **0x50ef** — acc0
had been changed by an instruction that names acc1. The same two
instructions replayed through the shim in a fresh Uc
(`tools/scratch/emac_shim_replay.py`) are correct. The difference is
history: `emu_bringup._emac_load_shim` executed every shimmed load form
from ONE trampoline address, rewriting its four bytes each time, and in
the long-running emulator Unicorn kept the address's previously translated
block — so the trampoline ran whichever plain form had been translated
there last (here: the acc0 form, with the newly loaded d1 as operand:
`−(0x3c9be80 × −1/3072)` = +20,623.9, + 31.9, + the guard bits → 0x50ef).
`uc.ctl_remove_cache(TRAMP, TRAMP+0x10)` before each run made acc0 stay 0x1f
and the trig word `0x721f` (byte 16 + 15: fires at sample 15, bit 7
clear, ARMED) — proof by removal. The fix that shipped: one trampoline
slot per distinct plain instruction (`r.emac_slots`, 16-byte slots on the
page above emu_rtos's SR trampoline), never rewritten, so nothing can be
stale. Every shimmed EMAC instruction since M6c (≈1,100 per frame: the
frame builder, the mixer's `0x400031a0` loop) executed under this defect,
so every route-A result that passed through a load-form EMAC before this
fix is suspect in its VALUE while still valid in its CONTROL FLOW: M6c's
"same byte 0xd3" gate compared the emulator with itself. The
measurements that follow are the first taken with all three fixes.

#### 10.16.3 With all three fixes: the timing byte is the firmware's arithmetic, sample-exact, no walk (7 Sep 2026 — measured)

`fbprobe.py` on `fxR1_128r4`, track 0's lane, tempo24 = 3072, lane event
20,623.875 samples (in frame-clock units), lookahead = frame clock + 16:

| frame N (builder) | lookahead (samples) | event − lookahead | byte written | dispatcher word in frame N+1 |
|---|---|---|---|---|
| 1289 | 20,592 | +31.875 | `0x2f` (16 + 31) | — |
| 1290 | 20,608 | +15.875 | `0x1f` (16 + 15) | **`0x721f` — fires at sample 15, bit 7 clear, ARMED** |
| 1291 | 20,624 | −0.125 | `0x0f` (16 − 1) | `0x000f` |
| 1293.. | | next event 41,295.875 (+20,672) | `0xaf, 0x9f, 0x8f, 0x7f` = 16 + 175, 159, 143, 127 | — |

So: byte = `16 + floor((event − lookahead) / tempo24)`, consumed one frame
later, bit 4 = "this frame", low nibble = sample offset, **bit 7 is never
set by this arithmetic while an event is within 112 samples** — bit 7 in the
trig word is a flag some other writer sets (the follow-up / one-shot path
the arm caller tests), not a sign. The trig fires at `floor(event)`: the
0.875 residue lands the arm on sample 15 of its frame, and the next event is
exactly 20,672 = 4 × 5,167.96875 later in the lane table (`0x3c9be80 →
0x792bd00`) — the sequencer keeps the fraction and nothing walks. The
retractions in §10.16.1 stand, now measured rather than read.

**The tempo sweep, all three fixes, no lever** (bank A step 2 = 4 steps of
the quarter-rate pattern = 4 × 15,876,000 / tempo24 samples, start phase −48
samples as measured above; 2,200 frames each). Predicted offset =
`floor(4 × 15,876,000 / tempo24 − 48) mod 16`:

| BPM | tempo24 | event (samples) | predicted nibble | trig word | armed |
|---|---|---|---|---|---|
| 100 | 2400 | 26,412.0 | 12 | `0x721c` | ✅ |
| 110 | 2640 | 24,006.545 | 6 | `0x7216` | ✅ |
| 115 | 2760 | 22,960.696 | 0 | `0x7210` | ✅ |
| 120 | 2880 | 22,002.0 | 2 | `0x7212` | ✅ |
| 125 | 3000 | 21,120.0 | 0 | `0x7210` | ✅ |
| 128 | 3072 | 20,623.875 | 15 | `0x721f` | ✅ |
| 135 | 3240 | 19,552.0 | 0 | `0x7210` | ✅ |
| 140 | 3360 | 18,852.0 | 4 | `0x7214` | ✅ |

Eight for eight, and every low nibble is the one the firmware's own
arithmetic predicts. This replaces §10.16's earlier sweep table (all
`0x7210`, taken with the stale trampoline) and closes §10.14's "dropped
trig" for good: hardware 120/128 both record, and so does the emulator, at
the right sample.

#### 10.16.4 The seam, measured: a looping recorder trig at 128 / RLEN 16 leaves a one-sample hole on alternate passes; at 120 / RLEN 16 none (7 Sep 2026 — measured, all three fixes)

Fixture `recproj_loop128_r16`: the §10.15 project with recorder trigs at
steps 2/6/10/14 of the quarter-rate A01 (one trig every 16 sixteenths =
4 × 15,876,000 / tempo24 samples) and RLEN 16 on **part 1** (the tool's
`recorder-setup <proj> 1 1 0 RLEN 15`; part 0 is not the part A01 plays —
a first attempt on part 0 changed nothing). `tools/scratch/recloop.py`,
17,500 frames, hooks on the arm caller, the arm post, the end post and the
record fields.

| | 128 BPM, RLEN 16 (period 82,687.5, Bryan's "first-repeat click") | 120 BPM, RLEN 16 (period 88,200 exact, clean) |
|---|---|---|
| length written (`+32`, end post) | **82,687** = `0x142ff` | **88,200** = `0x15888` |
| trig 1 | frame 1291, offset 15 | frame 1378, offset 2 |
| trig 2 | +5,168 frames, offset 15 → spacing **82,688** | offset 10 → spacing **88,200** |
| trig 3 | offset 14 → spacing **82,687** | offset 2 → 88,200 |
| trig 4 | offset 14 → spacing 82,688 | offset 10 → 88,200 |
| end of pass k vs arm of pass k+1 | +1 sample (hole), 0, +1 | 0, 0, 0 |

Two firmware facts fall out, both measured:

1. **The length converter is not "round half up"; it is round-half-up of a
   product taken with a TRUNCATED reciprocal.** `0x80001820` = ⌊2³¹ /
   tempo24⌋ (699,050 for 3072, exact 699,050.67), so 16 steps at 128 give
   508,032,000 × 699,050 >> 31 = 165,374.77 → 165,374 → `+1 >> 1` =
   **82,687**, where the sheet's arithmetic on the exact quotient 82,687.5
   rounds UP to 82,688. For 4 steps the product is 41,343.69 (exact 41,343.75)
   and still rounds to 20,672, so §10.15's "Bryan's 20,672" stands; his
   128/16 row (and any row whose exact quotient is x.5 or an integer)
   needs the truncated-reciprocal form. Rule: `L = (⌊S × 31,752,000 ×
   ⌊2³¹/tempo24⌋ / 2³¹⌋ + 1) >> 1`.
2. **Trigs fire at ⌊event⌋ with exact fractional events, so successive
   trig spacings are ⌊e_{k+1}⌋ − ⌊e_k⌋ ∈ {⌊P⌋, ⌈P⌉}**, and the seam between
   pass k's end (arm_k + L) and arm_{k+1} is `spacing − L`: with P =
   82,687.5 and L = 82,687 that is 0 or +1 — **a one-sample hole on alternate
   passes**, the first of them at the first repeat; with P integral and L
   = P it is always 0. For Bryan's 128 / RLEN 4 (P = 20,671.875, L =
   20,672) the same rule gives 0 for seven passes and **−1 on the eighth**:
   the next arm arrives one sample BEFORE the running recording's last
   sample. What the engine does with that one-sample overlap is the next
   thing to measure (a 1× pattern with trigs every 4 steps, nine passes;
   the quarter-rate fixture cannot express it).

Bryan's "0.1275 samples" is the residue 0.125 of the 128/4 period seen
once per pass; the firmware does not accumulate it (the events are exact),
it quantises it, and the quantisation lands a whole sample short or long
once every 1/ε passes. That is where the click lives.

#### 10.16.5 The pattern SCALE byte, and Bryan's 128 / RLEN 4 at 1×: seven clean seams, then a one-sample overlap on the eighth (7 Sep 2026 — measured)

**The scale.** The RIG's A01 stepped at quarter rate (§10.7) because of a
per-pattern setting, not the emulator: the PTRN chunk's last eleven bytes
are `len1 sc1 len2 sc2 flag 0 0 0 0 tempo24` (A01: `10 02 40 05 00 … 0b40`,
B01: `40 06 40 02 01 … 0b40`, A02: `10 02 10 02 00 … 0b40`), and rewriting
the SECOND pair from `(0x40, 5)` to `(0x10, 2)` makes A01's step-2 trig fire
at frame 323 instead of 1292 — 1×, 16 steps. So `sc2` is the running
scale with **2 = 1X and 5 = 1/4X**; the menu order `2X 3/2X 1X 3/4X 1/2X
1/4X 1/8X` fits both values and is otherwise inferred 🟡; `len1/sc1` and
the flag (B01 = 1, plausibly PER TRACK mode) are not understood.
`ot_project.py pattern-scale <proj> <bank> <pattern> <len> <scale>` writes
the pair.

**128 / RLEN 4 / 1× — Bryan's case as he plays it** (`recproj_loop1x`:
trigs at steps 2/6/10/14 of a 16-step 1X A01, RLEN 4 on part 1, 128 BPM;
`recloop.py`, 12,600 frames, ten trigs) and the 120 BPM control:

| | 128 BPM (period 20,671.875) | 120 BPM (period 22,050) |
|---|---|---|
| length written, every pass | **20,672** | **22,050** |
| trig offsets | 15 ×8, then 14, 14 | 8, 10, 12, 14, 0, 2, 4, 6, 8, 10 |
| spacings | 20,672 ×7, **20,671**, 20,672 | 22,050 ×9 |
| seam = arm(k+1) − (arm(k) + L) | 0 ×7, **−1**, 0 | 0 ×9 |

Exactly the rule of §10.16.4: the events are exact (`e_k = e_0 + k ×
20,671.875`), each trig fires at `⌊e_k⌋`, so the eighth spacing loses the
accumulated 8 × 0.125 = 1 sample while the recording is always 20,672 —
**the ninth arm lands on the eighth recording's last sample**. On the
ColdFire side nothing special happens: the end post for pass 8 goes out at
frame 10,657 with the full length, the arm for pass 9 at frame 10,658 with
sample offset 14 (word `0x721e`), the normal path (no bit-7 follow-up),
state 2 in the other bank. Which of the two the engine gives sample
170,542 to — the tail of recording 8 or the head of recording 9 — is
decided in the engine's opcode-0x25 handling and the DSP, which route A
does not run; the ColdFire has simply ordered a one-sample overlap. At 4
steps per pass that is **one seam defect every 8 passes = every 2 bars**,
where Bryan hears his click; at 120 the seams are all zero and the buffer
is the period.

The residue (0.125, his "0.1275") therefore does its damage by
accumulating in the sequencer's EXACT event times, which the trig
quantisation releases as one whole sample every 1/ε passes, while the
recorder's length never moves. Clean ⇔ the period is an integer (his
exactness test, with the truncated-reciprocal length of §10.16.4 for the
x.5 cases).

#### 10.16.6 RLEN MAX with a trig every 4 steps: no end post at all, so no seam on the ColdFire side (7 Sep 2026 — measured)

Same 1× fixture, RLEN 64 (MAX), 128 BPM, ten trigs (`recproj_loop1x_max`):
the trigs land where §10.16.5's do (spacings 20,672 ×7, 20,671, 20,672),
the control record gets the MAX buffer length once (`0x98b000`), and **no
end post ever goes out** — each pass is one arm post (opcode 0x25, the
other bank's record) and the running recording's end is the new arm
itself (the per-frame commit parks its position, `0x46c7fe24[track]`, at
the arm's sample offset). With a single event defining both the old end
and the new start there is nothing to be a sample short or long: **MAX +
a recorder trig every N steps is seam-free by construction on the
ColdFire side, at any tempo.** What the engine does with that position is
still the DSP's, but there is no ordering for it to get wrong. This is a
hardware test Bryan can run today: his 128 / RLEN 4 loop with RLEN set to
MAX and the same trigs — if the click goes, fixed-RLEN recordings are the
only place the seam error lives, and a patch that ends a fixed-RLEN
recording at the next arm (or sizes it from the lane's next event) is the
target.

### 10.17 The seam patch: a ColdFire cave that sizes a fixed-RLEN recording from the sequencer's next event (7 Sep 2026 — measured in route A, UNFLASHED)

Sam wants fixed RLEN to stay, so the fix goes where the seam error is
made: the length. `modules/recorder-seam` (`Kind.CF_PATCH`, remix
`seamtest` = `bus` + the cave; 102 bytes, floating, built at `0x400d7200`)
hooks the converter's last three instructions at `0x40006e0c`, replays
them, and then recomputes the length every call as

    s_next = [0x46104cf8] + 16 + floor(([0x80001904 + 4·track] − [0x46104cf0]) × r)
    L'     = s_next − [0x46c7fa84 + 4·track]

with `r = −[0x80001820]` through the same fractional `macl` the frame
builder uses — so `s_next` is exactly where the frame builder will fire
the next step's trig (validated first with a Python model inside the
converter, `tools/scratch/predprobe.py`: it predicts the second arm's
dispatcher sample, 25,839, from every frame of the first pass), and
`[0x46c7fa84]` is the arm sample the firmware stores per track at the
state-1 commit. `L'` replaces the stock `d4` only when `|L' − L| ≤ 1`, so
a recording whose next step is not its re-trig (RLEN shorter than the trig
spacing, a single trig, RLEN MAX never reaches this code) keeps its RLEN.
The converter runs twice per frame for the whole recording and the end
test reads its result, so the substitution is live by the frame the end is
decided — and since the lane holds the next STEP, it holds the re-trig's
step exactly then.

Two things went wrong on the way, both caught by the emulator: the build's
cave verifier assembled with `-mcpu=5407`, which has no EMAC (now `5475`;
`scripts/refhash.sh check` = 26 cases bit-identical), and the first cave
read the track from `164(%sp)` instead of `160(%sp)` (return address 4 +
saved registers 20 + the caller's `sp(136)`), which "worked" — it wrote
20,671 for 300 frames of the first pass and left the eighth seam at −1.

**Measured, patched image (`out/mainos_seamtest.bin`) against the stock
numbers of §10.16.4–5, same fixtures, `recloop.py --image`:**

| fixture | spacings | lengths written | seams |
|---|---|---|---|
| 128 / RLEN 4 / 1×, ten trigs | 20,672 ×7, 20,671, 20,672 | 20,672 ×7, **20,671**, 20,672 | **0 ×9** (stock: −1 on the eighth) |
| 128 / RLEN 16 / ¼×, four trigs | 82,688, 82,687, 82,688 | **82,688, 82,687, 82,688** | **0 ×3** (stock: +1, 0, +1) |
| 120 / RLEN 4 / 1×, ten trigs | 22,050 ×9 | 22,050 ×9 | 0 ×9 (unchanged) |

The recording is now exactly as long as the sequencer's spacing to the
next trig, hole and overlap both gone, and a clean tempo is untouched.

**What would falsify it:** the unit (flash `seamtest`, Bryan's 128 / RLEN
4 loop, the click every two bars); a PER TRACK scale pattern (the lane
index is assumed to be the track — every lane held the same event in the
fixtures); a recorder trig that is not on the next step (the guard must
keep RLEN, and it does by arithmetic but is unmeasured); the first pass
after a pattern change. Drivers: `tools/scratch/recloop.py --image`,
`predprobe.py`, `seamsum.py`.

❌ **Falsified by the first of those, 8 Sep 2026: the unit still clicks
with the cave, and at MAX without it — §10.18.**

### 10.18 The seam cave on Bryan's unit: it still clicks, at MAX too — and route A at AUDIO level says the recorder is sample-exact, so the click is not in the recording (8 Sep 2026 — hardware, then measured)

**Hardware, Bryan T, 7–8 Sep 2026** (`~/Downloads/note-for-bam-seam-flash.md`;
tag 21 = `seamtest`, the cave's 102 bytes verified in the image and the
hook `4eb9 400d 7200` in place; his Moog on the inputs, sound-on-sound;
internal clock, 1×; projects rebuilt from FLASHPLAN's description, not
copied from the card; AUX at 0):

| his test | result | what §10.16–10.17 had said |
|---|---|---|
| 128 / RLEN 4, rec + play trigs every 4 steps (the cave's own fixture) | **clicks**, onset varies run to run, one run around the sixth repeat | seams 0 ×9 with the cave |
| 128 / RLEN 16, one rec + play trig on step 1 | clicks on the first repeat | (a 16-step gap; the ¼× fixture was 4 steps) |
| 128 / RLEN MAX, rec trigs every 4 steps | **clicks** | §10.16.6: "seam-free by construction on the ColdFire side, at any tempo" — no end post, the cave never runs |
| 120 / MAX, same trigs | clean | clean |
| 120 / RLEN 4, same trigs | clean | clean |

❌ **The cave is not the fix, and the length seam is not the click.** The
third row decides it: at MAX there is no converter, no end post and no cave,
and it clicks at 128 and not at 120. Whatever is heard follows the tempo's
non-integer period into a part of the machine the ColdFire's length
arithmetic does not touch. §10.16.4–5 stand as measurements of the
ColdFire's own seam (they are reproduced below, in audio this time); the
claim that removing it removes the click is retracted, and with it the
"handed to Bryan" line of FLASHPLAN tag 19. Whether the cave even took
effect on his track is unknown (the lane index = track assumption is still
unmeasured on hardware) and no longer matters.

**Why every number before this was blind.** `recloop.py` measured
POSITIONS — arm sample, length written, end post. The read-back block the
recorder writes from was zeros in every run ("the audio in it is zeros",
§10.16), so no run had shown what a recording contains or where its first
and last samples come from. `tools/scratch/recaudio.py` fixes that: it
injects a known signal at the point the DSP delivers its frame and reads
the recorder's pool blocks back.

**Where the recorder's input actually is (measured, read hooks on the
mix loop).** Not the 0x80003190 read-back block (that carries the per-track
audio bus both ways: the DSP fills it, the host sends it back to X:0x6400
after processing). The write path reads the **input-capture ring**
`0x80005760 + slot·0x100`, 8 slots of 256 bytes, filled by eDMA ch 7 one
slot per frame (Bryan's §13.3 "channels 1 and 6 as input-capture staging"
was the neighbouring buffers); slot layout = 16 samples × (L, R) 32-bit
left-justified with **A/B at +0x80 and C/D at +0**, and the track reads
slot `(frameclock − (record+20 >> 4)) & 7` (`0x40007578`), eight frames
behind delivery — the recording lags the live input by **128 samples**
(buffer[0] = input time 16·(arm frame − 8) + offset, every pass). The
mix is two EMAC stages: per-source 16-sample gain ramps from the record's
+52/+56/+60 state toward the FIN/FOUT targets (`0x400073b4`–`0x40007438`,
inactive sources ramp 0→0x8000/2³¹ every frame, ≈ −98 dB) into staging
`0x800062cc`, then the fade mix under `MACSR 0xa0` (saturating) and the
6-byte pack. Block address = number × 6144 + 0x40A955E0, 0-based (row entry
14602 is the pool's last block), as Bryan wrote.

**Three defects of the instrument, found because a unity-gain source
vanished from the buffer, all fixed and gated:**

1. `_emac_load_shim` did the parallel load BEFORE the multiply. The chip
   multiplies with the pre-load registers — the pipelined idiom `msacl
   %a0,%d0,%a2@+,%d0,%acc0` depends on it — so every product in the mix
   loop took the next word (the R channel, or the next sample). Fixed:
   the load lands after the trampoline.
2. Unicorn does NOT trap on every MAC-with-load word. Of 122 distinct
   (opcode, extension) pairs in the image it accepts 27 and executes them
   with a made-up effective address (a bare core with every An mapped
   still reads UNMAPPED); two are the mix loop's `a09a 0908`/`a01b 0908`.
   `emu_bringup.native_macload_sites` now classifies every pair on the
   loaded library and `Rtos.install` hooks the accepted ones so they stop
   before executing and go through the shim as if they had trapped.
3. The fractional patch's extraction (`get_macf`) shifted the accumulator
   logically and, under OMC, compared it unsigned: every NEGATIVE result
   under `MACSR 0xa0` "overflowed" and saturated to 0 — a recorded buffer
   lost its negative half-waves. Fixed in
   `tools/unicorn_emac_fractional.patch` (arithmetic shift, signed compare,
   saturate to the sign), a fourth case in `emac_selftest`, and the library
   must be rebuilt (`make emu-unicorn`). The runs below sidestep it with a
   non-negative counter; the shared library on this machine is still the
   old one and now FAILS the selftest, deliberately.

Gates after 1 and 2: the M6a oracle (8 compared fields agree; the 34
resume-PC notes are the same ones an unpatched control run shows against
the golden — burst-boundary jitter in the pool-clear loop), the M6c
frame-mode oracle (5 fields agree), and the recorder numbers themselves
(length 0x50c0 = 20,672; the arm spacings of §10.16.5).

**The measurement** (`make_seam_fixtures.py` from the RECTRIG backup with
its own step-9 REC trig cleared — it had put an arm every 3 and 1 steps
into the first ten-pass run; SEAMTEST geometry: T1 REC1 at 2/6/10/14,
T2 FLEX-on-R1 with play trigs at the same steps; stock image; 12,600
frames = ten passes; `recaudio.py` snapshots the buffer at every arm,
`recaudio_seams.py` decodes the counter):

| fixture | input time at buffer[0], pass to pass | sub-frame slot of buffer[0] | vs §10.16.5's sequencer spacings |
|---|---|---|---|
| 128 / RLEN 4 | **20,672 ×7, then 20,671** | 15 ×8, then 14 | identical |
| 128 / RLEN MAX | **20,672 ×7, then 20,671** | 15 ×8, then 14 | identical (the same starts; no length to be wrong) |
| 120 / RLEN 4 | **22,050 ×9** | 8, 10, 12, 14, 0, 2, 4, 6, 8 | identical |

Within a pass the buffer is a sample-continuous copy of the input (steps
of +1 in the counter at every one of 20,672 positions, both tempos). At a
seam-0 pass boundary the last sample of pass k and the first of pass k+1
are consecutive input samples (13,630 → 13,631). At the −1 boundary (pass
8 → 9 at 128) **input sample 6,590 is recorded twice**: as pass 8's
position 20,671 and as pass 9's position 0 — the §10.16.5 overlap, now
seen in audio. That is the whole of the recording-side seam: one input
sample captured twice every 8 passes at a fixed RLEN, nothing at MAX
(the recording ends at the arm), nothing at 120.

**So the click is not in what the recorder writes.** A one-sample
duplicate every two bars is not what Bryan describes, MAX has none and
clicks, and 120 has none and is clean — consistent so far; but the
recording is the only half route A can see. The play side — what the
FLEX reads when its retrig arrives ⌊P⌋ or ⌈P⌉ samples after the last one
against a buffer of a fixed or just-ended length, and whether the hard cut
lands on one sample or on a frame — is where the tempo dependence has to
be, and **no voice ever starts under route A or the C++ port** (the trig →
voice path is unlocated; COLDFIRE_PORT O9b), so the outbound audio block
shows the input thru and nothing played. This driver is the recorder half
of O10; the play half needs either that path or a hardware capture of
the played output across a 128 BPM retrig.

**What would falsify this section:** a hardware recording (record, STOP,
play the buffer looped, no live writer) that clicks at 128 — then the
recording itself is wrong in a way this injection cannot show (the DSP's
input path, or the sub-frame split at 15/16 that route A runs but hardware
might not); a route A run with the rebuilt library and a signed signal
whose buffer differs from these; or Bryan's flex not being retrigged at
all in test 3 (then the reader is free-running and §6's frame-phase band
model is the candidate again — its 128/4 prediction was "seams from pass
5 to ~123, then clean", and his onset "around the sixth repeat" fits it).
Two questions for him cost nothing: does the click STOP after about a
minute, and what was trigged on the flex in the MAX test.

**Both answered (Bryan T, 8 Sep 2026, evening, via Sam):** *"REC trigs and
PLAY trigs on the same steps. I usually have both on 1, but tested
2/6/10/14. Clicking definitely does not stop. Once it is in the buffer it
is always in it."* He offers his sound-on-sound project file.

- ✅ **The flex IS retrigged, and on the same step the recorder arms, in
  every test including MAX.** The "flex not retrigged at all in test 3"
  escape above is closed: the reader is not free-running, so the play
  retrig arrives on the same step as the arm and the two heads start the
  pass together (d ≈ 0, ±the order in which the two trigs are serviced).
- 🟡 **"Does not stop" cannot separate the two candidates in HIS patch.**
  Sound-on-sound re-records the buffer's own playback (his wording — "once
  it is in the buffer" — says the feedback exists; the SRC3/INAB settings
  that make it so are in the project file, not yet seen). Any play-side
  discontinuity the first band pass produces is captured into the next
  layer and plays for as long as the feedback holds it, so the band
  model's "seams 5–123, then clean" would ALSO sound like it never stops.
  The discriminator is a recording with **no live writer**: record ONE
  pass at 128/RLEN 4, remove the REC trig, keep the PLAY trig every 4
  steps — clicks or not; then remove the PLAY trig too (LOOP on, free
  loop) — clicks or not. Clean/clicks/clean splits recording content from
  the retrig from the loop point. **Asked, 8 Sep 2026 (evening, via
  Sam); answer pending.**
- **The project file is the fixture.** The port now renders a FLEX voice
  sample-exactly from the card (COLDFIRE_PORT O10), so his project loads
  as-is (`ot_emu`, `emu_card`) and the recorder loop under the port can
  run his exact patch — SRC3, AB/CD, LOOP, QREC and the recorder buffer's
  timestretch attribute included — with a known tone in and the played
  output watched at the retrig, which is the half route A could not see.
  The timestretch attribute is worth reading first: at 120 the buffer
  length is an exact tempo multiple and at 128 it is not (🟡 a candidate
  only; nothing measured).

Drivers: `tools/scratch/recaudio.py` (`--reg-probe`, `--read-probe`,
`--field-probe` are the instruments that found the three defects),
`recaudio_seams.py`, `recaudio_analyse.py`, `make_seam_fixtures.py`
(`--self` puts the play trigs on T1, `--ab N` sets the AB level — which
measured as having no effect on the recorded level at 0, 64 or 127).

### 10.19 Bryan's project, firmware, spreadsheet and primer arrive; his own arithmetic already predicts every hardware result we have (9 Sep 2026)

**Received (`~/Downloads`):** his working project (`PROJECT 260908`) and the
exact firmware he ran it on (`to_bam.zip`), plus his companion documents
`octatrack_clickless_loops.xlsx` and `octatrack_sound_on_sound_primer.pdf`
(revision 5 Sep 2026).

**Firmware:** the `.bin` decodes (`tools/bin_decode.py`, then a small
standalone depacker against `vendor/elektron-firmware-tool`'s
`ap_depack`/`ELEK_SECT_OFF` — the tool's own `-d` needs SysEx framing our
bare container lacks) to a 1,112,560-byte MAIN OS section carrying
`BusDelay22`/`BusVerb22` — **build tag 22**, confirmed against the filename.

**Project (`ot_project.py`'s own offset tables, read-only):** bank A part 1,
T1 only is live — FLEX on slot 129 (R1, self-referencing: it plays its own
recorder buffer), `INAB=2 INCD=0 RLEN=15 TRIG=0 SRC3=1 LOOP=0`, one trig at
step 1 carrying masks `0x00/0x20/0x28/0x30` together (his "I usually have
both on 1" from §10.18's answers). Pattern LEN=16, SCALE=1X (one bar),
saved at 120.0 BPM (confirmed by Bryan directly). This project is a shared
base for us to work from, not a test case — Bryan confirmed it does not
click, consistent with prediction (RLEN 16 at 120 BPM is 88,200 samples,
exact — one of the bar-length-clean tempos in his own Bar Lengths sheet).

**His spreadsheet and primer, read directly.** Three sheets — Clean
Combinations (5,279 clean BPM/RLEN pairs, 30–300 BPM x RLEN 2–64), Golden
BPMs (60 tempos clean at every RLEN 2–64), Bar Lengths (86 tempos clean at
16/32/64 trigs) — all built from the identical condition our own arithmetic
uses: `RLEN x 15,876,000` must divide evenly by `tempo24`. His Calculator
sheet checks any BPM/RLEN pair directly and reports CLEAN or `NOT CLEAN -
will click`. His primer (page 5) states outright that 128 BPM "has no
clean one-bar loop at all" and that 120/160/200 are clean at bar lengths
but not at every RLEN.

✅ **Every hardware result in hand is already predicted by this arithmetic
— nothing here contradicts anything.** note-for-bam-seam-flash.md's five
tests: 128/RLEN4 (his Calculator: NOT CLEAN) clicks; 128/RLEN16 (no clean
one-bar length at 128 exists) clicks; 128/RLEN MAX with trigs every 4 steps
(same as RLEN4 arithmetic, NOT CLEAN) clicks; 120/RLEN MAX and 120/RLEN4
(both an integer sample count at 120 BPM) are clean. Bryan's own message —
"I get clicks with combos I predict won't work" — is him confirming his
calculator's `NOT CLEAN` predictions match hardware, not reporting a
predicted-clean combo that clicked. There is no falsifier here, of his
model or of the port's O10 arithmetic (the two share the same underlying
condition).

**Attempted: run his exact project through the C++ port with his exact
firmware, to see WHERE in the signal path a known-clicking combo actually
breaks.** `tools/ot_emu` was rebuilt clean (a peer session held the shared
checkout on `coldfire-o12b-reverb`, so this work moved to its own worktree)
and `stage_card.py` staged his project unmodified. Result: silent on every
track (`o10_recloop.track_audio`, all zero over 48,000 samples) — not
explained by a missing `--main-level` (O9b's root cause A; added, still
silent) and not diagnosable from `FW_TRIG_WORDS` (reads 0 in every run
tried, including ones that plainly did record audio — stale for tag 22,
the "instrument blind to the thing it's checking" trap again).

**Harness validated against a known-good fixture — and a real gap found in
the validation itself.** `make_seam_fixtures.py`'s `r4_128` (steps 2/6/10/14,
same firmware, same command line) DOES record and play audio (T1/T2 both
~47.6–47.8k/48,000 samples nonzero) — so the command line is right and
Bryan's silence is not a flag-mistake. But a control built to isolate "does
a step-1 trig fire" — `r4_128` with its trigs moved to step 1 only, nothing
else changed — came back with bit-identical nonzero counts to the
unmodified step-2/6/10/14 fixture (47,561 and 47,795, exactly, both tracks).
Two different on-disk trig patterns cannot legitimately produce the exact
same sample-accurate result; the run's own log line — `sequencer : playing
bank 1 pattern 0 (re-selected through the load's own last step)` — says the
port does not necessarily start stepping from step 1 at transport start, so
a short run (3,000 frames, under one loop pass at either tempo) cannot be
trusted to have exercised the trig at all. Separately, the primer's own
description of a step-1 REC+PLAY loop — "there's an implicit 16-trig
delay... the audio always lands on step 1 of the next cycle" — means any
future run also needs to cover at least two full loop passes before a
played-back click could show up at all, on top of that starting-step
question. **Neither is resolved. Stopping here for review rather than
guessing further.**

**What's actually open, now that the arithmetic side is settled:** the
port needs to run long enough, and from a known starting step, to show
WHERE a combo already known to click (e.g. 128/RLEN4) actually breaks —
the recorder's own write, or the FLEX voice's retrigger reading it. That is
work on our side; no further data is needed from Bryan for it.

Artifacts (this session's worktree, not yet committed to a branch): staged
card images and a MAIN-OS depacker (`out/depack_elek.c`, wants folding into
`tools/` proper if this path gets reused — it duplicates none of
`elektron-firmware-tool`'s logic, just calls its `ap_depack` on a bare ELUP
payload the tool's own `-d` refuses without SysEx framing).

### 10.21 The "wrong starting step" theory is wrong, and what it was covering for is bigger: `o10_recloop.track_audio` cannot tell a recorder loop from live pass-through (9 Sep 2026)

**§10.19's control test, redone with the right label.** `--sequencer`'s
"re-selected through the load's own last step" message is about which BANK
and PATTERN the firmware selects on load (§8.3, unrelated to which step the
sequencer starts stepping from) — not about trig position. That theory is
dropped. The actual anomaly (moving `r4_128`'s trigs from steps 2/6/10/14
to step 1 produced identical output) needed a different explanation, so it
got one: a byte-for-byte diff of the two runs' `track_audio` output shows
**48,000/48,000 samples identical, both tracks, no exceptions.** Two
genuinely different on-disk trig patterns, staged into genuinely different
card images (confirmed with `cmp`), produced the exact same output. The
trig step is not the variable that matters here; something about what
`track_audio` measures is.

**Decisive test: a burst-then-silence probe instead of a continuous tone.**
A continuous test tone (route A's `--audio-in tones`, and O10's own 1500 Hz
fixture) cannot distinguish "the recorder captured this and is looping it
back" from "the track is just passing its live input straight through" —
both look identical on a periodic signal. Built a 4-channel WAV
(`out/make_burst_wav.py`): each RX0 slot gets its own tone for the first
2,000 samples, then silence for the next 128,000. Ran `make_seam_fixtures.py`'s
known-good `r4_128` (REC/PLAY trigs on 2/6/10/14, 128 BPM, RLEN 4 — the
same fixture COLDFIRE_PORT O10 used to claim "sample-continuous for 32
passes") for 8,200 frames (>6 loop passes) with this probe instead of tones.

**T1 and T2 both receive the burst once, at the start, and are silent at
every subsequent loop boundary through 6 full passes** (`out/check_burst.py`):
nonzero content in the first 2,200 samples of pass 1 only; zero nonzero
samples in the equivalent window of passes 2 through 7, and zero everywhere
else. If the FLEX voice on either track were actually reading back a
recorded loop, the burst would reappear once per pass (RLEN 4 = 20,672
samples here) for as long as the recording holds it — sound-on-sound is the
whole point of the fixture. It does not. What `track_audio` shows is
consistent with **live input monitoring passed straight to the track's
output, not a played-back recording** — and a continuous tone cannot tell
the two apart, which is what let O10's "sample-continuous" result stand
unquestioned.

**This does not yet mean the recorder doesn't work under the port** — it
means the specific observable used to claim it does (`o10_recloop.
track_audio`, a per-track host-port audio record) cannot distinguish the
two, and every prior "continuity" measurement built on it (O10's kick fit,
the 128/RLEN4/RLEN16/RLEN MAX/120 sample-exact claims, §10.19's silence on
Bryan's own project) needs re-reading in that light. `FW_TRIG_WORDS`
(`0x46104d26`) and the recorder state record (`0x80004f1c`, per route A)
both read zero writes even during this run's live first pass, on a
`--watch-mem` check spanning the full 16-record table — consistent with
those being stale addresses for build tag 22 (the same address-drift this
project has hit repeatedly), not with anything meaningful about the
recorder's state.

**What would settle it:** find the ACTUAL recorder pool buffer content in
ColdFire address space (route A's `POOL_ROWS`/`POOL_BASE`,
`0x46c2e9c0`/`0x40A955E0`, `docs/RTOS_FORK.md` §10.18) for tag 22's build,
and read it directly with a range dump after the run — not a single-word
`--peek`, which the tool only supports pre-`--sequencer`. If the burst
shows up THERE, the recorder captured it and the gap is purely in reading
the FLEX voice's output; if it doesn't, the recorder itself isn't writing
under this configuration, which would be a materially different finding
than any click investigation to date. Not yet attempted — flagging before
going further, since this reframes what O10 actually established.

Drivers: `out/make_burst_wav.py`, `out/check_burst.py` (both in this
session's worktree, not yet moved into `tools/scratch/`).

### 10.22 `--mem-dump` added to the port; three independent checks converge on no recorded audio anywhere in the pool (9 Sep 2026)

**New tool capability.** `tools/ot_emu/main.cpp` gets `--mem-dump
"addr,len=path[;...]"` — raw ColdFire memory ranges to files, taken at the
very end of the run. `--peek` only supports one word and only fires before
`--sequencer` runs; nothing existing could read the recorder pool's actual
content after a run. Built, tested, works (confirmed against `r4_128`'s
pool rows and blocks below). Not yet moved out of this worktree.

**Three checks, same fixture (`r4_128`, known-good per O10, burst probe
instead of a tone, 2,600 frames / 6+ loop passes), three different
mechanisms, one answer:**

1. **The track's own output (§10.21):** the burst is heard once and never
   again at any loop boundary.
2. **The pool's block-assignment table** (route A's `POOL_ROWS =
   0x46c2e9c0`, ten rows of 14,602 halfword block numbers, `--watch-mem` on
   row 2 = track 0's row per `recaudio.py`'s own `track + 2` convention):
   the only writes in the whole run are a single batch of ALL ZEROS at
   sample 7,872 — never a real block number. Rows 0, 2, 3, 4 and 5's FINAL
   content (`--mem-dump`) are plain descending sequences 690 apart
   (14602→14583 for row 2, 13912→13893 for row 3, …) — a static per-track
   free-list partition set up once, not something that changes with
   recording activity. Row 1 is all zero.
3. **The blocks that list points at** (route A's `POOL_BASE = 0x40A955E0`,
   block N at `POOL_BASE + N*6144`): dumped blocks 14602, 14601 and 14583
   — **all 6,144 bytes zero, in all three.** No audio content anywhere in
   the region row 2 names.

**Converging on: under this configuration, in this port, no evidence of
captured audio exists anywhere in the recorder's own data structures** —
not "the wrong observable," but nothing to observe. This is a stronger
claim than §10.21's, and the honest caveat is the same shape as every
address-based check in this section: `row = track + 2` is `recaudio.py`'s
own convention for a DIFFERENT build (route A's Unicorn emulator, not tag
22's tables in the C++ port), unconfirmed here — if the row/track mapping
is wrong, blocks 14602/14601/14583 belong to some OTHER track or to
nothing, and the negative result proves less than it looks like. What
would close that gap: watch a MUCH wider span of the pool (dozens of
blocks) for any nonzero write at all, not just the three blocks one
assumed mapping points to — not yet done, the per-write overhead makes a
wide watch slow and this stopped here for review.

**If this holds up, it moves the bar for the whole recorder-click
investigation**: before asking "does a known-clicking BPM/RLEN combo click
because of the recorder's write side or the FLEX voice's retrigger," the
port first needs to show the recorder writing ANY audio at all, under ANY
configuration — which no measurement in this document has yet directly
shown (every prior "sample-continuous" result used a signal a live
pass-through would reproduce identically).

### 10.23 The wide scan: zero of 585 sampled blocks across the whole pool carry any content, and the free-list bookkeeping shows no sign of ever being touched (9 Sep 2026)

**`--watch-mem` does not scale to a wide range — a real failure mode, not
just slow.** Watching the full ten-row block-assignment table (292,040
bytes) logs every matching write into an in-memory vector with no cap;
over a 2,600-frame run this grew unbounded and the process died silently
(no fault message, a 39 MB log of unrelated printf output, no completion
line) rather than finishing. `--mem-dump` has no such cost — it reads final
state once, with no per-write logging — so the wide scan used that
instead: the full row table (285 KB, one dump) plus the first 64 bytes of
every 25th block across the entire 14,602-block pool (585 blocks, ~4%
sampled but evenly spread), all in one normal-speed run (`out/
make_scan_spec.py` builds the `--mem-dump` argument; `out/run_widescan.sh`
works around this session's sandbox flagging a `$(...)`-substituted
command as too complex to verify).

**Zero of 585 sampled blocks carry any nonzero byte, anywhere in the
pool.** And the full row table resolves the structure cleanly: row 0 is a
single large ascending free list (1, 2, 3, … up to 8,937 entries) — the
general STATIC/FLEX sample pool, not per-track; row 1 is entirely empty;
**rows 2–9 are the eight audio tracks**, each a ~689-entry descending list
spaced exactly 690 apart (row 2: 14602→13914, row 3: 13912→13224, … row 9:
9772→9084) — a static partition of the pool's top end, one reserved chunk
per track. Every one of the eight track rows is **completely intact and
undisturbed** at the end of a 2,600-frame run that included a live REC arm
and an audible input burst: no entries missing, none reordered, nothing
consumed. A recorder that had captured even one block's worth of audio
would show that block's number gone from its row's free list. None is.

**This closes the gap §10.22 left open.** The `row = track + 2` mapping
from `recaudio.py` (a different build, a different emulator) is no longer
load-bearing — every track's row is visible and every one shows the same
untouched pattern, so the finding does not depend on having picked the
right track. Combined with §10.21's burst-probe (the track's own output
never loops the burst back) and §10.22's three-block spot check, this is
now three independent methods, at increasing scope, all agreeing: **under
this port, on this build, with this project, no recorded audio exists
anywhere in the recorder's own pool — the free lists never move.**

**What this does and doesn't say.** It does not mean the ColdFire firmware
can't record — note-for-bam-seam-flash.md is hardware, and hardware
clicks, which requires something to have been recorded and played back.
It means either (a) the port's DSP-side or ColdFire-side recorder-arm path
has a real gap that stops audio ever reaching this pool, or (b) the
`POOL_ROWS`/`POOL_BASE` addresses (route A's, for a different build) are
wrong for tag 22 and the real pool lives elsewhere entirely — structurally
the same address-drift problem this project has hit repeatedly, but this
time the STRUCTURE read out (eight evenly-spaced per-track rows, a general
pool, a spare) fits the expected shape well enough that a wrong location
for the whole table seems the less likely of the two. Either way, the
recorder-click investigation cannot proceed to "where does a known-clicking
combo break" until one of these is resolved — the port needs to be shown
recording SOMETHING, under ANY configuration, before it can be trusted to
show where a click comes from.

Drivers: `out/make_scan_spec.py`, `out/run_widescan.sh`, `out/scan_results.py`
(session worktree, not yet moved into `tools/scratch/`).

### 10.24 Localized: the frame builder's own recorder-check pass never runs, not just one track's arm (9 Sep 2026)

**Why: same section, why not.** §10.23 left it open whether §10.22's
`--watch-pc` result (armcall/armpost/endpost at `0x40005ff0`/`0x40006b18`/
`0x40006edc`, zero hits) meant anything, since those addresses came from
route A's `recaudio.py` (a different build). Settled by disassembling them
directly out of Bryan's own tag-22 image (`scripts/disasm.sh emac`, which
uses `objdump -m m68k:cfv4e` — plain `r2` cannot decode this ISA, see the
script's own warning): all three are genuine, coherent, semantically
correct code. `0x40005ff0` reads a track's machine-type byte at file
offset `0x8eda2` (`ot_project.py`'s own formula) and compares it to `4`
(PICKUP). `0x40006edc` loads the reciprocal table at `0x80003c20` and
clamps against **14602** — the pool size itself, in the instruction
stream. These are not stale addresses.

**Traced one level further, into §10.10's already-documented mechanism**
(RTOS_FORK §10.10, measured under route A, 6 Sep 2026): opcode `0x22`
("take the buffer") is posted from `0x40005304` — disassembled here, it
writes the literal byte `0x22` to `0x46104d52`, exactly the message
address that section names. Opcode `0x25` ("arm it") is posted via a `jsr`
at `0x40006b18` inside a function starting at `0x40006a2c`, described
there as running "from the frame builder's own pass" every frame, for
every track. Watched all of `0x40005304`, `0x40006a2c`, `0x40005c7c` (the
shared poster both call into) and `0x400a1030` (the bank/pattern selector,
as a sanity check that watch-pc itself works) across the same 2,600-frame
burst-probe run.

**Only `0x400a1030` ever fires — six times, all bank/pattern-select
housekeeping. Zero hits on the other three, across the entire run.** Not
"this track's arm never happens" — **the frame builder's own per-frame
recorder-check pass, the function every track's arm or non-arm decision
runs through, is never entered at all**, despite a live REC1 trig at step
2 and 2,600 frames (many multiples of however often this pass is meant to
run). This is upstream of anything track-specific: whatever decides
whether to even look at a track's recorder state each frame is not
running under `--sequencer --dsp` for this fixture.

**Not yet found: what calls `0x40006a2c`, and what gates it.** It is not
a `jsr`/`bsr` target anywhere in the immediately surrounding disassembly
(`scripts/disasm.sh emac 0x40006800 800`) — finding the caller means
either a full disassembly pass over the image or a route-A trace of the
same call chain to compare against. Stopping here for review: this is a
firmly localized "the door is never opened" finding, one level short of
"and here is why."

### 10.25 The right arm-caller address, confirmed by measurement to be reached under route A for FLEX — never fires under the port, at any tempo tested (9 Sep 2026)

**First pass found the wrong function.** `0x4000672c`/`0x40006a2c`
(disassembled, real code, gated on machine type == 4/PICKUP) looked like
the arm caller, but §10.13 (7 Sep, already in this document) had already
identified and measured the real one: **`0x40006238`**, entered via
`tstb %d7 / bgew 0x40006238` at `0x4000607c`, which branches to the
non-PICKUP path (`0x40006714`) for FLEX and PICKUP alike. `0x4000672c` is
a different, later mechanism — §10.13's own text names it: "the bit-7 path
is a follow-up on an EXISTING recording... Bryan's pickup arm reads the
FOUT slot", PICKUP-only by design, not the one Bryan's FLEX fixtures use.
Disassembled `0x40006238` directly out of Bryan's tag-22 image: matches
§10.13's description byte for byte (`btst #4,%d7`, the `0x00000101`
header write at `0x40006274`, all present).

**§10.14 (also already in this document, 7 Sep) raised the obvious
alternative explanation, and it's now ruled out.** That section documents
a real, understood emulator artifact: under `--internal-clock`, the
sequencer's step clock and frame clock never re-lock, so a composed
timing byte reads negative at roughly half of all tempos, and the arm
caller gets skipped — 128 BPM is explicitly one of the affected tempos in
its own sweep, while 120 BPM is not, and hardware records fine at both
(confirmed on real Rytm audio, 7 Sep). Every fixture run tonight was
128 BPM. So the obvious question was: is tonight's whole "never arms"
result just this same known, already-fixed (route A has
`--arm-phase-fix`) artifact, applied to a new emulator that doesn't have
the lever yet?

**No.** Re-ran the burst probe and the `--watch-pc 0x40006238` check on
`r4_120` (RLEN 4, 120 BPM, the tempo §10.14's own sweep confirms arms) —
**zero hits, and the burst still plays once and never loops back**,
identical to 128 BPM. The tempo-dependent artifact is not the explanation;
if it were, 120 BPM would have armed like it does under route A.

**Narrowed further, and this part is a real, working result.** Watched
`0x400068e4`, the per-frame per-track function §10.13 measured at 25,600
calls over 1,600 frames under route A (8 tracks × 2/frame): **41,600 hits
over 2,600 frames — exactly 16 per frame, the same rate.** The general
per-frame track dispatcher runs correctly under this port. The gap is not
"frames don't process tracks"; it is specifically that whatever composes
the per-track trig word's bit 4 (recorder-trig flag) and sign (the byte
`bgew 0x40006238` tests) never produces a value that lets the arm caller
through, for this project's on-disk REC1 trig, at any tempo tried.

**Where this leaves it.** The lane/trig-word composition code
(`0x4000aece..0x4000af22` per §10.13 §5, filling `0x800017d6[...]` from
each of 62 "lanes") is the next thing to watch — not yet done. Everything
upstream of it (frame delivery, the per-frame track loop, the arm caller's
own code) is confirmed present and running; everything at or after it
(the arm caller onward) is confirmed never reached. The trig-word
composition is the remaining unmeasured link between the two.

### 10.26 §10.25's ruling-out may be premature: `tools/ot_emu` has no clock-lock modeling of any kind — not even the compensation §10.14 gave route A (9 Sep 2026 — read, not measured)

Checked before spending more session time on the lane-table trace §10.25
left open. `grep` across `tools/ot_emu/*.cpp`/`*.h` for `arm_phase`,
`internal_clock`, `clock_receive`, and the three literal addresses §10.14
names for the tick/frame-clock relock (`0x400a1ea4`, `0x4009c186`,
`0x4000ad4a`): **zero matches.** `--arm-phase-fix` exists only in
`tools/emu_rtos.py` (route A); the C++ port §10.21–§10.25 have been
running against (`tools/ot_emu`) has neither the bug's compensation nor,
so far as grep can show, a name-recognisable model of the MIDI-clock lock
M6f scoped. It has its own low-level `tickTimers`/PIT model (`rtos.cpp`),
which is a different layer — that runs the kernel's 5 ms tick correctly
(M6c's own gate), but is not the same thing as the sequencer-level
step-clock/frame-clock relock §10.14 traced.

**Why this matters for §10.25's "No."** That section ruled out the
§10.14 artifact by testing 120 BPM *under this same port* and getting the
identical zero-hit result to 128 BPM — correct as a statement about this
port (tempo doesn't distinguish the two here), but it does not rule out
the *same category* of bug: a port with no clock-lock modeling at all
would produce a composed timing byte that is wrong at every tempo, not
just the ~half that route A's specific tick/frame arithmetic happens to
land negative. §10.14's route A result (120 arms, 128 doesn't) is a
property of route A's particular uncompensated phase relationship, not a
universal signature — a differently-timed port missing the lock
entirely could easily be negative always, which is exactly what §10.25
measured. **This is 🟡 inferred from the absence of matching code, not
from a traced clock value under this port** — it has not been confirmed
that the timing byte is negative for the *same reason* (no relock) rather
than some other cause, only that the mechanism that would prevent it is
absent.

**What this changes.** Before extending §10.23's pool-address hypothesis
further, or continuing §10.25's plan to watch `0x4000aece..0x4000af22`,
the cheaper next step is checking what NOW (`0x46104cf0`/`0x46104cf4`) and
the step clock (`0x4610757c`) actually read under this port at the frame
the trig word is composed — if they show the same unbounded-negative
pattern §10.14 describes, this whole thread is the already-diagnosed M6f
gap wearing a new emulator's clothes, and the fix is porting
`--arm-phase-fix` (or a real MIDI-clock model) to `tools/ot_emu`, not a
new pool-address theory. Not yet done this session.

**Independent of which explanation is right:** hardware is the fastest
way to cut through it. §10.14's own hardware falsifier (Sam's unit, 7 Sep)
already settled the general "does recording arm at 120/128" question for
route A's finding. What has not been hardware-checked since is whether
*this exact build tag, this exact 128 BPM / RLEN 4 configuration* records
and plays back without the click Bryan reports — on hardware Sam controls
directly, not remotely through Bryan. Flash 7 (`tools/hw_flash7.py`) is
about to put hands on Sam's unit for an unrelated bus-claims run; folding
a short recorder-arm check into that same session is far cheaper than a
dedicated flash cycle later (see CLAUDE.md: "Flash cycles are
expensive").

### 10.27 ✅ THE FIRST HARDWARE MEASUREMENT: the recorder loop is clean on Sam's unit — exactly 20,672 samples, no ±1 seam (9 Sep 2026, tag OCTABAM21)

§10.21–§10.26 chased the recorder under the C++ port and found it never
arms (no audio anywhere in the pool, the frame builder's recorder-check
pass never runs, and §10.26: the port has no clock-lock model at all). So
the port could not show where a click comes from. The hardware can, and it
was cabled for flash 7, so the seam capture ran on Sam's own Octatrack.

**Fixture and rig.** Bryan's `r4_128` (128 BPM, T1 records inputs A/B with
recorder trigs at steps 2/6/10/14, T2 = FLEX on R1 with play trigs at the
same steps, RLEN 4), loaded on the flashed **OCTABAM21** image (the
UNPATCHED recorder — `bamsep27` carries no `recorder-seam` cave). A
Mac-generated tone into inputs A/B through the MicroBook, the OT's main
outs captured back, the Mac the clock master at 128 BPM
(`tools/hw_flash7.py`'s clock + source; capture analysed off-line). ⚠
`r4_128` was saved under OCTABAM17; it loaded and ran (an "errors" dialog
on the older build is dismissable).

**The decisive measurement — drift-immune.** The Mac and the OT are not
sample-locked, so the analog round trip drifts ~50 ppm (~1 sample per
20,672-sample loop), which is the SAME size as the ±1-sample seam route A
predicted — an ordinary phase or click metric cannot separate them
(instrument blindness, `CLAUDE.md`). The one view that survives the drift
is **cross-correlating T2's consecutive playback loops against each other**
(OT output vs OT output; the Mac's capture-clock drift cancels in the
alignment). Result, 40 consecutive loops:

```
per-loop period (samples): 20672 x40, spread 0, histogram {20672: 40}
```

**The loop period is exactly 20,672 samples, every pass, zero variation.**
The "−1 every 8 passes" seam route A measured for 128/RLEN 4 does NOT
appear as a period drop on hardware. The boundary discontinuity measured
directly is ~1 sample (median 0.1, max 2.7 × the tone's normal per-sample
slew; a full 1-sample drop would be a comparable ~1× step), i.e. at the
clock-drift floor, with no gross multi-sample click.

**What this settles, and what it does not.**
- ✅ The recorder records and loops on Sam's unit, and the PLAYBACK loop is
  exactly periodic — the fixed-RLEN playback is not the source of a hard,
  universal click. Bryan's audible click does not reproduce as a gross
  artifact here with a tone.
- ✅ It confirms §10.23's reading that the port's "no recorded audio" is a
  PORT GAP, not the firmware: the same fixture records fine on hardware.
- 🟡 It cannot, in an unsynced analog capture, confirm or deny a true
  ±1-sample seam at the drift floor — only that the loop period does not
  drop by a resolvable sample. A sample-locked capture (word clock) or the
  RLEN-MAX control (`max_128`, route A shows it seam-free) would separate a
  real ±1 seam from drift; neither was run.
- The stimulus caveat stands: a tone is a weak probe for a click, and
  Bryan records musical content whose phrase length rarely matches a fixed
  RLEN, so his click is most consistent with the content's own loop-point
  mismatch (or his unit) rather than a firmware playback seam.

**Where this leaves the recorder stream:** the sample-exact route-A
emulator remains the instrument for the RECORD-side seam arithmetic; the
hardware now shows the PLAYBACK loop is clean and the port's arm gap is the
port's, not the firmware's. The open port work (§10.26: model the
clock-lock / arm path) is a fidelity task, not a prerequisite for a click
that hardware does not exhibit.

### 10.28 ❌ §10.27 RETRACTED: the capture was live passthrough, not a recorded loop — recording is NOT confirmed on hardware (9 Sep 2026)

§10.27's "clean 20,672 loop" was measured with the tone playing the WHOLE
time, and §10.21's own warning applies to a hardware capture exactly as it
does to the port: a continuous tone monitored live through the track is
indistinguishable from a recorded buffer looped back. The decisive test
settles it — **record with the tone on, then CUT the input and keep
capturing:**

```
during tone:      output -30 dBFS
input cut off:    output -100 dBFS   (a 70 dB drop, flat silence, 8 s)
```

The output followed the input to silence. Nothing recorded is playing
back: T1 was MONITORING the live input (the armed recorder's input
monitor), not looping a captured buffer, and the seamless tone's period
(1000.53 Hz = exactly 469 cycles in 20,672 samples) is why the
cross-correlation "found" 20,672 — it was the tone's own period landing on
the search guess, not a buffer length. So **§10.27's three ✅ claims are
void**: the loop was not clean-because-recorded, it was the input; nothing
is settled about a playback seam because there was no playback; and it does
NOT confirm the recorder records on hardware.

**What is now actually known:** on Sam's unit, on this `r4_128` fixture
(saved under OCTABAM17, loaded past an "errors" dialog on the OCTABAM21
build), a live REC-armed track MONITORS its input but no recorded buffer
plays back when the input stops — the same "no recorded audio" the port
showed (§10.23), now seen on hardware too, so it is NOT simply a port gap.
Open question, unmeasured: whether the recorder trig arms and captures at
all here (the fixture's recorder SRC / the OCTABAM17-vs-21 load), or
whether it captures but T2's FLEX slot is not playing R1. The next step is
to reconfigure/verify the recorder ON THE UNIT (a real recorder trig, SRC =
the live input, T2's slot = R1) rather than trust a passthrough-blind
capture. The instrument rule from §10.21 stands and just cost another
reading: **prove the input is OFF before believing a recorder playback.**

### 10.29 Bryan's own image+project on hardware: recording WORKS; the seam is not cleanly measurable on this analog rig (9 Sep 2026)

Bryan's `to_bam` arrived (his image `OCTATRACK_OCTABAM22.bin`, his
`PROJECT 260908`, his clickless spreadsheet). Flashed OCTABAM22 on Sam's
unit and loaded his project.

**Recording works on his exact setup.** ✅ Unlike the rebuilt `r4_128`
fixture (§10.28, which only monitored the input), his image + project
capture and loop audio: with the transport running there is a sustained
looped signal on his self-looping track. So the recorder FUNCTIONS on
hardware; the earlier fixture's silence was a project-config problem (its
recorder trig lane / SRC / buffer assignment), not firmware, and it also
resolves §10.23's port "no recorded audio" as the port's gap, not the
firmware's.

**Driving it needed his sync flags flipped.** His project ships with MIDI
CLOCK RECEIVE and TRANSPORT RECEIVE OFF — he runs the unit standalone as the
master (CLOCK/TRANSPORT SEND on). With both RECEIVE flags turned on, the Mac
clocks the transport and can set the tempo for an A/B.

**The A/B against his spreadsheet did not hold up.** His formula: a loop is
clean when `RLEN × 15,876,000 / tempo24` is a whole number; 65.6 BPM
(tempo24 1575) gives 10,080 samples/trig exactly — a GOLDEN tempo, clean at
any RLEN — while 128 (tempo24 3072) gives 5167.96875, a 0.125-sample residue
per trig. A first pass looked like a clean reproduction (65.6: 2
click-candidates and a steady loop period; 128: 16 and a wandering period).
It did **not** survive repetition. Three confounds stack and dominate:

1. **His setup is sound-on-sound overdub.** The looped level builds up and
   CLIPS (7–8 % of samples) even at a 0.01 input — the output level is set
   by the accumulation ceiling, not the input — and clipping manufactures
   its own discontinuities (a ~100 Hz buzz at one point) that swamp the
   seam.
2. **The recorder never holds still.** It re-records every pass, so there is
   no static buffer to loop-analyse; the measured loop length jumped run to
   run (20,727 / 23,197 / 88,400 / 73,145 at 65.6) and at 0.01 read ~73,000
   at BOTH tempos — i.e. not tracking the tempo at all, so the "wander"
   cannot be attributed to the seam.
3. **No word clock.** The Mac and OT drift ~1 sample/loop, the same size as
   the seam; only a cross-correlation of a STATIC recorded buffer would
   cancel it, and there is no static buffer (see 2).

**Conclusion.** Recording is confirmed on hardware, but a clean, sample-level
hardware measurement of the golden-vs-clicking seam is not achievable on
this rig (analog round trip, unsynced clocks, live overdub). It would need a
single non-overdubbing recording, headroom below clipping, and a
word-clock-locked capture. **The sample-exact seam therefore remains route
A's result** (`octabam-emac-unicorn-bug`: −1 every 8 passes at 128/RLEN 4),
which the fixed-EMAC emulator measures without any of these confounds. The
hardware's contribution is narrower and real: the recorder works, and
Bryan's click is a loop-boundary phenomenon consistent with his fixed-RLEN
theory — but the number is the emulator's, not this capture's.

### 10.30 The golden CONTROL falsifies the A/B: the "wander" tracks loop length, not the seam (9 Sep 2026)

After §10.29, the clipping was traced to the OT's playback gain (not the
Mac input) and fixed over MIDI (track LEVEL/AMP VOL to unity, input at
~−60 dBFS, 0 % clipped). Clean captures then looked like a reproduction
again: 65.6 golden showed a stable modal loop period (11–14 of 16 loops
identical), 128 non-golden showed none (every loop distinct). **A golden
CONTROL settled it against us.** 125 BPM (tempo24 3000, 5292 samples/trig
exact) is ALSO golden — it must be clean if the metric measures the seam.
It wandered exactly as much as 128 (5/5 distinct, spread 55), because at
125 and 128 the recorded loop is long (85k–149k samples, only 5–10 passes
in the capture) while 65.6's is short (17,640, 16 passes). The
cross-correlation's per-loop period spread is set by the analog drift
ACCUMULATED over a loop and the number of passes available to average — a
loop-length artifact — not by the golden-vs-clicking residue. So the
apparent 65.6-clean / 128-wander difference is confounded by loop length,
and **the A/B does not reproduce the seam on hardware.** The §10.29
conclusion stands, now with the control that proves it: recording works on
Bryan's setup, but this analog rig cannot isolate the sample-level seam,
and the golden control is what catches the false positive. The sample-exact
number is route A's.

### 10.31 ✅ REPRODUCED ON HARDWARE, by ear: the golden rule holds (9 Sep 2026, tag OCTABAM22, Sam's unit + Bryan's project)

§10.29/§10.30 concluded the seam was "not measurable on this rig." That was
true for the NUMERICAL loop-period measurement (the analog drift floor of
±30–40 samples swamps the seam), and it was measured under two confounds
that also fooled the EAR test. Removing both reproduced Bryan's click
cleanly, and Sam — who had been trying to reproduce it for days —
confirmed it twice.

**The two confounds, both mine:**
1. **The Mac's MIDI clock.** Driving the OT's transport from Python's
   software clock (±~1 ms jitter) wobbles the recorder's timing at EVERY
   tempo, manufacturing click variation that is the clock's, not the
   recorder's. Bryan runs the unit standalone on its internal crystal.
2. **The recorder loop crossfade (FIN/FOUT).** With a crossfade set, the
   loop boundary carries the crossfade's own per-loop artifact at BOTH
   tempos, which masks the golden-vs-non-golden difference. (This is also
   the hardware proof of Bryan's hypothesis that the crossfade alone does
   not fix the click — the golden-tempo behaviour survives it.)

**The clean test (internal clock, crossfade OFF):** a continuous 1 kHz tone
into inputs A/B (the right stimulus — Bryan's source is a continuous Moog
synth, a drone, so a tone matches it; rhythmic content was a wrong turn),
T1 self-looping on R1 at RLEN 16, the Mac feeding only the tone and NO
clock, Sam running the transport on the unit's internal clock. By ear,
confirmed on two runs:

| tempo | | result |
|---|---|---|
| 65.6 (GOLDEN, 16×10,080 = 161,280 exact) | | **perfect loop, occasional blip** |
| 128 (non-golden, 16×5167.96875 = 82,687.5) | | **gaps at the loop** |

**What this establishes.** Bryan's golden rule is real on hardware: at a
golden tempo the loop is clean, at a non-golden one it clicks/gaps — with a
continuous source, the crossfade off, on the unit's own clock. It confirms
his spreadsheet's premise and his point that the crossfade is not the fix.
The sample-exact SIZE of the seam stays route A's number (the analog rig
cannot resolve one sample), but the AUDIBLE golden-vs-non-golden click is
now hardware-confirmed. Method note for next time: **the human ear on the
internal clock is the instrument here** — my cross-correlation of the
analog capture could not resolve the seam under the drift floor, but the
ear cleanly tells a perfect loop from a gappy one. And the process lesson
Sam enforced: reproduce and confirm before calling it — the first "clean"
reading of nearly every approach in this section did NOT survive
repetition; this one did, twice.

### 10.32 ✅ The seam reproduced in the EMULATOR (route A), sample-exact, matching §10.31's hardware ears (9 Sep 2026)

After the hardware reproduction (§10.31), the same golden-vs-non-golden pair
was run in route A (the EMAC-fixed Python emulator, `recaudio.py` injecting a
counter at the recorder input ring and reading the buffer + the firmware's own
arm/end records). Fixtures: T1 self-looping on R1, RLEN 16, single REC1+play
trig on step 1 (Bryan's geometry), at 65.6 and 128, via `ot_project`.

**The firmware's own recorded loop length (from the end record):**

| tempo | recorded length | ideal (16 × samples/trig) | residue |
|---|---|---|---|
| 65.6 GOLDEN | **161,280** (0x27600) | 16 × 10,080 = 161,280 | **0 — exact, clean** |
| 128 non-golden | **82,687** (0x142ff) | 16 × 5167.96875 = 82,687.5 | **−0.5 — truncated, seam** |

The golden tempo's length equals the grid interval exactly (arm spacing
161,280.0), so every pass aligns and the loop is clean — the hardware
"perfect." The non-golden length truncates the true 82,687.5 to 82,687 (the
truncated-reciprocal rounding of §10.16.4), leaving a −0.5-sample per-pass
residue — the seam, the hardware "gaps." Route A computes it with no analog
drift or clock jitter, the instrument the hardware A/B could not be, and it
agrees with the ear.

**This is the fix platform.** A recorder-side fix that makes a non-golden loop
seamless (size successive passes to alternate so they sum to the exact grid, or
a sample-accurate seam repair) is developed and verified HERE against the exact
length/buffer, then flashed and ear-confirmed on the unit the way §10.31 was.
What route A still cannot do is render the FLEX voice that plays the buffer back
to audio (the flex-from-recorder-buffer loader is unlocated in both emulators)
— that is the next task, to let the loop be heard in the emulator, not only
measured.

### 10.33 FLEX-loader is NOT unlocated: the recorder-buffer play trig binds a voice in route A, each pass — the gap is the render, not the bind (9 Sep 2026)

Getting the recorder-buffer FLEX voice to render (so the loop can be HEARD in
the emulator, not only measured) — Sam's next ask after §10.32. `recaudio.py`
gained a `--flex-probe` (watch the FLEX bind `0x4000f450` and its caller
`0x4000d49e`, §10.13). Run on `g65`/`n128` (RLEN 16 self-loop), route A:

- **The recorder captures.** The pool holds 82 non-zero 6,144-byte blocks —
  route A DID record the injected input (correcting the §10.22–23 "pool all
  zero," which was the C++ port, not route A).
- **The bind fires, and re-fires every pass.** `0x4000f450` runs at the
  step-1 play trig on pass 1 (frame 1) AND pass 2 (frame 5167, right at the
  first end-post) with **D0 = 0x80 = recorder buffer R1** (buffers are ids
  128–135) and A1 = 0x8000082f. So the FLEX-from-recorder-buffer loader is
  **reached and binds R1**, not "unlocated" — §10.13's `0x4000f450` "fails on
  an empty buffer" was the frame-1 case only; by pass 2 R1 is full and the
  same bind runs.

**So the remaining gap is the RENDER, not the bind.** `recaudio.py`'s
`audio_out` capture is the recorder INPUT block (`saddr 0x80003190`, where the
driver injects) — its L channel is the live input counter `16×frame` at every
pass, which is why it looked like "thru." That block is NOT the FLEX voice's
output; O10 established the voice's audio lands in the track's **84-word
record**. The open question, and the next probe: capture the 84-word record
(the voice output) at a pass-2 play trig and check whether it carries R1's
recorded samples (playback works) or is silent/passthrough (the DSP-side
voice render for a recorder buffer is the real gap). The pieces upstream of it
— recorder writes, control record, bind — are now all confirmed present in
route A.
