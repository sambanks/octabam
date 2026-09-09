"""MUTABLES-MODS -- the insert card plus every community firmware mod.

The five MI-flavoured inserts with MIDI SCENES, Octakit, the LO-FI AMF fix
and CC to page 2, bridged by SCENES KITS. No bus, so unimplemented ids
fall back to the firmware's own NONE. ⚠️ Octakit migrates Parts into Kits
on load: back up projects first. Unflashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="mutables-mods",
    doc="Five MI inserts + every community firmware mod, bridged.",
    modules=("WARPFOLD", "RIPPLE", "RUNGS", "STREAMZ", "BODESHIFT",
             "MIDI SCENES", "OCTAKIT", "LOFI AMF FIX", "CC PAGE 2", "SCENES KITS"),
    fallback="NONE",
)
