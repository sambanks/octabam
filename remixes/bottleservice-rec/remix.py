"""bottleservice-rec -- bottleservice with twenty USB channels out and the recorder fixes.

bottleservice (the rig, USB MIDI, USB AUDIO IN CD with USB CROSSBAR,
Octakit, SCENES P2) with USB AUDIO OUT TRACKS MAIN CUE in place of USB
AUDIO OUT MASTER (tracks 1-16 post-FX pre-fader, MAIN, CUE; the 250 us
layout USB AUDIO IN needs), and the three recorder click fixes from `mods`
(FLEX SEEK BIND, FLEX SEEK BIND CTR, RECORDER SPACING), pinned in the tail
of the 338 B zero run. The first of two staged images;
bottleservice-rec-plen adds RLEN PLEN.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="bottleservice-rec",
    family="rig", proof=Proof.HARDWARE, proof_note="an MKII, OCTABAM1, 29 Sep 2026",
    doc="bottleservice with 20-channel USB AUDIO OUT (tracks, MAIN, CUE) and the recorder click fixes.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE", "USB CROSSBAR", "USB AUDIO IN CD",
             "OCTAKIT", "SCENES KITS",
             "SCENES P2", "SCENES P2 KITS",
             "FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
