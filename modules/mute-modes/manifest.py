"""MUTE_MODES -- PERSONALIZE > MUTE MODE: OT (stock), OTFX, OTFX-T, DT-T -- what a muted or soloed-out audio track does.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `bb9bead`). The declaration is
`upstream/octabam-modules/mute-modes/manifest.py`: two linked units (`patch_softmute.s`, `patch_mutemode.s`), placed in ROM caves or DRAM by the `PLACE` setting (`kyoti.mute-modes`, default CAVE), six detours, three grown PERSONALIZE tables, four pokes, each re-linked and
compared with the author's own bytes (`reference`) every build. Its source
paths are derived from its own directory, so it is executed here from the
source on disk, as the registry does for every manifest, and this file only
re-exports its MODULE. Nothing inside `upstream/` is edited here.

On hardware: the author's MKI (standalone image, the KYOTI V1.7 combined image, and this octabam form beside SIDECHAIN_COMPRESSOR as OCTABAM39, 3 Nov 2026).
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "mute-modes" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_mute_modes")["MODULE"]
# The build passes (modules, remix) to every include so a unit can resolve
# the remix's settings; the author's include takes only (modules). Adapted
# here, not in `upstream/`: both the units themselves and the PLACE variant,
# which rebuilds `linked` from the author's own tuple.
def _adapt_unit(_unit):
    if callable(getattr(_unit, "include", None)):
        return dataclasses.replace(_unit, include=(lambda modules, remix, _inc=_unit.include: _inc(modules)))
    return _unit

_author_variant = MODULE.variant

def _adapted_variant(values):
    _out = dict(_author_variant(values))
    if "linked" in _out:
        _out["linked"] = tuple(_adapt_unit(_u) for _u in _out["linked"])
    return _out

# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, linked=tuple(_adapt_unit(_u) for _u in MODULE.linked), variant=_adapted_variant,
    category=Category.MACHINES, author="Zac Kyoti", author_url="https://github.com/Zac-Kyoti",
    proof=Proof.HARDWARE, proof_note="the author's MKI (standalone image, the KYOTI V1.7 combined image, and this octabam form beside SIDECHAIN_COMPRESSOR as OCTABAM39, 3 Nov 2026)")
