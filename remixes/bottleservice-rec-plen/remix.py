"""bottleservice-rec-plen -- bottleservice-rec plus RLEN PLEN.

bottleservice (the rig, USB MIDI, USB AUDIO IN CD with USB CROSSBAR,
Octakit, SCENES P2) with USB AUDIO OUT TRACKS MAIN CUE in place of USB
AUDIO OUT MASTER (tracks 1-16 post-FX pre-fader, MAIN, CUE; the 250 us
layout USB AUDIO IN needs), the three recorder click fixes (FLEX SEEK
BIND, FLEX SEEK BIND CTR, RECORDER SPACING, pinned in the 338 B run) and
RLEN PLEN (a DRAM unit). The second of two staged images: flash
bottleservice-rec first, so a fault here is RLEN PLEN's. RECORDER HOLD is
out: 328 B of ROM the rig does not have, and unproven on a unit.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="bottleservice-rec-plen",
    family="rig", proof=Proof.HARDWARE, proof_note="an MKII, OCTABAM2, 29 Sep 2026",
    doc="bottleservice-rec + RLEN PLEN (RLEN value PLEN: one pattern loop per take).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE", "USB CROSSBAR", "USB AUDIO IN CD",
             "OCTAKIT", "SCENES KITS",
             "SCENES P2", "SCENES P2 KITS",
             "FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING", "RLEN PLEN"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
