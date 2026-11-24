#!/usr/bin/env python3
"""VERBERATION under dsp_host, against a float model of Clouds' reverb.

    .venv/bin/python3 tools/verify/verify_verberation.py

Builds remix `verberation`, dumps payload A and runs one instance at track 1's
FX2 slot (`-r7 2 -alloc 1`, Y:0x4000). Gates:
  clear     the first 22 calls (the ring is cleared 653 words a call) pass the
            input through untouched
  dry       AMNT 0 is bit-exact dry
  model     an impulse and a noise burst through the module, against a float
            model of the same algorithm (same lengths, the same integer LFO
            phases and offsets, the same parameter laws and smoothing); the
            difference is the 24-bit arithmetic
  tail      the impulse response decays (TIME up -> longer), stays below full scale
  runaway   one impulse at TIME 120 and 127, 10 s: the tail falls by 15 dB or more and never
            rises by 3 dB from one half second to the next (until 5 Nov 2026 the smear LFO was
            bipolar, its reads fed the last tank line back to the input, and at TIME 120 the
            tail grew from -56 dB to -11 dB in 11 s)
  bounds    -guard 14366: no write outside the ring (it ends below 0x3820 of the
            slot, where octabam's window code starts), no stray write
  gate      GATE 40: open during the hold; then a desk gate's release (70-110 ms in, 4 to 25 dB
            under the ungated tail, not a cut); shut after it; the tank empty when it reopens
            (a second impulse, 190 ms after the gate shuts, rings as it does alone); against the float model
  pre       PRE moves the wet onset by 24 PRE samples at every SIZE (SIZE 127 included: the long
            delay gives up the room), against the model; no write outside the ring
  amnt      to 64 the dry is at unity under the wet, at 127 it is gone; against the model
  kill      MODE's field at 127 (the stop kill, kill.s) for 60 blocks: the output is the input
            exactly, and from the kill on a run with a ringing tail is bit-identical to one from silence
  dirty     X and Y filled with garbage before the first call: the output
            from silence is silent
What it cannot see: the real allocator's bases (dsp_host places the FX2 slot by
its own model), the chip's non-power-of-2 modulo with (Rn+Nn) addressing (the
stock code uses small non-power-of-2 moduli, never one this large).
"""
import math, os, pathlib, random, struct, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.chdir(ROOT)
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
REMIX = "verberation"
IMAGE, MEM = "out/mainos_bus.bin", "out/dsp/_verberation_A.mem"
TMP = pathlib.Path("out/_cvgate"); TMP.mkdir(parents=True, exist_ok=True)
FRAMES = 16
CLEAR_CALLS = 22
LEN = [109, 157, 233, 386, 1440, 1776, 2973, 1667, 1449, 4167]
BASE = []
_b = 0
for _l in LEN:
    BASE.append(_b); _b += _l + 1
N = BASE[-1] + LEN[-1]
Q = 1 << 23
def pg2(size=127, lcut=0, mod=64, rate=64, pre=0, mode=1):
    """Page 2's slots 6-11 in order: MODE, LCUT, MOD, RATE, SIZE, PRE. The DSP does not read MODE (MODE DEFAULTS
    applies a mode's knob values on the panel). SIZE 127, LCUT 0, MOD 64, RATE 64, PRE 0 are the constants the
    code had before page 2, exactly."""
    return [mode, lcut, mod, rate, size, pre]


TAIL = pg2()                             # the knob words after GATE
fails = 0


def check(label, ok, detail=""):
    global fails
    fails += 0 if ok else 1
    print(f"  [{'ok' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")


def s24(v):
    v &= 0xFFFFFF
    return v - (1 << 24) if v & 0x800000 else v


def build_dump():
    env = dict(os.environ, REMIX=REMIX, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], env=env, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_verberation: building {REMIX} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    send_probe.dump_mem(IMAGE, MEM, "A")


def host(samples, params, *, mem=MEM, extra=()):
    from remix import registry
    fxid = registry.by_key("VERBERATION").menu.fx2_id
    init, proc = send_probe.entry_points(mem, fxid)
    (TMP / "in.raw").write_bytes(b"".join(struct.pack("<i", s) for s in samples))
    cmd = [HOST, "-mem", mem, "-init", f"{init:x}", "-proc", f"{proc:x}", "-inst", "1", "-r7", "2", "-alloc", "1",
           "-inmask", "1", "-frames", str(FRAMES), "-blocks", str(len(samples) // FRAMES), "-in", str(TMP / "in.raw"),
           "-out", str(TMP / "out.raw"), "-params", ",".join(str(x) for x in params), *extra]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"dsp_host failed:\n{p.stdout}\n{p.stderr}")
    d = (TMP / "out.raw").read_bytes()
    w = struct.unpack(f"<{len(d) // 4}i", d)
    return list(w[0::2])[:len(samples)], list(w[1::2])[:len(samples)], p.stdout + p.stderr


# ---- the model -------------------------------------------------------------
def mulf(a, b):          # the DSP's fractional product, truncated
    return (a * b) >> 23


def parab(phase):
    x = s24(phase)
    t = (Q - 1) - min(abs(x), Q - 1) if abs(x) < Q else 0
    t = (Q - 1) - abs(x)
    return max(-Q, min(Q - 1, (x * t >> 23) * 4))


def model(samples, params, blocks_skip):
    """Float model of Clouds' reverb for the blocks after the clearing."""
    ring = [0.0] * N
    ph1 = ph2 = 0
    amt = gc = krt = kap = klp = 0
    lp1 = lp2 = 0.0
    sz_f = mod_s = lc = pdq = 0          # page 2's smoothed values: SIZE's f, MOD's offset, LCUT's c, PRE (1/256)
    hp1 = hp2 = 0.0
    mode, lcut, mod, rate, size, pre = list(params[6:12]) + pg2()[len(params[6:12]):]
    g_er = 0x500000 if mode == 0 else 0          # ROOM: the input diffuser's output into the wet
    k_t = 0x7FFFFF if mode == 3 else 0           # 80S: the gate keyed on transients
    hall = mode == 2
    p = 0
    env = hold = gs = 0
    hmax = 0x7FFFFF if params[5] == 0 else 2048 + 256 * params[5]
    out_l, out_r = [], []
    def smooth(cur, tgt):
        return cur + ((tgt - cur) >> 4)
    k = [(v << 16) for v in params[:5]]
    for blk in range(len(samples) // 2 // FRAMES):
        if blk < blocks_skip:
            for s in range(FRAMES):
                out_l.append(samples[2 * (blk * FRAMES + s)]); out_r.append(samples[2 * (blk * FRAMES + s) + 1])
            continue
        amt = smooth(amt, k[0])
        W = min(2 * amt, Q - 1) / Q      # AMNT's law: the wet to full by 64, then the dry fades out
        Kd = min(mulf(max(amt - 0x400000, 0), 0x410410) * 4, Q - 1) / Q
        gc = smooth(gc, k[1] >> 3)
        krt = smooth(krt, mulf(k[2], 0x50A3D7) + 0x2CCCCD)
        kap = smooth(kap, mulf(k[3], 0x666666))
        klp = smooth(klp, mulf(k[4], 0x79999A) + 0x066666)
        # page 2, as verberation.asm computes it each block
        sz_f = smooth(sz_f, mulf((127 - size) << 16, 0x6734EE))
        ln = [LEN[j] - mulf(LEN[j], sz_f) for j in range(10)]      # read lengths (lines 4-9 used)
        def wide(v):                     # MOD's and RATE's law: v/256 + max(0, v - 64)/128, Q23
            return ((v << 16) >> 1) + max(0, (v << 16) - 0x400000)
        mod_s = smooth(mod_s, wide(mod) - 0x200000)
        d2 = mulf(4 * (0x061000 - mulf(0x061000, sz_f)), 0x200000 + mod_s)     # the swing, Q12 samples
        # PRE: 24 PRE samples, smoothed in 1/256 samples and rounded, in the long delay's far end past its
        # tap; past what SIZE leaves (m - 2) it takes the room from the long delay (m' = pd + 2)
        pdq = smooth(pdq, (24 * pre) << 8)
        pd = (pdq + 0x80) >> 8
        m9 = mulf(4167, sz_f)
        m9 = max(m9, pd + 2 if pd else 0)
        active = pd != 0
        centre = 4165 - m9 - (d2 >> 12)
        pkw = 4168 - m9                  # the write cell, as an offset into line 9
        inc1, inc2 = mulf(760, wide(rate)), mulf(456, wide(rate))
        u = lcut << 16
        lc = smooth(lc, mulf(mulf(u, u), 0x12866A))
        C = lc / Q
        ph1 = s24(ph1 + inc1 * FRAMES); ph2 = s24(ph2 + inc2 * FRAMES)
        t1 = mulf((parab(ph1) + Q) >> 1, 0x03C000) + 0x00A000     # unipolar, as Clouds' LFO: 10..70
        kint1, fr1 = t1 >> 12, (t1 & 0xFFF) << 11
        t2 = mulf(parab(ph2), d2)
        kint2, fr2 = centre + (t2 >> 12), (t2 & 0xFFF) << 11
        t6 = mulf(-parab(ph2), d2) if hall else 0           # HALL: delay 1 swung in antiphase
        kint6, fr6 = ln[6] - 2 - ((d2 >> 12) if hall else 0) + (t6 >> 12), (t6 & 0xFFF) << 11
        K, G, R, L = kap / Q, gc / Q, krt / Q, klp / Q
        if gs == 0:                      # the gate shut at the block's start: the tank empties
            R = K = 0.0
        def cell(j, kk): return (p - BASE[j] - kk) % N
        def rd(j, kk): return ring[cell(j, kk)]
        def wr_(j, kk, v): ring[cell(j, kk)] = max(-1.0, min(1.0 - 1 / Q, v))
        for s in range(FRAMES):
            i0 = blk * FRAMES + s
            l_in, r_in = samples[2 * i0] / Q, samples[2 * i0 + 1] / Q
            mean_i = (samples[2 * i0] + samples[2 * i0 + 1]) >> 1
            m = min(abs(mean_i), Q - 1)
            env2 = env - (env >> 9)
            env = env2 + max(m - env2, 0)
            trig = env * Q - 2 * env2 * k_t - 0x010000 * Q
            hold = max(hold - 1, 0)
            if hmax == 0x7FFFFF:
                hold = hmax
            if trig > 0:
                hold = hmax
            if hold:                     # a desk gate: open, rise 1/32 a sample
                gs = gs + (((Q - 1) - gs) >> 5)
            else:                        # shut: fall 1/2048 a sample; 0 below 2^-11
                ex = gs * 2047                     # gs - gs/2048, exactly, in 1/2048 LSB
                gs = 0 if ex < 0x001000 * 2048 else ex >> 11
            G_ = gs / Q
            # smear
            a0 = rd(0, kint1); b0 = rd(0, kint1 + 1)
            wr_(0, 100, a0 + (b0 - a0) * fr1 / Q)
            x_in = (l_in + r_in) / 2
            if active:
                wr_(9, pkw, x_in); x_in = rd(9, pkw + pd)
            acc = x_in * G
            for j in range(4):
                r = rd(j, LEN[j] - 1); acc += K * r; wr_(j, 0, acc); acc = r - K * max(-1, min(1, acc))
            apout = acc
            wr_i = lambda j, v: wr_(j, 0, v)
            # first half
            a1 = rd(9, kint2); b1 = rd(9, kint2 + 1)
            x = a1 + (b1 - a1) * fr2 / Q
            acc = apout + x * R
            lp1 += L * (acc - lp1); acc = lp1
            d = acc - hp1; acc = d - C * d; hp1 += C * d
            r = rd(4, ln[4] - 1); acc += -K * r; wr_i(4, acc); acc = r + K * max(-1, min(1, acc))
            r = rd(5, ln[5] - 1); acc += K * r; wr_i(5, acc); acc = r - K * max(-1, min(1, acc))
            wr_i(6, acc)
            if g_er:
                acc += 2 * g_er / Q * apout
            wet = max(-1, min(1, 2 * acc)) * G_
            out_l.append(max(-1, min(1, l_in + 8 * wet * W - l_in * Kd)) * Q)
            # second half
            a6 = rd(6, kint6); b6 = rd(6, kint6 + 1)
            acc = apout + (a6 + (b6 - a6) * fr6 / Q) * R
            lp2 += L * (acc - lp2); acc = lp2
            d = acc - hp2; acc = d - C * d; hp2 += C * d
            r = rd(7, ln[7] - 1); acc += K * r; wr_i(7, acc); acc = r - K * max(-1, min(1, acc))
            r = rd(8, ln[8] - 1); acc += -K * r; wr_i(8, acc); acc = r + K * max(-1, min(1, acc))
            wr_i(9, acc)
            if g_er:
                acc -= 2 * g_er / Q * apout
            wet = max(-1, min(1, 2 * acc)) * G_
            out_r.append(max(-1, min(1, r_in + 8 * wet * W - r_in * Kd)) * Q)
            p = (p + 1) % N
    return out_l, out_r


def snr_db(ref, got):
    num = sum(x * x for x in ref)
    den = sum((x - y) ** 2 for x, y in zip(ref, got))
    return 200.0 if den == 0 else 10 * math.log10(max(num, 1e-30) / den)


def rms_db(x):
    v = sum(s * s for s in x) / max(len(x), 1)
    return -200.0 if v == 0 else 10 * math.log10(v / (Q * Q))


def main():
    build_dump()
    blocks = 3200
    random.seed(11)
    # stereo-interleaved? dsp_host feeds one stream to both channels: mono in, so L == R in
    imp = [0] * (blocks * FRAMES)
    imp[(CLEAR_CALLS + 4) * FRAMES] = int(0.5 * Q)
    for i in range((CLEAR_CALLS + 60) * FRAMES, (CLEAR_CALLS + 60) * FRAMES + 600):
        imp[i] = int(0.3 * Q * (random.random() - 0.5))
    params = [64, 51, 80, 100, 90, 0]
    L, R, _ = host(imp, params + TAIL)
    check(f"clear: the first {CLEAR_CALLS} calls pass the input untouched",
          all(L[i] == imp[i] for i in range(CLEAR_CALLS * FRAMES)))
    L0, R0, _ = host(imp, [0] + params[1:] + TAIL)
    check("dry: AMNT 0 is bit-exact dry", L0 == imp and R0 == imp)
    check("wet: AMNT 64 changes the output after the clearing", L != imp)
    # model: mono input to both channels
    st = []
    for s in imp:
        st += [s, s]
    mL, mR = model(st, params, CLEAR_CALLS)
    n0 = CLEAR_CALLS * FRAMES
    snrL, snrR = snr_db(mL[n0:], L[n0:]), snr_db(mR[n0:], R[n0:])
    check(f"model: left against the float model, {snrL:.1f} dB", snrL > 50)
    check(f"model: right against the float model, {snrR:.1f} dB", snrR > 50)
    check("tail: below full scale", max(abs(x) for x in L + R) < Q - 1)
    t1 = rms_db(L[n0 + 8000:n0 + 12000]); t2 = rms_db(L[n0 + 40000:n0 + 44000])
    check(f"tail: decays ({t1:.1f} dB then {t2:.1f} dB)", t2 < t1 - 6)
    Lh, _, _ = host(imp, [64, 51, 127, 100, 90, 0] + TAIL)
    th = rms_db(Lh[n0 + 40000:n0 + 44000])
    check(f"time: TIME 127 rings longer than TIME 80 ({th:.1f} dB against {t2:.1f} dB)", th > t2)
    # runaway: a long tail must keep falling (the bipolar smear grew it from TIME 94 up)
    sr, seg = 44100, 22050
    rimp = [0] * ((CLEAR_CALLS + 200) * FRAMES + 10 * sr // FRAMES * FRAMES)
    r0 = (CLEAR_CALLS + 200) * FRAMES
    rimp[r0] = int(0.5 * Q)
    for tm in (120, 127):
        Lr, _, _ = host(rimp, [80, 51, tm, 100, 90, 0] + TAIL)
        rr = [rms_db(Lr[i:i + seg]) for i in range(r0 + 1, len(Lr) - seg, seg)]
        rise = max(b - a for a, b in zip(rr, rr[1:]))
        check(f"runaway: TIME {tm}, 10 s: {rr[0]:.0f} dB to {rr[-1]:.0f} dB, largest rise {rise:+.1f} dB",
              rr[-1] < rr[0] - 15 and rise < 3)
    # gate: the wet is held for 2048 + 256 k samples after the input falls quiet, then closed
    gimp = [0] * (blocks * FRAMES)
    gimp[(CLEAR_CALLS + 4) * FRAMES] = int(0.5 * Q)
    t0 = (CLEAR_CALLS + 4) * FRAMES
    gp = [80, 51, 110, 100, 90]
    Lng, _, _ = host(gimp, gp + [0] + TAIL)
    Lg, Rg, _ = host(gimp, gp + [40] + TAIL)
    hold = 2048 + 256 * 40
    pre_ng, pre_g = rms_db(Lng[t0 + 2000:t0 + 8000]), rms_db(Lg[t0 + 2000:t0 + 8000])
    # the envelope needs about 2,200 samples to fall from 0.5 to the threshold before the hold
    # starts; the release then takes about 15,600 samples (gain falling 1/2048 a sample to 2^-11)
    rel0 = t0 + 2200 + hold
    mid_ng, mid_g = rms_db(Lng[rel0 + 3000:rel0 + 5000]), rms_db(Lg[rel0 + 3000:rel0 + 5000])
    post_ng, post_g = rms_db(Lng[rel0 + 17000:rel0 + 21000]), rms_db(Lg[rel0 + 17000:rel0 + 21000])
    check(f"gate: open during the hold ({pre_g:.1f} dB against {pre_ng:.1f} dB without)", abs(pre_g - pre_ng) < 3)
    check(f"gate: a release, not a cut: 70-110 ms into it {mid_g:.1f} dB against {mid_ng:.1f} dB without",
          mid_ng - 25 < mid_g < mid_ng - 4)
    check(f"gate: closed after the release ({post_g:.1f} dB against {post_ng:.1f} dB without)", post_g < post_ng - 30)
    # a shut gate empties the tank: the gain reaches 0 about 16,200 samples into the release, and
    # with the loop gain and the allpass coefficient 0 every line is a plain delay, so the longest
    # path (dap2a, dap2b, del2: 8,092 samples) has flushed 8,500 after that. A second impulse then
    # rings as the same impulse does alone (same moment: the same LFO phases and knob glides), but for
    # the truncation floor (a few LSB, mostly DC)
    t1 = rel0 + 16200 + 8500
    gimp2 = list(gimp); gimp2[t1] = int(0.5 * Q)
    gimp3 = [0] * len(gimp); gimp3[t1] = int(0.5 * Q)
    Lg2, _, _ = host(gimp2, gp + [40] + TAIL)
    Lg3, _, _ = host(gimp3, gp + [40] + TAIL)
    res = rms_db([x - y for x, y in zip(Lg2[t1:t1 + 12000], Lg3[t1:t1 + 12000])])
    check(f"gate: the tank is empty when it reopens (a second hit less the same hit alone: {res:.1f} dBFS)", res < -110)
    stg = []
    for s_ in gimp:
        stg += [s_, s_]
    mgL, _ = model(stg, gp + [40], CLEAR_CALLS)
    sg = snr_db(mgL[n0:], Lg[n0:])
    check(f"gate: left against the float model, {sg:.1f} dB", sg > 50)
    # page 2 away from its defaults, against the model. SIZE's offsets and the long delay's tap are
    # integers in both, so a wrong one is wrong from the first samples on: the first 8,000 must match
    # to 50 dB. Later the tail decays toward the 24-bit truncation floor the float model has not got,
    # and the match falls with it (57 dB to 20 dB over a second with LCUT 40), so the whole render is
    # held to 40 dB.
    p2 = {"SIZE 30": pg2(size=30), "SIZE 0, MOD 127": pg2(size=0, mod=127), "LCUT 90": pg2(lcut=90),
          "MOD 0, RATE 0": pg2(mod=0, rate=0), "MOD 127, RATE 127": pg2(mod=127, rate=127),
          "SIZE 60, LCUT 40, MOD 100, RATE 30": pg2(size=60, lcut=40, mod=100, rate=30)}
    lv = {}
    for name, pg in p2.items():
        Lp, Rp, _ = host(imp, params + pg)
        mpL, mpR = model(st, params + pg, CLEAR_CALLS)
        s8 = min(snr_db(mpL[n0:n0 + 8000], Lp[n0:n0 + 8000]), snr_db(mpR[n0:n0 + 8000], Rp[n0:n0 + 8000]))
        sp = min(snr_db(mpL[n0:], Lp[n0:]), snr_db(mpR[n0:], Rp[n0:]))
        lv[name] = Lp
        check(f"page 2: {name} against the float model, {s8:.1f} dB over 8,000 samples, {sp:.1f} dB whole",
              s8 > 50 and sp > 40)
    late = lambda x: rms_db(x[n0 + 30000:n0 + 40000])
    check(f"page 2: SIZE 30 decays faster than SIZE 127 ({late(lv['SIZE 30']):.1f} dB against {late(L):.1f} dB, 0.7-0.9 s in)",
          late(lv["SIZE 30"]) < late(L) - 6)
    def low_db(x):                       # the tail's energy under about 150 Hz (a 3 ms moving
        w = 128; a0 = n0 + 4000           # average), from after the noise burst: wet only
        s0 = sum(x[a0:a0 + w]); acc = []
        for i in range(a0 + w, n0 + 40000):
            s0 += x[i] - x[i - w]; acc.append(s0 / w)
        return rms_db(acc)
    check(f"page 2: LCUT 90 takes the low end out ({low_db(lv['LCUT 90']):.1f} dB against {low_db(L):.1f} dB under 150 Hz)",
          low_db(lv["LCUT 90"]) < low_db(L) - 6)
    _, _, logp = host(imp[:400 * FRAMES], params + pg2(size=0, mod=127, rate=127), extra=["-guard", str(N), "-guard-shared"])
    check("page 2: SIZE 0, MOD 127: no write outside the ring", "0 stray write regions, 0 CLOBBERING" in logp)
    # PRE: a predelay of 24 PRE samples in the long delay's far end, past its tap. Where SIZE leaves less
    # than pd + 2 words there, the long delay's tap moves in to make the room: PRE works at every SIZE
    pim = [0] * (blocks * FRAMES)
    pt0 = (CLEAR_CALLS + 200) * FRAMES   # after the knobs (SIZE's f and PRE's glide) have settled
    pim[pt0] = int(0.5 * Q)
    pst = [v_ for s_ in pim for v_ in (s_, s_)]
    wetp = [127, 51, 80, 100, 90, 0]
    def onset(x):                        # the first wet sample after the impulse
        return next(i for i in range(pt0 + 1, len(x)) if abs(x[i]) > 64) - pt0
    on = {}
    for size, pre in ((60, 0), (60, 40), (90, 0), (90, 127), (127, 0), (127, 127)):
        Lq, Rq, _ = host(pim, wetp + pg2(size=size, pre=pre))
        on[(size, pre)] = (onset(Lq), Lq, Rq)
    for size, pre in ((60, 40), (127, 127)):
        mq, _ = model(pst, wetp + pg2(size=size, pre=pre), CLEAR_CALLS)
        sq = snr_db(mq[pt0:pt0 + 8000], on[(size, pre)][1][pt0:pt0 + 8000])
        check(f"pre: SIZE {size}, PRE {pre} against the float model, {sq:.1f} dB over 8,000 samples", sq > 50)
    # the onset is a threshold crossing on a smeared, modulated response: +-2 samples of slack
    for size, pre in ((60, 40), (90, 127), (127, 127)):
        sh = on[(size, pre)][0] - on[(size, 0)][0]
        check(f"pre: PRE {pre} at SIZE {size} moves the wet onset by {sh} samples (24 x {pre} = {24 * pre:,})",
              abs(sh - 24 * pre) <= 2)
    _, _, logq = host(imp[:400 * FRAMES], params + pg2(size=0, pre=127), extra=["-guard", str(N), "-guard-shared"])
    check("pre: SIZE 0, PRE 127: no write outside the ring", "0 stray write regions, 0 CLOBBERING" in logq)
    _, _, logq = host(imp[:400 * FRAMES], params + pg2(size=127, mod=127, pre=127), extra=["-guard", str(N), "-guard-shared"])
    check("pre: SIZE 127, MOD 127, PRE 127: no write outside the ring", "0 stray write regions, 0 CLOBBERING" in logq)
    # AMNT's law: to 64 the dry stays at unity, at 127 it is gone. GAIN 0 sends nothing into the tank, so
    # the output is the dry alone. Against the model at 30 and 127.
    for amnt in (30, 64):
        La, Ra, _ = host(imp, [amnt, 0] + params[2:] + TAIL)
        check(f"amnt: AMNT {amnt} keeps the dry at unity (GAIN 0: the output is the input exactly)",
              La == imp and Ra == imp)
    La, _, _ = host(pim, [127, 0] + params[2:] + TAIL)     # its impulse comes after AMNT's glide has settled
    check(f"amnt: AMNT 127 takes the dry out (GAIN 0: {La[pt0]} where the input is {pim[pt0]}, under -96 dB)",
          abs(La[pt0]) < pim[pt0] >> 16)
    for amnt in (30, 127):
        La, Ra, _ = host(imp, [amnt] + params[1:] + TAIL)
        mL_, mR_ = model(st, [amnt] + params[1:], CLEAR_CALLS)
        sa = min(snr_db(mL_[n0:], La[n0:]), snr_db(mR_[n0:], Ra[n0:]))
        check(f"amnt: AMNT {amnt} against the float model, {sa:.1f} dB", sa > 50)
    # the stop kill: MODE's field at 127 (kill.s writes it while the kill holds) cuts to dry and clears the
    # state and the ring. A run with a ringing tail and a run with silence before the kill are bit-identical
    # from the kill on, and the output is the input exactly while it holds.
    kb, kn = CLEAR_CALLS + 400, 60       # the kill's first block, and its length in blocks
    kf = TMP / "kill.txt"
    live, dead = params + TAIL, params + [127] + TAIL[1:]
    kf.write_text(f"0,{','.join(map(str, live))}\n{kb},{','.join(map(str, dead))}\n"
                  f"{kb + kn},{','.join(map(str, live))}\n")
    kin = list(imp)
    for i in range(kb * FRAMES, (kb + 10) * FRAMES):
        kin[i] = int(0.2 * Q * (random.random() - 0.5))
    k2 = (kb + kn + 30) * FRAMES
    kin[k2] = int(0.5 * Q)
    quiet = [0] * (kb * FRAMES) + kin[kb * FRAMES:]
    ext = ["-paramfile", str(kf)]
    Lk, Rk, _ = host(kin, live, extra=ext)
    Lq_, Rq_, _ = host(quiet, live, extra=ext)
    a0 = kb * FRAMES
    check("kill: the tail before the kill rings (it is there to be cut)", rms_db(Lk[a0 - 4000:a0]) > -100)
    check("kill: the output is the input exactly while the kill holds",
          Lk[a0:(kb + kn) * FRAMES] == kin[a0:(kb + kn) * FRAMES] and Rk[a0:(kb + kn) * FRAMES] == kin[a0:(kb + kn) * FRAMES])
    check("kill: after it, a hit rings exactly as it does from silence (the tank and the state are clear)",
          Lk[a0:] == Lq_[a0:] and Rk[a0:] == Rq_[a0:])
    check("kill: and the reverb is back after it", rms_db(Lk[k2 + 2000:k2 + 6000]) > -90)
    # MODE: each mode is its own algorithm, against the model. ROOM adds early reflections (three taps a side
    # off the input line), HALL swings delay 1 as well as delay 2, 80S keys the gate on transients.
    for mode, name in ((0, "ROOM"), (2, "HALL"), (3, "80S")):
        pgm = pg2(mode=mode, mod=127) if mode == 2 else pg2(mode=mode)
        gk = [40] if mode == 3 else [0]
        Lm, Rm, _ = host(imp, params[:5] + gk + pgm)
        mmL, mmR = model(st, params[:5] + gk + pgm, CLEAR_CALLS)
        s8 = min(snr_db(mmL[n0:n0 + 8000], Lm[n0:n0 + 8000]), snr_db(mmR[n0:n0 + 8000], Rm[n0:n0 + 8000]))
        sw = min(snr_db(mmL[n0:], Lm[n0:]), snr_db(mmR[n0:], Rm[n0:]))
        check(f"mode: {name} against the float model, {s8:.1f} dB over 8,000 samples, {sw:.1f} dB whole",
              s8 > 50 and sw > 40)
    early = lambda x: rms_db(x[pt0 + 100:pt0 + 900])           # 2 to 20 ms after the impulse
    Lr_, _, _ = host(pim, wetp + pg2(mode=0, size=35))
    Lp_, _, _ = host(pim, wetp + pg2(mode=1, size=35))
    check(f"mode: ROOM's early reflections ({early(Lr_):.1f} dB against PLATE's {early(Lp_):.1f} dB, 2-20 ms in)",
          early(Lr_) > early(Lp_) + 6)
    _, _, logm = host(imp[:400 * FRAMES], params + pg2(mode=2, size=0, mod=127, rate=127), extra=["-guard", str(N), "-guard-shared"])
    check("mode: HALL, SIZE 0, MOD 127: no write outside the ring", "0 stray write regions, 0 CLOBBERING" in logm)
    # 80S's key: a hit, then steady noise that never goes quiet. Keyed on level (PLATE with GATE) the gate
    # stays open on the noise; keyed on the hit (80S) it shuts after the hold and the release
    busy = [0] * (blocks * FRAMES)
    b0 = (CLEAR_CALLS + 100) * FRAMES
    busy[b0] = int(0.6 * Q)
    for i in range(b0 + 1, len(busy)):
        busy[i] = int(0.1 * Q * (random.random() - 0.5))
    bp = [127, 51, 100, 100, 90, 10]
    Lb1, _, _ = host(busy, bp + pg2(mode=1))
    Lb3, _, _ = host(busy, bp + pg2(mode=3))
    win = lambda x: rms_db(x[b0 + 44100:b0 + 44100 + 8000])
    check(f"mode: 80S shuts on steady noise after a hit ({win(Lb3):.1f} dB), the level key stays open ({win(Lb1):.1f} dB)",
          win(Lb3) < win(Lb1) - 40)
    bst = [v_ for s_ in busy for v_ in (s_, s_)]
    mb3, _ = model(bst, bp + pg2(mode=3), CLEAR_CALLS)
    sb = snr_db(mb3[n0:], Lb3[n0:])
    check(f"mode: 80S on the busy input against the float model, {sb:.1f} dB", sb > 40)
    # bounds
    _, _, log = host(imp[:200 * FRAMES], params + TAIL, extra=["-guard", str(N), "-guard-shared"])
    check(f"bounds: -guard {N}, no write outside the ring", "0 stray write regions, 0 CLOBBERING" in log, log.strip().splitlines()[-1][:100] if log.strip() else "")
    # dirty: garbage in X (state block) and Y (the ring), silent input
    data = pathlib.Path(MEM).read_bytes()
    body, term = data[:-9], data[-9:]
    body += struct.pack("<BII", 1, 0x6200, 0x100) + struct.pack("<I", 0x5A5A5A) * 0x100
    body += struct.pack("<BII", 2, 0x4000, 0x4000) + struct.pack("<I", 0x320080) * 0x4000
    dm = TMP / "dirty.mem"; dm.write_bytes(body + term)
    z = [0] * (200 * FRAMES)
    Ld, Rd, _ = host(z, params + TAIL, mem=str(dm))
    check("dirty: garbage state and ring, silent input, silent output", not any(Ld) and not any(Rd))
    print(f"verify_verberation: {'PASS' if not fails else f'FAIL ({fails})'}")
    sys.exit(1 if fails else 0)


main()
