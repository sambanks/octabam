"""Float reference — 4 Chamberlin BPs.

out = dry + MIX*(wet-dry); MIX 127 → wet only.
wet = clamp(sum(g_i * band_i) * MAKEUP)

g = (GN/128)*scale_gain(SCALE)*32.
SCAL rises smoothly from zero to the former SCAL 70 gain.
DECY high → low damp + exc→0 at 127. Squared table spacing gives more
knob travel through the high-resonance range.
"""
from __future__ import annotations

import math

FS = 44100.0
BLOCK = 16
N_BANDS = 4
NYQ = FS * 0.5
F_MIN, F_MAX = 40.0, 4000.0
DAMP_MIN, DAMP_MAX = 0.02, 1.6
EXC_FLOOR = 0.0
PREV_QUIET = 0.05
HIT_ON = 0.02
PITCH_KEYS = ("PIT1", "PIT2", "PIT3", "PIT4")
GAIN_KEYS = ("GN1", "GN2", "GN3", "GN4")
WET_MAKEUP = 4.0


def _q23(v: float) -> int:
    return max(-(1 << 23), min((1 << 23) - 1, int(round(v * (1 << 23))))) & 0xFFFFFF


def f_table(n: int = 33) -> list[float]:
    out = []
    for i in range(n):
        fc = F_MIN * (F_MAX / F_MIN) ** (i / (n - 1))
        out.append(2.0 * math.sin(math.pi * min(fc, NYQ * 0.45) / FS))
    return out


def damp_table(n: int = 33) -> list[float]:
    out = []
    for i in range(n):
        out.append(DAMP_MIN * (DAMP_MAX / DAMP_MIN) ** ((i / (n - 1)) ** 2))
    return out


def table_read(tab: list[float], u: float) -> float:
    u = max(0.0, min(1.0, u))
    x = u * (len(tab) - 1)
    i = int(x)
    if i >= len(tab) - 1:
        return tab[-1]
    frac = x - i
    return tab[i] + frac * (tab[i + 1] - tab[i])


def mix(k: int) -> float:
    return 1.0 if k >= 127 else k / 128.0


def exc_gain(decy: int) -> float:
    if decy >= 127:
        return EXC_FLOOR
    u = decy / 127.0
    return 1.0 - (1.0 - EXC_FLOOR) * u


def band_gain(gn: int, scale: int) -> float:
    scale = max(0, min(scale, 127))
    scale_factor = (70 / 127) * (scale / 128.0)
    return (gn / 128.0) * scale_factor * 32.0


class Resonator:
    def __init__(self, PIT1=32, PIT2=48, PIT3=64, PIT4=80,
                 GN1=64, GN2=64, GN3=64, GN4=64, SCAL=8, DECY=127, MIX=127):
        self.k = dict(PIT1=PIT1, PIT2=PIT2, PIT3=PIT3, PIT4=PIT4,
                      GN1=GN1, GN2=GN2, GN3=GN3, GN4=GN4, SCAL=SCAL,
                      DECY=DECY, MIX=MIX)
        self.ft = f_table()
        self.dt = damp_table()
        self.st = [[0.0] * (2 * N_BANDS) for _ in range(2)]
        self.prev = [0.0, 0.0]
        self.fs = None
        self.gs = None
        self.damp = 0.5
        self.m = 1.0
        self.exc = 1.0

    def block(self):
        k = self.k
        self.damp = table_read(self.dt, 1.0 - k["DECY"] / 128.0)
        self.m = mix(k["MIX"])
        self.exc = exc_gain(k["DECY"])
        self.fs = [table_read(self.ft, k[key] / 128.0) for key in PITCH_KEYS]
        sc = k["SCAL"]
        self.gs = [band_gain(k[key], sc) for key in GAIN_KEYS]

    def process(self, L, R):
        outL, outR = [], []
        for n, (xL, xR) in enumerate(zip(L, R)):
            if n % BLOCK == 0:
                self.block()
            outs = []
            for ch, x in ((0, xL), (1, xR)):
                prev = self.prev[ch]
                drive = self.exc * x
                if abs(prev) < PREV_QUIET and abs(x) > HIT_ON:
                    drive = x
                self.prev[ch] = x
                st = self.st[ch]
                acc = 0.0
                damp = self.damp
                for i, f in enumerate(self.fs):
                    li = 2 * i
                    low, band = st[li], st[li + 1]
                    low = low + f * band
                    high = drive - low - damp * band
                    band = band + f * high
                    low = max(-1.0, min(1.0, low))
                    band = max(-1.0, min(1.0, band))
                    st[li], st[li + 1] = low, band
                    acc += self.gs[i] * band
                wet = max(-1.0, min(1.0, acc * WET_MAKEUP))
                y = wet if self.m >= 1.0 else x + self.m * (wet - x)
                outs.append(max(-1.0, min(1.0, y)))
            outL.append(outs[0])
            outR.append(outs[1])
        return outL, outR


def q23_list(xs):
    return [_q23(x) if isinstance(x, float) else x for x in xs]
