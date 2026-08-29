"""nimbus -- the granular texture card: Nimbus alone, plus the send bus.

Nimbus owns the core-private FX2 buffer region Y:0x4000-0xBFFF, which is
only free because every other module in an insert remix has no Y footprint
at all. That makes it a deliberately narrow selection: ONE Nimbus per core
(two instances would share one buffer), and no server, since ChonVerb's tank
lives in exactly that region.

`mutables` carries the three zero-footprint inserts together; this remix is
the one that needs a buffer, so it stands alone.
"""

from remix.schema import Remix

REMIX = Remix(
    name="nimbus",
    doc="Nimbus granular texture + send bus. One instance per core.",
    modules=("NIMBUS", "SEND"),
    fallback="SEND",
)
