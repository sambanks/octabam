"""LAZY CHOP R1 probe: open AED > SLICE > menu on an MKI port, read the LISTPOP rows."""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa
import verify_repitch as vr
from stems_panel import MenuPort

OUT = ROOT / "out/lc"
src = ROOT / "out/_src/om/src-tauri/tests/fixtures/real_device"
work = OUT / "w"; work.mkdir(parents=True, exist_ok=True)
wav = OUT / "REPITCH_440_120.wav"
if not wav.is_file():
    vr.make_loop(wav)
vr.build_project(src, work / "project", 0, 0, 120.0, 64, 127, "flex")
card = work / "card.img"
vr.stage(work / "project", card, wav)

def text(p):
    return "\n".join("".join("#" if c else "." for c in r) for r in p.screen())

def labels(p, n=12):
    lp = p.long(0x460e5e2c)
    out = []
    for i in range(n):
        a = p.long(lp + 4 * i)
        if not (0x40000000 <= a < 0x48000000):
            break
        out.append(p.cstr(a))
    return hex(lp), out

image = ROOT / sys.argv[1] if len(sys.argv) > 1 else ROOT / "out/mainos_bus.bin"
with MenuPort(image, card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port.log") as p:
    p.settle()
    p.chord("t1", "bank", settle=600)          # MKI: [TRACK] + [BANK] -> audio editor on T1's sample
    (OUT / "s1_aed.txt").write_text(text(p)); p.png(OUT / "s1_aed.png")
    p.press("pg_amp", settle=400)               # SLICE page
    (OUT / "s2_slice.txt").write_text(text(p)); p.png(OUT / "s2_slice.png")
    p.chord("func", "bank", settle=500)         # the slice menu
    (OUT / "s3_menu.txt").write_text(text(p)); p.png(OUT / "s3_menu.png")
    print("slice under marker 0x400ceb3c:", hex(p.long(0x400ceb3c)))
    print("labels:", labels(p))
    for _ in range(6):
        p.press("down", settle=200)
    (OUT / "s4_last.txt").write_text(text(p)); p.png(OUT / "s4_last.png")
    print("selection 0x460e5f54:", p.long(0x460e5f54))
    p.press("yes", settle=400)                  # run LAZY CHOP's handler (rts for now)
    (OUT / "s5_after.txt").write_text(text(p)); p.png(OUT / "s5_after.png")
    print("after YES, LISTPOP labels ptr:", hex(p.long(0x460e5e2c)))
    
print("ok")
