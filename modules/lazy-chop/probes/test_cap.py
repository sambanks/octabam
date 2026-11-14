"""LAZY CHOP: 64 slices across four pages, then the cap."""
import pathlib, re, struct, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa
import verify_repitch as vr
from stems_panel import MenuPort
OUT = ROOT / "out/lc"; card = OUT / "w4" / "card.img"
m = (ROOT / "out/platform/runtime/runtime.map").read_text()
sym = lambda n: int(re.search(rf"(0x[0-9a-f]+)\s+{n}\n", m).group(1), 16)
ST, NXT = sym("lc_state"), sym("lc_next")
REC, SEL = 0x100b14f0, 0x400ceb3c
fails = []
def check(c, what):
    print(("PASS " if c else "FAIL ") + what)
    if not c: fails.append(what)
def slices(p):
    n = p.long(REC + 1092)
    return n, [struct.unpack(">IIi", p.peek(REC + 312 + 12 * k, 12)) for k in range(min(n, 64))]
def tap(p, k, gap):
    p.key(k, True); p.run(15); p.key(k, False); p.run(gap - 15)
with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port_cap.log") as p:
    p.settle()
    p.chord("t1", "bank", settle=600); p.press("pg_amp", settle=400)
    p.chord("func", "bank", settle=500)
    for _ in range(11):
        p.press("up", settle=80)                  # the list stops at the top
    for _ in range(5):
        p.press("down", settle=120)
    p.press("yes", settle=400)
    tap(p, "trig1", 25)
    for n in range(1, 64):
        tap(p, f"trig{n % 16 + 1}", 25)
        if n in (15, 31, 47):
            p.png(OUT / f"page_{n + 1}.png")
            (OUT / f"page_{n + 1}.txt").write_text("\n".join("".join("#" if c else "." for c in r) for r in p.screen()))
            print(f"after TRIG 16 (tap {n}): next {p.long(NXT)} state {p.long(ST)}")
    n, s = slices(p)
    check(p.long(ST) == 0, f"the 64th slice ends the mode by itself (state {p.long(ST)})")
    check(n == 64, f"64 slices written ({n})")
    check(all(s[i][1] == s[i + 1][0] and s[i][0] < s[i + 1][0] for i in range(63)), "64 slices chained and increasing")
    check(s[-1][1] == vr.LOOP_FRAMES, "the last ends at the trim end")
    print("first/last:", s[:2], s[-2:])
    tap(p, "trig1", 300)
    check(slices(p)[0] == 64, "a 65th tap adds nothing")
print("FAILED:", fails if fails else "none")
