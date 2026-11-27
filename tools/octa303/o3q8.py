"""v7.6: the TB-303's square shaper, Q8 (2SA733P), from the Roland service notes' main board (= the x0xb0x netlist):

    saw (Q28's source, vlo..vhi) --R35 100k------------------+-- base of Q8 (PNP)
                                 --C10 0.01 uF--R34 10k------+
    emitter: R45 22k to +12 V, C11 1 uF to ground;   collector: R36 10k to +5.333 V  = the square

Solved as a circuit (the base-emitter exponential, hFE, saturation; Newton on the base node, explicit steps at
32x the sample rate), its steady-state cycle at each pitch.  The engine plays it as a smooth part (a table, 128
points a cycle) plus the one hard edge, at the saw's reset, made with the saw's own polyBLEP:
    square = C(phase) + K * saw(phase),  K = -J/2 (J = the jump at the reset, in saw units: the saw spans -1..+1)
vlo, vhi (the saw's swing, volts) and beta (hFE; the 2SA733's P rank is 200..400) are fitted (claude/OCTA303_v76).
"""
import math
VT, IS, VCESAT = 0.02585, 1e-14, 0.1
NPT = 128                                         # table points a cycle

def cycle(f0, vlo, vhi, beta, fs=44100.0, os=32, settle=0.25, n=1024):
    """the collector voltage on n phase points of one steady-state cycle, phase 0 = just after the saw's reset"""
    dt = 1.0 / (fs * os); ve, q10, x, ph = 9.0, 0.0, 0.6, 0.0      # x = the base-emitter voltage Veb
    nset = int(settle * fs * os); last = []
    i = 0; done = False; rec = False
    g = 1 / 100e3 + 1 / 10e3
    while not done:
        ph += f0 * dt
        if ph >= 1.0:
            ph -= 1.0
            if rec: done = True
            elif i >= nset: rec = True
        vs = vlo + (vhi - vlo) * ph
        x0 = ve - vs - q10 * (1 / 10e3) / g        # Veb with no base current (the junction off)
        if x0 < 0.45: x = x0                      # off: exact (ib < 1e-21 A)
        else:                                     # on: Newton on Veb from the clamp's side
            x = min(x0, 0.75)                     # (vb - vs)/R35 + (vb - vs - q10)/R34 = ib, vb = ve - x
            for _ in range(30):
                e = math.exp(min(x / VT, 80.0)) * IS / (beta + 1.0)
                f = (ve - x - vs) / 100e3 + (ve - x - vs - q10) / 10e3 - e
                st = f / (g + e / VT); x += max(-0.05, min(st, 0.05))
                if abs(st) < 1e-10: break
        vb = ve - x
        ib = math.exp(min((ve - vb) / VT, 80.0)) * IS / (beta + 1.0)
        ic = min(beta * ib, max(0.0, (ve - VCESAT - 5.333) / 10e3))
        q10 += dt * ((vb - vs - q10) / 10e3) / 0.01e-6
        ve += dt * ((12.0 - ve) / 22e3 - ic - ib) / 1e-6
        if rec and not done: last.append((ph, 5.333 + ic * 10e3))
        i += 1
    P = [p for p, _ in last]; Y = [y for _, y in last]
    out = []; j = 0
    for k in range(n):                            # linear interpolation onto the phase grid
        p = k / n
        while j + 1 < len(P) and P[j + 1] < p: j += 1
        if p <= P[0]: out.append(Y[0]); continue
        if j + 1 >= len(P): out.append(Y[-1]); continue
        a = (p - P[j]) / (P[j + 1] - P[j]); out.append(Y[j] + a * (Y[j + 1] - Y[j]))
    return out

def decompose(y, vlo, vhi, kmax=None):
    """y: one cycle in volts (phase 0 just after the reset) -> (C on NPT points in saw units, K): y = C + K * saw"""
    n = len(y); sw = vhi - vlo; m = sum(y) / n
    u = [(v - m) * 2.0 / sw for v in y]           # saw units: the saw spans 2
    u[0] = 2 * u[1] - u[2]                         # the edge lands within the first point (the turn-on takes ~2 us): at 0
    j0 = u[0]; j1 = 2 * u[-1] - u[-2]              # each side at the edge
    J = j0 - j1; K = -J / 2.0
    c = [u[k] - K * (2.0 * k / n - 1.0) for k in range(n)]
    cm = sum(c) / n; c = [v - cm for v in c]
    if kmax is not None:                           # band-limited: the harmonics the pitch can carry (no aliasing)
        import numpy as np
        X = np.fft.rfft(c); X[kmax + 1:] = 0; c = list(np.fft.irfft(X, n))
    step = n // NPT
    C = [sum(c[k * step + d] for d in range(step)) / step for k in range(NPT)]   # box-averaged onto NPT points
    sh = 0.5 * (step - 1) / n                      # the box average's centre lags by half a box: re-sample
    C = [_lerp(C, (k / NPT - sh) * NPT) for k in range(NPT)]
    return C, K

def _lerp(C, x):
    n = len(C); x %= n; i = int(x); a = x - i; return C[i] + a * (C[(i + 1) % n] - C[i])

def tables(f_low, vlo, vhi, beta, lo=28, hi=100):
    """per semitone index 0..127 (f = f_low 2^(i/12)): Q15 tables (NPT points) and Q15 K; outside lo..hi the edge's"""
    SQC, SQK = [], []
    cache = {}
    for i in range(128):
        ii = min(max(i, lo), hi)
        if ii not in cache:
            y = cycle(f_low * 2 ** (ii / 12.0), vlo, vhi, beta)
            C, K = decompose(y, vlo, vhi, kmax=min(NPT // 2 - 1, int(22050.0 / (f_low * 2 ** ((ii + 1) / 12.0)))))   # the row's top
            cache[ii] = ([int(round(max(-0.999, min(0.999, v)) * 32767)) for v in C], int(round(K * 32768)))
        SQC.append(cache[ii][0]); SQK.append(cache[ii][1])
    return SQC, SQK
