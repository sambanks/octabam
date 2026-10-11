"""core -- bottleservice plus BRAIN: the settings store on the rig.

bottleservice's selection (remixes/bottleservice) with BRAIN: card-wide knob
defaults from BRAIN/card.work, SAVE AS DEFAULT and CLEAR DEFAULT in the
BRAIN MAIN MENU category. BRAIN's gate (tools/verify/verify_brain.py) runs
on it, restoring the FX2 chooser's YES entry in RAM where it selects.
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="brain",
    family="mods", proof=Proof.PORT, proof_note="`verify_brain` under the port, 6 Oct 2026; not on hardware",
    doc="bottleservice + BRAIN: card-wide knob defaults, SAVE AS DEFAULT in the BRAIN menu.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT",
             "STORE", "KITS",
             "SCENES P2", "PLOCKS P2",
             "DELAY",
             "FX2 LOCK",
             "BRAIN"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("MASTER")},
)
