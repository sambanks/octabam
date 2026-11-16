#!/usr/bin/env python3
"""Where FLEX slot 1's audio sits in the block pool, and in what format."""
import pathlib, shutil, sys, struct, wave
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
wav = V.OUT / "_projects" / "LC_440_120.wav"
wf = wave.open(str(wav)); print("wav:", wf.getnchannels(), "ch", wf.getsampwidth() * 8, "bit", wf.getframerate(), wf.getnframes(), "frames")
raw = wf.readframes(wf.getnframes()); sw = wf.getsampwidth(); ch = wf.getnchannels()
w = V.OUT / "_probe" / "flexdata"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("flexdata", card, "OCTABAM", "LC")
POOL, BLK, N = 0x40A955E0, 6144, 14602
with r.p as p:
    p.settle(); p.run(500)
    f0 = 3000                                     # a frame well inside the loop
    probe16 = raw[f0 * sw * ch: f0 * sw * ch + 12]
    print("wav bytes at frame", f0, probe16.hex())
    # try big-endian 16-bit and the raw little-endian bytes
    samples = [int.from_bytes(raw[(f0 + i) * sw * ch:(f0 + i) * sw * ch + sw], "little", signed=True) for i in range(4)]
    be16 = b"".join(struct.pack(">h", s if sw == 2 else s >> 8) for s in samples)
    def be24(i): return (samples[i] << 8 & 0xffffff).to_bytes(3, "big")
    cands = {"be16 stereo": b"".join(struct.pack(">hh", x, x) for x in samples[:2]),
             "be24 stereo": be24(0) + be24(0) + be24(1) + be24(1),
             "le24 stereo": b"".join((samples[i] << 8 & 0xffffff).to_bytes(3, "little") * 2 for i in range(2)),
             "be16 mono": struct.pack(">hhh", *samples[:3])}
    for b0 in range(0, N, 256):
        chunk = p.peek(POOL + b0 * BLK, 256 * BLK)
        for name, pat in cands.items():
            at = chunk.find(pat)
            if at >= 0:
                addr = POOL + b0 * BLK + at
                print(f"found {name} at {addr:#x} (block {(addr - POOL) // BLK}, +{(addr - POOL) % BLK})")
                print("context:", p.peek(addr - 16, 48).hex())
                cands.pop(name); break
        if not cands: break
    rec = p.peek(V.FLEX1, 1096)
    print("slot1 record +0x100..+0x150:", rec[0x100:0x150].hex())
    print("slot1 record +1080..+1096:", rec[1080:1096].hex())
