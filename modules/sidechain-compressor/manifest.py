"""SIDECHAIN_COMPRESSOR -- stock COMPRESSOR with a side-chain KEY from any track: KEY, KFLT, KGN and MON on page 2.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `8e00275`). The declaration is
`upstream/octabam-modules/sidechain-compressor/manifest.py`: one linked unit
(`patch_sidechain.s`), placed in a ROM cave or DRAM by the `PLACE` setting
(`octabam.sidechain-compressor`, default CAVE), re-linked and compared with the author's own bytes
(`reference`) every build, and a DSP section reached only from three hooks
(`MenuEntry.stock_dsp`: the effect is stock COMPRESSOR). Its source paths are
derived from its own directory, so it is executed here from the source on disk,
as the registry does for every manifest, and this file only re-exports its
MODULE. Nothing inside `upstream/` is edited here.

"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "sidechain-compressor" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_sidechain_compressor")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in the author's manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.TRACK, author="Zac-Kyoti/octatrack-kyoti-fw", author_url="https://github.com/Zac-Kyoti/octatrack-kyoti-fw",
    proof=Proof.HARDWARE, proof_note="the author's MKI, 4 Oct 2026, an octabam image with all six KYOTI modules and REC_TRIG_MUTE: ducking on one core and across cores both ways, KFLT/KGN/MON, a muted KEY in every MUTE MODE")
