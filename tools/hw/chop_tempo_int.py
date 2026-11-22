"""LAZY CHOP TEMPO, whole-number reference (16 Nov 2026).

The same reading as chop_tempo.unit_display (step 0.1 BPM), written only with the operations the ColdFire port
uses: 32-bit integers, tables for cos / prior / loop agreement, unsigned divides. The port must give the same line
as this file on every test case; this file is checked against the float version on the owner's takes.

Units: tempo in centi-BPM (c = 100 x BPM); positions and gaps in samples at 44.1 kHz; fixed point Q14.
"""
import math

SR = 44100
C_LO, C_HI, C_STEP = 6000, 20000, 10
MIN_GAP = 1764                       # 0.04 s
MAX_GAP = 264_600                    # 6 s
D8 = 33_075_000                      # 60 * 44100 * 100 / 8: one beat at c = 1 BPM-cent, gaps >> 3
D8_IDX = D8 // 1024
D16 = D8 // 2                        # the grid scan works on gap >> 4: (gap >> 4) * c * 6 < 2^32 up to c = 309.00
D16_IDX = D16 // 1024
MAX_LEN = 3_000_000                  # a take longer than 68 s is no loop of 16 bars or fewer at 60 BPM and up
Q = 16384
COS = [round(Q * math.cos(2 * math.pi * i / 1024)) for i in range(1024)]
SIMPLE = {1, 2, 3, 4, 6, 8, 12, 16, 24, 32}
PRIOR_C, PRIOR_W = 120.0, 0.5
PRIOR = [round(Q * math.exp(-0.5 * (math.log((C_LO + i * C_STEP) / 100 / PRIOR_C) / PRIOR_W) ** 2)) for i in
         range((C_HI - C_LO) // C_STEP + 1)]
# loop agreement 0.15 + 0.85 exp(-0.5 (err / 0.012)^2), err in Q14 (0..1023); past the table: 0.15
LA = [round(Q * (0.15 + 0.85 * math.exp(-0.5 * ((e / Q) / 0.012) ** 2))) for e in range(1024)]
LA_FLOOR = round(Q * 0.15)
BARS = (1, 2, 4, 8, 16)
# structure units, Q12 (4096 = one beat), weight in percent; the order is the float version's dict order
UNITS = ((2048, 100), (4096, 100), (8192, 100), (16384, 100), (3072, 75), (6144, 75), (12288, 75),
         (683, 60), (1365, 60), (2731, 60), (5461, 60))
D8_U = D8 >> 12                      # gap>>3 * c / D8_U = the gap in beats, Q12


def prior(c):
    i = (c - C_LO + C_STEP // 2) // C_STEP
    return PRIOR[min(max(i, 0), len(PRIOR) - 1)]


def r_at(gaps, c):
    """How well the gaps sit on c's 16th / triplet-16th grid, Q14 (-16384..16384)."""
    best = None
    for sub, num, den in ((4, 1, 1), (6, 9, 10)):
        s = 0
        for x in gaps:
            p = (x >> 4) * c * sub                    # < 2^32 for gaps up to 6 s and c up to 30900
            k = (p + D16 // 2) // D16                 # whole grid steps (rounded)
            idx = ((p % D16) // D16_IDX) & 1023
            s += COS[idx] * (256 if k in SIMPLE else 141)
        r = int(s / (len(gaps) * 256))                # towards zero, as the port's divs.l
        r = int(r * num / den)
        best = r if best is None or r > best else best
    return best


def f6(r):
    f = (r + Q) >> 1
    f2 = (f * f) >> 14
    f3 = (f2 * f) >> 14
    return (f3 * f3) >> 14


def loop_agree(length, c):
    if not length:
        return Q
    q = (length >> 4) * c
    best = Q * 64
    for b in BARS:
        den = 66_150_000 * b                         # 264,600,000 * 4 * b / 16: b bars' (length >> 4) * c
        e = abs(q - den) // (den >> 14) if den >> 14 else Q
        best = min(best, e)
    return LA[best] if best < 1024 else LA_FLOOR


def exact_c(length, b):
    """The tempo at which `length` is exactly b bars of 4/4, centi-BPM (floor)."""
    n = 1_058_400_000
    return (n // length) * b + ((n % length) * b) // length


def gapgrid(gaps, length=0):
    rows = []
    c = C_LO
    while c <= C_HI:
        r = r_at(gaps, c)
        s = (f6(r) * prior(c)) >> 14
        if length:
            s = (s * loop_agree(length, c)) >> 14
        rows.append((s, c))
        c += C_STEP
    rows.sort(reverse=True)
    top_s, top_c = rows[0]
    fam = [x for x in (top_c // 2, top_c, top_c * 2) if C_LO <= x <= C_HI]
    pick = max(fam, key=lambda x: (prior(x) * loop_agree(length, x)) >> 14 if length else prior(x))
    second = None
    for s, x in rows[1:]:
        if not (9704 * pick < 10000 * x < 10305 * pick) and all(
                not (9704 * pick < 10000 * x * k2 // 2 < 10305 * pick) for k2 in (1, 4)):
            second = (s, x)
            break
    conf = Q - (second[0] * Q // top_s if second and top_s else 0)
    bars = None
    if length:
        for b in BARS:
            e = exact_c(length, b)
            if abs(e - pick) * 1000 < 12 * pick:
                bars = b
                break
    return {"c": pick, "conf": conf, "bars": bars, "loop_c": exact_c(length, bars) if bars else None}


def loopish(o, gaps, length):
    gs = sorted(gaps)
    unit = gs[len(gs) // 2]
    small = [x for x in gaps if 4 * x < 3 * unit]
    if len(small) >= 2:
        unit = sorted(small)[len(small) // 2]
    t = (length - o[-1]) * 100 // unit
    frac = t % 100
    return min(frac, 100 - frac) <= 16 and o[0] * 100 // unit < 16


def alt_of(c):
    return c * 2 if c < 12000 and c * 2 <= 20000 else c // 2


def reading(o, gaps, length):
    if length > MAX_LEN:
        length = 0
    g = gapgrid(gaps, 0)
    if length and not loopish(o, gaps, length):
        length = 0
    if length:
        gl = gapgrid(gaps, length)
        if gl["bars"] and gl["conf"] * 10 >= 6 * Q:
            return {"c": gl["loop_c"], "alt": alt_of(gl["c"])}
    c, conf = g["c"], g["conf"]
    gs = sorted(gaps)
    mg = gs[len(gaps) // 2]
    var = sum(((x - mg) >> 6) ** 2 for x in gaps) // len(gaps)       # gap spread, in 64-sample units
    sq = (mg >> 6) ** 2
    if sq and var <= (64 * sq - 1) // 10000 and conf * 2 < Q:     # cv < 0.08 (var*10000 < 64 sq, no overflow)
        c = 264_600_000 // mg
        while c < 7000:
            c *= 2
        while c >= 18000:
            c //= 2
    alt = alt_of(c)
    if length:
        best = None
        for b in range(1, 17):
            e = exact_c(length, b)
            for cand, pen in ((c, 0), (alt, 400)):
                if abs(e - cand) >= cand:
                    continue                                       # far off (and no 32-bit overflow below)
                d = abs(e - cand) * 100_000 // cand
                if d < 1200 and (best is None or d + pen < best[0]):
                    best = (d + pen, b, e, cand)
        if best:
            _, _, e, cand = best
            if cand == alt:
                c, alt = alt, c
            c = e
            alt = alt_of(c)
    return {"c": c, "alt": alt}


def structure(gaps, c, trip=False):
    units = [u for u in UNITS if trip or u[1] > 60]
    kinds, on, w = {}, 0, 0
    for x in gaps:
        u = (x >> 3) * c // D8_U
        k, kw = min(units, key=lambda v: abs(u - v[0]))
        if abs(u - k) * 10 < max(4096, k):           # within 0.1 beat, or 10 % of a longer unit
            kinds[k] = kinds.get(k, 0) + 1
            on += 1
            w += kw
    plain = sum(1 for k, n in kinds.items() if n >= 2 and (dict(UNITS)[k] == 100 or trip))
    return plain, on, w, kinds


def best_oct(gaps, c, trip=False):
    best = None
    for x in (c // 2, c, c * 2):
        s = structure(gaps, x, trip)
        key = (min(s[0], 2), s[2])
        if best is None or key > best[0]:
            best = (key, s, x)
    return best[1] + (best[2],)


def plainer(gaps, r):
    if len(gaps) < 3:
        return r
    c = r["c"]
    wcT = best_oct(gaps, c)[2]
    n = len(gaps)
    best = None
    for num, den in ((2, 3), (3, 4), (4, 3), (3, 2)):
        b0 = c * num // den
        pk = None
        for d in range(-30, 31, 2):
            x = b0 * (1000 + d) // 1000
            rv = r_at(gaps, x)
            if pk is None or (rv, x) > pk:
                pk = (rv, x)
        s2 = best_oct(gaps, pk[1])
        if s2[0] >= 2 and s2[2] >= wcT + 15 * n and (best is None or s2[2] > best[0]):
            best = (s2[2], pk[1])
    if not best:
        return r
    t2 = best[1]
    while t2 < 6000:
        t2 *= 2
    while t2 > 20000:
        t2 //= 2
    t2 = max((x for x in (t2 // 2, t2, t2 * 2) if 6000 <= x <= 20000), key=prior)
    return {"c": t2, "alt": alt_of(t2)}


def also_of(gaps, c):
    n = len(gaps)
    st, on, wc, kd, _ = best_oct(gaps, c)
    dotted = sum(v for k, v in kd.items() if dict(UNITS)[k] == 75)
    also = []
    for num, den in ((4, 3), (3, 4), (3, 2), (2, 3)):
        x = c * num // den
        st2, on2, wc2, _, _ = best_oct(gaps, x, trip=True)
        if st2 >= 2 and (wc2 >= wc - 5 * n or (dotted >= 2 and on2 * 100 >= on * 100 - 5 * n)):
            also.append((wc2, x))
    return max(also)[1] if also else None


def round_half_even(c):
    q, rem = divmod(c, 100)
    return q + (1 if rem > 50 or (rem == 50 and q % 2) else 0)


def closer(a, b, t):
    """Is a nearer to t than b, counted as a ratio (a log distance)?"""
    ra = (max(a, t), min(a, t))
    rb = (max(b, t), min(b, t))
    return ra[0] * rb[1] < rb[0] * ra[1]


def display(slices, length):
    o = sorted(set(slices))
    gaps = [min(b - a, MAX_GAP) for a, b in zip(o, o[1:]) if b - a > MIN_GAP]   # 6 s cap: 32-bit products
    if len(gaps) < 2:
        return None
    r = reading(o, gaps, length)
    r = plainer(gaps, r)
    c = r["c"]
    nb = also_of(gaps, c)
    dot = ""
    if nb:
        br = None
        for v in (nb // 2, nb, nb * 2):
            if br is None or closer(v, br, c):
                br = v
        if abs(br * 100 - 150 * c) < 4 * c or abs(br * 300 - 200 * c) < 9 * c:
            dot = "."
    else:
        br = r["alt"]
    if br > 20000:
        br //= 2
    return f"BPM {round_half_even(c)} ({round_half_even(br)}{dot})", c
