#!/usr/bin/env python3
"""GATE VERB voicing sandbox: the float model, with knobs the module does not have yet.

    python3 tools/harness/gateverb_voice.py IN.wav -o OUT.wav [-p SIZE=80 -p PRE=20 ...]
    python3 tools/harness/gateverb_voice.py --test pluck -o out.wav -p SIZE=40
    python3 tools/harness/gateverb_voice.py --test click --sweep SIZE=127,90,60,30 -o size.wav
    python3 tools/harness/gateverb_voice.py --impulse [-p ...]      # RT60, memory, no file
    python3 tools/harness/gateverb_voice.py --selftest              # defaults == verify_gateverb's model

A place to choose a voicing by ear before any of it is written in DSP assembly. It is
the float model `tools/verify/verify_gateverb.py` checks the module against (the
module matches it to 58 dB), the same topology, lengths, LFOs, parameter laws and
per-block smoothing, with three additions:

  SIZE   0-127, default 127: every delay length and the second LFO's centre and depth
         scaled by 0.2 + 0.8 SIZE/127 (127 is the module's lengths). The first LFO's
         smear (10 +- 60 samples on the first input allpass) is not scaled.
  PRE    0-127, default 0: a predelay of 32 PRE samples (0 to 92 ms) on the mono input,
         ahead of the input allpasses.
  LOCUT  0-127, default 0: a one-pole high-pass in each half of the tank, after the
         damping low-pass; 0 is off, 1-127 run from 20 Hz to 1 kHz, exponentially.

With the three at their defaults the output is the model's, sample for sample
(`--selftest` runs verify_gateverb.model beside it). Everything else here is
proposed, not built: no assembly exists for SIZE, PRE or LOCUT, and the costs and
memory the tool prints are the model's own arithmetic, not a measurement.

The memory line is the words the chip would need (ring + predelay) against two
limits: the module's 15,862-word ring today, and 14,368 words, the most a
reverb on T3, T4, T7 or T8 may use if nothing is to reach offset 0x3820 of the
slot, where octabam's window code lives.

Sample rate 44,100 Hz, 16-sample blocks, mono input (left and right summed), stereo out.
"""
import argparse, math, pathlib, random, struct, sys, wave

SR = 44100
FRAMES = 16
Q = 1 << 23
LEN = [109, 157, 233, 386, 1600, 1973, 3303, 1852, 1610, 4630]
RING_TODAY = 15862
RING_WINDOW = 0x3820          # 14,368
NAMES = ("AMNT", "GAIN", "TIME", "DIFF", "TONE", "GATE", "SIZE", "PRE", "LOCUT")
DEFAULTS = dict(AMNT=40, GAIN=51, TIME=64, DIFF=100, TONE=90, GATE=0, SIZE=127, PRE=0, LOCUT=0)


def s24(v):
    v &= 0xFFFFFF
    return v - (1 << 24) if v & 0x800000 else v


def mulf(a, b):
    return (a * b) >> 23


def parab(phase):
    x = s24(phase)
    t = (Q - 1) - abs(x)
    return max(-Q, min(Q - 1, (x * t >> 23) * 4))


def geometry(size):
    """SIZE scales the tank (lines 4-9) only: the input allpasses are 20 ms of diffusion
    either way, and the smear tap reads around line 0, which must keep its length."""
    s = 0.2 + 0.8 * size / 127
    lens = LEN[:4] + [round(l * s) for l in LEN[4:]]
    base, b = [], 0
    for l in lens:
        base.append(b); b += l + 1
    n = base[-1] + lens[-1]
    depth = 0x061000 if size == 127 else int(0x061000 * s)
    dsamp = depth >> 12
    centre = 4531 if size == 127 else min(round(4531 * s), lens[9] - 2 - dsamp)
    return s, lens, base, n, centre, depth


def memory_words(p):
    return geometry(p["SIZE"])[3] + 32 * p["PRE"]


def locut_coef(k):
    if k <= 0:
        return 0.0
    f = 20.0 * (1000.0 / 20.0) ** ((k - 1) / 126)
    return 1.0 - math.exp(-2 * math.pi * f / SR)


def model(samples, params, blocks_skip=0, lfo="module"):
    """samples: interleaved stereo ints (24-bit scale). params: dict of NAMES.
    Returns (left, right) as floats on the 24-bit scale.

    lfo: "module" (the default) is GATE VERB as built: the smear LFO unipolar, 0..1, as Clouds'
    (stmlib CosineOscillator::Next() returns 0..1), so the smear reads line 0 at 10..70; the
    long-delay tap swings centre +- depth, twice Clouds' excursion. "clouds": both unipolar, the tap
    at centre..centre+depth. "old": both bipolar, the module before 5 Nov 2026, whose smear read
    -50..70: up to 50 samples behind line 0, in the far end of the last tank line, fed back to the
    input; the tail grew from TIME 94 up (modules/gateverb/README.md).
    """
    p = dict(DEFAULTS, **params)
    _s, LN, BASE, N, centre, depth = geometry(p["SIZE"])
    pre_n = 32 * p["PRE"]
    pre = [0.0] * (pre_n + 1)
    pw = 0
    hc = locut_coef(p["LOCUT"])
    hp1 = hp2 = 0.0
    ring = [0.0] * N
    ph1 = ph2 = 0
    amt = gc = krt = kap = klp = 0
    lp1 = lp2 = 0.0
    w = 0
    env = hold = gs = 0
    hmax = 0x7FFFFF if p["GATE"] == 0 else 2048 + 256 * p["GATE"]
    out_l, out_r = [], []
    k = [(p[n] << 16) for n in NAMES[:5]]
    lo, hi = -1.0, 1.0 - 1 / Q
    for blk in range(len(samples) // 2 // FRAMES):
        if blk < blocks_skip:
            for s in range(FRAMES):
                out_l.append(samples[2 * (blk * FRAMES + s)]); out_r.append(samples[2 * (blk * FRAMES + s) + 1])
            continue
        amt += (k[0] - amt) >> 4
        gc += ((k[1] >> 3) - gc) >> 4
        krt += ((mulf(k[2], 0x50A3D7) + 0x2CCCCD) - krt) >> 4
        kap += (mulf(k[3], 0x666666) - kap) >> 4
        klp += ((mulf(k[4], 0x79999A) + 0x066666) - klp) >> 4
        ph1 = s24(ph1 + 190 * FRAMES); ph2 = s24(ph2 + 114 * FRAMES)
        u1 = parab(ph1) if lfo == "old" else (parab(ph1) + Q) >> 1     # 0..1 unless old
        u2 = (parab(ph2) + Q) >> 1 if lfo == "clouds" else parab(ph2)
        t1 = mulf(u1, 0x03C000) + 0x00A000
        kint1, fr1 = t1 >> 12, (t1 & 0xFFF) << 11
        t2 = mulf(u2, depth)
        kint2, fr2 = centre + (t2 >> 12), (t2 & 0xFFF) << 11
        K, G, R, L, A = kap / Q, gc / Q, krt / Q, klp / Q, amt / Q
        for s in range(FRAMES):
            i0 = blk * FRAMES + s
            li, ri = samples[2 * i0], samples[2 * i0 + 1]
            l_in, r_in = li / Q, ri / Q
            m = min(abs((li + ri) >> 1), Q - 1)
            env2 = env - (env >> 9)
            env = env2 + max(m - env2, 0)
            hold = max(hold - 1, 0)
            if hmax == 0x7FFFFF or env - 0x010000 > 0:
                hold = hmax
            gs += (min(hold << 16, Q - 1) - gs) >> 5
            G_ = gs / Q

            def rd(j, kk):
                return ring[(w - BASE[j] - kk) % N]

            def wr(j, kk, v):
                ring[(w - BASE[j] - kk) % N] = lo if v < lo else hi if v > hi else v
            a0 = rd(0, kint1); b0 = rd(0, kint1 + 1)
            wr(0, 100, a0 + (b0 - a0) * fr1 / Q)
            x_in = (l_in + r_in) / 2
            if pre_n:
                pre[pw] = x_in
                pw = (pw + 1) % (pre_n + 1)
                x_in = pre[pw]
            acc = x_in * G
            for j in range(4):
                r = rd(j, LN[j] - 1); acc += K * r; wr(j, 0, acc); acc = r - K * max(-1, min(1, acc))
            apout = acc
            # first half
            a1 = rd(9, kint2); b1 = rd(9, kint2 + 1)
            acc = apout + (a1 + (b1 - a1) * fr2 / Q) * R
            lp1 += L * (acc - lp1); acc = lp1
            if hc:
                hp1 += hc * (acc - hp1); acc -= hp1
            r = rd(4, LN[4] - 1); acc += -K * r; wr(4, 0, acc); acc = r + K * max(-1, min(1, acc))
            r = rd(5, LN[5] - 1); acc += K * r; wr(5, 0, acc); acc = r - K * max(-1, min(1, acc))
            wr(6, 0, acc); wet = max(-1, min(1, 2 * acc)) * G_
            out_l.append(max(-1, min(1, l_in + (8 * wet - l_in) * A)) * Q)
            # second half
            acc = apout + rd(6, LN[6] - 1) * R
            lp2 += L * (acc - lp2); acc = lp2
            if hc:
                hp2 += hc * (acc - hp2); acc -= hp2
            r = rd(7, LN[7] - 1); acc += K * r; wr(7, 0, acc); acc = r - K * max(-1, min(1, acc))
            r = rd(8, LN[8] - 1); acc += -K * r; wr(8, 0, acc); acc = r + K * max(-1, min(1, acc))
            wr(9, 0, acc); wet = max(-1, min(1, 2 * acc)) * G_
            out_r.append(max(-1, min(1, r_in + (8 * wet - r_in) * A)) * Q)
            w = (w + 1) % N
    return out_l, out_r


# ---- audio in and out ------------------------------------------------------
def read_wav(path):
    with wave.open(str(path)) as f:
        ch, sw, sr, n = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
        raw = f.readframes(n)
    if sw not in (2, 3):
        sys.exit(f"{path}: {8 * sw}-bit samples; 16 or 24 only")
    if sr != SR:
        print(f"note: {path} is {sr} Hz; the model runs at {SR} and does not resample", file=sys.stderr)
    vals = []
    for i in range(0, len(raw), sw):
        b = raw[i:i + sw]
        v = int.from_bytes(b, "little", signed=True)
        vals.append(v << (24 - 8 * sw))
    if ch == 1:
        st = []
        for v in vals:
            st += [v, v]
        return st
    return [v for i in range(0, len(vals), ch) for v in vals[i:i + 2]]


def write_wav(path, left, right):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2); f.setsampwidth(3); f.setframerate(SR)
        buf = bytearray()
        for a, b in zip(left, right):
            for v in (a, b):
                buf += int(max(-Q, min(Q - 1, round(v)))).to_bytes(3, "little", signed=True)
        f.writeframes(bytes(buf))


def test_signal(kind, seconds):
    n = int(seconds * SR)
    x = [0.0] * n
    rnd = random.Random(7)
    if kind == "click":
        for t in (0, 2.0):
            x[int(t * SR)] = 0.5
    elif kind == "pluck":             # Karplus-Strong notes, a short phrase
        for t, f in ((0.0, 220.0), (0.5, 330.0), (1.0, 262.0), (1.5, 196.0)):
            per = int(SR / f); buf = [rnd.uniform(-0.4, 0.4) for _ in range(per)]
            st = int(t * SR)
            for i in range(int(0.45 * SR)):
                v = buf[i % per]; buf[i % per] = 0.498 * (v + buf[(i + 1) % per])
                if st + i < n:
                    x[st + i] += v
    elif kind == "drums":             # kick, snare, hats at 120 bpm, one bar then silence
        for b in range(8):
            st = int(b * 0.25 * SR)
            if b % 4 == 0:
                for i in range(int(0.2 * SR)):
                    x[st + i] += 0.6 * math.sin(2 * math.pi * (50 + 120 * math.exp(-i / 800)) * i / SR) * math.exp(-i / 6000)
            if b % 4 == 2:
                for i in range(int(0.15 * SR)):
                    x[st + i] += 0.35 * rnd.uniform(-1, 1) * math.exp(-i / 2500)
            for i in range(int(0.04 * SR)):
                x[st + i] += 0.1 * rnd.uniform(-1, 1) * math.exp(-i / 300)
    elif kind == "noise":
        for i in range(int(0.3 * SR)):
            x[i] = 0.3 * rnd.uniform(-1, 1)
    else:
        sys.exit(f"--test {kind}: click, pluck, drums or noise")
    st = []
    for v in x:
        st += [int(v * Q)] * 2
    return st


# ---- measures --------------------------------------------------------------
def rt60(ir):
    """Schroeder integration, -5 to -25 dB slope, extrapolated to 60 dB."""
    e = [v * v for v in ir]
    edc, acc = [0.0] * len(e), 0.0
    for i in range(len(e) - 1, -1, -1):
        acc += e[i]; edc[i] = acc
    if edc[0] <= 0:
        return None
    db = [10 * math.log10(max(v, 1e-30) / edc[0]) for v in edc]
    try:
        i5 = next(i for i, d in enumerate(db) if d <= -5)
        i25 = next(i for i, d in enumerate(db) if d <= -25)
    except StopIteration:
        return None
    return 60 * (i25 - i5) / 20 / SR


def impulse_report(p, seconds=8.0, lfo="module"):
    # 200 blocks of silence first: the knobs glide from 0 (a sixteenth a block), so an
    # impulse at the start would meet an input gain still near 0
    pre = 200 * FRAMES
    n = pre + int(seconds * SR) // FRAMES * FRAMES
    st = [0] * (2 * n)
    st[2 * pre] = st[2 * pre + 1] = int(0.5 * Q)
    q = dict(p, AMNT=127)              # wet only: at 127 the dry is (1 - A), under -60 dB once settled
    L, R = model(st, q, lfo=lfo)
    ir = [a / Q for a in L[pre:]]
    t = rt60(ir)
    seg = int(0.5 * SR)
    tail = [10 * math.log10(sum(v * v for v in ir[i:i + seg]) / seg + 1e-30) for i in range(1, len(ir) - seg, seg)]
    grows = any(b > a + 3 for a, b in zip(tail, tail[1:]) if a > -110)
    words = memory_words(p)
    print(f"  {' '.join(f'{k}={p[k]}' for k in NAMES)}")
    print(f"  RT60 {'%.2f s' % t if t else 'n/a (decays past the window)'}; "
          f"peak wet {20 * math.log10(max(abs(v) for v in ir[1:]) + 1e-30):.1f} dBFS"
          f"{'; UNSTABLE: the tail grows (half-second RMS rises by over 3 dB)' if grows else ''}")
    print(f"  tail RMS by half second, dB: {' '.join('%.0f' % v for v in tail)}")
    print(f"  memory {words} words: {'within' if words <= RING_TODAY else 'OVER'} today's ring ({RING_TODAY}), "
          f"{'within' if words <= RING_WINDOW else 'OVER'} the window-slot cap ({RING_WINDOW})")


def selftest():
    """The model with SIZE/PRE/LOCUT at defaults against verify_gateverb.model, sample for sample."""
    src = pathlib.Path(__file__).resolve().parents[1] / "verify" / "verify_gateverb.py"
    # only the model is wanted: no build, no dsp_host, no registry (send_probe loads every manifest)
    code = src.read_text().replace("\nmain()\n", "\n").replace("import send_probe  # noqa: E402\n", "send_probe = None\n")
    ns = {"__name__": "gateverb_ref", "__file__": str(src)}
    cwd = pathlib.Path.cwd()
    try:
        exec(compile(code, str(src), "exec"), ns)
    finally:
        import os; os.chdir(cwd)
    rnd = random.Random(3)
    n = 400 * FRAMES
    mono = [0] * n
    mono[64] = int(0.5 * Q)
    for i in range(3000, 3600):
        mono[i] = int(0.3 * Q * (rnd.random() - 0.5))
    st = [v for s in mono for v in (s, s)]
    bad = 0
    for prm in ([64, 51, 80, 100, 90, 0], [80, 51, 110, 100, 90, 40], [127, 20, 127, 30, 10, 0]):
        rL, rR = ns["model"](st, prm, 4)
        mL, mR = model(st, dict(zip(NAMES, prm)), 4)
        same = rL == mL and rR == mR
        bad += not same
        print(f"  [{'ok' if same else 'FAIL'}] {prm}: sample for sample")
    print(f"selftest: {'PASS' if not bad else 'FAIL'}")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input", nargs="?", help="a 16- or 24-bit wav, 44.1 kHz")
    ap.add_argument("-o", "--out", help="output wav")
    ap.add_argument("-p", "--param", action="append", default=[], help="NAME=value, 0-127")
    ap.add_argument("--test", help="built-in source: click, pluck, drums, noise")
    ap.add_argument("--seconds", type=float, default=6.0, help="length of a --test source (default 6)")
    ap.add_argument("--tail", type=float, default=4.0, help="silence appended to a wav input (default 4 s)")
    ap.add_argument("--sweep", help="NAME=v1,v2,...: one output per value, the file name suffixed")
    ap.add_argument("--impulse", action="store_true", help="print RT60 and memory for the settings")
    ap.add_argument("--lfo", choices=("module", "clouds", "old"), default="module",
                    help="module: as built; clouds: both LFOs unipolar; old: before the smear fix (see model())")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    p = dict(DEFAULTS)
    for kv in a.param:
        k, _, v = kv.partition("=")
        k = k.upper()
        if k not in p:
            sys.exit(f"-p {kv}: knobs are {', '.join(NAMES)}")
        p[k] = max(0, min(127, int(v)))
    sweep = [(None, None)]
    if a.sweep:
        k, _, vs = a.sweep.partition("=")
        k = k.upper()
        if k not in p:
            sys.exit(f"--sweep {a.sweep}: knobs are {', '.join(NAMES)}")
        sweep = [(k, int(v)) for v in vs.split(",")]
    if a.impulse:
        for k, v in sweep:
            impulse_report(dict(p, **({k: v} if k else {})), lfo=a.lfo)
        return
    if a.test:
        st = test_signal(a.test, a.seconds)
    elif a.input:
        st = read_wav(a.input) + [0] * (2 * int(a.tail * SR))
    else:
        ap.error("an input wav, --test, --impulse or --selftest")
    st += [0] * ((-len(st)) % (2 * FRAMES))
    if not a.out:
        ap.error("-o OUT.wav")
    out = pathlib.Path(a.out)
    for k, v in sweep:
        q = dict(p, **({k: v} if k else {}))
        L, R = model(st, q, lfo=a.lfo)
        path = out if k is None else out.with_name(f"{out.stem}_{k}{v}{out.suffix}")
        write_wav(path, L, R)
        print(f"{path}: {' '.join(f'{n}={q[n]}' for n in NAMES)}; memory {memory_words(q)} words")


if __name__ == "__main__":
    main()
