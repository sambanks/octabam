#!/usr/bin/env python3
"""SLIC OFF card: where the engine reads T1's SLIC, and how the voice plays a slice
range with SLIC forced on (entry 0) versus with the trim set (rate, window)."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "slicbyte"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("slicbyte", card, "OCTABAM", "LC")
def vstate(p, what):
    v = V.VOICES
    print(f"  {what}: act {p.peek(v,1)[0]} rate {p.long(v+36):#x} win {p.long(v+48)}..{p.long(v+52)} pos {p.long(v+68)} +40 {p.long(v+40)} +44 {p.long(v+44)} +56 {p.long(v+56)} +60 {p.long(v+60)}")
with r.p as p:
    p.settle()
    blob = p.long(0x46C82456); part = p.peek(0x100B14CF, 1)[0]
    pb = blob + 0x8ED80 + part * 0x18B2
    slic = 0x80000810 + 72 * 0 + 0x21              # the live lane's SLIC (probe_slicdiff.py)
    print(f"part {part} at {pb:#x}; T1 FLEX SETUP bytes {p.peek(pb + 0x1E3 + 6, 6).hex()} (SLIC at {slic:#x})")
    rec = V.FLEX1
    # 1: trim set to slice 2's range (what G1 does with SLIC off)
    p.poke(rec + 300, (22050).to_bytes(4, "big")); p.poke(rec + 304, (44100).to_bytes(4, "big"))
    p.poke(0x46C80354, (0x1D).to_bytes(4, "big")); p.run(60); vstate(p, "trim 22050..44100, SLIC off")
    p.poke(0x46C80354, (0x40).to_bytes(4, "big")); p.run(100)
    p.poke(rec + 300, (0).to_bytes(4, "big")); p.poke(rec + 304, (88200).to_bytes(4, "big"))
    # 2: SLIC forced on in the part, entry 0 = slice 2's range
    p.poke(slic, b"\x01")
    old0 = p.peek(rec + 312, 12)
    p.poke(rec + 312, (22050).to_bytes(4, "big") + (44100).to_bytes(4, "big"))
    p.poke(0x46C80354, (0x1D).to_bytes(4, "big")); p.run(60); vstate(p, "SLIC poked on, entry 0 22050..44100")
    p.poke(0x46C80354, (0x40).to_bytes(4, "big")); p.run(100)
    p.run(200); vstate(p, "+200 ms (SLIC still on)")
    p.poke(slic, b"\x00"); p.run(300); vstate(p, "SLIC back off, +300 ms")
    p.poke(0x46C80354, (0x40).to_bytes(4, "big")); p.run(100)
    p.poke(rec + 312, old0)
    # 3: plain (the whole take, SLIC off)
    p.poke(0x46C80354, (0x1D).to_bytes(4, "big")); p.run(60); vstate(p, "whole take, SLIC off")
