"""SHATTER -- multi-stage crush with chaotic feedback.

A per-track insert: DRV into a wavefolder, hard or soft clip, combined
bit/sample-rate crush, then a feedback loop with a tone shelf. MODE CHAOS
flips feedback polarity from a free-running ramp. MIX 0 is bit-exact dry.
"""

from remix.schema import (BusRole, Category, DspSection, Formatter, Gate, Harness,
                          Kind, MenuEntry, Module, Param, Proof, YBase)

_P = Formatter.PLAIN
_S = Formatter.STEPPED
_BLANK = Param(b"", 0)

MODULE = Module(
    name="shatter",
    key="SHATTER",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="ilia-murzinov",
    author_url="https://github.com/ilia-murzinov",
    proof=Proof.HARDWARE,
    proof_note="Ilia's MKII, remix shatter BUILD S6 (SHATTER S6.RMX), 21 Oct 2026: "
               "every page-1/page-2 knob exercised (CLIP open + FDBK for MODE/"
               "TONE/RATE); verify_shatter",
    doc="Crush insert: drive, fold, clip, bit/SRR crush, self-modulating FDBK (CHAOS).",
    menu=MenuEntry(
        fx2_id=0x0a,
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"SHTR",
        fullname=b"Shatter",
        build_tag=False,
    ),
    params=(
        Param(b"DRV", 0, active=True, formatter=_P,
              doc="pre-gain on the dry, about x9 at 127; 0 is unity; the feedback is not driven"),
        Param(b"FOLD", 0, active=True, formatter=_P,
              doc="wavefolder; 0 is off, higher folds more (never quieter)"),
        Param(b"CLIP", 0, active=True, formatter=_P,
              doc="clip threshold: 0 is open, 127 is a brick wall"),
        Param(b"CRSH", 0, active=True, formatter=_P,
              doc="bit-depth and sample-rate crush together"),
        Param(b"FDBK", 0, active=True, formatter=_P,
              doc="feedback around the fold, clip and crush; CHAOS flips its polarity"),
        Param(b"MIX", 127, active=True, formatter=_P,
              doc="dry/wet; 0 is exact passthrough"),
        Param(b"MODE", 0, 3, active=True, formatter=_S,
              labels=("HARD", "SOFT", "CHAOS"),
              doc="HARD clip, SOFT (cubic) clip, or CHAOS (the feedback polarity flips)"),
        Param(b"TONE", 64, active=True, formatter=_P,
              doc="shelf in the feedback loop: 0 dark, 127 bright"),
        Param(b"RATE", 64, active=True, formatter=_P,
              doc="CHAOS: how fast the polarity flips; ignored in HARD and SOFT"),
        _BLANK, _BLANK, _BLANK,
    ),
    mode_slot=6,
    dsp=DspSection(
        asm="modules/shatter/shatter.asm",
        priority=18,
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char="4", is_server=False),  # B = stock MULTIBCOMP

    gates=(Gate("tools/verify/verify_shatter.py", remix_arg=False),),
    dear={"DRV": 127, "FOLD": 127, "CLIP": 100, "CRSH": 100, "FDBK": 80,
          "MIX": 127, "MODE": 2, "TONE": 100, "RATE": 100},
)
