"""Float reference for VOID SCRAPE — same law as modules/void/void.asm.

Knobs are integer panel values 0..127 (or count-1). Samples are float in [-1, 1].
Always wet: FDBK recirculates the post-sat sample into DRV (one-sample loop).
BAL crossfades input↔noise (0 = full input). NTYP colours the noise.
"""
from __future__ import annotations

import math

FS = 44100.0
A_NOISE = 0x19660D
C_NOISE = 0x6EF35F


def rate_hz(k: int) -> float:
    k = max(0, min(127, int(k)))
    return 2.0 * (100.0) ** (k / 127.0)  # 2 Hz .. 200 Hz


def rate_inc(k: int) -> float:
    """Phase step in Q23 units where 2.0 = one cycle (LOFI2 / WarpFold)."""
    return 2.0 * rate_hz(k) / FS


def onepole_coef(f: float) -> float:
    return 1.0 - math.exp(-2.0 * math.pi * f / FS)


def hpf_coef(k: int) -> float:
    k = max(0, min(127, int(k)))
    if k == 0:
        return 0.0
    return onepole_coef(20.0 * (100.0) ** (k / 127.0))


def color_coef(k: int) -> float:
    k = max(0, min(127, int(k)))
    if k >= 127:
        return 1.0
    return onepole_coef(200.0 * (80.0) ** (k / 127.0))


def _wrap_signed(p: float) -> float:
    """Keep phase in [-1, 1) — the a1 wrap of a Q23 phase word."""
    while p >= 1.0:
        p -= 2.0
    while p < -1.0:
        p += 2.0
    return p


def osc(shape: int, p: float) -> float:
    """Bipolar oscillator from signed phase in [-1, 1)."""
    x = _wrap_signed(p)
    shape = int(shape) % 3
    if shape == 0:  # SIN — WarpFold parabola 4 p (1-|p|)
        return 4.0 * x * (1.0 - abs(x))
    if shape == 1:  # SQR
        return 1.0 if x >= 0.0 else -1.0
    return x  # SAW


def soft_clip(x: float, drive: int) -> float:
    """DRV 0 = identity. Else g = 1+3d, u=x*g, soft = u - u^3/3 clamped to ±1."""
    d = max(0, min(127, int(drive))) / 128.0
    if d <= 0.0:
        return x
    g = 1.0 + 3.0 * d
    u = x * g
    if u > 1.0:
        u = 1.0
    elif u < -1.0:
        u = -1.0
    y = u - (u * u * u) / 3.0
    return y


def _white_step(state: int) -> tuple[int, float]:
    state = (A_NOISE * (state & 0xFFFFFF) + C_NOISE) & 0xFFFFFF
    s = state if state < 0x800000 else state - 0x1000000
    return state, 0.5 * s / float(1 << 23)


def _colour_noise(st: "VoidState", white: float, ntyp: int) -> float:
    """Update pink/brown from white; return the selected flavour."""
    w = white
    b0 = 0.99765 * st.pink0 + w * 0.0990460
    b1 = 0.96300 * st.pink1 + w * 0.2965164
    b2 = 0.57000 * st.pink2 + w * 1.0526913
    st.pink0, st.pink1, st.pink2 = b0, b1, b2
    pink = 0.25 * (b0 + b1 + b2 + w * 0.1848)

    br = 0.996 * st.brown + 0.08 * w
    if br > 1.0:
        br = 1.0
    elif br < -1.0:
        br = -1.0
    st.brown = br
    brown = 0.5 * br

    ntyp = int(ntyp) % 3
    if ntyp == 1:
        return pink
    if ntyp == 2:
        return brown
    return white


class VoidState:
    def __init__(self):
        self.phase = 0.0
        self.noise = 0x2A5F31
        self.lp_l = 0.0
        self.lp_r = 0.0
        self.hp_l = 0.0
        self.hp_r = 0.0
        self.fb_l = 0.0
        self.fb_r = 0.0
        self.dc_l = 0.0
        self.dc_r = 0.0
        self.pink0 = self.pink1 = self.pink2 = 0.0
        self.brown = 0.0

_DC_K = 0.02  # feedback DC tracker — matches asm #$028f5c


def process_block(
    left: list[float],
    right: list[float],
    *,
    bal: int = 0,
    rate: int = 80,
    shape: int = 0,
    depth: int = 100,
    drive: int = 0,
    fdbk: int = 0,
    color: int = 64,
    hpf: int = 0,
    ntyp: int = 0,
    state: VoidState | None = None,
) -> tuple[list[float], list[float]]:
    st = state or VoidState()
    inc = rate_inc(rate)
    d = max(0, min(127, int(depth))) / 128.0
    fb = max(0, min(127, int(fdbk))) / 128.0
    t = max(0, min(127, int(bal))) / 128.0
    hc = hpf_coef(hpf)
    cc = color_coef(color)
    out_l, out_r = [], []
    for x_l, x_r in zip(left, right):
        st.noise, w = _white_step(st.noise)
        n = _colour_noise(st, w, ntyp)
        s_l = x_l + t * (n - x_l)
        s_r = x_r + t * (n - x_r)

        st.phase = _wrap_signed(st.phase + inc)
        o = osc(shape, st.phase)
        uni = 0.5 * (o + 1.0)
        env = (1.0 - d) + d * uni
        w_l = s_l * env
        w_r = s_r * env

        if hc > 0.0:
            st.hp_l += hc * (w_l - st.hp_l)
            st.hp_r += hc * (w_r - st.hp_r)
            w_l = w_l - st.hp_l
            w_r = w_r - st.hp_r
        if cc < 1.0:
            st.lp_l += cc * (w_l - st.lp_l)
            st.lp_r += cc * (w_r - st.lp_r)
            w_l, w_r = st.lp_l, st.lp_r
        else:
            st.lp_l, st.lp_r = w_l, w_r

        # AC feedback: without stripping DC, high FDBK+DRV rails soft-clip to
        # ±2/3 constant (silence on AC-coupled outs).
        w_l = soft_clip(w_l + fb * (st.fb_l - st.dc_l), drive)
        w_r = soft_clip(w_r + fb * (st.fb_r - st.dc_r), drive)
        st.dc_l += _DC_K * (w_l - st.dc_l)
        st.dc_r += _DC_K * (w_r - st.dc_r)
        st.fb_l, st.fb_r = w_l, w_r
        out_l.append(w_l)
        out_r.append(w_r)
    return out_l, out_r
