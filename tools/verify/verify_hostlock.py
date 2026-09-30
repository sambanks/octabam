#!/usr/bin/env python3
"""HOST LOCK under the port: on T1 and T5 the FX2 chooser's YES does what NO
does; on the other tracks it selects.

    python3 tools/verify/verify_hostlock.py REMIX --project DIR

Builds the remix, stages the project's card and runs one panel script per
track (T1, T5, T2, T8): NO (the load dialog), the track key, FUNC + FX2 (the
chooser), DOWN, YES. PC watches count the chooser's two handlers: the select
(0x40052474, stock's FX2 machine select; Octakit's wrapper sits behind it)
and NO (0x4003d440).

  T1, T5   NO ran, the select never did: the host keeps its server
  T2, T8   the select ran, NO did not
  every    no `illegal` halt (Octakit's fatal checks)

What this cannot see: the panel's redraw, and a project whose T1/T5 FX2 is
already something else (the lock keeps whatever is there; `ot_project.py
host` puts the servers back). SKIPs without a project or the port.
"""
import argparse, os, pathlib, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
SELECT, NO = 0x40052474, 0x4003D440
KEY = {"NO": 0x32, "FUNC": 0x2D, "FX2": 0x26, "DOWN": 0x20, "YES": 0x31}
TRACKS = {1: True, 5: True, 2: False, 8: False}      # track -> locked


def script(track):
    t, lines = 300, []
    for k in ("NO", 0x10 + track - 1):
        code = KEY.get(k, k)
        lines += [f"{t} key {code:#x} down", f"{t + 20} key {code:#x} up"]; t += 300
    lines += [f"{t} key {KEY['FUNC']:#x} down", f"{t + 100} key {KEY['FX2']:#x} down",
              f"{t + 150} key {KEY['FX2']:#x} up", f"{t + 250} key {KEY['FUNC']:#x} up"]
    t += 500
    for k in ("DOWN", "YES"):
        lines += [f"{t} key {KEY[k]:#x} down", f"{t + 20} key {KEY[k]:#x} up"]; t += 300
    return "\n".join(lines + [f"{t + 1000} quit"]) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    a = ap.parse_args()
    if "HOST LOCK" not in registry.remix(a.remix).modules:
        print(f"  [SKIP] verify_hostlock: {a.remix} does not carry HOST LOCK"); return 0
    if not a.project:
        print("  [SKIP] verify_hostlock: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.exists():
        print("  [SKIP] verify_hostlock: the ColdFire port is not built (make emu-cf)"); return 0
    work = pathlib.Path(tempfile.mkdtemp(prefix="hostlock."))
    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1", BUILD=os.environ.get("BUILD", "0"))
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_hostlock: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1200:]}")
    image = work / "image.bin"
    shutil.copy(ROOT / "out/mainos_bus.bin", image)
    card = work / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(a.project), "OCTABAM", "HLK",
                        "--out", str(card), "--tree", str(work / "tree")], capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_hostlock: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    norver = work / "norver.bin"
    norver.write_bytes(STOCK.read_bytes()[0xDE648:0xDE64A])

    def run(track):
        scr = work / f"t{track}.txt"
        scr.write_text(script(track))
        out = subprocess.run([str(EMU), "--image", str(image), "--card", str(card), "--set", "/OCTABAM",
                              "--project", "HLK", "--mkii", "--rtc", "host", "--preload", f"0x3ffc={norver}",
                              "--load-ms", "90000", "--live-script", str(scr),
                              "--watch-pc", f"{SELECT:#x},{NO:#x}"],
                             capture_output=True, text=True, cwd=ROOT).stdout
        (work / f"t{track}.log").write_text(out)
        return (len(re.findall(rf"at {SELECT:#x}\b", out)), len(re.findall(rf"at {NO:#x}\b", out)),
                bool(re.search(r"unimplemented opcode 4afc", out)))

    with ThreadPoolExecutor(len(TRACKS)) as ex:
        res = dict(zip(TRACKS, ex.map(run, TRACKS)))
    fails = 0
    for track, locked in TRACKS.items():
        sel, no, halt = res[track]
        ok = not halt and ((no >= 1 and sel == 0) if locked else (sel >= 1 and no == 0))
        fails += not ok
        want = "YES answered as NO, no select" if locked else "YES selects"
        print(f"  [{'PASS' if ok else 'FAIL'}] verify_hostlock: T{track} {want}  "
              f"(select {sel}, NO {no}{', HALTED' if halt else ''})")
    if fails:
        print(f"  verify_hostlock: logs in {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
