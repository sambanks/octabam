#!/usr/bin/env python3
"""Tempo from LAZY CHOP's slice markers: prototypes, compared side by side (8thmyth, 16 Nov 2026).

    python3 tools/hw/chop_tempo.py selftest            # the methods on synthetic chop patterns
    python3 tools/hw/chop_tempo.py est SR LEN o1 o2 ...  # one estimate: sample rate, loop length (0 = unknown), onsets

The input is what the unit holds: the slice starts in samples (sample-exact; how they relate to the beat is what
is unknown) and, when known, the loop's length (the trim, or the take). Methods:

  median   the median gap between chops is one beat, folded into 70-180 BPM. Breaks on off-beat and uneven chops.
  loop     the loop is 1, 2, 4, 8 or 16 bars of 4/4; the BPM in 70-180 nearest 110 (needs LEN).
  grid     every BPM from 60 to 200 (step 0.05) is scored by how well ALL the chops sit on its 16th or triplet-16th
           grid, wherever its phase falls (circular mean of 2*pi*onset/grid), so off-beat and syncopated chops fit
           the right tempo too. A tempo twice as fast fits as well (every 16th is an 8th of it): a log-normal prior
           around 110 BPM and, with LEN, the loop-length agreement decide between them.
  grid+loop  grid, multiplied by how close the loop length comes to a whole number of bars at that BPM.

Every estimate comes with a confidence (0..1) and the runner-up, so a doubtful reading can say so.
"""
import cmath
import math
import random
import sys

BARS = (1, 2, 4, 8, 16)
SIMPLE = {1, 2, 3, 4, 6, 8, 12, 16, 24, 32}   # gaps (in grid steps) a chop plausibly spans


def fold(bpm, lo=70.0, hi=180.0):
    while bpm < lo:
        bpm *= 2
    while bpm >= hi:
        bpm /= 2
    return bpm


def median_ioi(sr, onsets):
    o = sorted(onsets)
    if len(o) < 2:
        return None
    gaps = sorted(b - a for a, b in zip(o, o[1:]) if b > a)
    g = gaps[len(gaps) // 2]
    return fold(60.0 * sr / g)


def loop_bpms(sr, length):
    """Every BPM in 60..200 at which `length` samples is a whole 1-16 bars of 4/4."""
    out = []
    for bars in BARS:
        bpm = 60.0 * sr * 4 * bars / length
        if 60 <= bpm <= 200:
            out.append(bpm)
    return out


def loop_only(sr, length):
    c = [b for b in loop_bpms(sr, length) if 70 <= b < 180] if length else []
    return min(c, key=lambda b: abs(math.log(b / 110.0))) if c else None


PRIOR_W = 0.5        # how strongly a reading leans toward 110 BPM (0.35 pulled 134 to 100.6)
LOOP_CONF = 0.6


PRIOR_C = 120.0      # half/double: 8thmyth's takes put the first number in the right octave 14/24 at 120, 10/24 at 110
LOOP_TOL = 0.012     # a whole number of bars within 1.2 % confirms and refines the spacing (was 2 %)


def prior(bpm):
    return math.exp(-0.5 * (math.log(bpm / PRIOR_C) / PRIOR_W) ** 2)


def fit(sr, onsets, bpm, subs=(4, 6)):
    """(how well the chops sit on this BPM's 16th or triplet grid, 0..1; the subdivision)."""
    beat = 60.0 * sr / bpm
    best = (0.0, 4)
    for sub in subs:
        g = beat / sub
        z = sum(cmath.exp(2j * math.pi * o / g) for o in onsets) / len(onsets)
        r = abs(z) * (1.0 if sub == 4 else 0.92)          # straight 16ths win a tie
        best = max(best, (r, sub))
    return best


def loop_agree(sr, length, bpm, tol=0.006):
    if not length:
        return 1.0
    beat = 60.0 * sr / bpm
    best = 0.0
    for bars in BARS:
        err = abs(length / (4 * bars * beat) - 1.0)
        best = max(best, math.exp(-0.5 * (err / tol) ** 2))
    return 0.15 + 0.85 * best


def grid(sr, onsets, length=0, use_loop=False, lo=60.0, hi=200.0, step=0.05):
    if len(onsets) < 3:
        return None
    scores = []
    n = int((hi - lo) / step) + 1
    for i in range(n):
        bpm = lo + i * step
        r, sub = fit(sr, onsets, bpm)
        s = (r ** 4) * prior(bpm) * (loop_agree(sr, length, bpm) if use_loop else 1.0)
        scores.append((s, bpm, sub, r))
    scores.sort(reverse=True)
    top = scores[0]
    # the runner-up: the best score more than 3% away in tempo (not the same peak's shoulder)
    second = next((x for x in scores[1:] if abs(math.log(x[1] / top[1])) > 0.03), None)
    conf = 1.0 - (second[0] / top[0] if second and top[0] else 0.0)
    return {"bpm": round(top[1], 2), "sub": top[2], "fit": round(top[3], 3), "conf": round(conf, 2),
            "runner_up": round(second[1], 2) if second else None}


def gapunit(sr, onsets, length=0, tol=0.13):
    """The step the chops are built on, from their spacing alone (8thmyth's random chunks have no whole-bar
    length to lean on). Every gap is a whole number of steps (1, 2, 3, 4, 6, 8); the step is the LONGEST one that
    leaves the gaps within `tol` (rms, in steps; a hand is about +-10%), refined by least squares. The step is then
    read as a 16th, an 8th or a quarter (or a triplet 8th), whichever lands nearest 110 BPM in 70-180, with the
    half/double reading as the alternative. A length that comes out a whole 1-16 bars at that tempo (within 0.6%)
    confirms it and gives the exact figure; a chunk of any other length is read from the spacing only."""
    o = sorted(onsets)
    gaps = [b - a for a, b in zip(o, o[1:]) if b - a > 0.04 * sr]
    if len(gaps) < 2:
        return None
    best = None
    u = 1.2 * sr
    while u >= 0.06 * sr:
        ks = [max(1, round(g / u)) for g in gaps]
        if max(ks) <= 8:
            err = math.sqrt(sum(((g - k * u) / u) ** 2 for g, k in zip(gaps, ks)) / len(gaps))
            if err <= tol:
                best = (u, err, ks)
                break
        u *= 0.995
    if best is None:
        return None
    u, err, ks = best
    u = sum(g * k for g, k in zip(gaps, ks)) / sum(k * k for k in ks)     # least squares
    err = math.sqrt(sum(((g - k * u) / u) ** 2 for g, k in zip(gaps, ks)) / len(gaps))
    cands = []
    for per_beat, kind in ((4, "16th"), (2, "8th"), (1, "quarter"), (3, "triplet 8th")):
        bpm = 60.0 * sr / (u * per_beat)
        if 70 <= bpm < 180:
            cands.append((abs(math.log(bpm / 110.0)) + (0.15 if kind == "triplet 8th" else 0.0), bpm, kind))
    if not cands:
        return None
    cands.sort()
    _, bpm, kind = cands[0]
    alt = bpm * 2 if bpm < PRIOR_C and bpm * 2 <= 200 else bpm / 2
    bars = None
    if length:
        for b in BARS:
            for t in (bpm, alt):
                exact = 60.0 * sr * 4 * b / length
                if abs(exact / t - 1) < 0.006:
                    bars, bpm_exact = b, exact
                    if t == alt:
                        bpm, alt = alt, bpm
                    bpm = exact
                    break
            if bars:
                break
    conf = max(0.0, 1.0 - err / tol) * min(1.0, len(gaps) / 8.0)
    return {"bpm": round(bpm, 2), "or": round(alt, 2), "step": kind, "conf": round(conf, 2),
            "loop_bars": bars, "spread": round(err, 3)}


def gapgrid(sr, onsets, length=0, lo=60.0, hi=200.0, step=0.05):
    """The grid method on the GAPS between neighbouring chops instead of their absolute positions: each gap is
    scored against a BPM's 16th (or triplet-16th) grid on its own, so a hand that drifts over a long take
    (8thmyth's 25 s takes, +-10% per gap) does not smear the fit, and a chunk cut anywhere needs no phase. Half
    and double tempo fit equally: the prior around 110 BPM picks one and the other is given as the alternative;
    a length that is a whole 1-16 bars at the tempo (within 1.2%, a hand's error) confirms it."""
    o = sorted(onsets)
    gaps = [b - a for a, b in zip(o, o[1:]) if b - a > 0.04 * sr]
    if len(gaps) < 2:
        return None
    rows = []
    n = int((hi - lo) / step) + 1
    for i in range(n):
        bpm = lo + i * step
        beat = 60.0 * sr / bpm
        best = (-1.0, 4)
        for sub, w in ((4, 1.0), (6, 0.9)):
            g = beat / sub
            # a gap of 5, 7, 9... grid steps is an unlikely chop: it is what a wrong tempo makes of even spacing
            r = sum(math.cos(2 * math.pi * x / g) * (1.0 if round(x / g) in SIMPLE else 0.55) for x in gaps) / len(gaps)
            best = max(best, (r * w, sub))
        r, sub = best
        fitv = ((r + 1) / 2) ** 6
        s = fitv * prior(bpm) * (loop_agree(sr, length, bpm, tol=0.012) if length else 1.0)
        rows.append((s, bpm, sub, r))
    rows.sort(reverse=True)
    top = rows[0]
    # Half and double tempo fit the same chops, but a finer grid punishes a hand's jitter more, so the raw fit
    # leans slow (8thmyth's 120 BPM chunk read 60, 16 Nov 2026). Within the octave family the fit is not
    # evidence: the prior and the loop decide between top/2, top and top*2.
    fam = [b for b in (top[1] / 2, top[1], top[1] * 2) if lo <= b <= hi]
    pick = max(fam, key=lambda b: prior(b) * (loop_agree(sr, length, b, tol=0.012) if length else 1.0))
    if pick != top[1]:
        top = (top[0], pick, top[2], top[3])
    second = next((x for x in rows[1:] if abs(math.log(x[1] / top[1])) > 0.03
                   and min(abs(math.log(x[1] / top[1] * k)) for k in (0.5, 1, 2)) > 0.03), None)
    conf = 1.0 - (second[0] / rows[0][0] if second and rows[0][0] else 0.0)
    alt = top[1] * 2 if top[1] < 110 else top[1] / 2
    bars = None
    if length:
        for b in BARS:
            exact = 60.0 * sr * 4 * b / length
            if abs(exact / top[1] - 1) < 0.012:
                bars = b
                break
    return {"bpm": round(top[1], 2), "or": round(alt, 2), "grid": "triplet" if top[2] == 6 else "16th",
            "fit": round(top[3], 3), "conf": round(conf, 2), "runner_up": round(second[1], 2) if second else None,
            "loop_bars": bars, "loop_bpm": round(60.0 * sr * 4 * bars / length, 2) if bars else None}


def estimate(sr, onsets, length=0):
    """Every method -> {name: bpm or dict}."""
    return {"reading": reading(sr, onsets, length), "gapgrid": gapgrid(sr, onsets, length), "gapgrid-noloop": gapgrid(sr, onsets, 0), "gapunit": gapunit(sr, onsets, length), "median": median_ioi(sr, onsets), "loop": loop_only(sr, length),
            "grid": grid(sr, onsets), "grid+loop": grid(sr, onsets, length, use_loop=True) if length else None}


LOOPISH = True
TAIL_TOL = 0.16


def loopish(sr, o, gaps, length):
    """Does the take look like a loop cut on the chops' grid? The end of the take, counted from the last chop in
    units of the chops' smallest common gap, lands near a whole number (8thmyth's loops: within 0.15; his
    random chunks and free-pace takes: 0.19-0.38)."""
    gs = sorted(gaps)
    unit = gs[len(gs) // 2]
    small = [x for x in gaps if x < 0.75 * unit]
    if len(small) >= 2:
        unit = sorted(small)[len(small) // 2]
    tail = (length - o[-1]) / unit
    return min(tail - int(tail), int(tail) + 1 - tail) <= TAIL_TOL and o[0] / unit < TAIL_TOL


def reading(sr, onsets, length=0):
    """The reading LAZY CHOP would show (16 Nov 2026, tuned on 8thmyth's MKI takes):
    1. gapgrid on the spacing alone (the length never decides the tempo);
    2. very even chops (gaps within 8%) with a weak gapgrid: one chop = one beat;
    3. the length confirms: when a whole 1-16 bars at a tempo lies within 2% of the reading or its
       half/double, that tempo is taken (exact) and the confidence raised; otherwise the length is ignored."""
    o = sorted(onsets)
    gaps = [b - a for a, b in zip(o, o[1:]) if b - a > 0.04 * sr]
    if len(gaps) < 2:
        return None
    g = gapgrid(sr, o, 0)
    if g is None:
        return None
    if length and LOOPISH and not loopish(sr, o, gaps, length):
        length = 0               # a random chunk: its length is not bars, and a coincidence would mislead
    if length:
        gl = gapgrid(sr, o, length)       # spacing and loop scored together: a clear joint winner is taken
        if gl and gl["loop_bars"] and gl["conf"] >= LOOP_CONF:
            alt = gl["bpm"] * 2 if gl["bpm"] < PRIOR_C and gl["bpm"] * 2 <= 200 else gl["bpm"] / 2
            return {"bpm": round(gl["loop_bpm"], 2), "or": round(alt, 2), "conf": gl["conf"],
                    "how": f"spacing + loop scored together, loop = {gl['loop_bars']} bars", "bars": gl["loop_bars"]}
    bpm, conf, how = g["bpm"], g["conf"], "chop spacing"
    mg = sorted(gaps)[len(gaps) // 2]
    cv = (sum((x - mg) ** 2 for x in gaps) / len(gaps)) ** 0.5 / mg
    if cv < 0.08 and conf < 0.5:
        bpm, conf, how = fold(60.0 * sr / mg), 0.5, "even chops = beats"
    alt = bpm * 2 if bpm < PRIOR_C and bpm * 2 <= 200 else bpm / 2
    bars = None
    if length:
        best = None
        for b in range(1, 17):
            exact = 60.0 * sr * 4 * b / length
            for cand, pen in ((bpm, 0.0), (alt, 0.004)):        # the reading's own octave first
                d = abs(exact / cand - 1)
                if d < LOOP_TOL and (best is None or d + pen < best[0]):
                    best = (d + pen, b, exact, cand)
        if best:
            _, bars, exact, cand = best
            if cand == alt:
                bpm, alt = alt, bpm
            bpm = exact
            alt = bpm * 2 if bpm < PRIOR_C and bpm * 2 <= 200 else bpm / 2
            conf = min(1.0, conf + (0.15 if conf >= 0.3 else 0.0))   # a coincidence must not look sure
            how += f" + loop = {bars} bars"
    return {"bpm": round(bpm, 2), "or": round(alt, 2), "conf": round(conf, 2), "how": how, "bars": bars}


# ---- the audio cross-check ----------------------------------------------------------------------------------
# The chops say where 8thmyth's hand fell; the audio says where the music's beats are. On his MKI, 16 Nov 2026
# (10 takes with a known tempo, main out recorded by ot_monitor while the take played under LAZY CHOP):
# every reading the two agreed on with clear audio was right, rounded (120, 75, 93, 133, 164, 164); the
# misses (144, 147: chops at his own pace; 172: both say 178, the label is in doubt) came out medium or low.
STRONG_AUDIO = 0.15      # autocorrelation support above which the audio sets the value
WEAK_AUDIO = 0.05        # below this the audio is not evidence


def audio_env(x, sr):
    """Onset strength (spectral flux) of mono float samples, and its frame rate. Needs numpy."""
    import numpy as np
    x = np.asarray(x, dtype=np.float32)
    if sr > 30000:                                   # 44.1/48 kHz -> half rate: the beat lives below 5 kHz
        x = x[:len(x) // 2 * 2].reshape(-1, 2).mean(1)
        sr = sr / 2
    hop, nfft = 220, 1024
    frames = 1 + (len(x) - nfft) // hop
    if frames < 64:
        return None, None
    idx = np.arange(nfft)[None, :] + hop * np.arange(frames)[:, None]
    spec = np.abs(np.fft.rfft(np.hanning(nfft) * x[idx], axis=1))
    flux = np.maximum(0, np.diff(np.log1p(1000 * spec), axis=0)).sum(1)
    flux = flux - np.convolve(flux, np.ones(40) / 40, "same")
    return np.maximum(flux, 0), sr / hop


def audio_acf(env):
    import numpy as np
    e = env - env.mean()
    n = len(e)
    f = np.fft.rfft(e, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    return ac / (ac[0] + 1e-9)


def audio_support(ac, fr, bpm):
    """Periodicity at 1, 2, 4, 8 and 16 beats: the long lags pin the tempo to a few tenths of a BPM."""
    lag = 60.0 * fr / bpm
    vals = []
    for k in (1, 2, 4, 8, 16):
        l = k * lag
        if l >= len(ac) * 0.8:
            break
        i = int(l)
        f = l - i
        vals.append(ac[i] * (1 - f) + ac[i + 1] * f)
    return float(sum(vals) / len(vals)) if vals else 0.0


def audio_peaks(ac, fr, lo=60.0, hi=200.0, step=0.05):
    """[(support, bpm)] local maxima, strongest first."""
    n = int((hi - lo) / step)
    bs = [lo + i * step for i in range(n)]
    sv = [audio_support(ac, fr, b) for b in bs]
    pk = [(sv[i], bs[i]) for i in range(1, n - 1) if sv[i] >= sv[i - 1] and sv[i] >= sv[i + 1] and sv[i] > 0.02]
    return sorted(pk, reverse=True)


def _octave_dist(x, y):
    return min(abs(math.log(x * k / y)) for k in (0.5, 1, 2))


def _octave_to(x, ref):
    return min((x * k for k in (0.5, 1, 2)), key=lambda v: abs(math.log(v / ref)))


def combined(sr, onsets, length, audio, audio_sr, r=None, g=None):
    """The chops' reading checked against the audio of the take (mono samples, any rate). An audio beat within 4%
    of the chops' reading (or of the spacing alone, which the loop snap can pull away) is agreement: clear audio
    then sets the value, weak audio is averaged with the chops. Clear audio the chops do not match wins with
    medium confidence; otherwise the chops stand, low. The confidence is a word, not a number: high / medium / low."""
    r = r or reading(sr, onsets, length)        # r, g: estimate()'s "reading" and "gapgrid-noloop", when at hand
    if r is None:
        return None
    env, fr = audio_env(audio, audio_sr) if audio is not None else (None, None)
    if env is None:
        return dict(r, conf="low" if r["conf"] < 0.5 else "medium", how=r["how"] + " (no audio)", audio=None)
    ac = audio_acf(env)
    g = g or gapgrid(sr, onsets, 0)
    fam = [r["bpm"]] + ([g["bpm"]] if g else [])
    pk = audio_peaks(ac, fr)
    top = pk[0] if pk else (0.0, None)
    agree = [(s, b) for s, b in pk if any(_octave_dist(b, f) < 0.04 for f in fam)]
    # An agreeing peak must be (nearly) the audio's strongest: a clear beat the chops do not match outranks a
    # weaker 3:2 / 4:3 neighbour they happen to fit (8thmyth's off-beat chops of an 89 BPM take read 119, and
    # the audio's 119 peak, under half its 178 peak, made that HIGH: 16 Nov 2026).
    if agree and max(agree)[0] < 0.7 * top[0] and top[0] >= STRONG_AUDIO:
        b = top[1]
        fam_a = [x for x in (b / 2, b, b * 2) if 60 <= x <= 200]
        best = max(audio_support(ac, fr, x) for x in fam_a)
        b = min((x for x in fam_a if audio_support(ac, fr, x) >= 0.8 * best), key=lambda x: abs(math.log(x / 110)))
        alt = b * 2 if b < 110 else b / 2
        return {"bpm": round(b, 2), "or": round(alt, 2), "conf": "medium",
                "how": f"audio (the chops fit {r['bpm']}, a weaker neighbour of the beat)", "chops": r["bpm"],
                "audio": (round(top[1], 2), round(top[0], 3))}
    if agree:
        s, b = max(agree)
        ref = min(fam, key=lambda f: _octave_dist(b, f))
        b = _octave_to(b, r["bpm"])
        if s >= STRONG_AUDIO:
            bpm, conf, how = b, "high", "audio + chops agree"
        elif s >= WEAK_AUDIO:
            bpm, conf, how = (b + _octave_to(ref, r["bpm"])) / 2, "medium", "audio + chops agree (weak audio)"
        else:
            bpm, conf, how = r["bpm"], "low", "chops (audio too weak)"
    elif top[0] >= 0.2:
        bpm, conf, how = _octave_to(top[1], r["bpm"]), "medium", "audio (the chops disagree)"
    else:
        bpm, conf, how = r["bpm"], "low", "chops (audio unclear, disagrees)"
    alt = bpm * 2 if bpm < PRIOR_C and bpm * 2 <= 200 else bpm / 2
    return {"bpm": round(bpm, 2), "or": round(alt, 2), "conf": conf, "how": how, "chops": r["bpm"],
            "audio": (round(top[1], 2), round(top[0], 3)) if top[1] else None}


def shown(r):
    """What the screen shows: both octaves, each rounded to a whole BPM (sources quote whole BPMs): '82 (or 163)'."""
    lo, hi = sorted((r["bpm"], r["or"]))
    return f"{round(lo)} (or {round(hi)})" if r["bpm"] == lo else f"{round(hi)} (or {round(lo)})"


# ---- the unit's gate: when is a chops-only reading sure? ---------------------------------------------------
# 8thmyth's 24 takes of 16 Nov 2026: SURE 10 times, 9 right, 1 wrong (a take chopped only in dotted values,
# which is straight chopping 3:2 away); every free-pace, even-chop and off-beat-chunk take came out unsure.
# Blind spot: fully swung chops in a random chunk read as straight chops 1.5x faster, sure (synthetic).
W = {0.5: 1.0, 1.0: 1.0, 2.0: 1.0, 4.0: 1.0, 0.75: 0.75, 1.5: 0.75, 3.0: 0.75,
     1 / 6: 0.6, 1 / 3: 0.6, 2 / 3: 0.6, 4 / 3: 0.6}
STRAIGHT = (0.5, 1.0, 2.0, 4.0)
UP = dict(tol=0.10, kind_min=2, cover=0.80, min_gaps=6, nb_margin=0.05)
def structure(sr, gaps, bpm, trip=False):
    beat = 60.0 * sr / bpm
    units = [u for u in W if trip or W[u] > 0.6]
    kinds, on, w = {}, 0, 0.0
    for x in gaps:
        u = x / beat
        k = min(units, key=lambda v: abs(u - v))
        if abs(u - k) < UP["tol"] * max(1.0, k):
            kinds[k] = kinds.get(k, 0) + 1; on += 1; w += W[k]
    plain = sum(1 for k in kinds if kinds[k] >= UP["kind_min"] and (W[k] == 1.0 or trip))
    return plain, on / len(gaps), w / len(gaps), kinds
def best_oct(sr, gaps, T, trip=False):
    return max((structure(sr, gaps, x, trip) + (x,) for x in (T / 2, T, T * 2)), key=lambda s: (min(s[0], 2), s[2]))
def unit_reading(sr, onsets, length=0):
    """The reading LAZY CHOP would show on the unit (chops only): reading() plus SURE / unsure."""
    r = reading(sr, onsets, length)
    if r is None:
        return None
    r = _plainer(sr, onsets, r)
    o = sorted(set(onsets))
    gaps = [b - a for a, b in zip(o, o[1:]) if b - a > 0.04 * sr]
    T = r["bpm"]
    st, cover, wc, kd, _ = best_oct(sr, gaps, T)
    why, also = [], []
    if len(gaps) < UP["min_gaps"]: why.append("few chops")
    if st < 2: why.append("one gap size")
    if cover < UP["cover"]: why.append(f"gaps off the grid ({cover:.0%})")
    for ratio in (4 / 3, 3 / 4, 3 / 2, 2 / 3):
        st2, cov2, wc2, _, b2 = best_oct(sr, gaps, T * ratio, trip=True)
        dotted = sum(v for k, v in kd.items() if W[k] == 0.75)
        # dotted gaps at the reading are triplet gaps at a 2:3 neighbour (a swung "and"): then plainness can't decide
        if st2 >= 2 and (wc2 >= wc - UP["nb_margin"] or (dotted >= 2 and cov2 >= cover - UP["nb_margin"])):
            also.append((wc2, round(T * ratio, 1)))
    if also: why.append("a 4:3 / 3:2 neighbour fits as plainly")
    also = [max(also)[1]] if also else []          # the one neighbour that explains the chops most plainly
    return dict(r, sure=not why, also=also, kinds=kd,
                how=r["how"] + ("; unsure: " + ", ".join(why) if why else "; SURE"))


def _gaps(sr, onsets):
    o = sorted(set(onsets))
    return [b - a for a, b in zip(o, o[1:]) if b - a > 0.04 * sr]


def _r_at(sr, gaps, bpm):
    beat = 60.0 * sr / bpm
    best = -1.0
    for sub, w in ((4, 1.0), (6, 0.9)):
        g = beat / sub
        r = sum(math.cos(2 * math.pi * x / g) * (1.0 if round(x / g) in SIMPLE else 0.55) for x in gaps) / len(gaps)
        best = max(best, r * w)
    return best


def _plainer(sr, onsets, r, margin=0.15):
    """A 3:2 / 4:3 neighbour that explains the chops as plain beats (1 / 2 / half) much better than the first pick
    replaces it (8thmyth's T2: chops 0.52 / 1.04 s read 154 for 115; T4: 0.6 / 1.2 s read 152 for 101)."""
    gaps = _gaps(sr, onsets)
    if len(gaps) < 3:
        return r
    T = r["bpm"]
    wcT = best_oct(sr, gaps, T)[2]
    best = None
    for ratio in (2 / 3, 3 / 4, 4 / 3, 3 / 2):
        b = max((_r_at(sr, gaps, T * ratio * (1 + d / 1000)), T * ratio * (1 + d / 1000)) for d in range(-30, 31, 2))[1]
        s2 = best_oct(sr, gaps, b)
        if s2[0] >= 2 and s2[2] >= wcT + margin and (best is None or s2[2] > best[0]):
            best = (s2[2], b)
    if not best:
        return r
    t2 = best[1]
    while t2 < 60:
        t2 *= 2
    while t2 > 200:
        t2 /= 2
    t2 = max((x for x in (t2 / 2, t2, t2 * 2) if 60 <= x <= 200), key=prior)
    alt = t2 * 2 if t2 < PRIOR_C and t2 * 2 <= 200 else t2 / 2
    out = dict(r, bpm=round(t2, 2), how=r["how"] + f" -> plainer at {t2:.1f}")
    out["or"] = round(alt, 2)
    return out


def _cv(gaps):
    m = sorted(gaps)[len(gaps) // 2]
    return (sum((x - m) ** 2 for x in gaps) / len(gaps)) ** 0.5 / m


def unit_display(sr, onsets, length=0):
    """The one line LAZY CHOP would show after the slice-count popup (agreed with 8thmyth, 16 Nov 2026, 22:05):
    'BPM first (second)'. First: the best guess. Brackets: the second-best: a 4:3 or 3:2 neighbour when one fits
    as plainly (in the range nearest the first), else half or double time. A dot marks the 3:2 reading (dotted
    chops at the faster tempo, triplet chops at the slower). Nothing is written to the sample. At most 13
    characters; the popup holds 17 inside the editor's frame (emulator, T8 image)."""
    r = unit_reading(sr, onsets, length)
    if r is None:
        return None
    T = r["bpm"]
    dot = ""
    if r.get("also"):
        n = r["also"][0]
        br = min((n * k for k in (0.5, 1, 2)), key=lambda v: abs(math.log(v / T)))
        q = br / T                       # 3:2 only, counted in the range nearest the first number (4:3 has no dot)
        if abs(q - 1.5) < 0.04 or abs(q - 2 / 3) < 0.03:
            dot = "."
    else:
        br = r["or"]
    if br > 200:                         # keep the bracket on the screen's scale (BPM 156 (209) read badly)
        br /= 2
    return {"line": f"BPM {round(T)} ({round(br)}{dot})", "bpm": T, "second": br, "sure": r["sure"], "r": r}


# ---- synthetic chop patterns --------------------------------------------------------------------------------
def pattern(name, bpm, sr=44100, bars=2, jitter_ms=10.0, seed=0):
    """(onsets in samples, loop length) of a way of chopping a `bars`-bar loop at `bpm`, each tap off by up to
    `jitter_ms` (a hand plus ZERO SNAP)."""
    rnd = random.Random(seed)
    beat = 60.0 * sr / bpm
    steps = {   # positions in 16ths within one bar
        "quarters": [0, 4, 8, 12],
        "eighths": [0, 2, 4, 6, 8, 10, 12, 14],
        "offbeat": [0, 6, 10, 12],                 # 1, 2&, 3&, 4
        "syncopated": [0, 3, 6, 10, 13],           # a breakbeat-style cut
        "sparse": [0, 10],                         # two chops a bar
        "swing16": [0, 1.33, 2, 3.33, 4, 5.33, 6, 7.33, 8, 9.33, 10, 11.33, 12, 13.33, 14, 15.33],
        "triplet": [0, 2.667, 5.333, 8, 10.667, 13.333],
        "halftime": [0, 12],                       # snare on 3 of a half-time feel... only the kick and snare
    }[name]
    out = []
    for b in range(bars):
        for s in steps:
            t = (b * 16 + s) * beat / 4
            out.append(int(t + rnd.uniform(-1, 1) * jitter_ms * sr / 1000.0))
    start = rnd.randint(0, 2000)                    # the trim start is not on the grid's zero
    return [o + start for o in out], int(bars * 4 * beat)


def selftest():
    sr = 44100
    takes = {   # 8thmyth's MKI, 16 Nov 2026: takes 1-2 the same 24.93 s sample, mixed spacing (truth 77 / 154);
                # take 3 a 120 BPM YouTube recording, TSTR off, 32.04 s, chops about every 2 beats (truth 120)
        "take 1": [0, 30848, 68816, 103424, 139888, 159088, 175264, 193344, 210864, 248080, 282704, 300368, 318336,
                   336720, 354272, 420288, 451632, 488832, 525184, 544320, 561552, 579888, 597376, 615456, 629904,
                   661040, 696240, 731328, 763792, 795264, 828512, 862496, 895664, 928432, 947216, 962896, 996448,
                   1030512, 1063680, 1095664],
        "take 2": [0, 34272, 68336, 103968, 139200, 159504, 176960, 196816, 213952, 246112, 281232, 301248, 319168,
                   337856, 355280, 387808, 419344, 439328, 457344, 475616, 493504, 511136, 528976, 546288, 561552,
                   595376, 631104, 663952, 696048, 730848, 763328, 827024, 862032, 895232, 927904, 946912, 963536,
                   997440, 1028192, 1062432, 1095072],
        "take 3": [0, 45216, 88752, 132944, 174352, 219760, 264480, 309344, 352768, 397424, 440624, 486128, 530464,
                   576720, 619344, 663200, 704608, 750224, 794496, 839120, 883456, 926736, 969184, 1014544, 1014688,
                   1059808, 1106544, 1147888, 1192256, 1235328, 1281184, 1324160]}
    lens = {"take 1": 1099376, "take 2": 1099376, "take 3": 1412768}
    for name, on in takes.items():
        for length in (lens[name], 0):
            g = gapgrid(sr, on, length)
            print(f"{name} ({'with loop length' if length else 'spacing only'}): gapgrid {g}")
    print()
    names = ["quarters", "eighths", "offbeat", "syncopated", "sparse", "swing16", "triplet", "halftime"]
    tempos = [84, 92, 100, 120, 128, 140, 174]
    methods = ["gapgrid", "gapgrid-noloop", "gapgrid-chunk", "gapunit", "median", "grid+loop"]
    hits = {m: 0 for m in methods}
    octv = {m: 0 for m in methods}
    total = 0
    per = {}
    for name in names:
        for bpm in tempos:
            for seed in range(3):
                on, length = pattern(name, bpm, sr, bars=2, seed=seed)
                est = estimate(sr, on, length)
                rnd = random.Random(seed + 100)                  # a random chunk: cut anywhere, any length
                cut = rnd.randint(0, len(on) // 3)
                chunk = on[cut:cut + max(4, len(on) - cut - rnd.randint(0, len(on) // 3))]
                est["gapgrid-chunk"] = gapgrid(sr, chunk, 0)
                total += 1
                for m in methods:
                    v = est[m]
                    v = v["bpm"] if isinstance(v, dict) else v
                    ok = v is not None and abs(v / bpm - 1) < 0.01
                    okx = v is not None and min(abs(v * k / bpm - 1) for k in (0.5, 1, 2)) < 0.01
                    hits[m] += ok
                    octv[m] += okx
                    per.setdefault((name, m), [0, 0])
                    per[(name, m)][0] += ok
                    per[(name, m)][1] += 1
    print(f"{total} patterns (8 ways of chopping x 7 tempos x 3 seeds, 2-bar loops, +-10 ms per chop;"
          f" gapgrid-chunk: a random piece of each, no loop length)")
    print("right within 1%:            " + "  ".join(f"{m} {100 * hits[m] / total:.0f}%" for m in methods))
    print("right or half/double tempo: " + "  ".join(f"{m} {100 * octv[m] / total:.0f}%" for m in methods))
    print()
    print(f"{'pattern':12s}" + "".join(f"{m:>15s}" for m in methods))
    for name in names:
        print(f"{name:12s}" + "".join(f"{100 * per[(name, m)][0] / per[(name, m)][1]:14.0f}%" for m in methods))


def realtest(path=None):
    """Score unit_reading on the owner's takes (chop_tempo_takes.json beside this file)."""
    import json
    import os
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "chop_tempo_takes.json")
    takes = json.load(open(path))["takes"]
    n = right = first = sr_ = sw = 0
    for t in takes:
        r = unit_reading(44100, t["slices"], t["length"])
        tr = t["bpm"]
        cands = [r["bpm"], r["or"]] + list(r.get("also", []))
        ok = any(min(abs(c * k / tr - 1) for k in (0.5, 1, 2)) < 0.01 for c in cands)
        n += 1
        right += ok
        first += abs(r["bpm"] / tr - 1) < 0.01
        sr_ += r["sure"] and ok
        sw += r["sure"] and not ok
        print(f"{t['time']} {tr:6.1f} {t['tier']} {t['style']:14s} -> {r['bpm']:7.2f} (or {r['or']:7.2f})"
              f" {'SURE  ' if r['sure'] else 'unsure'} {'ok' if ok else 'MISS'}")
    print(f"{n} takes: right {right}, first number exact {first}, sure and right {sr_}, SURE AND WRONG {sw}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "realtest":
        realtest(sys.argv[2] if len(sys.argv) > 2 else None)
    elif len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) > 4 and sys.argv[1] == "est":
        sr, length = int(sys.argv[2]), int(sys.argv[3])
        print(estimate(sr, [int(x) for x in sys.argv[4:]], length))
    else:
        print(__doc__)
