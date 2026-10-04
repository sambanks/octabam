"""REC_TRIG_MUTE -- [TRACK]+[NO] mutes, [TRACK]+[YES] unmutes the held tracks' recorder trigs; MIDI CC 80; '..' beside a muted track's status icon.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `9ea9a11`). The declaration is
`upstream/octabam-modules/rec-trig-mute/manifest.py`: one DRAM unit (`patch_rec_trig_mute.s`,
assembled with `--defsym OCTABAM_UNIT`), re-linked and compared with the author's own bytes
(`reference`) every build. Its source paths are derived from its own directory, so it is
executed here from the source on disk, as the registry does for every manifest, and this file
only re-exports its MODULE. Nothing inside `upstream/` is edited here.

On hardware: the author's MKI, 2-3 Oct 2026 (standalone image and KYOTI V1.0; MIDI CC 80 not
tried). This DRAM form has not been flashed.
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
    MODULE, category=Category.MACHINES, author="Zac-Kyoti/octatrack-kyoti-fw", author_url="https://github.com/Zac-Kyoti/octatrack-kyoti-fw",
    proof=Proof.HARDWARE, proof_note="the author's MKI, 2-3 Oct 2026 (standalone image and KYOTI V1.0; MIDI CC 80 not tried)")
