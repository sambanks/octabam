#!/usr/bin/env python3
"""Which commands the sequencer posts to T1's mailbox (0x46c80354) while LAZY CHOP chops with PLAY on."""
import pathlib, shutil, sys, re
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "release"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["slic"], card)
r = V.Run("release", card, "OCTABAM", "LC")
with r.p as p:
    p.settle(); r.editor(); p.press("play", settle=200); r.arm()
    p.proc.command("watchmem 0x46c80354 4", "ok")
    r.tap("trig1", 200)
    for k in range(2, 11):
        r.tap(f"trig{k}", 200)
    out = p.proc.command("writes", "writes")
    vals = re.findall(r"=(0x[0-9a-f]+|[0-9a-f]+)", out)
    print("writes to T1's mailbox:", out[:600])
    print("next", p.long(r.NXT), "voice act", p.peek(V.VOICES, 1)[0])
    p.press("stop", settle=200)
