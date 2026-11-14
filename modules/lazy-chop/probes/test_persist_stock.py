"""LAZY CHOP: slices survive a power cycle (the port rebooted on the same card)."""
import pathlib, re, struct, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel", "tools/emu"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa
import emu_card
from stems_panel import MenuPort
OUT = ROOT / "out/lc"; card = OUT / "w4" / "card.img"
m = (ROOT / "out/platform/runtime/runtime.map").read_text()
sym = lambda n: int(re.search(rf"(0x[0-9a-f]+)\s+{n}\n", m).group(1), 16)
ST = sym("lc_state")
REC = 0x100b14f0
fails = []
def check(c, what):
    print(("PASS " if c else "FAIL ") + what)
    if not c: fails.append(what)
def slices(p):
    n = p.long(REC + 1092)
    return n, [struct.unpack(">IIi", p.peek(REC + 312 + 12 * k, 12)) for k in range(min(n, 64))]
def tap(p, k, gap=150):
    p.key(k, True); p.run(20); p.key(k, False); p.run(gap - 20)
def card_slices():
    files = emu_card.extract_image(card.read_bytes())
    out = {}
    for name, data in files.items():
        if name.endswith(("markers.work", "markers.strd")):
            at = 0x16                                   # FLEX slot 1's record
            body = data[at:at + 784]
            n = struct.unpack(">I", body[780:784])[0]
            out[name] = (n, [struct.unpack(">IIi", body[12 + 12 * k:24 + 12 * k]) for k in range(min(n, 64))])
    return out
before = card_slices()
print("card before:", {k: v[0] for k, v in before.items()})
with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port_s1.log") as p:
    p.settle()
    p.chord("t1", "bank", settle=600); p.press("pg_amp", settle=400)
    p.proc.command("knob 0x30 3", "ok"); p.run(300)   # stock encoder A: slice 1 moves
    chopped = slices(p)
    print("chopped:", chopped[0], chopped[1])
    check(chopped[1][0][0] != 0, "stock encoder A moved slice 1")
    p.press("no", settle=400)                          # out of the editor
    p.open_menu(); p.press("left")
    for _ in range(6): p.press("up")
    p.press("right", settle=300)                       # PROJECT: CHANGE SAVE RELOAD [SYNC TO CARD]
    for _ in range(3): p.press("down", settle=120)
    p.press("yes", settle=600); p.png(OUT / ("sync_" + 'stock' + ".png"))
    p.press("yes", settle=600)                         # confirm, if asked
    p.run(4000)
    print(p.card_flush())
after = card_slices()
print("card after:", {k: v[0] for k, v in after.items()})
work = [v for k, v in after.items() if k.endswith("markers.work")]
check(bool(work) and work[0] == chopped, "markers.work on the card holds the chopped slices")
with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port_s2.log") as p:
    p.settle()
    back = slices(p)
    print("after reboot:", back[0], back[1])
    check(back == chopped, "after a reboot on the same card the slot has the chopped slices")
print("FAILED:", fails if fails else "none")
