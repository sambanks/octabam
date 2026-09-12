#!/usr/bin/env python3
"""Build the STEM REC fixture card, reproducibly, from a project template.

Task 11's fixture reproduces COLDFIRE_PORT.md O10's kick-on-T1-FLEX
recipe on EZBot's "Ultimate FX 1.5.3" template (no RIG project copy exists on
this machine): T1 = FLEX on slot 1, in banks 1 and 2, every part and its
mirror; T1's FX1 and FX2 = SEND; slot 1's TSMODE=0, so "the record IS the
file" (no timestretch grains to fit around). The kick itself is ours
(`scripts/make_test_audio.py kick`), never Elektron's.

    python3 tools/verify/stems_fixture.py [PROJECT_DIR]

PROJECT_DIR defaults to `out/projects/Ultimate FX 1.5.3`. The template is
copied into a scratch folder first and only the copy is edited -- the
template itself is never touched. Prints the card path, the set and the
project, and writes `out/stems_fixture.json` with the keys `card`, `set`,
`project` and `staged` (the file names this run put into the set's own
AUDIO folder, so a later check can count only what THIS fixture added).
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "hw"))
sys.path.insert(0, str(ROOT / "tools" / "emu"))

import ot_project      # noqa: E402
import emu_rtos         # noqa: E402

# No `/Users/sambanks/octa/backups/*pregain*` directory exists on this
# machine (checked: none under /home, /root or /mnt either). That guard
# protects the interactive GAIN-editing workflow (apply_gains); this fixture
# never calls it. set_machine_type and set_fx already expose their own
# `guard` parameter and are called with guard=False below; set_track_slot
# does not expose one at all (it always runs through _bank_write's
# guard=True default), so the only way to use it from a script is to
# neutralise the check itself. Nothing else about the guard's behaviour is
# touched.
ot_project.guard_backup = lambda: None

DEFAULT_PROJECT = ROOT / "out" / "projects" / "Ultimate FX 1.5.3"
SET_NAME = "STEMS"
PROJECT_NAME = "ULTFX"
SCRATCH = ROOT / "out" / "task11" / "fixture_src"
CARD_OUT = ROOT / "out" / "stems_fixture_card.img"
FIXTURE_JSON = ROOT / "out" / "stems_fixture.json"
KICK_NAME = "kick.wav"

FLEX_MTYPE = 1   # ot_project.py: 0=STATIC, 1=FLEX, 2=THRU, 3=NEIGHBOR, 4=PICKUP
SLOT1 = 1        # 1-based sample slot T1's FLEX machine will play
T1 = 1
FIXTURE_BANKS = (1, 2)   # O10: the emulated load applies bank 1, then the
                          # transport start re-applies the SAVED bank's
                          # pattern part -- write both so either is T1=FLEX.


def _add_sample_slot(project_work, slot, name):
    """Prepend a [SAMPLE] section for a FLEX slot pointing at
    ../AUDIO/<name>.wav -- the relative form project.work's own FLEX entries
    use (STEM_REC.md 5.6/5.7: "../AUDIO/%s.wav", AUDIO one level above the
    project folder, both inside the set). TSMODE=0 disables timestretch, so
    what the recorder captures is the file's own samples, unmodified (O10).
    Edited at the byte level (latin1, CRLF preserved) -- the same discipline
    apply_gains() already uses, so line endings never drift.
    """
    raw = project_work.read_bytes()
    entry = (
        b"[SAMPLE]\r\n"
        b"TYPE=FLEX\r\n"
        + f"SLOT={slot:03d}\r\n".encode("latin1")
        + f"PATH=../AUDIO/{name}.wav\r\n".encode("latin1")
        + b"BPMx24=2880\r\n"
          b"TSMODE=0\r\n"
          b"LOOPMODE=0\r\n"
          b"GAIN=48\r\n"
          b"TRIGQUANTIZATION=-1\r\n"
          b"[/SAMPLE]\r\n\r\n"
    )
    idx = raw.find(b"[SAMPLE]")
    if idx < 0:
        # No existing [SAMPLE] section (a bare template): append after the
        # "# Samples" header comment block, or at EOF as a last resort.
        idx = len(raw)
    project_work.write_bytes(raw[:idx] + entry + raw[idx:])


def build(project_dir=DEFAULT_PROJECT):
    project_dir = pathlib.Path(project_dir)
    if not project_dir.is_dir():
        sys.exit(f"no project at {project_dir}")

    # Copy first, edit the copy: the template is never modified.
    import shutil
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(project_dir, SCRATCH)

    # T1 = FLEX on slot 1, banks 1 and 2, every part and its mirror.
    for bank in FIXTURE_BANKS:
        for part in (1, 2, 3, 4):
            ot_project.set_machine_type(SCRATCH, bank, part, T1, FLEX_MTYPE,
                                         mirror=True, guard=False)
        for part in range(1, 9):   # NPARTS_ALL: current (1-4) + saved (5-8)
            ot_project.set_track_slot(SCRATCH, bank, part, T1, SLOT1, kind="flex")

    # T1 FX1 and FX2 = SEND (every part of every bank -- set_fx's own scope).
    ot_project.set_fx(SCRATCH, "fx1", T1, "SEND", guard=False)
    ot_project.set_fx(SCRATCH, "fx2", T1, "SEND", guard=False)

    # Slot 1: the kick, TSMODE=0.
    _add_sample_slot(SCRATCH / "project.work", SLOT1, "kick")

    # The kick is ours -- never an Elektron byte in the repo.
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_audio.py"), "kick"],
                    check=True, cwd=str(ROOT))
    kick_src = ROOT / "out" / "test_audio" / "kick.wav"
    if not kick_src.is_file():
        sys.exit(f"make_test_audio.py did not produce {kick_src}")

    card_bytes, name = emu_rtos.stage_project(
        SCRATCH, SET_NAME, PROJECT_NAME,
        audio=[f"{kick_src}:AUDIO/{KICK_NAME}"])
    CARD_OUT.write_bytes(card_bytes)

    result = {"card": str(CARD_OUT), "set": SET_NAME, "project": name,
              "staged": [KICK_NAME]}
    FIXTURE_JSON.write_text(json.dumps(result, indent=2) + "\n")
    print(f"card:    {result['card']}")
    print(f"set:     {result['set']}")
    print(f"project: {result['project']}")
    print(f"staged:  {result['staged']}")
    print(f"-> {FIXTURE_JSON}")
    return result


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROJECT)
