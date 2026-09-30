#!/usr/bin/env python3
"""OCTAKIT MIRROR under the port: page-key + CLEAR / COPY / PASTE complete on
an Octakit image instead of halting in her page-clipboard check.

    python3 tools/verify/verify_octakit_mirror.py REMIX --project DIR

Builds the remix twice -- as selected (OCTAKIT MIRROR appended with OCTAKIT)
and a CONTROL without it (OCTABAM_NO_OCTAKIT_MIRROR=1) -- stages the
project's card and runs one panel script on each: AMP + CLEAR, FX1 + CLEAR,
AMP + COPY, T2, AMP + PASTE.

  control  must halt on Octakit's `illegal` (gk_page_clipboard_fatal): the
           project triggers the fault. A project that does not (one Octakit
           has never staged a Kit into -- no kits3a/kits3b) cannot show the
           fix, and the gate SKIPs saying so rather than pass blind
  fixed    runs the whole script: CLEAR PAGE twice, COPY PAGE and PASTE
           PAGE are shown (the stock popups, 0x4005a2b8), no halt

What this cannot see: the unit's SRAM from earlier sessions (the port boots
it zeroed), and whether a Kit Octakit stages later (a Kit load, a part
reload) opens the same gap -- the sync runs before every CLEAR/PASTE, so
the timing of the gap does not matter to the fix.
SKIPs without a project, without the port, or for a remix without OCTAKIT.
"""
import argparse, os, pathlib, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
MESSAGE = 0x4005A2B8
TEXTS = {0x400B48C2: "CLEAR PAGE", 0x400B48CD: "PASTE PAGE", 0x400B48D8: "COPY PAGE"}
KEY = {"NO": 0x32, "AMP": 0x23, "FX1": 0x25, "COPY": 0x29, "CLEAR": 0x28, "PASTE": 0x27, "T2": 0x11}
SCRIPT = [("NO",), ("AMP",), ("AMP", "CLEAR"), ("FX1", "CLEAR"), ("AMP",),
          ("AMP", "COPY"), ("T2",), ("AMP", "PASTE")]


def script_lines():
    t, lines = 300, []
    for step in SCRIPT:
        if len(step) == 1:
            lines += [f"{t} key {KEY[step[0]]:#x} down", f"{t + 20} key {KEY[step[0]]:#x} up"]
        else:
            held, press = step
            lines += [f"{t} key {KEY[held]:#x} down", f"{t + 100} key {KEY[press]:#x} down",
                      f"{t + 150} key {KEY[press]:#x} up", f"{t + 250} key {KEY[held]:#x} up"]
        t += 400
    return lines + [f"{t + 1000} quit"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    a = ap.parse_args()
    if "OCTAKIT" not in registry.remix(a.remix).modules:
        print(f"  [SKIP] verify_octakit_mirror: {a.remix} does not carry OCTAKIT"); return 0
    if not a.project:
        print("  [SKIP] verify_octakit_mirror: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.exists():
        print("  [SKIP] verify_octakit_mirror: the ColdFire port is not built (make emu-cf)"); return 0
    work = pathlib.Path(tempfile.mkdtemp(prefix="okmirror."))
    images = {}
    for tag, extra in (("fixed", {}), ("control", {"OCTABAM_NO_OCTAKIT_MIRROR": "1"})):
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1", BUILD=os.environ.get("BUILD", "0"), **extra)
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_octakit_mirror: building {a.remix} ({tag}) failed:\n{(r.stdout + r.stderr)[-1200:]}")
        images[tag] = work / f"{tag}.bin"
        shutil.copy(ROOT / "out/mainos_bus.bin", images[tag])
    card = work / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(a.project), "OCTABAM", "OKM",
                        "--out", str(card), "--tree", str(work / "tree")], capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_octakit_mirror: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    norver = work / "norver.bin"
    stock = STOCK.read_bytes()
    norver.write_bytes(stock[0xDE648:0xDE64A])
    scr = work / "script.txt"
    scr.write_text("\n".join(script_lines()) + "\n")

    def run(tag):
        out = subprocess.run([str(EMU), "--image", str(images[tag]), "--card", str(card), "--set", "/OCTABAM",
                              "--project", "OKM", "--mkii", "--rtc", "host", "--preload", f"0x3ffc={norver}",
                              "--load-ms", "90000", "--live-script", str(scr), "--watch-pc", f"{MESSAGE:#x}"],
                             capture_output=True, text=True, cwd=ROOT).stdout
        (work / f"{tag}.log").write_text(out)
        halted = bool(re.search(r"unimplemented opcode 4afc", out))
        shown = [TEXTS.get(int(m.group(1), 16), m.group(1)) for m in
                 re.finditer(r"at 0x4005a2b8 .*?\[sp 0x[0-9a-f]+: 0x[0-9a-f]+ (0x[0-9a-f]+)", out)]
        return halted, shown

    with ThreadPoolExecutor(2) as ex:
        fc, ff = ex.submit(run, "control"), ex.submit(run, "fixed")
        (c_halt, c_shown), (f_halt, f_shown) = fc.result(), ff.result()
    if not c_halt:
        print(f"  [SKIP] verify_octakit_mirror: the control did not halt on {pathlib.Path(a.project).name} "
              f"(shown: {', '.join(c_shown) or 'nothing'}) -- a project Octakit has staged a Kit into "
              f"(kits3a/kits3b) is needed to see the fault")
        shutil.rmtree(work, ignore_errors=True)
        return 0
    fails = 0

    def check(label, ok, detail):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] verify_octakit_mirror: {label}  ({detail})")

    check("control (no OCTAKIT MIRROR): page CLEAR halts in Octakit's page-clipboard check",
          c_halt, "halted after: " + (", ".join(c_shown) or "nothing"))
    want = ["CLEAR PAGE", "CLEAR PAGE", "COPY PAGE", "PASTE PAGE"]
    check("with OCTAKIT MIRROR: AMP+CLEAR, FX1+CLEAR, AMP+COPY and AMP+PASTE complete, no halt",
          not f_halt and f_shown == want, ("HALTED; " if f_halt else "") + "shown: " + ", ".join(f_shown))
    if fails:
        print(f"  verify_octakit_mirror: logs in {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
