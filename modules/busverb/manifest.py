"""BusVerb -- an eight-line FDN reverb with shimmer, gating and mode select.

Hosted on payload A (core 0), which serves TRACKS 5-8 -- measured 10 Aug 2026
and inverted from what every doc assumed before then. Test it on track 5.
Any track can send into it over the bus.

Clones DARK REV's descriptor. Slot 0 is written with the name the donor
already carries (TIME), so the write is a no-op in bytes but the label is
stated here rather than inherited silently -- the harness reads these names,
and a name that exists only in a donor is a name no tool can see. (Slots 3
and 4 were the donor's HP/LP until v8; they are TONE and -DEL now.)
"""

from remix.schema import (BusRole, Claims, YBase, DspSection, Formatter,
                          Harness, Kind, MenuEntry, Module, Param)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="busverb",
    key="REVERB SERVER",
    kind=Kind.DSP_EFFECT,
    doc="Eight-line FDN reverb: ROOM/PLATE/BIG, shimmer, gate, mid/side width.",
    menu=MenuEntry(
        fx2_id=0x07,
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"BVRB",
        fullname=b"BusVerb",
        build_tag=True,
    ),
    params=(
        # ---- page 1 -------------------------------------------------------
        Param(b"TIME", 64, active=True, formatter=_PLAIN,
              doc="decay time -- how long the tail rings"),
        Param(b"MOD", 30, active=True, formatter=_PLAIN,
              doc="tank modulation depth -- 0 static, high = chorused tail; speed is RATE"),
        Param(b"SIZE", 100, active=True, formatter=_PLAIN,
              doc="room size -- scales the eight tank lines (taps up to ~89 ms)"),
        # TONE (v8, 5 Sep 2026) is the old HP + LP pair on ONE knob, so that
        # slot 4 can carry the host's ->DEL send: 0..64 closes the high cut
        # (dark), 64..127 opens the low cut inside the loop (thin). 64 IS the
        # old defaults (HP 0 / LP 127), bit-identical.
        Param(b"TONE", 64, active=True, formatter=_PLAIN,
              doc="tail tone: below 64 darkens (high cut), above 64 thins (low cut); 64 = flat"),
        # -DEL: this track's dry into BusDelay over the bus -- the host's own
        # send pair, now that its FX2 page is where the sends live. 0 for the
        # same load-bearing reason as IN: a non-zero default would register
        # every idle host as a delay client and dilute the real senders.
        Param(b"-DEL", 0, active=True, formatter=_PLAIN,
              doc="this track's dry send into BusDelay over the bus"),
        # IN is this track's own send into its own reverb. 0 IS LOAD-BEARING
        # (v4, the return conversion): a non-zero default registers every idle
        # host as a bus client, and the 1/sqrt(N) auto-gain then hands it a
        # share whether or not it has audio to contribute -- measured at
        # exactly -6.02 dB for one such phantom client. Since v5 the host's
        # dry rides under the wet at unity, so IN=0 is an exact passthrough
        # rather than a silent track.
        Param(b"IN", 0, active=True, formatter=_PLAIN,
              doc="this track's own send into the reverb; 0 = exact passthrough"),
        # ---- page 2 ---------------------------------------------------------
        # MODE on slot 6 (v7, 4 Sep 2026; was slot 7). An even slot is the
        # proven slot the panel's page-2 knob editor writes, so a main-menu
        # screen can set
        # MODE through the firmware's own routine; slot 7's select path needs
        # UI state nobody has mapped (docs/MAINMENU.md 9c-ii). The DSP reads
        # it from $c's KNOB field now (bits 16-23). A part saved before the
        # swap loads its old SHMR byte as MODE and its old MODE as SHMR --
        # ROOM and a whisper of shimmer at worst; re-select the effect.
        Param(b"MODE", 2, 3, active=True, formatter=_STEP,
              labels=("ROOM", "PLATE", "BIG"),
              doc="voicing; the modes sit 7-9 dB apart and BIG clips first"),
        # SHMR defaults OFF. The slot used to be SPEED (the LFO rate) with a
        # default of 48; when it became the shimmer amount the default was
        # never revisited, so a fresh part booted with the shimmer half up.
        # SHMR=0 is bit-identical to the pre-shimmer engine. On slot 7 it is
        # delivered in $c's companion field (bits 8-15), like stock FILTER's
        # DIST knob on slot 11.
        Param(b"SHMR", 0, 128, active=True, formatter=_PLAIN,
              doc="shimmer -- pitch-shifted regeneration in the tail; 0 = off"),
        Param(b"DIFF", 64, 128, active=True, formatter=_PLAIN,
              doc="diffusion -- low = discrete repeats, high = smooth wash"),
        # SHFT selects the shimmer interval +12/+19/+7/-12 (v6; was WIDTH,
        # which is retired and pinned wide). An old project's stored WIDTH=3
        # loads here as -12, which is benign at SHMR's 0 default.
        Param(b"SHFT", 0, 4, active=True, formatter=_STEP,
              labels=("+12", "+19", "+7", "-12"),
              doc="shimmer interval in semitones -- heard once SHMR is up"),
        Param(b"GATE", 0, 128, active=True, formatter=_PLAIN,
              doc="gated-reverb hold -- higher holds longer; the useful range is low (8-20)"),
        # MOD speed select, 0.5/1/2/4x. Index 1 is 1x; the panel shows it
        # 1-based, so it reads as "2".
        Param(b"RATE", 1, 4, active=True, formatter=_STEP,
              labels=("0.5x", "1x", "2x", "4x"),
              doc="MOD speed multiplier; the panel shows it 1-based"),
    ),
    dsp=DspSection(
        asm="modules/busverb/reverb_server.asm",
        priority=1,                       # after SEND, before the delay
        # Payload A -> the core serving TRACKS 5-8 (the docstring's measured
        # inversion). The build's SPEC table still hardcodes this pairing;
        # here it is stated so the remixer can derive the track range.
        payloads=frozenset({"A"}),
        bus_role=BusRole.SERVER,
        # Eight occurrences: the relocated tank buffers at 0x30000/0x34000.
        # The per-payload rewrite of this literal is load-bearing, not a
        # formality -- but only once the bus lives in the shared window.
        ybase=YBase.XBUS,
        r7_latch_slot=None,               # payload A is in lockstep with the
                                          # rotation flip and latches nothing
        gate_label="bus_notfirst",
        override_markers=("; MODE_OVERRIDE",),
    ),
    # The eight tank lines are hardcoded into Y:0x4000-0xBFFF, the per-CORE
    # FX2 instance buffer region -- so nothing else that owns memory there
    # can be hosted on the same core (the ledger refuses the pair).
    claims=Claims(owns_fx2_buffers=True),
    harness=Harness(layout_char="R", is_server=True),
)
