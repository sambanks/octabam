"""CPU Tape Echo -- one mono head in the stock four-second CPU delay ring.

FX2 SPRING REV's id and controls are retained. The DSP dispatch is dry;
ColdFire replaces only this id's post-FX2 filter/mix, retaining stock DMA.
FREE uses a smoothed motor; BEAT snaps TIME to twelve note divisions.
The economy fixed-point voice approximates the measured pedal/Galaxy response;
physical-cell tape transport and spring reverb remain omitted. See README for measured gates
and the outstanding hardware cycle/listening checks.
"""

from remix.schema import (Gate, Category, Evidence, Level, BusRole, CavePatch, Detour, DspSection, Formatter, FormatterReg, Harness,
                          Kind, Linked, MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="tapeecho",
    key="TAPE ECHO",
    kind=Kind.HYBRID,
    category=Category.TRACK, author="repeat98", author_url="https://github.com/repeat98",
    evidence=(Evidence(Level.UNIT,
        note="the author's unit (OCTACLID4): six instances run, a seventh freezes it, open"),),
    doc="Economy CPU tape echo: two biquads, simple FREE slew, snapped BEAT TIME and page-1 AGE.",
    menu=MenuEntry(
        fx2_id=0x15,
        replaces="SPRING REV",
        donor_desc=0x400d5726,        # SPRING REV: all twelve descriptor slots
        abbr=b"TAPE",
        fullname=b"Tape Echo",
        build_tag=False,
    ),
    params=(
        # ---- page 1: live performance surface ---------------------------
        Param(b"TIME", 64, active=True, formatter=_PLAIN,
              doc="FREE: 46..231 ms; BEAT: twelve note divisions from 1/64 to dotted 1/4"),
        Param(b"FDBK", 64, active=True, formatter=_PLAIN,
              doc="repeat intensity; the top of the range self-oscillates from tape noise"),
        Param(b"WOW", 25, active=True, formatter=_PLAIN,
              doc="0.8 Hz wow plus irregular flutter; about 8 cents at 44, 22 cents at 127"),
        Param(b"AGE", 64, 128, active=True, formatter=_PLAIN,
              doc="repeat bandwidth, flutter and noise; fresh at 0, worn at 127"),
        Param(b"SYNC", 0, 2, active=True, formatter=_STEP,
              labels=("FREE", "BEAT"),
              doc="FREE sets TIME in milliseconds; BEAT snaps it to note divisions of the project tempo"),
        Param(b"MIX", 90, active=True, formatter=_PLAIN,
              doc="dry/wet; 0 is exact passthrough"),
        # ---- detail/setup page (stock effect page 2) ---------------------
        Param(),  # former DRIVE: fixed at zero, including previously saved parts
        Param(),  # AGE moved to page 1; old page-2 values are ignored
        Param(), Param(), Param(), Param(),
    ),
    dsp=DspSection(
        asm="modules/tapeecho/cpu_passthrough.asm",
        priority=14,
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    cf_patches=(CavePatch(
        label="Tape TIME formatter", cave_addr=None,
        pinned=bytes.fromhex(
            "7000103980000003028000000003223c000018b24c010000207946c82456"
            "2208674ad1c0700010398000000002800000000772184c010000d1c0d1fc"
            "0008eeb04a106728202f000802800000007f720c4c010000ee8841fa0050"
            "720012300800d1c12f4800084ef940013a08202f000802800000007fed88"
            "068000000800720a4c010000223c000001b94c4100002f4000082f00487a"
            "005b2f2f000c4eb940013a084fef000c4e750c11171c22272c32363b4044"
            "312f363400312f33325400312f333200312f31365400312f313600312f38"
            "5400312f31362e00312f3800312f345400312f382e00312f3400312f342e"
            "00256400"),
        source="modules/tapeecho/time_fmt.s",
        registers_formatter=FormatterReg(module="TAPE ECHO", slot=0),
    ),),
    # Platform objects use the common ISA-B ELF tag; generate_cpu.py also
    # assembles for the real 54454 and checks that both text streams match.
    linked=(Linked("tapeecho", "modules/tapeecho/cpu.s", cpu="5475", dram=True),),
    detours=(Detour(0x40002f44, bytes.fromhex("4feffff048d7003c"),
                   "tapeecho", "te_cpu_reset", "reset CPU Tape Echo with stock delay rings", pad_to=8),
             Detour(0x4000361a, bytes.fromhex("2a6f005c2039800000e8"),
                   "tapeecho", "te_cpu_hook", "CPU Tape Echo in the stock track-delay path",
                   pad_to=10),),
    harness=Harness(layout_char="6", is_server=False),
    gates=(Gate('tools/verify/verify_tapeecho_cpu.py', venv=True, stage='image'),),
)
