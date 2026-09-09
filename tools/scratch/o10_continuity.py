#!/usr/bin/env python3
"""One-sine continuity test for a recorded-and-replayed tone (O10).
  o10_continuity.py [--readback] DUMP TRACK FREQ [pass_len=20672] [fit_lo=25000] [fit_hi=160000]
--readback tests the core's read-back slot (the chain output) instead of the voice's record audio.
Fits A sin + B cos at FREQ on samples fit_lo..fit_hi of the track's audio and
reports, per pass, the rms residual and the largest deviation (% of the
tone's amplitude) against that ONE sine: a seam (dropped/duplicated sample)
is a permanent phase step, a retrigger glitch a local spike; -100 dB is
24-bit rounding, i.e. sample-continuous.
"""
import sys, math, pathlib
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import blockdump as bd, o10_recloop as rl

def main():
    rb = sys.argv[1] == '--readback'; a = sys.argv[2:] if rb else sys.argv[1:]
    dump, track, f = a[0], int(a[1]), float(a[2])
    L = int(a[3]) if len(a) > 3 else 20672
    lo = int(a[4]) if len(a) > 4 else 25000
    hi = int(a[5]) if len(a) > 5 else 160000
    c = bd.classes(bd.read(dump))
    x = rl.readback_audio(c, track) if rb else rl.track_audio(c, track)
    first = next((i for i, v in enumerate(x) if v), None)
    if first is None: print(f"T{track}: silent"); return
    w = 2 * math.pi * f / 44100
    saa = sbb = sab = sa = sb = 0.0
    for n in range(lo, min(hi, len(x))):
        a = math.sin(w * n); b = math.cos(w * n); v = x[n]
        saa += a * a; sbb += b * b; sab += a * b; sa += a * v; sb += b * v
    det = saa * sbb - sab * sab; A = (sa * sbb - sb * sab) / det; B = (saa * sb - sab * sa) / det
    amp = math.hypot(A, B)
    print(f"T{track}: audio from sample {first}; one sine at {f:.0f} Hz fitted on {lo}..{hi}: {20 * math.log10(amp / 8388608):.1f} dBFS")
    for p in range(len(x) // L):
        seg = range(p * L, (p + 1) * L)
        if seg.stop <= first: continue
        r = [abs(x[n] - (A * math.sin(w * n) + B * math.cos(w * n))) / amp for n in seg if n >= first + 200]
        if not r: continue
        i = max(range(len(r)), key=lambda k: r[k]); rm = math.sqrt(sum(v * v for v in r) / len(r))
        flag = "" if r[i] < 0.005 else "   <-- deviates"
        print(f"  pass {p + 1:2d} ({seg.start:7d}..): rms {20 * math.log10(rm) if rm else -200:7.1f} dB, max {100 * r[i]:6.2f}% at {seg.start + i + (first + 200 - seg.start if seg.start < first + 200 else 0)}{flag}")

if __name__ == '__main__':
    main()
