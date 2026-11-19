"""LAZY CHOP + BUFFER SAVER: a chopped recorder take saved by SAVE PROJECT keeps its slices in the .ot."""
import pathlib, re, struct, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel", "tools/emu"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa
import emu_card
from stems_panel import MenuPort
OUT = ROOT / "out/lc"; card = OUT / "wr" / "card.img"          # T1 FLEX on R1 (test_rec.py staged it)
m = (ROOT / "out/platform/runtime/runtime.map").read_text()
sym = lambda n: int(re.search(rf"(0x[0-9a-f]+)\s+{n}\n", m).group(1), 16)
ST = sym("lc_state")
R1 = 0x100b14f0 + 128 * 1096
fails = []
def check(c, what):
    print(("PASS " if c else "FAIL ") + what)
    if not c: fails.append(what)
def slices(p, rec=R1):
    n = p.long(rec + 1092)
    return n, [struct.unpack(">IIi", p.peek(rec + 312 + 12 * k, 12)) for k in range(min(n, 64))]
def tap(p, k, gap=150):
    p.key(k, True); p.run(20); p.key(k, False); p.run(gap - 20)
def project_row(p, row, tag):
    p.open_menu(); p.press("left")
    for _ in range(6): p.press("up")
    p.press("right", settle=300)
    for _ in range(8): p.press("up", settle=80)
    for _ in range(row): p.press("down", settle=120)
    p.press("yes", settle=800); p.png(OUT / f"bs_{tag}_1.png")
def ot_files():
    files = emu_card.extract_image(card.read_bytes())
    out = {}
    for name, data in files.items():
        if name.lower().endswith(".ot") and len(data) >= 832:
            n = struct.unpack(">I", data[826:830])[0]
            out[name] = (n, [struct.unpack(">IIi", data[58 + 12 * k:70 + 12 * k]) for k in range(min(n, 64))])
    return out, files
before, _ = ot_files()
print(".ot before:", list(before))
with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port_bs.log") as p:
    p.settle()
    p.chord("func", "recab", settle=400)               # RECORDING SETUP
    p.proc.command("knob 0x33 8", "ok"); p.run(300)    # TRIG ONE -> HOLD (as verify_buffer_saver)
    p.press("no", settle=300)
    p.key("t1", True); p.run(40); p.key("recab", True); p.run(1500)
    p.key("recab", False); p.run(40); p.key("t1", False); p.run(500)
    take = p.long(R1 + 304)
    print("take:", take, "samples")
    check(20000 < take < 120000, f"a short HOLD take in R1 ({take} samples)")
    p.chord("recab", "bank", settle=600)
    check(p.long(0x46c8d19c) == 128, "the editor opens on R1")
    p.press("pg_amp", settle=400)
    p.chord("func", "bank", settle=500)
    for _ in range(11): p.press("up", settle=80)
    for _ in range(2): p.press("down", settle=120)    # off a slice: LAZY CHOP is row 3
    p.press("yes", settle=400)
    tap(p, "trig1")
    for k in range(2, 7): tap(p, f"trig{k}")
    p.press("yes", settle=400)
    chopped = slices(p)
    print("chopped:", chopped)
    check(chopped[0] == 6 and p.long(ST) == 0, "6 slices on the take")
    p.press("no", settle=400); p.press("no", settle=300)
    project_row(p, 1, "save")                          # SAVE: BUFFER SAVER asks first
    p.png(OUT / "bs_dialog.png")
    p.press("yes", settle=1500); p.png(OUT / "bs_after_yes.png")   # SAVE SAMPLES? YES
    p.run(4000); p.png(OUT / "bs_2.png")
    p.press("yes", settle=1000); p.png(OUT / "bs_3.png")           # stock's SAVE PROJECT? YES
    p.run(6000); p.png(OUT / "bs_4.png")
    after_ram = slices(p)
    check(after_ram == chopped, "after the save R1 still holds the chopped slices")
    name = p.peek(0x46c922c4 + 44 * 128 + 24, 24).split(b"\0")[0].decode("latin1")
    print("R1 name after save:", name)
    print(p.card_flush())
ots, files = ot_files()
new = {k: v for k, v in ots.items() if k not in before}
print(".ot new:", {k: v[0] for k, v in new.items()})
check(any(v == chopped for v in new.values()), "the saved take's .ot holds the chopped slices")
wavs = [k for k in files if k.lower().endswith(".wav") and "R1-" in k]
print("R1 wavs:", wavs)
print("FAILED:", fails if fails else "none")
