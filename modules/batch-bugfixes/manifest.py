"""BATCH_BUGFIXES -- three stock 1.40C fixes as one module: MIDI Plays-Free trig, empty-pattern LED, Part-change carryover.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `2cd3109`). The declaration is
`upstream/octabam-modules/batch-bugfixes/manifest.py`: three ROM caves (`patch_trigscale.s`, `patch_pattern_led.s`, `patch_partreapply.s`), each re-linked and
compared with the author's own bytes (`reference`) every build. Its source
paths are derived from its own directory, so it is executed here from the
source on disk, as the registry does for every manifest, and this file only
re-exports its MODULE. Nothing inside `upstream/` is edited here.

On hardware: the author's MKI (bugs 1 and 3, and bug 2's [BANK]-held stall ended); bug 2's [PTN] answers emulator-verified identical to its earlier hardware-confirmed version; bug 2's [BANK] answer for trigless locks: the author's MKI, 20 Nov 2026,
in KYOTI V1.8BC / V1.8C release candidates and VARISPEED_EMUS 140CVEMRC1 (the same 318 B); this octabam form not flashed.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Evidence, Level

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "batch-bugfixes" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_batch_bugfixes")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.FIXES, author="Zac Kyoti", author_url="https://github.com/Zac-Kyoti",
    evidence=(Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti",
        note="(bugs 1 and 3, and bug 2's [BANK]-held stall ended); bug 2's [PTN] answers emulator-verified "
             "identical to its earlier hardware-confirmed version"),
        Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti", image="KY18BC RC1", date="2026-11-20",
        note="bug 2's [BANK] grid lights a bank whose only content is trigless locks with a locked parameter "
             "(audio and MIDI; also KY18C RC1 and 140CVEMRC1, the same 318 B); [BANK] held with the sequencer "
             "running stays responsive; this octabam form not flashed"),))
