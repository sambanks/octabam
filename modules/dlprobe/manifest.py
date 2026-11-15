"""DLPROBE -- the demand loader's counters, read out of a track's audio.

A measurement source, not an effect: an insert that replaces its track's audio with a status word per frame
(the layout of PEXT PROBE) carrying, for each demand effect, whether it is bound and how many blocks the copier
received, refused for their sum, and published. modules/dlprobe/README.md is the procedure. A test instrument:
it ships in no remix but remixes/test/dl-probe and dl-probe-any.
"""
from remix.schema import (BusRole, Category, DspSection, Formatter, Gate, Harness, Kind, MenuEntry, Module, Param, Evidence, Level,
                          YBase)

_BLANK = Param(b"", 0)

MODULE = Module(
    name="dlprobe",
    key="DLPROBE",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="sambanks", author_url="https://github.com/sambanks",
    bench_only=True,
    evidence=(Evidence(Level.EMULATOR),),
    doc="Measurement instrument: the demand loader's per-effect counters, in the track's audio.",
    menu=MenuEntry(
        fx2_id=12,                    # EQUALIZER's id: every id 4..31 is taken, so the probe replaces one stock effect
        replaces="EQUALIZER",
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"DLPR",
        fullname=b"DL PROBE",
        build_tag=False,
    ),
    params=(
        Param(b"GO", 0, 2, active=True, formatter=Formatter.STEPPED, labels=("OFF", "ON"),
              doc="unused; the probe always reports"),
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/dlprobe/dlprobe.asm",
        priority=23,
        bus_role=BusRole.NONE,        # an insert
        ybase=YBase.NEVER,            # no buffers, nothing in the shared window
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char=None, is_server=False),
    gates=(Gate("tools/verify/verify_dlprobe.py"),),
)
