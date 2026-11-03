#!/usr/bin/env python3
"""Latency from a crossfader step (CC 48) to the MIDI SCENES lock CC on the wire, per condition.

    python3 tools/hw/ot_xflag.py [--steps 40] [--gap 1.5] [--out out/hw/xflag/NAME.json] [--conditions stopped,playing,flood]

Needs a loaded project with a MIDI track on channel 11 whose CC 1 is locked in scene 1 (index 0) and scene 16
(index 15) with different values: `ot_scenes.py stamp PROJECT --all-scenes`. The probe selects scene A = 0
(CC 55) and scene B = 15 (CC 56), then alternates the crossfader between 0 and 127. Each step is stamped with the
host's monotonic clock when sent and when the first `ba 01 vv` arrives afterwards; the step is "answered" if one
arrives within --gap seconds.

Conditions: stopped (no clock, no START); playing (host clock at 120 BPM and START); flood (playing, plus a
CC sweep on audio tracks 2-8 knobs, 200 CCs a second, to load the main loop).

Resolution is the USB MIDI polling interval (about 1 ms) plus CoreMIDI scheduling. A latency near 0.125 s or
0.5 s is the sequencer step or the track's trig grid (steps 1, 5, 9, 13 at 120 BPM).
"""
import argparse
import ctypes
import json
import pathlib
import queue
import statistics
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ot_midi as M          # noqa: E402
import ot_fuzz as F          # noqa: E402

PORT = "Elektron Octatrack DPS-1"


class Rx:
    """Incoming messages other than clock and active sensing, each stamped with time.monotonic()."""

    def __init__(self, port_name):
        self.q = queue.Queue()
        client = ctypes.c_uint32(); inport = ctypes.c_uint32()
        M.cm.MIDIClientCreate(M.cfstr("octabam-xflag"), None, None, ctypes.byref(client))

        def cb(pktlist, _a, _b):
            now = time.monotonic()
            for data in M.packets(pktlist):
                rest = bytes(b for b in data if b not in (0xF8, 0xFE))
                if rest:
                    self.q.put((now, rest))
        self.proc = M.READPROC(cb)
        M.cm.MIDIInputPortCreate(client, M.cfstr("in"), self.proc, None, ctypes.byref(inport))
        src = M.find("src", port_name)
        if src is None:
            sys.exit(f"no MIDI source named {port_name!r}")
        M.cm.MIDIPortConnectSource(inport, src, None)
        self.pump = threading.Thread(target=self._run, daemon=True)
        self.pump.start()

    def _run(self):
        M.cf.CFRunLoopRunInMode.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_bool]
        mode = M.cfstr("kCFRunLoopDefaultMode")
        while True:
            M.cf.CFRunLoopRunInMode(mode, 0.05, False)

    def drain(self):
        out = []
        while True:
            try:
                out.append(self.q.get_nowait())
            except queue.Empty:
                return out


def run_condition(name, out, rx, steps, gap):
    clock = None
    flood_stop = threading.Event()
    if name in ("playing", "flood"):
        clock = F.ClockGen(out, 120.0); clock.start(); out.send([0xFA]); time.sleep(2.0)
    if name == "flood":
        def flood():
            v, tr = 0, 1
            while not flood_stop.is_set():
                out.send([0xB0 | tr, 40 + (v % 6), v % 128]); v += 1; tr = 1 + tr % 7
                time.sleep(0.005)
        threading.Thread(target=flood, daemon=True).start()
    out.send([0xB0, 55, 0]); out.send([0xB0, 56, 15]); out.send([0xB0, 48, 0]); time.sleep(2.0)
    rx.drain()
    rows, xf = [], 0
    for i in range(steps):
        xf = 127 if xf == 0 else 0
        rx.drain()
        t0 = time.monotonic()
        out.send([0xB0, 48, xf])
        hit = None
        while time.monotonic() - t0 < gap:
            for t, msg in rx.drain():
                if msg[:2] == b"\xba\x01" and hit is None:
                    hit = (t - t0, msg[2])
            if hit is not None:
                break
            time.sleep(0.0005)
        rows.append({"i": i, "xf": xf, "lag_ms": None if hit is None else round(1000 * hit[0], 2),
                     "value": None if hit is None else hit[1]})
        time.sleep(max(0.0, gap - (time.monotonic() - t0)))
    flood_stop.set()
    if clock is not None:
        out.send([0xFC]); clock.stop_evt.set(); time.sleep(0.5)
    return rows


def summary(rows):
    lags = sorted(r["lag_ms"] for r in rows if r["lag_ms"] is not None)
    s = {"steps": len(rows), "answered": len(lags)}
    if lags:
        s.update(min=lags[0], median=round(statistics.median(lags), 2),
                 p95=lags[min(len(lags) - 1, int(0.95 * len(lags)))], max=lags[-1])
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--gap", type=float, default=1.5)
    ap.add_argument("--conditions", default="stopped,playing,flood")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out, rx = M.Out(PORT), Rx(PORT)
    result = {}
    for name in a.conditions.split(","):
        rows = run_condition(name, out, rx, a.steps, a.gap)
        result[name] = {"summary": summary(rows), "rows": rows}
        print(f"{name:8s} {result[name]['summary']}", flush=True)
    if a.out:
        p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
