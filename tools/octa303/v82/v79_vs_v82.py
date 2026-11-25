"""v7.9 and v8.2-P11 side by side on the same frames: every output word compared, cycles per frame, P11 skips.
Usage (worktree root of the v7.9 tree): p11meas79.py A.s B.s [frames]"""
import sys
sys.path.insert(0, 'tools/octa303/sim'); sys.path.insert(0, 'tools/octa303')
import harness as H, o3tables as T
from harness import Rig, SILENCE
A, B = sys.argv[1], sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
def src_from(path):
    s = open(path).read()
    return H._unflag(s.replace('        .include "remix.inc"', H.remix_inc(True).rstrip('\n'), 1))
def W6(cut=64, res=64, env=64, dec=64, acc=0): return [0x4000, cut << 8, res << 8, env << 8, dec << 8, acc << 8]
FPT = 57
def run_seq(f): return (127, 1 + (f // (6 * FPT)) % 16, (f // FPT) % 6, 0, 16, 1)
DF = [64, 30, 64, 64, 64, 64, 0, 0, 1, 2, 0, 0]
def scen(name, su, words, trigs, frames, df=None, seqf=None):
    ra, rb = Rig(src_from(A)), Rig(src_from(B))
    p11 = rb.cpu.labels.get('.Lp11'); rb.cpu.prof = {}
    bad = None; ca = cb = 0; ta = tb = nt = 0
    for f in range(frames):
        outs = []
        for r in (ra, rb):
            r.path(3, '/AUDIO/ACID/KICK.WAV'); r.voice(0, True, 3); r.machine(0, su)
            c0 = r.cpu.cyc
            o = r.call(0, words, 0, 16, f in trigs, SILENCE, df, 1, seqf(f) if seqf else None)
            outs.append((o, r.cpu.cyc - c0))
        if outs[0][0] != outs[1][0] and bad is None: bad = f
        ca += outs[0][1]; cb += outs[1][1]
        if f >= frames - 200: ta += outs[0][1]; tb += outs[1][1]; nt += 1
    hits = rb.cpu.prof.get(p11[1], 0) if p11 else 0
    print('%-36s bit-exact %-22s P11 skips %5.1f%%  cycles/frame all %5.0f -> %5.0f   last 200: %5.0f -> %5.0f' % (
        name, 'YES' if bad is None else 'NO (frame %d)' % bad, 100.0 * hits / (16 * frames), ca / frames, cb / frames, ta / nt, tb / nt), flush=True)
    return bad is None
G = (0, 1) + tuple(T.SETUP_NEUTRAL[2:])
ok = True
ok &= scen('GATE 303 saw, one note', G, W6(), {1}, N, seqf=run_seq)
ok &= scen('GATE 303 sq, dEVILish, one note', (1, 1) + G[2:], W6(cut=127, res=127, env=127, acc=127), {1}, N, df=DF, seqf=run_seq)
ok &= scen('GATE 303 sq RES127 CUT20 ACC127, 2 notes', (1, 1) + G[2:], W6(cut=20, res=127, acc=127), {1, 400}, N, seqf=run_seq)
ok &= scen('no gate, saw high, trig every 16 frames', (0,) + tuple(T.SETUP_NEUTRAL[1:]), W6(127, 127, 127, 64, 127), set(range(1, N, 16)), N, seqf=run_seq)
print('ALL BIT-EXACT' if ok else 'MISMATCH')
