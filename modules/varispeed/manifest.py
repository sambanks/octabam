"""VARISPEED -- STATIC/FLEX TSTR VARI: tempo-locked varispeed, QUAN on PTCH, nothing emulated.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `9b2e35a`). The declaration is
`upstream/octabam-modules/varispeed/manifest.py`: the linked unit `vari_cf`
(`varispeed.s`, VARISPEED_EMUS's source with its switch at 0, read from
`../varispeed-emus/` in the same checkout, with QUAN's rotary switch `tools/ui_switch.s`
inlined, its symbols local), re-linked and compared with the author's own
bytes (`reference`) every build, and `vari_store` (`varispeed_store.s`, its STORE handlers),
both placed in DRAM or a ROM cave by the `PLACE` setting (default DRAM); 16 detours and four
pokes; no DSP section. It requires STORE: the PART menu's CLEAR (0x4004a9d0) is STORE's
site, and VARISPEED holds and forgets there as a client (partclear, partsaved). Its source paths are
derived from its own directory, so it is executed here from the source on disk,
as the registry does for every manifest, and this file only re-exports its
MODULE. Nothing inside `upstream/` is edited here.

On hardware: the author's MKI, 15 Oct 2026 (VARI1 build); QUAN as a 9-position rotary switch, 23 Oct 2026
(standalone image).
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Evidence, Level

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "varispeed" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_varispeed")["MODULE"]
# The build passes (modules, remix) to every include so a unit can resolve
# the remix's settings; the author's include takes only (modules). Adapted
# here, not in `upstream/`, as for MUTE_MODES: both the units themselves and
# the PLACE variant, which rebuilds `linked` from the author's own tuple.
def _adapt_unit(_unit):
    if callable(getattr(_unit, "include", None)):
        return dataclasses.replace(_unit, include=(lambda modules, remix, _inc=_unit.include: _inc(modules)))
    return _unit

_author_variant = MODULE.variant

def _adapted_variant(values):
    _out = dict(_author_variant(values)) if _author_variant else {}
    if "linked" in _out:
        _out["linked"] = tuple(_adapt_unit(_u) for _u in _out["linked"])
    return _out

# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in the author's manifest.
MODULE = dataclasses.replace(
    MODULE, linked=tuple(_adapt_unit(_u) for _u in MODULE.linked), variant=_adapted_variant,
    category=Category.MACHINES, author="Zac Kyoti", author_url="https://github.com/Zac-Kyoti",
    evidence=(Evidence(Level.UNIT, unit="MKI", who="Zac Kyoti", date="2026-10-15",
        note="(the VARI1 build, standalone image); QUAN's rotary switch, 23 Oct 2026 (standalone image)"),))
