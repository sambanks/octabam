"""The hybrid's ColdFire half (octa303.s built with O3_SEAM = 1) in cfsim: every frame's record, halfword for halfword,
against hyb.py's model, and the samples the DSP half makes of it (hyb.dsp_model) against ref303 (coordination,
19 Nov 2026; code written by Claude).  v9.1 (25 Nov 2026): every voice is the seam's (FM, MUFF, DIST and DRIV too), so the sound of every frame
is compared with ref303; fm_toggle switches FM, MUFF and DRIV within notes (FM's KEEP pieces).
usage (worktree root): python3 tools/octa303/seam/test_seam_cf.py [frames]"""
import os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'sim'))
import harness as H
import hyb
R, T = hyb.R, hyb.T
FRAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 120
REC = 0x80001c90                     # + (ping & 1) * 0xa80 + 336 * track; the rig's ping argument is even
fails = []
def W(tune=0, cut=64, res=64, env=64, dec=64, acc=0):
    return [0x4000 + tune * 256, cut << 8, res << 8, env << 8, dec << 8, acc << 8]

def check(name, ok, detail=''):
    print('%-4s %s %s' % ('ok' if ok else 'FAIL', name, detail))
    if not ok: fails.append(name)

def record(rig, track):
    m = rig.cpu.mem
    return [m.r(REC + 336 * track + 2 * i, 'w') for i in range(84)]

def run(script, track=0, seam=True):
    """script: frames (words, start_at or None, code, df, setup).  The ColdFire in cfsim against hyb.Voice (the
    model of the same code) on every frame -- the record halfword for halfword, the header's samples -- and the
    model's sound (records through hyb.dsp_model, ColdFire frames as they are) against ref303 where the voice never
    leaves the seam.  Returns (samples, records, first problem or None)."""
    rig = H.Rig(H.source(True, seam)); ref, dsp, mv = R.Track(), R.Track(), hyb.Voice()
    nrec = 0; n = 0; pure = True
    for f, (w, start_at, code, df, su) in enumerate(script):
        rig.path(3, '/AUDIO/ACID/X.WAV'); rig.voice(track, True, 3)
        rig.machine(track, su, sign=True)
        calls = [(0, 16)] if not start_at else [(0, start_at), (start_at, 16)]
        exp = []; cf = []; mod = []
        rig.cpu.mem.w(REC + 336 * track, 'w', 0)                 # the stock record's first half (never $a303)
        for (a, b) in calls:
            last = b == 16; stb = start_at is not None
            L, Rr = rig.call(track, w, a, b, stb, H.SILENCE, df, 1)
            c = min(su[0], 7) if (last and stb) else -1
            r = R.render_call(ref, w, last and stb, c, b - a, True, df, last=last, seq=None, setup=su)
            m = mv.call(w, last and stb, c, b - a, df, su, last=last, frame_start=(a == 0))
            exp += [0] * (b - a) if r is None else r
            mod += [0] * (b - a) if m is None else m
            if not seam: mod = exp[:] if len(exp) == len(mod) else mod
            cf += L
        want = mv.frame_end() if seam else None
        words = record(rig, track)
        if seam and not hyb.hybrid_ok(mv.st) and mv.st.latched: pure = False
        if words[0] == hyb.SIG0:
            nrec += 1
            if want is None: return n, nrec, 'frame %d: a record the model did not write' % f
            live = list(range(4 + hyb.PIECE * (want[3] >> 8))) + list(range(hyb.W_U + 2 * (want[3] & 0xFF), hyb.W_U + 32))
            if any(words[k] != want[k] for k in live):         # the halves the DSP reads (the rest is the slot's)
                i = next(k for k in live if words[k] != want[k])
                return n, nrec, 'frame %d: record half %d = %04x, model %04x' % (f, i, words[i], want[i])
            out = hyb.dsp_model(dsp, words)
            s = words[3] & 0xFF
            snd = [0] * s + [(v << 8) & 0xFFFFFFFF for v in out[s:]]     # the DSP writes silence before start
        else:
            if want is not None: return n, nrec, 'frame %d: no record, the model wrote one' % f
            snd = [x & 0xFFFFFFFF for x in mod]
        if [x & 0xFFFFFFFF for x in cf] != [x & 0xFFFFFFFF for x in mod]:
            return n, nrec, 'frame %d: the header samples differ from the model' % f
        if pure and snd != [x & 0xFFFFFFFF for x in exp]:
            return n, nrec, 'frame %d: the sound differs from ref303' % f
        n += 16
    return n, nrec, None

def scen(seed, frames, devil=False, mix=False):
    rnd = random.Random(seed); sc = []; w = W(); df = None
    su = [0, 0, 64, 0, 0, 64]
    for f in range(frames):
        start = None
        if f == 0 or rnd.random() < 0.05:
            start = rnd.choice([0, 0, 0, rnd.randint(1, 15)])
            w = W(rnd.randint(-12, 24), rnd.randint(0, 127), rnd.randint(0, 127), rnd.randint(0, 127),
                    rnd.randint(0, 127), rnd.choice([0, 0, 64, 127]))
            su = [rnd.choice([0, 1, 4, 5]) if not mix else rnd.choice([0, 1, 2, 3, 4, 5]), 0,
                  rnd.randint(0, 127), rnd.randint(0, 127), 0 if not mix or rnd.random() < 0.7 else rnd.randint(1, 127),
                  rnd.randint(0, 127)]
        elif rnd.random() < 0.03:
            w = list(w); w[0] = 0x4000 + rnd.randint(-12, 24) * 256
        if devil and rnd.random() < 0.05:
            df = None if rnd.random() < 0.2 else [rnd.choice([0, 1, 2, 3, 25, 50, 64, 100, 127, rnd.randint(0, 127)]) for _ in range(12)]
            if df is not None and not mix: df[1] = df[9] = 0
        sc.append((w, start, 0, df, su))
    return sc

def fm_toggle(seed, frames):
    """v9.1: FM, MUFF and DRIV switched on and off inside held notes, often between control steps (KEEP pieces)"""
    rnd = random.Random(seed); sc = []; df = [64] * 12; df[7] = df[8] = df[10] = df[11] = 0; df[1] = 127
    su = [0, 0, 64, 0, 0, 64]; w = W(0, 70, 110, 90, 60, 64)
    for f in range(frames):
        start = rnd.randint(1, 15) if f == 0 else rnd.choice([0, rnd.randint(1, 15)]) if rnd.random() < 0.03 else None
        if start is not None: su = list(su); su[0] = rnd.choice([0, 1, 2, 3])       # WAVE (+D: DIST)
        if rnd.random() < 0.2:
            df = list(df); df[1] = 0 if df[1] else rnd.choice([64, 127]); df[9] = rnd.choice([0, 0, 1, 2])
        if rnd.random() < 0.1: su = list(su); su[4] = rnd.choice([0, 0, 127])
        sc.append((w, start, 0, df, su))
    return sc

for nm, kw in (('saw_square', {}), ('devilish_smooth', {'devil': True}), ('mixed_modes', {'devil': True, 'mix': True})):
    tot = 0; recs = 0; bad = None
    for seed in range(3):
        n, nr, mm = run(scen(seed * 17 + len(nm), FRAMES, **kw))
        tot += n; recs += nr
        if mm: bad = 'seed %d: %s' % (seed, mm); break
    check('seam_' + nm, bad is None, ('%d samples, %d records' % (tot, recs)) if bad is None else bad)
tot = 0; recs = 0; bad = None
for seed in range(3):
    n, nr, mm = run(fm_toggle(seed + 40, FRAMES))
    tot += n; recs += nr
    if mm: bad = 'seed %d: %s' % (seed, mm); break
check('seam_fm_toggle', bad is None, ('%d samples, %d records' % (tot, recs)) if bad is None else bad)
# review 19 Nov: a frame whose first call is hybrid and last is not (a START of a DIST note at 11), then a START of
# a saw note at 5 whose first call is the ColdFire's: the pieces of the first must not reach the second's record
sv = [0, 0, 64, 0, 0, 64]; sd = [2, 0, 64, 0, 0, 64]
st_sc = [(W(0, 60, 90, 80, 50), 0, 0, None, sv)] + [(W(0, 60, 90, 80, 50), None, 0, None, sv)] * 6 + \
        [(W(3, 60, 90, 80, 50), 11, 0, None, sd), (W(3, 60, 90, 80, 50), 5, 0, None, sv)] + \
        [(W(3, 60, 90, 80, 50), None, 0, None, sv)] * 6
n, nr, mm = run(st_sc)
check('seam_stale_pieces_after_a_coldfire_frame', mm is None, '%d samples, %d records' % (n, nr) if mm is None else mm)
n, nr, mm = run(scen(5, FRAMES), seam=False)
check('no_seam_build_unchanged', mm is None and nr == 0, '%d samples' % n if mm is None else mm)
print('test_seam_cf: %s' % ('OK' if not fails else '%d FAILED' % len(fails)))
sys.exit(1 if fails else 0)
