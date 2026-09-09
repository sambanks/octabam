"""RIG-SCENES -- the bus rig (bamsep26) plus MIDI SCENES and CC to page 2.

Everything the rig is -- BusVerb + BusDelay on the one aux bus, the three
stations, the stock delay, tempo sync, the menu shortcut -- with
bkkbrls-del's MIDI scene locks and octabam's CC->page 2 on top. The LO-FI
AMF fix is NOT here on purpose: the CHARACTER station replaces LO-FI, so
its code is harvested and there is nothing to fix. Unflashed; the rig
itself is on the unit (flash 7), the scenes are not.
"""

from remix.schema import Remix

REMIX = Remix(
    name="rig-scenes",
    doc="The rig + MIDI SCENES + CC to page 2.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "DELAY",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "MENU SHORTCUT",
             "MIDI SCENES", "CC PAGE 2"),
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
