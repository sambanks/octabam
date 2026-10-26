"""EXTPROBE -- how far into its slot does a stock reverb write?

A measurement source, not an effect: an insert that fills the shared window's view of one FX2 slot with a
pattern, scans it, and reports in its track's audio the highest word that no longer matches and how many
words differ per 1,024-word bucket. modules/extprobe/README.md is the procedure. A test instrument: it
ships in no remix but remixes/test/ext-probe.
"""
from remix.schema import (BusRole, Category, DspSection, Formatter, Gate, Harness, Kind, MenuEntry, Module, Param,
                          Proof, YBase)

_BLANK = Param(b"", 0)

MODULE = Module(
    name="extprobe",
    key="EXTPROBE",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.CHECK, proof_note="",
    doc="Measurement instrument: the highest window word a reverb on T8's FX2 writes, in the track's audio.",
    menu=MenuEntry(
        fx2_id=12,                    # EQUALIZER's id: every id 4..31 is taken, so the probe replaces one stock effect
        replaces="EQUALIZER",
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"EXPR",
        fullname=b"EXT PROBE",
        build_tag=False,
    ),
    params=(
        Param(b"GO", 0, 3, active=True, formatter=Formatter.STEPPED, labels=("OFF", "FILL", "SCAN"),
              doc="OFF touches nothing; FILL writes the pattern over T8's slot, then scans; SCAN counts without filling"),
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/extprobe/extprobe.asm",
        priority=24,
        bus_role=BusRole.NONE,        # an insert
        ybase=YBase.NEVER,            # no buffers of its own
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char=None, is_server=False),
    gates=(Gate("tools/verify/verify_extprobe.py", remix_arg=False),),
)
