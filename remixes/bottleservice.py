"""bottleservice -- the rig plus USB MIDI, USB AUDIO and Octakit.

bamsep26's selection (hosts, TEMPO BUS) with USB MIDI and USB AUDIO on
the DRAM platform (as `usb-audio`) and Em's Octakit (as `rig-kits`, with
SCENES KITS bridging CC MAP and Octakit on the CC dispatch). Unflashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bottleservice",
    doc="The rig + USB MIDI + USB AUDIO + Octakit.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO",
             "OCTAKIT", "SCENES KITS",
             "SCENES P2", "SCENES P2 KITS"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
