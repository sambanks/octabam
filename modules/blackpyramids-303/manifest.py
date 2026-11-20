"""BLACKPYRAMIDS_303 -- BLKPYRAMD, a TB-303 voice (adapted from Open303, recalibrated on the TB-303's circuit, on
the DSP56300) as a track machine, one per DSP core.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `07f47d1`). The declaration is
`upstream/octabam-modules/blackpyramids-303/manifest.py`: one DRAM unit (`bp_runtime.s`, the
ColdFire runtime generated from its sources), re-linked and compared with the author's own bytes
(`reference`) every build; 49 detours, 7 pokes, the FLEX renderer `SymbolRef`; and the DSP voice
written by `bp_image.py` through `Module.dsp_source`, as ANALOG BD's `tools/build/ab_image.py`.
Its source paths are derived from its own directory, so it is executed here from the source on
disk, as the registry does for every manifest, and this file only re-exports its MODULE. Nothing
inside `upstream/` is edited here.

On hardware: the author's standalone images on their MKI, 14-16 Oct 2026, and the recalibrated voice's
(FINAL, mainos ecc85887...) 21 Oct 2026: all good; with the link clips CUT-RES and DEC-ACC (FINAL, mainos
88d49307...) 23 Oct 2026: all good; the same voice 90 words smaller, its output bit-exact (FINAL, mainos
5b7dfb2f..., 936 / 932 words) 3 Nov 2026: all tests pass. This octabam form (remixes/test/blackpyramids-303) on
their MKI: with the previous voice, 19 Oct 2026, all checks pass; with the recalibrated voice, 21 Oct 2026, all
good; with one BLKPYRAMD per core on every path, SRC page copy / paste keeping the machine and the Part / pattern
change fixes (OCTABAM40-43), 19 Nov 2026: OCTABAM43 all checks pass.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Evidence, Level

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "blackpyramids-303" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_blackpyramids_303")["MODULE"]
# The author's conflict with SCALE QUANTIZER names the MIDI note site 0x4000e746,
# which SCALE QUANTIZER no longer claims (SYNTH MACHINE's po_mon took it, 30 Sep
# 2026: modules/quantizer). The three CHROMATIC sites the two do share are
# bridged by HOOKS (modules/hooks, chromatic), so that one conflict is dropped
# here; the author's manifest is not edited.
MODULE = dataclasses.replace(MODULE, conflicts=tuple(
    c for c in MODULE.conflicts if c[0] != "SCALE QUANTIZER"))
# VARISPEED parks a track's PTCH in the NEIGHBOR bytes a FLEX or STATIC track leaves unused, and BLKPYRAMD keeps
# its signature, FLEX's own values and its parked knobs in the same bytes (the author's repository found the clash
# on 19 Nov 2026: a VARI track's PTCH or TSTR can be lost on a round trip through BLKPYRAMD). Refused here until
# the author's fix lands; the author's manifest is not edited.
MODULE = dataclasses.replace(MODULE, conflicts=MODULE.conflicts + (
    ("VARISPEED", "both keep a track's values in the NEIGHBOR bytes a FLEX or STATIC track leaves unused"),))
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in the author's manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="Zac Kyoti", author_url="https://github.com/Zac-Kyoti",
    evidence=(Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti", image="OCTABAM43", date="2026-11-19",
        note="this octabam form (remixes/test/blackpyramids-303) with one BLKPYRAMD per core on every path, SRC page "
             "copy / paste and the Part / pattern change fixes: all checks pass; earlier forms 19 / 21 Oct 2026, the "
             "author's standalone images 14 Oct - 3 Nov 2026"),))
