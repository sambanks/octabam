"""bottleservice-pf-flag -- bottleservice-pf plus PIRATE FLAG (the boot
animation as a Jolly Roger): the home rig, to try through OS SWITCH before
flashing.

Kept in step with bottleservice-pf (RETURNS on the chooser, MODE DEFAULTS,
HOST LOCK, 1 Oct 2026). Not flashed.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="bottleservice-pf-flag",
    family="rig", proof=Proof.CHECK, proof_note="make check, 29 Sep 2026; not flashed",
    doc="bottleservice-pf + PIRATE FLAG; bottleservice-ret + POST FADER: the bus sends follow each track's fader, mute and solo.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE", "USB CROSSBAR", "USB AUDIO IN CD",
             "OCTAKIT", "SCENES KITS",
             "SCENES P2", "SCENES P2 KITS",
             "FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING", "RLEN PLEN",
             "RETURNS", "POST FADER", "MODE DEFAULTS", "HOST LOCK", "PIRATE FLAG"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
