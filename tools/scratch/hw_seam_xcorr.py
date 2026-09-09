#!/usr/bin/env python3
"""Drift-immune per-loop period of a recorder-loop CAPTURE. The Mac and the
Octatrack are not sample-locked, so an analog round-trip drifts ~1 sample per
loop -- the same size as the ±1-sample seam route A predicts, which an ordinary
phase/click metric cannot separate (instrument blindness). Cross-correlating
the OT's OWN consecutive playback loops against each other cancels the Mac's
capture-clock drift and yields the true per-loop period: a ±1-sample seam
shows as the period alternating; a clean loop is constant.

    python3 tools/scratch/hw_seam_xcorr.py CAPTURE.wav [ch=3] [guess=20672] [loops=40]

Judged decisive on Sam's unit 9 Sep 2026 (RTOS_FORK 10.27): period = 20,672
for all 40 loops, spread 0 -- no seam on the playback loop."""
import sys, wave, array, statistics
from collections import Counter

path = sys.argv[1]
ch = int(sys.argv[2]) if len(sys.argv) > 2 else 3
guess = int(sys.argv[3]) if len(sys.argv) > 3 else 20672
loops = int(sys.argv[4]) if len(sys.argv) > 4 else 40

w = wave.open(path, 'rb'); n = w.getnchannels(); sw = w.getsampwidth()
a = array.array('i' if sw == 4 else 'h'); a.frombytes(w.readframes(w.getnframes()))
full = 2 ** 31 if sw == 4 else 2 ** 15
x = [a[i * n + ch] / full for i in range(len(a) // n)]

W = 4096
def best_lag(anchor, g, span=40):
    ref = x[anchor:anchor + W]
    best, bl = -9e9, None
    for lag in range(g - span, g + span):
        seg = x[anchor + lag:anchor + lag + W]
        if len(seg) < W:
            continue
        num = sum(p * q for p, q in zip(ref, seg))
        if num > best:
            best, bl = num, lag
    return bl

periods, anchor = [], 5000
for _ in range(loops):
    if anchor + guess + W + 40 > len(x):
        break
    lag = best_lag(anchor, guess)
    if lag is None:
        break
    periods.append(lag); anchor += lag

if not periods:
    print("no loops found -- check the channel and that the capture holds the looped playback"); sys.exit(1)
print(f"per-loop period (samples), {len(periods)} loops:")
print(" ", periods)
print(f"  median {statistics.median(periods)}, min {min(periods)}, max {max(periods)}, "
      f"spread {max(periods) - min(periods)}, histogram {dict(sorted(Counter(periods).items()))}")
print(f"  {'CLEAN: constant period, no seam' if max(periods) == min(periods) else 'SEAM: period varies -- a -1 is a dropped sample at the loop'}")
