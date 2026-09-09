#!/usr/bin/env python3
"""Align, on one frame axis (frames since transport start), for the T2 voice (0x80004a80):
  - every write to +0x1f/+0x5c/+0x60/+0x64 (and the bind's +0x48 read-pos resets),
  - the converter's compare at 0x40008c88 (d0 = read pos) and which exit followed,
  - the host->DSP feed's zero frames (block dump, track 2)."""
import sys, re, bisect, pathlib
sys.path.insert(0, 'tools/scratch')
import blockdump as bd, o10_recloop as rl
log, dump = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
V = 0x80004a80
txt = pathlib.Path(log).read_text().splitlines()
t0 = None
for l in txt:
    m = re.search(r'transport start at ESAI frame (\d+) out', l)
    if m and int(m.group(1)) > 0: t0 = int(m.group(1)); break
print('transport start sample', t0)
# mem writes: sample, addr, val, pc, instr
W = []
for l in txt:
    m = re.match(r'\s*\[\s*([\d.]+)\] \[(0x[0-9a-f]+)\] <- (0x[0-9a-f]+|\d+) \((\d)\) at pc (0x[0-9a-f]+) in \S+\s+i=(\d+)', l)
    if m: W.append((float(m.group(1)), int(m.group(2),16), int(m.group(3),0), int(m.group(5),16), int(m.group(6))))
print('mem writes', len(W))
inst = [w[4] for w in W]; samp = [w[0] for w in W]
def frame_of_instr(i):
    k = bisect.bisect_left(inst, i)
    if k >= len(samp): k = len(samp) - 1
    return (samp[k] - t0) / 16
names = {0x1f: '+1f', 0x5c: '+5c', 0x60: '+60', 0x64: '+64', 0x48: '+48'}
print('--- field writes (frame, field, value, pc); +48 only when pc is not the per-frame stepper')
last = {}
for s, a, v, pc, i in W:
    off = a - V
    if off in names:
        f = (s - t0) / 16
        if off == 0x48 and pc in (0x40008898, 0x40008e6e, 0x400088dc, 0x400088e2, 0x400088e8, 0x400088ee, 0x400088f4, 0x400088fa, 0x40008900): continue
        key = (off, v, pc)
        if last.get(off) == key and off != 0x48: continue
        last[off] = key
        print(f'  f{f:9.2f} {names[off]} <- {v:#x} ({v if v < 2**31 else v-2**32}) at {pc:#x}')
# pc hits
H = []
for l in txt:
    m = re.match(r'\s*\[\s*(\d+)\] at (0x[0-9a-f]+) d0=(0x[0-9a-f]+|\d+) .* a2-6 (0x[0-9a-f]+|\d+) ', l)
    if m: H.append((int(m.group(1)), int(m.group(2),16), int(m.group(3),0), int(m.group(4),0)))
print('pc hits', len(H))
print('--- T2 converter decisions: runs of (exit) with pos range')
runs = []
for k, (i, pc, d0, a2) in enumerate(H):
    if pc != 0x40008c88 or a2 != V: continue
    nxt = H[k+1][1] if k + 1 < len(H) else 0
    ex = {0x40008cfc: 'ZERO', 0x40008de2: 'FETCH'}.get(nxt, hex(nxt))
    f = frame_of_instr(i)
    if runs and runs[-1][0] == ex and f - runs[-1][2] < 3: runs[-1][2] = f; runs[-1][4] = d0; runs[-1][5] += 1
    else: runs.append([ex, f, f, d0, d0, 1])
for ex, f0, f1, p0, p1, n in runs:
    print(f'  {ex:5s} f{f0:8.1f}..f{f1:8.1f} ({n} frames) pos {p0:#x}..{p1:#x}')
if dump:
    c = bd.classes(bd.read(dump)); x = rl.track_audio(c, 2)
    print('--- feed (track 2 host->DSP), zero-frame runs after frame 50; samples', len(x))
    zr = []; cur = None
    for f in range(50, len(x) // 16):
        z = all(v == 0 for v in x[f*16:(f+1)*16])
        if z and cur is None: cur = f
        if not z and cur is not None: zr.append((cur, f - 1)); cur = None
    if cur is not None: zr.append((cur, len(x)//16 - 1))
    for a, b in zr: print(f'  zero frames {a}..{b} ({b-a+1})')
