"""SCALE QUANTIZER -- SCALE / ROOT / GLIDE (Tim pin).

Source: `upstream/` pinned with SYNTH MACHINE. Nothing inside `upstream/`
is edited here.

Octabam CX OSC writes Part signature "CX",1. Tim's qz_is_synth only knows
FLEX+SYNTH* (v2.9) or Part "FM" (v2.15+). Without teaching it CX, SCALE ON
drives the sample PTCH path (raw = 64 + 5*n) against CX's 1-raw = 1-st page.
This wrapper assembles a generated quantizer.s that also treats "CX",1 as
synth, and keeps FUNC+PTCH's octave snap under SCALE (po_knob result).
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Gate, Keep, Proof

_HERE = pathlib.Path(__file__).resolve().parent
_UPSTREAM = _HERE / "upstream" / "quantizer" / "manifest.py"
_UP_QZ = _HERE / "upstream" / "quantizer" / "quantizer.s"
_GEN = _HERE / "_generated" / "quantizer.s"

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
    """Patch quantizer.s for CX Part sig + FUNC octave keep under SCALE."""
    text = _UP_QZ.read_text(encoding="utf-8")

    # v2.15+ / v2.22: Part sig "FM" (+ optional SY DRUM).
    if 'cmpi.l  #0x464d,%d0             | "FM": 1\n' in text:
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
    else:
        # v2.9: FLEX + SYNTH* marker — insert CX Part-sig check after FLEX.
        text = _patch_once(
            text,
            (
                "        mvz.b   (%a1,%d2.l),%d0         | the track's machine\n"
                "        subq.l  #1,%d0                  | FLEX\n"
                "        jbne    qz_is_no\n"
                "        move.l  %d2,%d0\n"
                "        lsl.l   #2,%d0\n"
                "        add.l   %d2,%d0                 | track * 5\n"
            ),
            (
                "        mvz.b   (%a1,%d2.l),%d0         | the track's machine\n"
                "        subq.l  #1,%d0                  | FLEX\n"
                "        jbne    qz_is_no\n"
                "        move.l  %a0,%a1                 | octabam: CX OSC Part sig \"CX\",1\n"
                "        move.l  %d2,%d0\n"
                "        mulu.w  #30,%d0\n"
                "        adda.l  %d0,%a1\n"
                "        adda.l  #0x8edbc,%a1\n"
                "        mvz.w   (%a1),%d0\n"
                "        cmpi.l  #0x4358,%d0             | \"CX\"\n"
                "        jbne    qz_is_mark\n"
                "        mvz.b   2(%a1),%d0\n"
                "        subq.l  #1,%d0\n"
                "        jbne    qz_is_mark\n"
                "        moveq   #1,%d0\n"
                "        jbra    qz_is_out\n"
                "qz_is_mark:\n"
                "        move.l  %d2,%d0\n"
                "        lsl.l   #2,%d0\n"
                "        add.l   %d2,%d0                 | track * 5\n"
            ),
            "v2.9 FLEX→SYNTH* CX insert",
        )

    # SCALE ON + FUNC: keep po_knob (±12 / octave snap), both Tim shapes.
    kn_old_v22 = (
        "        move.l  %a4,%d1                 | delta: detents, signed\n"
        "        jbeq     qz_k_store\n"
        "        mvz.b   %d6,%d2                 | start from the value the knob was turned from\n"
        "        jbsr     qz_quant\n"
        "qz_k_store:\n"
    )
    kn_new = (
        "        move.l  %a4,%d1                 | delta: detents, signed\n"
        "        jbeq     qz_k_store\n"
        f"        tst.l   {_FUNC_HELD}              | [FUNCTION] held: keep po_knob\n"
        "        jbeq     qz_k_doquant\n"
        f"        tst.l   {_FUNC_ENC_OFF}              | PERSONALIZE: FUNC+ENC off\n"
        "        jbne     qz_k_doquant\n"
        "        jbra     qz_k_store             | octabam: octave snap, not scale degrees\n"
        "qz_k_doquant:\n"
        "        mvz.b   %d6,%d2                 | start from the value the knob was turned from\n"
        "        jbsr     qz_quant\n"
        "qz_k_store:\n"
    )
    if "qz_k_doquant" not in text:
        text = _patch_once(text, kn_old_v22, kn_new, "qz_knob FUNC keep")

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


# The MIDI branch at 0x400449b6 enters the final word of the author's
# eight-byte audio hook: `movel d0,sp@-`. Keep that shared instruction.
# qz_octnum already pushes the audio value and resumes at 0x400449c0, so
# the six-byte jump needs only the preceding audio-only load. #741.
MODULE = dataclasses.replace(
    MODULE,
    linked=tuple(_adapt_unit(_u) for _u in MODULE.linked),
    detours=tuple(
        dataclasses.replace(d, expect=d.expect[:6], pad_to=6)
        if d.site == 0x400449B8 else d for d in MODULE.detours),
    keeps=MODULE.keeps + (Keep(0x400449BE, bytes.fromhex("2f00"),
                               "MIDI CHROMATIC octave argument: branch enters after the audio hook"),),
    gates=MODULE.gates + (Gate("tools/verify/verify_quantizer_ui.py", once=True, venv=True),),
    category=Category.MACHINES, author="timhastie/octatrick-modules",
    author_url="https://github.com/timhastie/octatrick-modules",
    proof=Proof.HARDWARE,
    proof_note="Tim pin; octabam qz_is_synth accepts CX OSC; FUNC+PTCH keeps octave under SCALE",
)
