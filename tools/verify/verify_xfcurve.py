#!/usr/bin/env python3
"""XF CURVE under the port: the crossfader's curve table and the per-track
weights after panel crossfader moves.

    python3 tools/verify/verify_xfcurve.py [REMIX]     (REMIX defaults to $REMIX)

Reads the built image (out/mainos_bus.bin, `make bus REMIX=<a remix with XF
CURVE>`) and its runtime (out/platform/runtime/runtime.elf), stages an empty
project, and boots it under ot_emu once per scenario. The crossfader is the
panel pot (`pot 0..255`, xf = pot / 2). After each run the table at
0x400bcd90, the ten weight longs at 0x80003c60 and xf are dumped.

Checks, every scenario: the table is one of the module's curves, the one
expected; each weight long is stock's formula on that table at xf
((w << 16) | ((0x8000 - w) & 0xffff), as 0x40061e4a..0x40061e58 builds it).
LINEAR's generated table equals the stock image's bytes.

With BRAIN in the remix, CURVE is poked in BRAIN's value table
(brain_v_octabam_xfcurve_1) as the menu would set it:
  default  no poke, fader moved: the table is stock's (LINEAR), never written
  cut      CURVE = CUT, fader moved: the table is CUT
  back     CUT, fader moved, CURVE = LINEAR, fader moved: stock's table again
  scurve   CURVE = S-CURVE, fader moved
  cuta     CURVE = CUT A, fader inside the dead step at the A end
Without BRAIN (a pin): one scenario, the pinned curve after a fader move.

Not covered: MIDI CC 48 (the second hook site runs the same routine; no
scenario sends the CC), and the BRAIN menu row itself.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(ROOT / "tools/emu")); import emu_card  # noqa: E402

IMAGE = ROOT / "out/mainos_bus.bin"
RUNTIME = ROOT / "out/platform/runtime/runtime.elf"
EMU = ROOT / "out/emu/ot_emu"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
BASE = 0x40000400
CURVE, WEIGHTS, XF = 0x400BCD90, 0x80003C60, 0x460D16C8

fails = 0


def check(name, ok, info=""):
    global fails
    print(("  [PASS] " if ok else "  [FAIL] ") + name + (("  " + info) if info else ""), flush=True)
    if not ok:
        fails += 1


def manifest():
    spec = importlib.util.spec_from_file_location("xfc_manifest", ROOT / "modules/xfcurve/manifest.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def symbols():
    out = subprocess.check_output(["m68k-elf-nm", str(RUNTIME)], text=True)
    return {n: int(a, 16) for a, _, n in re.findall(r"^([0-9a-f]+) (\w) (\S+)$", out, re.M)}


def weight(t, x):
    w = t[x]
    return (((w & 0xFFFF) << 16) | ((0xFFFF8000 - w) & 0xFFFF)) & 0xFFFFFFFF


def run(work, card, name, lines):
    script = work / f"{name}.txt"
    script.write_text("\n".join(lines + ["%d quit" % (int(lines[-1].split()[0]) + 1000)]) + "\n")
    dump = f"{WEIGHTS:#x},40={work}/{name}.w;{CURVE:#x},256={work}/{name}.t;{XF:#x},4={work}/{name}.x"
    log = work / f"{name}.log"
    with log.open("w") as f:
        subprocess.run([str(EMU), "--image", str(IMAGE), "--mkii", "--card", str(card), "--set", "OCTABAM",
                        "--project", "XFC", "--load-ms", "90000", "--live-script", str(script),
                        "--mem-dump", dump], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=900)
    ended = "ended on quit" in log.read_text()
    t = list(struct.unpack(">128h", (work / f"{name}.t").read_bytes()))
    w = struct.unpack(">10I", (work / f"{name}.w").read_bytes())
    x = struct.unpack(">i", (work / f"{name}.x").read_bytes())[0]
    return ended, t, w, x


def main(argv):
    remix = (argv[0] if argv else os.environ.get("REMIX", "")).strip()
    if not EMU.is_file():
        print("  [FAIL] the ColdFire port is not built (make emu-cf)"); return 1
    if not IMAGE.is_file() or not RUNTIME.is_file():
        print("  [FAIL] build the image first (make bus REMIX=<a remix with XF CURVE>)"); return 1
    m = manifest()
    tabs = {n: m.table(f) for n, f in m.CURVES}
    raw = STOCK.read_bytes()
    stock = list(struct.unpack(">128h", raw[CURVE - BASE:CURVE - BASE + 256]))
    check("LINEAR's generated table is stock's 0x400bcd90", tabs["LINEAR"] == stock)
    sym = symbols()
    if "xfc_hook" not in sym:
        print("  [FAIL] the runtime carries no XF CURVE (xfc_hook)"); return 1
    value = sym.get("brain_v_octabam_xfcurve_1")
    poke = (lambda ms, i: f"{ms} poke {value + 3:#x}={i}") if value else None
    idx = {n: i for i, n in enumerate(m.LABELS)}
    if value:
        cases = {
            "default": (["500 pot 0", "1500 pot 200"], "LINEAR", 100),
            "cut": ([poke(300, idx["CUT"]), "500 pot 0", "1500 pot 200"], "CUT", 100),
            "back": ([poke(300, idx["CUT"]), "500 pot 0", "1500 pot 200", poke(2000, idx["LINEAR"]),
                      "2500 pot 150"], "LINEAR", 75),
            "scurve": ([poke(300, idx["S-CURVE"]), "500 pot 0", "1500 pot 160"], "S-CURVE", 80),
            "cuta": ([poke(300, idx["CUT A"]), "500 pot 0", "1500 pot 252"], "CUT A", 126),
        }
    else:
        sys.path.insert(0, str(ROOT / "tools"))
        from remix import brain, registry  # noqa: E402
        pinned = None
        try:
            pinned = brain.value(registry.remix(remix), registry.modules(), m.STORE_ID, "CURVE")
        except Exception as e:  # noqa: BLE001
            print(f"  [FAIL] cannot resolve CURVE for remix {remix!r}: {e}"); return 1
        cases = {"pinned": (["500 pot 0", "1500 pot 200"], pinned, 100)}
    with tempfile.TemporaryDirectory(prefix="xfcurve_") as d:
        work = pathlib.Path(d)
        (work / "proj").mkdir()
        card, _ = emu_card.stage_project(work / "proj", "OCTABAM", "XFC", tree=work / "tree")
        (work / "card.img").write_bytes(card)
        with ThreadPoolExecutor(max_workers=len(cases)) as ex:
            res = {n: ex.submit(run, work, work / "card.img", n, c[0]) for n, c in cases.items()}
        for n, (_, want, xf_want) in cases.items():
            ended, t, w, x = res[n].result()
            got = [k for k, v in tabs.items() if v == t]
            check(f"{n}: the script ran to its end", ended)
            check(f"{n}: xf {xf_want}", x == xf_want, f"xf {x}")
            check(f"{n}: the table is {want}", got == [want], f"table {got or 'none of the curves'}")
            check(f"{n}: the ten weights are the table's at xf", all(v == weight(t, x) for v in w),
                  f"T1 {w[0]:#010x}")
    print(f"verify_xfcurve: {'FAIL' if fails else 'PASS'} ({fails} failed)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
