#!/usr/bin/env python3
"""BUFFER SAVER under the port: SAVE PROJECT (FUNC + PROJ) after a take,
in seven scenarios, each its own boot.

Each boots the built image (out/mainos_bus.bin) on a private card holding a
saved, empty project (project.work and project.strd, so SAVE takes stock's
CONTINUE? path rather than SAVE TO NEW). RECORDING SETUP 1 sets TRIG to
HOLD, so TRACK 1 + REC AB held for one second makes a short take into
recorder buffer 1. The port's clock is unset, so the automatic name is
R1-000000-0000. A YES/NO dialog is told apart by its lines: the module's
SAVE SAMPLES? passes its own table (in DRAM), stock's CONTINUE? a stack
copy.

  yes      take, FUNC + PROJ, YES (SAVE SAMPLES?), YES (CONTINUE?). Wanted:
           R1-000000-0000.wav and .ot, the project's SLOT=129 path on it,
           one mode-2 save by the module.
  again    take, FUNC + PROJ, YES, NO (CONTINUE?: no project write), then
           FUNC + PROJ again and NO. Wanted: the take saved once and SAVE
           SAMPLES? asked once: the saved take is not offered again.
  taken    as yes, on a card that already holds R1-000000-0000.wav: the
           take is saved as R1-000000-0000-2.wav, the project points at it,
           the old file is unchanged.
  no       take, FUNC + PROJ, NO (SAVE SAMPLES?), YES (CONTINUE?). Wanted: no
           WAV, SLOT=129 with no path, the project saved, no mode-2 save.
  new      take, PROJECT > SAVE TO NEW, YES, a new name (BUFSAVF). Wanted:
           the take saved, the new project pointing at it, SAVE SAMPLES?
           once, stock's name keyboard once.
  first    the project's name cleared (never saved), take, FUNC + PROJ, NO.
           Stock's SAVE runs SAVE TO NEW's code itself: SAVE SAMPLES? still
           once, and stock's name keyboard opens.

`verify_buffer_saver.py [scenario ...]` runs the named scenarios (default: all,
in parallel) and prints each one's wall time.

  audio    the only run with the DSP: take, FUNC + PROJ, YES (SAVE SAMPLES?),
           NO (CONTINUE?). Wanted: the saved WAV holds the take's audio (the
           tones input), not silence.

Without --dsp a take has the right length and is silent, and the port runs
about 5x faster (the `yes` script: 37 s against 195 s, 4 Nov 2026, M-series,
one scenario alone), so every scenario but `audio` runs without it.

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
import time
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
KEYBOARD = 0x4007E664                # stock's naming keyboard (SAVE TO NEW asks the new name)
PROJECT_NAME = 0x100F8378            # the open project's name; empty = never saved
AUDIO = "OCTABAM/AUDIO/"
PROJECT = "OCTABAM/BUFSAVE/project.strd"
NEW_PROJECT = "OCTABAM/BUFSAVF/project.work"   # SAVE TO NEW with the name's last letter stepped up

# Panel key codes (tools/panel/key_map.json: row 0x20+r, bit b -> r*8+b).
NO, YES, FUNC, REC_AB, T1, PROJ = 0x32, 0x31, 0x2D, 0x2B, 0x10, 0x1C
UP, DOWN, LEFT = 0x33, 0x20, 0x34
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


def run(work, card, name, script, quit_ms, dsp=False):
    card = card[name] if isinstance(card, dict) else card
    path = work / f"{name}.script"
    path.write_text("\n".join(script + [f"{quit_ms} quit"]) + "\n")
    out_card = work / f"{name}.img"
    args = [str(EMU), "--image", str(IMAGE), "--card", str(card), "--card-out", str(out_card),
            "--set", "OCTABAM", "--project", "BUFSAVE", "--load-ms", "90000",
            "--mkii", *(["--dsp"] if dsp else []), "--main-level", "64", "--audio-in", "tones",
            "--watch-mem", f"{MODE:#x},4", "--watch-pc", f"{DIALOG_ENTRY:#x},{KEYBOARD:#x}",
            "--live-script", str(path)]
    t0 = time.monotonic()
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=3600)
    print(f"  scenario {name}: {time.monotonic() - t0:.0f} s", flush=True)
    files = emu_card.extract_image(out_card.read_bytes()) if out_card.is_file() else {}
    return name, r.returncode, r.stdout + r.stderr, files


def writes(output, addr):
    """(time, value, pc) for each watched write to addr, in order."""
    return [(float(t), int(v, 0), int(pc, 16)) for t, v, pc in re.findall(
        rf"\[\s*([\d.]+)\] \[{addr:#x}\] <- (\S+) \(\d\) at pc (0x[0-9a-f]+)", output)]


def dialogs(output):
    """(ours, stock) counts of YES/NO dialogs opened (the words at the
    entry's sp: return address, title, line count, lines): lines in the
    module's DRAM are SAVE SAMPLES? (titled SAVE PROJECT or SAVE TO NEW);
    stock's are its SAVE PROJECT dialogs (CONTINUE?). Others (the staged
    card's load message at boot, SAVE AS NEW's notice) are not counted."""
    ours = stock = 0
    for words in re.findall(rf"at {DIALOG_ENTRY:#x} .*?\[sp 0x[0-9a-f]+: ([^\]]+)\]", output):
        w = [int(x, 16) for x in words.split()]
        if len(w) < 4:
            continue
        if DRAM[0] <= w[3] < DRAM[1]:
            ours += 1
        elif w[1] == SAVE_PROJECT_TITLE:
            stock += 1
    return ours, stock


def keyboards(output):
    """How often stock's naming keyboard opened."""
    return len(re.findall(rf"at {KEYBOARD:#x} ", output))


def slot129_in(files, name):
    text = files.get(name, b"").decode("latin1")
    m = re.search(r"SLOT=129\r?\nPATH=([^\r\n]*)", text)
    return m.group(1) if m else None


def slot129(files):
    text = files.get(PROJECT, b"").decode("latin1")
    m = re.search(r"SLOT=129\r?\nPATH=([^\r\n]*)", text)   # the unit writes CRLF
    return m.group(1) if m else None


def main(only=None):
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
        cards = {"yes": card, "audio": card, "again": card, "taken": card_taken, "no": card, "new": card, "first": card}

        first = SETUP + take(2000) + save(6000) + press(9000, YES) + press(14000, YES)
        # One project save at most per boot (it writes ~10 MB) and a late quit:
        # the port caps each script step by its target time, and a heavier image
        # (USB in the remix) stretches the save ("live script: ... ended early
        # -- time"). "again" answers NO to CONTINUE?, so it writes no project.
        jobs = [("yes", first, 30000),
                ("audio", SETUP + take(2000) + save(6000) + press(9000, YES) + press(14000, NO), 17000, True),
                ("again", SETUP + take(2000) + save(6000) + press(9000, YES) + press(14000, NO)
                 + save(17000) + press(20000, NO), 24000),
                ("taken", first, 30000),
                ("no", SETUP + take(2000) + save(6000) + press(9000, NO) + press(12000, YES), 30000),
                # PROJECT > SAVE TO NEW (row 4), YES; on stock's keyboard LEFT then UP
                # make BUFSAVE BUFSAVF, YES; stock copies the project to it.
                ("new", SETUP + take(2000) + ["6000 key 0x1c down", "6060 key 0x1c up"] + press(6500, YES)
                 + sum((press(7000 + 300 * i, DOWN) for i in range(4)), []) + press(9000, YES)
                 + press(11000, YES) + press(30000, LEFT) + press(30300, UP) + press(31000, YES), 75000),
                # A project never saved (its name cleared): stock's SAVE runs SAVE
                # TO NEW's code itself; NO, and nobody is asked a second time.
                ("first", [f"1000 poke {PROJECT_NAME:#x}=0"] + SETUP + take(2000) + save(6000)
                 + press(9000, NO), 30000)]
        unknown = set(only or ()) - {j[0] for j in jobs}
        if unknown:
            return fail(f"no such scenario: {sorted(unknown)}; the scenarios are {[j[0] for j in jobs]}")
        jobs = [j for j in jobs if not only or j[0] in only]
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            results = {name: (rc, out, files) for name, rc, out, files in
                       pool.map(lambda j: run(work, cards, *j), jobs)}

    for name, (rc, out, _) in results.items():
        if rc or "M6a gate   : PASS" not in out or "ended on quit" not in out:
            return fail(f"{name}: the port run did not finish cleanly (exit {rc})", out)

    if not only or "yes" in only:
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
        if dialogs(out) != (1, 1):
            return fail(f"yes: wanted SAVE SAMPLES? and CONTINUE? once each, saw {dialogs(out)}", out)

    if not only or "audio" in only:
        rc, out, files = results["audio"]
        wav = files.get(AUDIO + "R1-000000-0000.wav", b"")
        data = wav[44:]
        frames = len(data) // 4
        loud = sum(1 for i in range(0, len(data) - 1, 4) if data[i:i + 2] != b"\0\0")
        if frames < 22050 or loud < frames // 2:
            return fail(f"audio: R1-000000-0000.wav holds {frames} frames, {loud} of them non-zero (the tones input, with the DSP)", out)

    if not only or "again" in only:
        rc, out, files = results["again"]
        mode2 = [w for w in writes(out, MODE) if w[1] == 2]
        if len(mode2) != 1:
            return fail(f"again: wanted the take saved once, saw {len(mode2)} mode-2 saves", out)
        if dialogs(out) != (1, 2):
            return fail(f"again: wanted SAVE SAMPLES? once (not on the second FUNC + PROJ) and "
                        f"CONTINUE? twice, saw {dialogs(out)}", out)

    if not only or "taken" in only:
        rc, out, files = results["taken"]
        names = sorted(k[len(AUDIO):] for k in files if k.startswith(AUDIO))
        if names != ["R1-000000-0000-2.ot", "R1-000000-0000-2.wav", "R1-000000-0000.wav"]:
            return fail(f"taken: wanted the take as R1-000000-0000-2 beside the old file, saw {names}", out)
        if files[AUDIO + "R1-000000-0000.wav"] != _wav(4410):
            return fail("taken: the old R1-000000-0000.wav was changed", out)
        if slot129(files) != "../AUDIO/R1-000000-0000-2.wav":
            return fail(f"taken: the project's SLOT=129 path is {slot129(files)!r}", out)

    if not only or "no" in only:
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

    if not only or "new" in only:
        rc, out, files = results["new"]
        names = sorted(k[len(AUDIO):] for k in files if k.startswith(AUDIO))
        if names != ["R1-000000-0000.ot", "R1-000000-0000.wav"]:
            return fail(f"new: wanted the take saved before SAVE TO NEW, saw {names}", out)
        if slot129_in(files, NEW_PROJECT) != "../AUDIO/R1-000000-0000.wav":
            return fail(f"new: the new project's SLOT=129 path is {slot129_in(files, NEW_PROJECT)!r}", out)
        if dialogs(out)[0] != 1 or keyboards(out) != 1:
            return fail(f"new: wanted SAVE SAMPLES? once and stock's name keyboard once, saw "
                        f"{dialogs(out)[0]} and {keyboards(out)}", out)

    if not only or "first" in only:
        rc, out, files = results["first"]
        if dialogs(out)[0] != 1 or keyboards(out) != 1:
            return fail(f"first: wanted SAVE SAMPLES? once (not again inside stock's SAVE TO NEW) and "
                        f"stock's name keyboard, saw {dialogs(out)[0]} and {keyboards(out)}", out)

    if only:
        print(f"  [PASS] verify_buffer_saver: {', '.join(sorted(only))}")
        return 0
    print("  [PASS] verify_buffer_saver: after a take FUNC + PROJ asks SAVE SAMPLES?; YES writes "
          "R1-000000-0000.wav and .ot and points the project's buffer 1 at it, and the next save does "
          "not ask; with that name taken the take is saved as R1-000000-0000-2 and the old file is "
          "left alone; NO writes no sample and the project saves as stock; SAVE TO NEW asks too, and the "
          "new project points at the saved take; a project never saved is asked once")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
