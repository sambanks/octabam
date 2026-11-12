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
`Events` keeps the last head it saw and returns the records since, with `lost` the number overwritten before they
were read. A scenario calls `wait_for` instead of sleeping: it returns the first record that matches, or raises.

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

KINDS = {1: "LOADALL", 2: "LOADMASK", 3: "NEWPROJ", 4: "BANKW", 5: "PSTORE", 6: "PRELOAD",
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
    def __init__(self, ctrl, from_start=False):
        self.ctrl = ctrl
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
        end = time.monotonic() + timeout
        while True:
            n = self.header()[1]
            if n != since:
                return n
            if time.monotonic() >= end:
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
        """The first record of `kind` (a name or a number), with `arg` when given. `tick` is called between
        polls (the port's gate advances the machine there; on a unit it defaults to a 5 ms sleep). With
        `strict`, records lost while waiting raise Lost instead of being counted."""
        k = BY_NAME[kind] if isinstance(kind, str) else kind
        end = time.monotonic() + timeout
        passed = []
        while True:
            for r in self.poll():
                passed.append(r)
                if r["kind"] == k and (arg is None or r["arg"] == arg):
                    r["passed"] = passed[:-1]
                    return r
            if strict and self.lost:
                raise Lost(f"{self.lost} record(s) overwritten before they were read")
            if time.monotonic() >= end:
                raise TimeoutError(f"no {KINDS.get(k, k)}{'' if arg is None else f' arg {arg}'} in {timeout} s; "
                                   f"passed: {[(p['name'], p['arg']) for p in passed]}")
            (tick or (lambda: time.sleep(0.005)))()


def unit_ctrl(dev):
    return lambda off, n: bytes(dev.ctrl_transfer(0xc0, 0x5a, off, 0, n, timeout=1000))


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
