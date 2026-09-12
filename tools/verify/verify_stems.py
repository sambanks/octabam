#!/usr/bin/env python3
"""STEM REC -- the row, the tap and the file, checked without hardware.

    python3 tools/verify/verify_stems.py [remix]      (default: stems)

Static, from the built image: CONTROL has seven rows, the six stock ones
byte for byte, the seventh labelled STEM REC with the module's action and
id 0; the frame site jumps to the hook; the ring and the stack sit at the
top of the platform reserve, above the runtime's stage. Then, when the
port is built and the fixture exists (tools/verify/stems_fixture.py), the
runs of Tasks 14 to 16.
"""
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
BASE = 0x40000400
IMAGE = pathlib.Path("out/mainos_bus.bin")
STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
RUNTIME_ELF = pathlib.Path("out/platform/runtime/runtime.elf")
LAYOUT = pathlib.Path("out/platform")          # platform_build.LAYOUT lives here
CONTROL_DESC, CONTROL_ROWS, ROW_LEN, STOCK_N = 0x400cbd54, 0x400cc5a8, 24, 6
FRAME_SITE = 0x40004b12
fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def syms():
    out = subprocess.run(["m68k-elf-nm", str(RUNTIME_ELF)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def rd32(img, a):
    return int.from_bytes(img[a - BASE:a - BASE + 4], "big")


def static(img, stock, s):
    check("CONTROL count is 7", rd32(img, CONTROL_DESC) == 7, f"{rd32(img, CONTROL_DESC)}")
    rows = rd32(img, CONTROL_DESC + 0x18)
    check("CONTROL rows moved", rows != CONTROL_ROWS, f"0x{rows:08x}")
    a, b = rows - BASE, CONTROL_ROWS - BASE
    check("the six stock rows came across byte for byte",
          img[a:a + ROW_LEN * STOCK_N] == stock[b:b + ROW_LEN * STOCK_N])
    r7 = [rd32(img, rows + ROW_LEN * STOCK_N + 4 * k) for k in range(6)]
    check("row 7 label is stems_label", r7[0] == s["stems_label"], f"0x{r7[0]:08x}")
    check("row 7 action is stems_action", r7[2] == s["stems_action"], f"0x{r7[2]:08x}")
    check("row 7 window, pad, child and id are 0", r7[1] == r7[3] == r7[4] == r7[5] == 0, f"{r7}")
    want = b"\x4e\xb9" + s["stems_frame_hook"].to_bytes(4, "big") + b"\x4e\x71"
    got = img[FRAME_SITE - BASE:FRAME_SITE - BASE + 8]
    check("0x40004b12 is jsr stems_frame_hook; nop", got == want, got.hex())


def regions(s):
    lay = json.loads(next(LAYOUT.glob("*.json")).read_text())
    ring, stack = s["stems_ring"], s["stems_stack"]
    check("ring is 4 MiB ending at the reserve ceiling", ring + 0x400000 == lay["ceiling"],
          f"0x{ring:08x} + 4 MiB vs ceiling 0x{lay['ceiling']:08x}")
    check("stack sits just below the ring", stack + 0x2000 <= ring, f"0x{stack:08x}")
    check("the runtime's stage ends below the stack", lay["stage_end"] <= stack,
          f"stage end 0x{lay['stage_end']:08x}")


def main():
    from remix import registry
    name = sys.argv[1] if len(sys.argv) > 1 else "stems"
    if "STEM REC" not in registry.remix(name).modules:
        print(f"  [ -- ] {name} does not carry STEM REC -- nothing to check")
        return 0
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], capture_output=True, text=True, env=env)
    if r.returncode:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    img, stock, s = IMAGE.read_bytes(), STOCK.read_bytes(), syms()
    static(img, stock, s)
    regions(s)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
