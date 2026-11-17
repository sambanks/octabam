"""DIRECT_JUMP_KYOTI -- an immediate pattern change, toggled with [PTN] + [YES] (OFF at every power-on): a cued pattern takes over on the next step, locked to the master clock.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `cd788e9`). The declaration is
`upstream/octabam-modules/direct-jump-kyoti/manifest.py`: one DRAM unit (`patch_directjump_v7.s`) on the pattern landing, the MIDI START gate, the [PTN] release, the light Part apply, stock's pattern switch and the [PTN]-layer YES record, each re-linked and
compared with the author's own bytes (`reference`) every build. Its source
paths are derived from its own directory, so it is executed here from the
source on disk, as the registry does for every manifest, and this file only
re-exports its MODULE. Nothing inside `upstream/` is edited here.

On hardware: the author's MKI, 27-28 Sep 2026 (standalone 140C_KDJ7 and the KYOTI V1.0 combined image), and 1 Oct 2026 from DRAM in an octabam image with all six KYOTI modules; 15 Nov 2026 V7.2.2 (`109f54c`): the standalone image 140C_KDJ7 (the SILENCE TRACKS pop gone) and KYOTI V1.8C (landings at other lengths and scales, a cue in the last step, trig conditions carried across a jump, each track's Part at its first trig). 16 Nov 2026 V7.3 (`cd788e9`, a jump counts from the last restart): KYOTI V1.8C (KY18C DJR1): after a normal pattern change, a jump lands in phase with it, 1:2 trigs stay in step and a Clyps one-track load after it stays in step; RELOAD after a jump emulator-verified. Program Change re-cues, MIDI tracks and START SILENT emulator-verified. This octabam form of V7.3 has not been flashed.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Evidence, Level

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "direct-jump-kyoti" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_direct_jump_kyoti")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest. His conflict with OCTAKIT is
# dropped: Octakit is not in octabam since 6 Oct 2026 (KITS replaces it).
MODULE = dataclasses.replace(
    MODULE, conflicts=tuple(c for c in MODULE.conflicts if c[0] != "OCTAKIT"), category=Category.MACHINES, author="Zac Kyoti", author_url="https://github.com/Zac-Kyoti",
    evidence=(Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti", date="2026-09-28",
        note="27-28 Sep 2026 (standalone 140C_KDJ7 and the KYOTI V1.0 combined image) and 1 Oct 2026 from DRAM (an"
             " octabam image with all six KYOTI modules); Program Change re-cues, MIDI tracks, START SILENT and "
             "the trig-condition reset emulator-verified"),
              Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti", image="140C_KDJ7", date="2026-11-15",
        note="V7.2.2 (109f54c), the standalone image: the SILENCE TRACKS pop gone; the same code in KYOTI V1.8C "
             "passed the author's walk-through (this octabam form not flashed)"),
              Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti", image="KY18C DJR1", date="2026-11-16",
        note="V7.3 (cd788e9), KYOTI V1.8C: after a normal pattern change a jump lands in phase with it, 1:2 trigs "
             "stay in step and a Clyps one-track load after it stays in step (this octabam form not flashed)"),))
