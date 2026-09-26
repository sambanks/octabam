#!/usr/bin/env python3
"""SCENES P2 under the port: page-2 locks reach the DSP frame through the
crossfader, and a page-2 knob turned with a scene held writes the pool.

    python3 tools/verify/verify_scenesp2.py REMIX --project DIR

Stages the project's card, boots the remix's image in `ot_emu`, and:

  frame   pokes a pool into every bank's part-0 window (scene 0: T1 FX2
          MODE = 1 and TIME = 100; scene 1: TIME = 20), selects scenes 0/1,
          clears both scene-disable bytes, sets the fader and the stock
          weight table, runs 120 frames with the transport on, and reads
          T1's voice record (0x80000110, both pings): at fader 64 MODE must
          snap to the A side (1) and TIME lerp to 60; at fader 0 the B side
          alone: MODE the knob (0), TIME 20.
  editor  calls the FX2 page-2 editor `0x4003a9dc(5, 2 ticks)` on T1 with
          scene A held (0x460d169c = 1): the Part byte and the live lane
          must not move; the pool in the Part DB's part-0 window and its
          SRAM twin must hold one entry (scene 0, track 0, slot 5) whose
          value is the knob's plus the ticks' step. A second run starts from
          a poked entry of 50 and expects the same entry updated, count 1.

SKIPs without a project, without the port, or for a remix without SCENES
P2. Under a remix with Octakit the unheld editor path is not exercised: her
wrapper refuses a `--call` (no UI context; plain rig-kits faults the same).
"""
import argparse, os, pathlib, shutil, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/scenesp2verify"
BLOB, BANK_STRIDE, PART_STRIDE = 0x400e21e0, 0x9b340, 0x18b2
POOL_OFF, SEL_OFF = 0x90522, 0x8ed90
RECORDS, DBPTR, SRAM_PART = 0x80000110, 0x46c82456, 0x100a4ece
WEIGHTS, FADER, SCENE_HELD = 0x80003c60, 0x460d16c8, 0x460d169c
TRACK_CUR, PART_DISP = 0x80000000, 0x100b14cf
FX2_EDITOR = 0x4003a9dc
LANES = 0x80000810


def pokes_bytes(addr, data):
    return [f"{addr + i:#x}={v:#x}" for i, v in enumerate(data)]


def weights(xf):
    hi = (-258 * xf) & 0xffff
    lo = (0x8000 + 258 * xf) & 0xffff
    w = (hi << 16) | lo
    out = []
    for t in range(10):
        out += pokes_bytes(WEIGHTS + 4 * t, w.to_bytes(4, "big"))
    return out + pokes_bytes(FADER, xf.to_bytes(4, "big"))


def run(cmd, log):
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"verify_scenesp2: ot_emu exit {r.returncode} -- {log}")
    return log.read_text()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=registry.DEFAULT_REMIX)
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--set-name", default="OCTABAM")
    ap.add_argument("--name", default="SCENESP2")
    ap.add_argument("--image", default="")
    ap.add_argument("--out", default="", help="scratch dir (default out/scenesp2verify)")
    a = ap.parse_args()
    global OUT
    if a.out:
        OUT = pathlib.Path(a.out)
    remix = registry.remix(a.remix)
    if "SCENES P2" not in remix.modules:
        print(f"  [ -- ] verify_scenesp2: {a.remix} carries no SCENES P2"); return 0
    if not a.project:
        print("  [SKIP] verify_scenesp2: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_scenesp2: no port binary (make emu-cf)"); return 0
    pdir = pathlib.Path(a.project).expanduser()
    if not (pdir / "project.work").is_file():
        sys.exit(f"verify_scenesp2: {pdir} is not a project")
    OUT.mkdir(parents=True, exist_ok=True)
    image = pathlib.Path(a.image) if a.image else OUT / "mainos.bin"
    if not a.image:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_scenesp2: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    copy = OUT / "project"
    if copy.exists():
        shutil.rmtree(copy)
    copy.mkdir(parents=True)
    for f in pdir.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)
    card = OUT / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_scenesp2: stage_card failed:\n{r.stdout[-1000:]}{r.stderr[-1000:]}")
    base = [str(EMU), "--image", str(image), "--card", str(card), "--set", a.set_name, "--project", a.name,
            "--load-ms", "20000"]
    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    # ---- the frame pass ---------------------------------------------------
    # the pool: 'P2', 3 entries -- scene 0 / T1 / FX2 slot 5 (TIME) = 100,
    # scene 1 / T1 / slot 5 = 20, scene 0 / T1 / slot 0 (MODE) = 1 -- in part
    # 0 of every bank (the playing bank is the saved one, not bank 0)
    pool = [0x50, 0x32, 3, 0x00, 0x05, 100, 0x08, 0x05, 20, 0x00, 0x00, 1]
    common = []
    for bank in range(16):
        common += pokes_bytes(BLOB + bank * BANK_STRIDE + POOL_OFF, pool)
        common += pokes_bytes(BLOB + bank * BANK_STRIDE + SEL_OFF, [0, 1])
    common += ["0x80000006=0", "0x80000007=0"]
    for xf, want_mode, want_time in ((64, 1, 60), (0, 0, 20)):
        dump, log = OUT / f"rec_{xf}.bin", OUT / f"frames_{xf}.txt"
        cmd = base + ["--sequencer", "--internal-clock", "--frames", "120", "--dsp", "--main-level", "64",
                      "--poke-trig", "2", "--poke", ";".join(common + weights(xf)),
                      "--mem-dump", f"{RECORDS:#x},1024={dump}"]
        text = run(cmd, log)
        check(f"fader {xf}: 120 frames ran", "frames run : 120" in text)
        rec = dump.read_bytes()
        for ping in (0, 1):
            r = rec[ping * 0x200:ping * 0x200 + 64]
            check(f"fader {xf}: ping {ping} T1 MODE (hw 24 hi) = {r[48]} (want {want_mode}: "
                  f"{'the A side, a select snaps' if xf >= 64 else 'the knob, B alone'})", r[48] == want_mode)
            check(f"fader {xf}: ping {ping} T1 TIME (hw 26 lo) = {r[53]} (want {want_time})", r[53] == want_time)

    # ---- the editor with a scene held -------------------------------------
    early = f"{TRACK_CUR:#x}=0;{SCENE_HELD + 3:#x}=1;{PART_DISP:#x}=0"
    dumps = ";".join([f"{DBPTR:#x},4={OUT / 'dbptr.bin'}"]
                     + [f"{BLOB + b * BANK_STRIDE + POOL_OFF:#x},12={OUT / f'pool_{b}.bin'}" for b in range(16)]
                     + [f"{BLOB + b * BANK_STRIDE + 0x8f084:#x},6={OUT / f'p2_{b}.bin'}" for b in range(16)]
                     + [f"{SRAM_PART + POOL_OFF - 0x8ed80:#x},12={OUT / 'pool_sram.bin'}",
                        f"{LANES + 0x38:#x},6={OUT / 'lane.bin'}"])
    for seed in (None, 50):
        early2 = early
        if seed is not None:
            for b in range(16):
                early2 += ";" + ";".join(pokes_bytes(BLOB + b * BANK_STRIDE + POOL_OFF, [0x50, 0x32, 1, 0, 5, seed]))
        log = OUT / f"editor_{seed}.txt"
        text = run(base + ["--mount", "--poke-early", early2, "--call", f"{FX2_EDITOR:#x},5,2",
                           "--mem-dump", dumps], log)
        check(f"editor (seed {seed}): the call returned", "returned, d0" in text)
        db = int.from_bytes((OUT / "dbptr.bin").read_bytes(), "big")
        bank = (db - BLOB) // BANK_STRIDE
        got = (OUT / f"pool_{bank}.bin").read_bytes()
        sram = (OUT / "pool_sram.bin").read_bytes()
        lane = (OUT / "lane.bin").read_bytes()
        part = (OUT / f"p2_{bank}.bin").read_bytes()
        knob = part[5]
        check(f"editor (seed {seed}): pool magic + count 1 in bank {bank}'s part 0 ({got[:3].hex(' ')})",
              got[:3] == bytes([0x50, 0x32, 1]))
        check(f"editor (seed {seed}): entry = scene 0 / T1 / FX2 slot 5 ({got[3:5].hex(' ')})", got[3:5] == bytes([0, 5]))
        start = seed if seed is not None else knob
        check(f"editor (seed {seed}): value {got[5]} moved up from {start} by the ticks", start < got[5] <= start + 4)
        check(f"editor (seed {seed}): the SRAM twin matches ({sram[:6].hex(' ')})", sram[:6] == got[:6])
        check(f"editor (seed {seed}): the Part byte ({knob}) and the lane ({lane[5]}) did not take the turn",
              knob == lane[5] and knob != got[5])
    print(f"verify_scenesp2: {'FAIL' if fails else 'ok'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
