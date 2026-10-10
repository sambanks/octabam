# The kernel: scheduler, tasks, interrupts

Read byte-exact from the image 6 Sep 2026 (`scripts/disasm.sh emac`) and
measured under the firmware's own scheduler (route A, retired 26 Sep 2026,
60509404; the logs are `git show 3ceba41:docs/history/RTOS_FORK.md` and
`git show 3ceba41:docs/history/COLDFIRE_PORT.md`; the emulators and what
they must reproduce: `tools/emu/README.md`). ✅ measured or byte-exact,
🟡 inferred, ❓ open.

## Scheduler ✅

About 0x200 bytes at `0x40000550`–`0x40000760`. TCB layout (`0x400005fc`
builds it, `0x40000550`/`0x4000056e` save and restore):

| offset | field |
|---|---|
| `+0x00` / `+0x04` | next / prev in the priority's circular list |
| `+0x08` | pointer to the priority level's list head, `0x800068dc + 4·prio` |
| `+0x0c`–`+0x4b` | saved `d0–d7, a0–a7` (`moveml`; `a7` at `+0x48`) |
| `+0x4c` | ready flag (1 = on a ready list) |
| `+0x50` | lock waiter chain |

Globals: current TCB `0x800068fc`; top-priority pointer `0x800068d8`
(points into `0x800068dc[8]`; higher index = higher priority; the block path
scans downward, `0x40000852`); `0x80006900` scratch for `a0` on entry.

Entry `0x40000550` serves two vectors, `trap #0` (32) and PIT0 (171),
installed at `0x400005d8`/`0x400005dc`: masks interrupts, saves all
registers into the current TCB, takes the head of the top ready list,
clears the reschedule bit (`0xfc04c010 &= ~0x800`), re-arms PIT0 with
`0xb3f`, sets cache control, restores with `moveml a0@(12),d0-sp`, `rte`. A
new task's saved context is an exception frame on its own stack
`[0x407c][SR 0x2000][entry PC]` with task exit `0x400006e4` under it
(`0x4000061c`–`0x40000626`).

Primitives (all `jsr` targets): create `0x400005fc(tcb, entry, prio,
stack, size)`; make-ready `0x4000063c(tcb)` (raises the top pointer, does
not force a switch); unlink `0x4000068c(tcb)`; event wait
`0x40000818(event)`; queue post `0x40000c3c(queue, msg)` (ring at
`queue+0x14`, mask `+0x10`, head `+0x18`; wakes the waiter at `+0x0c`);
queue receive `0x40000d1a`; event signal `0x40000888`; counting wait
`0x400007a4` (traps at `0x40000810`); queue init `0x40000bd4`; task exit
`0x400006e4`. `0x400009f4` is a lock (owner TCB `+0`, waiter list `+4`/`+8`
chained through `TCB+0x50`; contended take traps at `0x40000a78`; unlock
`0x40000ab4` hands to the first waiter and traps if it outranks the top
pointer; try-lock `0x40000a94`; init `0x400009e4`); the serial-link driver
wraps it at `0x40010db0`/`0x40010d90`.

A reschedule is a forced PIT0 interrupt: signal (`0x400008ea`) and post set
INTFRCH bit 11 of INTC1 (`0xfc04c010`), source 43, vector 171. It lands once
the primitive restores the caller's SR. After main creates its tasks the
first switch is the first tick (sample 8,812).

Vector install `0x40000d50(vec, fn)` writes `[VBR + 4·vec]`; default
handler `0x40000d74` calls `[0x460ba970]` (set by `0x40000da4` from
`0x40040b88`). Kernel init `0x40000db0` refills all 256 slots with the
trampoline, so handlers installed during boot (the UART driver's,
`0x40010faa`) are re-installed by main. VBR = `0x40000000` (the image's
first KB, `[0x400b9668]`).

## Tasks ✅ (eleven, measured by a hook on create)

| prio | TCB | entry | stack | created by | what |
|---|---|---|---|---|---|
| 6 | `0x46c7fb0c` | `0x40005540` | `0x46c7ea20` +0x1000 | main | MIDI / voice mailbox task (`MIDI.md`) |
| 5 | `0x460bcc2c` | `0x4001ee30` | `0x460bc42c` +0x800 | sys | storage (FAT/ATA) |
| 4 | `0x460d4f80` | `0x4005593c` | `0x460d4780` +0x800 | sys | key-repeat timer |
| 3 | `0x460d59d4` | `0x40056c40` | `0x460d51d4` +0x800 | sys | UI (`queue_receive(UI_QUEUE)`) |
| 2 | `0x460fab80` | `0x40091d18` | `0x460fabd4` +0x2000 | main | 🟡 likely the Static streaming scheduler: waits on `0x46c901b8`, walks eight per-track records, builds read requests (`STEM_REC.md` 19.6) |
| 2 | `0x460ffd44` | `0x400921c4` | `0x460fdd44` +0x2000 | main | 🟡 card reader: requests on queue `0x460fcd24`, the raw read slot `0x46c82426`, signals the requester; likely for the Static machines (`STEM_REC.md` 19.6) |
| 2 | `0x460e0e38` | `0x4009203c` | `0x460dee38` +0x2000 | main | machine parameters: receives queue `0x460d17ee` (kinds `0x0f` and `0x0e`, `MIDI.md`); ping-pongs with sys |
| 1 | `0x460ddde4` | `0x4008445c` | `0x460d9de4` +0x4000 | main | engine (46-opcode dispatcher, queue `0x460d17ce`; RELOAD BANK types `0x14`, `6`) |
| 1 | `0x46105508` | `0x40098a5c` | `0x4610555c` +0x2000 | main | ❓ waits on `0x4610755c`, walks eight per-track records with the EMAC fractional: per-voice work (`STEM_REC.md` 19.6) |
| 1 | `0x46c7bed8` | `0x40061a94` | `0x460d6de4` +0x2000 | main | sys: serial + SPI start-up, then creates storage, UI, p3 |
| 0 | `0x46c7ae84` | `0x4001f834` | top `0x46c7becc` | boot | main: runs the init list, then `bras .` at `0x4001fc9c` (= idle) |

At the handoff (`trap #0` at PC `0x40000e46`) only main is ready; the
current TCB `0x46c7ae30` is the pre-multitasking context, saved once and
never resumed. Route A's M6a gate: 10 tasks created, 11 ran, gate at
204.95 ms (`out/oracle/m6a.json`).

## Interrupts ✅

Two controllers. INTC0 `0xfc048000`, vectors `64 + source`; INTC1
`0xfc04c000`, vectors `128 + source`. 🟡 The firmware never writes
IMRH/IMRL; it unmasks through CIMR (`+0x1d`, value = source, `0x40` = all)
and sets ICRn at `+0x40+n`; a CIMR write must also clear IMRL's MASKALL bit.

| vector | source | handler | installed at | what |
|---|---|---|---|---|
| `0x41` | INTC0 1 | `0x4000aad0` | `0x4001fc02` (main) | DSP frame (level 5) |
| `0x47` | INTC0 7 | `0x4001fca0` | `0x4001f81c` | halt path (`SR 0x2700`, `bras .`) |
| `0x48`/`0x49`/`0x4f` | INTC0 8/9/15 | `0x40004840` | `0x400097a6`/`0x400097b0`/`0x400097ba` | eDMA channels 0/1/7: the 7-state frame transfer, jump table `0x400ab61a` (`ARCHITECTURE.md` section 6) |
| `0x56` | INTC0 22 | `0x400152a4` | `0x400160c6` (the ATA init) | eDMA channel 14, the ATA sector DMA's completion: clears CINT 14, sectors done = (`0xfc0451d0` − buffer `0x4ecb8000`) ≫ 9 into `0x460bac04`, one kernel signal (`0x40000c3c`, `0x460bb3a0`) per new sector |
| `0x5a` | INTC0 26 | `0x400106ec` | `0x400110ae` | UART0 RX, MIDI IN (`MIDI.md`) |
| `0x5b` | INTC0 27 | `0x400109bc` | `0x40010faa` (UART init `0x40010efc`, 312,500 baud) | serial link `0xfc064000`, level 6 |
| `0x5c` | INTC0 28 | `0x40010b88` | `0x40010d6e` | serial block `0xfc068000`, RX only |
| `0x60` | INTC0 32 | `0x400a1e0c` | `0x400a109c` | forced sequencer tick (INTFRCH bit 0, `0xfc048010`) |
| `0x61`/`0x62` | INTC0 33/34 | `0x40055cb8`/`0x400409f4` | `0x40040482`/`0x4004044c` | ❓ |
| `0x64`/`0x65` | INTC0 36/37 | `0x40092bf4`/`0x4009228c` | `0x40092f10`/`0x4009268c` | MIDI framer (`MIDI.md`) / ❓ |
| `0xab` | INTC1 43 | `0x40000550` | `0x400005dc` | PIT0, the time-slice |
| `0xac` | INTC1 44 | `0x40020d38` | `0x40020c5e` | PIT1, the storage delay timer |
| `0xaf` | INTC1 47 | `0x4001e594` | `0x4001e01a` | USB OTG (source 47 in the MCF54455RM; installed from the USB stack's init) |
| `0xb1` | INTC1 49 | `0x4001c244` | `0x4001c2fc` | counter + ack of `0xfc0bc008` |
| `0xb6` | INTC1 54 | `0x40015304` | `0x40016128` (ATA init `0x400160f8`) | ATA: one sector per interrupt, signal at count 0 |

Levels, from the ICR byte writes (✅ objdump, 5 Oct 2026):

| level | vectors |
|---|---|
| 7 | `0x47` halt |
| 6 | `0x48`/`0x49`/`0x4f` eDMA frame transfer; `0x5a` UART0 MIDI IN; `0x5b` UART1 serial link |
| 5 | `0x41` DSP frame; `0xb1`; `0xb6` ATA |
| 4 | `0x5c` serial block; `0xaf` USB |
| 3 | `0x56` eDMA 14 (ATA sector DMA) |
| 2 | `0xac` PIT1 |
| 1 | `0xab` PIT0 time-slice |

INTC0 sources 8 + n are eDMA channel n (channels 0, 1, 7 and 14 are
used); `0xfc04401c` is the eDMA CINT register, written with the channel
number by each of their handlers. Level 6 nests inside the frame interrupt
when it lands before the ISR's
`rte`; level 5 and below cannot (unless the ISR lowers SR mid-body, not
checked). The frame ISR is measured from entry to the epilogue at
`0x4000d9a6` by CF METER, so the eDMA chain and both UARTs can be inside
that span and ATA and USB cannot (`ARCHITECTURE.md` section 6, the CF METER
takes).

Time-slice: PIT0 `0xfc080000`, prescaler 2¹¹ (PCSR `0x0b36` at init,
`0x0b3f` on every switch), PMR `264,000,000 / 409,600 − 1 = 643` → 5.0 ms
per tick = 220.5 samples = 13.8 audio frames. PIT1 `0xfc084000` (PCSR
`0x0b3a`, PMR 2014) is the storage layer's delay timer (`0x40020c7c`).
