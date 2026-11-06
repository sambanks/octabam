"""The STUDIO VERB rows on the stock reverbs' ids (octabam-verbs): each one is STUDIO VERB's knobs, modes and code
(MenuEntry.dsp_of) under its own name, starting on one MODE with that mode's knob values as its defaults. A Part saved
with PLATE, SPRING or DARK REV opens on the row that took that reverb's id."""
import dataclasses
import pathlib
import runpy

from remix.schema import Kind, MenuEntry, Module, Proof

_SV = runpy.run_path(str(pathlib.Path(__file__).resolve().parent / "manifest.py"),
                     run_name="remix_manifest_studioverb_rows")["MODULE"]


def row(name, key, mode, replaces, fx2_id, abbr, fullname, doc):
    view = next(v for v in _SV.mode_views if v.mode == mode).defaults
    params = tuple(dataclasses.replace(p, default=mode if i == _SV.mode_slot else view.get(i, p.default))
                   if p.name else p for i, p in enumerate(_SV.params))
    return Module(
        name=name, key=key, kind=Kind.DSP_EFFECT, category=_SV.category,
        author=_SV.author, author_url=_SV.author_url,
        proof=Proof.RENDER, proof_note="runs STUDIO VERB's code (verify_studioverb); not run on a unit",
        doc=doc,
        menu=MenuEntry(fx2_id=fx2_id, replaces=replaces, donor_desc=_SV.menu.donor_desc,
                       abbr=abbr, fullname=fullname, build_tag=False, dsp_of="STUDIO VERB"),
        params=params, mode_slot=_SV.mode_slot, mode_views=_SV.mode_views,
    )
