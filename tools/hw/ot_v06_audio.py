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

    def play(self, prog, secs, events=(), tail=0.0, stops=1, stop_gap=0.05):
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
        for k in range(stops):
            self.clock.stop()
            if k < stops - 1:
                time.sleep(stop_gap)
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
        rig.play(3, 3.0, tail=0.5)                      # the first START after a load is silent
        for stops in (1, 2):
            x, n = rig.play(3, 6.0, events=ev, tail=3.0, stops=stops)
            ts = n / FS
            print(f"STOP x{stops}: playing T1 {level(x, 1, 1.0, ts):.1f} dBFS, T2 {level(x, 2, 1.0, ts):.1f}; "
                  f"after STOP 0.5-3.0 s: T1 {level(x, 1, ts + 0.5):.1f}, T2 {level(x, 2, ts + 0.5):.1f}; "
                  f"T3 (not WAVE) {level(x, 3, 1.0, ts):.1f}")
    finally:
        rig.close()


def impulse(x, t, after=1.0):
    """Sample index of the loudest sample of track t in the second after `after`: one impulse of the stimulus."""
    c0, c1 = track_cols(t)
    seg = np.abs(x[int(after * FS):int((after + 1.0) * FS), c0:c1 + 1]).max(axis=1)
    return int(after * FS) + int(seg.argmax())


def win(x, t, i, a_ms, b_ms):
    """RMS dBFS of track t from a_ms to b_ms after sample i."""
    c0, c1 = track_cols(t)
    s = x[i + int(a_ms * FS / 1000):i + int(b_ms * FS / 1000), c0:c1 + 1]
    return db(np.sqrt((s ** 2).mean())) if s.size else -240.0


def cmd_verb(a):
    """#1234 on octabam-verbs (project V06_VRB; T6 plays the impulses): the stop kill, AMNT's fixed dry, PRE at SIZE 127."""
    rig = Rig()
    try:
        rig.play(1, 3.0, tail=0.5)                      # the first START after a load is silent
        print("-- STOP kill: the tail on T6 after a single STOP, and after STOP, STOP")
        for stops, gap in ((1, 0.0), (2, 0.05), (2, 0.3)):
            x, n = rig.play(1, 5.0, tail=3.0, stops=stops, stop_gap=gap)
            ts = n / FS
            print(f"  STOP x{stops} gap {gap:.2f} s: T6 rms {level(x, 6, ts + 0.3, ts + 1.0):7.1f} (0.3-1.0 s)  "
                  f"{level(x, 6, ts + 1.0, ts + 2.0):7.1f} (1-2 s)  {level(x, 6, ts + 2.0, ts + 3.0):7.1f} (2-3 s)", flush=True)
        print("-- AMNT: the dry hit (peak within 1 ms) and the wet (rms 30-250 ms after it) on T6")
        base = None
        for v in (0, 32, 64, 96, 127):
            x, n = rig.play(1, 4.0, events=[(0.05, lambda v=v: rig.clock.cc(6, 40, v))], tail=0.2)
            i = impulse(x, 6, 1.0)
            dry = db(np.abs(x[i - 44:i + 44, 10:12]).max())
            wet = win(x, 6, i, 30, 250)
            base = dry if base is None else base
            print(f"  AMNT {v:3d}: dry peak {dry:7.1f} dBFS ({dry - base:+5.1f} against AMNT 0)  wet rms {wet:7.1f} dBFS", flush=True)
        print("-- PRE at SIZE 127: energy after the dry hit, relative to its peak (program 1: PRE 0; program 2: PRE 127)")
        for prog in (1, 2):
            x, n = rig.play(prog, 4.0, tail=0.2)
            i = impulse(x, 6, 1.0)
            dry = db(np.abs(x[i - 44:i + 44, 10:12]).max())
            ws = [(a_, b_, win(x, 6, i, a_, b_) - dry) for a_, b_ in ((5, 20), (20, 50), (50, 80), (80, 120))]
            print(f"  program {prog}: " + "  ".join(f"{a_}-{b_} ms {r:+6.1f} dB" for a_, b_, r in ws), flush=True)
    finally:
        rig.close()


def env(x, cols, a_s, b_s, ms=20):
    """RMS envelope of the given columns in `ms` frames between a_s and b_s seconds."""
    seg = x[int(a_s * FS):int(b_s * FS), cols[0]:cols[1] + 1]
    n = int(ms * FS / 1000)
    k = len(seg) // n
    return np.sqrt((seg[:k * n].reshape(k, n, -1) ** 2).mean(axis=(1, 2)))


def cmd_vca_key(a):
    """#1219: VCA160's KEY T1 reads KEYBUS's mean square of T1. VCA160 is on FX1 of T2 (project V06_RIG, program 3, image V06-RIG),
    T2 plays steady pink noise and T1 hits every half second. The KEY knob (FX1 knob D, CC 37) is swept: the value that is T1 makes
    T2's level follow T1's hits (a negative correlation, compression), OFF makes T2 follow its own signal."""
    rig = Rig()
    try:
        rig.play(3, 3.0, tail=0.5)                      # the first START after a load is silent
        for v in (None, 7, 21, 35, 49, 63, 77, 91, 105, 119):         # None: KEY untouched (the Part's value); then the nine positions' midpoints
            ev = [(0.05, lambda: rig.clock.cc(2, 34, 0)), (0.10, lambda: rig.clock.cc(2, 35, 100))]
            if v is not None:
                ev.append((0.20, lambda v=v: rig.clock.cc(2, 37, v)))
            x, n = rig.play(3, 6.5, events=ev, tail=0.2)
            ts = n / FS
            e1 = env(x, (0, 1), 1.0, ts)
            e2 = env(x, (2, 3), 1.0, ts)
            m = min(len(e1), len(e2))
            c = float(np.corrcoef(np.log10(e1[:m] + 1e-9), np.log10(e2[:m] + 1e-9))[0, 1])
            lab = "untouched" if v is None else f"{v:9d}"
            print(f"  KEY knob {lab}: corr(T1 env, T2 env) {c:+.2f}   T2 rms {level(x, 2, 1.0, ts):6.1f} dBFS  "
                  f"T2 env range {20 * np.log10(max(e2.max(), 1e-9) / max(e2.min(), 1e-9)):5.1f} dB", flush=True)
    finally:
        rig.close()


def spectrum_peak(x, t, a_s, b_s, hz, band=(9000, 13000), guard=250):
    """Level of the bin at `hz` above the median of `band` (excluding +-guard Hz), averaged spectrum of track t: a narrow tone
    standing out of the noise floor (a whistle) reads tens of dB."""
    c0, c1 = track_cols(t)
    seg = x[int(a_s * FS):int(b_s * FS), c0:c1 + 1].mean(axis=1)
    n = 8192
    win = np.hanning(n)
    acc = np.zeros(n // 2 + 1)
    k = 0
    for i in range(0, len(seg) - n, n // 2):
        acc += np.abs(np.fft.rfft(seg[i:i + n] * win)) ** 2
        k += 1
    f = np.fft.rfftfreq(n, 1 / FS)
    p = 10 * np.log10(np.maximum(acc / max(k, 1), 1e-30))
    near = (np.abs(f - hz) < 60)
    ref = (f > band[0]) & (f < band[1]) & (np.abs(f - hz) > guard)
    return float(p[near].max() - np.median(p[ref]))


def cmd_octa303(a):
    """#1270 on T1+T2 OCTA-303 tracks (project V06_OCT: program 2 has CUT, RES, ENV at 127; program 16 has ACCV 110 and the accent knob up):
    the 11.025 kHz whistle, and clicks, clipping and wrapping with a high ACCV."""
    import ot_matrix as M
    rig = Rig()
    try:
        rig.play(2, 3.0, tail=0.5)                      # the first START after a load is silent
        for prog, label, ev in ((2, "CUT RES ENV 127", []), (16, "ACCV 110, ACC 127", []), (17, "ACCV 64, ACC 127", [])):
            for rep in range(2):
                x, n = rig.play(prog, 7.0, events=ev, tail=0.3)
                ts = n / FS
                seg = x[int(1.0 * FS):int(ts * FS), 0:2]
                ce = M.click_events(seg, FS)
                e, b, nb = (sum(c[i] for c in ce) for i in range(3))
                clip = int((np.abs(seg) >= 0.9999).sum())
                print(f"  program {prog:2d} ({label}) run {rep + 1}: T1 rms {level(x, 1, 1.0, ts):6.1f} peak {peak(x, 1, 1.0, ts):6.1f} dBFS  "
                      f"11.025 kHz over its band {spectrum_peak(x, 1, 1.0, ts, 11025):5.1f} dB  clicks {e:4d} ({b} blocks)  clipped samples {clip}", flush=True)
    finally:
        rig.close()


def cmd_cx_fold(a):
    """#1263: FOLD moved with DEC at HOLD clicked. T1 is a CX OSC track (project V06_RIG, program 17, image V06-RIG): the click
    count on its own channels with FOLD static (0 and 100) and swept 0 to 127 over six seconds."""
    import ot_matrix as M
    rig = Rig()
    try:
        rig.play(a.prog, 3.0, tail=0.5)                 # the first START after a load is silent
        cc = lambda v: (lambda: rig.clock.cc(1, 20, v))
        sweep = [(0.1 + k * 0.045, cc(int(127 * k / 119))) for k in range(120)]
        out = []
        for label, ev in (("FOLD 0 static", [(0.05, cc(0))]), ("FOLD 100 static", [(0.05, cc(100))]), ("FOLD 0..127 swept", sweep),
                          ("FOLD 100 static again", [(0.05, cc(100))])):
            x, n = rig.play(a.prog, 6.0, events=ev, tail=0.3)
            seg = x[int(1.0 * FS):int(n), 0:2]
            ce = M.click_events(seg, FS)
            e, b, nb = (sum(c[i] for c in ce) for i in range(3))
            row = (label, level(x, 1, 1.0, n / FS), M.hf_power_db(seg, FS), e, b, nb)
            out.append(row)
            print(f"{label:24s} T1 rms {row[1]:7.1f} dBFS  hf {row[2]:7.1f} dB  click events {e:4d}  blocks with one {b:3d} of {nb}", flush=True)
        static = max(out[0][3], out[1][3], out[3][3])
        print(f"swept {out[2][3]} events against the static maximum {static}; FOLD moved the audio: hf {out[0][2]:.1f} to {out[1][2]:.1f} dB")
    finally:
        rig.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tracks")
    p.add_argument("prog", type=int)
    p.add_argument("--secs", type=float, default=6.0)
    sub.add_parser("wave-stop")
    sub.add_parser("verb")
    sub.add_parser("vca-key")
    sub.add_parser("octa303")
    p = sub.add_parser("cx-fold")
    p.add_argument("--prog", type=int, default=17)
    a = ap.parse_args()
    {"tracks": cmd_tracks, "wave-stop": cmd_wave_stop, "cx-fold": cmd_cx_fold, "verb": cmd_verb, "vca-key": cmd_vca_key, "octa303": cmd_octa303}[a.cmd](a)


if __name__ == "__main__":
    main()
