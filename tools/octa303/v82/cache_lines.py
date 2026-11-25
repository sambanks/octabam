"""Distinct 16-byte data lines one 16-sample OCTA303 call touches (by region), mean over 48 frames.
A cold-cache upper bound on its data misses. Usage (worktree root): lines.py name=path ..."""
import sys
sys.path.insert(0, 'tools/octa303/sim'); sys.path.insert(0, 'tools/octa303')
import harness as H, o3tables as T, cfsim
def src_from(path):
    s = open(path).read()
    return H._unflag(s.replace('        .include "remix.inc"', H.remix_inc(True).rstrip('\n'), 1))
touched = set()
r0, w0 = cfsim.Mem.r, cfsim.Mem.w
def r(self, a, sz): touched.add(a >> 4); return r0(self, a, sz)
def w(self, a, sz, v): touched.add(a >> 4); return w0(self, a, sz, v)
cfsim.Mem.r, cfsim.Mem.w = r, w
DF = [64, 30, 64, 64, 64, 64, 0, 0, 1, 2, 0, 0]
def W(c, rs, e, acc=127): return [c << 8, rs << 8, e << 8, 64 << 8, 0, acc << 8]
def region(l):
    a = l << 4
    if cfsim.TEXT_DATA <= a < cfsim.DATA_BASE: return 'tables'
    if cfsim.BSS_BASE <= a < cfsim.BSS_BASE + 0x1000000: return 'state'
    if cfsim.DATA_BASE <= a < cfsim.BSS_BASE: return 'data'
    return 'other'
for arg in sys.argv[1:]:
    name, path = arg.split('=')
    src = src_from(path)
    for cname, wave, w, df in (('saw low', 0, W(32, 32, 32), None), ('saw high', 0, W(127, 127, 127), None),
                               ('sq high+dEV', 1, W(127, 127, 127), DF)):
        rig = H.Rig(src); cpu = rig.cpu
        su = (wave,) + tuple(T.SETUP_NEUTRAL[1:]); rig.path(3, '/AUDIO/x.wav'); rig.voice(0, True, 3); rig.machine(0, su, sign=True)
        tot = {}; worst = 0; allt = set()
        for f in range(48):
            touched.clear()
            rig.call(0, w, 0, 16, f % 16 == 0, H.SILENCE, df, 1)
            worst = max(worst, len(touched)); allt |= touched
            for l in touched: k = region(l); tot[k] = tot.get(k, 0) + 1
        print('%-6s %-12s lines/call mean %s  worst %d  over 48 calls %d (%d KB)' % (name, cname,
              ' '.join('%s %.0f' % (k, v / 48) for k, v in sorted(tot.items())), worst, len(allt), len(allt) * 16 // 1024), flush=True)
