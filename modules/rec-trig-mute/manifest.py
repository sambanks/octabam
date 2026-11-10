"""REC_TRIG_MUTE -- [TRACK]+[REC] mutes / unmutes each held track's recorder trigs; MIDI CC 80; '..' beside a muted track's tab letter.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `91a58e9`). The declaration is
`upstream/octabam-modules/rec-trig-mute/manifest.py`: one DRAM unit (`patch_rec_trig_mute.s`,
assembled with `--defsym OCTABAM_UNIT`), re-linked and compared with the author's own bytes
(`reference`) every build. Its source paths are derived from its own directory, so it is
executed here from the source on disk, as the registry does for every manifest, and this file
only re-exports its MODULE. Nothing inside `upstream/` is edited here.

On hardware: the author's MKI -- the earlier [TRACK]+[NO]/[YES] gesture 2-3 Oct 2026 (standalone
image and KYOTI V1.0); the [TRACK]+[REC] form, toggle and toast, 29 Oct 2026 inside KYOTI V1.6;
the mute dots beside the tab letter at `91a58e9`, 9 Nov 2026 inside a KYOTI V1.7 test build (CL22).
Not on hardware yet: MIDI CC 80, and this DRAM form.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "rec-trig-mute" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_rec_trig_mute")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="Zac Kyoti", author_url="https://github.com/Zac-Kyoti",
    proof=Proof.HARDWARE, proof_note="the author's MKI: [TRACK]+[REC] inside KYOTI V1.6, 29 Oct 2026; the tab-letter dots (91a58e9) "
        "inside a KYOTI V1.7 test build, 9 Nov 2026 (MIDI CC 80 not tried; this DRAM form not flashed)")
