"""SYNTH MACHINE -- a two-operator FM synth machine: a FLEX track whose
sample is named SYNTH*.wav plays an FM voice instead of the sample, with its
own PLAYBACK page (PTCH RATO INDX RATE FDBK DEC) and, on the LFO page, VOIC
(1 = mono, 2..4 = paraphonic) and CHRD (32 chord shapes, lockable per step,
snapped onto SCALE QUANTIZER's scale).

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v9 = OCTATRICK9). The declaration is
`upstream/synth/manifest.py`: the voice engine as a DRAM unit (`poly.s`,
`Linked(dram=True)`, in the platform reserve with the other DRAM modules),
the page as a pinned ROM cave (`page.s` at 0x400d24d0, the start of the
second free gap -- the ledger refuses it beside `tempo-bus`, which uses the
same gap), a SymbolRef on the kind table's FLEX renderer entry, detours and
pokes. Its source paths are derived from its own directory, so it is
executed here from the source on disk, as the registry does for every
manifest, and this file only re-exports its MODULE. Nothing inside
`upstream/` is edited here.

On hardware as OCTATRICK9 (remix octatrick-usb) on Tim's MKI, 26 Sep 2026.
"""

import pathlib
import runpy

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "synth" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_synth")["MODULE"]
