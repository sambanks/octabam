"""CF METER -- a probe: the frame interrupt's duration (and, with CF METER
IDLE, the ColdFire's idle time) on the unit, and core 0's own frame
budget, read out as audio from track 8.

The ColdFire unit (`meter.s`, DRAM) wraps the frame interrupt (vector 0x41:
main's install names `m_isr` instead of the stock handler) with an entry
stamp on DMA timer 3 and a BURN of 2 us per step, and replaces the
handler's epilogue with an exit stamp and the publisher. Every 125 ms the
publisher advances a 16-slot cycle: slots 0..7 carry its own values into
track 8's FX2 page-2 lane beside a fixed reference and the slot number;
for slots 8..15 the DSP insert (`meter_out.asm`) on T8's FX2 prints what
it measured itself on core 0: the spin count of the wait for the next
frame (min / max), ESAI underrun and overrun frames, the frame period on
timer 0 (min / max) and the frame count. `tools/harness/cfmeter.py`
decodes a capture. README.md has the procedure. With WAVE LOAD in the
remix, BURN is the number of wave engines rendered per frame instead
(modules/waveload/README.md).
"""

from remix.schema import (BusRole, Category, Detour, DspSection, Formatter, Gate, Harness, Kind,
                          Linked, MenuEntry, Module, Param, Evidence, Level, YBase)

_BLANK = Param(b"", None, active=False)


def load_inc(modules, remix):
    """WAVE LOAD in the remix: m_isr calls its cl_load with BURN as K. And
    HOOKS's flags: beside LOAD METER or BOOT TRACE, m_tail returns and HOOKS
    replays the epilogue (modules/hooks, frame_tail)."""
    from remix import hooks_flags
    return (("        .set    WAVE_LOAD, 1\n" if "WAVE LOAD" in modules else "")
            + hooks_flags.inc("CF METER", modules))


MODULE = Module(
    name="cfmeter", key="CF METER", kind=Kind.HYBRID,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); ColdFire half on image 92 (Sam's MKII, 3 "
             "Oct 2026: interrupt 123.1 us stopped, 213.5 us playing); the DSP slots and DBRN under the port only "
             "(4 Oct 2026)"),),
    doc="Probe: frame-interrupt duration and (with CF METER IDLE) idle time, plus core 0's frame spin count, "
        "ESAI underrun/overrun frames and frame period, printed as audio on T8's FX2.",
    menu=MenuEntry(fx2_id=0x0e, donor_desc=0x400d4772,  # FILTER
                   abbr=b"CFMT", fullname=b"CF Meter", build_tag=False),
    params=(
        Param(b"BURN", 0, active=True, formatter=Formatter.PLAIN,
              doc="read on track 8 only: 2 us of busy-wait per step at the start of every frame interrupt"),
        Param(b"MEM", 0, active=True, formatter=Formatter.PLAIN,
              doc="track 8 only: MEM KB read after the burn, a longword per 16-byte line, timed into slot 7"),
        Param(b"DBRN", 0, active=True, formatter=Formatter.PLAIN,
              doc="24 x DBRN DSP cycles per sample burnt before the sample loop; slots 8/9 fall by it"),
        _BLANK,
        Param(b"SPAN", 0, active=True, formatter=Formatter.PLAIN,
              doc="slot 7: 0 BURN or the walk, 1 HC polls, 2 eDMA handler time inside the ISR, 3 all of it"),
        Param(b"SRC", 0, active=True, formatter=Formatter.PLAIN,
              doc="what MEM walks: 0 cached SDRAM (the OS), 1 its uncached alias, 2 on-chip SRAM (MEM <= 31)"),
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(asm="modules/cfmeter/meter_out.asm", priority=15, bus_role=BusRole.NONE,
                   ybase=YBase.NEVER, r7_latch_slot=None, gate_label=None),
    linked=(Linked("cfmeter", "modules/cfmeter/meter.s", dram=True, include=load_inc),),
    detours=(
        Detour(0x4001fbf8, bytes.fromhex("48794000aad0"), "cfmeter", "m_isr",
               "main's install of vector 0x41 (the frame interrupt): pea m_isr", kind="lea"),
        Detour(0x4000d9a6, bytes.fromhex("4cd77fff4fef00fc4e73"), "cfmeter", "m_tail",
               "the frame interrupt's epilogue, every exit path: the exit stamp", pad_to=10),
        Detour(0x4000ab26, bytes.fromhex("3039200000044a006df6"), "cfmeter", "m_hc1",
               "the frame interrupt's HC poll loop, timed", pad_to=10),
        Detour(0x4000a90c, bytes.fromhex("3039200000044a006df6"), "cfmeter", "m_hc2",
               "the second HC poll loop (0x4000a8fc), timed", pad_to=10),
        Detour(0x40004840, bytes.fromhex("4feffff048d70303"), "cfmeter", "m_e6",
               "the level-6 eDMA handler's entry: the entry stamp", pad_to=8),
        Detour(0x40004bc8, bytes.fromhex("4cd703034fef00104e73"), "cfmeter", "m_e6x",
               "the level-6 eDMA handler's exit: its duration, and the share inside the frame interrupt", pad_to=10),
    ),
    harness=Harness(layout_char=None, is_server=False),
    gates=(Gate("tools/verify/verify_cfmeter.py", venv=True),),
)
