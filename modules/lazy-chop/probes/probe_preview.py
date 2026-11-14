#!/usr/bin/env python3
"""Stock slice preview: press TRIG 3 on the SLICE page (4 slices) and record
who writes T1's mailbox and voice 0 (window +48/+52, position +68, settings +8)."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "preview"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("preview", card, "OCTABAM", "LC")
with r.p as p:
    p.settle(); r.editor(); p.run(300)
    p.proc.command("watchmem 0x46c80354 4", "ok")
    p.proc.command(f"watchmem {V.VOICES + 48:#x} 24", "ok")
    p.key("trig3", True); p.run(120)
    out = p.proc.command("writes", "writes")
    for rec in out.split()[2:40]:
        print(rec)
    print("voice: act", p.peek(V.VOICES, 1)[0], "win", p.long(V.VOICES + 48), p.long(V.VOICES + 52), "pos", p.long(V.VOICES + 68),
          "slices", [x[:2] for x in r.slices()[1]])
    p.key("trig3", False); p.run(200)
