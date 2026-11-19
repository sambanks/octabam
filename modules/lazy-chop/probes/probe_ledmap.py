#!/usr/bin/env python3
"""Which LED ids stock uses for the trig keys: grid recording with a trig on
step 1 (T1), on the wire (PanelLink) and in the state array; then LAZY CHOP's."""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V

def show(r, what):
    p = r.p
    wire = sorted(k for k, v in p.link.led_bits().items() if v)
    lv = {k: v for k, v in p.link.leds.items() if k < 0x58 and v != 15}
    print(f"  {what}: state-array {sorted(V.lit(p) if hasattr(V,'lit') else [])} | wire bits {wire} | levels!=15 {lv}")

cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / "ledmap"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["sample"], card)
r = V.Run("ledmap", card, "OCTABAM", "LC")
with r.p as p:
    p.settle()
    if "again" in sys.argv:
        r.editor(); r.arm(); r.tap("trig1", 150); r.tap("trig2", 150); r.tap("trig3", 150); show(r, "chop 1: 3 taps")
        p.press("yes", settle=400); show(r, "YES")
        for k in (1, 2, 3, 2):
            p.key(f"trig{k}", True); p.run(150); show(r, f"stock: TRIG {k} held (preview)")
            p.key(f"trig{k}", False); p.run(300); show(r, f"stock: TRIG {k} released")
        r.arm(); show(r, "chop 2 armed")
        r.tap("trig1", 150); show(r, "chop 2: TRIG 1")
        r.tap("trig2", 150); show(r, "chop 2: TRIG 2")
        r.tap("trig3", 150); show(r, "chop 2: TRIG 3")
    elif "play" in sys.argv:
        r.editor(); p.press("play", settle=300); show(r, "editor, sequencer playing")
        r.arm(); show(r, "armed, playing")
        r.tap("trig1", 150); r.tap("trig2", 150); r.tap("trig3", 150); show(r, "3 taps, playing")
        p.run(600); show(r, "+600 ms")
        p.press("stop", settle=300); show(r, "STOP"); r.tap("trig4", 150); show(r, "TRIG 4 after STOP")
    else:
        r.editor(); r.arm(); show(r, "armed, stopped")
        r.tap("trig1", 150); show(r, "TRIG 1 (T1 plays the take)")
        for k in range(2, 6): r.tap(f"trig{k}", 150)
        show(r, "5 taps"); p.run(1500); show(r, "+1.5 s")
