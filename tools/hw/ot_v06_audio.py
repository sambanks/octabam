#!/usr/bin/env python3
"""Per-track audio checks for the v0.6 items, over the one cable (USB audio with TRACKS PRE: track t is channels 2t-2 and
2t-1 of the capture; MAIN and CUE follow the sixteen).

    .venv/bin/python3 tools/hw/ot_v06_audio.py tracks PROG [--secs 6]      # per-track level for a program change
    .venv/bin/python3 tools/hw/ot_v06_audio.py wave-stop                    # #1232 (image `octabam`, project V06_OCT, PC 3)

`Rig.play` does what ot_matrix.py run does for one layout (STOP, program change, settle, START with a 120 BPM host clock,
the capture open) and returns the audio. The checks read a track's own channels, so a machine that plays on T1 is told
from the stimulus on the other tracks. Every number is printed.
"""
import argparse
import sys
import time
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402
import sounddevice as sd  # noqa: E402
import ot_events  # noqa: E402
import ot_ladder as L  # noqa: E402
import usb_transport_probe as U  # noqa: E402

PORT = "Elektron Octatrack DPS-1"
FS = 44100


def db(v):
    return 20.0 * np.log10(max(float(v), 1e-12))


class Rig:
    def __init__(self, audio="Octatrack", bpm=120.0):
        self.dev, self.nch = U.find_input(audio)
        self.chunks = []
        self.stream = sd.InputStream(device=self.dev, channels=self.nch, samplerate=FS, dtype="float32",
                                     callback=lambda i, f, t, s: self.chunks.append(i.copy()))
        self.clock = L.Clock(bpm, PORT)
        self.stream.start()
        time.sleep(0.5)

    def close(self):
        self.stream.stop()
        self.clock.stop()
        self.clock.close()

    def take(self):
        c, self.chunks = self.chunks, []
        return np.concatenate(c).astype(np.float64) if c else np.zeros((0, self.nch))

    def prepare(self, prog, settle=3.0, bank_settle=3.0):
        self.clock.stop()
        ot_events.wait_stopped(self.clock.remote, 0.5)
        self.clock.pc_wait(1, prog, 0.8)
        time.sleep(settle)

    def play(self, prog, secs, events=(), tail=0.0, stops=1):
        """Program change, START, `events` as (seconds after START, callable), STOP after `secs`, then `tail` seconds.
        Returns (x, t_stop): the audio from START and the sample index of STOP."""
        self.prepare(prog)
        self.take()
        t0 = time.monotonic()
        self.clock.start()
        pend = sorted(events, key=lambda e: e[0])
        while time.monotonic() - t0 < secs:
            while pend and time.monotonic() - t0 >= pend[0][0]:
                pend.pop(0)[1]()
            time.sleep(0.005)
        n_stop = int((time.monotonic() - t0) * FS)
        for _ in range(stops):
            self.clock.stop()
            time.sleep(0.05)
        time.sleep(tail)
        x = self.take()
        return x, n_stop


def track_cols(t):
    return (2 * t - 2, 2 * t - 1)


def level(x, t, a=0.0, b=None):
    """RMS dBFS of track t over seconds a..b of x."""
    c0, c1 = track_cols(t)
    s = x[int(a * FS):None if b is None else int(b * FS), c0:c1 + 1]
    return db(np.sqrt((s ** 2).mean())) if len(s) else -240.0


def peak(x, t, a=0.0, b=None):
    c0, c1 = track_cols(t)
    s = x[int(a * FS):None if b is None else int(b * FS), c0:c1 + 1]
    return db(np.abs(s).max()) if len(s) else -240.0


def cmd_tracks(a):
    rig = Rig()
    try:
        x, n = rig.play(a.prog, a.secs, tail=1.0)
        print(f"program {a.prog}: {len(x) / FS:.1f} s captured, STOP at {n / FS:.1f} s")
        for t in range(1, 9):
            print(f"  T{t}: rms {level(x, t, 0.5, n / FS):7.1f}  peak {peak(x, t, 0.5, n / FS):7.1f}  "
                  f"after STOP (0.5-1.0 s) rms {level(x, t, n / FS + 0.5):7.1f}")
    finally:
        rig.close()


def cmd_wave_stop(a):
    """#1232: a WAVE track with AMP HOLD INF and REL INF keeps sounding after STOP on the build before the fix."""
    rig = Rig()
    try:
        def amp(t):
            return [(0.2, lambda: rig.clock.cc(t, 23, 127)), (0.25, lambda: rig.clock.cc(t, 24, 127))]
        ev = amp(1) + amp(2)
        for stops in (1, 2):
            x, n = rig.play(3, 6.0, events=ev, tail=3.0, stops=stops)
            ts = n / FS
            print(f"STOP x{stops}: playing T1 {level(x, 1, 1.0, ts):.1f} dBFS, T2 {level(x, 2, 1.0, ts):.1f}; "
                  f"after STOP 0.5-3.0 s: T1 {level(x, 1, ts + 0.5):.1f}, T2 {level(x, 2, ts + 0.5):.1f}; "
                  f"T3 (not WAVE) {level(x, 3, 1.0, ts):.1f}")
    finally:
        rig.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tracks")
    p.add_argument("prog", type=int)
    p.add_argument("--secs", type=float, default=6.0)
    sub.add_parser("wave-stop")
    a = ap.parse_args()
    {"tracks": cmd_tracks, "wave-stop": cmd_wave_stop}[a.cmd](a)


if __name__ == "__main__":
    main()
