#!/usr/bin/env python3
"""BROWSE PATH GUARD under the ColdFire port: a file whose full path passes 259 characters no longer overwrites the
sample browser's current folder (#1258).

A blank card in set LONGSETNAME1 (12 characters) holds one folder of 125 characters under AUDIO with three WAVs
whose full paths from the card root run from 250 to 265 characters (259 is the most a 260-byte buffer holds). The firmware makes a new project; T1's QUICK
ASSIGN (a double tap), RIGHT opens the browser in AUDIO, RIGHT enters the folder, and DOWN walks the cursor over
the three files. Checked after each step: the browser's current folder (0x460e4c00) still reads
/LONGSETNAME1/AUDIO/ + the folder; the three 260-byte path buffers end in a NUL inside their 260 bytes; and NO
then RIGHT opens the browser again. On stock 1.40C the row path of the 260-character file ends with its NUL on
the folder's first byte, and the folder reads empty.

What this cannot see: a unit's timing, and the reporter's LOADING... that never ended (the folder corruption is
the cause it fits, not shown here). SKIPs when the remix has no BROWSE PATH GUARD or the port is not built.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(ROOT / "tools/verify"))

from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
PY = ROOT / ".venv/bin/python3"
SET = "LONGSETNAME1"
FOLDER = "D" * 125
CURDIR = 0x460E4C00
BUFS = (0x460E48F0, 0x460E49F8, 0x460E4AFC)      # 260 bytes each, the next one right after
NAMES = (100, 105, 109, 110, 111, 113, 115)      # full paths 250 to 265 characters from the root; 259 fits, 260 does not
AFTER48 = 0x460E49F4                             # the word the first buffer runs into


def card(work):
    src = work / "empty"
    src.mkdir()
    audio = []
    for n in NAMES:
        name = f"N{n:03d}" + "x" * (n - 4) + ".wav"
        wav = work / name
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(b"\0\0" * 4410)
        audio += ["--audio", f"{wav}:AUDIO/{FOLDER}/{name}"]
    out = work / "card.img"
    r = subprocess.run([str(PY if PY.exists() else sys.executable), str(ROOT / "tools/emu/ot_emu/stage_card.py"),
                        str(src), SET, "NOPROJ", "--tree", str(work / "tree"), "--out", str(out), *audio],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"stage_card failed:\n{r.stdout[-600:]}{r.stderr[-600:]}")
    return out


def main():
    if not EMU.is_file():
        print("  [SKIP] verify_browse_path_guard: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_browse_path_guard: no out/mainos_bus.bin (make bus)")
        return 1
    remix = os.environ.get("REMIX") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if "BROWSE PATH GUARD" not in registry.remix(remix).modules:
        print("  [SKIP] verify_browse_path_guard: the remix has no BROWSE PATH GUARD")
        return 0
    from stems_panel import MenuPort
    fails = []

    def check(what, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + detail if detail else ''}")
        if not ok:
            fails.append(what)

    want = f"/{SET}/AUDIO/{FOLDER}".encode()
    with tempfile.TemporaryDirectory() as d:
        work = pathlib.Path(d)
        img = card(work)
        try:
            with MenuPort(IMAGE, img, SET, "NOPROJ", True, log_path=str(work / "port.log")) as p:
                p.settle()
                p.press("yes", settle=1500)                      # SET DATE/TIME on a blank card
                for _ in range(2):                               # QUICK ASSIGN: a double tap on T1
                    p.key("t1", True); p.run(50); p.key("t1", False); p.run(160)
                p.run(600)
                p.press("right", settle=3000)                    # the browser, in AUDIO
                word = p.peek(AFTER48, 4)
                p.press("right", settle=3000)                    # into the folder
                for step in ["in the folder"] + [f"cursor down {i}" for i in range(1, len(NAMES))]:
                    cur = p.peek(CURDIR, 260).split(b"\0")[0]
                    check(f"{step}: the current folder reads /{SET}/AUDIO/ + the folder",
                          cur == want, f"{len(cur)} characters: {cur[:40]!r}")
                    for b in BUFS:
                        check(f"{step}: the path buffer at {b:#x} ends inside its 260 bytes", 0 in p.peek(b, 260))
                    check(f"{step}: the word after the first buffer ({AFTER48:#x}) is unchanged", p.peek(AFTER48, 4) == word,
                          f"{word.hex()} -> {p.peek(AFTER48, 4).hex()}")
                    p.press("down", settle=3000)
                p.press("no", settle=1500)
                p.press("right", settle=3000)
                cur = p.peek(CURDIR, 260).split(b"\0")[0]
                check("NO, then RIGHT: the browser opens with its folder intact", cur.startswith(f"/{SET}/AUDIO".encode()),
                      f"{cur[:40]!r}")
        except Exception as e:  # noqa: BLE001 -- a hang or a fault is the finding
            check(f"the probe completed ({type(e).__name__}: {e})", False)
    print(f"verify_browse_path_guard: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
