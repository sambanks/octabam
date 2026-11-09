"""SCALE QUANTIZER -- SCALE / ROOT / GLIDE + TRACK/FOLLOW (v2.22).

Source: `upstream/` pinned to v2.22 with SYNTH MACHINE. Nothing inside
`upstream/` is edited here.

Octabam CX OSC writes Part signature "CX",1 (not Tim's "FM",1). Without
teaching qz_is_synth that CX is a synth track, SCALE ON drives the sample
PTCH path (raw = 64 + 5*n) against CX's 1-raw = 1-semitone page -- MAJOR
etc. jump by ~5 / ~10 a detent. This wrapper assembles a generated copy
of quantizer.s that also accepts "CX" (same return as "FM").

Also: with SCALE ON, qz_knob recomputes from raw encoder detents and drops
po_knob's FUNC ×12 (octave). Keep the clamped handler value while
[FUNCTION] is active so FUNC+PTCH stays ±12.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Gate, Proof

_HERE = pathlib.Path(__file__).resolve().parent
_UPSTREAM = _HERE / "upstream" / "quantizer" / "manifest.py"
_UP_QZ = _HERE / "upstream" / "quantizer" / "quantizer.s"
_GEN = _HERE / "_generated" / "quantizer.s"

# Stock panel flags (same addresses CX / Tim po_knob use).
_FUNC_HELD = "0x46c7dd26"
_FUNC_ENC_OFF = "0x800000a0"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_quantizer")["MODULE"]


def _patch_once(text: str, old: str, new: str, what: str) -> str:
    if new.strip() in text:
        return text
    if old not in text:
        raise RuntimeError(
            f"quantizer CX patch: {what} not found -- "
            "Tim pin moved; update modules/quantizer/manifest.py")
    return text.replace(old, new, 1)


def _cx_aware_quantizer_s() -> str:
    """Return quantizer.s with CX sig + FUNC+SCALE octave keep."""
    text = _UP_QZ.read_text(encoding="utf-8")

    # HAVE_SYDRUM branch: after "FM" match, also accept "CX" as kind 1.
    text = _patch_once(
        text,
        (
            "        cmpi.l  #0x464d,%d0             | \"FM\": 1\n"
            "        jbeq    qz_is_fmsig\n"
            "        cmpi.l  #0x5359,%d0             | \"SY\": 2\n"
        ),
        (
            "        cmpi.l  #0x464d,%d0             | \"FM\": 1\n"
            "        jbeq    qz_is_fmsig\n"
            "        cmpi.l  #0x4358,%d0             | \"CX\": 1 (octabam CX OSC)\n"
            "        jbeq    qz_is_fmsig\n"
            "        cmpi.l  #0x5359,%d0             | \"SY\": 2\n"
        ),
        "HAVE_SYDRUM FM/SY block",
    )

    # Non-SYDRUM branch: FM-only compare -> FM or CX.
    text = _patch_once(
        text,
        (
            "        mvz.w   (%a1),%d0\n"
            "        cmpi.l  #0x464d,%d0\n"
            "        jbne    qz_is_no\n"
            "        mvz.b   2(%a1),%d0\n"
            "        subq.l  #1,%d0\n"
            "        jbne    qz_is_no\n"
        ),
        (
            "        mvz.w   (%a1),%d0\n"
            "        cmpi.l  #0x464d,%d0             | \"FM\"\n"
            "        jbeq    qz_is_sigok\n"
            "        cmpi.l  #0x4358,%d0             | \"CX\" (octabam CX OSC)\n"
            "        jbne    qz_is_no\n"
            "qz_is_sigok:\n"
            "        mvz.b   2(%a1),%d0\n"
            "        subq.l  #1,%d0\n"
            "        jbne    qz_is_no\n"
        ),
        "non-SYDRUM FM-only block",
    )

    # Doc comment: name CX beside FM.
    text = _patch_once(
        text,
        '| machine is chosen (the Part\'s "FM", 1; 2.11: 2 for SY DRUM\'s "SY", 1) -- the',
        '| machine is chosen (the Part\'s "FM", 1; octabam "CX", 1; 2.11: 2 for SY DRUM\'s "SY", 1) -- the',
        "qz_is_synth doc line",
    )

    # SCALE ON + FUNC: keep po_knob's ±12 instead of re-quantizing raw detents.
    text = _patch_once(
        text,
        (
            "        move.l  %a4,%d1                 | delta: detents, signed\n"
            "        jbeq     qz_k_store\n"
            "        mvz.b   %d6,%d2                 | start from the value the knob was turned from\n"
            "        jbsr     qz_quant\n"
            "qz_k_store:\n"
        ),
        (
            "        move.l  %a4,%d1                 | delta: detents, signed\n"
            "        jbeq     qz_k_store\n"
            f"        tst.l   {_FUNC_HELD}              | [FUNCTION] held: keep po_knob (±12)\n"
            "        jbeq     qz_k_doquant\n"
            f"        tst.l   {_FUNC_ENC_OFF}              | PERSONALIZE: FUNC+ENC off\n"
            "        jbne     qz_k_doquant\n"
            "        jbra     qz_k_store             | octabam: octave, not scale degrees\n"
            "qz_k_doquant:\n"
            "        mvz.b   %d6,%d2                 | start from the value the knob was turned from\n"
            "        jbsr     qz_quant\n"
            "qz_k_store:\n"
        ),
        "qz_knob FUNC keep",
    )

    return text


def _ensure_generated() -> str:
    body = _cx_aware_quantizer_s()
    _GEN.parent.mkdir(parents=True, exist_ok=True)
    if not _GEN.exists() or _GEN.read_text(encoding="utf-8") != body:
        _GEN.write_text(body, encoding="utf-8")
    return str(_GEN)


def _adapt_unit(_unit):
    kwargs = {}
    if _unit.label == "qz":
        kwargs["source"] = _ensure_generated()
    if callable(getattr(_unit, "include", None)):
        kwargs["include"] = (
            lambda modules, remix=None, _inc=_unit.include: _inc(modules))
    return dataclasses.replace(_unit, **kwargs) if kwargs else _unit


MODULE = dataclasses.replace(
    MODULE,
    linked=tuple(_adapt_unit(_u) for _u in MODULE.linked),
    gates=MODULE.gates + (Gate("tools/verify/verify_quantizer_ui.py", once=True, venv=True),),
    category=Category.MACHINES, author="timhastie/octatrick-modules",
    author_url="https://github.com/timhastie/octatrick-modules",
    proof=Proof.HARDWARE,
    proof_note="v2.22 with SYNTH MACHINE on Tim's MKI, 1 Nov 2026; "
               "octabam qz_is_synth accepts CX; FUNC+PTCH keeps octave under SCALE",
)
