"""BLACKPYRAMIDS_303 -- BLKPYRAMD, a TB-303 voice (Open303 on the DSP56300) as a track machine, one per DSP core.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `fee95f5`). The declaration is
`upstream/octabam-modules/blackpyramids-303/manifest.py`: one DRAM unit (`bp_runtime.s`, the
ColdFire runtime generated from its sources), re-linked and compared with the author's own bytes
(`reference`) every build; 43 detours, 7 pokes, the FLEX renderer `SymbolRef`; and the DSP voice
written by `bp_image.py` through `Module.dsp_source`, as ANALOG BD's `tools/build/ab_image.py`.
Its source paths are derived from its own directory, so it is executed here from the source on
disk, as the registry does for every manifest, and this file only re-exports its MODULE. Nothing
inside `upstream/` is edited here.

On hardware: the standalone image on the author's MKI, 14 Oct 2026. This octabam form (the same
runtime and DSP bytes) has not been flashed.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "blackpyramids-303" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_blackpyramids_303")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in the author's manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="Zac-Kyoti/octatrack-kyoti-fw", author_url="https://github.com/Zac-Kyoti/octatrack-kyoti-fw",
    proof=Proof.HARDWARE, proof_note="the standalone image on the author's MKI, 14 Oct 2026 (this octabam form not flashed)")
