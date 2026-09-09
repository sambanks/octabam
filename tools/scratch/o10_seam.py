#!/usr/bin/env python3
"""Residual phase of a recorded-and-replayed tone against a perfect tone:
phase(s) - w*s, unwrapped in small hops, so a dropped input sample is a
permanent +360/period step, a duplicated one -period step, and a playback
rate error a ramp. Prints the residual at each pass boundary and the largest
single hop inside each pass.
  o10_seam.py DUMP TRACK FREQ [pass_len=20672] [win=128]
  o10_seam.py --wav FILE CH FREQ [pass_len] [win]
"""
import sys, math, pathlib
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import blockdump as bd, o10_recloop as rl, o10_phase as ph

def main():
    wav = sys.argv[1] == '--wav'; a = sys.argv[2:] if wav else sys.argv[1:]
    src, trk, f = a[0], int(a[1]), float(a[2])
    L = int(a[3]) if len(a) > 3 else 20672; win = int(a[4]) if len(a) > 4 else 128
    x = ph.read_wav_channel(src, trk) if wav else rl.track_audio(bd.classes(bd.read(src)), trk)
    w = 2 * math.pi * f / 44100; period = 44100 / f
    cos = [math.cos(w * i) for i in range(win)]; sin = [math.sin(w * i) for i in range(win)]
    res = {}; prev = None; acc = 0.0; start = None
    for s in range(0, len(x) - win, win // 2):
        seg = x[s:s + win]; re = sum(v * c for v, c in zip(seg, cos)); im = sum(v * c for v, c in zip(seg, sin))
        mag = 2 * math.hypot(re, im) / win
        if mag < 8388608 * 1e-4: prev = None; continue
        r = (math.degrees(math.atan2(re, im)) - math.degrees(w * s)) % 360   # residual vs a tone starting at sample 0
        if prev is not None:
            acc += (r - prev + 180) % 360 - 180
        elif start is None:
            start = s
        prev = r; res[s] = acc
    if not res: print("no tone"); return
    print(f"{'pass':>4} {'start':>9} {'residual at start':>18} {'at end':>8} {'max hop in pass':>16}  (deg; one sample = {360 / period:.1f} deg; audio from {start})")
    keys = sorted(res)
    for p in range(len(x) // L):
        ks = [k for k in keys if p * L <= k < (p + 1) * L]
        if len(ks) < 4: continue
        hops = [(res[ks[i]] - res[ks[i - 1]], ks[i]) for i in range(1, len(ks))]
        h, at = max(hops, key=lambda t: abs(t[0]))
        print(f"{p + 1:4d} {p * L:9d} {res[ks[0]]:18.1f} {res[ks[-1]]:8.1f} {h:+9.1f} at {at:7d}")

if __name__ == '__main__':
    main()
