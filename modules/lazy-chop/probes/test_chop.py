"""LAZY CHOP end to end under the port (MKI): chop, adjust, page, cancel, leave."""
import pathlib, re, struct, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa
import verify_repitch as vr
from stems_panel import MenuPort

OUT = ROOT / "out/lc"; work = OUT / "w4"
card = work / "card.img"                      # the 4-slice project staged by probe_trig.py
m = (ROOT / "out/platform/runtime/runtime.map").read_text()
sym = lambda n: int(re.search(rf"(0x[0-9a-f]+)\s+{n}\n", m).group(1), 16)
ST, NXT = sym("lc_state"), sym("lc_next")
REC = 0x100b14f0                              # FLEX slot 1
SEL = 0x400ceb3c
fails = []
def check(c, what):
    print(("PASS " if c else "FAIL ") + what)
    if not c: fails.append(what)
def slices(p):
    n = p.long(REC + 1092)
    return n, [struct.unpack(">IIi", p.peek(REC + 312 + 12 * k, 12)) for k in range(min(n, 64))]
def text(p):
    return "\n".join("".join("#" if c else "." for c in r) for r in p.screen())
def tap(p, k, gap=100):
    p.key(k, True); p.run(20); p.key(k, False); p.run(gap - 20)
def open_mode(p):
    on = p.long(SEL) < 0x80000000            # the marker is on a slice: the 10-row menu
    selw, last = (0x460e5f58, 5) if on else (0x460e5f54, 2)
    p.chord("func", "bank", settle=500)
    for _ in range(11):
        p.press("up", settle=80)                  # the list stops at the top
    for _ in range(last):
        p.press("down", settle=120)
    print("menu", "on" if on else "off", "a slice; row", p.long(selw))
    p.press("yes", settle=400)

with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port_t.log") as p:
    p.settle()
    p.chord("t1", "bank", settle=600); p.press("pg_amp", settle=400)
    n0, s0 = slices(p)
    print("before:", n0, s0)
    open_mode(p)
    check(p.long(ST) == 1, f"LAZY CHOP row arms the mode (state {p.long(ST)})")
    (OUT / "c1_armed.txt").write_text(text(p)); p.png(OUT / "c1_armed.png")
    tap(p, "trig2")
    check(p.long(ST) == 1, "TRIG 2 before TRIG 1 does nothing")
    tap(p, "trig1")
    check(p.long(ST) == 2 and p.long(REC + 1092) == 0, "TRIG 1 starts the take (count 0 while chopping)")
    keys = [f"trig{k}" for k in range(2, 17)] + ["trig1", "trig2"]
    tap(p, "trig5")                            # out of order: expecting TRIG 2
    check(p.long(NXT) == 1, "an out-of-order key places nothing")
    for k in keys:
        tap(p, k)
    check(p.long(NXT) == 18, f"17 taps across the page turn place 17 markers (next {p.long(NXT)})")
    p.press("yes", settle=400)
    n, s = slices(p)
    print("after YES:", n, s)
    (OUT / "c2_done.txt").write_text(text(p)); p.png(OUT / "c2_done.png")
    check(p.long(ST) == 0, "YES writes the slices and ends the mode")
    check(n == 18, f"18 slices written ({n})")
    check(all(s[i][1] == s[i + 1][0] for i in range(n - 1)), "each slice ends where the next starts")
    check(all(s[i + 1][0] - s[i][0] >= 2000 for i in range(n - 1)), "markers ~100 ms apart, increasing")
    check(s[0][0] == 0 and s[-1][1] == vr.LOOP_FRAMES, "first starts at trim start, last ends at trim end")
    check(all(x[2] == -1 for x in s), "no loop points")
    # after YES: the stock editor, as with any slices
    for i in range(40):                                       # LEVEL: the marker moves
        p.proc.command("knob 0x36 3", "ok"); p.run(120)
        if 0 < p.long(SEL) < 0x80000000: break
    sel = p.long(SEL)
    print("LEVEL turns", i + 1, "marker", p.long(REC + 1080), "slice", sel + 1)
    check(0 < sel < n, f"stock LEVEL moves the marker onto a new slice (slice {sel + 1})")
    before = slices(p)[1]
    p.proc.command("knob 0x30 3", "ok"); p.run(300)
    after = slices(p)[1]
    changed = [i for i in range(n) if before[i] != after[i]]
    check(sel in changed and all(i in (sel - 1, sel) for i in changed), f"stock encoder A edits it (changed {changed})")
    tap(p, "trig3", 300)
    check(p.long(ST) == 0 and slices(p)[1] == after, "trig keys are stock again (no slice change)")
    (OUT / "c3_after.txt").write_text(text(p)); p.png(OUT / "c3_after.png")
    # cancel: a new chop, then NO, brings the 18 back
    keep = slices(p)
    open_mode(p); tap(p, "trig1"); tap(p, "trig2"); tap(p, "trig3")
    p.press("no", settle=400)
    check(p.long(ST) == 0 and slices(p) == keep, "NO while chopping restores the slices")
    # leave mid-chop by changing page: restored, layer gone
    open_mode(p); tap(p, "trig1"); tap(p, "trig2")
    p.press("pg_playback", settle=400)         # TRIM page: the SLICE page's leave runs
    check(p.long(ST) == 0 and slices(p) == keep, "leaving the page mid-chop restores and ends the mode")
    tap(p, "trig2", 300)
    check(p.long(ST) == 0, "trig keys are stock again after leaving")
print("FAILED:", fails if fails else "none")
