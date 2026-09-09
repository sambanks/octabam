"""M6e: set a track's MACHINE TYPE in a copy of a project, so route A can
run a trig against a machine the real projects never use -- the fixture
RTOS_FORK.md section 9.4 and EMU.md's M5 section both flagged as missing.

Usage:
    cp -R <a real project dir> out/_recproj
    .venv/bin/python3 tools/scratch/make_recorder_testproj.py out/_recproj [type]

`type` defaults to 4, the value PARAM_PAGES.md's inference calls PICKUP.
The byte, its file offset and the ⚠️ on those value names live in
`ot_project.set_machine_type`, which this wraps; nothing is duplicated here.
Patches bank02.work (the bank `out/_testproj`'s BANK=1 project setting
selects), track 1, part 1 and its saved mirror part 5. Nothing else changes
-- track 1 keeps its existing trig (pattern 1 step 2, the one M6c/M6d's
fidelity gate fires at frame 344, byte 0xd3), so `press_play_live()` +
`poke_trig(2)` exercises it with no on-disk trig edit.

✅ MEASURED (6 Sep 2026), machine type 4, against 400 frames of
`--sequencer --internal-clock --poke-trig 2`:
  - the patch lands: all 8 tracks read [4, 2, 0, 0, 0, 0, 0, 1] out of RAM
    after a real LOAD PROJECT, where the source reads [2, 2, ...].
  - track 1 stops writing FW_LIVE_NIBBLE (0x46104d15) ENTIRELY: 8 writes
    -> 5. Both of its frame-344 trig writes go, AND its frame-0
    transport-start 0x10 -- one of the six start writes in M6c's own
    fidelity table. The track never starts; nothing about this happens at
    the trig.

❌ WHAT THIS DOES **NOT** SHOW -- controls run the same day, same command:
  - machine type 7, OUT OF RANGE for the 0..4 dispatch PARAM_PAGES.md
    names, gives the IDENTICAL 5-write signature.
  - machine type 3 (NEIGHBOR, in range) gives the baseline 8, `0xd3` at
    frame 344 included.
  So the signature reads "type >= 4 / this track is not started", and is
  NOT evidence that a PICKUP machine takes its own dispatch branch. The
  first pass of this file claimed it was; that claim is retracted.
  Reproduce a control with `[type]` above: 3 and 7 are the two that matter.

Still open: the arm/record path. See RTOS_FORK.md section 10.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from ot_project import set_machine_type            # noqa: E402


if __name__ == "__main__":
    if not 2 <= len(sys.argv) <= 3:
        sys.exit(f"usage: {sys.argv[0]} <project dir already copied there> [type]")
    mtype = int(sys.argv[2]) if len(sys.argv) == 3 else 4
    # guard=False: this edits a COPY made for the emulator, not a real set,
    # so the backup guard that protects the card projects does not apply.
    set_machine_type(pathlib.Path(sys.argv[1]), 2, 1, 1, mtype, guard=False)
