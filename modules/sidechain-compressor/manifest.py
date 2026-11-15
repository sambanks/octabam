"""SIDECHAIN_COMPRESSOR -- stock COMPRESSOR with a side-chain KEY from any track and a base-width key filter: MON, KEY, KGN, KBAS and KWID on page 2.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `6c9180d` on the sambanks/octatrack-kyoti-fw fork until Zac-Kyoti/octatrack-kyoti-fw#4,
its opt-in FORM = SHARED, is merged upstream). The declaration is
`upstream/octabam-modules/sidechain-compressor/manifest.py`: two linked units
(`patch_sidechain.s`, and `ui_switch.s`: KEY's 9-position rotary switch and KWID's link clip),
placed in a ROM cave or DRAM by the `PLACE` setting
(`octabam.sidechain-compressor`, default CAVE), re-linked and compared with the author's own bytes
(`reference`) every build, and a DSP section reached only from four hooks
(`MenuEntry.stock_dsp`: the effect is stock COMPRESSOR). Its source paths are
derived from its own directory, so it is executed here from the source on disk,
as the registry does for every manifest, and this file only re-exports its
MODULE. Nothing inside `upstream/` is edited here.

"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Evidence, Level

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "sidechain-compressor" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_sidechain_compressor")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in the author's manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.TRACK, author="Zac Kyoti", author_url="https://github.com/Zac-Kyoti",
    evidence=(Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti", image="OCTABAM33", date="2026-10-26",
        note="this pin's octabam form (remixes/test/sidechain-compressor) on the author's MKI as OCTABAM33, 26 Oct"
             " 2026: KBAS/KWID, MON's switch and its OFF on older projects, KEY's pressed turn, the fades, all "
             "good; the key-filter table fix alone as OCTABAM32, 25 Oct 2026. The author's standalone image "
             "(140C_SCKF4) and KYOTI V1.6 on the author's MKI, 22 Oct 2026, and KEY's rotary switch and KWID's "
             "clip in the standalone image, 23 Oct 2026: page 2, KBAS/KWID ranges and readouts, a kick fundamental"
             " keyed at short attack and release, MON and KEY declick, load with 1 + 7 and 4 + 4 COMPRESSOR/DJ EQ "
             "per core. The previous version's octabam form ran on the unit on 4 Oct 2026"),))
