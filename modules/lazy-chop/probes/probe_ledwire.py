#!/usr/bin/env python3
"""Raw panel-link bytes (non-LCD) around a stock grid-rec trig and a LAZY CHOP tap."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify")); sys.path.insert(0, str(ROOT / "tools/panel"))
import verify_lazy_chop as V
from panel_link import PanelLink

def grab(p, fn):
    a = len(p.rt.uart64.tx); fn(); b = len(p.rt.uart64.tx)
    raw = bytes(p.rt.uart64.tx[a:b])
    # keep only LED ops: 0x2r/0xar rows (2 B), 0x3n levels (2 B); skip LCD by decoding with a scratch link
    out, i = [], 0
    L = PanelLink()
    msgs = []
    orig = L._message
    L._message = lambda m: (msgs.append(bytes(m)), orig(m))
    L.feed(raw)
    return [m.hex() for m in msgs if m and (0x20 <= m[0] <= 0x3f or 0xa0 <= m[0] <= 0xaf or m[0] == 0xb5)]

cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "ledwire"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("ledwire", card, "OCTABAM", "LC")
with r.p as p:
    p.settle()
    p.press("rec", settle=300)
    print("stock grid-rec, trig on step 5:", grab(p, lambda: p.press("trig5", settle=300)))
    print("stock grid-rec, trig off step 5:", grab(p, lambda: p.press("trig5", settle=300)))
    p.press("rec", settle=300)
    r.editor()
    print("LAZY CHOP arm:", grab(p, r.arm))
    print("LAZY CHOP TRIG 1:", grab(p, lambda: r.tap("trig1", 150)))
    print("LAZY CHOP TRIG 2:", grab(p, lambda: r.tap("trig2", 150)))
    print("1 s idle:", grab(p, lambda: p.run(1000)))
