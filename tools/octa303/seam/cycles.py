"""Chip cycles of the hybrid's DSP half on traced frames: sam/main's tools/build/interlock_scan.py (Table A-1 plus the
A.2 / 3.5 stalls; a model from the manual, about 3 % over the unit on its measured cases, not a measurement) priced
over the PCs o3hhost executed (O3H_TRACE) from the seam's jsr to the continuation.
usage (worktree root): cycles.py interlock_scan.py placed.bin org trace.txt"""
import importlib.util, pathlib, statistics, sys
spec = importlib.util.spec_from_file_location('ils', sys.argv[1]); ils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ils)
ils.DIS = pathlib.Path('vendor/dsp56300/build/source/disassemble/dsp56kDisassemble')
b = pathlib.Path(sys.argv[2]).read_bytes(); org = int(sys.argv[3], 16)
p = {org + i // 3: b[i] | b[i + 1] << 8 | b[i + 2] << 16 for i in range(0, len(b) - 2, 3)}
seam = 0x39c if org > 0x1100 else 0x1a2
p[seam], p[seam + 1] = 0x0bf080, org
rows = []
for line in open(sys.argv[4]):
    tok = line.split(); pcs = [int(x, 16) for x in tok[2:]]
    lo = min(pcs)
    ins = {}
    ins.update(ils.decode({k: v for k, v in p.items() if k >= org}, [x for x in pcs if x >= org], org))
    ins[seam] = ('jsr >$%x' % org, 2)
    seq = []
    for k, pc in enumerate(pcs):
        i = ils.Ins(pc, *ins[pc])
        if i.cond and k + 1 < len(pcs): i.taken = pcs[k + 1] != pc + i.nwords
        seq.append(i)
    total, stalls, sites = ils.analyze(seq)
    rows.append((int(tok[1]), len(pcs), total, dict(stalls)))
for f, n, c, st in rows:
    print('frame %6d: %5d instructions, %5d cycles (%.1f a sample), stalls %s' % (f, n, c, c / 16, st))
cs = [r[2] for r in rows]
print('mean %.1f cycles a frame (%.1f a sample), max %d (%.1f a sample), %d frames' % (statistics.mean(cs), statistics.mean(cs) / 16, max(cs), max(cs) / 16, len(cs)))
