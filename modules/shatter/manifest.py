"""SHATTER -- multi-stage crush with chaotic feedback and a post-MIX ceiling.

A per-track insert: DRV into a wavefolder, hard or soft clip, combined
bit/sample-rate crush, then a feedback loop with a tone shelf. MODE CHAOS
flips feedback polarity from a free-running ramp. LIM is a stereo-linked
peak limiter after MIX (current-block peak + one block-rate div). MIX 0 is
bit-exact dry when LIM is 0.
"""

from remix.peak_limiter import source as peak_limiter_source
from remix.schema import (BusRole, Category, DspSection, Formatter, Gate, Harness,
                          Kind, Linked, MenuEntry, Module, Param, Proof, YBase)

_P = Formatter.PLAIN
_BLANK = Param(b"", 0)
_UI = "shatter_ui"
# Raw A=0 matches Formatter.PLAIN; B is the live icon (see ui.s).
_W = lambda sym: dict(formatter_word=0, widget_word=(_UI, sym))

MODULE = Module(
    name="shatter",
    key="SHATTER",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="ilia-murzinov",
    author_url="https://github.com/ilia-murzinov",
    proof=Proof.CHECK,
    proof_note="Current-block stereo limiter gated in verify_shatter; "
               "unity below ceiling; LIM 127 about -2.5 dBFS. "
               "New limiter awaits hardware confirmation; prior LIM tests used the old curve.",
    doc="Crush insert: fold, clip, crush, chaotic FDBK, stereo peak limiter after MIX.",
    menu=MenuEntry(
        fx2_id=0x0a,
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"SHTR",
        fullname=b"SHATTER",
        build_tag=False,
    ),
    params=(
        Param(b"DRV", 0, active=True, formatter=_P,
              doc="pre-gain on the dry, about x9 at 127; 0 is unity; the feedback is not driven"),
        Param(b"FOLD", 0, active=True, **_W("wid_fold"),
              doc="wavefolder; 0 is off, higher folds more (never quieter)"),
        Param(b"CLIP", 0, active=True, **_W("wid_clip"),
              doc="clip threshold: 0 is open, 127 is a brick wall"),
        Param(b"CRSH", 0, active=True, **_W("wid_crsh"),
              doc="bit-depth and sample-rate crush together"),
        Param(b"FDBK", 0, active=True, **_W("wid_fdbk"),
              doc="feedback around the fold, clip and crush; CHAOS flips its polarity"),
        Param(b"MIX", 127, active=True, formatter=_P,
              doc="dry/wet; 0 is exact passthrough when LIM is 0"),
        # MODE: DRAM label formatter + live icon (brick/blob/shards). Labels
        # also feed the help row; raw words own the panel drawing.
        Param(b"MODE", 0, 3, active=True, labels=("HARD", "SOFT", "CHAOS"),
              formatter_word=(_UI, "fmt_mode"), widget_word=(_UI, "wid_mode"),
              doc="HARD clip, SOFT (cubic) clip, or CHAOS (the feedback polarity flips)"),
        Param(b"TONE", 64, active=True, **_W("wid_tone"),
              doc="shelf in the feedback loop: 0 dark, 127 bright"),
        Param(b"RATE", 64, active=True, **_W("wid_rate"),
              doc="CHAOS: how fast the polarity flips; ignored in HARD and SOFT"),
        # count=128 overrides DARK GATE's 0/1 companion (count None = donor).
        Param(b"LIM", 0, 128, active=True, formatter=_P,
              doc="stereo peak limiter after MIX; 0 off, 1..127 ceiling ~0..-2.5 dB"),
        _BLANK, _BLANK,
    ),
    mode_slot=6,
    dsp=DspSection(
        asm="modules/shatter/shatter.asm",
        subst={pl: peak_limiter_source("shpk", 0x19, 0xd, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, knob=0xd) for pl in ("A", "B")},
        priority=18,
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    linked=(Linked(_UI, "modules/shatter/ui.s", cpu="5475", dram=True),),
    harness=Harness(layout_char="4", is_server=False),  # B = stock MULTIBCOMP

    gates=(Gate("tools/verify/verify_shatter.py", remix_arg=False),),
    dear={"DRV": 127, "FOLD": 127, "CLIP": 100, "CRSH": 100, "FDBK": 80,
          "MIX": 127, "MODE": 2, "TONE": 100, "RATE": 100, "LIM": 100},
)
