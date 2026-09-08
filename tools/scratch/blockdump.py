#!/usr/bin/env python3
"""Read ot_emu --block-dump files: every host-port block's content at the move.

  blockdump.py summary A.dump            per block class: frames, non-zero, RMS
  blockdump.py diff A.dump B.dump        per block class: frames whose content differs
  blockdump.py wav A.dump CLASS OUT.wav  a block class's words as int16 mono (words in order)
A class is (dir, ch, core, ram) -- ram is the ColdFire address; ping-pong pairs are
separate classes.
"""
import struct, sys, math, wave, array

def read(path):
    out = []
    with open(path, 'rb') as f:
        data = f.read()
    o = 0
    while o + 16 <= len(data):
        d, frame, ch, core, ram, n = struct.unpack_from('<BIHBII', data, o)
        o += 16
        words = array.array('H'); words.frombytes(data[o:o + 2 * n])
        if sys.byteorder != 'little': words.byteswap()
        o += 2 * n
        out.append((chr(d), frame, ch, core, ram, words))
    return out

def classes(blocks):
    c = {}
    for d, frame, ch, core, ram, w in blocks:
        c.setdefault((d, ch, core, ram), []).append((frame, w))
    return c

def summary(path):
    c = classes(read(path))
    print(f"{'dir':3} {'ch':>2} {'core':>4} {'ram':>8} {'words':>5} {'blocks':>6} {'nz-frac':>7} {'rms16':>8} {'max16':>6}  frames")
    for k in sorted(c, key=lambda k: (k[0], k[1], k[2], k[3])):
        d, ch, core, ram = k
        ws = [x for _, w in c[k] for x in w]
        s = [x - 65536 if x >= 32768 else x for x in ws]
        nz = sum(1 for x in ws if x) / len(ws) if ws else 0
        rms = math.sqrt(sum(x * x for x in s) / len(s)) if s else 0
        mx = max(abs(x) for x in s) if s else 0
        fr = [f for f, _ in c[k]]
        print(f"{d:3} {ch:2d} {core:4d} {ram:08x} {len(c[k][0][1]):5d} {len(c[k]):6d} {nz:7.3f} {rms:8.1f} {mx:6d}  {fr[0]}..{fr[-1]}")

def diff(a, b):
    ca, cb = classes(read(a)), classes(read(b))
    print(f"{'dir':3} {'ch':>2} {'core':>4} {'ram':>8} {'blocks':>6} {'differ':>6} {'maxdiff':>7} {'first-frame':>11}")
    for k in sorted(set(ca) | set(cb)):
        if k not in ca or k not in cb:
            print(f"{k[0]:3} {k[1]:2d} {k[2]:4d} {k[3]:08x}  only in {'A' if k in ca else 'B'}")
            continue
        fa = dict(ca[k]); fb = dict(cb[k])
        common = sorted(set(fa) & set(fb))
        nd = 0; md = 0; first = None
        for f in common:
            x, y = fa[f], fb[f]
            if len(x) != len(y) or x != y:
                nd += 1
                if first is None: first = f
                if len(x) == len(y):
                    md = max(md, max(abs(a - b) for a, b in zip(x, y)))
        print(f"{k[0]:3} {k[1]:2d} {k[2]:4d} {k[3]:08x} {len(common):6d} {nd:6d} {md:7d} {str(first):>11}")

def towav(path, cls, out):
    d, ch, core, ram = cls.split(':')
    key = (d, int(ch), int(core), int(ram, 16))
    c = classes(read(path))
    ws = array.array('h', [x - 65536 if x >= 32768 else x for _, w in c[key] for x in w])
    if sys.byteorder != 'little': ws.byteswap()
    with wave.open(out, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(ws.tobytes())
    print(f"{out}: {len(ws)} words")

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'summary': summary(sys.argv[2])
    elif cmd == 'diff': diff(sys.argv[2], sys.argv[3])
    elif cmd == 'wav': towav(sys.argv[2], sys.argv[3], sys.argv[4])
