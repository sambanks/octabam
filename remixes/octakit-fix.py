"""OCTAKIT + LOFI AMF FIX -- the first two-mod image with Em's runtime.

The pick-and-choose proof for the appended-runtime class: OCTAKIT (598
sparse writes + a 73 KB append, DRAM runtime) and LOFI AMF FIX (two DSP
words) share nothing, so the ledger passes them together. midi-scenes is
deliberately NOT here: it and Octakit both rewrite the apply_part entry
0x40009094, and until detour chaining exists the ledger refuses that
combination -- see modules/octakit/README.md.
"""

from remix.schema import Remix

REMIX = Remix(
    name="octakit-fix",
    doc="Em's Octakit + the LO-FI AMF fix: two ported mods, one image.",
    modules=("OCTAKIT", "LOFI AMF FIX"),
    fallback="NONE",
)
