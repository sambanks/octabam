"""ERASE_EMPTY_TRIGLESS_LOCKS -- a trigless lock whose last lock is erased disappears instead of staying lit, on audio and MIDI tracks; FUNC + TRIG trigless locks are left alone.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `2cd3109`). The declaration is
`upstream/octabam-modules/erase-empty-trigless-locks/manifest.py`: one linked unit `tl` (`patch_triglock.s`, 240 B,
position independent), re-linked and compared with the author's own bytes (`reference`) every build, and two
`jsr` detours, one per LIVE erase worker: `0x40038a5c` (audio, `FUN_40038874`) and `0x400387b8` (MIDI,
`FUN_40038668`). Its source
paths are derived from its own directory, so it is executed here from the
source on disk, as the registry does for every manifest, and this file only
re-exports its MODULE. Nothing inside `upstream/` is edited here.

On hardware: the author's MKI (audio, standalone image); both sides with these bytes on 20 Nov 2026 in a KYOTI
V1.8BC release candidate (KY18BC RC2). This octabam form: not flashed.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Evidence, Level

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "erase-empty-trigless-locks" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_erase_empty_trigless_locks")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="Zac Kyoti", author_url="https://github.com/Zac-Kyoti",
    evidence=(Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti",
        note="(audio, standalone image)"),
        Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti", image="KY18BC RC2", date="2026-11-20",
        note="MIDI and audio: an erased last lock darkens the step, an empty FUNC + TRIG trigless lock stays, "
             "a note or trigless trig with a lock keeps its trig (the same 240 B in KYOTI V1.8BC); this octabam "
             "form not flashed"),))
