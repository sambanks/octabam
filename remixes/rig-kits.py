"""RIG-KITS -- the bus rig (bamsep26) plus Octakit.

The rig with Em's 256 Kits per Project instead of Parts. Not here, on
purpose: the LO-FI AMF fix (the CHARACTER station replaces LO-FI) and CC
to page 2 (it repoints the MIDI control-parameter dispatch entry Octakit's
own recipe rewrites -- see `kits`). ⚠️ Two things nobody has measured:
Octakit migrates Parts into Kits on load, and the rig's hosts are reached
through the project's part bytes (`ot_project.py stamp-defaults`) --
whether those survive her migration unchanged is the first thing to check
on a unit, with a backed-up project. Unflashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="rig-kits",
    doc="The rig + Octakit.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "DELAY",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "MENU SHORTCUT",
             "OCTAKIT"),
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
