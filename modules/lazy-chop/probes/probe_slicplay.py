#!/usr/bin/env python3
"""The F5 unit report: chopping with the sequencer running on a SLIC ON track
(trigs on steps 1 and 9), and LED traffic against a faked running light."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify")); sys.path.insert(0, str(ROOT / "tools/panel"))
import verify_lazy_chop as V
from panel_link import PanelLink

def count_led(p, fn):
    a = len(p.rt.uart64.tx); fn(); raw = bytes(p.rt.uart64.tx[a:len(p.rt.uart64.tx)])
    L = PanelLink(); n = [0]; orig = L._message
    def m(x):
        if x and (0x20 <= x[0] <= 0x3f or 0xa0 <= x[0] <= 0xaf): n[0] += 1
        orig(x)
    L._message = m; L.feed(raw); return n[0]

cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "slicplay"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["slic"], card)
r = V.Run("slicplay", card, "OCTABAM", "LC")
with r.p as p:
    p.settle(); r.editor()
    if "play" in sys.argv: p.press("play", settle=200)
    r.arm()
    r.tap("trig1", 200)
    poss = []
    for k in range(2, 11):
        r.tap(f"trig{k}", 200); poss.append(p.long(V.VOICES + 68))
    print("playing, SLIC on, 9 taps 200 ms: next", p.long(r.NXT), "count", p.long(V.FLEX1 + 1092), "playheads", poss)
    def fake():
        for _ in range(100):
            b = bytearray(p.peek(0x460BA98C, 1)); b[0] |= 0x30          # blink ids 4, 5 (step 3's pair)
            p.poke(0x460BA98C, bytes(b)); p.run(10)
    print("faked running light 1 s: LED messages", count_led(p, fake), "lit", sorted(V.lit(p)))
    p.press("yes", settle=400); print("YES: count", r.slices()[0])
    p.press("stop", settle=300)
