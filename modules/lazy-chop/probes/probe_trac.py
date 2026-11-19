#!/usr/bin/env python3
"""T1's trig mask in RAM ([0x46c82456] + pattern*0x8ed8 + track*0x91a), and whether
the emulated sequencer retriggers T1 (steps 1 and 9 on the slic card)."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "trac"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["slic"], card)
r = V.Run("trac", card, "OCTABAM", "LC")
with r.p as p:
    p.settle()
    bank = p.long(0x46C82456); ptn = p.peek(0x80000004, 1)[0]
    trac = bank + ptn * 0x8ED8 + 0 * 0x91A
    print(f"bank blob {bank:#x}, pattern {ptn}, T1 TRAC {trac:#x}: trig mask {p.peek(trac, 8).hex()}, one-shot {p.peek(trac + 0x18, 8).hex()}")
    print(f"T2 trig mask {p.peek(trac + 0x91a, 8).hex()}")
    p.press("play", settle=20)
    ps = []
    for _ in range(25):
        p.run(100); ps.append(p.long(V.VOICES + 68))
    print("T1 playhead every 100 ms while playing:", ps)
    p.press("stop", settle=100)
