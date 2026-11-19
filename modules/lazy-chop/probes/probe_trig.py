"""LAZY CHOP R2/R3 probe: a 4-slice FLEX sample on T1; what TRIG keys do on the AED SLICE page."""
import pathlib, struct, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa
import verify_repitch as vr
from stems_panel import MenuPort

OUT = ROOT / "out/lc"; work = OUT / "w4"; work.mkdir(parents=True, exist_ok=True)
src = ROOT / "out/_src/om/src-tauri/tests/fixtures/real_device"
wav = OUT / "REPITCH_440_120.wav"
vr.build_project(src, work / "project", 0, 0, 120.0, 64, 127, "flex")
mrec = vr.MACHINES["flex"][1]
N = vr.LOOP_FRAMES
for suffix in ("work", "strd"):
    pm = work / "project" / f"markers.{suffix}"
    if not pm.is_file():
        continue
    d = bytearray(pm.read_bytes()); at = 0x16 + 784 * mrec
    sl = b"".join(struct.pack(">III", i * N // 4, (i + 1) * N // 4, 0xFFFFFFFF) for i in range(4))
    d[at:at + 784] = struct.pack(">III", 0, N, 0) + sl + bytes(768 - len(sl)) + struct.pack(">I", 4)
    d[-2:] = (sum(d[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
    pm.write_bytes(bytes(d))
card = work / "card.img"; vr.stage(work / "project", card, wav)

VB, VS = 0x800049d8, 0xA8
def voices(p):
    out = []
    for i in range(16):
        v = VB + i * VS
        act = p.peek(v, 1)[0]
        if act:
            out.append((i, hex(act), "slice", struct.unpack(">b", p.peek(v + 32, 1))[0],
                        "win", hex(p.long(v + 48)), hex(p.long(v + 52)), "pos", p.long(v + 68)))
    return out
def text(p):
    return "\n".join("".join("#" if c else "." for c in r) for r in p.screen())
SEL = 0x400ceb3c
with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port5.log") as p:
    p.settle()
    p.chord("t1", "bank", settle=600); p.press("pg_amp", settle=400)
    flex1 = 0x100b14f0 + 0 * 1096
    print("slot1 count", p.long(flex1 + 1092), "slices", [p.long(flex1 + 312 + 4 * k) for k in range(8)])
    print("start: sel", p.long(SEL), voices(p)); (OUT / "t0.txt").write_text(text(p))
    CMD = 0x46c80354
    def trig_t1(tag):
        p.poke(CMD, (0x1d).to_bytes(4, "big")); 
        for ms in (50, 250, 500):
            p.run(ms if ms == 50 else ms - (50 if ms == 250 else 250))
            print(tag, f"{ms}ms", voices(p)[:1], "cmd", hex(p.long(CMD)))
        p.poke(CMD, (0x40).to_bytes(4, "big")); p.run(200)
        print(tag, "after release", voices(p)[:1])
    trig_t1("4 slices:")
    p.poke(flex1 + 1092, (0).to_bytes(4, "big"))
    trig_t1("0 slices:")
print("ok")
