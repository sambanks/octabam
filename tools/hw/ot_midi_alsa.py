#!/usr/bin/env python3
"""ot_midi.py's calls over ALSA raw MIDI, for a Linux host: `endpoints`, `find`, `Out` and `In`.

ot_midi.py imports these on Linux in place of its CoreMIDI ones, so the tools that use them
(ot_ladder.Clock and so ot_matrix and ot_suite, ot_midi's own list, listen and sends,
freeze_watch) run unchanged. The CoreMIDI-only parts of ot_midi.py (`packets`, `cfstr`,
`READPROC`) have no equivalent here; ot_djump.py and ot_xflag.py call them, so they stay
macOS-only.

The unit's USB MIDI port is a raw MIDI device, /dev/snd/midiC<card>D<device>, which
snd-usb-audio creates when the unit is plugged in (on WSL2: attached with usbipd-win). A
port's name is its card's short name in /proc/asound/cards, for the unit "Elektron
Octatrack DPS-1", as CoreMIDI names it. A card's second and later devices add " 2", " 3"
and so on. Every port is both a source and a destination. Reading and writing /dev/snd needs the audio group
(docs/contributing/HARDWARE_TESTING.md, "What you need").

    python3 tools/hw/ot_midi_alsa.py selftest      # the message parser, no device
"""
import glob
import os
import re
import select
import sys
import threading
import time


def _cards():
    """{card number: short name}, from /proc/asound/cards, whose line for a card is
    ' N [id ]: driver - short name'. A USB card's short name is the device's product string,
    the name CoreMIDI gives its port ("Elektron Octatrack DPS-1"); the long name on the next
    line puts the maker first ("Elektron Music Machines Elektron Octatrack DPS-1 at ...",
    WSL2, 8 Nov 2026)."""
    try:
        lines = open("/proc/asound/cards").read().splitlines()
    except OSError:
        return {}
    out = {}
    for line in lines:
        m = re.match(r"\s*(\d+)\s+\[[^\]]*\]:\s*(.*)$", line)
        if m:
            out[int(m.group(1))] = m.group(2).split(" - ", 1)[-1].strip()
    return out


def endpoints(kind):
    """[(name, device path)] for every raw MIDI device. A raw MIDI device reads and writes, so
    `kind` ('src' or 'dst') selects nothing; it is kept for ot_midi.py's signature."""
    cards = _cards()
    eps = []
    for path in glob.glob("/dev/snd/midiC*D*"):
        m = re.search(r"midiC(\d+)D(\d+)$", path)
        if m:
            c, d = int(m.group(1)), int(m.group(2))
            eps.append(((c, d), cards.get(c, f"card {c}") + (f" {d + 1}" if d else ""), path))
    return [(name, path) for _, name, path in sorted(eps)]


def find(kind, name, wait=3.0):
    """The device path of the port called `name`, or None. Polls for `wait` s, as ot_midi.find
    does: the device appears a moment after the unit is attached."""
    t0 = time.time()
    while True:
        m = [ep for n, ep in endpoints(kind) if n == name]
        if m or time.time() - t0 >= wait:
            return m[0] if m else None
        time.sleep(0.1)


class Out:
    """Sends to port `port_name`. Opened with O_APPEND, ALSA's shared open: several writers may
    hold the port at once (ot_ladder.Clock's thread beside another Out), and each write goes out
    whole. The lock keeps one object's sends from interleaving across its threads."""

    def __init__(self, port_name):
        self.dest = find("dst", port_name)
        if self.dest is None:
            sys.exit(f"no MIDI destination named {port_name!r}; have "
                     f"{[n for n, _ in endpoints('dst')]}")
        self.fd = os.open(self.dest, os.O_WRONLY | os.O_APPEND)
        self.lock = threading.Lock()

    def send(self, data):
        b = bytes(data)
        with self.lock:
            while b:
                b = b[os.write(self.fd, b):]


class Parser:
    """Raw MIDI bytes to whole messages, one `on_bytes(data)` call each, as CoreMIDI's packets
    deliver them: a real-time byte (F8 to FF) alone, wherever it falls; a SysEx from F0 to F7
    (a status byte ends it early); a channel message with its data bytes, running status
    filled in; a system common message with its own."""
    CHANNEL = {0x80: 3, 0x90: 3, 0xA0: 3, 0xB0: 3, 0xC0: 2, 0xD0: 2, 0xE0: 3}
    COMMON = {0xF1: 2, 0xF2: 3, 0xF3: 2}

    def __init__(self, on_bytes):
        self.cb = on_bytes
        self.msg = bytearray()
        self.need = 0
        self.running = None
        self.sysex = None

    def feed(self, data):
        for b in data:
            if b >= 0xF8:
                self.cb(bytes([b]))
            elif self.sysex is not None and b < 0x80:
                self.sysex.append(b)
            elif self.sysex is not None:
                if b == 0xF7:
                    self.sysex.append(b)
                self.cb(bytes(self.sysex))
                self.sysex = None
                if b != 0xF7:
                    self._status(b)
            elif b == 0xF0:
                self.sysex = bytearray([b])
                self.msg, self.running = bytearray(), None
            elif b & 0x80:
                self._status(b)
            else:
                if not self.msg:
                    if self.running is None:
                        continue                          # a data byte with no status: dropped
                    self.msg = bytearray([self.running])
                    self.need = self.CHANNEL[self.running & 0xF0]
                self.msg.append(b)
                if len(self.msg) == self.need:
                    self.cb(bytes(self.msg))
                    self.msg = bytearray()

    def _status(self, b):
        if b == 0xF0:
            self.sysex = bytearray([b])
            self.msg, self.running = bytearray(), None
            return
        self.msg = bytearray([b])
        self.need = self.CHANNEL[b & 0xF0] if b < 0xF0 else self.COMMON.get(b, 1)
        self.running = b if b < 0xF0 else None
        if self.need == 1:                                # F6, F4, F5, a stray F7
            self.cb(bytes(self.msg))
            self.msg = bytearray()


class In:
    """Port `port_name`'s messages to `on_bytes(data)`, on a thread of its own, as CoreMIDI
    delivers them on its threads: anything shared with the caller needs a lock."""

    def __init__(self, port_name, on_bytes):
        self.src = find("src", port_name)
        if self.src is None:
            sys.exit(f"no MIDI source named {port_name!r}")
        self.fd = os.open(self.src, os.O_RDONLY | os.O_NONBLOCK)
        self.parser = Parser(on_bytes)
        self._stop = threading.Event()
        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()

    def _run(self):
        while not self._stop.is_set():
            if not select.select([self.fd], [], [], 0.1)[0]:
                continue
            try:
                data = os.read(self.fd, 256)
            except BlockingIOError:
                continue
            except OSError:
                return                                    # the unit went away
            self.parser.feed(data)

    def close(self):
        """No more deliveries."""
        self._stop.set()
        self.th.join(1.0)
        os.close(self.fd)

    @staticmethod
    def pump(seconds):
        """CoreMIDI's run loop has no counterpart here: the reader thread delivers by itself."""
        time.sleep(seconds)


def selftest():
    got = []
    p = Parser(got.append)
    p.feed(bytes([0xC0, 0x05]))                           # program change
    p.feed(bytes([0xB0, 0x28]))                           # a CC split across two reads ...
    p.feed(bytes([0xF8, 0x40]))                           # ... with a clock inside it
    p.feed(bytes([0x29, 0x41]))                           # running status
    p.feed(bytes([0xF0, 0x00, 0x20]))                     # a SysEx split across reads
    p.feed(bytes([0x3C, 0xF7, 0xFA, 0xFC]))
    p.feed(bytes([0x12, 0xF0, 0x01, 0x90, 0x3C, 0x64]))  # a stray data byte; a SysEx cut by a note
    want = [b"\xc0\x05", b"\xf8", b"\xb0\x28\x40", b"\xb0\x29\x41", b"\xf0\x00\x20\x3c\xf7",
            b"\xfa", b"\xfc", b"\xf0\x01", b"\x90\x3c\x64"]
    for g, w in zip(got, want):
        print(f"  [{'PASS' if g == w else 'FAIL'}] {g.hex(' ')}  want {w.hex(' ')}")
    ok = got == want
    print(f"ot_midi_alsa selftest: {'ok' if ok else f'FAILED ({len(got)} messages, want {len(want)})'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        sys.exit(selftest())
    for name, path in endpoints("dst"):
        print(f"{path}  {name}")
