"""RIG-MODS -- the bus rig (bamsep26) plus every community firmware mod.

The rig with MIDI SCENES, Octakit and CC to page 2, bridged by SCENES
KITS. No LO-FI AMF fix: the CHARACTER station replaces LO-FI. ⚠️ Unmeasured
on top of `mods`' caveats: the rig's hosts are reached through the
project's part bytes (`ot_project.py stamp-defaults`); whether those
survive Octakit's Parts->Kits migration is the first thing to check on a
unit, with a backed-up project. Unflashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="rig-mods",
    doc="The rig + MIDI SCENES + Octakit + CC to page 2, bridged.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "DELAY",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "MENU SHORTCUT",
             "MIDI SCENES", "OCTAKIT", "CC PAGE 2", "SCENES KITS"),
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
