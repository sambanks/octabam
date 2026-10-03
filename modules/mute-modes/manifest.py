"""MUTE_MODES -- PERSONALIZE > MUTE MODE: OT (stock), OTFX, OTFX-T, DT-T -- what a muted or soloed-out audio track does.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `7c2fe04`). The declaration is
`upstream/octabam-modules/mute-modes/manifest.py`: two linked ROM units (`patch_softmute.s`, `patch_mutemode.s`), six detours, three grown PERSONALIZE tables, four pokes, each re-linked and
compared with the author's own bytes (`reference`) every build. Its source
paths are derived from its own directory, so it is executed here from the
source on disk, as the registry does for every manifest, and this file only
re-exports its MODULE. Nothing inside `upstream/` is edited here.

On hardware: the author's MKI (standalone image and the KYOTI V1.0 combined image).
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "mute-modes" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_mute_modes")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="Zac-Kyoti/octatrack-kyoti-fw", author_url="https://github.com/Zac-Kyoti/octatrack-kyoti-fw",
    proof=Proof.HARDWARE, proof_note="the author's MKI (standalone image and the KYOTI V1.0 combined image)")
