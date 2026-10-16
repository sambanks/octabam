#!/usr/bin/env python3
"""BUFFER SAVER under the port: SAVE PROJECT (FUNC + PROJ) after a take,
in three scenarios, each its own boot.

Each boots the built image (out/mainos_bus.bin) on a private card holding a
saved, empty project (project.work and project.strd, so SAVE takes stock's
CONTINUE? path rather than SAVE TO NEW). RECORDING SETUP 1 sets TRIG to
HOLD, so TRACK 1 + REC AB held for one second makes a short take into
recorder buffer 1. The port's clock is unset, so the automatic name is
R1-000000-0000. A YES/NO dialog is told apart by its lines: the module's
SAVE SAMPLES? passes its own table (in DRAM), stock's CONTINUE? a stack
copy.

  yes      take, FUNC + PROJ, YES (SAVE SAMPLES?), YES (CONTINUE?), then
           FUNC + PROJ again, YES (CONTINUE?). Wanted: R1-000000-0000.wav
           and .ot, the project's SLOT=129 path on it, one mode-2 save by
           the module, SAVE SAMPLES? once (not on the second save).
  taken    as yes up to the first CONTINUE?, on a card that already holds
           R1-000000-0000.wav: the take is saved as R1-000000-0000-2.wav,
           the project points at it, the old file is unchanged.
  no       take, FUNC + PROJ, NO (SAVE SAMPLES?), YES (CONTINUE?). Wanted:
           no WAV, SLOT=129 with no path, the project saved, no mode-2 save.

Never flashes or talks to hardware.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(ROOT / "tools/emu")); import emu_card  # noqa: E402
EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
STAGE_CARD = ROOT / "tools/emu/ot_emu/stage_card.py"
MODE = 0x460BCFC8                    # the sample save's mode; the module writes 2
DIALOG_ENTRY = 0x4006D57C            # stock's YES/NO dialog (title, lines n, lines, 3, callback)
DRAM = (0x40A00000, 0x46000000)      # the module's own data, where SAVE SAMPLES?'s lines live
SAVE_PROJECT_TITLE = 0x400B3820      # "SAVE PROJECT", both dialogs' title
AUDIO = "OCTABAM/AUDIO/"
PROJECT = "OCTABAM/BUFSAVE/project.strd"

# Panel key codes (tools/panel/key_map.json: row 0x20+r, bit b -> r*8+b).
NO, YES, FUNC, REC_AB, T1, PROJ = 0x32, 0x31, 0x2D, 0x2B, 0x10, 0x1C
SETUP = [f"500 key {NO:#x} down", f"560 key {NO:#x} up",
         f"800 key {FUNC:#x} down", f"860 key {REC_AB:#x} down",
         f"920 key {REC_AB:#x} up", f"960 key {FUNC:#x} up",
         "1300 enc 3 8",                                   # TRIG ONE -> HOLD
         f"1600 key {NO:#x} down", f"1660 key {NO:#x} up"]


def take(ms):
    """TRACK 1 + REC AB held one second under TRIG HOLD."""
    return [f"{ms} key {T1:#x} down", f"{ms + 40} key {REC_AB:#x} down",
            f"{ms + 1040} key {REC_AB:#x} up", f"{ms + 1080} key {T1:#x} up"]


def save(ms):
    return [f"{ms} key {FUNC:#x} down", f"{ms + 60} key {PROJ:#x} down",
            f"{ms + 120} key {PROJ:#x} up", f"{ms + 180} key {FUNC:#x} up"]


def press(ms, key):
    return [f"{ms} key {key:#x} down", f"{ms + 60} key {key:#x} up"]


def _wav(frames):
    """A 16-bit stereo 44.1 kHz WAV of `frames` frames of a ramp."""
    data = b"".join(struct.pack("<hh", i, -i) for i in range(frames))
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 2, 44100, 176400, 4, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


def fail(message, output=""):
    print(f"  [FAIL] verify_buffer_saver: {message}")
    if output:
        print(output[-4000:])
    return 1


def run(work, card, name, script, quit_ms):
    card = card[name] if isinstance(card, dict) else card
    path = work / f"{name}.script"
    path.write_text("\n".join(script + [f"{quit_ms} quit"]) + "\n")
    out_card = work / f"{name}.img"
    args = [str(EMU), "--image", str(IMAGE), "--card", str(card), "--card-out", str(out_card),
            "--set", "OCTABAM", "--project", "BUFSAVE", "--load-ms", "90000",
            "--mkii", "--dsp", "--main-level", "64", "--audio-in", "tones",
            "--watch-mem", f"{MODE:#x},4", "--watch-pc", f"{DIALOG_ENTRY:#x}",
            "--live-script", str(path)]
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=1800)
    files = emu_card.extract_image(out_card.read_bytes()) if out_card.is_file() else {}
    return name, r.returncode, r.stdout + r.stderr, files


def writes(output, addr):
    """(time, value, pc) for each watched write to addr, in order."""
    return [(float(t), int(v, 0), int(pc, 16)) for t, v, pc in re.findall(
        rf"\[\s*([\d.]+)\] \[{addr:#x}\] <- (\S+) \(\d\) at pc (0x[0-9a-f]+)", output)]


def dialogs(output):
    """(ours, stock) counts of SAVE PROJECT dialogs opened (the words at the
    entry's sp: return address, title, line count, lines): lines in the
    module's DRAM are SAVE SAMPLES?, the rest stock's CONTINUE?. Other
    dialogs (the staged card's load message at boot) are not counted."""
    ours = stock = 0
    for words in re.findall(rf"at {DIALOG_ENTRY:#x} .*?\[sp 0x[0-9a-f]+: ([^\]]+)\]", output):
        w = [int(x, 16) for x in words.split()]
        if len(w) < 4 or w[1] != SAVE_PROJECT_TITLE:
            continue
        if DRAM[0] <= w[3] < DRAM[1]:
            ours += 1
        else:
            stock += 1
    return ours, stock


def slot129(files):
    text = files.get(PROJECT, b"").decode("latin1")
    m = re.search(r"SLOT=129\r?\nPATH=([^\r\n]*)", text)   # the unit writes CRLF
    return m.group(1) if m else None


def main():
    if not EMU.is_file():
        return fail("the ColdFire port is not built (make emu-cf)")
    if not IMAGE.is_file():
        return fail("build the image first (make bus REMIX=<a remix with BUFFER SAVER>)")

    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        project = work / "project"
        project.mkdir()
        (project / "project.work").write_text("[STATES]\nBANK=0\n\n")
        shutil.copy(project / "project.work", project / "project.strd")
        card = work / "card.img"
        staged = subprocess.run([sys.executable, str(STAGE_CARD), str(project), "OCTABAM", "BUFSAVE",
                                 "--tree", str(work / "tree"), "--out", str(card)],
                                cwd=ROOT, capture_output=True, text=True)
        if staged.returncode:
            return fail("could not stage the card", staged.stdout + staged.stderr)
        old = work / "old.wav"
        old.write_bytes(_wav(4410))
        card_taken = work / "card_taken.img"
        staged = subprocess.run([sys.executable, str(STAGE_CARD), str(project), "OCTABAM", "BUFSAVE",
                                 "--tree", str(work / "tree_taken"), "--out", str(card_taken),
                                 "--audio", f"{old}:AUDIO/R1-000000-0000.wav"],   # relative to the set
                                cwd=ROOT, capture_output=True, text=True)
        if staged.returncode:
            return fail("could not stage the card with R1-000000-0000.wav", staged.stdout + staged.stderr)
        cards = {"yes": card, "taken": card_taken, "no": card}

        first = SETUP + take(2000) + save(6000) + press(9000, YES) + press(14000, YES)
        jobs = [("yes", first + save(45000) + press(49000, YES), 56000),   # the first project save writes ~10 MB
                ("taken", first, 20000),
                ("no", SETUP + take(2000) + save(6000) + press(9000, NO) + press(12000, YES), 17000)]
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            results = {name: (rc, out, files) for name, rc, out, files in
                       pool.map(lambda j: run(work, cards, *j), jobs)}

    for name, (rc, out, _) in results.items():
        if rc or "M6a gate   : PASS" not in out or "ended on quit" not in out:
            return fail(f"{name}: the port run did not finish cleanly (exit {rc})", out)

    rc, out, files = results["yes"]
    names = sorted(k[len(AUDIO):] for k in files if k.startswith(AUDIO))
    if names != ["R1-000000-0000.ot", "R1-000000-0000.wav"]:
        return fail(f"yes: wanted R1-000000-0000.wav and .ot in the set's AUDIO, saw {names}", out)
    if len(files[AUDIO + "R1-000000-0000.wav"]) < 44 + 4 * 22050:
        return fail("yes: R1-000000-0000.wav holds under half a second of audio", out)
    if slot129(files) != "../AUDIO/R1-000000-0000.wav":
        return fail(f"yes: the project's SLOT=129 path is {slot129(files)!r}", out)
    mode2 = [w for w in writes(out, MODE) if w[1] == 2]
    if len(mode2) != 1 or not DRAM[0] <= mode2[0][2] < DRAM[1]:
        return fail(f"yes: wanted one mode-2 save by the module, saw {mode2}", out)
    if dialogs(out) != (1, 2):
        return fail(f"yes: wanted SAVE SAMPLES? once and CONTINUE? twice, saw {dialogs(out)}", out)

    rc, out, files = results["taken"]
    names = sorted(k[len(AUDIO):] for k in files if k.startswith(AUDIO))
    if names != ["R1-000000-0000-2.ot", "R1-000000-0000-2.wav", "R1-000000-0000.wav"]:
        return fail(f"taken: wanted the take as R1-000000-0000-2 beside the old file, saw {names}", out)
    if files[AUDIO + "R1-000000-0000.wav"] != _wav(4410):
        return fail("taken: the old R1-000000-0000.wav was changed", out)
    if slot129(files) != "../AUDIO/R1-000000-0000-2.wav":
        return fail(f"taken: the project's SLOT=129 path is {slot129(files)!r}", out)

    rc, out, files = results["no"]
    names = [k for k in files if k.startswith(AUDIO)]
    if names:
        return fail(f"no: NO wrote {names}", out)
    if slot129(files) != "":
        return fail(f"no: the project's SLOT=129 path is {slot129(files)!r}, wanted none "
                    "(or the project was not saved)", out)
    if writes(out, MODE):
        return fail(f"no: the sample save ran after NO: {writes(out, MODE)}", out)
    if dialogs(out) != (1, 1):
        return fail(f"no: wanted SAVE SAMPLES? and CONTINUE? once each, saw {dialogs(out)}", out)

    print("  [PASS] verify_buffer_saver: after a take FUNC + PROJ asks SAVE SAMPLES?; YES writes "
          "R1-000000-0000.wav and .ot and points the project's buffer 1 at it, and the next save does "
          "not ask; with that name taken the take is saved as R1-000000-0000-2 and the old file is "
          "left alone; NO writes no sample and the project saves as stock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
