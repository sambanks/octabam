"""core -- bottleservice plus CORE: the card-layer knob defaults on the rig.

The rig's selection (remixes/bottleservice) with CORE, for CORE's gate
(tools/verify/verify_core.py): a default record on the card for an effect
the chooser offers lands when that effect is selected.
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="core",
    family="mods", proof=Proof.PORT, proof_note="`verify_core` under the port, 6 Oct 2026; not on hardware",
    doc="bottleservice + CORE: card-wide knob defaults from OCTABAM/card.work.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT",
             "KITS",
             "SCENES P2", "PLOCKS P2",
             "DELAY",
             "CORE"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("MASTER")},
)
