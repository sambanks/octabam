"""Instructions and cycle floor per 16-sample OCTA303 call, worst over 48 frames, for knob settings.
Usage (from a worktree root): python3 grid.py name=path/to/octa303.s ..."""
import sys
sys.path.insert(0, 'tools/octa303/sim'); sys.path.insert(0, 'tools/octa303')
import harness as H, o3tables as T
def src_from(path):
    s = open(path).read()
    return H._unflag(s.replace('        .include "remix.inc"', H.remix_inc(True).rstrip('\n'), 1))
DF = [64, 30, 64, 64, 64, 64, 0, 0, 1, 2, 0, 0]      # dEVILish as in cost3.py (FM+MUFF)
DFHI = [127]*6 + [127, 127, 1, 2, 127, 127]          # dEVILish every knob high
def W(cut, res, env, acc=127): return [cut << 8, res << 8, env << 8, 64 << 8, 0, acc << 8]
CASES = [('low 32/32/32', W(32,32,32), None), ('mid 64', W(64,64,64), None),
         ('high 127', W(127,127,127), None), ('high+dEV', W(127,127,127), DF), ('high+dEVhi', W(127,127,127), DFHI)]
srcs = [a.split('=') for a in sys.argv[1:]]
for name, path in srcs:
    src = src_from(path)
    for wave in (0, 1):
        for cname, w, df in CASES:
            rig = H.Rig(src); cpu = rig.cpu
            su = (wave,) + tuple(T.SETUP_NEUTRAL[1:]); rig.path(3, '/AUDIO/x.wav'); rig.voice(0, True, 3); rig.machine(0, su, sign=True)
            worst_i = worst_c = tot_i = 0; peak = 0
            for f in range(48):
                i0, c0 = cpu.icount, getattr(cpu, 'cyc', 0)
                L, R = rig.call(0, w, 0, 16, f % 16 == 0, H.SILENCE, df, 1)
                di, dc = cpu.icount - i0, getattr(cpu, 'cyc', 0) - c0
                worst_i = max(worst_i, di); worst_c = max(worst_c, dc); tot_i += di
                for v in L: v = v - (1 << 32) if v >= 1 << 31 else v; peak = max(peak, abs(v))
            print('%-7s %s %-12s instr worst %6d mean %6d  cyc floor worst %6d  peak %08x' % (
                name, 'sq ' if wave else 'saw', cname, worst_i, tot_i // 48, worst_c, peak), flush=True)
