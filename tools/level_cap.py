#!/usr/bin/env python3
"""Record N seconds from the EVO4 (avfoundation dev 0, ch1/2) and report
peak / RMS / crest / clipped-sample runs per channel.  Pure python: no numpy.

    python3 tools/level_cap.py NAME [-t SEC]      -> out/hw/level/NAME.wav
    python3 tools/level_cap.py --analyse FILE.wav
"""
import argparse, array, math, subprocess, sys, wave, pathlib
OUT = pathlib.Path("out/hw/level"); OUT.mkdir(parents=True, exist_ok=True)
CLIP = 0.985   # a sample at/above this is treated as pinned

def analyse(path):
    w = wave.open(str(path)); n = w.getnchannels(); sw = w.getsampwidth(); sr = w.getframerate()
    raw = w.readframes(w.getnframes())
    if sw == 2:
        a = array.array('h'); a.frombytes(raw); full = 32768.0
    else:
        a = array.array('i'); a.frombytes(raw); full = 2**31
    res = []
    for c in range(min(n, 2)):
        ch = [v / full for v in a[c::n]]
        if not ch: continue
        pk = max(abs(v) for v in ch)
        rms = math.sqrt(sum(v * v for v in ch) / len(ch))
        # clipped runs: consecutive samples pinned
        runs = 0; longest = 0; cur = 0; pinned = 0
        for v in ch:
            if abs(v) >= CLIP:
                cur += 1; pinned += 1
            else:
                if cur >= 2: runs += 1
                longest = max(longest, cur); cur = 0
        if cur >= 2: runs += 1
        longest = max(longest, cur)
        # top-1% sample level (robust peak)
        s = sorted(abs(v) for v in ch); p99 = s[int(0.999 * (len(s) - 1))]
        db = lambda x: 20 * math.log10(x + 1e-9)
        res.append(dict(ch=c + 1, peak=db(pk), p999=db(p99), rms=db(rms),
                        crest=db(pk) - db(rms), runs=runs, longest=longest, pinned=pinned))
        print(f"ch{c+1}: peak {db(pk):6.1f}  top0.1% {db(p99):6.1f}  rms {db(rms):6.1f} dBFS"
              f"  crest {db(pk)-db(rms):5.1f} dB  clip-runs {runs} (longest {longest} smp, {pinned} pinned)  [{sr} Hz]")
    return res

def record(name, secs):
    path = OUT / f"{name}.wav"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "avfoundation",
                    "-i", ":0", "-t", str(secs), "-ac", "2", "-c:a", "pcm_s32le", "-y", str(path)], check=True)
    print(f"-> {path}")
    return path

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("name", nargs="?")
    ap.add_argument("-t", type=float, default=8); ap.add_argument("--analyse")
    a = ap.parse_args()
    if a.analyse: analyse(a.analyse)
    elif a.name: analyse(record(a.name, a.t))
    else: ap.print_help()
