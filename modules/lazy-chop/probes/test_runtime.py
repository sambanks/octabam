#!/usr/bin/env python3
"""Probe: LAZY CHOP against the running sequencer, a new recording into the
buffer being chopped, and pattern changes (MIDI program change, [PTN]+trig).
Prints what happens; verify_lazy_chop's seq/recnew/ptn scenarios are the gate.

    python3 modules/lazy-chop/probes/test_runtime.py seq|recnew|pc|pcplay|ptnkey
"""
import pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_lazy_chop as V

def st(r, what):
    p = r.p
    n, s = r.slices(r.rec)
    v = V.VOICES
    print(f"  {what}: state={p.long(r.ST)} next={p.long(r.NXT)} count={n} trim_e={p.long(r.rec+304)} "
          f"voice(act={p.long(v)&0xff000000 and 1}, rec={p.long(v+8):#x}, pos={p.long(v+68)}) "
          f"ptn={p.peek(0x80000004,1)[0]} part={p.peek(0x80000003,1)[0]} editor_slot={p.long(V.EDITOR_SLOT):#x} slices={s[:6]}")
    print("     screen:", " | ".join("".join(map(chr, row)).strip() if isinstance(row[0], int) else "".join(row).strip()
                                    for row in r.p.screen()[:3]) if r.p.screen() else "")

def seq(r):
    p = r.p; r.rec = V.FLEX1
    r.editor(); r.arm(); st(r, "armed")
    p.press("play", settle=100); st(r, "PLAY pressed")
    r.tap("trig1", 250)
    for k in range(2, 13):
        r.tap(f"trig{k}", 250); st(r, f"after TRIG {k}")
    p.press("yes", settle=400); st(r, "YES")
    p.press("stop", settle=300); st(r, "STOP")
    r.arm(); r.tap("trig1", 200); r.tap("trig2", 200)
    p.press("play", settle=200); st(r, "PLAY mid-chop")
    r.tap("trig3", 200); st(r, "TRIG 3")
    p.press("stop", settle=300); st(r, "STOP mid-chop")
    r.tap("trig4", 200); st(r, "TRIG 4 after STOP")
    p.press("yes", settle=400); st(r, "YES")

def recnew(r):
    p = r.p; r.rec = V.R1
    p.chord("func", "recab", settle=400)
    p.proc.command("knob 0x33 8", "ok"); p.run(300); p.press("no", settle=300)
    def take(ms):
        p.key("t1", True); p.run(40); p.key("recab", True); p.run(ms)
        p.key("recab", False); p.run(40); p.key("t1", False); p.run(500)
    take(1500); st(r, "take 1")
    r.editor(("recab", "bank")); r.arm(); st(r, "armed")
    r.chop(4, gap=150); st(r, "4 taps")
    p.key("t1", True); p.run(40); p.key("recab", True); p.run(200); st(r, "recording starts")
    p.run(600); p.key("recab", False); p.run(40); p.key("t1", False); p.run(500); st(r, "take 2 (0.8 s) done")
    r.tap("trig5", 150); r.tap("trig6", 150); st(r, "taps 5,6")
    p.press("yes", settle=400); st(r, "YES")

def pc(r, play=False):
    p = r.p; r.rec = V.FLEX1
    r.editor()
    if play:
        p.press("play", settle=100)
    r.arm(); r.chop(4, gap=150); st(r, "4 taps")
    p.proc.command("midi c0 01", "ok"); p.run(300); st(r, "PC -> A02 (+300 ms)")
    p.run(2200); st(r, "+2.5 s")
    r.tap("trig5", 150); st(r, "TRIG 5")
    p.press("yes", settle=400); st(r, "YES")
    p.press("stop", settle=300)

def ptnkey(r):
    p = r.p; r.rec = V.FLEX1
    r.editor(); r.arm(); r.chop(3, gap=150); st(r, "3 taps")
    p.key("pattern", True); p.run(60); r.tap("trig2", 100); p.key("pattern", False); p.run(400); st(r, "[PTN]+TRIG 2")
    p.key("pattern", True); p.run(60); r.tap("trig4", 100); p.key("pattern", False); p.run(400); st(r, "[PTN]+TRIG 4 (next key)")
    p.press("yes", settle=400); st(r, "YES")

def recslices(r, chop_during):
    p = r.p; r.rec = V.R1
    p.chord("func", "recab", settle=400)
    p.proc.command("knob 0x33 8", "ok"); p.run(300); p.press("no", settle=300)
    def take(ms):
        p.key("t1", True); p.run(40); p.key("recab", True); p.run(ms)
        p.key("recab", False); p.run(40); p.key("t1", False); p.run(500)
    take(1500)
    r.editor(("recab", "bank")); r.arm(); r.chop(4, gap=150); p.press("yes", settle=400); st(r, "take 1 chopped, YES")
    if chop_during:
        r.arm(); r.chop(2, gap=150); st(r, "chopping again")
    take(800); st(r, "take 2 (0.8 s) done")

SC = {"seq": seq, "recnew": recnew, "pc": pc, "pcplay": lambda r: pc(r, True), "ptnkey": ptnkey,
      "recstock": lambda r: recslices(r, False), "recchop": lambda r: recslices(r, True)}
name = sys.argv[1]
cards = V.build_projects(V.OUT / "_projects")
w = V.OUT / "_probe" / name; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
card = w / "card.img"; shutil.copy(cards["rec" if name.startswith("rec") else "sample"], card)
r = V.Run(name, card, "OCTABAM", "LC")
with r.p as p:
    p.settle()
    SC[name](r)
