#!/usr/bin/env python3
"""Watch a unit on USB and stop the moment it freezes, keeping the seconds that led up to it.

    python3 tools/hw/freeze_watch.py [--port NAME] [--image FILE] [--out DIR]
    python3 tools/hw/freeze_watch.py list         # MIDI sources and the USB device
    python3 tools/hw/freeze_watch.py selftest     # the detector on synthetic streams; no unit

Nothing is added to the image under test: it reads what the unit already sends on its USB cable.

  MIDI clock  24 a beat while the sequencer plays (PROJECT > MIDI > SYNC: CLOCK SEND and TRANSPORT
              SEND on). STOP ends it on purpose; clock that stops with no STOP, after two beats of it,
              is a sequencer stall.
  USB         a GET_STATUS request to the device each second, answered by the ColdFire's USB code.
              --usb-fails unanswered in a row is a main-processor hang (or the cable); the device
              leaving the bus is a reboot, a power-off or the cable. Needs pyusb and libusb
              (`brew install libusb`, `.venv/bin/pip install pyusb`); without them MIDI only, and
              the unit's MIDI source going away stands in for it leaving the bus.

After a stall the USB heartbeat runs --follow seconds more, so the freeze file says whether the
main processor went down with the sequencer. Every second a line (clocks, tempo, the longest gap
between clocks, USB round trip) goes to OUT/watch_<time>.jsonl, and every non-clock MIDI message
as its own line; on a freeze the last --keep seconds go to OUT/freeze_<time>.json and the exit
status is 3. --image records that file's sha256 with the log, so the port can run the same bytes.

Measured on an MKII, 2 Nov 2026: four freezes caught, two kinds -- clock stopped with USB answering
for over five minutes after (the screen still responsive), and clock and USB stopping in the same
second (nothing responsive); a reboot was seen as the device leaving the bus.

What it cannot see: a freeze while the transport is stopped unless USB dies with it; glitches that
leave the clock running; what the unit was executing (it reads none of its memory).
"""
import argparse, collections, hashlib, json, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
VID, PID = 0x1935, 0x0002                 # Elektron Octatrack
CLOCK, START, CONTINUE, STOP, SENSE = 0xF8, 0xFA, 0xFB, 0xFC, 0xFE
FREEZE = 3                                # exit status on a freeze
NAMES = ("octatrack", "elektron")         # a MIDI source whose name holds one of these


class Detector:
    """The freeze rules, fed with timestamps: midi() per packet, usb() once a second. Pure, so the
    selftest drives it with synthetic time."""

    def __init__(self, clock_timeout=1.0, usb_fails=3, min_clocks=48):
        self.clock_timeout, self.usb_fails, self.min_clocks = clock_timeout, usb_fails, min_clocks
        self.last_clock = self.last_stop = None
        self.since_start = 0              # clocks since START/CONTINUE (or since the first one seen)
        self.window, self.max_gap = [], 0.0
        self.fails = 0

    def midi(self, t, data):
        """-> the packet without its real-time bytes (clock, start/stop, active sensing), for the log."""
        rest = bytearray()
        for b in data:
            if b == CLOCK:
                if self.last_clock is not None:
                    self.max_gap = max(self.max_gap, t - self.last_clock)
                self.last_clock = t
                self.since_start += 1
                self.window.append(t)
            elif b in (START, CONTINUE):
                self.since_start, self.last_stop = 0, None
            elif b == STOP:
                self.last_stop = t
            if b not in (CLOCK, SENSE):
                rest.append(b)
        return bytes(rest)

    def second(self):
        """-> this second's clock count, tempo and longest gap; starts the next second."""
        w, self.window = self.window, []
        gap, self.max_gap = self.max_gap, 0.0
        bpm = 60 * (len(w) - 1) / (24 * (w[-1] - w[0])) if len(w) > 2 and w[-1] > w[0] else None
        return {"clocks": len(w), "bpm": round(bpm, 2) if bpm else None, "max_gap_ms": round(1000 * gap, 1)}

    def stalled(self, t):
        if self.last_clock is None or self.since_start < self.min_clocks:
            return False
        if self.last_stop is not None and self.last_stop >= self.last_clock:
            return False
        return t - self.last_clock > self.clock_timeout

    def usb(self, state):
        """state: 'ok', 'fail' or 'gone' -> 'usb_gone', 'usb_dead' or None."""
        if state == "gone":
            return "usb_gone"
        self.fails = 0 if state == "ok" else self.fails + 1
        return "usb_dead" if self.fails >= self.usb_fails else None


class Usb:
    """The unit's presence and a GET_STATUS round trip; inert without pyusb or libusb."""

    def __init__(self):
        try:
            import usb.core
            import load_meter
            self.core, self.backend = usb.core, load_meter.libusb_backend()
        except ImportError:
            self.core = self.backend = None
        self.dev = None

    @property
    def available(self):
        return self.core is not None and self.backend is not None

    def find(self):
        return self.core.find(idVendor=VID, idProduct=PID, backend=self.backend) if self.available else None

    def poll(self):
        """-> ('ok', ms), ('fail', None), ('gone', None), or (None, None) before the unit is first seen."""
        if not self.available:
            return None, None
        if self.dev is None:
            self.dev = self.find()
            if self.dev is None:
                return None, None
        if self.find() is None:
            return "gone", None
        t = time.monotonic()
        try:
            self.dev.ctrl_transfer(0x80, 0x00, 0, 0, 2, timeout=500)
        except self.core.USBError:
            return "fail", None
        return "ok", round(1000 * (time.monotonic() - t), 1)


def source_name(want):
    import ot_midi
    names = [n for n, _ in ot_midi.endpoints("src")]
    keys = (want.lower(),) if want else NAMES
    return next((n for n in names if any(k in n.lower() for k in keys)), None)


def cmd_list(_a):
    import ot_midi
    print("MIDI sources:", [n for n, _ in ot_midi.endpoints("src")] or "none")
    u = Usb()
    if not u.available:
        print("USB: no pyusb or no libusb (brew install libusb; .venv/bin/pip install pyusb)")
        return 0
    state, ms = u.poll()
    print("Octatrack on USB:", f"yes, GET_STATUS {ms} ms" if state == "ok" else state or "no")
    return 0


def cmd_watch(a):
    import ot_midi
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    started, stamp = time.time(), time.strftime("%Y%m%d_%H%M%S")
    path = out / f"watch_{stamp}.jsonl"
    log_f = path.open("a", buffering=1)
    history = collections.deque(maxlen=a.keep)
    det, u = Detector(a.clock_timeout, a.usb_fails), Usb()
    image = None
    if a.image:
        p = pathlib.Path(a.image)
        image = {"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}

    def log(rec):
        rec = {"t": round(time.time(), 3), "s": round(time.time() - started, 1), **rec}
        log_f.write(json.dumps(rec) + "\n")
        return rec

    log({"event": "watch_start", "image": image, "usb": u.available})
    print(f"logging to {path}" + ("" if u.available else
          "\nUSB heartbeat off: no pyusb or no libusb (brew install libusb; .venv/bin/pip install pyusb)"),
          flush=True)
    inp, seen = None, None

    def on_bytes(data):
        rest = det.midi(time.monotonic(), data)
        if rest:
            log({"event": "midi", "hex": rest.hex(" ")})

    def freeze(kind, why):
        rec = log({"event": "FREEZE", "kind": kind, "why": why})
        dump = out / f"freeze_{time.strftime('%Y%m%d_%H%M%S')}.json"
        dump.write_text(json.dumps({"freeze": rec, "image": image, "seen_s": seen and round(time.time() - seen, 1),
                                    "history": list(history)}, indent=1))
        print(f"\n*** FREEZE ({kind}): {why}"
              + (f"\n    {round(time.time() - seen)} s after the unit appeared" if seen else "")
              + f"\n    history: {dump}\n    log: {path}"
              + "\n    if the screen shows EXCEPTION, photograph it before touching the unit", flush=True)
        return FREEZE

    try:
        while True:
            if inp is None:
                name = source_name(a.port)
                if name:
                    inp = ot_midi.In(name, on_bytes)
                    log({"event": "midi_open", "port": name})
                    print(f"listening on MIDI '{name}'", flush=True)
            t_end = time.monotonic() + 1.0
            while time.monotonic() < t_end:
                ot_midi.In.pump(0.05)
            if inp is not None and source_name(a.port) is None:
                log({"event": "midi_gone"})
                if not u.available:               # the only sign of a reboot without USB
                    return freeze("midi_gone", "the unit's MIDI source went away (reboot, power-off or cable)")
                inp = None                        # USB says whether the unit left; reconnect when it is back
            state, ms = u.poll()
            if state and seen is None:
                seen = time.time()
                log({"event": "usb_appeared"})
                print("unit on USB", flush=True)
            verdict = det.usb(state) if state else None
            s = log({"event": "second", **det.second(), "usb": state, "usb_ms": ms})
            history.append(s)
            if verdict == "usb_gone":
                return freeze(verdict, "the unit left the USB bus (reboot, power-off or cable)")
            if verdict == "usb_dead":
                return freeze(verdict, f"{det.fails} USB requests in a row went unanswered (main processor hang?)")
            if det.stalled(time.monotonic()):
                print(f"clock stalled; following USB for {a.follow} s ...", flush=True)
                dead = None
                for _ in range(a.follow if u.available else 0):
                    time.sleep(1.0)
                    state, ms = u.poll()
                    history.append(log({"event": "after_stall", "usb": state, "usb_ms": ms}))
                    if state != "ok" and dead is None:
                        dead = history[-1]["s"]
                usb_note = ("" if not u.available else
                            f"; USB stopped answering at {dead} s" if dead else f"; USB answered for {a.follow} s")
                return freeze("clock_stall", f"MIDI clock stopped for over {a.clock_timeout} s with no STOP{usb_note}")
            if int(s["s"]) % 10 == 0:
                print(f"{time.strftime('%H:%M:%S')}  clocks {s['clocks']:3d}/s  bpm {s['bpm']}  "
                      f"max gap {s['max_gap_ms']} ms  usb {state} {ms} ms", flush=True)
    except KeyboardInterrupt:
        log({"event": "stopped_by_user"})
        print(f"\nstopped; log at {path}")
        return 0
    finally:
        log_f.close()


def cmd_selftest(_a):
    fails = []

    def expect(what, got, want):
        ok = got == want
        print(f"  [{'ok' if ok else 'FAIL'}] {what}: {got!r}")
        if not ok:
            fails.append(what)

    def run(events, until, step=0.25, **kw):
        """events: (t, bytes); -> the first time stalled() holds, or None by `until`."""
        d, ev, t = Detector(**kw), sorted(events), 0.0
        while t <= until:
            while ev and ev[0][0] <= t:
                d.midi(*ev.pop(0))
            if d.stalled(t):
                return round(t, 2)
            t += step
        return None

    def clocks(t0, seconds, bpm=120):
        n = int(seconds * bpm * 24 / 60)
        return [(t0 + i * 60 / (bpm * 24), bytes([CLOCK])) for i in range(n)]

    play = [(0.0, bytes([START]))] + clocks(0.01, 3.0)
    t = run(play, 10)
    expect(f"clock stops with no STOP: a stall about clock_timeout after the last clock (at {t} s)",
           t is not None and 3.9 <= t <= 4.3, True)
    expect("clock then STOP: no stall", run(play + [(3.02, bytes([STOP]))], 10), None)
    expect("under two beats of clock, then nothing: no stall",
           run([(0.0, bytes([START]))] + clocks(0.01, 0.4), 10), None)
    expect("a minute of steady clock: no stall", run([(0.0, bytes([START]))] + clocks(0.01, 60.0), 60.0), None)
    expect("STOP, then START and clock that stops: a stall",
           run(play + [(3.02, bytes([STOP])), (4.0, bytes([START]))] + clocks(4.01, 3.0), 12) is not None, True)
    expect("clock with no START seen (watch joined mid-song) that stops: a stall", run(clocks(0.0, 3.0), 10) is not None, True)

    d = Detector()
    expect("real-time bytes dropped from the logged packet, the rest kept",
           d.midi(0.0, bytes([CLOCK, 0x90, 0x24, 0x64, CLOCK, SENSE])).hex(" "), "90 24 64")
    expect("two clocks in that packet counted", d.since_start, 2)
    d = Detector()
    for i in range(48):
        d.midi(i / 48, bytes([CLOCK]))
    s = d.second()
    expect("120 BPM from one second of clock", (s["clocks"], round(s["bpm"])), (48, 120))

    import ctypes, struct
    import ot_midi
    msgs = [bytes([START]), bytes([0xB0, 0x10, 0x40]), bytes([0xB0, 0x11, 0x00]), bytes([CLOCK]),
            bytes([0xF0, 0x00, 0x20]), bytes([0x3C, 0xF7]), bytes([0x90, 0x24, 0x64])]

    def pktlist(aligned):
        """A MIDIPacketList laid out at a 4-byte-aligned address, its packets aligned or not."""
        raw = bytearray(struct.pack("<I", len(msgs)))
        for m in msgs:
            raw += struct.pack("<QH", 0x1122334455667788, len(m)) + m
            if aligned:
                raw += bytes(-len(raw) % 4)
        buf = ctypes.create_string_buffer(bytes(raw) + bytes(16))
        return buf, ctypes.addressof(buf)
    for aligned in (True, False):
        buf, addr = pktlist(aligned)
        got = list(ot_midi.packets(addr)) if ot_midi.ARM or not aligned else msgs
        expect(f"a packet list {'aligned' if aligned else 'unaligned'} (a SysEx across two packets) reads whole",
               got, msgs)

    d = Detector(usb_fails=3)
    expect("two unanswered, then an answer: no hang", [d.usb(x) for x in ("fail", "fail", "ok", "fail")],
           [None, None, None, None])
    expect("three unanswered in a row: usb_dead", [d.usb(x) for x in ("fail", "fail")], [None, "usb_dead"])
    expect("the device gone: usb_gone", Detector().usb("gone"), "usb_gone")
    print(f"selftest: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="watch", choices=("watch", "list", "selftest"))
    ap.add_argument("--port", help="part of the MIDI source's name (default: one naming Octatrack or Elektron)")
    ap.add_argument("--image", help="the image on the unit: its sha256 goes in the log")
    ap.add_argument("--out", default=str(ROOT / "out/hw/freeze"), help="where the logs go (default out/hw/freeze)")
    ap.add_argument("--clock-timeout", type=float, default=1.0, help="seconds of missing clock that count as a stall")
    ap.add_argument("--usb-fails", type=int, default=3, help="unanswered USB requests in a row that count as a hang")
    ap.add_argument("--follow", type=int, default=20, help="seconds of USB heartbeat kept after a stall")
    ap.add_argument("--keep", type=int, default=120, help="seconds of history saved with a freeze")
    a = ap.parse_args()
    return {"watch": cmd_watch, "list": cmd_list, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
