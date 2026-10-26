#!/usr/bin/env python3
"""A project that stores an FX2 id of 32 or more keeps it through the load, in the 64-id layout.

    python3 tools/verify/verify_ids64_load.py [--project DIR]       (default: $OT_PROJECT or ~/.octabam_project)

The stock Part validator (0x40002318) clamps each track's FX2 id byte to 31 as the project loads, so an id the 64-id
layout assigns above that (BBD on 0x25 in `test/ids64`) arrived as 0x1f and the slot showed nothing (a unit, 27 Oct 2026).
`idspace.convert` raises the clamp to 63. This builds `test/ids64`, writes the id into a copy of the project's bank files
(a poke into the Part would bypass the validator, which runs at load), loads it under the port and reads the live FX2 ids
(0x80000ecc..). Track 1's must be 0x25.
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT / "tools/hw")); sys.path.insert(0, str(ROOT / "tools/verify"))
import toolpath  # noqa: E402,F401
import ot_project  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/ids64load"
FX2_LIVE = 0x80000ECC
REMIX, FX_ID = "test/ids64", 0x25


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    a = ap.parse_args()
    project = a.project
    if not project and pathlib.Path("~/.octabam_project").expanduser().is_file():
        project = pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
    if not project:
        print("  [SKIP] verify_ids64_load: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)")
        return 0
    if not EMU.is_file():
        print("  [SKIP] verify_ids64_load: no port binary (make emu-cf)")
        return 0
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "project").mkdir(parents=True)
    env = dict(os.environ, REMIX=REMIX, XBUS="1", SPEC="1", BUILD="0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_ids64_load: building {REMIX} failed:\n{(r.stdout + r.stderr)[-1200:]}")
    shutil.copy2(ROOT / "out/mainos_bus.bin", OUT / "mainos.bin")
    for f in pathlib.Path(project).expanduser().iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, OUT / "project" / f.name)
    ot_project.set_fx(OUT / "project", "fx2", 1, FX_ID, guard=False)           # in every part of every bank
    card = OUT / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(OUT / "project"), "BRAINSET", "BRAINPRJ",
                        "--tree", str(OUT / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_ids64_load: stage_card failed:\n{r.stdout[-600:]}{r.stderr[-600:]}")
    (OUT / "s.script").write_text("2000 key 0x32 down\n2040 key 0x32 up\n4500 quit\n")      # the date prompt, then stop
    ids = OUT / "ids.bin"
    r = subprocess.run([str(EMU), "--image", str(OUT / "mainos.bin"), "--card", str(card), "--set", "BRAINSET", "--project",
                        "BRAINPRJ", "--load-ms", "90000", "--mkii", "--dsp", "--frame", "--live-script", str(OUT / "s.script"),
                        "--mem-dump", f"{FX2_LIVE:#x},8={ids}"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode or not ids.is_file():
        sys.exit(f"verify_ids64_load: the port run failed:\n{(r.stdout + r.stderr)[-800:]}")
    got = ids.read_bytes()[0]
    ok = got == FX_ID
    print(f"  [{'PASS' if ok else 'FAIL'}] track 1's FX2 id is 0x{FX_ID:02x} after the load of a project that stores it"
          f"  (live id 0x{got:02x}; a clamp to 31 reads 0x1f)")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
