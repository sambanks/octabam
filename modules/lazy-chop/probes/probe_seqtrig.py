#!/usr/bin/env python3
"""Who starts T1's voice when the sequencer plays step 1 (writes to voice 0's +0 and +68)."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "seqtrig"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("seqtrig", card, "OCTABAM", "LC")
with r.p as p:
    p.settle()
    p.proc.command(f"watchmem {V.VOICES:#x} 72", "ok")
    p.press("play", settle=150)
    out = p.proc.command("writes", "writes")
    recs = out.split()[2:]
    seen = {}
    for rec in recs:
        f = rec.split(":")
        if len(f) >= 4:
            pc, addr = f[1], int(f[2], 16) - V.VOICES
            seen.setdefault((pc, addr), f[3])
    for (pc, off), v in sorted(seen.items())[:40]:
        print(f"pc {pc} voice+{off} = {v}")
    p.press("stop", settle=100)
