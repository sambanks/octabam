#!/usr/bin/env python3
"""Panel-link LED traffic while chopping with the sequencer running (the F5 storm on the unit)."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify")); sys.path.insert(0, str(ROOT / "tools/panel"))
import verify_lazy_chop as V
from panel_link import PanelLink

def ledmsgs(p, ms):
    a = len(p.rt.uart64.tx); p.run(ms); raw = bytes(p.rt.uart64.tx[a:len(p.rt.uart64.tx)])
    L = PanelLink(); n = [0]; orig = L._message
    def m(x):
        if x and (0x20 <= x[0] <= 0x3f or 0xa0 <= x[0] <= 0xaf): n[0] += 1
        orig(x)
    L._message = m; L.feed(raw); return n[0], len(raw)

cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "ledstorm"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("ledstorm", card, "OCTABAM", "LC")
with r.p as p:
    p.settle(); r.editor()
    p.press("play", settle=300)
    print("playing, editor, no chop: LED msgs/s, bytes", ledmsgs(p, 1000))
    r.arm(); print("armed, playing:", ledmsgs(p, 1000))
    r.tap("trig1", 100); r.tap("trig2", 100)
    print("chopping (2 taps), playing:", ledmsgs(p, 1000), "next", p.long(r.NXT))
    for k in range(3, 7): r.tap(f"trig{k}", 150)
    print("after 4 more taps: next", p.long(r.NXT))
    p.press("stop", settle=300); print("stopped, chopping:", ledmsgs(p, 1000))
