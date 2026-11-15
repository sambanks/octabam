"""QUANTIZE_LIVE_REC_TOGGLE -- QUANTIZE LIVE REC from the front panel: [REC] + [PLAY] shows it, a second [PLAY] while the toast is up inverts it.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `9c890bb`). The declaration is
`upstream/octabam-modules/quantize-live-rec-toggle/manifest.py`: one ROM cave (`patch_qlrec.s`), each re-linked and
compared with the author's own bytes (`reference`) every build. Its source
paths are derived from its own directory, so it is executed here from the
source on disk, as the registry does for every manifest, and this file only
re-exports its MODULE. Nothing inside `upstream/` is edited here.

On hardware: the author's MKI, 25 Sep 2026 (gesture) and 30 Sep 2026 (setting survives a power cycle).
22 Oct 2026, the author's standalone and KYOTI V1.6 images (not this octabam form): the toasts
LIVE REC: QUANTIZED / UNQUANTIZED, and the PERSONALIZE check mark following the gesture.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Evidence, Level

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "quantize-live-rec-toggle" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_quantize_live_rec_toggle")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="Zac Kyoti", author_url="https://github.com/Zac-Kyoti",
    evidence=(Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti", date="2026-09-25",
        note="(gesture) and 30 Sep 2026 (setting survives a power cycle); 22 Oct 2026 (toast text, PERSONALIZE "
             "redraw; standalone and KYOTI V1.6 images, not this octabam form)"),))
