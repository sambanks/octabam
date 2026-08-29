"""ChonVerb -- an eight-line FDN reverb with shimmer, gating and mode select.

Hosted on payload A (core 0), which serves TRACKS 5-8 -- measured 10 Aug 2026
and inverted from what every doc assumed before then. Test it on track 5.
Any track can send into it over the bus.

Clones DARK REV's descriptor. Slots 0, 3 and 4 are written with the names the
donor already carries (TIME/HP/LP), so the write is a no-op in bytes but the
label is stated here rather than inherited silently -- the harness reads these
names, and a name that exists only in a donor is a name no tool can see.
"""

from remix.schema import (BusRole, YBase, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="chonverb",
    key="REVERB SERVER",
    kind=Kind.DSP_EFFECT,
    doc="Eight-line FDN reverb: ROOM/PLATE/BIG, shimmer, gate, mid/side width.",
    menu=MenuEntry(
        fx2_id=0x07,
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"CVRB",
        fullname=b"ChonVerb",
        build_tag=True,
    ),
    params=(
        # ---- page 1 -------------------------------------------------------
        Param(b"TIME", 64, active=True, formatter=_PLAIN),
        Param(b"MOD", 30, active=True, formatter=_PLAIN),
        Param(b"SIZE", 100, active=True, formatter=_PLAIN),
        Param(b"HP", 0, active=True, formatter=_PLAIN),
        Param(b"LP", 127, active=True, formatter=_PLAIN),
        # IN is this track's own send into its own reverb. 0 IS LOAD-BEARING
        # (v4, the return conversion): a non-zero default registers every idle
        # host as a bus client, and the 1/sqrt(N) auto-gain then hands it a
        # share whether or not it has audio to contribute -- measured at
        # exactly -6.02 dB for one such phantom client. Since v5 the host's
        # dry rides under the wet at unity, so IN=0 is an exact passthrough
        # rather than a silent track.
        Param(b"IN", 0, active=True, formatter=_PLAIN),
        # ---- page 2: three knobs and three selects, in that alternation ----
        # SHMR defaults OFF. The slot used to be SPEED (the LFO rate) with a
        # default of 48; when it became the shimmer amount the default was
        # never revisited, so a fresh part booted with the shimmer half up.
        # SHMR=0 is bit-identical to the pre-shimmer engine.
        Param(b"SHMR", 0, 128, active=True, formatter=_PLAIN),
        Param(b"MODE", 2, 3, active=True, formatter=_STEP),      # ROOM/PLATE/BIG
        Param(b"DIFF", 64, 128, active=True, formatter=_PLAIN),
        # SHFT selects the shimmer interval +12/+19/+7/-12 (v6; was WIDTH,
        # which is retired and pinned wide). An old project's stored WIDTH=3
        # loads here as -12, which is benign at SHMR's 0 default.
        Param(b"SHFT", 0, 4, active=True, formatter=_STEP),
        Param(b"GATE", 0, 128, active=True, formatter=_PLAIN),
        # MOD speed select, 0.5/1/2/4x. Index 1 is 1x; the panel shows it
        # 1-based, so it reads as "2".
        Param(b"RATE", 1, 4, active=True, formatter=_STEP),
    ),
    dsp=DspSection(
        asm="modules/chonverb/reverb_server.asm",
        priority=1,                       # after SEND, before the delay
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
    harness=Harness(layout_char="R", is_server=True),
)
