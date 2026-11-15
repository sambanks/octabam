"""SEND -- the bus client every other track runs: DEL into the delay, REV into
the reverb.

It taps the audio buffer and never writes it, so a SEND at SEND 0 is
indistinguishable from no effect; a fresh, unassigned track (FX2 id 0) is
aliased to it rather than to NONE because, unlike NONE, it performs the
per-block bus housekeeping, so no track can stall the bus.

Clones FILTER's descriptor. Slots 2-11 are blanked but keep FILTER's
defaults and value counts (not drawn; writing them would change bytes for
no reason). No formatter is declared, so the knobs keep FILTER's
plain-numeric zeros (hardware-confirmed). REV took blank slot 1 on 25 Sep
2026: a part saved earlier holds FILTER's slot-1 byte there, so stamp it
(`ot_project.py stamp-slot <project> SEND REV`).
"""

from remix.schema import (Category, Evidence, Level, BusRole, YBase, DspSection, Harness, Kind, MenuEntry,
                          Module, Param)

_BLANK = Param(b"", None, active=False)

MODULE = Module(
    name="send",
    key="SEND",
    kind=Kind.DSP_CLIENT,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks"),),
    doc="Bus client: DEL into the delay, REV into the reverb, from any track. The default effect.",
    menu=MenuEntry(
        fx2_id=0x09,
        donor_desc=0x400d4772,        # FILTER
        abbr=b"SEND",
        fullname=b"Send",
        build_tag=False,
    ),
    params=(
        # Both 0 by default: a nonzero default registers every idle track as
        # a client and dilutes the real senders (the phantom-client rule).
        Param(b"DEL", 0, active=True,
              doc="this track's send into the delay (the reverb hears the repeats through its DLY)"),
        Param(b"REV", 0, active=True,
              doc="this track's send into the reverb"),
        _BLANK, _BLANK, _BLANK, _BLANK,
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/send/send_client.asm",
        priority=0,                       # FIRST: the absent-server alias
                                          # points at SEND's entry points, so
                                          # it must already be placed
        bus_role=BusRole.CLIENT,
        # XBUS, not NEVER: the source carries one `$30000` literal, the
        # payload discriminator of the track-8 send refusal (payload A keeps
        # $30000, B is rewritten to $38000), never used as an address. In a
        # plain (non-XBUS) build it is not rewritten and both payloads refuse
        # position 3; plain builds do not ship.
        ybase=YBase.XBUS,
        r7_latch_slot=0x69,
        gate_label="notfirst",
    ),
    # bus_client: SEND writes the shared accumulators and carries the
    # housekeeping block, so an image containing it HAS a bus. That is what
    # forbids schema.NO_FALLBACK beside it.
    harness=Harness(layout_char="S", is_server=False, bus_client=True),
    dear={'DEL': 100, 'REV': 100},
)
