"""DIRECT JUMP -- CHAIN AFTER's value 1 becomes DIRECT: a pattern selected
while the sequencer runs starts at the next step, at the step count the old
pattern had reached (the Analog Four / Rytm behaviour), instead of at the
old pattern's end or after its CHAIN AFTER length. Off by
default: the value is an existing, unused position of an existing project
setting, so a project that never selects it plays exactly as stock.

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v2.14 (39dc5d8) = Octatrick 2.14, 13 Oct 2026; the test
builds 2.3 .. 2.8 and the 2.9 line flashed on his MKI). The declaration is
`upstream/direct-jump/manifest.py`: one floating ROM cave (`direct_jump.s`,
ratified bytes re-linked and compared every build) on the pattern-queue
setter and the tick handler, four fixed pokes. Its source paths are derived from its own directory, so
it is executed here from the source on disk, as the registry does for every
manifest, and this file only re-exports its MODULE. Nothing inside
`upstream/` is edited here. The sources are unchanged since v9.1 (v2.14
included); at 2.9
the quantizer's move into DRAM frees the ROM zero run, so the 358-byte cave
fits beside SCALE QUANTIZER and CF METER's clone again.

On hardware as OCTATRICK9 (remix octatrick-usb) on Tim's MKI, 26 Sep 2026,
and every test build 2.3 .. 2.8 since; the 2.9 line up to the build before its
last two fixes (ROOT, the DRAM quantizer, FINE 0c, the envelope engine, no
limiter) has run on the same MKI; the last two fixes (sequencer trigs, the
index ramp) are emulator-verified only.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "direct-jump" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_direct_jump")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="timhastie/octatrick-modules", author_url="https://github.com/timhastie/octatrick-modules",
    proof=Proof.HARDWARE, proof_note="`octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the last two 2.9 fixes under the port")
