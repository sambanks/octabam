#!/usr/bin/env python3
"""BAR LED under the ColdFire port: the beat flash on the pattern's 1 asks
for the tempo LED's green half (id 39), every other flash for stock's red (38).

    python3 tools/verify/verify_bar_led.py REMIX --project DIR      (image gate)
    python3 tools/verify/verify_bar_led.py --stock --project DIR    (the unit alone on stock)

Stages the project on a card (`stage_card.py`), boots the remix's built image
(`out/mainos_bus.bin`, nothing preloaded) and runs the sequencer on the
internal clock with pattern A01's length poked to 12, 16 and 20 steps (bank
RAM 0x400e21e0 + 0x8e53, normal mode). It reads every write of the master
step 0x800065b4 and every set_led (0x40013784) call returning to 0x40056f2a,
the beat flash's return address, and passes when each flash on step 0 asks
for id 39 and every other for 38, each for 3 ticks, with at least three
greens per run. `--stock` runs the same on the stock MAIN OS
(out/raw/section_3_MAIN_OS.bin) with unit.s assembled at a free ROM run
(0x400d24d0) and a `jsr` to it preloaded over 0x40056f24: the form the
module was developed in.

SKIPs without a project (OT_PROJECT / --project), without the port or the
image, and for a remix without BAR LED. What it cannot see: the LED's colour
on a unit, external MIDI clock, a tempo change.
"""
import argparse
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/bar-led"
UNIT = ROOT / "modules/bar-led/unit.s"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
CAVE, SITE, RETURN = 0x400d24d0, 0x40056f24, 0x40056f2a
GREEN, RED, TICKS = 39, 38, 3
PATTERN_LENGTH = 0x400e21e0 + 0x8e53        # pattern A01's length byte in the bank's RAM
STEP_WRITE = re.compile(r"\[0x800065b4\] <- (0x[0-9a-f]+|0) \(2\) at pc \S+ in \S+\s+i=(\d+)")
FLASH = re.compile(r"\[\s*(\d+)\] at 0x40013784 .*?\[sp 0x[0-9a-f]+: (0x[0-9a-f]+) (0x[0-9a-f]+) (0x[0-9a-f]+)")
FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    FAILS += not ok
    print(f"  [{'PASS' if ok else 'FAIL'}] bar-led: {name}" + (f": {detail}" if detail else ""))


def flashes(log):
    """(master step at the flash, LED id, ticks) for every beat flash, in order."""
    events = [(int(i), 0, int(v, 16)) for v, i in STEP_WRITE.findall(log)]
    events += [(int(i), 1, (int(led, 16), int(n, 16)))
               for i, ret, led, n in FLASH.findall(log) if int(ret, 16) == RETURN]
    step, out = None, []
    for _, kind, value in sorted(events):
        if kind == 0:
            step = value
        else:
            out.append((step,) + value)
    return out


def stock_preload():
    """unit.s at CAVE and a `jsr` to it over the beat-flash call, for --stock."""
    work = OUT / "unit"
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run(["m68k-elf-as", "-mcpu=54455", "-o", work / "u.o", UNIT], check=True)
    subprocess.run(["m68k-elf-ld", "-e", "bl_flash", f"-Ttext={CAVE:#x}", "-o", work / "u.elf", work / "u.o"], check=True)
    subprocess.run(["m68k-elf-objcopy", "-O", "binary", work / "u.elf", work / "u.bin"], check=True)
    (work / "jsr.bin").write_bytes(b"\x4e\xb9" + struct.pack(">I", CAVE))
    return ["--preload", f"{CAVE:#x}={work / 'u.bin'};{SITE:#x}={work / 'jsr.bin'}"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX", "bar-led"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--stock", action="store_true", help="the stock MAIN OS with unit.s preloaded")
    a = ap.parse_args()
    if not a.stock and "BAR LED" not in registry.remix(a.remix).modules:
        print(f"  [ -- ] verify_bar_led: {a.remix} carries no BAR LED")
        return 0
    if not a.project:
        print("  [SKIP] verify_bar_led: no project (OT_PROJECT=<dir> or --project)")
        return 0
    image = STOCK if a.stock else pathlib.Path(a.image)
    if not EMU.is_file() or not image.is_file():
        print(f"  [SKIP] verify_bar_led: needs the port ({EMU.relative_to(ROOT)}, make emu-cf) and {image}")
        return 0
    project = pathlib.Path(a.project).expanduser()
    if not (project / "project.work").is_file():
        sys.exit(f"verify_bar_led: {project} is not a project")

    OUT.mkdir(parents=True, exist_ok=True)
    card = OUT / "card.img"
    r = subprocess.run([str(PY if PY.is_file() else sys.executable), str(ROOT / "tools/emu/ot_emu/stage_card.py"),
                        str(project), "OCTABAM", "BARLED", "--tree", str(OUT / "tree"), "--out", str(card)],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_bar_led: stage_card failed:\n{r.stdout[-1000:]}{r.stderr[-1000:]}")
    preload = stock_preload() if a.stock else []

    form = "stock 1.40C + unit.s" if a.stock else f"{a.remix}'s image"
    for length in (12, 16, 20):
        log = subprocess.run([str(EMU), "--image", str(image), *preload,
                              "--card", str(card), "--set", "OCTABAM", "--project", "BARLED", "--load-ms", "20000",
                              "--sequencer", "--internal-clock", "--frames", "20000",
                              "--step", f"-:poke:{PATTERN_LENGTH:#x}={length}",
                              "--watch-mem", "0x800065b4,2", "--watch-pc", "0x40013784"],
                             cwd=ROOT, capture_output=True, text=True, timeout=600).stdout
        (OUT / f"run{length}.log").write_text(log)
        seen = flashes(log)
        wrong = [f for f in seen if f[1:] != ((GREEN if f[0] == 0 else RED), TICKS)]
        greens = sum(1 for f in seen if f[1] == GREEN)
        text = " ".join(("G" if led == GREEN else "r") + f"@{step}" for step, led, _ in seen)
        check(f"{form}, {length} steps: green on step 0 only, at least three passes",
              bool(seen) and not wrong and greens >= 3, text or "no beat flash seen")
    shutil.rmtree(OUT / "tree", ignore_errors=True)
    print(f"verify_bar_led: {FAILS} failed checks")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
