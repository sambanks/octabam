"""PROCESSOR LOAD -- how busy the ColdFire is making audio, in the stock
TEMPO popup: the mean share of real time spent in the audio frame interrupt
over the last quarter second, timed on DMA timer 3 at CF METER's two
frame-interrupt sites; `!` from 70 %, `--%` without a fresh reading, FUNC
held shows the longest block of the quarter second. Standalone (its own UI
tick, armed by the stock startup flag, no USB, nothing on a computer).

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v2.14 (39dc5d8) = Octatrick 2.14, 13 Oct 2026). The
declaration is `upstream/processor-load/manifest.py`: one DRAM unit
(`loadmeter.s`, `Linked(dram=True)`), four detours and one poke; it
declares the conflicts with CF METER and TEMPO BUS. Its source paths are
derived from its own directory, so it is executed here from the source on
disk, as the registry does for every manifest, and this file only
re-exports its MODULE. Nothing inside `upstream/` is edited here.

Verified on the ColdFire port, 8 Oct 2026 (arms after a cold boot, reads
idle and playing, FUNC shows the longest block, `--%` by a forced fault).
On his MKI on 10 Oct 2026 in a Modwerk test image (MAIN OS SHA-256
f3ebd1c5...; loadmeter.s byte-identical to v2.11's, the same at v2.12, v2.13 and v2.14),
not in an octabam build: working, no issues reported.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "processor-load" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_processor_load")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.REFERENCE, author="timhastie/octatrick-modules", author_url="https://github.com/timhastie/octatrick-modules",
    proof=Proof.HARDWARE, proof_note="his MKI, 10 Oct 2026, in a Modwerk test image (MAIN OS SHA-256 f3ebd1c5...; loadmeter.s as at v2.11 .. v2.14), not an octabam build: working, no issues reported; the port, 8 Oct 2026: arms after a cold boot, reads idle and playing, FUNC shows the longest block, `--%` by a forced fault")
