#!/usr/bin/env python3
"""LAZY CHOP's LEDs after the F4 report: green/red per key, the trig-LED pass
slot (lc_ledpass) repainting after stock clears ids 0-31, live markers."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V

def wire(p):
    return sorted(k for k, v in p.link.led_bits().items() if v and k < 32)

cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "ledpass"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("ledpass", card, "OCTABAM", "LC")
pass_addr = r.sym("lc_ledpass")
with r.p as p:
    p.settle()
    p.proc.command(f"watch {pass_addr:#x},0x40043fdc", "ok")
    r.editor(); r.arm()
    print("armed:", sorted(V.lit(p)), "wire", wire(p), "count", p.long(V.FLEX1 + 1092))
    r.tap("trig1", 150); r.tap("trig2", 150); r.tap("trig3", 150)
    print("3 taps:", sorted(V.lit(p)), "wire", wire(p), "count", p.long(V.FLEX1 + 1092), "slices",
          [x[0] for x in r.slices()[1]])
    print("hits:", p.proc.command("hits", "hits")[:300])
    for t in range(3):
        p.poke(0x460BA9AE, b"\0\0\0\0")
        p.run(200)
        print(f"wiped ids 0-31, +200 ms:", sorted(V.lit(p)), "hits", p.proc.command("hits", "hits")[:300])
    for cd in (5, 10, 30):
        p.poke(0x460BA9CC + 4 * 0, cd.to_bytes(4, "big"))     # a stock-style flash on id 0: countdown cd ticks
        p.run(400)
        print(f"id 0 countdown set to {cd}, +400 ms:", sorted(V.lit(p)), "countdown", p.long(0x460BA9CC))
    p.press("play", settle=500)
    print("PLAY:", sorted(V.lit(p)), "wire", wire(p), "hits", p.proc.command("hits", "hits")[:300])
    for k in range(4, 18):
        r.tap(f"trig{(k - 1) % 16 + 1}", 120)
    print("17 taps (page 2, 1 tapped):", sorted(V.lit(p)), "count", p.long(V.FLEX1 + 1092))
    p.press("stop", settle=300)
    p.press("yes", settle=400)
    print("YES:", sorted(V.lit(p)), "wire", wire(p), "count", r.slices()[0])
