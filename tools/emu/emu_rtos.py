#!/usr/bin/env python3
"""Emulator route A: the firmware's own scheduler, running (docs/firmware/RTOS_FORK.md).

M1-M5 run firmware COLD: a function called against the warm machine, an
interrupt handler pushed a fake frame. This module crosses the `trap #0`
boundary and lets the kernel run: the trap is dispatched by hand into the
scheduler entry, every `rte` is popped by hand (Unicorn's CFV4E raises
intno 256 instead of executing it), PIT0 is modelled as a timer counted in
SAMPLES, and the two interrupt controllers are register-level models whose
asserted sources are injected between bursts.

M6a (done 6 Sep 2026): boot, dispatch the handoff, run until every task has
been created and each has run at least once. The exit gate compares what the
emulator observes against EXPECTED_TASKS below -- eleven tasks, measured
here and written back into docs/firmware/RTOS_FORK.md §2 (the scope's eight came from
a literal scan that missed the create sites called through a register).

Three facts from the 6 Sep 2026 idle read that shape the loop (byte-exact,
scripts/disasm.sh emac):
  * the main task parks in `bras .` at 0x4001fc9c and never blocks, so
    level 0 is never empty: no idle task exists, and a PC parked there means
    "skip to the next timer event";
  * a reschedule IS a forced PIT0 interrupt -- signal/post set INTFRCH bit 11
    of INTC1 (source 43, vector 171 = the scheduler entry), which lands only
    once the primitive restores the caller's SR; so an INTFRC write ends the
    burst at once and a pending-but-masked interrupt is re-checked at a fine
    grain until the IPL drops;
  * make-ready (0x4000063c) does NOT force: after main creates the seven
    tasks nothing switches until the first real tick.

Time accounting: a burst is charged its full instruction quantum even when
an exception or a hook stopped it early (Unicorn does not report how far it
got); the error is bounded by one quantum per event and the clock runs
slightly FAST, never slow. `--ips` (instructions per sample) is a knob with
a default, not a measurement -- RTOS_FORK.md §6.

    .venv/bin/python3 tools/emu/emu_rtos.py --project <dir> --set OCTABAM --name RIG --ms 100
"""
import argparse
import collections
import os
import pathlib
import struct
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import emu_bringup as eb           # noqa: E402
import emu_card as ec              # noqa: E402

# --- the kernel, byte-exact (docs/firmware/RTOS_FORK.md §2) --------------------------
VBR = 0x40000000                   # [0x400b9668]; the image's own first KB
SCHED = 0x40000550                 # one handler for trap #0 (vec 32) and PIT0 (vec 171)
SCHED_RTE = 0x400005a6             # the scheduler's rte: a task is being (re)entered
CREATE = 0x400005fc                # create(tcb, entry, prio, stack, size)
CUR_TCB = 0x800068fc               # current TCB
TOP_PRIO = 0x800068d8              # -> into the list-head array
LIST_HEADS = 0x800068dc            # [8] circular-list heads, higher = higher prio
TCB_A7 = 0x48                      # moveml d0-sp from +0x0c: a7 at +0x48
MAIN_SPIN = 0x4001fc9c             # `bras .` -- main's park, the idle point
MAIN_TCB = 0x46c7ae84
BOOT_TCB = 0x46c7ae30              # the pre-multitasking context the first trap saves
HANDOFF = 0x40000e46               # the boot's trap #0
LOCK_TRAP = 0x40000a78             # the lock primitive's (0x400009f4) block trap
SR_TRAMP = 0x47ef0800              # `movew %sr,%d0; nop` -- see Rtos._sr (emu_bringup's
                                   # EMAC trampoline slots live at 0x47ef1000..0x47ef1fff)
KERNEL_POST = 0x40000c3c           # post(queue, msg) -- non-blocking, see Rtos.post_message
SYS_TCB = 0x46c7bed8
SYS_QUEUE = 0x460d17ae             # the sys task's own command queue
SYS_MSG_SCRATCH = 0x46c00000       # scratch for a hand-built message -- see request_card_mount;
                                   # inside the boot's 0x46000000+32MB map, far from any named global
# The bank blobs in RAM: PART_PTR (ec.PART_PTR, 0x46c82456) = BANK_BLOB +
# bank * BANK_STRIDE, i.e. the CURRENT BANK's data; 0x400e21e0 is bank A,
# 0x4017d520 bank B. 0x80000002 is the current BANK (emu_card.FW_CUR_BANK),
# 0x80000004 the current pattern. Read 6 Sep 2026 from the engine's LOAD
# PROJECT handler, which parses the project file's BANK= and PATTERN= keys
# (0x40087d0e..0x40087d44) -- correcting an earlier reading of this module
# that called 0x400e21e0 an "empty sentinel" and 0x80000002 the current
# track (docs/firmware/RTOS_FORK.md section 7 has the retraction).
BANK_BLOB = 0x400e21e0
BANK_STRIDE = 635712
CUR_BANK = 0x80000002
CUR_PATTERN = 0x80000004
ENGINE_BANK_WRITE = 0x40087d44     # LOAD PROJECT writes PART_PTR from the file's BANK= here
SELECT_BANK_CASE = 0x40062288      # sys table[20]: "select bank msg[1]" -- switch the working bank

# M6d: the real key-press path. UI_QUEUE (0x460d1664) is what FW_TRANSPORT
# posts to (EMU.md, "a post to the UI queue"); its ring buffer sits at
# 0x460d4fd4 (queue_init site 0x40040b70), 0x54 bytes past the TCB this
# module used to call "ui" -- which is why that TCB was misnamed (see the
# TASK_NAMES retraction below). The keys themselves are found in a jump
# table at 0x400d2d54 (8 track-key entries, a gap, then a function-key run);
# REC/PLAY/STOP sit at consecutive indices 24/25/26. All three call chains
# (checked by disassembly, 6 Sep 2026: 0x400a013c, 0x400a030c, 0x400a14a4,
# 0x400a10c8, 0x40033968, 0x4009b290 -- everything PLAY and REC reach) are
# free of the blocking primitives (0x40000818/0x400007a4/0x40000d00), so
# call_as_main is safe for both, the same way it already was for
# FW_TRANSPORT/FW_START_TRACK.
UI_QUEUE = 0x460d1664
KEY_REC = 0x4000a274
KEY_PLAY = 0x4000a200               # gated on 0x80000029 (nonzero from boot in the test project);
                                     # sets clock-sync fields, then tail-calls FW_TRANSPORT
KEY_STOP = 0x4000a1e0
REC_ARM = 0x800066a0                 # the record-arm state REC's own handler tests
TRANSPORT = 0x800065b8               # 0 -> 1 when the transport starts (§9.4)
# ⚠️ BOTH ARE LONGWORDS, NOT BYTES. The transport start is a 4-byte store of
# 1 at 0x800065b8 (measured 6 Sep 2026: `[0x800065b8] <- 0x1 (4)` at pc
# 0x4009c3d4 in main), so the byte AT 0x800065b8 stays 0 and the 1 lands in
# 0x800065bb. Reading either of these a byte at a time reports "never
# changed" no matter what the firmware does -- read the word.
def _word(rt, addr):
    return int.from_bytes(rt.uc.mem_read(addr, 4), "big")

# The tasks, as MEASURED under the real scheduler on 6 Sep 2026 (the create
# hook below): (tcb, entry, prio, stack, size, creator). Main is created by
# the boot before our hooks exist. RTOS_FORK.md §2's table of eight was read
# from the five `jsr` create sites the literal scan finds; the other five
# sites call through a register and were missed. Ten are created: seven by
# main's init list, three by the prio-1 task at 0x40061a94 once its own
# start-up traffic (serial link, SPI) is done.
EXPECTED_TASKS = (
    (0x46c7fb0c, 0x40005540, 6, 0x46c7ea20, 0x1000, MAIN_TCB),     # voice / DSP mailbox
    (0x460fab80, 0x40091d18, 2, 0x460fabd4, 0x2000, MAIN_TCB),
    (0x460ffd44, 0x400921c4, 2, 0x460fdd44, 0x2000, MAIN_TCB),
    (0x460e0e38, 0x4009203c, 2, 0x460dee38, 0x2000, MAIN_TCB),     # not in the §2 table
    (0x460ddde4, 0x4008445c, 1, 0x460d9de4, 0x4000, MAIN_TCB),     # engine
    (0x46105508, 0x40098a5c, 1, 0x4610555c, 0x2000, MAIN_TCB),
    (0x46c7bed8, 0x40061a94, 1, 0x460d6de4, 0x2000, MAIN_TCB),     # not in the §2 table: creates the three below
    (0x460bcc2c, 0x4001ee30, 5, 0x460bc42c, 0x0800, 0x46c7bed8),   # storage
    (0x460d4f80, 0x4005593c, 4, 0x460d4780, 0x0800, 0x46c7bed8),   # repeat-key timer, NOT ui (M6d retraction)
    (0x460d59d4, 0x40056c40, 3, 0x460d51d4, 0x0800, 0x46c7bed8),   # ui -- the real UI_QUEUE receiver (M6d)
)
ALL_TCBS = frozenset(t[0] for t in EXPECTED_TASKS) | {MAIN_TCB}
# M6d retraction: 0x460d4f80 (entry 0x4005593c) was named "ui" by
# neighbourhood -- its ring buffer (0x460d4fd4) sits just past this TCB, but
# the task itself waits on an unrelated counting semaphore (0x46c7e0e2) and
# spends its life decrementing a 136-slot key-repeat timer array
# (0x4001387c). The task that actually calls queue_receive(UI_QUEUE)
# (0x40000d00, confirmed by disassembly 6 Sep 2026) is 0x460d59d4, entry
# 0x40056c40 -- previously the unidentified "p3". Names swapped here to
# match; RTOS_FORK.md's table carries the same correction.
TASK_NAMES = {0x46c7fb0c: "voice", 0x460bcc2c: "storage", 0x460d4f80: "keyrepeat",
              0x460fab80: "p2a", 0x460ffd44: "p2b", 0x460e0e38: "p2c",
              0x460ddde4: "engine", 0x46105508: "p1b", 0x46c7bed8: "sys",
              0x460d59d4: "ui", MAIN_TCB: "main", BOOT_TCB: "boot"}

# --- peripherals ------------------------------------------------------------
PERIPH_BASE, PERIPH_SIZE = 0xfc000000, 0x100000
INTC0, INTC1 = 0xfc048000, 0xfc04c000
PIT0, PIT1 = 0xfc080000, 0xfc084000
DSPI = 0xfc05c000
PLL_REG, PLL_VAL = 0xfc0c4000, 0x16000000       # emu_bringup's one load-bearing reply

SAMPLE_HZ = 44100.0

# M6c: the DSP audio-frame interrupt (INTC0 source 1, vector 0x41) is a
# free-running hardware clock, unlike PIT0/PIT1 -- fixed period, no enable
# bit, no registers (RTOS_FORK.md §4: "a frame interrupt every 16 samples").
# Its ICR level and CIMR unmask are programmed by main's own boot tail
# (0x4001fc2e..0x4001fc3e, byte-exact from the M6a scan) and its handler
# installed on the vector by main's own init (0x4001fbf8) -- both run for
# real under our scheduler, so nothing needs seeding here, only the source.
FRAME_PERIOD = 16.0                # samples per DSP-frame interrupt
FW_FRAME_ISR = 0x4000aad0          # the frame builder (emu_frames.FW_FRAME_ISR)
FW_TRANSPORT = 0x4009b964          # (arg) transport start/stop; start posts to the UI queue
FW_START_TRACK = 0x4009b5c8        # (track) promote a track to running (emu_frames.py names both)
FW_LIVE_NIBBLE = 0x46104d15        # per-track byte a fired trig actually changes (emu_frames.py)
FW_TRIG_WORDS = 0x46104d26         # per-track word Bryan named; stays zero in every run so far
FW_MIDI_SETTINGS = 0x80000028      # project MIDI byte: bit 0 = CLOCK RECEIVE (emu_frames.py)
FW_SEQ_SELECT = 0x400a1030         # sequencer select(bank, pattern): the LOAD PROJECT handler's
                                   # last step (0x40025b16), also the sequencer init's (0x400a1088)
FW_SEQ_BANK = 0x800065bd           # the sequencer's own playing bank byte (FW_START_TRACK: x 635712)
FW_SEQ_PATTERN = 0x800065be        # ...and playing pattern (x 36568)
PATTERN_STRIDE = 0x8ed8            # 36568; sixteen records fill blob+0..0x8ed80
TRAC_STRIDE = 0x91a                # one audio track's sequencer record inside a pattern


class Pit:
    """MCF547x programmable interrupt timer, counted in samples.

    PCSR bits: EN 0, RLD 1, PIF 2 (write-1-clear), PIE 3, OVW 4, DBG 5,
    DOZE 6, PRE 8-11 (clock / 2**PRE). PMR at +2, PCNTR (read-only) at +4.
    The clock the prescaler divides is a knob: the firmware sizes PMR from a
    264 MHz constant (0x400005b4) and that is the default; if the PIT runs
    off the 132 MHz bus clock every period below is 2x longer.
    """
    EN, RLD, PIF, PIE, OVW = 1, 2, 4, 8, 16

    def __init__(self, name, clock_hz):
        self.name, self.clock_hz = name, clock_hz
        self.pcsr, self.pmr = 0, 0xffff
        self.expiry = None          # sample at which PCNTR next reaches 0
        self.fired = 0

    def period_samples(self):
        pre = (self.pcsr >> 8) & 0xf
        return (self.pmr + 1) * (1 << pre) / self.clock_hz * SAMPLE_HZ

    def _arm(self, now):
        self.expiry = now + self.period_samples() if self.pcsr & self.EN else None

    @property
    def irq(self):
        return bool(self.pcsr & self.PIF) and bool(self.pcsr & self.PIE)

    def read(self, off, size, now):
        if off == 0:
            return self.pcsr
        if off == 2:
            return self.pmr
        if off == 4:                 # PCNTR: what is left of the current period
            if self.expiry is None:
                return self.pmr
            frac = max(0.0, self.expiry - now) / max(self.period_samples(), 1e-9)
            return int(frac * self.pmr) & 0xffff
        return (1 << (size * 8)) - 1

    def write(self, off, size, val, now):
        if off == 0:
            was_en = self.pcsr & self.EN
            pif_clear = val & self.PIF
            self.pcsr = (val & ~self.PIF) | (self.pcsr & self.PIF)
            if pif_clear:
                self.pcsr &= ~self.PIF
            if (self.pcsr & self.EN) and not was_en:
                self._arm(now)
            elif not self.pcsr & self.EN:
                self.expiry = None
        elif off == 2:
            self.pmr = val & 0xffff
            if self.pcsr & self.OVW or self.expiry is None:
                self._arm(now)

    def advance(self, now):
        """Fire every expiry up to `now`; returns the number fired."""
        n = 0
        while self.expiry is not None and now >= self.expiry:
            self.pcsr |= self.PIF
            self.fired += 1; n += 1
            self.expiry = self.expiry + self.period_samples() if self.pcsr & self.RLD else None
        return n

    def seed(self, pcsr, pmr, now):
        """State the boot left behind the generic stub (0x400005a8..0x400005f6)."""
        self.pcsr, self.pmr = pcsr, pmr
        self._arm(now)


class Intc:
    """MCF5445x interrupt controller (MCF54455RM rev 5 ch. 17; "MCF547x" here
    until 6 Sep 2026 was wrong -- same register map, different chip): IMRH/L
    +0x08/+0x0c, INTFRCH/L +0x10/+0x14,
    SIMR/CIMR bytes at +0x1c/+0x1d (value = source, 0x40 = all), ICRn at
    +0x40+n. IPRH/L (+0x00/+0x04) read back the asserted sources. Vector =
    `vec_base + source`. `lines` maps a source to a callable giving its level.
    """
    def __init__(self, name, vec_base, lines=None):
        self.name, self.vec_base = name, vec_base
        self.imr = 0xffffffff_ffffffff      # bit n = source n masked; bit 0 = mask all
        self.intfrc = 0
        self.icr = [0] * 64
        self.lines = dict(lines or {})
        self.on_force = None                # called when an INTFRC bit is set

    def asserted(self):
        a = self.intfrc
        for src, fn in self.lines.items():
            if fn():
                a |= 1 << src
        return a

    def pending(self):
        """[(level, source)] asserted and unmasked, highest level first.

        A FORCED request ignores the mask: "The assertion of an interrupt
        request via the interrupt force register is not affected by the
        interrupt mask register" (MCF54455RM rev 5, 17.2.3, read 6 Sep 2026).
        The firmware depends on it -- the sequencer tick (INTFRCH0 bit 0,
        source 32) is installed with ICR 3 at 0x400a10a4 and never unmasked
        anywhere in the image (15 CIMR sites, none names 32; no IMRH/IMRL
        write at all), and masking it here left the sequencer silent: 400
        frames, zero ticks. The kernel's own reschedule (source 43) IS
        unmasked at 0x400005ea, so nothing changes for it. A source with
        ICR 0 is still never delivered."""
        a = self.asserted() & ~self.imr
        if self.imr & 1:
            a = 0
        a |= self.intfrc
        out = [(self.icr[s], s) for s in range(1, 64) if a >> s & 1 and self.icr[s]]
        out.sort(reverse=True)
        return out

    def read(self, off, size):
        if off < 0x18 and size == 4:
            a = self.asserted()
            return {0x00: a >> 32, 0x04: a & 0xffffffff,
                    0x08: self.imr >> 32, 0x0c: self.imr & 0xffffffff,
                    0x10: self.intfrc >> 32, 0x14: self.intfrc & 0xffffffff}.get(off, 0)
        if 0x40 <= off < 0x80 and size == 1:
            return self.icr[off - 0x40]
        return (1 << (size * 8)) - 1

    def write(self, off, size, val):
        if off == 0x08 and size == 4:
            self.imr = (val << 32) | (self.imr & 0xffffffff)
        elif off == 0x0c and size == 4:
            self.imr = (self.imr & ~0xffffffff) | val
        elif off in (0x10, 0x14) and size == 4:
            before = self.intfrc
            if off == 0x10:
                self.intfrc = (val << 32) | (self.intfrc & 0xffffffff)
            else:
                self.intfrc = (self.intfrc & ~0xffffffff) | val
            if self.intfrc & ~before and self.on_force:
                self.on_force(self, self.intfrc & ~before)
        elif off == 0x1c and size == 1:      # SIMR: set mask
            self.imr = 0xffffffff_ffffffff if val & 0x40 else self.imr | (1 << (val & 0x3f))
        elif off == 0x1d and size == 1:      # CIMR: clear mask
            # ...and MASKALL (IMRL bit 0) with it: nothing in the image ever
            # writes IMRH/IMRL (literal scan, 6 Sep 2026), the firmware unmasks
            # only through CIMR, and the unit takes interrupts. Inferred.
            self.imr = 0 if val & 0x40 else self.imr & ~((1 << (val & 0x3f)) | 1)
        elif 0x40 <= off < 0x80 and size == 1:
            self.icr[off - 0x40] = val & 7


class Uart:
    """One of the serial blocks at 0xfc064000/0xfc068000, modelled from the
    firmware's own use of it (handler 0x400109bc, ring writer 0x40010b1c,
    polled sender 0x40010a4c; read 6 Sep 2026):
      +0x04 status: bit 0 = receive ready (must read 0 with nothing queued,
            or the handler's receive loop never ends), bit 2 = transmit ready
            (the code loads the byte into CCR and tests Z);
      +0x0c data: read = next received byte, write = one byte sent;
      +0x14 mask: 3 = transmit + receive interrupts, 2 = receive only.
    Transmit is always ready here, so the line is asserted exactly while the
    transmit interrupt is enabled -- the handler drains the ring and drops
    the mask to 2 itself. Every byte sent is kept in `tx`.
    """
    RXRDY, TXRDY = 1, 4

    def __init__(self, name, base):
        self.name, self.base = name, base
        self.imr = 0
        self.regs = {}
        self.tx = bytearray()
        self.rx = collections.deque()

    @property
    def irq(self):
        return bool(self.imr & 1) or (bool(self.imr & 2) and bool(self.rx))

    def read(self, off, size):
        if off == 0x04:
            return self.TXRDY | (self.RXRDY if self.rx else 0)
        if off == 0x0c:
            return self.rx.popleft() if self.rx else 0
        if off == 0x14:
            return self.imr
        return self.regs.get(off, (1 << (size * 8)) - 1)

    def write(self, off, size, val, replay=False):
        if off == 0x0c:
            if not replay:
                self.tx.append(val & 0xff)
        elif off == 0x14:
            self.imr = val & 0xff
        else:
            self.regs[off] = val


class Dspi:
    """The DSPI at 0xfc05c000 as a loopback: every frame pushed (PUSHR +0x34)
    yields one received frame (POPR +0x38, value 0), and the status register
    (+0x2c) reports the receive count in bits 4-7 with TCF (31) and TFFF (25)
    set. Sites read 6 Sep 2026: 0x4001c398 pushes three and waits for three;
    0x40040b94 waits for two (the card boot's fixed reply of 2, which can
    never satisfy the first). What sits on the far end is not modelled: the
    reply is 0 and the config registers are stored and read back.
    """
    SR, PUSHR, POPR = 0x2c, 0x34, 0x38

    def __init__(self):
        self.rx = collections.deque()
        self.regs = {}
        self.pushed = 0

    def read(self, off, size):
        if off == self.SR:
            return 0x82000000 | (min(len(self.rx), 15) << 4)
        if off == self.POPR:
            return self.rx.popleft() if self.rx else 0
        return self.regs.get(off, (1 << (size * 8)) - 1)

    def write(self, off, size, val, replay=False):
        if off == self.PUSHR:
            if not replay:
                self.rx.append(0)
                self.pushed += 1
        elif off != self.SR:
            self.regs[off] = val


MEDIA_KICK = 0xfc0b01bc
MEDIA_KICK_VAL = 0x00020002
# The card-detect interrupt handler (0x4001e594, vector 0xaf source 47) kicks
# whatever sits at 0xfc0b01bc (writes 0x00010001, later 0x00010000 swapped)
# and spins reading it back until bits 0/16 (the ones the busy mask 0x10001
# tests) clear -- a start/busy register for a block nothing else in this
# trace touches (not the ATA task-file window; a card-presence debounce or a
# small DMA channel, address range unidentified further, 6 Sep 2026). Once
# clear, the SAME handler re-reads the register and tests bits 1/17
# separately, gating the two posts to the storage queue (0x4001e844,
# 0x4001e8fc) that a fully all-ones or fully-zero reply both defeat: all-ones
# never clears the busy bits (infinite spin, found first); all-zero clears
# them but also clears 1/17, so neither post fires and the "card present"
# outcome we know is correct (a card genuinely is attached) never triggers.
# Modelled as a constant reply with 0/16 clear (instant completion) and 1/17
# set (the detect IS relevant) -- inferred from what the two readings must
# mean for the branch we know should be taken, not from a spec for the block.


EDMA = 0xfc044000                  # MCF5445x eDMA: control at +0x0000, TCDs at +0x1000
EDMA_TCD = 0xfc045000              # 16 channels x 32 bytes: SADDR +0, ATTR/SOFF +4, NBYTES +8,
                                   # SLAST +0xc, DADDR +0x10, CITER +0x14, DOFF +0x16,
                                   # DLAST_SGA +0x18, BITER +0x1c, CSR +0x1e


class Edma:
    """The MCF5445x eDMA, as far as the DSP frame exchange and the ColdFire's
    per-frame EMAC work use it (read 6 Sep 2026, Fable review of M6c).

    Registers: TCDs at 0xfc045000, 32 bytes per channel (SADDR +0, NBYTES
    +8, DADDR +0x10, CITER +0x14, BITER +0x1c, CSR +0x1e); control bytes at
    0xfc04401c CINT (clear a channel's request; 0x40 = all), +0x1e SSRT
    (software-start a channel), +0x1f CDNE (clear DONE). A channel starts by
    SSRT or by CSR.START (bit 0). On completion: DONE (CSR bit 7) is set; if
    CSR.INTMAJOR (bit 1) its INTC0 source (8 + channel) is asserted until
    CINT; if CSR.MAJORELINK (bit 5) the channel MAJORLINKCH (CSR bits 8-12)
    starts. That last rule IS the audio chain the frame handler kicks: ch1
    CSR 0x621 links to ch6, ch6's 0x720 links to ch7, ch7's 0x0002 raises
    source 15 -- and the seven-step completion ISR (0x40004840, jump table
    on 0x46104d3e at 0x400ab61a, state 7 = the frame-source unmask at
    0x40004bc0) then SSRTs ch1 and ch0 in turn (sources 9, 8).

    No data moves (audio is out of route A's scope, RTOS_FORK.md section 1;
    M5 ran 12,000 frames with no DSP at all). Completion TIMING is the one
    thing that has to be right, because the exchange is a two-frame
    pipeline with ~64k+ instructions of EMAC work (0x400031a0) inside it.
    Three kinds of transfer, told apart by how they start and what they
    touch (TCDs read 6 Sep 2026: ch0 RAM->0x2000001c, ch1/6/7 0x2000001c->RAM,
    ch2/3 0x4f502c10->RAM, i.e. the delay ring the stock-delay finding
    named):
    - a CSR.START of a host-port channel is the frame's audio stream; the
      chain it links (1 -> 6 -> 7) is one frame of DSP data and completes
      at the DSP's next 16-sample boundary, as a whole -- the DSP delivers
      on its own clock, not "kick + 16" (that gave an 18.5-sample period and
      dropped every sixth frame), and not instantly (that re-raised source
      15 before state 0 could ack it and the ISR spun in state 6);
    - an SSRT is one of the ISR's 256-byte control transfers over the same
      host port: bus-speed, completes at once;
    - a CSR.START of a memory-to-memory channel (0x400031a0's ch2, linked
      to ch3) is a copy the caller busy-waits for at 0x400035a8: at once --
      holding it for a frame spun forever.
    ch0 and ch1 carry INTMAJOR from boot (CSR 0x0002 at the handoff), so
    nothing here asserts a source the TCD doesn't ask for.
    """
    SSRT, CINT, CDNE = 0x1e, 0x1c, 0x1f
    START, INTMAJOR, MAJORELINK, DONE = 0x0001, 0x0002, 0x0020, 0x0080
    HOSTPORT = (0x20000000, 0x20001000)

    def __init__(self):
        self.tcd = bytearray(16 * 32)
        self.regs = {}
        self.irq = [False] * 16
        self.started = 0
        self.due = {}                       # channel -> sample at which it completes
        self.now = 0.0                      # kept current by Rtos._tick_timers
        self.boundary = FRAME_PERIOD        # the DSP's next frame boundary (Rtos keeps it current)

    def _u(self, ch, off, n):
        return int.from_bytes(self.tcd[ch * 32 + off:ch * 32 + off + n], "big")

    def _csr(self, ch):
        return self._u(ch, 0x1e, 2)

    def _set_csr(self, ch, v):
        self.tcd[ch * 32 + 0x1e:ch * 32 + 0x20] = (v & 0xffff).to_bytes(2, "big")

    def _paced(self, ch):
        lo, hi = self.HOSTPORT
        return any(lo <= self._u(ch, o, 4) < hi for o in (0, 0x10))

    def tcd_fields(self, ch):
        """the channel's TCD as a dict (MCF5445x eDMA, chapter 19)"""
        return dict(saddr=self._u(ch, 0, 4), soff=self._u(ch, 4, 2), attr=self._u(ch, 6, 2),
                    nbytes=self._u(ch, 8, 4), slast=self._u(ch, 0xc, 4), daddr=self._u(ch, 0x10, 4),
                    citer=self._u(ch, 0x14, 2), doff=self._u(ch, 0x16, 2),
                    dlast=self._u(ch, 0x18, 4), biter=self._u(ch, 0x1c, 2), csr=self._csr(ch))

    on_transfer = None          # (ch, paced, fields) -- the TAPE hook (tier 2, 7 Sep 2026)

    def _start(self, ch, paced):
        if self.on_transfer is not None:
            self.on_transfer(ch, paced, self.tcd_fields(ch))
        self._set_csr(ch, self._csr(ch) & ~self.DONE)
        self.started += 1
        if paced:                            # the DSP delivers its frame on ITS clock
            self.due.setdefault(ch, self.boundary)
        else:
            self._complete(ch)

    def _complete(self, ch):
        csr = self._csr(ch)
        self._set_csr(ch, (csr & ~self.START) | self.DONE)
        if csr & self.INTMAJOR:
            self.irq[ch] = True
        if csr & self.MAJORELINK:                # the linked channel is the same
            self._start((csr >> 8) & 0x1f, False)  # burst: completes with its parent

    def advance(self, now):
        self.now = now
        for ch in [c for c, t in self.due.items() if now >= t]:
            del self.due[ch]
            self._complete(ch)

    def read(self, a, size):
        if EDMA_TCD <= a < EDMA_TCD + len(self.tcd):
            off = a - EDMA_TCD
            return int.from_bytes(self.tcd[off:off + size], "big")
        return self.regs.get(a, 0)

    def write(self, a, size, val, replay=False):
        if EDMA_TCD <= a < EDMA_TCD + len(self.tcd):
            off = a - EDMA_TCD
            self.tcd[off:off + size] = (val & ((1 << (8 * size)) - 1)).to_bytes(size, "big")
            if not replay and off % 32 + size > 0x1e and (val & self.START):
                ch = off // 32
                self._start(ch, paced=self._paced(ch))
            return
        off = a - EDMA
        if off == self.SSRT and size == 1:
            if not replay:
                self._start(val & 0x0f, paced=False)
        elif off == self.CINT and size == 1:
            if val & 0x40:
                self.irq = [False] * 16
            else:
                self.irq[val & 0x0f] = False
        elif off == self.CDNE and size == 1:
            for c in (range(16) if val & 0x40 else [val & 0x0f]):
                self._set_csr(c, self._csr(c) & ~self.DONE)
        else:
            self.regs[a] = val


DSP_SELECT = 0xfc0a400c     # the GPIO that picks which DSP core the host port talks to (DSP.md section 1)


class RtosFault(Exception):
    pass


class Rtos:
    """The event loop over a booted machine. Construct via `attach()`."""

    def __init__(self, r, ips=3990.0, pit_clock_hz=264e6, quantum=4096,
                 step_quantum=32, tick=True, frame=False, trace=None):
        self.r, self.uc = r, r.uc
        self.ips = float(ips)
        self.quantum, self.step_quantum = int(quantum), int(step_quantum)
        self.tick = tick
        # M6c's frame clock (source 1) is OFF by default: main's own boot
        # tail unmasks it unconditionally (0x4001fc2e), so once modelled it
        # fires every 16 samples in EVERY run regardless of whether anything
        # needs the sequencer -- M6a's gate and M6b's load were built and
        # verified without it (~16x more dispatches otherwise: PIT0's own
        # 220-sample period is the coarsest timer beforehand). Same pattern
        # as `tick`: the register state is real either way, only the model's
        # assertion is gated.
        self.frame = frame
        self.trace = trace                   # callable(str) or None
        self.sample = 0.0
        self.instrs = 0
        self.bursts = 0
        self.wall = 0.0
        self.pc = None
        self.trap = r.trap                   # the boot's (32, HANDOFF)
        self.created = []                    # (sample, tcb, entry, prio, stack, size, creator)
        self.blocks = []                     # (sample, tcb, trap pc, caller, object, owner)
        self.last_block = {}                  # tcb -> the same tuple, O(1) lookup
        self.dispatches = []                 # (sample, tcb, pc) at every scheduler rte
        self.switches = 0
        self.forces = 0
        self.idle_skips = 0
        self.first_switch = None             # (from_tcb, to_tcb)
        self.pc_samples = collections.Counter()   # (tcb, pc) per burst end
        self.stop_reason = None
        self.unmapped = None
        self._sr_cache = None
        self._force_stop = False
        self.card = None                     # set by attach_card
        # peripheral models
        self.pit0, self.pit1 = Pit("PIT0", pit_clock_hz), Pit("PIT1", pit_clock_hz)
        self.uart64, self.uart68 = Uart("UART@fc064000", 0xfc064000), Uart("UART@fc068000", 0xfc068000)
        self.dspi = Dspi()
        self.edma = Edma()
        # M6c: the DSP frame clock (source 1, FRAME_PERIOD above). A latch:
        # set at every 16-sample boundary, cleared when delivered. Not a
        # count -- while the source is masked (boot, and the handler's own
        # self-mask for the whole DSP exchange) a real edge source remembers
        # one edge, not how many it missed; a count here delivered ~540
        # phantom frames back to back after main's unmask (measured 6 Sep
        # 2026). The handler re-arms itself only through the eDMA exchange
        # (RTOS_FORK.md section 8); the ISR's `rte` is not the ack.
        self.next_frame = FRAME_PERIOD
        self.frame_pending = False
        self.frame_count = 0
        # Sequencer ticks: deliveries of vector 0x60 (INTC0 source 32, the
        # frame handler's own forced interrupt -- §8.2). Counted so the M6c
        # report can state it instead of leaving it to be inferred from the
        # trig log; the C++ port counts the same vector's acknowledgements.
        self.tick_count = 0
        # INTC0 sources: 1 = DSP frame (vector 0x41); 27/28 -> vectors
        # 0x5b/0x5c -> handlers 0x400109bc/0x40010b88 (vector-install scan,
        # 6 Sep 2026); INTC1 source 43 = PIT0.
        # INTC0 sources 8..23 = eDMA channels 0..15 (MCF5445x); 8, 9 and 15
        # are the ones the frame exchange raises (RTOS_FORK.md section 8).
        edma_lines = {8 + c: (lambda c=c: self.edma.irq[c]) for c in range(16)}
        self.intc0 = Intc("INTC0", 64, {1: lambda: self.frame and bool(self.frame_pending),
                                        27: lambda: self.uart64.irq, 28: lambda: self.uart68.irq,
                                        **edma_lines})
        self.ata_irq = False                 # the card's INTRQ (INTC1 source 54, vector 0xb6)
        # INTC1: 43 = PIT0 (vector 171, the scheduler), 44 = PIT1 (vector 0xac,
        # the storage layer's delay timer, handler 0x40020d38), 54 = ATA (0xb6)
        self.intc1 = Intc("INTC1", 128, {43: lambda: self.tick and self.pit0.irq,
                                         44: lambda: self.pit1.irq,
                                         54: lambda: self.ata_irq})
        self.intc0.on_force = self.intc1.on_force = self._on_force

    # -- attach --------------------------------------------------------------
    def attach_card(self, card):
        """Interpose on the card's task-file window so the card raises INTRQ
        the way ATA does (handler 0x40015304, read 6 Sep 2026: one sector per
        interrupt, completion signalled when the count reaches zero):
        asserted when a command completes or a sector is ready, after each
        sector consumed with more to come, and after each sector absorbed by
        a WRITE; cleared by a read of the status register (not the alternate
        status). The card model itself is emu_card's, untouched."""
        uc = self.uc
        self.card = card

        def rd(u, off, size, d):
            v = card.read(off, size)
            if off == ec.R_CMD:
                self.ata_irq = False
            elif off == ec.R_DATA and card.dpos % ec.SECTOR == 0 and card.dpos < len(card.data):
                self.ata_irq = True
            return v

        def wr(u, off, size, val, d):
            before = card.writes
            card.write(off, size, val)
            if off == ec.R_CMD:
                self.ata_irq = (val & 0xff) != 0x30
            elif off == ec.R_DATA and card.writes > before:
                self.ata_irq = True
        uc.mem_unmap(ec.ATA_BASE, 0x1000)
        uc.mmio_map(ec.ATA_BASE, 0x1000, rd, None, wr, None)
        return self

    def watch_calls(self, addrs):
        """Log every entry to each address as (sample, task, addr, caller) in
        `self.calls` -- a cheap diagnostic (single-address code hooks)."""
        self.calls = []

        def on_call(u, addr, size, user):
            sp = u.reg_read(eb.UC_M68K_REG_A7)
            ret, arg = struct.unpack(">II", u.mem_read(sp, 8))
            self.calls.append((self.sample, self._cur(), addr, ret, arg))
            self._t(f"call {addr:#x} from {ret:#x} arg={arg:#x} in {self._name(self._cur())}")
        for a in addrs:
            self.uc.hook_add(eb.UC_HOOK_CODE, on_call, begin=a, end=a)
        self.uc.ctl_flush_tb()
        return self

    def exact_clock(self):
        """Charge bursts the instructions they actually executed (a global
        UC_HOOK_CODE counter) instead of their full quantum. ~10x slower, so
        it is switched on only where timing is load-bearing: from
        `start_transport_live` on. Why: the quantum rule bills a burst that
        stopped early on a hook or shim in full -- ~2.1x over the frame
        exchange (35.2M charged vs 16.5M executed over one window, 6 Sep
        2026) -- and the DSP exchange is a two-frame pipeline with ~64k
        instructions of EMAC work inside it, which a 2x clock error breaks."""
        if getattr(self, "_exact", None) is not None:
            return self
        self._exact = {"n": 0}

        def on_code(u, a, sz, x):
            self._exact["n"] += 1
        self.uc.hook_add(eb.UC_HOOK_CODE, on_code, begin=1, end=0xffffffff)
        self.uc.ctl_flush_tb()
        return self

    def watch_pc(self, addrs):
        """Log registers each time one of `addrs` is about to execute."""
        regs = [("d0", eb.UC_M68K_REG_D0), ("d1", eb.UC_M68K_REG_D1), ("a0", eb.UC_M68K_REG_A0),
                ("a1", eb.UC_M68K_REG_A1), ("a3", eb.UC_M68K_REG_A3), ("sp", eb.UC_M68K_REG_A7),
                ("sr", eb.UC_M68K_REG_SR)]

        # Kept in a list AND traced: the trace-only form printed nothing
        # without --trace -- the third silent instrument of 6 Sep 2026
        # (after --watch-calls and --watch-mem). The CLI prints the list.
        self.pc_hits = getattr(self, "pc_hits", [])

        def on_pc(u, addr, size, user):
            vals = " ".join(f"{n}={u.reg_read(r) & 0xffffffff:#x}" for n, r in regs)
            # the return address and the first four stack args, so a hit on
            # a callee (a kernel post, say) names its caller and arguments
            sp = u.reg_read(eb.UC_M68K_REG_A7)
            try:
                st = u.mem_read(sp, 20)
                stack = " ".join(f"{int.from_bytes(st[i:i+4], 'big'):#x}" for i in range(0, 20, 4))
            except Exception:
                stack = "?"
            line = (f"at {addr:#x} {vals} cur={self._cur():#x} in {self._name(self._cur())}"
                    f" [sp: {stack}]")
            if len(self.pc_hits) < 2000:
                self.pc_hits.append((self.sample, line))
            self._t(line)
        for a in addrs:
            self.uc.hook_add(eb.UC_HOOK_CODE, on_pc, begin=a, end=a)
        self.uc.ctl_flush_tb()
        return self

    def watch_mem(self, addr, length):
        """Log every write into [addr, addr+length) as (sample, task, pc,
        address, size, value) in `self.mem_writes` -- a diagnostic."""
        self.mem_writes = []

        def on_write(u, acc, a, size, val, user):
            pc = u.reg_read(eb.UC_M68K_REG_PC)
            self.mem_writes.append((self.sample, self._cur(), pc, a, size, val))
            self._t(f"write [{a:#x}] <- {val:#x} ({size}) at {pc:#x} in {self._name(self._cur())}")
        self.uc.hook_add(eb.UC_HOOK_MEM_WRITE, on_write, begin=addr, end=addr + length - 1)
        self.uc.ctl_flush_tb()
        return self

    def install(self):
        uc = self.uc
        vec = int.from_bytes(uc.mem_read(VBR + 0x80, 4), "big")
        if vec != SCHED:
            raise RtosFault(f"vector 32 -> {vec:#x}, expected the scheduler {SCHED:#x}")
        vec171 = int.from_bytes(uc.mem_read(VBR + 4 * 171, 4), "big")
        if vec171 != SCHED:
            raise RtosFault(f"vector 171 -> {vec171:#x}, expected the scheduler {SCHED:#x}")
        # Main's init reads a magic word at 0x1ffffe (0x4003232c: == 0xdcba means
        # a test-mode flash); the boot maps only the first 64 KB. Zero = no magic.
        # The settings reset (0x4001f298) clears 0x100fff04..0x10100004, four
        # bytes past the SRAM window (a firmware off-by-four hardware absorbs).
        for base, size in ((0x00010000, 0x001f0000), (0x10100000, 0x1000)):
            try:
                uc.mem_map(base, size)
            except eb.UcError:
                pass
        uc.mem_write(SR_TRAMP, bytes.fromhex("40c0" "4e71"))     # movew %sr,%d0 ; nop
        # MAC-with-load words the core would run natively and wrongly: stop
        # BEFORE them (a code hook's emu_stop lands before the instruction,
        # measured 8 Sep 2026) and hand them to the shim as if they had
        # trapped. See emu_bringup.native_macload_sites.
        self.native_macload = eb.native_macload_sites(uc)
        for site in self.native_macload:
            uc.hook_add(eb.UC_HOOK_CODE, self._on_native_macload, begin=site, end=site)
        if self.frame:
            self.exact_clock()               # frame mode is timing-load-bearing throughout
        # the whole window, not a sub-range: Unicorn's MMIO split is unproven here
        uc.mem_unmap(PERIPH_BASE, PERIPH_SIZE)
        uc.mmio_map(PERIPH_BASE, PERIPH_SIZE,
                    lambda u, off, size, d: self._pread(PERIPH_BASE + off, size), None,
                    lambda u, off, size, val, d: self._pwrite(PERIPH_BASE + off, size, val), None)
        # Seed the models with what the boot wrote into the generic stub before
        # we existed: attach() logs every write to the window (7,886 on the
        # stock image) and we replay them in order. Without a log, fall back to
        # the handful read from the image (0x400005a8..f6, 0x40010fb2..ba).
        boot_writes = getattr(self.r, "rtos_boot_writes", None)
        if boot_writes:
            for a, size, val in boot_writes:
                val &= (1 << (size * 8)) - 1
                # An all-ones value is a read-modify-write of the stub's
                # all-ones reply (PIT0's `PCSR |= 9` arrives as 0xffff), not a
                # value the firmware chose: skip it. Nothing in the boot writes
                # all-ones on purpose (7,886 writes, stock image, 6 Sep 2026).
                if val == (1 << (size * 8)) - 1:
                    continue
                self._pwrite(a, size, val, replay=True)
            self.seeded = len(boot_writes)
            # Boot artefact: the boot enables the transmit interrupt from its
            # ring writer, and on hardware the driver's handler (installed at
            # 0x40010faa) drains the ring during the boot, before the kernel
            # init at 0x40000db0 refills every vector slot with the trampoline
            # 0x40000d74. The cold boot here takes no interrupts, so the mask
            # arrives at the handoff still armed with the trampoline as its
            # handler, which storms. Main re-installs the handler (0x40010efc)
            # and re-arms transmit on its first write; the ring's leftover
            # bytes go out then. Inferred from the storm, not measured.
            for u in (self.uart64, self.uart68):
                u.imr &= ~1
        else:
            self.pit0.seed(0x0b3f, 643, self.sample)
            self.intc1.icr[43] = 1
            self.intc1.write(0x1d, 1, 43)
            self.intc0.icr[27] = 6
            self.intc0.write(0x1d, 1, 27)
            self.seeded = 0

        def on_create(u, addr, size, user):
            sp = u.reg_read(eb.UC_M68K_REG_A7)
            args = struct.unpack(">5I", u.mem_read(sp + 4, 20))
            self.created.append((self.sample,) + args + (self._cur(),))
            self._t(f"create tcb={args[0]:#x} entry={args[1]:#x} prio={args[2]} "
                    f"stack={args[3]:#x}+{args[4]:#x} by {self._name(self._cur())}")
        uc.hook_add(eb.UC_HOOK_CODE, on_create, begin=CREATE, end=CREATE)

        def on_idle(u, addr, size, user):
            self._force_stop = "idle"
            u.emu_stop()
        uc.hook_add(eb.UC_HOOK_CODE, on_idle, begin=MAIN_SPIN, end=MAIN_SPIN)

        def on_unmapped(u, access, addr, size, value, user):
            self.unmapped = (access, addr, size, u.reg_read(eb.UC_M68K_REG_PC))
            return False
        uc.hook_add(eb.UC_HOOK_MEM_READ_UNMAPPED | eb.UC_HOOK_MEM_WRITE_UNMAPPED, on_unmapped)
        uc.ctl_flush_tb()
        return self

    # -- peripheral window ---------------------------------------------------
    def _pread(self, a, size):
        if INTC0 <= a < INTC0 + 0x100:
            return self.intc0.read(a - INTC0, size)
        if INTC1 <= a < INTC1 + 0x100:
            return self.intc1.read(a - INTC1, size)
        if PIT0 <= a < PIT0 + 0x10:
            return self.pit0.read(a - PIT0, size, self.sample)
        if PIT1 <= a < PIT1 + 0x10:
            return self.pit1.read(a - PIT1, size, self.sample)
        for u in (self.uart64, self.uart68):
            if u.base <= a < u.base + 0x20:
                return u.read(a - u.base, size)
        if DSPI <= a < DSPI + 0x100:
            return self.dspi.read(a - DSPI, size)
        if EDMA <= a < EDMA + 0x2000:
            return self.edma.read(a, size)
        if a == MEDIA_KICK:
            return MEDIA_KICK_VAL
        v = PLL_VAL if a == PLL_REG else eb.EXTRA_OVERRIDES.get(a, (1 << (size * 8)) - 1)
        if callable(v):
            v = v(self.uc, a, size)
        return v

    def _pwrite(self, a, size, val, replay=False):
        if INTC0 <= a < INTC0 + 0x100:
            self.intc0.write(a - INTC0, size, val)
        elif INTC1 <= a < INTC1 + 0x100:
            self.intc1.write(a - INTC1, size, val)
        elif PIT0 <= a < PIT0 + 0x10:
            self.pit0.write(a - PIT0, size, val, self.sample)
        elif PIT1 <= a < PIT1 + 0x10:
            self.pit1.write(a - PIT1, size, val, self.sample)
        elif DSPI <= a < DSPI + 0x100:
            self.dspi.write(a - DSPI, size, val, replay=replay)
        elif EDMA <= a < EDMA + 0x2000:
            self.edma.write(a, size, val, replay=replay)
        else:
            if a == DSP_SELECT and not replay and self._tape is not None:
                self._tape_rec("gpio", val=val & 0xff)
            for u in (self.uart64, self.uart68):
                if u.base <= a < u.base + 0x20:
                    u.write(a - u.base, size, val, replay=replay)

    def _on_force(self, intc, bits):
        # a reschedule request: end the burst so it is seen within the instruction
        self.forces += 1
        self._force_stop = "force"
        self.uc.emu_stop()

    # -- exception plumbing --------------------------------------------------
    def _sr(self):
        """The true SR. NOT `reg_read(SR)`: at a burst boundary Unicorn
        2.1.4's m68k SR read computes the condition codes wrong AND installs
        them, so the next conditional branch goes the wrong way (measured
        6 Sep 2026 with a cmpl/bne pair split across a burst: Z lost, branch
        taken; reading D2 instead is harmless). Executing `movew %sr,%d0`
        from a trampoline flushes the flags through the translator's own
        path and returns them intact. Cached until the next burst."""
        if self._sr_cache is None:
            uc = self.uc
            d0 = uc.reg_read(eb.UC_M68K_REG_D0)
            uc.emu_start(SR_TRAMP, 0, count=1)
            self._sr_cache = uc.reg_read(eb.UC_M68K_REG_D0) & 0xffff
            uc.reg_write(eb.UC_M68K_REG_D0, d0)
        return self._sr_cache

    def _push(self, vec, ret_pc, new_sr):
        uc = self.uc
        sr = self._sr()
        sp = uc.reg_read(eb.UC_M68K_REG_A7) - 8
        uc.mem_write(sp, struct.pack(">HHI", 0x4000 | (vec << 2), sr, ret_pc & 0xffffffff))
        uc.reg_write(eb.UC_M68K_REG_SR, new_sr)      # SR before A7 (bank select)
        self._sr_cache = new_sr
        uc.reg_write(eb.UC_M68K_REG_A7, sp)
        self.pc = int.from_bytes(uc.mem_read(VBR + 4 * vec, 4), "big")

    def _pop(self, rte_pc):
        uc = self.uc
        sp = uc.reg_read(eb.UC_M68K_REG_A7)
        fmt, sr, pc = struct.unpack(">HHI", uc.mem_read(sp, 8))
        if fmt >> 12 != 4:
            raise RtosFault(f"rte at {rte_pc:#x}: frame format {fmt:#06x} is not a 4-word frame")
        if not sr & 0x2000:
            raise RtosFault(f"rte at {rte_pc:#x} would return to user mode (SR {sr:#06x})")
        uc.reg_write(eb.UC_M68K_REG_SR, sr)          # SR before A7
        self._sr_cache = sr
        uc.reg_write(eb.UC_M68K_REG_A7, sp + 8)
        self.pc = pc
        if rte_pc == SCHED_RTE:
            cur = self._cur()
            if self.dispatches and self.dispatches[-1][1] != cur:
                self.switches += 1
            self.dispatches.append((self.sample, cur, pc))
            self._t(f"dispatch -> {self._name(cur)} pc={pc:#x} sr={sr:#06x}")

    def _cur(self):
        return int.from_bytes(self.uc.mem_read(CUR_TCB, 4), "big")

    def _name(self, tcb):
        return TASK_NAMES.get(tcb, f"{tcb:#x}")

    def _on_native_macload(self, u, addr, size, x):
        self.r.trap = (4, addr)
        u.emu_stop()

    def _handle_trap(self):
        intno, pc = self.trap
        self.trap = None
        if intno == 32:
            frm = self._cur()
            # a primitive's trap: [sp] = its caller, [sp+4] = its object
            sp = self.uc.reg_read(eb.UC_M68K_REG_A7)
            # event/semaphore waits trap with [sp]=caller,[sp+4]=object; the
            # lock primitive 0x400009f4 traps at 0x40000a78 under 12 bytes of
            # saved registers, and its object's first word is the owner TCB
            if pc == LOCK_TRAP:
                caller, obj = struct.unpack(">II", self.uc.mem_read(sp + 12, 8))
                owner = int.from_bytes(self.uc.mem_read(obj, 4), "big")
            else:
                caller, obj = struct.unpack(">II", self.uc.mem_read(sp, 8))
                owner = None
            entry = (self.sample, frm, pc, caller, obj, owner)
            self.blocks.append(entry)
            self.last_block[frm] = entry
            self._push(32, pc + 2, (self._sr() | 0x2000) & ~0x8000)
            if self.first_switch is None:
                self.first_switch = [frm, None]
            self._t(f"trap #0 at {pc:#x} from {self._name(frm)} caller={caller:#x} obj={obj:#x}")
            return
        if intno == 256:
            self._pop(pc)
            if self.first_switch and self.first_switch[1] is None and pc == SCHED_RTE:
                self.first_switch[1] = self._cur()
            return
        r = self.r
        r.trap = (intno, pc)
        npc = eb._isa_c_shim(self.uc, r) or eb._movem_shim(self.uc, r) or eb._emac_load_shim(self.uc, r)
        r.trap = None
        if npc is None:
            raise RtosFault(f"unhandled exception {intno} at {pc:#x} in {self._name(self._cur())}")
        self.pc = npc

    # -- interrupts ----------------------------------------------------------
    def _candidates(self):
        out = []
        for intc in (self.intc0, self.intc1):
            for level, src in intc.pending():
                out.append((level, intc.vec_base + src, intc.name, src))
        out.sort(reverse=True)
        return out

    def _deliver(self):
        c = self._candidates()
        if not c:
            return False
        level, vec, name, src = c[0]
        ipl = (self._sr() >> 8) & 7
        if level <= ipl:
            return False
        sr = self._sr()
        self._push(vec, self.pc, (sr & ~0x8700) | 0x2000 | (level << 8))
        if name == "INTC0" and src == 1:
            self.frame_pending = False
            self.frame_count += 1
        if vec == 0x60:
            self.tick_count += 1
        self._t(f"irq {name} src {src} vec {vec} level {level} -> {self.pc:#x} (was ipl {ipl})")
        return True

    def _masked_pending(self):
        c = self._candidates()
        return bool(c) and c[0][0] <= ((self._sr() >> 8) & 7)

    def _next_expiry(self):
        ex = [p.expiry for p in (self.pit0, self.pit1) if p.expiry is not None]
        if self.frame:
            ex.append(self.next_frame)
        return min(ex) if ex else None

    # -- the loop ------------------------------------------------------------
    def _t(self, s):
        if self.trace:
            self.trace(f"[{self.sample:10.1f}] {s}")

    def step(self):
        uc = self.uc
        if self.trap:
            self._handle_trap()
        while self._deliver():
            pass
        if self.pc == MAIN_SPIN and not self._candidates():
            ex = self._next_expiry()
            if ex is None:
                raise RtosFault("idle at main's spin with no timer armed: deadlock")
            self.sample = max(self.sample, ex)
            self.idle_skips += 1
            self._tick_timers()
            return
        n = self.quantum
        if self._masked_pending():
            n = self.step_quantum
        ex = self._next_expiry()
        if ex is not None:
            n = max(1, min(n, int((ex - self.sample) * self.ips) + 1))
        self.r.trap = None
        self._force_stop = None
        self._sr_cache = None
        t0 = time.perf_counter()
        ex = getattr(self, "_exact", None)
        if ex is not None:
            ex["n"] = 0
        uc.emu_start(self.pc, 0, count=n)
        self.wall += time.perf_counter() - t0
        self.bursts += 1
        if ex is not None:
            n = ex["n"]                      # what actually ran, not the quantum
        self.instrs += n
        self.sample += n / self.ips
        self.trap = self.r.trap
        self.pc = self.trap[1] if self.trap else uc.reg_read(eb.UC_M68K_REG_PC)
        self.pc_samples[(self._cur(), self.pc)] += 1
        self._tick_timers()

    # -- THE TAPE (tier 2 of the emulator uplift, 7 Sep 2026) ----------------
    # Everything the ColdFire pushes towards the DSPs, in order, with the frame
    # it happened in: every eDMA transfer whose source or destination is the
    # host-port window (the TCD's fields and the source bytes, read at the
    # kick), every CPU write into the host-port window (the 0x81 / 0x8C
    # commands and whatever else the frame handler pokes), and every write of
    # the DSP-select GPIO (which core the window is talking to). Replayed into
    # the two-core dsp_host, this is the sequencer's parameter motion --
    # scenes, p-locks, LFOs, CC -- driving the DSP without the ColdFire in
    # the loop. JSON lines; the decoder lives beside the replayer.
    _tape = None

    def tape(self, path):
        import json
        self._tape = open(path, "w")
        self._tape_n = 0
        self._tape_json = json

        def on_transfer(ch, paced, f):
            lo, hi = self.edma.HOSTPORT
            src_host = lo <= f["saddr"] < hi
            dst_host = lo <= f["daddr"] < hi
            if not (src_host or dst_host):
                return
            rec = dict(kind="edma", ch=ch, paced=paced, **f)
            if not src_host:
                # source in RAM: the bytes the DSP is about to receive. One
                # major loop is BITER minor loops of NBYTES; the source walks
                # SOFF per element, so the span is NBYTES x BITER when SOFF
                # is nonzero (a fixed source would be a peripheral register).
                n = f["nbytes"] * max(1, f["biter"]) if f["soff"] else f["nbytes"]
                n = min(n, 0x10000)
                rec["data"] = bytes(self.uc.mem_read(f["saddr"], n)).hex()
            self._tape_rec(**rec)
        self.edma.on_transfer = on_transfer

        def on_hostw(u, acc, addr, size, val, x):
            self._tape_rec("hostw", addr=addr, size=size, val=val & ((1 << (8 * size)) - 1),
                           pc=u.reg_read(eb.UC_M68K_REG_PC))
        lo, hi = self.edma.HOSTPORT
        self.uc.hook_add(eb.UC_HOOK_MEM_WRITE, on_hostw, begin=lo, end=hi - 1)
        return self

    def _tape_rec(self, kind=None, **kw):
        rec = dict(n=self._tape_n, frame=self.frame_count, sample=round(self.sample, 1),
                   kind=kind or kw.pop("kind"), **kw)
        self._tape.write(self._tape_json.dumps(rec) + "\n")
        self._tape_n += 1

    def _tick_timers(self):
        if self.pit0.advance(self.sample):
            self._t(f"PIT0 expiry #{self.pit0.fired}")
        self.pit1.advance(self.sample)
        if self.frame:
            while self.sample >= self.next_frame:
                self.frame_pending = True       # a latch, not a count: a masked
                self.next_frame += FRAME_PERIOD  # edge source remembers ONE edge
        self.edma.boundary = self.next_frame
        self.edma.advance(self.sample)

    def run(self, ms=None, until=None, max_bursts=None):
        """Run until `ms` emulated milliseconds elapse, `until(self)` is true,
        or `max_bursts` bursts. Returns the reason."""
        end = None if ms is None else self.sample + ms * SAMPLE_HZ / 1000.0
        n = 0
        while True:
            if until is not None and until(self):
                self.stop_reason = "until"; return self.stop_reason
            if end is not None and self.sample >= end:
                self.stop_reason = "time"; return self.stop_reason
            if max_bursts is not None and n >= max_bursts:
                self.stop_reason = "bursts"; return self.stop_reason
            self.step(); n += 1

    def arm_phase_fix(self):
        """RETIRED 7 Sep 2026 (RTOS_FORK section 10.16): the negative timing
        byte this lever cleared was an artefact of stock Unicorn's halved
        fractional EMAC; with the fixed library (scripts/build_unicorn.sh)
        the trig arms on its own at every tempo tried. Kept, logged, harmless.

        COMPENSATION, not fidelity (RTOS_FORK section 10.14, 7 Sep 2026):
        at the recorder arm caller's entry (0x40005ff0) clear bit 7 of the
        trig word when the track has NO recorder record yet (state byte +2
        zero in both banks of 0x80004f1c). Bit 7 is the sign of the frame
        builder's per-lane timing byte (16 + 8/frame toward the event); the
        arm caller takes a negative one as "a follow-up on an existing
        recording" and, finding no record, returns -1 -- the trig is dropped.
        Under route A that byte wanders across the whole tick period because
        nothing re-locks the sequencer's step clock (0x4610757c) to the frame
        clock (0x46104cf0): the tick-side resync at 0x400a1e92 is gated on
        the CLOCK RECEIVE bit (0x80000028 bit 0, which --internal-clock
        clears) and on 0x46104ca8 (zero here), so about half the tempos drop
        a first recorder trig (100/120/125/135 arm, 110/115/128/140 do not,
        bank A step 2; bank B: 100/128/140 arm, 120 does not). Hardware
        records at all of them. Until the lock is modelled, this lever makes
        the trig arm as if its offset were non-negative; every use is logged
        in self.arm_fixes as (sample, track, word)."""
        self.arm_fixes = []

        def on_entry(u, addr, size, user):
            sp = u.reg_read(eb.UC_M68K_REG_A7)
            track, word = struct.unpack(">II", u.mem_read(sp + 4, 8))
            if not (word & 0x80) or track > 7:
                return
            states = [u.mem_read(0x80004f1c + bank * 672 + track * 84 + 2, 1)[0] for bank in (0, 1)]
            if any(states):
                return
            u.mem_write(sp + 8, struct.pack(">I", word & ~0x80))
            self.arm_fixes.append((self.sample, track, word))
            self._t(f"arm-phase-fix track {track} word {word:#x} -> {word & ~0x80:#x}")
        self.uc.hook_add(eb.UC_HOOK_CODE, on_entry, begin=0x40005ff0, end=0x40005ff0)
        self.uc.ctl_flush_tb()
        return self

    def call_as_main(self, addr, args=(), budget=4_000_000):
        """Borrow main's idle slot to call an OS subroutine the way a UI
        action would call it -- not a cold detour: the normal trap-dispatch
        loop stays live underneath, so any REAL waits inside the call run
        correctly against every other task and interrupt. Requires
        `self.pc == MAIN_SPIN` (run with `until=lambda r: r.pc == MAIN_SPIN`
        first). Convention matches the sites calling FW_POST_LOAD_PROJECT
        (`pea a1; pea a0; jsr addr`): retaddr at [sp], args at [sp+4],
        [sp+8], ... in the order given. Returns D0 once the call `rts`s back
        to the spin.

        ONLY for a call that CANNOT genuinely block (post/signal, or a query
        confirmed instant). Main is priority 0 and never legitimately blocks
        on hardware -- Fact 1, RTOS_FORK.md -- so it is the kernel's de facto
        idle backstop: main being non-ready is a state the block path never
        expects. Borrowing main to call FW_CARD_INIT (which waits on a real
        timer) proved this the hard way (6 Sep 2026): main blocked, nothing
        else was ready either, and the scheduler dispatched a garbage TCB
        (`rte ... would return to user mode`). A call that can block belongs
        to a real task instead -- post it a message and let it run for real
        (see `request_card_mount`)."""
        if self.pc != MAIN_SPIN:
            raise RtosFault(f"call_as_main({addr:#x}): pc is {self.pc:#x}, not the main spin")
        uc = self.uc
        sp = uc.reg_read(eb.UC_M68K_REG_A7) - 4 * (1 + len(args))
        uc.mem_write(sp, struct.pack(f">{1 + len(args)}I", MAIN_SPIN, *args))
        uc.reg_write(eb.UC_M68K_REG_A7, sp)
        self.pc = addr
        n = 0
        while self.pc != MAIN_SPIN:
            self.step()
            n += 1
            if n > budget:
                raise RtosFault(f"call_as_main({addr:#x}) did not return in {budget} steps")
        return uc.reg_read(eb.UC_M68K_REG_D0)

    def post_message(self, queue, msg):
        """`0x40000c3c(queue, msg)` -- the kernel post primitive, guaranteed
        non-blocking (a post/signal can never itself wait), so safe through
        `call_as_main` regardless of what the woken task goes on to do."""
        return self.call_as_main(KERNEL_POST, args=(queue, msg))

    def request_card_mount(self):
        """Post to the SYS task's own queue (0x460d17ae) the message its
        dispatch table (decoded 6 Sep 2026: table at 0x40061cfa, 78 entries,
        index = msg[0]-1) sends to table[15] = 0x40061f7c -- the case that
        checks `0x460d1cb8` (card ready) and, if clear, calls FW_CARD_INIT
        for real from SYS's own task context (priority 1, safe to block).
        msg[0]=16 selects that case; msg[1] nonzero is required to reach it
        (`tstb a2@(1)`, else the handler returns having done nothing)."""
        self.uc.mem_write(SYS_MSG_SCRATCH, bytes([16, 1]))
        return self.post_message(SYS_QUEUE, SYS_MSG_SCRATCH)

    def select_bank_live(self, bank, ms=500):
        """Switch the working bank through sys's own case (opcode 21, table[20]
        = 0x40062288 -- the very message the engine's reset posts with bank
        0, RTOS_FORK.md section 7): PART_PTR := the bank's blob, 0x4000faf0
        copies it into SRAM, the bank byte follows. Returns the bank byte."""
        self.run(until=lambda r: r.pc == MAIN_SPIN)
        self.uc.mem_write(SYS_MSG_SCRATCH, bytes([21, bank & 0x0f]))
        self.post_message(SYS_QUEUE, SYS_MSG_SCRATCH)
        self.run(ms=ms, until=lambda r: r.uc.mem_read(CUR_BANK, 1)[0] == bank)
        return self.uc.mem_read(CUR_BANK, 1)[0]

    def seq_select_live(self, bank, pattern):
        """The sequencer's own bank/pattern select, `0x400a1030(bank,
        pattern)`: the LOAD PROJECT handler's LAST step (0x40025b16, called
        with the project's bank and pattern bytes) and the sequencer init's
        (0x400a1088). It writes the sequencer's playing bank/pattern
        (0x800065bd/0x800065be and their mirrors, via 0x400a0570) -- the
        bytes FW_START_TRACK and the step handler index the bank blob by.
        Route A needs it re-issued after the load: the handler reads the
        bank byte at its end, and by then `sys` has applied the engine's
        own reset-time "select bank 0" (it runs in the handler's real card
        waits, RTOS_FORK.md section 7), so the sequencer is left on bank A
        with the pattern record of an empty bank (measured 6 Sep 2026: the
        step handler scheduled every track 3 frames out and never came
        back; cold, with no waits, gets the parsed bank). Non-blocking
        (plain stores + 0x40009e00), safe under call_as_main. Returns the
        sequencer's (bank, pattern) bytes."""
        self.run(until=lambda r: r.pc == MAIN_SPIN)
        self.call_as_main(FW_SEQ_SELECT, args=(bank, pattern))
        return self.uc.mem_read(FW_SEQ_BANK, 1)[0], self.uc.mem_read(FW_SEQ_PATTERN, 1)[0]

    def internal_clock(self):
        """Clear the project's CLOCK RECEIVE bit (0x80000028 bit 0) so the
        sequencer runs on its own clock -- with it set, as Sam's projects
        save it (the Rytm is master), the engine waits for MIDI clock that
        never comes: 400 frames, zero ticks, no trig (measured 6 Sep 2026).
        The same switch as emu_frames.py's --internal-clock."""
        midi = self.uc.mem_read(FW_MIDI_SETTINGS, 1)[0]
        self.uc.mem_write(FW_MIDI_SETTINGS, bytes([midi & ~1]))
        return midi

    def load_project_live(self, set_name, project_name, run_ms=6000, mount_ms=3000,
                          names_early=False):
        """M6b: drive a project load the way hardware would, then let the
        REAL sys, engine and storage tasks do the rest -- no engine_run_once
        stand-in, no hand-run init list. Two real actions, neither of which
        anything at boot does on its own (both are normally UI/button
        triggers): ask SYS to mount the card (`request_card_mount`, which
        blocks SYS on real ATA commands completed through vector 0xb6, not
        main -- see `call_as_main`'s docstring for why that distinction
        matters), then post LOAD PROJECT (opcode 4) to the engine's queue
        exactly as `FW_POST_LOAD_PROJECT` does. Returns (mounted, posted,
        saved_bank, final_bank, elapsed_ms): `saved_bank` is the bank the
        engine parsed from the project file's BANK= key and wrote to
        PART_PTR (None if that write never happened -- the load did not get
        that far); `final_bank` is the current bank at the end of the run.

        THE TWO CAN DIFFER, and that is a real cross-task ordering, not a
        load failure (root-caused 6 Sep 2026, correcting an earlier reading
        of this code that mistook the bank byte for the current track and
        bank A's blob for an "empty" sentinel). The engine's LOAD PROJECT
        handler starts with a reset to bank A / pattern 1 that, among other
        things, posts "select bank 0" to SYS's queue (from the pattern-load
        routine, sites 0x4000a150/0x40009638, twice), then reads the files,
        then parses BANK= and switches PART_PTR to the saved bank. SYS
        consumes the reset's queued "select bank 0" whenever the scheduler
        next gives it the CPU -- and if that is AFTER the engine's BANK=
        parse, SYS switches the working bank back to A, overriding the
        saved bank. Route B (cold) never showed this because SYS never ran
        at all there, so it froze on the engine's value. Whether hardware
        orders it the same way is exactly the class of question route A
        exists to ask; the run's dispatch log answers it for the emulator,
        and the cheap hardware observable is: does the unit come up on the
        saved bank after LOAD PROJECT?

        Deliberately does NOT call `FW_SET_PROJECT_EXISTS`: with no card
        mounted it returns near-instantly (a genuine short-circuit, which is
        why it looked call_as_main-safe at first), but once a card IS
        present it does real FAT lookups (`0x40025230`) and blocks -- the
        same main-blocks-and-nothing-else-is-ready crash `FW_CARD_INIT` hit,
        found the same way (6 Sep 2026). It is a pure diagnostic in route B
        (its result is never used to gate the load); dropping it costs
        nothing here."""
        start = self.sample
        self.run(until=lambda r: r.pc == MAIN_SPIN)
        if names_early:
            # ⚠️ AN EXPERIMENT, NOT A FIX, and it is off by default. `sys`'s
            # media case (0x4006203a) reloads the current project when
            # `strlen(0x100f8378)` is non-zero -- so whether the mount
            # triggers a SECOND load depends only on whether the name has
            # been written by the time `sys` gets the CPU. Route A writes it
            # after; the C++ port writes it before, and loads twice
            # (COLDFIRE_PORT.md O7b). Setting it early here makes route A do
            # the same, which is what turns that account from a story into a
            # measurement.
            ec.set_names(self, set_name, project_name)
        self.request_card_mount()
        self.run(ms=mount_ms, until=lambda r: int.from_bytes(
            r.uc.mem_read(0x460d1cb8, 4), "big") != 0)
        mounted = int.from_bytes(self.uc.mem_read(0x460d1cb8, 4), "big")
        self.run(until=lambda r: r.pc == MAIN_SPIN)
        ec.set_names(self, set_name, project_name)
        if not getattr(self, "_watching_part_ptr", False):
            self.watch_mem(ec.PART_PTR, 4)
            self._watching_part_ptr = True
        n0 = len(self.mem_writes)
        posted = self.call_as_main(ec.FW_POST_LOAD_PROJECT, args=(ec.FW_PROJECT_NAME,))
        self.run(ms=run_ms)
        saved = [val for _, _, pc, _, _, val in self.mem_writes[n0:] if pc == ENGINE_BANK_WRITE]
        saved_bank = (saved[-1] - BANK_BLOB) // BANK_STRIDE if saved else None
        final_bank = self.uc.mem_read(CUR_BANK, 1)[0]
        return mounted, posted, saved_bank, final_bank, (self.sample - start) / SAMPLE_HZ * 1000.0

    # -- M6c: the sequencer under the real scheduler --------------------------
    def start_transport_live(self):
        """Start the sequencer the way `emu_frames.start_transport` does
        cold, but through the real tasks: `FW_TRANSPORT(0)`'s start case
        only sets state and posts to the UI queue (`0x460d1664`, EMU.md
        M5) -- no wait primitive on that path -- and `FW_START_TRACK(t)`
        writes a per-track state byte directly, no queue at all. Both
        confirmed safe under `call_as_main` (6 Sep 2026): unlike
        `FW_CARD_INIT`, neither ever blocked in testing. This is the "M5
        detour" route RTOS_FORK.md §5 explicitly allows for M6c -- real key
        injection into the UI queue is M6d's job, not required here."""
        self.exact_clock()
        self.run(until=lambda r: r.pc == MAIN_SPIN)
        self.call_as_main(FW_TRANSPORT, args=(0,))
        for t in range(8):
            self.run(until=lambda r: r.pc == MAIN_SPIN)
            self.call_as_main(FW_START_TRACK, args=(t,))

    # -- M6d: real key injection -----------------------------------------------
    def press_key_live(self, handler, edge=0):
        """Call one of the firmware's own key-press handlers (`KEY_PLAY`,
        `KEY_REC`, `KEY_STOP`) directly, `action(edge)` -- the same shape as
        the FX2-shortcut handler in MAINMENU.md and PLAY/REC's own chosen
        entry in the per-key jump table at `0x400d2d54` (indices 24/25/26;
        the first 8 entries are the track keys, `0x4000184c` fills unused
        scan positions). Confirmed call_as_main-safe by disassembly (see the
        module header comment by `UI_QUEUE`) and empirically: run against
        `out/_testproj`, `press_key_live(KEY_PLAY)` reproduces M6c's fidelity
        gate exactly (frame 344, byte 0xd3), and `0x80000029` -- the byte
        PLAY's handler tests before doing anything -- is already nonzero
        after a real LOAD PROJECT, so no extra setup is needed. `edge=0` is
        press; the handlers never read past it in what PLAY/REC/STOP reach.
        Retracts RTOS_FORK.md's M6d premise that key events arrive via a
        post to the UI task's queue -- they don't: `UI_QUEUE` (0x460d1664)
        only carries state-change notices (FW_TRANSPORT's own post included)
        to the real UI task (TASK_NAMES's "ui", TCB 0x460d59d4); physical
        keys dispatch straight through this jump table instead."""
        self.run(until=lambda r: r.pc == MAIN_SPIN)
        return self.call_as_main(handler, args=(edge,))

    def press_play_live(self):
        """PLAY, through its own firmware handler rather than FW_TRANSPORT
        directly: sets the same clock-sync fields hardware would (only when
        CLOCK RECEIVE is on) before tail-calling FW_TRANSPORT(1). Still needs
        `FW_START_TRACK` for each track afterward, exactly as
        `start_transport_live` does -- PLAY's handler only starts the
        transport state machine, not the eight tracks."""
        self.exact_clock()
        d0 = self.press_key_live(KEY_PLAY)
        for t in range(8):
            self.run(until=lambda r: r.pc == MAIN_SPIN)
            self.call_as_main(FW_START_TRACK, args=(t,))
        return d0

    def press_rec_live(self):
        """REC, through its own firmware handler. Measured 6 Sep 2026 against
        `out/_testproj` (no track configured as a recorder): starts the
        transport exactly like PLAY (`0x800065b8` 0->1) and leaves
        `0x800066a0` (the record-arm state byte its own code tests) at 0 --
        consistent with EMU.md's open gap that the recorder-arm path needs a
        project with a track's machine set to a recorder, which this method
        does not supply. A second press does not toggle anything back off
        with no recorder armed. Does NOT call FW_START_TRACK -- unlike PLAY,
        untested here whether REC's own path reaches it for a plain project;
        pair with `press_play_live` or call FW_START_TRACK by hand if tracks
        need to run."""
        return self.press_key_live(KEY_REC)

    def poke_trig(self, step):
        """Set a trig on track 1 at `step` (1-64), same bytes as
        `emu_frames.poke_trig` (track 1's 64-step mask, big-endian, byte 7
        bit 0 = step 1) against whichever bank PART_PTR currently names."""
        # 64 steps: byte 7 - (step-1)//8, bit (step-1)%8 -- the same layout
        # ot_project.set_pattern_trig writes on disk. The 1-8 form threw
        # "bytes must be in range" at step 9 (6 Sep 2026).
        blob = int.from_bytes(self.uc.mem_read(ec.PART_PTR, 4), "big")
        at = blob + 7 - (step - 1) // 8
        v = self.uc.mem_read(at, 1)[0] | (1 << ((step - 1) % 8))
        self.uc.mem_write(at, bytes([v]))
        return v

    def watch_reads(self, addr, length, cap=200000):
        """Log READS into [addr, addr+length) as {(offset, pc): count}.

        The counterpart of `watch_mem`, for finding which fields of a
        record the firmware actually consults: the sequencer's step
        handler reads the pattern record, so watching that record says
        where a trig array is instead of guessing its offset.
        """
        self.reads = {}
        self._read_base = addr

        def on_read(u, acc, a, size, val, d):
            if len(self.reads) < cap:
                pc = u.reg_read(eb.UC_M68K_REG_PC)
                k = (a - addr, size, pc)
                self.reads[k] = self.reads.get(k, 0) + 1
        self.uc.hook_add(eb.UC_HOOK_MEM_READ, on_read, begin=addr, end=addr + length - 1)
        self.uc.ctl_flush_tb()
        return self

    def pattern_base(self):
        """Base of the CURRENT pattern's record: the bank blob plus
        `pattern * 0x8ed8` (sixteen records fill blob+0..0x8ed80, the parts
        follow -- EXTERNAL.md §6). Track 1's note-trig mask is its first
        eight bytes, which is what `poke_trig` writes."""
        blob = int.from_bytes(self.uc.mem_read(ec.PART_PTR, 4), "big")
        return blob + self.uc.mem_read(CUR_PATTERN, 1)[0] * PATTERN_STRIDE

    def poke_mask(self, off, step, track=1):
        """Set `step`'s bit in the 64-bit mask at `off` in a track's TRAC
        record, in the CURRENT pattern.

        The pattern record is eight TRAC records of **0x91a** bytes (the
        file carries them as `TRAC` sub-chunks of 0x922, tag+len more), and
        each begins with a run of 64-bit step masks at an 8-byte stride:
        `mulsl #0x91a,%d7` with d7 = track, at 0x4009d376 and every sibling
        site, is where that stride is measured from. Mask `0x00` is the one
        `poke_trig` writes; the sequencer ORs 0x00/0x08/0x10/0x18 into its
        "anything on this step" test (0x4009d382..0x4009d39a), reads a
        per-step value behind 0x40 (0x4009d3d6), and builds a per-track flag
        word in `0x46c7a6c0` out of 0x20 -> bit 12, 0x28 -> bit 13,
        0x30 -> bit 14 and 0x38 -> bits 5+8 (0x4009d93c..0x4009da12).
        """
        base = self.pattern_base() + track * TRAC_STRIDE + off
        at = base + 7 - (step - 1) // 8          # 64 steps, as poke_trig
        v = self.uc.mem_read(at, 1)[0] | (1 << ((step - 1) % 8))
        self.uc.mem_write(at, bytes([v]))
        return v

    def install_trig_log(self):
        """As `emu_frames.install_trig_log`, keyed by `self.frame_count`
        (this module's own frame clock) instead of a hand-kept counter."""
        live, words = [], []

        def on_live(u, acc, addr, size, val, d):
            val &= 0xFF
            if val:
                live.append((self.frame_count, addr - FW_LIVE_NIBBLE, val))

        def on_word(u, acc, addr, size, val, d):
            val &= 0xFFFF
            if val:
                words.append((self.frame_count, (addr - FW_TRIG_WORDS) // 2, val))

        self.uc.hook_add(eb.UC_HOOK_MEM_WRITE, on_live, begin=FW_LIVE_NIBBLE, end=FW_LIVE_NIBBLE + 7)
        self.uc.hook_add(eb.UC_HOOK_MEM_WRITE, on_word, begin=FW_TRIG_WORDS, end=FW_TRIG_WORDS + 15)
        self.uc.ctl_flush_tb()
        self.live_nibble_log, self.trig_words_log = live, words
        return live

    # -- the M6a gate --------------------------------------------------------
    def ran(self):
        return {d[1] for d in self.dispatches}

    def gate_m6a(self):
        problems = []
        got = sorted(tuple(c[1:7]) for c in self.created)
        want = sorted(EXPECTED_TASKS)
        if got != want:
            problems.append(f"created {len(got)} tasks, table differs: "
                            f"missing {[hex(t[0]) for t in want if t not in got]} "
                            f"extra {[hex(t[0]) for t in got if t not in want]}")
        missing = ALL_TCBS - self.ran()
        if missing:
            problems.append("never ran: " + ", ".join(self._name(t) for t in sorted(missing)))
        if self.first_switch != [BOOT_TCB, MAIN_TCB]:
            problems.append(f"first switch {self.first_switch}, expected boot -> main")
        return not problems, problems

    def report(self):
        lines = []
        lines.append(f"sample {self.sample:.1f} ({self.sample / SAMPLE_HZ * 1000:.2f} ms), "
                     f"{self.instrs:,} instrs charged in {self.bursts} bursts, "
                     f"{self.wall:.2f} s wall ({self.instrs / max(self.wall, 1e-9) / 1e6:.2f} M instr/s), "
                     f"{self.idle_skips} idle skips, {self.forces} INTFRC writes, PIT0 fired {self.pit0.fired}")
        lines.append(f"seeded from {self.seeded} boot writes; serial sent: "
                     f"{len(self.uart64.tx)} B on {self.uart64.name}, {len(self.uart68.tx)} B on {self.uart68.name}")
        lines.append("created:")
        for c in self.created:
            ok = tuple(c[1:7]) in EXPECTED_TASKS
            lines.append(f"  [{c[0]:9.1f}] {self._name(c[1]):8s} tcb={c[1]:#x} entry={c[2]:#x} "
                         f"prio={c[3]} stack={c[4]:#x}+{c[5]:#x} by {self._name(c[6]):8s} "
                         f"{'ok' if ok else 'NOT IN TABLE'}")
        lines.append(f"dispatches ({len(self.dispatches)}, {self.switches} switches):")
        last = None
        rows = []
        for s, t, pc in self.dispatches:
            if t != last:
                rows.append(f"  [{s:9.1f}] {self._name(t):8s} pc={pc:#x}")
            last = t
        if len(rows) > 80:                  # a 20 s sequencer run switches ~13,000 times
            rows = rows[:40] + [f"  ... {len(rows) - 80} switches elided ..."] + rows[-40:]
        lines.extend(rows)
        lines.append("last block per task (trap site, caller, object):")
        last = {}
        for smp, t, pc, caller, obj, owner in self.blocks:
            last[t] = (smp, pc, caller, obj, owner)
        for t, (smp, pc, caller, obj, owner) in sorted(last.items(), key=lambda kv: kv[1][0]):
            lines.append(f"  [{smp:9.1f}] {self._name(t):8s} at {pc:#x} caller={caller:#x} obj={obj:#x}"
                         + (f" held by {self._name(owner)}" if owner is not None else ""))
        for pit in (self.pit0, self.pit1):
            lines.append(f"{pit.name}: pcsr={pit.pcsr:#06x} pmr={pit.pmr} expiry={pit.expiry} fired={pit.fired}")
        card = getattr(self, "card", None)
        if card is not None:
            lines.append(f"card: {len(card.log)} commands, {card.reads} sectors read, {card.writes} written; "
                         f"last: {card.log[-5:]}")
        ran = self.ran()
        lines.append("ran: " + " ".join(self._name(t) for t in sorted(ALL_TCBS) if t in ran)
                     + ("   never: " + " ".join(self._name(t) for t in sorted(ALL_TCBS - ran)) if ALL_TCBS - ran else ""))
        return "\n".join(lines)

    def starvation(self, top=6):
        by = collections.defaultdict(collections.Counter)
        for (t, pc), n in self.pc_samples.items():
            by[t][pc] += n
        lines = ["burst-end PCs per task (who is spinning where):"]
        for t, ctr in sorted(by.items(), key=lambda kv: -sum(kv[1].values())):
            tot = sum(ctr.values())
            lines.append(f"  {self._name(t):8s} {tot:6d}: " +
                         " ".join(f"{pc:#x}x{n}" for pc, n in ctr.most_common(top)))
        return "\n".join(lines)


def stage_project(project, set_name, name, tree="out/_emu_rtos_tree",
                  audio=(), image_mb=64):
    """Copy a project directory into <tree>/<SET>/<NAME> and build a card
    image from it -- the same staging emu_frames does.

    No audio by default: every .wav/.ot is skipped, which is why no sample
    slot ever became valid under route A (RTOS_FORK section 10.12 -- the
    sample-slot control record 0x80004f1c got 0 writes in every run). `audio`
    is a list of "<src file>:<card-relative path>" pairs to stage as well,
    e.g. "~/octa/pool/x.wav:AUDIO/Loopmasters/x.wav" (relative to the SET
    folder, the way project.work's PATH=../AUDIO/... resolves). The image
    grows to `image_mb`."""
    import shutil
    src = pathlib.Path(project)
    name = name or src.name
    tree = pathlib.Path(tree)
    if tree.exists():
        shutil.rmtree(tree)
    dst = tree / set_name / name
    dst.mkdir(parents=True)
    (tree / set_name / "AUDIO").mkdir()
    for p in sorted(src.iterdir()):
        if p.is_file() and not p.name.startswith("._") and p.suffix.lower() not in (".wav", ".ot"):
            shutil.copy2(p, dst / p.name)
    for spec in audio:
        f, rel = spec.split(":", 1)
        f = pathlib.Path(f).expanduser()
        out = tree / set_name / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
    return ec.build_image(str(tree), image_mb), name


def attach(image=None, card_image=None, log=None, **kw):
    """Boot to the handoff, attach the card WITHOUT its cold-detour hooks,
    install the route-A models. Returns (BootResult, Rtos)."""
    ping = {"v": 0}

    def dsp_ping(uc, addr, size):
        ping["v"] ^= 1
        return ping["v"]
    # Log every peripheral write the boot makes, to seed the models from
    # (Rtos.install). The PLL read at 0x40000418 is the first peripheral
    # access, so its reply callable is where the write hook gets installed.
    boot_writes = []
    hooked = {"done": False}

    def pll_probe(uc, addr, size):
        if not hooked["done"]:
            hooked["done"] = True
            uc.hook_add(eb.UC_HOOK_MEM_WRITE,
                        lambda u, acc, a, sz, val, x: boot_writes.append((a, sz, val)),
                        begin=PERIPH_BASE, end=PERIPH_BASE + PERIPH_SIZE - 1)
        return PLL_VAL
    eb.EXTRA_OVERRIDES[PLL_REG] = pll_probe
    # the DSP host port as M5 faked it, and the two replies the card needs
    eb.EXTRA_OVERRIDES[0x2000001c] = dsp_ping
    eb.EXTRA_OVERRIDES[0x20000004] = 0x0000
    eb.EXTRA_OVERRIDES[ec.FW_ATA_HOST_STATUS] = 0x00
    eb.EXTRA_OVERRIDES[0xfc05c02c] = 0x00000020
    r = eb.boot(image)
    if not r.reached_handoff:
        raise RtosFault(f"boot did not reach the handoff: {r.stopped}")
    if r.trap != (32, HANDOFF):
        raise RtosFault(f"handoff trap is {r.trap}, expected (32, {HANDOFF:#x})")
    r.rtos_boot_writes = boot_writes
    # The region set the BOOT ends with, captured rather than written down.
    # ⚠️ It grows on its own from here: `_prime_menu` (emu_bringup) installs
    # an unmapped-access hook that maps a zero page and returns True -- a
    # workaround for a stale formatter pointer in the menu render -- and it
    # stays installed, so route A does not fault on unmapped memory on any
    # path that has primed the menu. Measured 8 Sep 2026: the card attach and
    # main's own init grow FOUR spans this way before the M6a gate, and they
    # are exactly the four the C++ port was answering all-ones for
    # (COLDFIRE_PORT.md, O5).
    _boot_regions = {(b, e) for b, e, _ in r.uc.mem_regions()}
    rt = Rtos(r, **kw)
    if card_image is not None:
        s = ec.attach(r, card_image, log, cold_hooks=False)
        rt.attach_card(s.card)
    rt.install()
    # The region set the run STARTS from, captured rather than written down:
    # an unmapped access auto-maps a zero page once `_prime_menu` has run, so
    # the list grows, and the growth is the interesting part (see the report
    # at the end of the until-gate path).
    rt._base_regions = _boot_regions
    return r, rt


def selftest():
    """Pin the Unicorn fact Rtos._sr rests on: a `cmpl`/`bne` pair split
    across two bursts branches right on its own and wrong after a
    `reg_read(SR)` in between; the trampoline read keeps it right. Code at
    0x1000: cmpl d1,d0 / bnes +4 / moveq #1,d0 / nop / moveq #2,d0 / nop."""
    code = bytes.fromhex("b081" "6604" "7001" "4e71" "7002" "4e71" "4e71" "4e71")

    def run(read):
        mu = eb.Uc(eb.UC_ARCH_M68K, eb.UC_MODE_BIG_ENDIAN)
        mu.ctl_set_cpu_model(eb.UC_CPU_M68K_CFV4E)
        mu.mem_map(0, 0x10000)
        mu.mem_write(0x1000, code)
        mu.mem_write(0x2000, bytes.fromhex("40c0" "4e71"))
        mu.reg_write(eb.UC_M68K_REG_SR, 0x2700)
        mu.reg_write(eb.UC_M68K_REG_A7, 0x8000)
        mu.reg_write(eb.UC_M68K_REG_D0, 5)
        mu.reg_write(eb.UC_M68K_REG_D1, 5)
        mu.emu_start(0x1000, 0, count=1)
        pc = mu.reg_read(eb.UC_M68K_REG_PC)
        sr = None
        if read == "api":
            sr = mu.reg_read(eb.UC_M68K_REG_SR)
        elif read == "tramp":
            d0 = mu.reg_read(eb.UC_M68K_REG_D0)
            mu.emu_start(0x2000, 0, count=1)
            sr = mu.reg_read(eb.UC_M68K_REG_D0) & 0xffff
            mu.reg_write(eb.UC_M68K_REG_D0, d0)
        mu.emu_start(pc, 0, count=3)
        return mu.reg_read(eb.UC_M68K_REG_D0), sr
    plain, api, tramp = run(None), run("api"), run("tramp")
    print(f"split, no read : d0={plain[0]} (want 1)")
    print(f"split, API read: d0={api[0]} sr={api[1]:#06x} (Unicorn 2.1.4: d0=2, Z lost)")
    print(f"split, tramp   : d0={tramp[0]} sr={tramp[1]:#06x} (want 1, 0x2704)")
    ok = plain[0] == 1 and tramp == (1, 0x2704)
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def _cli():
    if "--selftest" in sys.argv:
        return selftest()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--image", default=None, help="MAIN OS image (default: the raw stock image)")
    ap.add_argument("--project", default=None, help="project dir to put on an emulated card")
    ap.add_argument("--tree", default="out/_emu_rtos_tree",
                    help="scratch dir the emulated card is staged in; it is WIPED at "
                         "start, so two concurrent runs need two trees (three runs "
                         "launched together died on this, 6 Sep 2026)")
    ap.add_argument("--stage-audio", default="",
                    help="';'-separated '<file>:<SET-relative card path>' pairs to stage "
                         "beside the project (default: no audio at all -- see stage_project)")
    ap.add_argument("--image-mb", type=int, default=64, help="emulated card image size")
    ap.add_argument("--set", default="OCTABAM")
    ap.add_argument("--name", default=None)
    ap.add_argument("--ms", type=float, default=100.0, help="emulated milliseconds to run")
    ap.add_argument("--ips", type=float, default=3990.0, help="instructions per sample (a knob)")
    ap.add_argument("--pit-clock", type=float, default=264e6, help="PIT prescaler input, Hz (a knob)")
    ap.add_argument("--quantum", type=int, default=4096)
    ap.add_argument("--step-quantum", type=int, default=32)
    ap.add_argument("--no-tick", action="store_true", help="PIT0 never asserts (step-1 checkpoint)")
    ap.add_argument("--until-gate", action="store_true", help="stop as soon as the M6a gate passes")
    ap.add_argument("--serial-out", default="",
                    help="write the bytes each UART transmitted to FILE.a / FILE.b")
    ap.add_argument("--golden", default="",
                    help="write the M6a facts (created tasks, which ran, the first switch, the first "
                         "dispatches, the handoff PC and the boot's auto-pokes) as JSON: THE ORACLE the "
                         "C++ port (tools/emu/ot_emu) is diffed against, docs/firmware/COLDFIRE_PORT.md")
    ap.add_argument("--trace", action="store_true", help="print every dispatch/irq/create")
    ap.add_argument("--starvation", action="store_true", help="print burst-end PCs per task")
    ap.add_argument("--watch-calls", default="", help="comma-separated addresses to log entries to")
    ap.add_argument("--watch-mem", default="", help="ADDR,LEN: log every write into that range")
    ap.add_argument("--watch-pc", default="", help="comma-separated addresses: log registers there")
    ap.add_argument("--load-project", action="store_true",
                    help="M6b: after the gate, drive a project load through the real tasks (needs --project)")
    ap.add_argument("--sequencer", action="store_true",
                    help="M6c: enable the frame clock, start transport, run the sequencer for real "
                         "(needs --project; --load-project is implied)")
    ap.add_argument("--poke-trig", type=int, default=0,
                    help="with --sequencer: set a trig on track 1 at this step (1-8) after loading")
    ap.add_argument("--frames", type=int, default=400, help="with --sequencer: DSP frames to run")
    ap.add_argument("--internal-clock", action="store_true",
                    help="with --sequencer: clear CLOCK RECEIVE so the sequencer runs on its own clock")
    ap.add_argument("--bank", type=int, default=None,
                    help="with --sequencer: switch to this bank via sys before starting (default: the file's saved bank)")
    ap.add_argument("--via-key", action="store_true",
                    help="with --sequencer: start transport through the real PLAY key handler "
                         "(press_play_live, M6d) instead of calling FW_TRANSPORT directly")
    ap.add_argument("--poke-mask", default="",
                    help="with --sequencer and --poke-trig: also set that step's bit in "
                         "each comma-separated TRAC mask offset (e.g. 0x08,0x10) on track 1 "
                         "-- for finding which mask a trig type lives in")
    ap.add_argument("--poke-mask-track", type=int, default=1,
                    help="which track --poke-mask writes (0-7, default 1)")
    ap.add_argument("--watch-pattern", type=lambda x: int(x, 0), default=0,
                    help="with --sequencer: log every READ into the first N bytes of the "
                         "current pattern record and report them by offset -- finds the "
                         "trig arrays instead of guessing their offsets")
    ap.add_argument("--arm-phase-fix", action="store_true",
                    help="RETIRED (RTOS_FORK 10.16): compensation for the stock-EMAC timing byte; "
                         "with the fixed Unicorn the trig arms on its own. Kept for comparison runs")
    ap.add_argument("--tape", default="",
                    help="with --sequencer: record every host-port-bound eDMA transfer (fields + "
                         "source bytes), every CPU write into the host-port window and every "
                         "DSP-select GPIO write to this JSON-lines file -- tier 2's parameter tape")
    ap.add_argument("--names-early", action="store_true",
                    help="with --load-project: write the SET/PROJECT names BEFORE requesting the "
                         "mount instead of after. An EXPERIMENT (COLDFIRE_PORT.md O7b): sys's media "
                         "case reloads the current project when its name is non-empty, so this makes "
                         "route A load twice the way the C++ port does")
    ap.add_argument("--cmd-log", default="",
                    help="write every ATA command in order (`WHAT LBA COUNT`, one per line) "
                         "to FILE -- the counterpart of the C++ port's --cmd-log, so the two "
                         "logs can be diffed line for line instead of compared by count")
    ap.add_argument("--stock-emac", action="store_true",
                    help="run even though this Unicorn's EMAC fails emu_bringup.emac_selftest "
                         "(fractional products halved; RTOS_FORK section 10.16)")
    ap.add_argument("--via-rec", action="store_true",
                    help="with --sequencer: start the transport through the real REC key "
                         "handler INSTEAD of PLAY (REC starts it too, §9.4) and report the "
                         "record-arm byte (0x800066a0) either side of the press -- RTOS_FORK "
                         "section 9.4's falsifier. Overrides --via-key")
    a = ap.parse_args()

    ok, detail = eb.emac_selftest()
    if not ok and not a.stock_emac:
        sys.exit("refusing to run route A on a stock Unicorn EMAC: " + detail
                 + "\n  every fractional product would be half of hardware's (recorder length, "
                 "block walk, sequencer timing byte -- RTOS_FORK section 10.16). "
                 "Build the fixed library with scripts/build_unicorn.sh, or pass --stock-emac "
                 "to run anyway.")
    print(f"EMAC       : {'fixed' if ok else 'STOCK (halved fractional products)'} -- {detail}")

    card = None
    staged_name = a.name
    if a.project:
        card, staged_name = stage_project(a.project, a.set, a.name, tree=a.tree,
                                          audio=[x for x in a.stage_audio.split(";") if x],
                                          image_mb=a.image_mb)
    t0 = time.perf_counter()
    r, rt = attach(a.image, card, ips=a.ips, pit_clock_hz=a.pit_clock, quantum=a.quantum,
                   step_quantum=a.step_quantum, tick=not a.no_tick,
                   trace=(lambda s: print(s, flush=True)) if a.trace else None)
    if a.watch_calls:
        rt.watch_calls([int(x, 0) for x in a.watch_calls.split(",")])
    if a.watch_mem:
        wa, wl = a.watch_mem.split(",")
        rt.watch_mem(int(wa, 0), int(wl, 0))
    if a.watch_pc:
        rt.watch_pc([int(x, 0) for x in a.watch_pc.split(",")])
    if a.arm_phase_fix:
        rt.arm_phase_fix()
    if a.tape:
        # From the handoff on, not from transport start: the FX knob values
        # were nowhere in 400 frames of steady-state traffic (7 Sep 2026), so
        # they travel as EVENTS -- at the load, at an effect select, at a
        # knob move -- and a tape that misses the load misses them all.
        pathlib.Path(a.tape).parent.mkdir(parents=True, exist_ok=True)
        rt.tape(a.tape)
        print(f"tape       : recording host-port traffic to {a.tape} (from the handoff)")
    print(f"boot       : {r.stopped} ({time.perf_counter() - t0:.1f} s)")
    print(f"PIT0       : period {rt.pit0.period_samples():.2f} samples "
          f"({rt.pit0.period_samples() / SAMPLE_HZ * 1000:.3f} ms) at pit clock {a.pit_clock:.0f} Hz")

    def _watch_report():
        """Print what --watch-calls / --watch-mem actually collected.

        ⚠️ Both hooks appended to `rt.calls` / `rt.mem_writes` and the CLI
        printed NEITHER unless --trace was also on, so a watched address
        that never fired and one that fired every frame looked exactly the
        same from the command line: silence. Anything concluded from "the
        watch printed nothing" is worthless without this (M6e, 6 Sep 2026).
        """
        calls = getattr(rt, "calls", None)
        if calls is not None:
            seen = {}
            for _, _, addr, ret, _ in calls:
                e = seen.setdefault(addr, [0, set()])
                e[0] += 1; e[1].add(ret)
            for a_ in [int(x, 0) for x in a.watch_calls.split(",")]:
                n, callers = seen.get(a_, (0, set()))
                where = (", callers " + ", ".join(f"{c:#x}" for c in sorted(callers)[:4])) if callers else ""
                print(f"watch-call : {a_:#x} entered {n} time(s){where}")
        hits = getattr(rt, "pc_hits", None)
        if hits is not None:
            print(f"watch-pc   : {len(hits)} hit(s)")
            for sample, line in hits:
                print(f"   [{sample:10.1f}] {line}")
        writes = getattr(rt, "mem_writes", None)
        if writes is not None:
            # ⚠️ `load_project_live` installs its own watch_mem and shares
            # this list, so a run that loads a project carries its writes too
            # -- the addresses below say which is which.
            print(f"watch-mem  : {len(writes)} write(s) logged "
                  f"(the load's own watch shares this list)")
            # Print them ALL (capped only against a flood): the first
            # version showed 12 and "... 111 more", and the 111 were the
            # only writes that mattered -- a watch that hides its hits is
            # the silent-instrument trap again (RTOS_FORK section 10.3b).
            cap = 4000
            for sample, task, pc, addr_, size, val in writes[:cap]:
                print(f"   [{sample:10.1f}] [{addr_:#x}] <- {val:#x} ({size}) "
                      f"at pc {pc:#x} in {rt._name(task)}")
            if len(writes) > cap:
                print(f"   ... {len(writes) - cap} more (raise cap in emu_rtos.py)")

    def _cmd_log(path, rt):
        """Every ATA command in order, the shape the C++ port's --cmd-log
        writes its first field group in, so `diff` names the first divergence
        instead of a count difference naming none (O7's method, made a flag)."""
        if not path or not rt.card:
            return
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for e in rt.card.log:
                # ⚠️ The entries are VARIABLE length: ("IDENTIFY",),
                # ("READ", lba, n), ("CFA-TRANSLATE", lba). Pad to three so a
                # short one lines up with the port's, which always writes all
                # three fields.
                lba = e[1] if len(e) > 1 else 0
                n = e[2] if len(e) > 2 else 0
                f.write(f"{e[0]} {lba} {n}\n")
        print(f"cmd log    : {path} ({len(rt.card.log)} commands)")

    def _fault(e):
        why = f"FAULT {e} pc={rt.pc:#x} task={rt._name(rt._cur())}"
        if rt.unmapped:
            acc, addr, size, pc = rt.unmapped
            why += f" unmapped {'write' if acc in (eb.UC_MEM_WRITE_UNMAPPED,) else 'read'} {addr:#x} size {size} at pc {pc:#x}"
        return why

    if a.sequencer:
        if not a.project:
            print("--sequencer needs --project"); return 1
        try:
            if not rt.gate_m6a()[0]:
                rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
            mounted, posted, saved_bank, final_bank, elapsed = rt.load_project_live(
                a.set, staged_name, run_ms=a.ms)
            # The frame clock and the exact instruction clock come on here,
            # after the boot and the load: both are ~10x slower and neither
            # matters to the sequencer until it runs (on hardware the frame
            # exchange runs from boot; nothing the trig test reads depends
            # on it having done so). Rtos(frame=True) still gives the
            # from-boot form for Python callers.
            bank = a.bank if a.bank is not None else saved_bank
            if bank is not None and final_bank != bank:
                # The load ends on bank A here (sys applies the engine's own
                # reset-time "select bank 0" after the BANK= parse). The UNIT
                # does not: it comes up on the saved bank and plays it
                # (measured 6 Sep 2026, RTOS_FORK section 7), so this switch
                # and seq_select_live below compensate for an emulator timing
                # defect; both go once the load's timing is made faithful.
                final_bank = rt.select_bank_live(bank)
            pattern = rt.uc.mem_read(CUR_PATTERN, 1)[0]
            seq_bank, seq_pattern = rt.seq_select_live(final_bank, pattern)
            if a.internal_clock:
                rt.internal_clock()
            rt.frame = True
            rt.next_frame = rt.sample + FRAME_PERIOD
            rt.exact_clock()
            if a.tape:
                rt._tape_rec("mark", what="transport-start")
            if a.watch_pattern:
                pbase = rt.pattern_base()
                print(f"pattern    : record at {pbase:#x} "
                      f"(pattern {rt.uc.mem_read(CUR_PATTERN, 1)[0]}), "
                      f"watching reads of its first {a.watch_pattern:#x} bytes")
                rt.watch_reads(pbase, a.watch_pattern)
            rec_arm = None
            if a.via_rec:
                # RTOS_FORK §9.4's falsifier, on a project whose track 1 IS
                # configured as a recorder machine: does REC through its own
                # handler move the record-arm byte? Read `0x800066a0` and the
                # transport byte either side of the press.
                #
                # ⚠️ ORDER IS LOAD-BEARING, and two orders are already known
                # bad (measured 6 Sep 2026, BOTH on the plain project too, so
                # neither is a recorder finding): REC then PLAY delivers 400
                # frames with ZERO FW_LIVE_NIBBLE writes -- REC starts the
                # transport itself (§9.4), so PLAY toggles it back off -- and
                # REC alone, with the tracks started by hand the way
                # press_play_live does, ALSO gives zero. Only PLAY first,
                # then REC, keeps M6c's gate intact, which is what makes the
                # arm reading here mean anything: if the trig still lands at
                # frame 344, the run is faithful and the arm byte was
                # genuinely watched over a working transport.
                rt.press_play_live()
                before = (_word(rt, TRANSPORT), _word(rt, REC_ARM))
                rt.press_rec_live()
                rec_arm = (before, (_word(rt, TRANSPORT), _word(rt, REC_ARM)))
            elif a.via_key:
                rt.press_play_live()
            else:
                rt.start_transport_live()
            if a.poke_trig:
                v = rt.poke_trig(a.poke_trig)
                print(f"poke trig  : track 1 step {a.poke_trig} -> mask byte 7 = {v:#04x}")
                for off in [int(x, 0) for x in a.poke_mask.split(",") if x.strip()]:
                    v = rt.poke_mask(off, a.poke_trig, a.poke_mask_track)
                    print(f"poke mask  : track {a.poke_mask_track} mask {off:#04x} "
                          f"step {a.poke_trig} -> byte 7 = {v:#04x}")
            rt.install_trig_log()
            # Frame 0 = the first frame delivered after the transport start
            # returned, which is what emu_frames.py's cold run calls frame 0:
            # the two reports compare directly (cold: the trig at 344).
            frame0 = rt.frame_count + 1
            ticks0 = rt.tick_count
            target = frame0 + a.frames
            rt.run(ms=a.frames * FRAME_PERIOD / SAMPLE_HZ * 1000.0 * 5 + 2000,
                   until=lambda x: x.frame_count >= target)
        except (RtosFault, eb.UcError) as e:
            print(f"stopped    : {_fault(e)}")
            print(rt.report())
            print(rt.starvation())
            return 1
        print(rt.report())
        print(f"sequencer  : playing bank {seq_bank} pattern {seq_pattern} (re-selected through the load's own last step)")
        if rec_arm is not None:
            (t0b, a0b), (t1b, a1b) = rec_arm
            print(f"REC        : across the press -- transport {TRANSPORT:#x} "
                  f"{t0b:#x} -> {t1b:#x}, record-arm {REC_ARM:#x} {a0b:#x} -> {a1b:#x} "
                  f"(longwords); after the run {_word(rt, TRANSPORT):#x} / "
                  f"{_word(rt, REC_ARM):#x}")
        print(f"load       : mounted={mounted} saved_bank={saved_bank} bank={final_bank} "
              f"clock={'internal' if a.internal_clock else 'external (CLOCK RECEIVE as saved)'}")
        print(f"ticks      : {rt.tick_count - ticks0} sequencer tick(s) (vector 0x60) since transport start")
        print(f"frames run : {rt.frame_count - frame0} since transport start (target {a.frames}; "
              f"{frame0} before it), eDMA transfers {rt.edma.started}")
        if a.tape:
            rt._tape.close()
            print(f"tape       : {rt._tape_n} records -> {a.tape} (frame numbers are absolute; "
                  f"transport started at frame {frame0})")
        print(f"FW_LIVE_NIBBLE (0x{FW_LIVE_NIBBLE:x}) writes ({len(rt.live_nibble_log)}), frames since transport start:")
        for frame, track, val in rt.live_nibble_log:
            print(f"   frame {frame - frame0:5d} track {track} byte {val:#04x}  nibble {val & 0xf:x}  flags {val & 0xf0:#04x}")
        print(f"FW_TRIG_WORDS (0x{FW_TRIG_WORDS:x}) nonzero writes ({len(rt.trig_words_log)}): {rt.trig_words_log}")
        ok = rt.frame_count >= target
        if not ok:
            print(rt.starvation())
        reads = getattr(rt, "reads", None)
        if reads:
            by_off = {}
            for (off, size, pc), n in reads.items():
                e = by_off.setdefault(off, [0, size, set()])
                e[0] += n; e[2].add(pc)
            print(f"pattern rd : {len(by_off)} distinct offsets read")
            for off in sorted(by_off):
                n, size, pcs = by_off[off]
                print(f"   +{off:#06x} size {size} x{n:<5d} pc "
                      + ", ".join(f"{c:#x}" for c in sorted(pcs)[:3]))
        fixes = getattr(rt, "arm_fixes", None)
        if fixes is not None:
            print(f"arm-phase  : {len(fixes)} trig word(s) had bit 7 cleared (COMPENSATION): "
                  + ", ".join(f"track {t} {w:#x} @ {s_:.0f}" for s_, t, w in fixes[:8]))
        _watch_report()
        _cmd_log(a.cmd_log, rt)
        if a.golden:
            # THE M6c ORACLE, in the shape tools/emu/ot_emu/oracle.py compares:
            # the trig log with frame numbers relative to the transport start,
            # the tick count, the frames run, and the four bank/pattern bytes.
            # Deliberately a SEPARATE file from the M6a golden -- a different
            # configuration measures a different thing.
            import json as _json
            pathlib.Path(a.golden).parent.mkdir(parents=True, exist_ok=True)
            with open(a.golden, "w") as f:
                _json.dump({
                    "m6c_trig": [[fr - frame0, tr, v] for fr, tr, v in rt.live_nibble_log],
                    "m6c_trig_words": [[fr - frame0, i, v] for fr, i, v in rt.trig_words_log],
                    "m6c_ticks": rt.tick_count - ticks0,
                    "m6c_frames": rt.frame_count - frame0,
                    "m6c_bank": [saved_bank if saved_bank is not None else -1,
                                 final_bank, seq_bank, seq_pattern],
                }, f, indent=1)
            print(f"golden     : {a.golden}")
        label = "M6d run (via-key)" if a.via_key else "M6c run"
        print(f"{label:11s}:", "PASS (ran to target)" if ok else "FAIL (stopped short)")
        return 0 if ok else 1

    if a.load_project:
        if not a.project:
            print("--load-project needs --project"); return 1
        try:
            if not rt.gate_m6a()[0]:
                rt.run(ms=1000, until=lambda x: x.gate_m6a()[0])
            mounted, posted, saved_bank, final_bank, elapsed = rt.load_project_live(
                a.set, staged_name, run_ms=a.ms, names_early=a.names_early)
        except (RtosFault, eb.UcError) as e:
            print(f"stopped    : {_fault(e)}")
            print(rt.report())
            print(rt.starvation())
            return 1
        print(rt.report())
        part = int.from_bytes(rt.uc.mem_read(ec.PART_PTR, 4), "big")
        print(f"load       : ready={mounted} posted={posted} saved_bank={saved_bank} "
              f"final_bank={final_bank} PART_PTR={part:#x} ({elapsed:.1f} ms emulated total)")
        if saved_bank is not None and final_bank != saved_bank:
            print("             final bank != saved bank: SYS applied the engine's own reset-time "
                  "'select bank 0' after the BANK= parse (RTOS_FORK.md section 7)")
        if rt.card:
            print(f"card       : {len(rt.card.log)} commands, {rt.card.reads} sectors read, "
                  f"{rt.card.writes} written; last: {rt.card.log[-8:]}")
        _cmd_log(a.cmd_log, rt)
        # ⚠️ THE SILENT-INSTRUMENT TRAP, IN A THIRD BRANCH. `_watch_report`
        # was called from the M6c path and (since 8 Sep) from the plain one,
        # and NOT from here -- so `--watch-pc` on a `--load-project` run
        # printed nothing whether the address fired twice or never. Found
        # 8 Sep 2026 by O7b, whose whole question is "how many times".
        # Section 10.3b records this trap; this is its third instance.
        _watch_report()
        ok = bool(mounted) and saved_bank is not None
        if not ok:
            print(rt.starvation())
        print("M6b load   :", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    until = (lambda x: x.gate_m6a()[0]) if a.until_gate else None
    try:
        why = rt.run(ms=a.ms, until=until)
    except (RtosFault, eb.UcError) as e:
        why = _fault(e)
    print(f"stopped    : {why}")
    print(rt.report())
    ok, problems = rt.gate_m6a()
    if a.starvation or not ok:
        print(rt.starvation())
    print("M6a gate   :", "PASS" if ok else "FAIL")
    for p in problems:
        print("   -", p)
    # ⚠️ --watch-pc / --watch-calls / --watch-mem printed NOTHING on this
    # path: `_watch_report` was only called from the M6c branch, so a watched
    # address that never fired and one that fired constantly looked identical
    # here -- silence. That is the same silent-instrument trap section 10.3b
    # records for --trace, surviving in a second branch; found 8 Sep 2026
    # while asking whether route A ever executes the two large clear loops the
    # C++ port runs (COLDFIRE_PORT.md, O5). Nothing concluded from a silent
    # watch on this path before today is worth anything.
    _watch_report()
    # ⚠️ HOW MANY REGIONS ARE MAPPED, and it is not a constant. `_prime_menu`
    # (emu_bringup) installs an unmapped-access hook that MAPS A ZERO PAGE and
    # returns True -- a menu-render workaround for a stale formatter pointer --
    # and it stays installed for the rest of the run. So on any path that has
    # primed the menu, route A does NOT fault on unmapped memory: it silently
    # grows a zero page. Printed because the C++ port answers ALL-ONES and
    # drops the write instead, which is a different machine (COLDFIRE_PORT.md,
    # O5, 8 Sep 2026).
    _now = {(b, e) for b, e, _ in rt.uc.mem_regions()}
    _grew = sorted(_now - getattr(rt, "_base_regions", _now))
    print(f"regions    : {len(_now)} mapped at the stop, {len(_grew)} GREW after the boot"
          + (": " + ", ".join(f"{b:#x}-{e:#x}" for b, e in _grew) if _grew else ""))
    if a.serial_out:
        for suffix, u in (("a", rt.uart64), ("b", rt.uart68)):
            pathlib.Path(a.serial_out + "." + suffix).write_bytes(bytes(u.tx))
        print(f"serial out : {a.serial_out}.a ({len(rt.uart64.tx)} B), "
              f"{a.serial_out}.b ({len(rt.uart68.tx)} B)")
    if a.golden:
        import base64
        import json
        gold = dict(
            handoff_pc=HANDOFF,
            auto_pokes=[dict(pc=pc, addr=ad, value=v) for pc, ad, v in r.auto_pokes],
            created=[dict(sample=round(c[0], 1), tcb=c[1], entry=c[2], prio=c[3], stack=c[4],
                          stack_size=c[5], creator=c[6], name=rt._name(c[1])) for c in rt.created],
            ran=sorted(rt.ran()),
            first_switch=rt.first_switch,
            dispatches=[dict(sample=round(s_, 1), tcb=t, pc=pc) for s_, t, pc in rt.dispatches[:200]],
            gate_ms=round(rt.sample / SAMPLE_HZ * 1000, 2),
            pit0_fired=rt.pit0.fired,
            # THE SERIAL STREAM, not its length. ⚠️ The COUNT is a clock
            # artefact and the bytes are not: the transmit ring is drained in
            # bursts, so whether the last ~900-byte drain lands before or
            # after the gate depends on the instruction budget per sample.
            # Measured 8 Sep 2026 on the C++ port, same image, same
            # everything else: ips 3900 and 3990 stop with 5731 bytes sent,
            # ips 4100, 4200 and 4300 with 4831 -- and every one of those
            # streams has this one as an exact prefix. So the oracle compares
            # the BYTES over the length both reached, which is a real property
            # of the code path, and reports the length difference.
            serial_sent=[len(rt.uart64.tx), len(rt.uart68.tx)],
            serial_a=base64.b64encode(bytes(rt.uart64.tx)).decode(),
            serial_b=base64.b64encode(bytes(rt.uart68.tx)).decode(),
        )
        pathlib.Path(a.golden).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.golden).write_text(json.dumps(gold, indent=1))
        print(f"golden     : {a.golden} ({len(gold['created'])} tasks, {len(gold['dispatches'])} dispatches)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_cli())
