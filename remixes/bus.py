"""bus -- the plain two-server image: BusVerb, BusDelay, the send bus, tempo sync.

The shape octabam built from the start, and of what is on the unit today
(tag 77, under the old ChonVerb / BongDelay names). It is the registry
default and the reference remix: every build refactor proves itself by
rebuilding this one byte for byte (scripts/refhash.sh). The rig --
`bamsep26`, this plus the three stations, the stock DELAY row and the menu
shortcut -- is what `make` builds by default and what goes on the unit next.

Module order is the FX2 chooser order, so BusVerb draws first. TEMPO SYNC has
no menu entry and takes no row; it is in the list because a remix that wants
BusDelay's TIME knob to read "1/8" instead of milliseconds needs its cave.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bus",
    doc="The plain two-server image: BusVerb + BusDelay + send bus + tempo sync.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC"),
    fallback="SEND",
)
