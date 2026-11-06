#!/usr/bin/env python3
"""STUDIO VERB under dsp_host, against a float model of Clouds' reverb.

    .venv/bin/python3 tools/verify/verify_studioverb.py

Builds remix `studioverb`, dumps payload A and runs one instance at track 1's
FX2 slot (`-r7 2 -alloc 1`, Y:0x4000). Gates:
  clear     the first 77 calls (the ring is cleared 206 words a call) pass the
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
  bounds    -guard 15862: no write outside the ring (the top 256 words of the
            slot stay clear for the mailbox and LOAD METER), no stray write
  gate      GATE 40: open during the hold; then a desk gate's release (70-110 ms in, 4 to 25 dB
            under the ungated tail, not a cut); shut after it; the tank empty when it reopens
            (a second impulse, 190 ms after the gate shuts, rings as it does alone); against the float model
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
REMIX = "studioverb"
IMAGE, MEM = "out/mainos_bus.bin", "out/dsp/_studioverb_A.mem"
TMP = pathlib.Path("out/_cvgate"); TMP.mkdir(parents=True, exist_ok=True)
FRAMES = 16
CLEAR_CALLS = 77
LEN = [109, 157, 233, 386, 1600, 1973, 3303, 1852, 1610, 4630]
BASE = []
_b = 0
for _l in LEN:
    BASE.append(_b); _b += _l + 1
N = BASE[-1] + LEN[-1]
Q = 1 << 23
PAGE2 = [127, 0, 64, 64]                 # SIZE LCUT MOD RATE defaults: today's sound exactly
TAIL = PAGE2 + [0, 0]                    # the knob words after GATE, as a Part with the defaults holds them
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
        sys.exit(f"verify_studioverb: building {REMIX} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    send_probe.dump_mem(IMAGE, MEM, "A")


def host(samples, params, *, mem=MEM, extra=()):
    from remix import registry
    fxid = registry.by_key("STUDIO VERB").menu.fx2_id
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
    sz_f = mod_s = lc = 0                # page 2's smoothed values: SIZE's f, MOD's offset, LCUT's c
    hp1 = hp2 = 0.0
    size, lcut, mod, rate = (list(params[6:10]) + PAGE2[len(params[6:10]):])
    pre = params[11] if len(params) > 11 else 0
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
        gc = smooth(gc, k[1] >> 3)
        krt = smooth(krt, mulf(k[2], 0x50A3D7) + 0x2CCCCD)
        kap = smooth(kap, mulf(k[3], 0x666666))
        klp = smooth(klp, mulf(k[4], 0x79999A) + 0x066666)
        # page 2, as studioverb.asm computes it each block
        sz_f = smooth(sz_f, mulf((127 - size) << 16, 0x6734EE))
        ln = [LEN[j] - mulf(LEN[j], sz_f) for j in range(10)]      # read lengths (lines 4-9 used)
        mod_s = smooth(mod_s, (mod << 16) - 0x400000)
        d2 = mulf(2 * (0x061000 - mulf(0x061000, sz_f)), 0x400000 + mod_s)     # the swing, Q12 samples
        centre = ln[9] - 2 - (d2 >> 12)
        # PRE: in the long delay's far end, past its tap; m - 2 words of room, none at SIZE 127
        m9 = mulf(4630, sz_f)
        pd = min(32 * pre, max(0, m9 - 2))
        pkw = 4631 - m9                  # the write cell, as an offset into line 9
        inc1, inc2 = mulf(380, rate << 16), mulf(228, rate << 16)
        u = lcut << 16
        lc = smooth(lc, mulf(mulf(u, u), 0x12866A))
        C = lc / Q
        ph1 = s24(ph1 + inc1 * FRAMES); ph2 = s24(ph2 + inc2 * FRAMES)
        t1 = mulf((parab(ph1) + Q) >> 1, 0x03C000) + 0x00A000     # unipolar, as Clouds' LFO: 10..70
        kint1, fr1 = t1 >> 12, (t1 & 0xFFF) << 11
        t2 = mulf(parab(ph2), d2)
        kint2, fr2 = centre + (t2 >> 12), (t2 & 0xFFF) << 11
        K, G, R, L = kap / Q, gc / Q, krt / Q, klp / Q
        if gs == 0:                      # the gate shut at the block's start: the tank empties
            R = K = 0.0
        A = amt / Q
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
            hold = max(hold - 1, 0)
            if hmax == 0x7FFFFF:
                hold = hmax
            if env - 0x010000 > 0:
                hold = hmax
            if hold:                     # a desk gate: open, rise 1/32 a sample
                gs = gs + (((Q - 1) - gs) >> 5)
            else:                        # shut: fall 1/2048 a sample; 0 below 2^-11
                gs = gs - (gs >> 11)
                if gs - 0x001000 < 0:
                    gs = 0
            G_ = gs / Q
            # smear
            a0 = rd(0, kint1); b0 = rd(0, kint1 + 1)
            wr_(0, 100, a0 + (b0 - a0) * fr1 / Q)
            x_in = (l_in + r_in) / 2
            if pd:
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
            wr_i(6, acc); wet = max(-1, min(1, 2 * acc)) * G_
            out_l.append(max(-1, min(1, l_in + (8 * wet - l_in) * A)) * Q)
            # second half
            acc = apout + rd(6, ln[6] - 1) * R
            lp2 += L * (acc - lp2); acc = lp2
            d = acc - hp2; acc = d - C * d; hp2 += C * d
            r = rd(7, ln[7] - 1); acc += K * r; wr_i(7, acc); acc = r - K * max(-1, min(1, acc))
            r = rd(8, ln[8] - 1); acc += -K * r; wr_i(8, acc); acc = r + K * max(-1, min(1, acc))
            wr_i(9, acc); wet = max(-1, min(1, 2 * acc)) * G_
            out_r.append(max(-1, min(1, r_in + (8 * wet - r_in) * A)) * Q)
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
    p2 = {"SIZE 30": [30, 0, 64, 64], "SIZE 0, MOD 127": [0, 0, 127, 64], "LCUT 90": [127, 90, 64, 64],
          "MOD 0, RATE 0": [127, 0, 0, 0], "MOD 127, RATE 127": [127, 0, 127, 127],
          "SIZE 60, LCUT 40, MOD 100, RATE 30": [60, 40, 100, 30]}
    lv = {}
    for name, pg in p2.items():
        Lp, Rp, _ = host(imp, params + pg + [0, 0])
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
    _, _, logp = host(imp[:400 * FRAMES], params + [0, 0, 127, 127, 0, 0], extra=["-guard", str(N), "-guard-shared"])
    check("page 2: SIZE 0, MOD 127: no write outside the ring", "0 stray write regions, 0 CLOBBERING" in logp)
    # PRE: a predelay in the long delay's unread far end (room = m - 2 words, m = 4630 f), so it
    # clamps to what SIZE leaves and is nothing at SIZE 127
    pim = [0] * (blocks * FRAMES)
    pt0 = (CLEAR_CALLS + 200) * FRAMES   # after the knobs (SIZE's f included) have settled
    pim[pt0] = int(0.5 * Q)
    pst = [v_ for s_ in pim for v_ in (s_, s_)]
    wetp = [127, 51, 80, 100, 90, 0]
    def onset(x):                        # the first wet sample after the impulse
        return next(i for i in range(pt0 + 1, len(x)) if abs(x[i]) > 64) - pt0
    def room(size):                      # the model's arithmetic for the settled f
        f = mulf((127 - size) << 16, 0x6734EE)
        return max(0, mulf(4630, f) - 2)
    on = {}
    for size, pre in ((60, 0), (60, 40), (90, 127), (127, 0), (127, 127)):
        Lq, Rq, _ = host(pim, wetp + [size, 0, 64, 64, 0, pre])
        on[(size, pre)] = (onset(Lq), Lq, Rq)
    mq, _ = model(pst, wetp + [60, 0, 64, 64, 0, 40], CLEAR_CALLS)
    sq = snr_db(mq[pt0:pt0 + 8000], on[(60, 40)][1][pt0:pt0 + 8000])
    check(f"pre: SIZE 60, PRE 40 against the float model, {sq:.1f} dB over 8,000 samples", sq > 50)
    sh = on[(60, 40)][0] - on[(60, 0)][0]
    # the onset is a threshold crossing on a smeared, modulated response: +-2 samples of slack
    check(f"pre: PRE 40 at SIZE 60 moves the wet onset by {sh} samples (32 x 40 = 1,280)", abs(sh - 1280) <= 2)
    sh90 = on[(90, 127)][0] - on[(127, 0)][0]
    check(f"pre: PRE 127 at SIZE 90 is clamped to the room, {room(90)} samples (onset moved {sh90})",
          abs(sh90 - room(90)) <= 2 and room(90) < 32 * 127)
    check("pre: at SIZE 127 there is no room, and PRE 127 is bit-exact PRE 0",
          on[(127, 127)][1] == on[(127, 0)][1] and on[(127, 127)][2] == on[(127, 0)][2])
    _, _, logq = host(imp[:400 * FRAMES], params + [0, 0, 64, 64, 0, 127], extra=["-guard", str(N), "-guard-shared"])
    check("pre: SIZE 0, PRE 127: no write outside the ring", "0 stray write regions, 0 CLOBBERING" in logq)
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
    print(f"verify_studioverb: {'PASS' if not fails else f'FAIL ({fails})'}")
    sys.exit(1 if fails else 0)


main()
