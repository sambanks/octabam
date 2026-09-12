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
        # THE ONE-AUX RE-SLOT (7 Sep 2026): AUX at slot 0 on EVERY track,
        # hosts included -- it is the host's own dry send into the one aux
        # bus (the v8 ->DEL machinery). 0 is load-bearing: a non-zero default
        # would register every idle host as a client and dilute the real
        # senders (the -6.02 dB phantom-client defect).
        Param(b"AUX", 0, active=True, formatter=_PLAIN,
              doc="this track's send into the one aux bus (delay, then reverb, back on T8)"),
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
        # MIX (one-aux rig, 7 Sep 2026; IN until then): the STAGE's crossfade.
        # The reverb is chain stage 2: out = in*(1-MIX) + wet*MIX, where `in`
        # is the delay's output while the delay is live, else the aux. 127
        # is the old wet-only return; lower lets the delay's repeats (or the
        # dry aux) survive the tail. The host prints wet*MIX under its dry.
        Param(b"MIX", 127, active=True, formatter=_PLAIN,
              doc="stage dry/wet: 0 passes the chain input through, 127 = wet only"),
        # ---- page 2 ---------------------------------------------------------
        # MODE on slot 6 (v7, 4 Sep 2026; was slot 7). An even slot is the
        # proven slot the panel's page-2 knob editor writes, so a main-menu
        # screen can set
        # MODE through the firmware's own routine; slot 7's select path needs
        # UI state nobody has mapped (docs/firmware/MAINMENU.md 9c-ii). The DSP reads
        # it from $c's KNOB field now (bits 16-23). A part saved before the
        # swap loads its old SHMR byte as MODE and its old MODE as SHMR --
        # ROOM and a whisper of shimmer at worst; re-select the effect.
        # PLATE by default (12 Sep 2026; was BIG). Measured on the loop at
        # the unit's level the three wet levels sit within 2 dB now (ROOM
        # -16.9, PLATE -19.1, BIG -19.0 dBFS at defaults, AUX 100) -- the
        # "7-9 dB apart" note predated the re-laws -- so the default is the
        # conventional shared plate rather than the biggest space.
        Param(b"MODE", 1, 3, active=True, formatter=_STEP,
              labels=("ROOM", "PLATE", "BIG"),
              doc="voicing: ROOM / PLATE / BIG; BIG clips first"),
        # SHMR defaults OFF. The slot used to be SPEED (the LFO rate) with a
        # default of 48; when it became the shimmer amount the default was
        # never revisited, so a fresh part booted with the shimmer half up.
        # SHMR=0 is bit-identical to the pre-shimmer engine. On slot 7 it is
        # delivered in $c's companion field (bits 8-15), like stock FILTER's
        # DIST knob on slot 11.
        Param(b"SHMR", 0, 128, active=True, formatter=_PLAIN,
              doc="shimmer -- pitch-shifted regeneration in the tail; 0 = off"),
        # DIFF 80 by default (12 Sep 2026; was 64): R59's VintageVerb match
        # point bracketed at ~80-90, never applied.
        Param(b"DIFF", 80, 128, active=True, formatter=_PLAIN,
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
