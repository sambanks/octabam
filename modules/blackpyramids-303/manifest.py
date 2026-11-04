"""BLACKPYRAMIDS_303 -- BLKPYRAMD, a TB-303 voice (built on Open303, recalibrated on the TB-303's circuit, on the
DSP56300) as a track machine, one per DSP core.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `c66cf6f`). The declaration is
`upstream/octabam-modules/blackpyramids-303/manifest.py`: one DRAM unit (`bp_runtime.s`, the
ColdFire runtime generated from its sources), re-linked and compared with the author's own bytes
(`reference`) every build; 44 detours, 7 pokes, the FLEX renderer `SymbolRef`; and the DSP voice
written by `bp_image.py` through `Module.dsp_source`, as ANALOG BD's `tools/build/ab_image.py`.
Its source paths are derived from its own directory, so it is executed here from the source on
disk, as the registry does for every manifest, and this file only re-exports its MODULE. Nothing
inside `upstream/` is edited here.

On hardware: the author's standalone images on their MKI, 14-16 Oct 2026, and the recalibrated voice's
(FINAL, mainos ecc85887...) 21 Oct 2026: all good; with the link clips CUT-RES and DEC-ACC (FINAL, mainos
88d49307...) 23 Oct 2026: all good; the same voice 90 words smaller, its output bit-exact (FINAL, mainos
5b7dfb2f..., 936 / 932 words) 3 Nov 2026: all tests pass. This octabam form (remixes/test/blackpyramids-303) on
their MKI: with the previous voice, 19 Oct 2026, all checks pass; with the recalibrated voice, 21 Oct 2026, all
good; the clips' and the 936 / 932-word voice's forms are not flashed.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "blackpyramids-303" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_blackpyramids_303")["MODULE"]
# The author's conflict with SCALE QUANTIZER names the MIDI note site 0x4000e746,
# which SCALE QUANTIZER no longer claims (SYNTH MACHINE's po_mon took it, 30 Sep
# 2026: modules/quantizer). The three CHROMATIC sites the two do share are
# bridged by HOOKS (modules/hooks, chromatic), so that one conflict is dropped
# here; the author's manifest is not edited.
MODULE = dataclasses.replace(MODULE, conflicts=tuple(
    c for c in MODULE.conflicts if c[0] != "SCALE QUANTIZER"))
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in the author's manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="Zac Kyoti", author_url="https://github.com/Zac-Kyoti",
    proof=Proof.HARDWARE, proof_note="the author's MKI: standalone images 14 Oct - 3 Nov 2026; this octabam form 19 Oct 2026 and, with the recalibrated voice, 21 Oct 2026 (the 23 Oct link clips and the 3 Nov 936 / 932-word voice: standalone only)")
