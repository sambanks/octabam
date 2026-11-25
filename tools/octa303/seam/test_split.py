"""v9.1 (25 Nov 2026; code written by Claude): split303 against ref303 with every feature the DSP half now carries --
FM (smoothed), MUFF SOFT/HARD, DIST, DRIV, SWP WHST/SELF, OVDR -- and the record path (hyb.Frame -> hyb.dsp_model)
against ref303's samples.  Also prints the peak of every intermediate the DSP computes (split303.pk), against the
2^23 the exact-integer multiply needs.  usage: test_split.py [runs] [frames]"""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hyb, split303 as S
R, T = hyb.R, hyb.T
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 60
FR = int(sys.argv[2]) if len(sys.argv) > 2 else 300
fails = 0; nsamp = 0; nrec = 0; feat = {'fm': 0, 'muff1': 0, 'muff2': 0, 'dist': 0, 'driv': 0, 'swp<2': 0}
for run in range(RUNS):
    rnd = random.Random(7000 + run)
    kv = lambda: rnd.choice([0, 1, 64, 100, 126, 127, rnd.randint(0, 127)])
    ref, cf, dsp = R.Track(), R.Track(), R.Track()
    df = setup = w = None; code = 0; fresh = 1
    for f in range(FR):
        if f == 0 or rnd.random() < 0.04:
            df = [kv() for _ in range(12)] if rnd.random() < 0.9 else None
            if df and rnd.random() < 0.5: df[1] = rnd.choice([64, 100, 127])          # FM often, and high
            setup = [0, rnd.choice([0, 1]), kv(), kv(), kv() if rnd.random() < 0.5 else 0, kv()]
            code = rnd.choice([0, 1, 2, 3, 4, 5, 6, 7])                             # DIST is bit 1
            w = [0x4000 + rnd.randint(-24, 30) * 256, kv() << 8, kv() << 8, kv() << 8, kv() << 8, rnd.choice([0, 0, 127, kv()]) << 8]
            s = rnd.randint(0, 15) if f else 0
            calls = [(w, False, s), (w, True, 16 - s)]
        else:
            if rnd.random() < 0.08: w = list(w); w[rnd.randint(1, 5)] = kv() << 8
            s = rnd.randint(1, 15) if rnd.random() < 0.3 else 0
            calls = [(w, False, s), (w, False, 16 - s)] if s else [(w, False, 16)]
        fr = hyb.Frame(); exp = []
        for (ww, st_, n) in calls:
            hyb.render_call(cf, ww, st_, code, n, fr, df=df, setup=setup)
            r = R.render_call(ref, ww, st_, code, n, df=df, setup=setup)
            exp += [((x >> 8) & 0xFFFFFF) for x in r] if r is not None else [0] * n
        if cf.latched:
            feat['fm'] += bool(cf.fmq); feat['muff1'] += cf.muff == 1; feat['muff2'] += cf.muff == 2
            feat['dist'] += bool(cf.dist); feat['driv'] += cf.osin != T.DRV_G[0]; feat['swp<2'] += cf.swp < 2
        words = fr.words()
        if words is None: continue
        if fresh: words[1] |= 1; fresh = 0
        got = hyb.dsp_model(dsp, words); nrec += 1
        s0 = words[3] & 0xFF
        if got[s0:] != exp[s0:]:
            fails += 1
            if fails < 5: print('run %d frame %d: record path differs from ref303' % (run, f))
        nsamp += 16 - s0
# split_sample against sample, twin tracks, peaks on
sp = 0
for run in range(RUNS // 2):
    rnd = random.Random(9000 + run); a, b = R.Track(), R.Track()
    df = [rnd.choice([0, 64, 127, rnd.randint(0, 127)]) for _ in range(12)]; df[1] = rnd.choice([0, 127, rnd.randint(1, 127)])
    setup = [0, 0, 64, 0, rnd.choice([0, 127, rnd.randint(0, 127)]), 64]
    w = [0x4000 + rnd.randint(-24, 30) * 256] + [rnd.choice([0, 127, rnd.randint(0, 127)]) << 8 for _ in range(4)] + [127 << 8]
    code = rnd.randint(0, 7)
    for t in (a, b):                                  # a call of 16 sets the knobs (a call of 0 only latches)
        R.render_call(t, w, True, code, 16, df=df, setup=setup)
    for i in range(4000):
        for t in (a, b):
            t.cs -= 1
            if t.cs == 0: t.cs = T.CS; R.ctrl(t)
        x, y = R.sample(a), S.split_sample(b, peaks=True); sp += 1
        if x != y:
            fails += 1; print('split differs, run %d sample %d' % (run, i)); break
print('features (frames):', feat)
print('record path: %d records, %d samples; split: %d samples; %d failures' % (nrec, nsamp, sp, fails))
big = sorted(S.PEAK.items(), key=lambda kv: -kv[1])
print('peaks:', ' '.join('%s=%d%s' % (k, v, '(!)' if v >= 1 << 23 else '') for k, v in big))
sys.exit(1 if fails else 0)
