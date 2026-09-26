"""SCALE QUANTIZER -- a SCALE row in PROJECT > CONTROL > SEQUENCER (OFF, then
24 scales): the PTCH knob, parameter locks and CHROMATIC trig keys snap to
the scale; a GLIDE row (OFF, 1..127) gives the synth its glide time and the
chromatic keys 303-style legato; polyphonic chromatic keys on a synth track
whose VOIC is 2..4.

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v9.1 = OCTATRICK9 + the runtime page clone, hardware-confirmed as OCTATRIK10 on an MKI). The declaration is
`upstream/quantizer/manifest.py`: four ROM units (`glide.s`, `keys.s`,
`quantizer.s`, `scale.s`; the glide byte, the key trampoline and the scale
trampoline at pinned addresses the synth's engine reads), detours, pokes
and a TableGrow for the menu rows. Its source paths are derived from its
own directory, so it is executed here from the source on disk, as the
registry does for every manifest, and this file only re-exports its
MODULE. Nothing inside `upstream/` is edited here.

On hardware as OCTATRICK9 (remix octatrick-usb) on Tim's MKI, 26 Sep 2026.
"""

import pathlib
import runpy

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "quantizer" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_quantizer")["MODULE"]
