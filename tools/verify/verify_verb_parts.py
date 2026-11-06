#!/usr/bin/env python3
"""VERB PARTS under the ColdFire port: a Part saved with a stock reverb opens on its VERBERATION row at the row's
defaults, and nothing else in it moves.

    OT_PROJECT=<dir> .venv/bin/python3 tools/verify/verify_verb_parts.py [REMIX]      (default octabam-verbs)

Every Part of every bank of a copy of the project gets, on FX2:
  T2  0x16 (DARK REV's id, VERB HALL here)   DARK's own values, page-2 slots 9 and 10 at 0     -> HALL's defaults
  T4  0x15 (SPRING REV's id, VERB ROOM)       a stock-looking page, slots 9 and 10 at 0          -> ROOM's defaults
  T3  0x14 (PLATE REV's id, VERB PLATE)       slot 9 at 4: a Part saved with the row             -> untouched
  T5  0x1a (VERBERATION)                      slots 9 and 10 at 0, but not a row's id            -> untouched
The port boots the image and loads the project; the load applies one Part (0x40009094). Each bank's Part 1 is
dumped: the applied one must carry the conversion, and T3 and T5 must be as written in every bank.
What it cannot see: the unit's own load timing; a Part applied later (another bank, a pattern change through
0x40009e00) converts when it is applied, which this run does not reach.
"""
import argparse, os, pathlib, shutil, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/verb_parts"
BANK0, BANK_STRIDE, PART_STRIDE = 0x40170F60, 0x9B340, 0x18B2     # bank 1's working Part 1 (0x400e21e0 + 0x8ed80)
P1, P2 = 0x12C, 0x304                                              # FX2 page 1 + t*24, page 2 + t*30 (PARAM_PAGES 5a)
FAILS = []

DARK_P1, DARK_P2 = [24, 0, 127, 0, 127, 0], [0, 64, 0, 0, 0, 0]           # DARK REV's own defaults
SPRING_P1, SPRING_P2 = [23, 9, 9, 20, 127, 0], [1, 64, 9, 0, 0, 9]
PLATE_ROW_P1, PLATE_ROW_P2 = [10, 20, 30, 40, 50, 60], [1, 2, 3, 4, 5, 6]  # slot 9 = 4: a row's own Part
VERB_P1, VERB_P2 = [7, 7, 7, 7, 7, 7], [0, 7, 7, 0, 0, 7]


def check(what, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {what}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(what)


def fx2(blob, t):
    return list(blob[P1 + 24 * t:P1 + 24 * t + 6]), list(blob[P2 + 30 * t:P2 + 30 * t + 6])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default="octabam-verbs")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--ms", type=int, default=4000)
    a = ap.parse_args()
    project = a.project or (pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
                            if pathlib.Path("~/.octabam_project").expanduser().is_file() else "")
    if not project:
        print("  [SKIP] verify_verb_parts: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_verb_parts: no port binary (make emu-cf)"); return 0
    from remix import registry
    sys.path.insert(0, str(ROOT / "tools/hw")); import ot_project as otp
    mods = registry.modules()
    want = {k: [p.default or 0 for p in mods[k].params] for k in ("VERB PLATE", "VERB ROOM", "VERB HALL")}
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1", BUILD=os.environ.get("BUILD", "0"))
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_verb_parts: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    if "VERB PARTS:" not in r.stdout:
        sys.exit(f"verify_verb_parts: {a.remix} does not carry VERB PARTS")
    image = OUT / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    copy = OUT / "project"
    shutil.rmtree(copy, ignore_errors=True)
    copy.mkdir(parents=True)
    for f in pathlib.Path(project).expanduser().iterdir():
        if f.is_file() and f.suffix.lower() in (".work", ".strd"):
            shutil.copy2(f, copy / f.name)
    otp.set_fx(copy, "fx2", 2, 0x16, page=DARK_P1, page2=DARK_P2, guard=False)
    otp.set_fx(copy, "fx2", 4, 0x15, page=SPRING_P1, page2=SPRING_P2, guard=False)
    otp.set_fx(copy, "fx2", 3, 0x14, page=PLATE_ROW_P1, page2=PLATE_ROW_P2, guard=False)
    otp.set_fx(copy, "fx2", 5, 0x1A, page=VERB_P1, page2=VERB_P2, guard=False)
    card = OUT / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), "BRAINSET", "BRAINPRJ",
                        "--tree", str(OUT / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_verb_parts: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    (OUT / "run.script").write_text(f"{a.ms} quit\n")
    dumps = [(BANK0 + b * BANK_STRIDE, OUT / f"bank{b + 1:02d}.bin") for b in range(16)]
    cmd = [EMU, "--image", image, "--card", card, "--set", "BRAINSET", "--project", "BRAINPRJ", "--load-ms", "90000",
           "--mkii", "--dsp", "--frame", "--live-script", OUT / "run.script",
           "--mem-dump", ";".join(f"{ad:#x},{PART_STRIDE}={f}" for ad, f in dumps)]
    with open(OUT / "run.txt", "w") as fh:
        rc = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
    text = (OUT / "run.txt").read_text(errors="replace")
    if rc or "ended on quit" not in text:
        sys.exit(f"verify_verb_parts: the port run did not finish -- {OUT / 'run.txt'}")
    blobs = {b + 1: f.read_bytes() for b, (_, f) in enumerate(dumps)}
    hall = (want["VERB HALL"][:6], want["VERB HALL"][6:])
    room = (want["VERB ROOM"][:6], want["VERB ROOM"][6:])
    applied = [b for b, blob in blobs.items() if fx2(blob, 1) == hall]
    print("the applied Part:")
    check("one bank's Part 1 carries VERB HALL's defaults on T2 (DARK REV's values, slots 9 and 10 at 0)",
          len(applied) >= 1, f"banks {applied}")
    for b in applied:
        check(f"bank {b}: T4 (SPRING REV's id, slots 9 and 10 at 0) carries VERB ROOM's defaults",
              fx2(blobs[b], 3) == room, f"{fx2(blobs[b], 3)}")
    print("left alone:")
    check("T3 (PLATE REV's id, slot 9 at 4: a row's own Part) is as written in every bank",
          all(fx2(blob, 2) == (PLATE_ROW_P1, PLATE_ROW_P2) for blob in blobs.values()))
    check("T5 (VERBERATION's own id, slots 9 and 10 at 0) is as written in every bank",
          all(fx2(blob, 4) == (VERB_P1, VERB_P2) for blob in blobs.values()))
    others = [b for b in blobs if b not in applied]
    check("a Part not yet applied keeps its stock values (it converts when it is applied)",
          all(fx2(blobs[b], 1) == (DARK_P1, DARK_P2) for b in others), f"{len(others)} banks")
    print("PASS" if not FAILS else "FAIL")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
