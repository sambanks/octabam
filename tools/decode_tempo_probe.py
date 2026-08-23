#!/usr/bin/env python3
"""Decode TEMPO PROBE captures and diff the staging block across tempos.

    python3 tools/decode_tempo_probe.py bpm60.wav bpm180.wav [bpm120.wav ...]

The probe (dsp/tempoprobe.asm, TPROBE=1) streams X:0x30000-0x30047 -- stock's
72-word per-frame parameter staging -- on the LEFT channel, one word per
sample, round-robin, with the word INDEX as a 0..71 staircase on the RIGHT.
This script aligns on the staircase, averages each word over the whole
capture, and prints the words whose value CHANGES between captures, with the
ratio -- a word whose ratio matches the tempo ratio (or its inverse) is a
rate (or period), and tempo sync is on.

Robust to capture gain (the index staircase self-calibrates the scale) and to
level inaccuracy: the diff needs relative change, not exact bits. A capture
that decodes to all-zero words is what the EMULATOR produces (dsp_host never
runs stock's frame setup); on hardware it means the probe is not running.
"""
import math
import sys
import wave


def load(path):
    with wave.open(path, "rb") as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if ch != 2:
        sys.exit(f"{path}: need the stereo pair (L=data, R=index), got {ch}ch")
    frames = []
    if sw == 3:
        step = 6
        for i in range(n):
            def s24(off):
                v = raw[off] | (raw[off + 1] << 8) | (raw[off + 2] << 16)
                return v - (1 << 24) if v & 0x800000 else v
            frames.append((s24(i * step), s24(i * step + 3)))
    elif sw == 2:
        import array
        a = array.array("h")
        a.frombytes(raw)
        # scale 16-bit up so the index staircase lands near idx<<16 anyway
        frames = [(a[i * 2] << 8, a[i * 2 + 1] << 8) for i in range(n)]
    else:
        sys.exit(f"{path}: unsupported sample width {sw * 8} bit")
    return frames


def decode(path):
    frames = load(path)
    # The staircase is idx<<16 at unity gain. Estimate gain from its peak
    # (idx 71 -> 71<<16), then bucket samples by nearest index.
    peak = max(r for _, r in frames)
    if peak <= 0:
        sys.exit(f"{path}: right channel carries no staircase -- wrong "
                 f"routing, or the probe is not running")
    scale = peak / (71 << 16)
    acc = [[0.0, 0] for _ in range(72)]
    for lft, rgt in frames:
        idx = round(rgt / scale / (1 << 16))
        if 0 <= idx <= 71:
            acc[idx][0] += lft / scale
            acc[idx][1] += 1
    words = []
    for i, (tot, cnt) in enumerate(acc):
        if cnt == 0:
            sys.exit(f"{path}: index {i} never seen -- capture too short "
                     f"or staircase misdecoded")
        words.append(tot / cnt)
    return words


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    paths = sys.argv[1:]
    sets = [decode(p) for p in paths]
    if all(all(abs(v) < 256 for v in ws) for ws in sets):
        print("every word ~0 in every capture: this is the EMULATOR result "
              "(no stock frame setup) -- run the captures on hardware")
        return
    print(f"{'word':>4}  " + "  ".join(f"{p[-16:]:>16}" for p in paths)
          + "   ratio(1/0)")
    changed = 0
    for i in range(72):
        vals = [ws[i] for ws in sets]
        span = max(vals) - min(vals)
        if span < 512:            # ~capture noise floor at 24-bit scale
            continue
        changed += 1
        r = (vals[1] / vals[0]) if abs(vals[0]) > 256 else math.inf
        print(f"{i:4d}  " + "  ".join(f"{v:16.0f}" for v in vals)
              + f"   {r:8.3f}")
    if not changed:
        print("no word changed between captures: the staging block does not "
              "carry tempo (negative result -- the ColdFire-side path is "
              "what remains)")


if __name__ == "__main__":
    main()
