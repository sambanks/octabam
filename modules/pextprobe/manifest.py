"""PEXT PROBE -- where can a DSP core keep code besides its stock P memory?

A measurement source, not an effect: an insert that replaces its track's audio
with a 32-bit status word per frame (the sign of each of the frame's 32
samples), and, once its GO select is turned, runs a ladder of seven tests: LOW,
a control at P:0x1fe0 and P memory at 0x2000..0x3800; WIN, read, write and
execute at seven words of the shared window. A capture of the track's audio (the USB
audio out) reads the result with modules/pextprobe/decode.py, and keeps it if
the core freezes on the way. modules/pextprobe/README.md is the procedure.

A test instrument: it ships in no remix but remixes/test/pext-probe.
"""
from remix.schema import (BusRole, Category, DspSection, Formatter, Gate, Harness, Kind, MenuEntry, Module,
                          Param, Evidence, Level, YBase)

_BLANK = Param(b"", 0)

MODULE = Module(
    name="pextprobe",
    key="PEXT PROBE",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.EMULATOR),),
    doc="Measurement instrument: tests P memory above P:0x2000 and code in the shared window, and reports it in the track's audio.",
    menu=MenuEntry(
        fx2_id=12,                    # EQUALIZER's id: every id 4..31 is taken, so the probe replaces one stock effect
        replaces="EQUALIZER",
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"PXPR",
        fullname=b"PEXT PROBE",
        build_tag=False,
    ),
    params=(
        Param(b"GO", 0, 3, active=True, formatter=Formatter.STEPPED, labels=("OFF", "LOW", "WIN"),
              doc="OFF idle; LOW P:0x1fe0 control, P:0x2000..0x3800; WIN shared window; a rung per 64 frames"),
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/pextprobe/pextprobe.asm",
        priority=18,
        bus_role=BusRole.NONE,        # an insert
        ybase=YBase.NEVER,            # no buffers, nothing in the shared window
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char=None, is_server=False),
    gates=(Gate("tools/verify/verify_pextprobe.py", remix_arg=False),),
)
