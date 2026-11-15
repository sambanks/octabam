#!/usr/bin/env python3
"""REMOTE's event records from a unit over USB (the vendor request 0xc0/0x5a the USB module answers on EP0;
modules/remote/remote.s, modules/usb/usbaudio.s).

  tools/hw/ot_events.py                 # every record the ring holds
  tools/hw/ot_events.py --follow        # then each new record as it arrives
  tools/hw/ot_events.py --wait PATTERN [--arg 3] [--timeout 20]    # exit 0 when it arrives, 1 at the timeout

Needs pyusb and a libusb (load_meter.py's note). The image must carry REMOTE and USB; any other image STALLs.

The block is a 32-byte header {magic "RMT1", head, screen count, screen stamp, RMT_TRACE's address} and 256
records; a record is seq (16 bits), kind (8), arg (8), stamp (32 bits of
DMA timer 3, 132 MHz, so it wraps every 32.5 s). `head` counts every record written; record n is at index n & 255.
COMMAND (0xc0/0x59, id in wValue's low byte): 1 enters USB DISK MODE, 2 leaves it (the project reloads), 3 boots
a file of REMIX SWITCH's list (`boot`), 4 rescans that list. Nothing else.

`Events` keeps the last head it saw and returns the records since, with `lost` the number overwritten before they
were read. A scenario calls `wait_for` instead of sleeping: it returns the first record that matches, or raises.

`connect()` gives a `Remote` or None (an image without REMOTE, or no libusb in this python); `wait_stopped(remote,
fallback)` is the wait after a MIDI STOP: the old sleep when `remote` is None, else the playing byte (PEEK
`0x800065bb`; 1 while playing) until it leaves 1, within the same `fallback`; `wait_pattern(remote, program,
fallback)` is the wait after a program change sent with the sequencer stopped: the bank and pattern bytes
(`0x800065bd`, `0x800065be`) until they are the program's (bank `p // 16`, pattern `p % 16`), within `fallback`.
It reads the bytes, not a record, because a change to the current pattern writes none. While playing,
QPATTERN comes at once and PATTERN at the pattern's end (7.9 and 8.0 s at 120 BPM); stopped, both come
4.5 to 5.9 ms after the send.

As a library the transport is a function ctrl(offset, wLength) -> bytes, so the same reader runs on a unit
(`unit_ctrl`) and under the port's scripted host (tools/verify/verify_remote.py).
"""
import argparse
import struct
import sys
import time

MAGIC = b"RMT1"
NREC = 256
HEADER = 32
NTRACE = 512
BYTES = HEADER + NREC * 8
TIMER_HZ = 132e6

KINDS = {1: "LOADALL", 2: "LOADMASK", 3: "NEWPROJ", 4: "BANKW", 5: "PSTORE", 6: "PRELOAD", 8: "COMMAND",
         16: "PLAYING", 17: "BANK", 18: "PATTERN", 19: "QBANK", 20: "QPATTERN"}
BY_NAME = {v: k for k, v in KINDS.items()}


class Lost(RuntimeError):
    """The ring wrapped past records that were never read."""


def read_bytes(ctrl, offset, size):
    """`size` bytes of the block from `offset`. A reply is at most 255 bytes and never a multiple of 64."""
    out = b""
    while len(out) < size:
        raw = ctrl(offset + len(out), min(255, size - len(out)))
        if not raw:
            raise RuntimeError(f"0 bytes back at offset {offset + len(out)}")
        out += raw
    return out[:size]


def decode(raw, n):
    """Record number n from its 8 bytes -> dict, or None when the slot holds another record (it was overwritten)."""
    seq, kind, arg, stamp = struct.unpack(">HBBI", raw)
    if seq != n & 0xffff:
        return None
    return {"n": n, "kind": kind, "name": KINDS.get(kind, str(kind)), "arg": arg, "stamp": stamp}


class Events:
    def __init__(self, ctrl, from_start=False, clock=time.monotonic):
        """`clock` measures the waits' timeouts: wall seconds on a unit; under the port, the machine's emulated
        seconds, so a loaded runner advances the same emulated time before a wait gives up."""
        self.ctrl = ctrl
        self.clock = clock
        self.lost = 0
        self.seen = max(0, self.head() - NREC) if from_start else self.head()

    def header(self):
        """(head, screen count, screen stamp)."""
        magic, head, screens, stamp = struct.unpack(">4s3I", read_bytes(self.ctrl, 0, 16))
        if magic != MAGIC:
            raise RuntimeError(f"not REMOTE's block: {magic!r}")
        return head, screens, stamp

    def head(self):
        return self.header()[0]

    def wait_screen(self, since=None, timeout=10.0, tick=None):
        """The screen count once it has passed `since` (default: its value now): the LCD was redrawn."""
        since = self.header()[1] if since is None else since
        end = self.clock() + timeout
        while True:
            n = self.header()[1]
            if n != since:
                return n
            if self.clock() >= end:
                raise TimeoutError(f"no screen redraw in {timeout} s")
            (tick or (lambda: time.sleep(0.005)))()

    def poll(self):
        """The records written since the last call, oldest first."""
        head = self.head()
        first = self.seen
        if head - first > NREC:
            self.lost += head - first - NREC
            first = head - NREC
        out = []
        n = first
        while n < head:
            i = n & (NREC - 1)
            run = min(head - n, NREC - i, 31)             # 31 records = 248 bytes, one reply
            raw = read_bytes(self.ctrl, HEADER + 8 * i, 8 * run)
            for j in range(run):
                r = decode(raw[8 * j:8 * j + 8], n + j)
                if r is None:
                    self.lost += 1                        # overwritten between the head read and this one
                else:
                    out.append(r)
            n += run
        self.seen = head
        return out

    def wait_for(self, kind, arg=None, timeout=10.0, tick=None, strict=False):
        """The first record of `kind` (a name or a number, or several), with `arg` when given. `tick` is called between
        polls (the port's gate advances the machine there; on a unit it defaults to a 5 ms sleep). With
        `strict`, records lost while waiting raise Lost instead of being counted."""
        ks = {BY_NAME[k] if isinstance(k, str) else k for k in (kind if isinstance(kind, (tuple, list, set)) else (kind,))}
        end = self.clock() + timeout
        passed = []
        while True:
            for r in self.poll():
                passed.append(r)
                if r["kind"] in ks and (arg is None or r["arg"] == arg):
                    r["passed"] = passed[:-1]
                    return r
            if strict and self.lost:
                raise Lost(f"{self.lost} record(s) overwritten before they were read")
            if self.clock() >= end:
                raise TimeoutError(f"no {'/'.join(KINDS.get(k, str(k)) for k in sorted(ks))}{'' if arg is None else f' arg {arg}'} in {timeout} s; "
                                   f"passed: {[(p['name'], p['arg']) for p in passed]}")
            (tick or (lambda: time.sleep(0.005)))()


def unit_ctrl(dev):
    return lambda off, n: bytes(dev.ctrl_transfer(0xc0, 0x5a, off, 0, n, timeout=1000))


CMD_DISK_ENTER, CMD_DISK_LEAVE, CMD_BOOT, CMD_SCAN = 1, 2, 3, 4
NLEN = 24                       # bytes a name of REMIX SWITCH's list (modules/remix-switch/switch.s)


def name_hash(name):
    h = 0
    for c in name:
        h = (h * 33 + c) & 0xffff
    return h


def remixes(ctrl, peek1):
    """REMIX SWITCH's list as the unit holds it, in its order: the .RMX names of /BRAIN/REMIXES at the last
    scan (MAIN MENU's opening, or COMMAND 4). [] in an image without REMIX SWITCH."""
    names, count = struct.unpack(">II", read_bytes(ctrl, 20, 8))
    if not names:
        return []
    n = struct.unpack(">I", peek(peek1, count, 4))[0]
    raw = peek(peek1, names, NLEN * n)
    return [raw[NLEN * i:NLEN * (i + 1)].split(b"\0")[0] for i in range(n)]


def boot(cmd1, ctrl, peek1, name):
    """Boot /BRAIN/REMIXES/<name> through REMIX SWITCH (COMMAND 3: the file's index in the unit's list and
    the hash of its name, which the unit checks against that list). True when taken: the unit stops the
    sequencer, syncs the card, stages the file and resets, so it leaves the bus. False when the name is
    not in the list (send COMMAND 4 first after writing a file) or the unit refuses."""
    name = name.encode() if isinstance(name, str) else name
    names = remixes(ctrl, peek1)
    if name not in names:
        return False
    return command(cmd1, CMD_BOOT | names.index(name) << 8, name_hash(name))
LOADS = ("LOADALL", "LOADMASK", "PRELOAD")


def unit_command(dev):
    return lambda cid, arg=0: bytes(dev.ctrl_transfer(0xc0, 0x59, cid, arg, 1, timeout=1000))


def command(cmd1, cid, arg=0):
    """COMMAND (0xc0/0x59) through cmd1(id, arg) -> the reply byte. True when the unit took it: its routine
    then runs in the UI task and a COMMAND record with arg = id follows. False for an id the unit does not
    have or while an earlier command is still waiting."""
    return cmd1(cid, arg) == b"\x00"


def unit_peek(dev):
    return lambda addr, n: bytes(dev.ctrl_transfer(0xc0, 0x58, addr >> 16, addr & 0xffff, n, timeout=1000))


def peek(peek1, addr, size):
    """`size` bytes from `addr` through peek1(addr, wLength) -> bytes (PEEK, 0xc0/0x58: at most 255 bytes a
    reply, never a multiple of 64, only inside SDRAM's cached view, the on-chip SRAM and CS1)."""
    out = b""
    while len(out) < size:
        raw = peek1(addr + len(out), min(255, size - len(out)))
        if not raw:
            raise RuntimeError(f"0 bytes back at {addr + len(out):#x}")
        out += raw
    return out[:size]


def trace(ctrl, peek1, last=NTRACE):
    """The last `last` frame interrupts, oldest first: [(n, interrupted pc, entry stamp)]. The unit keeps
    writing while the host reads, so the newest entries are read first and an entry overwritten meanwhile
    is dropped (its number is checked against a second read of the count)."""
    base = struct.unpack(">I", read_bytes(ctrl, 16, 4))[0]
    count = struct.unpack(">I", peek(peek1, base, 4))[0]
    last = min(last, count, NTRACE)
    out = []
    hi = count                                            # entries [lo, hi) are read newest chunk first
    while hi > count - last:
        i = (hi - 1) & (NTRACE - 1)
        run = min(hi - (count - last), i + 1, 31)         # 31 entries = 248 bytes, one reply; not across the wrap
        lo = hi - run
        raw = peek(peek1, base + 8 + 8 * (lo & (NTRACE - 1)), 8 * run)
        out += [(lo + j,) + struct.unpack(">II", raw[8 * j:8 * j + 8]) for j in range(run)]
        hi = lo
    now = struct.unpack(">I", peek(peek1, base, 4))[0]
    return sorted(e for e in out if e[0] > now - NTRACE)


PLAYING_ADDR = 0x800065bb          # the byte the watch reads for PLAYING (modules/remote/remote.s, rmt_wtab)
BANK_ADDR = 0x800065bd             # the current bank, then the current pattern (the watch's kinds 17 and 18)


class Remote:
    """What a scenario needs of REMOTE: the ring, and the playing byte through PEEK."""

    def __init__(self, ctrl, peek1):
        self.ev = Events(ctrl)
        self.peek1 = peek1

    def playing(self):
        """True while the sequencer plays (the byte is 1; a MIDI STOP leaves 2)."""
        return peek(self.peek1, PLAYING_ADDR, 1)[0] == 1

    def pattern(self):
        """(bank, pattern), both from 0: a program change p selects bank p // 16, pattern p % 16."""
        b = peek(self.peek1, BANK_ADDR, 2)
        return b[0], b[1]

    def wait(self, kind, arg=None, timeout=10.0):
        """The first matching record, or None at the timeout."""
        try:
            return self.ev.wait_for(kind, arg, timeout)
        except TimeoutError:
            return None


def connect(dev=None):
    """A Remote for the unit on USB, or None: no pyusb or libusb, no unit, or an image without REMOTE (its
    0xc0/0x5a STALLs)."""
    try:
        if dev is None:
            import load_meter
            dev = load_meter.libusb_device()
        return Remote(unit_ctrl(dev), unit_peek(dev))
    except (SystemExit, Exception):  # noqa: BLE001
        return None


def wait_pattern(remote, program, fallback):
    """Return once the unit's bank and pattern are those of MIDI program change `program`, after the caller
    sent it. Without REMOTE, or when the unit cannot be read, this sleeps `fallback` seconds, as the
    scenarios did; with it, it returns when the two bytes match (at once when they already do: a program
    change to the current pattern writes no record) and never waits longer than `fallback`. With the
    sequencer stopped the change lands 4.5 to 5.9 ms after the send; while playing, at the pattern's end.
    True when the bytes matched, False after a sleep or at the limit."""
    if remote is None:
        time.sleep(fallback)
        return False
    want = (program // 16, program % 16)
    end = time.monotonic() + fallback
    while True:
        try:
            if remote.pattern() == want:
                return True
        except Exception:  # noqa: BLE001
            time.sleep(max(0.0, end - time.monotonic()))
            return False
        if time.monotonic() >= end:
            return False
        time.sleep(0.005)


def wait_stopped(remote, fallback):
    """Return once the sequencer has stopped, after the caller sent STOP. Without REMOTE, or when the unit
    cannot be read, this sleeps `fallback` seconds, as the scenarios did; with it, it returns when the
    playing byte leaves 1, and never waits longer than `fallback`. A stop of a sequencer that was not
    playing writes no record, so the byte is the state. True when the byte was seen to leave 1 (or was
    not 1), False after a sleep or at the limit."""
    if remote is None:
        time.sleep(fallback)
        return False
    end = time.monotonic() + fallback
    while True:
        try:
            if not remote.playing():
                return True
        except Exception:  # noqa: BLE001
            time.sleep(max(0.0, end - time.monotonic()))
            return False
        if time.monotonic() >= end:
            return False
        time.sleep(0.005)


def show(r, t0=None):
    return f"{r['n']:6d}  {r['name']:9s} {r['arg']:3d}  stamp {r['stamp']:10d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--follow", action="store_true")
    ap.add_argument("--wait", metavar="KIND", help=f"one of {', '.join(BY_NAME)}")
    ap.add_argument("--arg", type=int)
    ap.add_argument("--timeout", type=float, default=10.0)
    a = ap.parse_args()
    import load_meter
    ev = Events(unit_ctrl(load_meter.libusb_device()), from_start=not a.wait)
    if a.wait:
        try:
            print(show(ev.wait_for(a.wait, a.arg, a.timeout)))
            return 0
        except TimeoutError as e:
            print(e)
            return 1
    while True:
        for r in ev.poll():
            print(show(r), flush=True)
        if not a.follow:
            break
        time.sleep(0.02)
    if ev.lost:
        print(f"{ev.lost} record(s) overwritten before they were read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
