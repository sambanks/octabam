"""DIRECT JUMP -- CHAIN AFTER's unused value 1 becomes DIRECT: a pattern
selected while the sequencer runs starts at the next step, at the step count
the old pattern had reached (the Analog Four / Rytm behaviour). Off by
default: the value is an existing, unused position of an existing project
setting, so a project that never selects it plays exactly as stock.

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v9.1 = OCTATRICK9 + the runtime page clone, hardware-confirmed as OCTATRIK10 on an MKI). The declaration is
`upstream/direct-jump/manifest.py`: one floating ROM cave (`direct_jump.s`,
ratified bytes re-linked and compared every build) on the pattern-queue
setter and the tick handler, four fixed pokes. Its source paths are derived from its own directory, so
it is executed here from the source on disk, as the registry does for every
manifest, and this file only re-exports its MODULE. Nothing inside
`upstream/` is edited here.

On hardware as OCTATRICK9 (remix octatrick-usb) on Tim's MKI, 26 Sep 2026.
"""

import pathlib
import runpy

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "direct-jump" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_direct_jump")["MODULE"]
