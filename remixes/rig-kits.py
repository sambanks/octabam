"""rig-kits -- bamsep26 + Octakit (SCENES KITS bridges CC MAP and Octakit).

No LO-FI AMF fix (Character replaces LO-FI). Unmeasured: whether the part
bytes that place the rig's hosts (ot_project.py stamp-defaults) survive
Octakit's Parts->Kits migration. Back up projects first. Unflashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="rig-kits",
    doc="The rig + Octakit.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "DELAY",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP",
             "OCTAKIT", "SCENES KITS",
             "SCENES P2", "SCENES P2 KITS"),
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
