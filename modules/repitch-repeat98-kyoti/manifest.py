"""REPITCH_REPEAT98_KYOTI -- TSTR RPCH / RPS9 / RPSP: tempo-locked varispeed with S900/S950 and SP-1200 repitch emulations, and QUAN ratios on PTCH.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `0fea4f4`). The declaration is
`upstream/octabam-modules/repitch-repeat98-kyoti/manifest.py`: three DRAM units
(`patch_repitch_kyoti.s`, `rpk_glyphs.s`, `patch_repitch_reload.s`), the first
two re-linked and compared with the author's own bytes (`reference`) every
build. Its source paths are derived from its own directory, so it is executed
here from the source on disk, as the registry does for every manifest, and this
file only re-exports its MODULE. Nothing inside `upstream/` is edited here.

Work in progress: the ColdFire half only. RPS9 and RPSP's DSP kernel is not
declared yet.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "repitch-repeat98-kyoti" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_repitch_repeat98_kyoti")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="Zac-Kyoti/octatrack-kyoti-fw", author_url="https://github.com/Zac-Kyoti/octatrack-kyoti-fw",
    proof=Proof.CHECK, proof_note="ColdFire half only (WIP); the octabam form has not run on a unit")
