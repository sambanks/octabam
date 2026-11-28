#!/usr/bin/env python3
"""Hunt the frame-interrupt stall with the frame log read continuously (an image built with tools/hw/framelog.patch).

    .venv/bin/python3 tools/hw/ot_stallhunt.py [--trials 200] [--project out/v06c/V06_OCT_01] [--programs 0,0,1,2,3]

Each trial is what ot_matrix.py run does for one layout: STOP, program change, START with a 120 BPM host clock and the unit's
USB audio capture open, play, STOP. A thread reads the frame log (ot_stall.frame_log) as fast as the unit answers and keeps the
last SNAPS snapshots. When a read fails (the unit froze or left USB) the buffer is written to out/hw/stall/<time>.json: the
entries before the stop, with their entry times, durations and chain ends, and what the host had just sent. Also written, every
trial, the longest gap between two frame-interrupt entries seen in the 300 ms after each START and program change (the grid is
362.8 us), so the distribution of a normal entry is on disk beside the stall's.
Stops when the unit is lost; it does not retry. A command that fails is printed in full.
"""
import argparse
import collections
import json
import pathlib
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ot_events  # noqa: E402
import ot_ladder as L  # noqa: E402
import ot_stall  # noqa: E402
import load_meter as lm  # noqa: E402

PORT = "Elektron Octatrack DPS-1"
SNAPS = 400
OUT = pathlib.Path("out/hw/stall")


class Poller(threading.Thread):
    def __init__(self, dev):
        super().__init__(daemon=True)
        self.dev = dev
        self.buf = collections.deque(maxlen=SNAPS)
        self.lost = threading.Event()
        self.err = None
        self.stop_flag = threading.Event()
        self.mark = None                    # (label, t0): the host's last command
        self.i = 0                          # snapshots taken

    def run(self):
        while not self.stop_flag.is_set():
            try:
                fl = ot_stall.frame_log(self.dev)
            except Exception as e:  # noqa: BLE001
                self.err = repr(e)
                self.lost.set()
                return
            self.i += 1
            self.buf.append({"i": self.i, "t": time.monotonic(), "mark": self.mark, "count": fl["count"], "frozen": fl["frozen"],
                             "frames": fl["frames"]})


def max_gap(snaps):
    """The longest entry-to-entry gap (us) inside any snapshot."""
    g = 0.0
    for s in snaps:
        f = s["frames"]
        for a, b in zip(f, f[1:]):
            d = b[0] - a[0]
            if 0 < d < 5000:            # a read that raced the unit's writes gives a wrapped or negative difference
                g = max(g, d)
    return g


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--project", default="out/v06c/V06_OCT_01")
    ap.add_argument("--programs", default="0,0,1,2,3")
    ap.add_argument("--play", type=float, default=8.0)
    ap.add_argument("--audio", default="Octatrack")
    ap.add_argument("--noload", action="store_true", help="do not reload the project first")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not a.noload:
        r = subprocess.run([sys.executable, str(HERE / "ot_card.py"), "load", a.project])
        if r.returncode:
            sys.exit("ot_card.py load failed")
    import numpy as np  # noqa: F401
    import sounddevice as sd
    import usb_transport_probe as U
    dev = lm.libusb_device()
    audio_dev, nch = U.find_input(a.audio)
    cap = sd.InputStream(device=audio_dev, channels=nch, samplerate=44100, dtype="float32", callback=lambda *x: None)
    clock = L.Clock(120.0, PORT)
    poll = Poller(dev)
    progs = [int(x) for x in a.programs.split(",")]
    stats = []
    stamp = time.strftime("%Y%m%d-%H%M%S")
    try:
        with cap:
            poll.start()
            for n in range(a.trials):
                for prog in progs:
                    if poll.lost.is_set():
                        raise SystemExit("lost")
                    poll.mark = ("stop", n, prog)
                    clock.stop()
                    ot_events.wait_stopped(clock.remote, 0.3)
                    poll.mark = ("pc", n, prog)
                    k0 = poll.i
                    clock.pc_wait(1, prog, 0.8)
                    time.sleep(0.3)
                    pc_gap = max_gap([x for x in poll.buf if x["i"] > k0])
                    poll.mark = ("start", n, prog)
                    k1 = poll.i
                    clock.start()
                    time.sleep(0.3)
                    st_gap = max_gap([x for x in poll.buf if x["i"] > k1])
                    stats.append({"trial": n, "prog": prog, "pc_gap_us": pc_gap, "start_gap_us": st_gap})
                    t0 = time.monotonic()
                    while time.monotonic() - t0 < a.play - 0.3:
                        if poll.lost.is_set():
                            raise SystemExit("lost")
                        time.sleep(0.1)
                print(f"trial {n}: max pc gap {max(s['pc_gap_us'] for s in stats if s['trial'] == n):.0f} us, "
                      f"max start gap {max(s['start_gap_us'] for s in stats if s['trial'] == n):.0f} us", flush=True)
    except SystemExit as e:
        print("stopped:", e)
    finally:
        poll.stop_flag.set()
        time.sleep(0.2)
        clock.stop()
        snaps = list(poll.buf)
        rec = {"error": poll.err, "lost": poll.lost.is_set(), "stats": stats, "snapshots": snaps[-SNAPS:]}
        f = OUT / f"hunt_{stamp}.json"
        f.write_text(json.dumps(rec))
        print(f"{'UNIT LOST: ' + str(poll.err) if poll.lost.is_set() else 'finished'}; {len(snaps)} snapshots; written {f}")


if __name__ == "__main__":
    main()
