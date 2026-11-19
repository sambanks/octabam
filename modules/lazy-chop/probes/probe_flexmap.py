#!/usr/bin/env python3
"""FLEX slot 1's audio: its first frame, its blocks (contiguous?), and what points at it."""
import pathlib, shutil, sys, struct, wave
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
wf = wave.open(str(V.OUT / "_projects" / "LC_440_120.wav")); raw = wf.readframes(wf.getnframes())
def be(f, n=4):
    out = b""
    for i in range(n):
        x = int.from_bytes(raw[(f + i) * 4:(f + i) * 4 + 2], "little", signed=True)
        y = int.from_bytes(raw[(f + i) * 4 + 2:(f + i) * 4 + 4], "little", signed=True)
        out += struct.pack(">hh", x, y)
    return out
w = V.OUT / "_probe" / "flexmap"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("flexmap", card, "OCTABAM", "LC")
POOL, BLK, N = 0x40A955E0, 6144, 14602
with r.p as p:
    p.settle(); p.run(500)
    mem = p.peek(POOL, N * BLK)
    hits = {}
    for f in (100, 1536, 1537, 3000, 20000, 60000, 88000):   # 1536 frames = one 6144-byte block
        at = mem.find(be(f, 6))
        hits[f] = at
        print(f"frame {f}: pool+{at:#x} block {at // BLK} +{at % BLK}" if at >= 0 else f"frame {f}: not found")
    base = hits[100] - 400
    contiguous = all(hits[f] == base + 4 * f for f in hits if hits[f] >= 0)
    print(f"start pool+{base:#x} = {POOL + base:#x} (block {base // BLK} +{base % BLK}); contiguous: {contiguous}")
    # anything in the slot record, its control record, or the status record that equals the start or its block?
    startaddr, startblk = POOL + base, base // BLK
    for name, a, n in (("slot record", V.FLEX1, 1096), ("control rec", 0x46C922C4 + 0 * 44, 44), ("status rec", 0x46C90A78, 0x2C)):
        b = p.peek(a, n)
        for o in range(0, n - 3, 2):
            v = int.from_bytes(b[o:o + 4], "big")
            if v in (startaddr, startblk, base) or (o % 2 == 0 and int.from_bytes(b[o:o+2], "big") == startblk):
                print(f"  {name} +{o}: {v:#x}")
    idx = p.peek(0x46C2E580, 64); arr = p.peek(0x46C2E9C0, 64)
    print("index table 0x46c2e580:", idx.hex()); print("block array 0x46c2e9c0:", arr.hex())
