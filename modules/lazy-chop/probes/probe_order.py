import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa
from stems_panel import MenuPort
OUT = ROOT / "out/lc"
def labels(p, n):
    lp = p.long(0x460e5e2c)
    return [p.cstr(p.long(lp + 4 * i)) for i in range(n)] if 0x40000000 <= lp < 0x48000000 else []
for name, card, selw, n, at, grid in (("off", OUT / "w/card.img", 0x460e5f54, 7, 2, 3),
                                      ("on", OUT / "w4/card.img", 0x460e5f58, 10, 5, 6)):
    with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / f"port_o{name}.log") as p:
        p.settle()
        p.chord("t1", "bank", settle=600); p.press("pg_amp", settle=400)
        def goto(i):
            p.chord("func", "bank", settle=500)
            for _ in range(11):
                p.press("up", settle=80)            # the list stops at the top
            for _ in range(i):
                p.press("down", settle=120)
            lo = p.long(0x460e5e34)
            return p.long(lo) if 0x40000000 <= lo < 0x48000000 else -1
        cur = goto(at)
        print(name, "rows:", labels(p, n), "live cursor", cur)
        p.png(OUT / f"menu_{name}.png")
        p.press("no", settle=300)
        cur = goto(grid)
        print(name, "cursor on", labels(p, n)[cur] if 0 <= cur < n else cur)
        p.press("yes", settle=400)
        print(name, "-> opens:", labels(p, 3))
