"""Full-rate, modulated four-branch diffused FDN insert with allocator-owned memory."""
from remix.schema import (Gate, Category, Evidence, Level, BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, Module, Param, YBase)

MODULE = Module(
    name="miniverb", key="MINIVERB", kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="repeat98", author_url="https://github.com/repeat98",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); `make verify-miniverb`"),),
    doc="Modulated diffused FDN reverb; independent FX2 buffers, smoothed controls.",
    menu=MenuEntry(fx2_id=0x16, replaces="DARK REV", donor_desc=0x400d58b8,
                   abbr=b"MINI", fullname=b"Mini Verb", build_tag=False),
    params=(
        Param(b"DECAY", 104, active=True, formatter=Formatter.PLAIN,
              doc="feedback 0.65 to 0.97; the room size is fixed"),
        Param(b"DAMP", 70, active=True, formatter=Formatter.PLAIN,
              doc="higher values darken the tail"),
        Param(b"MIX", 40, active=True, formatter=Formatter.PLAIN,
              doc="dry/wet, smoothed; 0 dry, 127 wet"),
        Param(b"MOD", 80, active=True, formatter=Formatter.PLAIN,
              doc="depth of two in-loop allpass modulators, smoothed, 0 to 64 samples"),
        Param(b"RATE", 2, count=8, active=True, formatter=Formatter.STEPPED,
              labels=("0.34", "0.67", "1.01", "1.35", "1.68", "2.02", "2.36", "2.69"),
              doc="modulation speed in Hz, 0.34 to 2.69"),
        *(Param() for _ in range(7)),
    ),
    dsp=DspSection(asm="modules/miniverb/miniverb.asm", priority=15,
                   bus_role=BusRole.NONE, ybase=YBase.NEVER,
                   r7_latch_slot=None, gate_label=None),
    claims=Claims(stock_instance_buffer=True, buffer_words=15870),
    harness=Harness(layout_char="7", is_server=False),
    gates=(Gate('tools/verify/verify_miniverb.py', stage='image'),),
)
