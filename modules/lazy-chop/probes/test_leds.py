"""LAZY CHOP: the trig LEDs while chopping (port; the LED state array 0x460ba9ae)."""
import pathlib, re, struct, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa
from stems_panel import MenuPort
OUT = ROOT / "out/lc"; card = OUT / "w4" / "card.img"
m = (ROOT / "out/platform/runtime/runtime.map").read_text()
ST = int(re.search(r"(0x[0-9a-f]+)\s+lc_state\n", m).group(1), 16)
fails = []
def check(c, what):
    print(("PASS " if c else "FAIL ") + what)
    if not c: fails.append(what)
def lit(p):
    b = p.peek(0x460ba9ae, 4)                     # ids 0-31: the trig LED pairs
    return {i for i in range(32) if b[i >> 3] >> (i & 7) & 1}
def tap(p, k, gap=80):
    p.key(k, True); p.run(20); p.key(k, False); p.run(gap - 20)
with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port_led.log") as p:
    p.settle()
    p.chord("t1", "bank", settle=600); p.press("pg_amp", settle=400)
    print("before:", sorted(lit(p)))
    p.chord("func", "bank", settle=500)
    for _ in range(11): p.press("up", settle=80)
    for _ in range(5): p.press("down", settle=120)
    p.press("yes", settle=400)
    print("armed:", sorted(lit(p)))
    check(lit(p) == {1}, "armed: only TRIG 1, in the 'next' colour")
    tap(p, "trig1"); p.run(40)                 # stock flashes id 16 for 10 ticks when T1 triggers
    check(lit(p) == {0, 3}, f"after TRIG 1: TRIG 1 placed, TRIG 2 next ({sorted(lit(p))})")
    for k in range(2, 9): tap(p, f"trig{k}")
    check(lit(p) == {0, 2, 4, 6, 8, 10, 12, 14, 17}, f"after TRIG 8: 1-8 placed, TRIG 9 next ({sorted(lit(p))})")
    p.run(200)
    check(lit(p) == {0, 2, 4, 6, 8, 10, 12, 14, 17}, "0.2 s later they are still lit (nothing stock clears them)")
    for k in range(9, 17): tap(p, f"trig{k}")
    check(lit(p) == {1}, f"after TRIG 16: the page turns, only TRIG 1 next ({sorted(lit(p))})")
    tap(p, "trig1")
    check(lit(p) == {0, 3}, f"slice 17 on TRIG 1: placed, TRIG 2 next ({sorted(lit(p))})")
    p.press("yes", settle=400)
    check(p.long(ST) == 0 and not (lit(p) & set(range(32))), f"YES: the mode ends and the trig LEDs are cleared ({sorted(lit(p))})")
    p.chord("func", "bank", settle=500)
    for _ in range(11): p.press("up", settle=80)
    for _ in range(5): p.press("down", settle=120)
    p.press("yes", settle=400); tap(p, "trig1"); tap(p, "trig2")
    p.press("no", settle=400)
    check(not lit(p), f"NO: cleared ({sorted(lit(p))})")
print("FAILED:", fails if fails else "none")
