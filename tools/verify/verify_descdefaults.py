#!/usr/bin/env python3
"""verify_descdefaults -- the FX choosers take a new effect's knob defaults
from its descriptor in RAM at the moment of the select.

    python3 tools/verify/verify_descdefaults.py [REMIX] [--project DIR]

The BRAIN module's card-layer defaults rest on it (docs/proposals/BRAIN.md
section 5.1): it writes the card's values over the descriptor
bytes (P+0x5e, 12 bytes) after the boot, and nothing else is patched.

Builds REMIX (default bottleservice), stages the project, and under the
port selects T2's effect through the FX2 chooser and then the FX1 chooser
(the track key, the page key twice, DOWN, YES), twice each: once as built,
once with the landed effect's twelve default bytes poked in RAM after the
load to values inside each slot's count. The live lane (0x80000810 + t*72:
FX1 page 1 +0x12, page 2 +0x32; FX2 +0x18 / +0x38) must hold the image's
defaults in the first run and the poked bytes in the second. With FX2 LOCK
in the remix the chooser's YES entry is restored in RAM for both runs.

What it cannot see: the new-part initialiser (0x40005638), which runs
inside the load, before a post-load poke; it reads the same bytes at run
time (its loads are `lea P,%a1 / lea %a1@(5e,%d2:l)`, and under the port
the read watch on stock DELAY's defaults shows it at 0x4000583c/0x4000584a
during the load).
"""
import argparse, os, pathlib, shutil, struct, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/descdefaults"
BASE = 0x40000400
LANES, IDS = 0x80000810, 0x80000ec4
FX2_TABLE, FX1_TABLE = 0x400d5fdc, 0x400d5f58          # id -> descriptor P (build_bus FX2_IDS / FX1_IDS)
UNLOCK = (0x400bc374, bytes.fromhex("40052474"))       # FX2 LOCK's poke undone: YES -> the select handler
K = dict(no=0x32, fx1=0x25, fx2=0x26, down=0x20, yes=0x31, t2=0x11)
PAGE = {"fx1": (0x12, 0x32, 0), "fx2": (0x18, 0x38, 8)}  # lane page 1, page 2; id row offset


def script(page):
    t, lines = 1500, []

    def tap(k, gap=250):
        nonlocal t
        lines.append(f"{t} key {K[k]:#x} down"); t += 40
        lines.append(f"{t} key {K[k]:#x} up"); t += gap
    tap("no", 400)                       # the boot's date prompt
    tap("t2", 400)
    tap(page, 160); tap(page, 800)       # the chooser: a double tap
    tap("down", 600)
    tap("yes", 1200)
    lines.append(f"{t} quit")
    return "\n".join(lines) + "\n"


def run(image, card, a, page, poke, tag):
    sp, dump, log, c = OUT / f"{page}.script", OUT / f"{tag}.bin", OUT / f"{tag}.txt", OUT / f"{tag}.img"
    sp.write_text(script(page))
    shutil.copy2(card, c)
    cmd = [EMU, "--image", image, "--card", c, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
           "--mkii", "--live-script", sp, "--mem-dump", f"{LANES:#x},{IDS + 16 - LANES}={dump}"]
    if poke:
        cmd += ["--poke", ";".join(f"{addr:#x}={v:#x}" for addr, v in poke)]
    with open(log, "w") as f:
        f.write(" ".join(map(str, cmd)) + "\n"); f.flush()
        r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode or "ended on quit" not in log.read_text():
        sys.exit(f"verify_descdefaults: ot_emu did not finish its script -- {log}")
    m = dump.read_bytes()
    return m[IDS - LANES:], m[72:144]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX") or "bottleservice")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--set-name", default="OCTABAM")
    ap.add_argument("--name", default="DESCDEF")
    a = ap.parse_args()
    project = a.project
    if not project and pathlib.Path("~/.octabam_project").expanduser().is_file():
        project = pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
    if not project:
        print("  [SKIP] verify_descdefaults: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_descdefaults: no port binary (make emu-cf)"); return 0
    remix = registry.remix(a.remix)
    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / "mainos.bin"
    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_descdefaults: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    img = image.read_bytes()

    def rd(addr, n):
        return img[addr - BASE:addr - BASE + n]

    pdir = pathlib.Path(project).expanduser()
    copy = OUT / "project"
    shutil.rmtree(copy, ignore_errors=True)
    copy.mkdir(parents=True)
    for f in pdir.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)
    card = OUT / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_descdefaults: stage_card failed:\n{r.stdout[-1000:]}{r.stderr[-1000:]}")

    unlock = [(UNLOCK[0] + i, b) for i, b in enumerate(UNLOCK[1])] if "FX2 LOCK" in remix.modules else []
    fails = 0
    for page in ("fx2", "fx1"):
        p1, p2, row = PAGE[page]
        ids, lane = run(image, card, a, page, unlock, f"{page}_asbuilt")
        fx = ids[row + 1]
        table = FX2_TABLE if page == "fx2" else FX1_TABLE
        P = struct.unpack(">I", rd(table + 4 * fx, 4))[0]
        defaults = rd(P + 0x5e, 12)
        counts = struct.unpack(">12I", rd(P + 0x9a, 48))
        sentinel = bytes((d + 5) % n if n > 1 else d for d, n in zip(defaults, counts))
        got = lane[p1:p1 + 6] + lane[p2:p2 + 6]
        ok = got == defaults
        print(f"  [{'ok' if ok else 'FAIL'}] {page}: T2 -> id 0x{fx:02x} (P 0x{P:08x}) lands its descriptor's defaults  {got.hex(' ')}")
        fails += not ok
        ids2, lane2 = run(image, card, a, page, unlock + [(P + 0x5e + i, v) for i, v in enumerate(sentinel)],
                          f"{page}_poked")
        got2 = lane2[p1:p1 + 6] + lane2[p2:p2 + 6]
        ok = ids2[row + 1] == fx and got2 == sentinel
        print(f"  [{'ok' if ok else 'FAIL'}] {page}: the same select with the defaults poked in RAM lands the poked bytes  {got2.hex(' ')}")
        fails += not ok
    print(f"verify_descdefaults: {'ok' if not fails else 'FAILED'} ({fails} failure(s)) -- {OUT}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
