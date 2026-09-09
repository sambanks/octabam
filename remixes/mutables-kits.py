"""MUTABLES-KITS -- the insert card plus the Octakit family.

The five MI-flavoured inserts (WarpFold, Ripple, Rungs, Streamz, BodeShift)
with 256 Kits per Project and the LO-FI AMF fix. No CC to page 2: it
repoints the MIDI control-parameter dispatch entry Octakit's own recipe
rewrites (see `kits`). No bus, so unimplemented ids fall back to the
firmware's own NONE. ⚠️ Octakit migrates Parts into Kits on load: back up
projects first. Unflashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="mutables-kits",
    doc="Five MI inserts + Octakit + the LO-FI AMF fix.",
    modules=("WARPFOLD", "RIPPLE", "RUNGS", "STREAMZ", "BODESHIFT",
             "OCTAKIT", "LOFI AMF FIX"),
    fallback="NONE",
)
