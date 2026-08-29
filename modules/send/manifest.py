"""SEND -- the bus client every other track uses to feed the two servers.

Two knobs, one per bus. It never writes the audio buffer, only taps it, so a
SEND with both levels at zero is indistinguishable from "no effect" -- which
is why a fresh, unassigned track (FX2 id 0) is aliased to this rather than to
NONE. Unlike NONE it performs the per-block bus housekeeping, so making every
unassigned track a SEND removes the "first track set to NONE stalls the bus"
hazard by construction instead of patching around it.

Clones FILTER's descriptor. Slots 2-11 are blanked (they would otherwise draw
FILTER's names) but deliberately keep FILTER's DEFAULTS and value counts: the
slots are not drawn, and writing them would change bytes for no reason. This
module declares no formatter for any slot, so the formatter pass skips it
entirely and its two knobs keep FILTER's plain-numeric zeros -- which is what
they want and what hardware confirmed.
"""

from remix.schema import (BusRole, YBase, DspSection, Harness, Kind, MenuEntry,
                          Module, Param)

_BLANK = Param(b"", None, active=False)

MODULE = Module(
    name="send",
    key="SEND",
    kind=Kind.DSP_CLIENT,
    doc="Bus client: feeds -DEL and -VRB from any track. The default effect.",
    menu=MenuEntry(
        fx2_id=0x09,
        donor_desc=0x400d4772,        # FILTER
        abbr=b"SEND",
        fullname=b"Send",
        build_tag=False,
    ),
    params=(
        Param(b"-DEL", 0, active=True),
        Param(b"-VRB", 0, active=True),
        _BLANK, _BLANK, _BLANK, _BLANK,
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/send/send_client.asm",
        priority=0,                       # FIRST: the absent-server alias
                                          # points at SEND's entry points, so
                                          # it must already be placed
        bus_role=BusRole.CLIENT,
        ybase=YBase.NEVER,                # carries no shared-window literal
        r7_latch_slot=0x69,
        gate_label="notfirst",
    ),
    harness=Harness(layout_char="S", is_server=False),
)
