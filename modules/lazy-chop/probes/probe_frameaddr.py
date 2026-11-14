#!/usr/bin/env python3
"""0x4009499c(id, pos): the address of frame pos of arena object id; checked against FLEX slot 1's
known frames, and R1 after a take. Also the format table entry (0x400946d8(1, id) -> +0; 0x80003c20)."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "frameaddr"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("frameaddr", card, "OCTABAM", "LC")
with r.p as p:
    p.settle(); p.run(500)
    def call(line):
        for _ in range(20):
            try:
                return p.proc.command(line, "")
            except Exception as e:
                last = e; p.run(3)
        return f"failed: {last}"
    for pos in (0, 100, 1536, 3000, 88199):
        out = call(f"call 0x4009499c 0 {pos}")
        print("frame", pos, "->", out)
    print("object rec:", call("call 0x400946d8 1 0"))
    print("format table 0x80003c20:", p.peek(0x80003C20, 64).hex())
