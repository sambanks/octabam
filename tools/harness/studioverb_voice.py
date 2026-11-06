#!/usr/bin/env python3
"""STUDIO VERB voicing sandbox: the float model, with knobs the module does not have yet.

    python3 tools/harness/studioverb_voice.py IN.wav -o OUT.wav [-p SIZE=80 -p LCUT=40 ...]
    python3 tools/harness/studioverb_voice.py --test pluck -o out.wav -p SIZE=40
    python3 tools/harness/studioverb_voice.py --test click --sweep SIZE=127,90,60,30 -o size.wav
    python3 tools/harness/studioverb_voice.py --impulse -p MODE=2     # a mode's voicing (0 ROOM 1 PLATE 2 HALL 3 GATED)
    python3 tools/harness/studioverb_voice.py --selftest              # defaults == verify_studioverb's model

A place to choose a voicing by ear before any of it is written in DSP assembly. It is
the float model `tools/verify/verify_studioverb.py` checks the module against (the
module matches it to 58 dB), the same topology, lengths, LFOs, parameter laws and
per-block smoothing, and every knob the module has:

  SIZE, LCUT, MOD, RATE   page 2, as the module has them (5 Nov 2026): SIZE moves the tank's read
         taps in to 20 % of each length at 0 (127 is full); LCUT a one-pole high-pass in each tank
         half, c = 0.1447 LCUT^2 (about 1 kHz at 127); MOD the long delay's swing, 0 to twice
         today's; RATE both LFOs' speed, 0 (frozen) to twice today's. At their defaults (127, 0, 64,
         64) the module is as it was.
  PRE    0-127, default 0 (slot 11): a predelay of 32 PRE samples (0 to 92 ms) on the mono input,
         held in the far end of the long delay that SIZE leaves unread, so clamped to that room:
         none at SIZE 127, about 24 ms at 90, 44 ms at 60.
Two gate forms (--gate):
  module  as built (5 Nov 2026): when the hold runs out the gain falls 1/2^REL a sample, a straight
          line in dB like a desk gate's release (SSL channel gate, Drawmer DS201; the module's REL is
          11: a 46 ms time constant, -60 dB in about 320 ms), and below 2^-11 it is 0. While it is 0
          (tested at each block's start) the loop gain and the allpass coefficient are 0, so every
          line is a plain delay and the tank flushes in one pass of its longest path (8,092 samples);
          the next hit starts from silence. --release-shift changes REL here only.
  old     the module before 5 Nov 2026: the wet closed in about 3 ms and the tank rang on.

The output is verify_studioverb's model, sample for sample (`--selftest` runs the two side by
side, every knob included). The ring is 14,366 words whatever the knobs (SIZE moves read taps,
PRE borrows what SIZE frees); `--impulse` prints the predelay a setting actually gets.

Sample rate 44,100 Hz, 16-sample blocks, mono input (left and right summed), stereo out.
"""
import argparse, math, pathlib, random, struct, sys, wave

SR = 44100
FRAMES = 16
Q = 1 << 23
LEN = [109, 157, 233, 386, 1440, 1776, 2973, 1667, 1449, 4167]
RING_TODAY = 14366
NAMES = ("AMNT", "GAIN", "TIME", "DIFF", "TONE", "GATE", "MODE", "LCUT", "MOD", "RATE", "SIZE", "PRE")   # slots 0-11
DEFAULTS = dict(AMNT=40, GAIN=51, TIME=64, DIFF=100, TONE=90, GATE=0, MODE=1, LCUT=0, MOD=64, RATE=64, SIZE=127, PRE=0)


def mode_view(mode):
    """A MODE's knob values from the manifest (modules/studioverb), as MODE DEFAULTS writes them on the panel."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import toolpath  # noqa: F401
    from remix import registry
    m = registry.by_key("STUDIO VERB")
    v = next(v for v in m.mode_views if v.mode == mode)
    return {NAMES[slot]: val for slot, val in v.defaults.items()}


def s24(v):
    v &= 0xFFFFFF
    return v - (1 << 24) if v & 0x800000 else v


def mulf(a, b):
    return (a * b) >> 23


def parab(phase):
    x = s24(phase)
    t = (Q - 1) - abs(x)
    return max(-Q, min(Q - 1, (x * t >> 23) * 4))


def pre_samples(p):
    """The predelay a setting gets: 32 PRE, clamped to the m - 2 words SIZE leaves past the long
    delay's tap (m = 4167 f, f settled)."""
    f = mulf((127 - p["SIZE"]) << 16, 0x6734EE)
    return min(32 * p["PRE"], max(0, mulf(4167, f) - 2))


def model(samples, params, blocks_skip=0, lfo="module", gate="module", rel=11):
    """samples: interleaved stereo ints (24-bit scale). params: dict of NAMES.
    Returns (left, right) as floats on the 24-bit scale.

    lfo: "module" (the default) is STUDIO VERB as built: the smear LFO unipolar, 0..1, as Clouds'
    (stmlib CosineOscillator::Next() returns 0..1), so the smear reads line 0 at 10..70; the
    long-delay tap swings centre +- depth, twice Clouds' excursion. "clouds": both unipolar, the tap
    at centre..centre+depth. "old": both bipolar, the module before 5 Nov 2026, whose smear read
    -50..70: up to 50 samples behind line 0, in the far end of the last tank line, fed back to the
    input; the tail grew from TIME 94 up (modules/studioverb/README.md).
    """
    p = dict(DEFAULTS, **params)
    BASE, b = [], 0
    for l in LEN:
        BASE.append(b); b += l + 1
    N = BASE[-1] + LEN[-1]
    hp1 = hp2 = 0.0
    sz_f = mod_s = lc = 0
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
        # page 2 as studioverb.asm computes it each block (verify_studioverb.model is the reference)
        sz_f += (mulf((127 - p["SIZE"]) << 16, 0x6734EE) - sz_f) >> 4
        LN = [LEN[j] - mulf(LEN[j], sz_f) for j in range(10)]
        mod_s += (((p["MOD"] << 16) - 0x400000) - mod_s) >> 4
        depth = mulf(2 * (0x061000 - mulf(0x061000, sz_f)), 0x400000 + mod_s)
        centre = LN[9] - 2 - (depth >> 12)
        m9 = mulf(4167, sz_f)
        pd = min(32 * p["PRE"], max(0, m9 - 2)); pkw = 4168 - m9
        u = p["LCUT"] << 16
        lc += (mulf(mulf(u, u), 0x12866A) - lc) >> 4
        C = lc / Q
        ph1 = s24(ph1 + mulf(380, p["RATE"] << 16) * FRAMES); ph2 = s24(ph2 + mulf(228, p["RATE"] << 16) * FRAMES)
        u1 = parab(ph1) if lfo == "old" else (parab(ph1) + Q) >> 1     # 0..1 unless old
        u2 = (parab(ph2) + Q) >> 1 if lfo == "clouds" else parab(ph2)
        t1 = mulf(u1, 0x03C000) + 0x00A000
        kint1, fr1 = t1 >> 12, (t1 & 0xFFF) << 11
        t2 = mulf(u2, depth)
        kint2, fr2 = centre + (t2 >> 12), (t2 & 0xFFF) << 11
        K, G, R, L, A = kap / Q, gc / Q, krt / Q, klp / Q, amt / Q
        if gate == "module" and gs == 0:     # a shut gate: the tank flushes
            R = K = 0.0
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
            if gate == "module":
                if hold:
                    gs += ((Q - 1) - gs) >> 5
                else:
                    gs -= gs >> rel
                    if gs - 0x001000 < 0:
                        gs = 0
            else:
                gs += (min(hold << 16, Q - 1) - gs) >> 5
            G_ = gs / Q

            def rd(j, kk):
                return ring[(w - BASE[j] - kk) % N]

            def wr(j, kk, v):
                ring[(w - BASE[j] - kk) % N] = lo if v < lo else hi if v > hi else v
            a0 = rd(0, kint1); b0 = rd(0, kint1 + 1)
            wr(0, 100, a0 + (b0 - a0) * fr1 / Q)
            x_in = (l_in + r_in) / 2
            if pd:
                wr(9, pkw, x_in); x_in = rd(9, pkw + pd)
            acc = x_in * G
            for j in range(4):
                r = rd(j, LEN[j] - 1); acc += K * r; wr(j, 0, acc); acc = r - K * max(-1, min(1, acc))
            apout = acc
            # first half
            a1 = rd(9, kint2); b1 = rd(9, kint2 + 1)
            acc = apout + (a1 + (b1 - a1) * fr2 / Q) * R
            lp1 += L * (acc - lp1); acc = lp1
            d = acc - hp1; acc = d - C * d; hp1 += C * d
            r = rd(4, LN[4] - 1); acc += -K * r; wr(4, 0, acc); acc = r + K * max(-1, min(1, acc))
            r = rd(5, LN[5] - 1); acc += K * r; wr(5, 0, acc); acc = r - K * max(-1, min(1, acc))
            wr(6, 0, acc); wet = max(-1, min(1, 2 * acc)) * G_
            out_l.append(max(-1, min(1, l_in + (8 * wet - l_in) * A)) * Q)
            # second half
            acc = apout + rd(6, LN[6] - 1) * R
            lp2 += L * (acc - lp2); acc = lp2
            d = acc - hp2; acc = d - C * d; hp2 += C * d
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


def impulse_report(p, seconds=8.0, lfo="module", gate="module", rel=11):
    # 200 blocks of silence first: the knobs glide from 0 (a sixteenth a block), so an
    # impulse at the start would meet an input gain still near 0
    pre = 200 * FRAMES
    n = pre + int(seconds * SR) // FRAMES * FRAMES
    st = [0] * (2 * n)
    st[2 * pre] = st[2 * pre + 1] = int(0.5 * Q)
    q = dict(p, AMNT=127)              # wet only: at 127 the dry is (1 - A), under -60 dB once settled
    L, R = model(st, q, lfo=lfo, gate=gate, rel=rel)
    ir = [a / Q for a in L[pre:]]
    t = rt60(ir)
    seg = int(0.5 * SR)
    tail = [10 * math.log10(sum(v * v for v in ir[i:i + seg]) / seg + 1e-30) for i in range(1, len(ir) - seg, seg)]
    grows = any(b > a + 3 for a, b in zip(tail, tail[1:]) if a > -110)
    pd = pre_samples(p)
    print(f"  {' '.join(f'{k}={p[k]}' for k in NAMES)}")
    print(f"  RT60 {'%.2f s' % t if t else 'n/a (decays past the window)'}; "
          f"peak wet {20 * math.log10(max(abs(v) for v in ir[1:]) + 1e-30):.1f} dBFS"
          f"{'; UNSTABLE: the tail grows (half-second RMS rises by over 3 dB)' if grows else ''}")
    print(f"  tail RMS by half second, dB: {' '.join('%.0f' % v for v in tail)}")
    print(f"  predelay {pd} samples ({1000 * pd / SR:.1f} ms) of the {32 * p['PRE']} PRE asks for"
          f"{' (clamped: SIZE leaves no more)' if pd < 32 * p['PRE'] else ''}")


def selftest():
    """The model against verify_studioverb.model, sample for sample."""
    src = pathlib.Path(__file__).resolve().parents[1] / "verify" / "verify_studioverb.py"
    # only the model is wanted: no build, no dsp_host, no registry (send_probe loads every manifest)
    code = src.read_text().replace("\nmain()\n", "\n").replace("import send_probe  # noqa: E402\n", "send_probe = None\n")
    ns = {"__name__": "studioverb_ref", "__file__": str(src)}
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
    for prm in ([64, 51, 80, 100, 90, 0], [80, 51, 110, 100, 90, 40], [127, 20, 127, 30, 10, 0],
                [64, 51, 80, 100, 90, 0, 1, 40, 100, 30, 60], [80, 51, 110, 100, 90, 40, 1, 90, 127, 0, 20],
                [64, 51, 80, 100, 90, 0, 1, 0, 64, 64, 60, 20], [80, 51, 110, 100, 90, 30, 1, 50, 90, 70, 0, 127]):
        rL, rR = ns["model"](st, prm, 4)       # slots: 0-9 as NAMES, 10 blank, 11 PRE
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
    ap.add_argument("--gate", choices=("module", "old"), default="module",
                    help="module: as built, a desk gate's release, then the tank flushed; old: the 3 ms close")
    ap.add_argument("--release-shift", type=int, default=11, help="the release: gain falls 1/2^N a sample (the module's is 11)")
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
        if k == "MODE":                  # landing on a MODE sets the other knobs, as MODE DEFAULTS does on the panel;
            p.update(mode_view(p[k]))    # a -p after it still wins
            for kv2 in a.param[a.param.index(kv) + 1:]:
                k2, _, v2 = kv2.partition("=")
                if k2.upper() in p:
                    p[k2.upper()] = max(0, min(127, int(v2)))
    sweep = [(None, None)]
    if a.sweep:
        k, _, vs = a.sweep.partition("=")
        k = k.upper()
        if k not in p:
            sys.exit(f"--sweep {a.sweep}: knobs are {', '.join(NAMES)}")
        sweep = [(k, int(v)) for v in vs.split(",")]
    if a.impulse:
        for k, v in sweep:
            impulse_report(dict(p, **({k: v} if k else {})), lfo=a.lfo, gate=a.gate, rel=a.release_shift)
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
        L, R = model(st, q, lfo=a.lfo, gate=a.gate, rel=a.release_shift)
        path = out if k is None else out.with_name(f"{out.stem}_{k}{v}{out.suffix}")
        write_wav(path, L, R)
        print(f"{path}: {' '.join(f'{n}={q[n]}' for n in NAMES)}; predelay {pre_samples(q)} samples")


if __name__ == "__main__":
    main()
