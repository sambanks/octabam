#!/usr/bin/env python3
"""O9d: the port's per-track chain against dsp_host, on the same input.

  o9d_compare.py extract DUMP TRACK PREFIX   -> PREFIX_in.wav (the 84-word record's
                                                audio = the chain INPUT) and
                                                PREFIX_rb_L.wav (the core's read-back
                                                slot = the chain OUTPUT), 24-bit mono
  o9d_compare.py fit PORT_rb.wav HOST_T.wav [lag_lo lag_hi]
                                             -> best integer lag, least-squares scale,
                                                residual, and the residual with NO scale

Measured 8 Sep 2026 (COLDFIRE_PORT.md O9d): T1, FX1 = SEND, FX2 = EQUALIZER,
tone on RX0 slot 2. Flat page: residual -125.6 dB at scale -11.906 dB, lag -32.
Boosted page: -95.7 dB with the stem pre-scaled by that k (rig_render --amp k)
and NO fit -- the port applies the track gain BEFORE the FX chain, and driving
the EQ 12 dB hotter saturates it (the "+4.95 vs +6.22 dB" confound).
"""
import sys, wave, math, pathlib
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import blockdump as bd

CORE_OF = {t: (0 if t >= 5 else 1) for t in range(1, 9)}
REC = {1: (0x80001c90, 0x80002710), 0: (0x800021d0, 0x80002c50)}     # 672-hw track records, ping/pong
RB  = {1: (0x80003190, 0x80003590), 0: (0x80003390, 0x80003790)}     # 256-hw read-backs

def words(w):
    out = []
    for i in range(0, len(w), 2):
        v = (w[i] << 8) | (w[i + 1] >> 8)
        out.append(v - (1 << 24) if v >= 1 << 23 else v)
    return out

def save(path, samples):
    with wave.open(path, 'wb') as o:
        o.setnchannels(1); o.setsampwidth(3); o.setframerate(44100)
        o.writeframes(b''.join(int(v).to_bytes(3, 'little', signed=True) for v in samples))
    rms = math.sqrt(sum(v * v for v in samples) / len(samples))
    print(f"{path}: {len(samples)} samples, rms {20 * math.log10(rms / 8388608) if rms else -200:.1f} dBFS")

def extract(dump, track, prefix):
    c = bd.classes(bd.read(dump)); core = CORE_OF[track]; pos = (track - 1) % 4
    rec = sorted(sum((c.get(('>', 0, core, a), []) for a in REC[core]), []))
    inp = []
    for _, w in rec:
        ws = words(w); inp += ws[pos * 84 + 8: pos * 84 + 40: 2]
    save(f"{prefix}_in.wav", inp)
    rb = sorted(sum((c.get(('<', 1, core, a), []) for a in RB[core]), []))
    out = []
    for _, w in rb:
        ws = words(w); out += ws[pos * 32: pos * 32 + 32: 2]
    save(f"{prefix}_rb_L.wav", out)

def rd(path, ch=0):
    w = wave.open(path, 'rb'); n = w.getnframes(); nch = w.getnchannels(); sw = w.getsampwidth(); raw = w.readframes(n)
    return [int.from_bytes(raw[(i * nch + ch) * sw:(i * nch + ch + 1) * sw], 'little', signed=True) / (1 << (8 * sw - 1)) for i in range(n)]

def rms(x): return math.sqrt(sum(v * v for v in x) / len(x))
def db(x): return 20 * math.log10(x) if x > 0 else -200

def fit(port_path, host_path, lo=-64, hi=64):
    port = rd(port_path); host = rd(host_path, 0)
    n = min(len(port), len(host)); seg = range(max(1500, -lo), min(n - 100, n - hi))
    best = None
    for lag in range(lo, hi + 1):
        den = sum(host[i + lag] ** 2 for i in seg)
        if den <= 0: continue
        k = sum(port[i] * host[i + lag] for i in seg) / den
        r = rms([port[i] - k * host[i + lag] for i in seg]); p = rms([port[i] for i in seg])
        if best is None or r < best[2]: best = (lag, k, r, p)
    lag, k, r, p = best
    r1 = rms([port[i] - host[i + lag] for i in seg])
    print(f"lag {lag:+d} samples, scale {db(abs(k)):+.3f} dB (k = {k:.9f} = {k * 8388608:.0f}/2^23), "
          f"residual {db(r / p):.1f} dB below the port's output; with NO scale {db(r1 / p):.1f} dB; "
          f"port {db(p):.2f} host {db(rms([host[i] for i in seg])):.2f} dBFS over samples {seg.start}..{seg.stop}")

if __name__ == '__main__':
    if sys.argv[1] == 'extract': extract(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    elif sys.argv[1] == 'fit': fit(sys.argv[2], sys.argv[3], *map(int, sys.argv[4:6]))
