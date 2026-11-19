"""LAZY CHOP: SAVE PROJECT writes the chopped slices (markers.strd); RELOAD brings them back over a later edit."""
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
ST = sym("lc_state"); REC = 0x100b14f0
fails = []
def check(c, what):
    print(("PASS " if c else "FAIL ") + what)
    if not c: fails.append(what)
def slices(p):
    n = p.long(REC + 1092)
    return n, [struct.unpack(">IIi", p.peek(REC + 312 + 12 * k, 12)) for k in range(min(n, 64))]
def tap(p, k, gap=150):
    p.key(k, True); p.run(20); p.key(k, False); p.run(gap - 20)
def labels(p, n=6):
    lp = p.long(0x460e5e2c)
    return [p.cstr(p.long(lp + 4 * i)) for i in range(n)] if 0x40000000 <= lp < 0x48000000 else []
def project_row(p, row, tag):
    p.open_menu(); p.press("left")
    for _ in range(6): p.press("up")
    p.press("right", settle=300)                       # PROJECT: CHANGE SAVE RELOAD SYNC...
    for _ in range(8): p.press("up", settle=80)        # the menu remembers its row: from the top
    for _ in range(row): p.press("down", settle=120)
    p.press("yes", settle=600); p.png(OUT / f"sr_{tag}_1.png")
    p.press("yes", settle=600); p.png(OUT / f"sr_{tag}_2.png")   # the confirmation
    p.run(5000); p.png(OUT / f"sr_{tag}_3.png")
def card_strd():
    files = emu_card.extract_image(card.read_bytes())
    for name, data in files.items():
        if name.endswith("markers.strd"):
            body = data[0x16:0x16 + 784]
            n = struct.unpack(">I", body[780:784])[0]
            return n, [struct.unpack(">IIi", body[12 + 12 * k:24 + 12 * k]) for k in range(min(n, 64))]
print("strd before:", card_strd())
with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port_sr.log") as p:
    p.settle()
    p.chord("t1", "bank", settle=600); p.press("pg_amp", settle=400)
    p.chord("func", "bank", settle=500)
    for _ in range(11): p.press("up", settle=80)
    for _ in range(5): p.press("down", settle=120)
    p.press("yes", settle=400)
    tap(p, "trig1")
    for k in range(2, 8): tap(p, f"trig{k}")
    p.press("yes", settle=400)
    chopped = slices(p)
    check(chopped[0] == 7 and p.long(ST) == 0, f"7 slices chopped")
    p.press("no", settle=400)
    project_row(p, 1, "save")                          # SAVE
    print(p.card_flush())
    strd = card_strd()
    print("strd after SAVE:", strd[0] if strd else None)
    check(strd == chopped, "SAVE PROJECT writes the chopped slices to markers.strd")
    for _ in range(3): p.press("no", settle=300)       # close the menu
    p.chord("t1", "bank", settle=600); p.press("pg_amp", settle=400)
    print("editor slot", p.long(0x46c8d19c), "sel", p.long(0x400ceb3c)); p.png(OUT / "sr_edit_0.png")
    for _ in range(3):
        p.proc.command("knob 0x30 5", "ok"); p.run(300)  # a later stock edit
    edited = slices(p)
    check(edited != chopped, "a stock encoder edit after the save changes the slices")
    p.press("no", settle=400); p.press("no", settle=300)
    project_row(p, 2, "reload")                        # RELOAD
    for i in range(30):                                # until the reload has finished
        p.run(1000)
        if slices(p) != edited: break
    p.run(2000); p.png(OUT / "sr_reload_4.png")
    print("reload settled after", i + 1, "more s")
    back = slices(p)
    print("after RELOAD:", back[0], back[1][:3])
    check(back == chopped, "RELOAD brings back the saved (chopped) slices, not the later edit")
print("FAILED:", fails if fails else "none")
