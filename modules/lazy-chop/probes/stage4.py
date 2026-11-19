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

print("staged", card)
