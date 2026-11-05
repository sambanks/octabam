#!/usr/bin/env python3
"""SLOW LFO under the ColdFire port: MULT 7, 8 and 9 run the LFO at 1/2,
1/4 and 1/8 of 1X, and the MULT formatter prints 1/2X, 1/4X and 1/8X.

    python3 tools/verify/verify_slow_lfo.py REMIX --project DIR      (image gate)
    python3 tools/verify/verify_slow_lfo.py --stock --project DIR    (the unit alone on stock)

Stages the project on a card (`stage_card.py`) and boots the remix's built
image (`out/mainos_bus.bin`, nothing preloaded) with the sequencer on the
internal clock:
  1. Rate: track 1's LFO 1 MULT poked in its live lane (0x80000810 + 0x3e);
     the LFO's phase value (0x800010e8) over frames 100..2100 at MULT 0 (1X),
     7, 8 and 9 must be 1/2, 1/4 and 1/8 of 1X's, within 1 %.
  2. Labels: the MULT formatter (0x4003bda4) called with 0, 6, 7, 8, 9 into
     a zeroed buffer must write 1X, 64X, 1/2X, 1/4X, 1/8X.
`--stock` runs the same on the stock MAIN OS (out/raw/section_3_MAIN_OS.bin)
with unit.s assembled at a free ROM run (0x400d24d0), a `jmp` preloaded at
each detour site and the two MULT counts set to 10: the form the module was
developed in.

SKIPs without a project (OT_PROJECT / --project), without the port or the
image, and for a remix without SLOW LFO. What it cannot see: the MIDI engine
(the staged project plays no MIDI track), the LFO's audible output, the page
as drawn, a tempo change, external MIDI clock.
"""
import argparse
import os
import pathlib
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/slow-lfo"
UNIT = ROOT / "modules/slow-lfo/unit.s"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
IMAGE_BASE = 0x40000400
CAVE = 0x400d24d0
DETOURS = ((0x4000cfb0, "sl_rate_audio", 10), (0x4000cfd6, "sl_mult_audio", 6), (0x40003c16, "sl_rate_midi", 10),
           (0x40003c3c, "sl_mult_midi", 6), (0x4003bda4, "sl_format", 6))
COUNTS = (0x400d38b0, 0x400d421c)
FORMATTER = 0x4003bda4
LANE_MULT, PHASE = 0x80000810 + 0x3e, 0x800010e8
FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    FAILS += not ok
    print(f"  [{'PASS' if ok else 'FAIL'}] slow-lfo: {name}" + (f": {detail}" if detail else ""))


def stock_preload():
    """unit.s at CAVE, a jmp at every detour site and the counts at 10, for --stock."""
    work = OUT / "unit"
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run(["m68k-elf-as", "-mcpu=54455", "-o", work / "u.o", UNIT], check=True)
    subprocess.run(["m68k-elf-ld", "-e", "sl_format", f"-Ttext={CAVE:#x}", "-o", work / "u.elf", work / "u.o"], check=True)
    subprocess.run(["m68k-elf-objcopy", "-O", "binary", work / "u.elf", work / "u.bin"], check=True)
    nm = subprocess.run(["m68k-elf-nm", work / "u.elf"], capture_output=True, text=True, check=True).stdout
    syms = {f[2]: int(f[0], 16) for f in (line.split() for line in nm.splitlines()) if len(f) == 3}
    parts = [f"{CAVE:#x}={work / 'u.bin'}"]
    for site, name, length in DETOURS:
        stub = work / f"{site:x}.bin"
        stub.write_bytes(b"\x4e\xf9" + struct.pack(">I", syms[name]) + b"\x4e\x71" * ((length - 6) // 2))
        parts.append(f"{site:#x}={stub}")
    (work / "count.bin").write_bytes(struct.pack(">I", 10))
    parts += [f"{a:#x}={work / 'count.bin'}" for a in COUNTS]
    return ["--preload", ";".join(parts)]


def zero_buffer(image):
    """16 zero bytes in the image's free ROM run for the formatter to write into."""
    raw = image.read_bytes()
    for at in range(0x400d4600, 0x400e0000, 16):
        if raw[at - IMAGE_BASE:at - IMAGE_BASE + 16] == bytes(16):
            return at
    sys.exit(f"verify_slow_lfo: no 16 zero bytes in {image} for the formatter's output")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX", "slow-lfo"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--stock", action="store_true", help="the stock MAIN OS with unit.s preloaded")
    a = ap.parse_args()
    if not a.stock and "SLOW LFO" not in registry.remix(a.remix).modules:
        print(f"  [ -- ] verify_slow_lfo: {a.remix} carries no SLOW LFO")
        return 0
    if not a.project:
        print("  [SKIP] verify_slow_lfo: no project (OT_PROJECT=<dir> or --project)")
        return 0
    image = STOCK if a.stock else pathlib.Path(a.image)
    if not EMU.is_file() or not image.is_file():
        print(f"  [SKIP] verify_slow_lfo: needs the port ({EMU.relative_to(ROOT)}, make emu-cf) and {image}")
        return 0
    project = pathlib.Path(a.project).expanduser()
    if not (project / "project.work").is_file():
        sys.exit(f"verify_slow_lfo: {project} is not a project")

    OUT.mkdir(parents=True, exist_ok=True)
    card = OUT / "card.img"
    r = subprocess.run([str(PY if PY.is_file() else sys.executable), str(ROOT / "tools/emu/ot_emu/stage_card.py"),
                        str(project), "OCTABAM", "SLOW", "--tree", str(OUT / "tree"), "--out", str(card)],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_slow_lfo: stage_card failed:\n{r.stdout[-1000:]}{r.stderr[-1000:]}")
    preload = stock_preload() if a.stock else []
    form = "stock 1.40C + unit.s" if a.stock else f"{a.remix}'s image"

    def emu(*args):
        return subprocess.run([str(EMU), "--image", str(image), *preload, "--card", str(card), "--set", "OCTABAM",
                               "--project", "SLOW", "--load-ms", "20000", "--sequencer", "--internal-clock", *args],
                              cwd=ROOT, capture_output=True, text=True, timeout=600)

    moved = {}
    for mult in (0, 7, 8, 9):
        before, after = OUT / f"phase{mult}.100", OUT / f"phase{mult}.2100"
        for p in (before, after):
            p.unlink(missing_ok=True)
        emu("--frames", "2200", "--step", f"-:poke:{LANE_MULT:#x}={mult}",
            "--step", f"100:dump:{PHASE:#x},4={before}", "--step", f"2100:dump:{PHASE:#x},4={after}")
        if not before.is_file() or not after.is_file():
            check(f"{form}, MULT {mult}: the phase dumps", False, "the run wrote none")
            continue
        moved[mult] = (struct.unpack(">I", after.read_bytes())[0] - struct.unpack(">I", before.read_bytes())[0]) & 0xffffffff
    if 0 in moved and moved[0]:
        for mult, want in ((7, 0.5), (8, 0.25), (9, 0.125)):
            if mult in moved:
                got = moved[mult] / moved[0]
                check(f"{form}, MULT {mult} runs at {want:g} of 1X", abs(got - want) <= 0.01 * want,
                      f"{moved[mult]} phase units, {got:.4f} of 1X's {moved[0]}")
    else:
        check(f"{form}, MULT 0 (1X) moves the LFO", False, f"{moved.get(0)}")

    buf = zero_buffer(image)
    steps = []
    for v in (0, 6, 7, 8, 9):
        out = OUT / f"label{v}"
        out.unlink(missing_ok=True)
        steps += ["--step", f"-:call:{FORMATTER:#x},{buf:#x},{v}", "--step", f"-:dump:{buf:#x},8={out}"]
    emu("--frames", "5", *steps)
    for v, want in ((0, "1X"), (6, "64X"), (7, "1/2X"), (8, "1/4X"), (9, "1/8X")):
        out = OUT / f"label{v}"
        got = out.read_bytes().split(b"\0")[0].decode("latin1") if out.is_file() else None
        check(f"{form}, the formatter prints MULT {v}", got == want, f"{got!r}, want {want!r}")
    shutil.rmtree(OUT / "tree", ignore_errors=True)
    print(f"verify_slow_lfo: {FAILS} failed checks")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
