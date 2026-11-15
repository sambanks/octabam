"""BusDelay -- a multi-mode delay: CLEAN, GRAIN (pitched), REVERSE.

Two 32K lines on the shipping core (741 ms of TIME): LineL the shared half,
LineR core 1's private FX2 buffer region Y:0x4000-0xBFFF, which the reverb's
tank owns on core 0 and nothing writes on core 1 (port, 15 Sep 2026). The
DEV hatch keeps two 16K lines (tools/remix/geom.py).

Clones SPRING REV's descriptor. A cloned descriptor inherits the donor's
display formatter, which overrides the value count, so every slot below
states its renderer. TIME's formatter is the tempo-sync cave, registered
over slot 0 by that module.
"""

from remix.schema import (Gate, Category, Evidence, Level, ModeView, BusRole, Claims, DspRange, YBase, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

# ---- the P table ----------------------------------------------------------
# SIZE rows, eight words each: REVERSE's [S, 2^23/S, 32704 - 2S] on the left
# and GRAIN's [G-1, G/4, 2^(23-k), 2^(32-k)] on the right, one pad. Rows 0..3
# are the four select positions in the engine's index order; row 4 is the
# garbage row: the engine clamps any index of 4 and up (a stale part byte
# holds 0..127) onto it, row 0's REVERSE half with row 3's GRAIN half. Read
# by delay_server.asm's table block; the build parks it in the stock curve
# bank X:0x4840 beside SPECTRUM's and CHARACTER's tables.
SIZE_ROWS = (
    # index 1 (93 ms) is the panel default; 46 ms is comb territory on
    # sustained sources
    (2048,  4096, 28608, 0x7ff,  0x200, 0x1000, 0x200000, 0),   # 0: 46 ms
    (4096,  2048, 24512, 0xfff,  0x400, 0x800,  0x100000, 0),   # 1: 93 ms (default)
    (1024,  8192, 30656, 0x3ff,  0x100, 0x2000, 0x400000, 0),   # 2: 23 ms
    # 3: XTRM -- REVERSE S = 16384 (371 ms), cap 0: the lag floor is TIME-free
    # at this size, 2S - 2 = 32,766 is the mono ring's oldest valid sample.
    # GRAIN: 8192-sample (186 ms) grains.
    (16384, 512,  0,     0x1fff, 0x800, 0x400,  0x80000,  0),
    (2048,  4096, 28608, 0x1fff, 0x800, 0x400,  0x80000,  0),   # 4+: garbage index
)
# The sticky snap's twelve tempo divisions, M << 11 for M in 2, 3, 4, 6, 8,
# 9, 12, 16, 18, 24, 32, 36 (1/32T .. 1/4.; 1/2 = 48 never fits the 741 ms
# line below 162 BPM, 1/4. fits from 122), smallest first -- last match wins
# in the engine's loop. At offset 40.
SNAP_DIVS = (0x1000, 0x1800, 0x2000, 0x3000, 0x4000,
             0x4800, 0x6000, 0x8000, 0x9000, 0xc000, 0x10000, 0x12000)
# The bus auto-gain's 1/sqrt(N), Q23, indexed by the client count masked to
# 0..7 -- so [0] is 1/sqrt(8), where eight writers wrap to (and a count of 0
# lands harmlessly: the accumulator is zero then). 1/sqrt(N) because
# uncorrelated senders sum as sqrt(N). At offset 52.
RECIP = (0x2d413c, 0x7fffff, 0x5a8279, 0x49e69d,
         0x400000, 0x393e4b, 0x34417a, 0x306123)
PTABLE = tuple(w for row in SIZE_ROWS for w in row) + SNAP_DIVS + RECIP

MODULE = Module(
    name="busdelay",
    key="DELAY SERVER",
    kind=Kind.DSP_EFFECT,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks"),),
    doc="Multi-mode delay: CLEAN / pitched GRAIN cloud / REVERSE, tape wow.",
    menu=MenuEntry(
        fx2_id=0x06,
        donor_desc=0x400d5726,        # SPRING REV
        abbr=b"BDLY",
        fullname=b"BusDelay",
        build_tag=False,              # the tag is added by the XBUS/DEV arms
    ),
    params=(
        # ---- page 1 -------------------------------------------------------
        # DEL / REV on slots 0 / 1, SEND's layout (26 Sep 2026, Sam: "want
        # all the tracks to look the same"): the host page draws these two
        # and nothing else; the rest is the TEMPO window's. DEL is this
        # host's own dry send into the aux, the delay's input; REV its dry
        # send into the reverb's REV accumulator. Both count as clients only
        # while nonzero, so both default to 0.
        Param(b"DEL", 0, active=True, formatter=_PLAIN,
              doc="this track's own send into the delay"),
        Param(b"REV", 0, active=True, formatter=_PLAIN,
              doc="this track's own send into the reverb"),
        Param(b"FDBK", 60, active=True, formatter=_PLAIN,
              doc="feedback: how much each repeat regenerates"),
        Param(b"TONE", 100, active=True, formatter=_PLAIN,
              doc="tone of the repeats: lower is darker on every pass"),
        # PING 0 = centred. Measured at FDBK 60: 0 mono (L/R correlation
        # 1.000), 32 / 64 near-mono (0.998 / 0.965), the alternation is in
        # 96..127 (0.73 / 0.01); 127 leans +4.4 dB left (L gets repeats 1, 3,
        # 5: L/R = 1/feedback).
        Param(b"PING", 0, active=True, formatter=_PLAIN,
              doc="stereo ping-pong; 0 is centred, the alternation comes in over the top quarter"),
        # WET: the repeats' level on this host, wet*WET under its dry. The
        # chain to the reverb carries wet*DLY, DLY being BusVerb's page-2
        # knob (a crossfade until 15 Sep 2026).
        Param(b"WET", 127, active=True, formatter=_PLAIN,
              doc="level of the repeats on this track (the reverb's DLY sets what the reverb hears)"),
        # ---- page 2 -------------------------------------------------------
        # MODE on slot 6: an even slot is the one the panel's page-2 knob
        # editor writes (docs/firmware/MAINMENU.md 9c-ii). The DSP reads $c's
        # KNOB field for it.
        Param(b"MODE", 0, 3, active=True, formatter=_STEP,
              labels=("CLEAN", "GRAIN", "REVRS"),
              doc="engine: CLEAN, GRAIN (a pitched granular cloud) or REVRS (reverse)"),
        # MDEP on slot 7: delivered in $c's companion field (bits 8-15), as
        # stock FILTER's DIST knob is on slot 11. Default 0: an aux delay
        # sits still.
        # SCTR / DENS are GRAIN's (inert in CLEAN and REVERSE); the tape wow
        # that used these slots went 15 Sep 2026.
        Param(b"SCTR", 40, 128, active=True, formatter=_PLAIN,
              doc="GRAIN: how far apart the grains are read; no effect in CLEAN or REVRS"),
        Param(b"DENS", 127, 128, active=True, formatter=_PLAIN, link=True,
              doc="GRAIN: grain density, level stays flat; no effect in CLEAN or REVRS"),
        # SIZE: GRAIN's grain length and REVERSE's segment, one select; drawn
        # GLEN in GRAIN, SLEN in REVERSE, `---` in CLEAN (the mode names it).
        Param(b"SIZE", 1, 4, active=True, formatter=_STEP,
              labels=("46MS", "93MS", "23MS", "XTRM"),
              doc="GRAIN: grain length 46, 93 or 23 ms, XTRM 186 ms. REVRS: segment length, XTRM 371 ms"),
        # PTCH on page-2 slot 10: the DSP reads $e's KNOB field. GRAIN's
        # pitch; idle in other modes.
        Param(b"PTCH", 64, 128, active=True, formatter=_PLAIN, link=True,
              doc="GRAIN: pitch +-2 octaves, 64 unison (a held MIDI note overrides); idle in other modes"),
        # TIME on page-2 slot 11, $e's companion field (page-1 slot 1 until
        # 26 Sep 2026, when WOW left to make room for REV). Tempo-sync's
        # division formatter follows it here.
        Param(b"TIME", 20, 128, active=True, formatter=_PLAIN,
              doc="delay time, 1.5 to 739 ms: a free dial that snaps to tempo divisions when close"),
    ),
    # ---- what each MODE re-defaults, and which knobs it names `---` ------
    # A knob a mode never reads is named `---` there, the unused-knob
    # convention (Sam, 20 Sep 2026: every effect, every mode). SCTR, DENS and
    # PTCH are GRAIN's; SIZE is GRAIN's and REVERSE's; REVERSE pins PING to 0.
    mode_slot=6,
    mode_views=(
        # slots: 11 TIME, 2 FDBK, 3 TONE, 4 PING, 5 MIX, 10 PTCH; DEL and REV
        # at 0 / 1 are never re-defaulted by a mode. TIME is 64 + knob*256 samples since
        # the 32K lines (15 Sep 2026): 20 = 5,184 samples, 18 = 4,672 -- the
        # same times the views held at 40 / 36 under the old *128 law.
        ModeView(mode=0,                        # CLEAN: centred
                 names={7: b"---", 8: b"---", 9: b"---", 10: b"---"},   # SCTR DENS SIZE PTCH: not read
                 defaults={11: 20, 2: 60, 3: 100, 4: 0, 5: 127, 10: 64}),
        ModeView(mode=1,                        # GRAIN: Sam's recipe on the unit
                 # (15 Sep 2026): octave up, ping-pong
                 names={9: b"GLEN"},            # the grain length (Sam, 20 Sep 2026: "size is confusing")
                 defaults={11: 18, 2: 40, 3: 100, 4: 127, 5: 127,
                           7: 40, 8: 127, 9: 1, 10: 96}),
        ModeView(mode=2,                        # REVERSE: centred, 371 ms
                 names={4: b"---", 7: b"---", 8: b"---", 9: b"SLEN", 10: b"---"},   # PING pinned 0; the segment length; SCTR DENS PTCH: not read
                 defaults={11: 20, 2: 60, 3: 100, 4: 0, 5: 127,   # segments (SIZE 3 = XTRM)
                           9: 3, 10: 64}),
    ),
    dsp=DspSection(
        asm="modules/busdelay/delay_server.asm",
        priority=2,                       # last: the region's trailing free
                                          # words are its growth room
        payloads=frozenset({"B"}),        # the core serving tracks 1-4
        bus_role=BusRole.SERVER,
        ybase=YBase.ALWAYS,               # its 32K of lines live at the base
        # DEV puts the delay in payload A; based at 0x30000 its lines would
        # sweep the reverb's buffers, the bus scratch and both role locks
        # every 16,384 samples, so it keeps its shipping base.
        dev_pin_ybase=0x38000,
        r7_latch_slot=0x20,               # payload B tracks its own rotation (raw $20: $84..$8a are the unit's between calls, 21 Sep 2026)
        gate_label="bus_notfirst",
        override_markers=("; DMODE_OVERRIDE", "; DINT_OVERRIDE",
                          "; DNOTE_OVERRIDE"),
        ptable=PTABLE,
    ),
    # The source names 0901h-0903h as this module's RATE/DRV state block; the
    # scan sees 0901 and 0902. 0903 is reserved because whether it is live
    # is not established.
    # LineR is the core's private FX2 buffer region: the ledger refuses a
    # second owner on the same payload (BusVerb's tank is payload A's).
    # LineL is payload B's whole half of the shared window: the write
    # pointer walks base + (phase & $7fff) every sample whatever TIME is.
    claims=Claims(reserved_private_y=(0x0903,), owns_fx2_buffers=True, dsp_ranges=(
        DspRange("y", 0x0000, 0x8000, "LineL", half_relative=True),)),
    harness=Harness(layout_char="D", is_server=True),
    # the GRAIN lever, the tempo feed, and the bus's two-core and one-aux gates
    gates=(Gate('tools/verify/verify_grains.py'),
           Gate('tools/verify/verify_tempo.py'),
           Gate('tools/verify/verify_two_core.py', remix_arg=False),
           Gate('tools/verify/verify_one_bus.py', remix_arg=False)),
    dear={'DEL': 100, 'FDBK': 100, 'MODE': 1, 'SCTR': 127, 'DENS': 127, 'WET': 127},
)
