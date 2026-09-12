"""BusDelay -- a multi-mode delay: CLEAN, GRAIN (pitched), REVERSE.

Hosted on payload B (core 1), which serves TRACKS 1-4. Any track can send
into it, and its wet can be sent on into BusVerb over the bus (-VRB) -- the
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

from remix.schema import (ModeView, BusRole, Claims, YBase, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="busdelay",
    key="DELAY SERVER",
    kind=Kind.DSP_EFFECT,
    doc="Multi-mode delay: CLEAN / pitched GRAIN cloud / REVERSE, tape wow, freeze.",
    menu=MenuEntry(
        fx2_id=0x06,
        donor_desc=0x400d5726,        # SPRING REV
        abbr=b"BDLY",
        fullname=b"BusDelay",
        build_tag=False,              # the tag is added by the XBUS/DEV arms
    ),
    params=(
        # ---- page 1 -------------------------------------------------------
        # THE ONE-AUX RE-SLOT (7 Sep 2026): AUX at slot 0 on EVERY track,
        # hosts included -- this host's own dry send into the aux (the IN /
        # ->DEL machinery: headroomed, summed, counted only while nonzero).
        Param(b"AUX", 0, active=True, formatter=_PLAIN,
              doc="this track's send into the one aux bus (delay, then reverb, back on T8)"),
        Param(b"TIME", 40, active=True, formatter=_PLAIN,
              doc="delay time -- a free dial that sticky-snaps to tempo divisions"),
        Param(b"FDBK", 60, active=True, formatter=_PLAIN,
              doc="feedback -- how much each repeat regenerates"),
        Param(b"TONE", 100, active=True, formatter=_PLAIN,
              doc="tone of the repeats -- lower = darker every pass"),
        # PING 0 = centred (12 Sep 2026, Sam: an aux delay on a mixer sits in
        # the middle; the bounce is the knob's). Measured on the loop at FDBK
        # 60: 0 mono (L/R correlation 1.000), 32 / 64 near-mono (0.998 /
        # 0.965), the alternation lives in 96..127 (0.73 / 0.01), and 127
        # leans +4.4 dB left -- the arithmetic of ping-pong itself (L gets
        # repeats 1, 3, 5: L/R = 1/feedback), not a defect. The 17 Aug note
        # that 64 leaned +14.7 dB is not what the current code measures.
        Param(b"PING", 0, active=True, formatter=_PLAIN,
              doc="stereo ping-pong spread; 0 = centred, the alternation is in the top quarter"),
        # MIX (one-aux rig, 7 Sep 2026; -VRB and PTCH moved): the STAGE's
        # crossfade. The delay is chain stage 1: out = in*(1-MIX) + wet*MIX
        # goes on to the reverb and to the return, so MIX 0 is a clean
        # reverb send with the delay still in the chain and 127 the old
        # wet-only behaviour. The chain itself is hardwired, unscaled.
        Param(b"MIX", 127, active=True, formatter=_PLAIN,
              doc="stage dry/wet: 0 passes the aux through, 127 = repeats only"),
        # ---- page 2 -------------------------------------------------------
        # MODE on slot 6 (v6, 4 Sep 2026; was slot 7): an even slot is the
        # proven slot the panel's page-2 knob editor writes, so a main-menu
        # screen can set it
        # through the firmware's own routine (docs/firmware/MAINMENU.md 9c-ii). The DSP
        # reads $c's KNOB field for it now. A part saved before the swap loads
        # its old MDEP byte as MODE (48 clamps to REVRS) and 0/1/2 as MDEP;
        # re-select the effect or stamp defaults.
        # v5 (3 Sep 2026): three real positions, nothing dead. The parts that
        # stored PITCH (1) get GRAIN, which is its harmoniser now; the stamper
        # writes fresh defaults for a replaced/renumbered effect anyway (plan A6).
        Param(b"MODE", 0, 3, active=True, formatter=_STEP,
              labels=("CLEAN", "GRAIN", "REVRS"),
              doc="engine select: CLEAN, GRAIN (pitched cloud, v5), REVERSE"),
        # MDEP on slot 7: delivered in $c's companion field (bits 8-15), as
        # stock FILTER's DIST knob is on slot 11.
        # MDEP 0 (12 Sep 2026, Sam): the wow at 48 read as motion/panning on a
        # mono loop; a mixer's aux delay sits still by default, the wow is the knob's.
        Param(b"MDEP", 0, 128, active=True, formatter=_PLAIN,
              doc="tape mod (wow) depth; 0 = none - GRAIN: scatter, how far apart the grains read"),
        # RATE 64 IS LOAD-BEARING: exactly 1x, the pre-knob modulation speed.
        # The DPTH=0 bypass gate only holds with the law exact here.
        Param(b"MRAT", 64, 128, active=True, formatter=_PLAIN,
              doc="tape mod (wow) rate, 64 = 1x - GRAIN: density, full dial, level-flat (R61)"),
        # SIZE (the PTCH slot until v5): GRAIN's grain length and REVERSE's
        # segment, one select read the same way by both. Count stays 4.
        Param(b"SIZE", 1, 4, active=True, formatter=_STEP,
              labels=("46MS", "93MS", "23MS", "XTRM"),
              doc="segment/grain size 46/93/23 ms; XTRM = 12 ms REVERSE, 186 ms GRAIN"),
        # PTCH on page-2 slot 10 (one-aux re-slot, 7 Sep 2026; page-1 slot
        # 5 until then, which is MIX now). The DSP reads $e's KNOB field for
        # it. GRAIN's pitch; idle in other modes.
        Param(b"PTCH", 64, 128, active=True, formatter=_PLAIN,
              doc="GRAIN pitch, +-2 oct, 64 = unison (a held MIDI note overrides); idle in other modes"),
        Param(b"FRZE", 0, 2, active=True, formatter=_STEP,
              labels=("RUN", "HOLD"),
              doc="freeze the line as a loop -- loop length = TIME"),
    ),
    # ---- what each MODE renames and re-defaults (v5.1, 3 Sep 2026) --------
    # MDEP and MRAT are the tape modulation depth and rate in CLEAN and
    # REVERSE, and the grain scatter and density in GRAIN; PTCH is the grain
    # pitch and idle elsewhere. The panel printed one name for both meanings
    # until this table existed.
    mode_slot=6,
    mode_views=(
        # (slots are the one-aux layout: 1 TIME, 2 FDBK, 3 TONE, 4 PING,
        # 5 MIX, 10 PTCH -- AUX at 0 is never re-defaulted by a mode)
        ModeView(mode=0,                        # CLEAN: centred, no wow (12 Sep 2026)
                 defaults={1: 40, 2: 60, 3: 100, 4: 0, 5: 127,
                           7: 0, 8: 64, 10: 64}),
        ModeView(mode=1,                        # GRAIN
                 names={7: b"SCAT", 8: b"DENS"},   # PTCH is PTCH in every mode
                 defaults={1: 36, 2: 40, 3: 100, 4: 0, 5: 127,
                           7: 40, 8: 127, 9: 1, 10: 64}),
        ModeView(mode=2,                        # REVERSE: centred, no wow
                 defaults={1: 40, 2: 60, 3: 100, 4: 0, 5: 127,
                           7: 0, 8: 64, 9: 1, 10: 64}),
    ),
    dsp=DspSection(
        asm="modules/busdelay/delay_server.asm",
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
