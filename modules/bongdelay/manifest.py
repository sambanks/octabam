"""BongDelay -- a multi-mode delay: CLEAN, GRAIN (pitched), REVERSE.

Hosted on payload B (core 1), which serves TRACKS 1-4. Any track can send
into it, and its wet can be sent on into ChonVerb over the bus (-VRB) -- the
delay-into-reverb series topology the stock firmware has no path for.

Clones SPRING REV's descriptor. That inheritance shipped a defect once: until
17 Aug 2026 the formatter pass was gated to the reverb, so three of six
page-2 slots here drew as whatever SPRING REV drew -- WOW drew no knob at
all, MODE drew as a balance dial reading -64..-60. Every slot below states
its renderer for that reason.

TIME's display formatter is not one of the two below: it is a ColdFire code
cave that prints the tempo division while the DSP's sticky snap holds one,
installed by the tempo-sync patch and registered over slot 0 afterwards.
"""

from remix.schema import (BusRole, Claims, YBase, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="bongdelay",
    key="DELAY SERVER",
    kind=Kind.DSP_EFFECT,
    doc="Multi-mode delay: CLEAN / pitched GRAIN cloud / REVERSE, tape wow, drive, freeze.",
    menu=MenuEntry(
        fx2_id=0x06,
        donor_desc=0x400d5726,        # SPRING REV
        abbr=b"BDLY",
        fullname=b"BongDelay",
        build_tag=False,              # the tag is added by the XBUS/DEV arms
    ),
    params=(
        # ---- page 1 -------------------------------------------------------
        Param(b"TIME", 40, active=True, formatter=_PLAIN,
              doc="delay time -- a free dial that sticky-snaps to tempo divisions"),
        Param(b"FDBK", 60, active=True, formatter=_PLAIN,
              doc="feedback -- how much each repeat regenerates"),
        Param(b"TONE", 100, active=True, formatter=_PLAIN,
              doc="tone of the repeats -- lower = darker every pass"),
        # PING 127, not 64. Measured 17 Aug 2026: 64 was the worst place on
        # the knob to boot -- it leaned +14.7 dB left with correlation 0.185,
        # i.e. more lean than 127 and no audible bounce. 127 is the classic
        # ping-pong, and where the lean is smallest.
        Param(b"PING", 127, active=True, formatter=_PLAIN,
              doc="stereo ping-pong spread; 127 = the classic alternation (least lean)"),
        # -VRB: this delay's wet send into the reverb. 0 for the same
        # load-bearing reason as IN -- a non-zero default would register the
        # delay as a reverb client whenever it exists, idle or not, diluting
        # every real sender.
        Param(b"-VRB", 0, active=True, formatter=_PLAIN,
              doc="wet send into ChonVerb over the bus -- delay into reverb in series"),
        # PTCH sits where IN did (v5.1, 3 Sep 2026): the host's own send is its
        # FX1 station's ->DEL now, and GRAIN's pitch belongs on the scene page.
        Param(b"PTCH", 64, active=True, formatter=_PLAIN,
              doc="GRAIN pitch, +-2 oct, 64 = unison (a held MIDI note overrides); idle in other modes"),
        # ---- page 2 -------------------------------------------------------
        Param(b"MDEP", 48, 128, active=True, formatter=_PLAIN,
              doc="tape mod (wow) depth; 0 = none - GRAIN: scatter, how far apart the grains read"),
        # v5 (3 Sep 2026): three real positions, nothing dead. The parts that
        # stored PITCH (1) get GRAIN, which is its harmoniser now; the stamper
        # writes fresh defaults for a replaced/renumbered effect anyway (plan A6).
        Param(b"MODE", 0, 3, active=True, formatter=_STEP,
              labels=("CLEAN", "GRAIN", "REVRS"),
              doc="engine select: CLEAN, GRAIN (pitched cloud, v5), REVERSE"),
        # RATE 64 IS LOAD-BEARING: exactly 1x, the pre-knob modulation speed.
        # The DPTH=0 bypass gate only holds with the law exact here.
        Param(b"MRAT", 64, 128, active=True, formatter=_PLAIN,
              doc="tape mod (wow) rate, 64 = 1x - GRAIN: density, full dial, level-flat (R61)"),
        # SIZE (the PTCH slot until v5): GRAIN's grain length and REVERSE's
        # segment, one select read the same way by both. Count stays 4.
        Param(b"SIZE", 1, 4, active=True, formatter=_STEP,
              labels=("46MS", "93MS", "23MS", "XTRM"),
              doc="segment/grain size 46/93/23 ms; XTRM = 12 ms REVERSE, 186 ms GRAIN"),
        # DRV is drive in every mode but GRAIN, where the same byte is the
        # scatter depth. 0 = exact bypass, which outranks a scatter taste
        # that gets played by hand anyway.
        Param(b"DRV", 0, 128, active=True, formatter=_PLAIN,
              doc="drive on the repeats, every mode; 0 = bypass"),
        Param(b"FRZE", 0, 2, active=True, formatter=_STEP,
              labels=("RUN", "HOLD"),
              doc="freeze the line as a loop -- loop length = TIME"),
    ),
    dsp=DspSection(
        asm="modules/bongdelay/delay_server.asm",
        priority=2,                       # LAST, deliberately: the trailing
                                          # free words of the region belong to
                                          # the algorithm still being designed
        # Payload B -> the core serving TRACKS 1-4 (the 10 Aug 2026 track/core
        # inversion). The build's SPEC table still hardcodes this pairing;
        # here it is stated so the remixer can derive the track range.
        payloads=frozenset({"B"}),
        bus_role=BusRole.SERVER,
        ybase=YBase.ALWAYS,               # its 32K of lines live at the base
        # DEV puts the delay in payload A, but based at 0x30000 its lines
        # would sweep the reverb's buffers, the bus scratch and both role
        # locks every 16,384 samples. It keeps its shipping base instead.
        dev_pin_ybase=0x38000,
        r7_latch_slot=0x86,               # payload B tracks its own rotation
        gate_label="bus_notfirst",
        override_markers=("; DMODE_OVERRIDE", "; DINT_OVERRIDE",
                          "; DFRZ_OVERRIDE", "; DNOTE_OVERRIDE"),
    ),
    # 0901h-0903h is named in the source as this module's RATE/DRV state
    # block. The scan sees 0901 and 0902; 0903 is reserved here because the
    # comment claims the block and DRIVE's d was later moved to r7+$83, so
    # whether 0903 is live is not established. Reserving a word nobody uses
    # costs nothing; letting a second module take one that is quietly live
    # costs a hardware session.
    claims=Claims(reserved_private_y=(0x0903,)),
    harness=Harness(layout_char="D", is_server=True),
)
