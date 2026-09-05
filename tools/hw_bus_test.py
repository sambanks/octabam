#!/usr/bin/env python3
"""Repeatable hardware A/B test for the bus effects over MIDI, EVO4 capture.

The bus reverb/delay is a SEND effect fed by the other tracks, so it cannot be
isolated by muting (muting the source kills the wet). Its wet is a small part
of a busy mix, so a single A/B is swamped by loop-to-loop drift (~1.5 dB).

This uses SYNCHRONOUS DETECTION: toggle a parameter A/B/A/B on a fixed period
while recording continuously, slice the recording per toggle, and compare
ADJACENT A vs B segments (a paired test). Slow drift cancels across neighbours;
a real per-parameter effect survives. Every run also drives a CONTROL
parameter known to reach the DSP (a page-1 knob), so the harness proves its own
sensitivity: if the control separates and the test does not, the test
parameter is not reaching the DSP.

Usage:
    python3 tools/hw_bus_test.py                 # default: reverb on ch5,
                                                 #   control TIME(40), test MODE(62)
    python3 tools/hw_bus_test.py --ch 5 --test 63 --a 0 --b 127 \
        --control 40 --ca 127 --cb 0 --period 1.5 --cycles 8

Prereqs: EVO4 capturing the rig's master; transport driven by the Rytm
(master); tools/rec (compile: swiftc -O tools/rec.swift -o tools/rec).
"""
import argparse
import array
import math
import os
import pathlib
import subprocess
import sys
import time
import wave

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import ot_midi

OUT = pathlib.Path("out/hw/bustest")
OUT.mkdir(parents=True, exist_ok=True)
REC = str(pathlib.Path(__file__).parent / "rec")


def _one_pole_lp(x, a):
    y = 0.0
    o = [0.0] * len(x)
    for i, s in enumerate(x):
        y += a * (s - y)
        o[i] = y
    return o


def metric(samples, sr):
    """Three per-segment numbers (dB):
      rms      -- overall level (dominated by the dry source)
      tilt     -- HF/LF spectral balance
      gapfloor -- the reverb-tail proxy: the 15th-percentile of short-window
                  energy. A reverb fills the QUIET gaps between transients, so
                  the gap floor tracks tail level/decay while ignoring the loud
                  hits that dominate plain RMS. This is the sensitive one.
    """
    if not samples:
        return -99.0, 0.0, -99.0
    af = 1 - math.exp(-2 * math.pi * 800 / sr)
    lo = _one_pole_lp(samples, af)
    hi = [samples[i] - lo[i] for i in range(len(samples))]

    def rms(z):
        return (sum(v * v for v in z) / len(z)) ** 0.5 if z else 1e-9

    def db(x):
        return -99.0 if x <= 0 else 20 * math.log10(x)

    win = max(1, int(0.04 * sr))          # 40 ms windows
    floors = []
    for i in range(0, len(samples) - win, win):
        floors.append(rms(samples[i:i + win]))
    floors.sort()
    gf = floors[max(0, int(0.15 * len(floors)))] if floors else 1e-9
    return db(rms(samples)), db(rms(hi)) - db(rms(lo)), db(gf)


def load_ch1(path):
    w = wave.open(path)
    n = w.getnchannels()
    sw = w.getsampwidth()
    sr = w.getframerate()
    a = array.array('i' if sw == 4 else 'h')
    a.frombytes(w.readframes(w.getnframes()))
    full = 2 ** 31 if sw == 4 else 2 ** 15
    return [v / full for v in a[0::n]], sr


def toggle_capture(out, ch, cc, va, vb, period, cycles, tag, nudge=None):
    """Record continuously while toggling cc between va/vb every `period` s.
    Returns the list of per-segment (value, rms, tilt), START-aligned.
    `nudge=(cc, val)`: sent right after every toggle. A page-1 CC at an
    unchanged value makes the stock writer call the resolver 0x4009da20 for
    the track, republishing its parameters -- the zero-flash test of whether
    a page-2 store only lacks that publish call."""
    total = period * cycles * 2 + 1.0
    wav = str(OUT / f"{tag}.wav")
    proc = subprocess.Popen([REC, f"{total:.1f}", wav],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True)
    # rec prints "START <epoch> ..." once the tap is live
    t0 = None
    for line in proc.stdout:
        if line.startswith("START"):
            t0 = float(line.split()[1])
            break
    if t0 is None:
        proc.wait()
        raise RuntimeError("recorder never reported START")
    # drive the toggles on a schedule measured from t0
    schedule = []            # (relative_start, value)
    for k in range(cycles * 2):
        val = va if k % 2 == 0 else vb
        rel = k * period
        # send at the right wall-clock moment
        while time.time() - t0 < rel:
            time.sleep(0.002)
        out.send([0xB0 | (ch - 1), cc, val])
        if nudge:
            out.send([0xB0 | (ch - 1), nudge[0], nudge[1]])
        schedule.append((rel, val))
    proc.wait()

    samples, sr = load_ch1(wav)
    guard = 0.6              # drop the transition (MIDI latency + reverb attack)
    segs = []
    for rel, val in schedule:
        s0 = int((rel + guard) * sr)
        s1 = int((rel + period) * sr)
        if s1 <= len(samples) and s1 > s0:
            r, t, gf = metric(samples[s0:s1], sr)
            segs.append((val, r, t, gf))
    return segs


def paired(segs, va, vb):
    """Adjacent A,B pairs -> per-pair metric difference; drift cancels."""
    dr, dt, dg = [], [], []
    for i in range(0, len(segs) - 1, 2):
        a, b = segs[i], segs[i + 1]
        if a[0] == va and b[0] == vb:
            dr.append(a[1] - b[1])
            dt.append(a[2] - b[2])
            dg.append(a[3] - b[3])
    return dr, dt, dg


def stats(xs):
    n = len(xs)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = sum(xs) / n
    if n < 2:
        return mean, 0.0, 0.0
    sd = (sum((x - mean) ** 2 for x in xs) / (n - 1)) ** 0.5
    se = sd / math.sqrt(n)
    t = mean / se if se > 0 else 0.0
    return mean, sd, t


def run_param(out, ch, cc, va, vb, period, cycles, tag, name, nudge=None):
    segs = toggle_capture(out, ch, cc, va, vb, period, cycles, tag, nudge)
    dr, dt, dg = paired(segs, va, vb)
    mr, sdr, tr = stats(dr)
    mt, sdt, tt = stats(dt)
    mg, sdg, tg = stats(dg)
    print(f"  {name:16s} CC{cc} {va}<->{vb}:  gapfloor d={mg:+.2f}dB (t={tg:+.1f})  "
          f"| rms d={mr:+.2f} (t={tr:+.1f})  tilt d={mt:+.2f} (t={tt:+.1f})  n={len(dg)}",
          flush=True)
    # the gap floor is the reverb-tail-sensitive detector; fall back to the others
    return max(abs(tg), abs(tr), abs(tt))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="A")
    ap.add_argument("--ch", type=int, default=5, help="host track's MIDI channel")
    ap.add_argument("--in-cc", type=int, default=45, help="reverb IN knob CC (pinned full)")
    ap.add_argument("--control", type=int, default=40, help="page-1 control CC (known-good)")
    ap.add_argument("--ca", type=int, default=127)
    ap.add_argument("--cb", type=int, default=0)
    ap.add_argument("--test", type=int, default=62, help="page-2 test CC")
    ap.add_argument("--a", type=int, default=0)
    ap.add_argument("--b", type=int, default=2)
    ap.add_argument("--period", type=float, default=1.5)
    ap.add_argument("--cycles", type=int, default=8)
    ap.add_argument("--no-transport", action="store_true")
    ap.add_argument("--solo", dest="solo", action="store_true", default=True,
                    help="solo the host track (CC 50) so its dry+wet is isolated")
    ap.add_argument("--no-solo", dest="solo", action="store_false")
    ap.add_argument("--nudge-cc", type=int, default=0,
                    help="page-1 CC re-sent after every TEST toggle (0 = off); "
                         "makes stock call the resolver 0x4009da20 for the track")
    ap.add_argument("--nudge-val", type=int, default=127)
    args = ap.parse_args()

    if not os.path.exists(REC):
        sys.exit(f"recorder missing: compile it with\n  swiftc -O tools/rec.swift -o {REC}")

    out = ot_midi.Out(args.port)
    if not args.no_transport:
        try:
            ot_midi.Out("Elektron Analog Rytm MKII").send([0xFA])   # START
        except SystemExit:
            print("  (no Rytm port; assuming transport already running)")
    if args.solo:
        out.send([0xB0 | (args.ch - 1), 50, 127])       # solo the host track
    out.send([0xB0 | (args.ch - 1), args.in_cc, 127])   # reverb IN full
    time.sleep(1.0)

    print(f"synchronous A/B on ch{args.ch}"
          f"{' (host SOLOED)' if args.solo else ''}, "
          f"period {args.period}s x{args.cycles} cycles:")
    print("  (adjacent-paired; |t|>~3 = a real, repeatable effect)")
    ctrl_t = run_param(out, args.ch, args.control, args.ca, args.cb,
                       args.period, args.cycles, "control", "CONTROL page-1")
    nudge = (args.nudge_cc, args.nudge_val) if args.nudge_cc else None
    if nudge:
        print(f"  (TEST toggles followed by a page-1 nudge CC{nudge[0]}={nudge[1]} "
              "-> stock republishes the track via 0x4009da20)")
    test_t = run_param(out, args.ch, args.test, args.a, args.b,
                       args.period, args.cycles, "test", "TEST page-2", nudge)

    print("\nverdict:")
    if ctrl_t < 3:
        print(f"  INCONCLUSIVE: the control barely moved (|t|={ctrl_t:.1f}); the reverb "
              "is too quiet in this mix to measure. Raise the reverb send/wet and retry.")
    elif test_t >= 3:
        print(f"  PAGE-2 REACHES THE DSP: test |t|={test_t:.1f} alongside control |t|={ctrl_t:.1f}.")
    else:
        print(f"  PAGE-2 IS NOT REACHING THE DSP: control moved (|t|={ctrl_t:.1f}) but "
              f"test did not (|t|={test_t:.1f}) under the same isolation.")

    if args.solo:
        out.send([0xB0 | (args.ch - 1), 50, 0])         # un-solo the host track


if __name__ == "__main__":
    main()
