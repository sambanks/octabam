#!/usr/bin/env python3
"""INPUT HOLD: a project reload under the port, stock vs the image.

The fixture is OT_PROJECT through ab_fixture.prepare, then: Part B current
([STATES] PART=1 and pattern 1's Part byte), T5 THRU in Part B, inputs on
C/D (DIR_AB 0, DIR_CD 127), MASTER_TRACK 1, PHONES_MIX 0 and 165 BPM. Both
images load it, run 300 frames, post LOAD PROJECT of the same project and
run on until the bank is read and its Part applied.

Stock must show the transients, or the fixture does not reach the path:
the current Part to A, DIR CD 0, MASTER_TRACK 0, PHONES_MIX 64, T5's track
record rewritten, the tempo word to 120 BPM. The image must show none of
them across the reload, and end with the same working bank and the same
bank/pattern/Part/track bytes as stock.

Under the port the main output does not follow the mixer bytes
(tools/emu/README.md), so this checks what the frame interrupt sends, not
audio. SKIP without OT_PROJECT.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools/hw"), str(ROOT / "tools/harness")]
import ot_project as otp                                   # noqa: E402
from ab_fixture import prepare                             # noqa: E402

OUT = ROOT / "out/input-hold"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
IMAGE = ROOT / "out/mainos_bus.bin"
EMU = ROOT / "out/emu/ot_emu"
FRAMES, POST_AT = 9300, 300
BANK, BANK_LEN = 0x400e21e0, 0x9b340                       # the working bank
T5_REC = 0x80000110 + 64 * 4                                # T5's DSP instance record
# What is watched: the current Part (live, copy), the output block 0x2e..0x37,
# T5's record +0x00..+0x33 and its tempo word's high byte (+0x3e; +0x3d and
# +0x3f change every frame).
WATCH = (f"0x80000003,1;0x100b14cf,1;0x8000002e,10;"
         f"{T5_REC:#x},0x34;{T5_REC + 0x3e:#x},1")
SETTINGS = dict(PART=1, DIR_AB=0, DIR_CD=127, MASTER_TRACK=1, PHONES_MIX=0, TEMPOx24=3960)
PATTERN_PART = 0x8ee7                                       # pattern record: its Part (0 = A)


def fixture():
    project = prepare(os.environ["OT_PROJECT"], OUT / "project")
    for path in project.glob("project.*"):
        raw = path.read_bytes()
        for key, value in SETTINGS.items():
            raw, n = re.subn(rb"(?m)^" + key.encode() + rb"=[^\r\n]*",
                             key.encode() + b"=" + str(value).encode(), raw)
            if not n:
                raise SystemExit(f"[FAIL] {path.name}: no {key}=")
        path.write_bytes(raw)
    otp.set_machine_type(project, 1, 2, 5, 2, guard=False)  # Part B T5 THRU (and its saved copy)

    def part_b(data):
        data[otp.PTRN0 + PATTERN_PART] = 1                  # pattern 1 plays Part B
    otp._bank_write(project, 1, part_b, guard=False)
    card = OUT / "card.img"
    subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(project),
                    "OCTABAM", "RIG", "--tree", str(OUT / "tree"), "--out", str(card)],
                   check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    return card


def start(tag, image, card):
    d = OUT / tag
    d.mkdir(parents=True, exist_ok=True)
    name = ";".join(f"{0x100f8378 + i:#x}={c:#x}" for i, c in enumerate(b"RIG\0"))
    cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM",
           "--project", "RIG", "--sequencer", "--internal-clock", "--frames", str(FRAMES),
           "--load-ms", "90000", "--dsp", "--main-level", "64", "--audio-in", "tones",
           "--step", f"{POST_AT - 1}:dump:0x80000003,1={d}/part_before.bin",
           "--step", f"{POST_AT}:poke:{name}",
           "--step", f"{POST_AT}:call:0x40023c7c,0x100f8378",
           "--step", f"{FRAMES - 1}:dump:{BANK:#x},{BANK_LEN:#x}={d}/bank.bin;"
                     f"0x80000000,0x16={d}/state.bin",
           "--watch-mem", WATCH]
    log = open(d / "port.log", "w")
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT), d


LINE = re.compile(r"\[0x([0-9a-f]+)\] <- (0x[0-9a-f]+|0) \((\d)\) at pc (0x[0-9a-f]+).*?i=(\d+)")
# A watch reports the whole write that touches a range (the reset's long at
# 0x8000002c carries the two MIDI channel bytes): judge the watched bytes only.
WATCHED = {a for spec in WATCH.split(";")
           for start, length in [(int(spec.split(",")[0], 16), int(spec.split(",")[1], 0))]
           for a in range(start, start + length)}


def changes(d):
    """Every byte whose value changes after the first load, as (addr, old, new, pc)."""
    log = (d / "port.log").read_text()
    end = re.search(r"load run ended: .*\(instruction (\d+)\)", log)
    if not end or "STILL RUNNING" in log:
        raise SystemExit(f"[FAIL] {d.name}: the first load did not complete")
    loaded = int(end.group(1))
    if not re.search(rf"frames run : {FRAMES} ", log):
        raise SystemExit(f"[FAIL] {d.name}: the frames did not all run")
    last, out = {}, []
    for m in LINE.finditer(log):
        addr, val, n, pc, i = int(m[1], 16), int(m[2], 16), int(m[3]), m[4], int(m[5])
        for k in range(n):
            a, b = addr + k, (val >> (8 * (n - 1 - k))) & 0xff
            if a not in WATCHED:
                continue
            if last.get(a, b) != b and i > loaded:
                out.append((a, last[a], b, pc))
            last[a] = b
    return out


def main():
    if not os.environ.get("OT_PROJECT"):
        print("[SKIP] INPUT HOLD: set OT_PROJECT to a project fixture")
        return 0
    for need in (STOCK, IMAGE, EMU):
        if not need.exists():
            raise SystemExit(f"[FAIL] missing {need.relative_to(ROOT)}")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    card = fixture()
    runs = [start("stock", STOCK, card), start("image", IMAGE, card)]
    for proc, d in runs:
        if proc.wait(timeout=3600):
            raise SystemExit(f"[FAIL] {d.name}: the port exited {proc.returncode}")
    (_, stock), (_, image) = runs
    bad = 0

    def check(ok, what):
        nonlocal bad
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}")
        bad += not ok

    for d in (stock, image):
        check((d / "part_before.bin").read_bytes() == b"\x01",
              f"{d.name}: Part B is current before the reload")
    s, h = changes(stock), changes(image)
    went = {(a, b) for a, _, b, _ in s}
    check((0x80000003, 0) in went, "stock: the reset makes Part A current")
    check((0x80000030, 0) in went, "stock: DIR CD 0 for the load")
    check((0x80000034, 0) in went, "stock: MASTER_TRACK 0 for the load")
    check((0x80000032, 64) in went, "stock: PHONES_MIX 64 for the load")
    check(any(T5_REC <= a < T5_REC + 0x34 for a, _, _, _ in s), "stock: T5's record rewritten")
    check(any(a == T5_REC + 0x3e for a, _, _, _ in s), "stock: the tempo word moves")
    for a, o, b, pc in h:
        print(f"      image: {a:#010x} {o} -> {b} at {pc}")
    check(not h, "INPUT HOLD: Part, output block, T5's record and tempo never change")
    check((stock / "bank.bin").read_bytes() == (image / "bank.bin").read_bytes(),
          "INPUT HOLD: the working bank after the load equals stock's")
    check((stock / "state.bin").read_bytes() == (image / "state.bin").read_bytes(),
          "INPUT HOLD: bank/pattern/Part/track after the load equal stock's")
    print(f"verify_input_hold: {'OK' if not bad else f'{bad} FAILED'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
