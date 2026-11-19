#!/usr/bin/env python3
"""Stock grid recording: which LED id each step's trig uses (steps 1-16), on the wire."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V
cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "ledmap2"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("ledmap2", card, "OCTABAM", "LC")
def bits(p): return {k for k, v in p.link.led_bits().items() if v and k < 32}
with r.p as p:
    p.settle(); p.press("rec", settle=300)
    base = bits(p)
    for n in range(2, 17):
        p.chord("func", f"trig{n}", settle=250); now = bits(p)
        print(f"step {n} FUNC (trigless): new ids {sorted(now - base)} gone {sorted(base - now)}"); base = now
