#!/usr/bin/env python3
"""Clicks and dropouts in a capture of the unit's output (tools/hw/rec WAV, PCM 16/24/32-bit).

    python3 tools/hw/clicks.py TAKE.wav [--channels 0,1] [--k 40] [--grid SECONDS]
    python3 tools/hw/clicks.py --selftest

Click: a sample where the second difference |x[n+1] - 2 x[n] + x[n-1]| exceeds K times the
median |second difference| of its own 20 ms block (a sustained sound has a small, steady one)
and an absolute floor of 2e-3 of full scale. Hits within 1 ms are one click.

Dropout: at least 5 ms with |x| under 1e-4 of full scale, where the 20 ms on both sides has RMS
over 1e-2 of full scale. Silence at the start, the end or between notes is not reported.

--grid SECONDS: onsets of a pattern (a trig restarting a sample) are clicks too. The first
click's phase is taken as the grid; clicks within 3 ms of a multiple of SECONDS after it are
listed as `onset` and not counted.

Exit status 1 when any click or dropout is counted. Per channel; the channels are the file's
(--channels picks by index).
"""
import argparse
import sys
import wave

import numpy as np

BLOCK_S = 0.020
FLOOR = 2e-3
DROP_S = 0.005
DROP_LEVEL = 1e-4
SIDE_RMS = 1e-2
MERGE_S = 0.001
GRID_TOL_S = 0.003


def read(path):
    """(samples float64 in [-1,1) shaped (frames, channels), rate)."""
    with wave.open(str(path)) as w:
        n, width, sr, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(frames)
    if width == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 2**15
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        x = np.where(v & 0x800000, v - 0x1000000, v).astype(np.float64) / 2**23
    elif width == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2**31
    else:
        sys.exit(f"{path}: {8 * width}-bit samples not handled")
    return x.reshape(-1, n), sr


def find_clicks(x, sr, k):
    """Sample indices of clicks in one channel."""
    d2 = np.abs(x[2:] - 2 * x[1:-1] + x[:-2])          # d2[i] belongs to sample i+1
    blk = max(int(BLOCK_S * sr), 8)
    hits = []
    for s in range(0, len(d2), blk):
        seg = d2[s:s + blk]
        thr = max(k * float(np.median(seg)), FLOOR)
        hits.extend(s + np.nonzero(seg > thr)[0] + 1)
    merged, gap = [], int(MERGE_S * sr)
    for h in hits:
        if not merged or h - merged[-1] > gap:
            merged.append(int(h))
    return merged


def find_dropouts(x, sr):
    """[(start, length)] in samples."""
    quiet = np.abs(x) < DROP_LEVEL
    need, side = int(DROP_S * sr), int(BLOCK_S * sr)
    out, i, n = [], 0, len(x)
    while i < n:
        if not quiet[i]:
            i += 1
            continue
        j = i
        while j < n and quiet[j]:
            j += 1
        if j - i >= need and i >= side and j + side <= n:
            lo, hi = x[i - side:i], x[j:j + side]
            if np.sqrt(np.mean(lo ** 2)) > SIDE_RMS and np.sqrt(np.mean(hi ** 2)) > SIDE_RMS:
                out.append((i, j - i))
        i = j
    return out


def split_onsets(clicks, sr, grid):
    if not grid or not clicks:
        return clicks, []
    t0 = clicks[0] / sr
    own, onsets = [], []
    for c in clicks:
        ph = ((c / sr - t0) / grid) % 1.0 * grid
        (onsets if min(ph, grid - ph) <= GRID_TOL_S else own).append(c)
    return own, onsets


def report(path, channels, k, grid):
    x, sr = read(path)
    total = 0
    for ch in channels:
        if ch >= x.shape[1]:
            sys.exit(f"{path}: no channel {ch} (has {x.shape[1]})")
        s = x[:, ch]
        clicks, onsets = split_onsets(find_clicks(s, sr, k), sr, grid)
        drops = find_dropouts(s, sr)
        for c in clicks:
            print(f"ch{ch} click   {c / sr:9.3f} s")
        for c in onsets:
            print(f"ch{ch} onset   {c / sr:9.3f} s (on the grid, not counted)")
        for st, ln in drops:
            print(f"ch{ch} dropout {st / sr:9.3f} s  {1000 * ln / sr:.1f} ms")
        print(f"ch{ch}: {len(clicks)} clicks, {len(onsets)} onsets, {len(drops)} dropouts in {len(s) / sr:.2f} s")
        total += len(clicks) + len(drops)
    return total


def selftest():
    sr = 44100
    t = np.arange(sr * 2) / sr
    x = 0.3 * np.sin(2 * np.pi * 220 * t)
    clean = find_clicks(x, sr, 40), find_dropouts(x, sr)
    assert clean == ([], []), clean
    y = x.copy()
    y[30000] += 0.2                                  # one-sample step spike
    y[60000:60000 + int(0.008 * sr)] = 0.0           # 8 ms hole inside the tone
    z = np.zeros_like(x)
    z[: sr // 2] = x[: sr // 2]                      # tone, then silence
    c, d = find_clicks(y, sr, 40), find_dropouts(y, sr)
    assert len(c) >= 1 and abs(c[0] - 30000) <= 2, c
    assert len(d) == 1 and abs(d[0][0] - 60000) <= 2 and d[0][1] >= int(0.008 * sr) - 2, d
    assert find_dropouts(z, sr) == [], "trailing silence is not a dropout"
    own, on = split_onsets([1000, 1000 + 22050, 1000 + 22050 + 5000], sr, 0.5)
    assert on == [1000, 23050] and own == [28050], (own, on)
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav", nargs="?")
    ap.add_argument("--channels", default="0,1")
    ap.add_argument("--k", type=float, default=40.0)
    ap.add_argument("--grid", type=float, default=0.0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.wav:
        ap.error("a WAV file, or --selftest")
    sys.exit(1 if report(a.wav, [int(c) for c in a.channels.split(",")], a.k, a.grid) else 0)


if __name__ == "__main__":
    main()
