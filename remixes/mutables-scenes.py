"""MUTABLES-SCENES -- the insert card plus the MIDI SCENES family.

The five MI-flavoured inserts (WarpFold, Ripple, Rungs, Streamz, BodeShift)
with MIDI scene locks, the LO-FI AMF fix and CC to page 2. No bus, so
unimplemented ids fall back to the firmware's own NONE. The inserts are
verified by local render and never flashed; so are the mods. Unflashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="mutables-scenes",
    doc="Five MI inserts + MIDI SCENES + the LO-FI AMF fix + CC to page 2.",
    modules=("WARPFOLD", "RIPPLE", "RUNGS", "STREAMZ", "BODESHIFT",
             "MIDI SCENES", "LOFI AMF FIX", "CC PAGE 2"),
    fallback="NONE",
)
