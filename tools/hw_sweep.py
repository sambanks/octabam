#!/usr/bin/env python3
"""Scripted hardware sweeps: MIDI CC/notes to the Octatrack + EVO4 capture +
per-step metrics, one process.  Pure python (no numpy on this machine).

    python3 tools/hw_sweep.py 'cc 1 41 100' 'cap base 3' 'cc 5 40 127' 'cap t127 3' ...
    python3 tools/hw_sweep.py --file steps.txt          # one step per line

Steps:  cc CH CC VAL | note CH NOTE [VEL] [HOLD] | cap NAME [SECS] | sleep S | say TEXT
cap prints: name, L/R peak dBFS, RMS dBFS, crest, clip runs, spectral tilt
(HF/LF energy ratio, 2-8 kHz vs 100-800 Hz) and a coarse pitch estimate.
Recordings land in out/hw/sweep/NAME.wav.
"""
import sys, time, math, wave, array, subprocess, pathlib, cmath
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import ot_midi
OUT = pathlib.Path("out/hw/sweep"); OUT.mkdir(parents=True, exist_ok=True)
CLIP = 0.985

def record(name, secs):
    path = OUT / f"{name}.wav"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "avfoundation",
                    "-i", ":0", "-t", str(secs), "-ac", "2", "-c:a", "pcm_s16le", "-y", str(path)], check=True)
    return path

def load(path):
    w = wave.open(str(path))
    if w.getsampwidth() != 2:   # emulator renders are 24-bit; go through ffmpeg
        tmp = pathlib.Path(str(path) + '.16.wav')
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
                        "-c:a", "pcm_s16le", str(tmp)], check=True)
        w = wave.open(str(tmp))
    n = w.getnchannels(); sr = w.getframerate()
    a = array.array('h'); a.frombytes(w.readframes(w.getnframes()))
    return sr, [[v / 32768.0 for v in a[c::n]] for c in range(min(n, 2))]

def fft(x):
    n = len(x)
    if n == 1: return x
    e = fft(x[0::2]); o = fft(x[1::2])
    t = [cmath.exp(-2j * math.pi * k / n) * o[k] for k in range(n // 2)]
    return [e[k] + t[k] for k in range(n // 2)] + [e[k] - t[k] for k in range(n // 2)]

def spectrum(ch, sr, nfft=4096, hops=8):
    """Average power spectrum over `hops` windows spread through the capture."""
    acc = [0.0] * (nfft // 2)
    step = max(1, (len(ch) - nfft) // hops)
    for h in range(hops):
        seg = ch[h * step: h * step + nfft]
        if len(seg) < nfft: break
        win = [s * (0.5 - 0.5 * math.cos(2 * math.pi * i / nfft)) for i, s in enumerate(seg)]
        X = fft(win)
        for k in range(nfft // 2): acc[k] += abs(X[k]) ** 2
    return acc, sr / nfft

def band(acc, hz, lo, hi):
    return sum(acc[int(lo / hz): int(hi / hz)]) + 1e-12

def metrics(path):
    sr, chans = load(path); out = []
    for ci, ch in enumerate(chans):
        pk = max(abs(v) for v in ch); rms = math.sqrt(sum(v * v for v in ch) / len(ch))
        runs = cur = 0
        for v in ch:
            if abs(v) >= CLIP: cur += 1
            else:
                if cur >= 2: runs += 1
                cur = 0
        if cur >= 2: runs += 1
        db = lambda x: 20 * math.log10(x + 1e-9)
        d = dict(peak=db(pk), rms=db(rms), crest=db(pk) - db(rms), runs=runs)
        if ci == 0:
            acc, hz = spectrum(ch, sr)
            d['lf'] = 10 * math.log10(band(acc, hz, 100, 800)); d['hf'] = 10 * math.log10(band(acc, hz, 2000, 8000))
            d['tilt'] = d['hf'] - d['lf']
            ref = 10 * math.log10(band(acc, hz, 150, 400))
            d['b1k'] = 10 * math.log10(band(acc, hz, 1000, 2000)) - ref
            d['b4k'] = 10 * math.log10(band(acc, hz, 3000, 6000)) - ref
            # dominant bin 60-2000 Hz
            lo, hi = int(60 / hz), int(2000 / hz)
            k = max(range(lo, hi), key=lambda i: acc[i]); d['fpk'] = k * hz
        out.append(d)
    return out

def fmt(name, m):
    L, R = m[0], (m[1] if len(m) > 1 else m[0])
    return (f"{name:22s} pk {L['peak']:6.1f}/{R['peak']:6.1f}  rms {L['rms']:6.1f}/{R['rms']:6.1f}"
            f"  crest {L['crest']:4.1f}  clip {L['runs']}/{R['runs']}  tilt {L['tilt']:6.1f}  1k {L['b1k']:6.1f}  4k {L['b4k']:6.1f} dB  fpk {L['fpk']:5.0f} Hz")

def run(steps, port="A"):
    out = ot_midi.Out(port); res = {}
    for s in steps:
        p = s.split()
        if not p or p[0].startswith('#'): continue
        if p[0] == 'cc':
            ch, cc, val = map(int, p[1:4]); out.send([0xB0 | (ch - 1), cc, val]); time.sleep(0.03)
        elif p[0] == 'note':
            ch, note = int(p[1]), int(p[2]); vel = int(p[3]) if len(p) > 3 else 100
            hold = float(p[4]) if len(p) > 4 else 0.2
            out.send([0x90 | (ch - 1), note, vel]); time.sleep(hold); out.send([0x80 | (ch - 1), note, 0])
        elif p[0] == 'noteon':
            out.send([0x90 | (int(p[1]) - 1), int(p[2]), int(p[3]) if len(p) > 3 else 100])
        elif p[0] == 'noteoff':
            out.send([0x80 | (int(p[1]) - 1), int(p[2]), 0])
        elif p[0] == 'sleep': time.sleep(float(p[1]))
        elif p[0] == 'say': print('#', ' '.join(p[1:]), flush=True)
        elif p[0] == 'cap':
            name = p[1]; secs = float(p[2]) if len(p) > 2 else 3
            time.sleep(0.4); m = metrics(record(name, secs)); res[name] = m; print(fmt(name, m), flush=True)
        else: sys.exit(f"bad step {s!r}")
    return res

if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == '--file':
        steps = pathlib.Path(a[1]).read_text().splitlines()
    else: steps = a
    run(steps)


# ---- pitch-shift estimator: log-f spectrum cross-correlation -------------
def logspec(path, fmin=60.0, fmax=6000.0, bins_per_semi=4, nfft=8192, hops=24):
    sr, ch = load(path); x = ch[0]
    acc, hz = spectrum(x, sr, nfft, hops)
    n = int(math.log2(fmax / fmin) * 12 * bins_per_semi)
    out = []
    for i in range(n):
        f0 = fmin * 2 ** (i / (12 * bins_per_semi)); f1 = fmin * 2 ** ((i + 1) / (12 * bins_per_semi))
        k0, k1 = int(f0 / hz), max(int(f0 / hz) + 1, int(f1 / hz))
        out.append(10 * math.log10(sum(acc[k0:k1]) / (k1 - k0) + 1e-15))
    m = sum(out) / len(out)
    return [v - m for v in out], bins_per_semi

def shift_semitones(dry, wet, max_semi=26):
    """Semitone shift that best maps dry's log spectrum onto wet's (peak of the
    cross-correlation), plus the second-best candidate."""
    a, bps = logspec(dry); b, _ = logspec(wet)
    best = []
    for s in range(-max_semi * bps, max_semi * bps + 1):
        num = 0.0; da = 0.0; db = 0.0
        for i in range(len(a)):
            j = i + s
            if 0 <= j < len(b):
                num += a[i] * b[j]; da += a[i] ** 2; db += b[j] ** 2
        best.append((num / math.sqrt(da * db + 1e-12), s / bps))
    best.sort(reverse=True)
    top = [best[0]]
    for c in best[1:]:
        if all(abs(c[1] - t[1]) > 1.5 for t in top): top.append(c)
        if len(top) == 3: break
    return top
