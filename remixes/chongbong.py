"""chongbong -- the shipping image: ChonVerb, BongDelay, the send bus, tempo sync.

This is what octabam has always built, now stated as a selection rather than
assumed by the build script. It is also the reference remix: every refactor
proves itself by rebuilding this one byte-for-byte.

Module order is the FX2 chooser order, so ChonVerb draws first. TEMPO SYNC has
no menu entry and takes no row; it is in the list because a remix that wants
BongDelay's TIME knob to read "1/8" instead of milliseconds needs its cave.
"""

from remix.schema import Remix

REMIX = Remix(
    name="chongbong",
    doc="The shipping image: ChonVerb + BongDelay + send bus + tempo sync.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC"),
    fallback="SEND",
)
