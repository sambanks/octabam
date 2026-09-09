#!/usr/bin/env python3
"""Successive-loop stationarity on the T2 feed of a block dump (RTOS_FORK 10.42's instrument):
loop k vs k+1 at the best integer shift in [-3,3], residual in dB re the loop's own RMS,
skipping SKIP samples either side of the loop point. Also reports zero-frame runs."""
import sys, math
sys.path.insert(0, 'tools/scratch')
import blockdump as bd, o10_recloop as rl
dump, L = sys.argv[1], float(sys.argv[2])          # ideal pass length in samples
SKIP = 300
c = bd.classes(bd.read(dump)); x = rl.track_audio(c, 2)
nz = next((i for i, v in enumerate(x) if v), None)
print(f'{dump}: {len(x)} samples, first nonzero {nz}')
zr = []; cur = None
for f in range(len(x) // 16):
    z = all(v == 0 for v in x[f*16:(f+1)*16])
    if z and cur is None: cur = f
    if not z and cur is not None: zr.append((cur, f-1)); cur = None
print('zero-frame runs:', zr[:10])
Li = int(round(L)); a = nz
k = 0
while a + 2 * Li + 4 < len(x):
    best = None
    for s in range(-3, 4):
        num = den = 0.0
        for i in range(SKIP, Li - SKIP):
            d = x[a + i] - x[a + Li + s + i]; num += d * d; den += x[a + i] ** 2
        db = 10 * math.log10(num / den) if num > 0 else -240.0
        if best is None or db < best[1]: best = (s, db)
    print(f'  loop {k} vs {k+1}: shift {best[0]:+d}, residual {best[1]:7.1f} dB')
    a += Li + best[0]; k += 1
