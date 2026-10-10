"""character-txtr -- bottleservice with CHARACTER TXTR in CHARACTER's place.

The image for testing Character's texture stage on a unit: the same rig,
hosts, USB and KITS as bottleservice, the station swapped for the one
with TXTR (Airwindows Pockey2) on page-2 slot 9. Four of these beside the
reverb price a core at 2,751 cycles per sample against 3,120 usable (the
pricer reads the reverb ~270 low, so ~3,020), which no hardware has run;
bottleservice keeps the plain station until it has.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="character-txtr",
    family="rig", proof=Proof.CHECK, proof_note="",
    doc="bottleservice with CHARACTER TXTR (Character + Airwindows Pockey2 texture) on FX1 in place of CHARACTER: the image for measuring the texture stage's cost on a unit.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER TXTR", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT MASTER",
             "STORE", "KITS",
             "SCENES P2", "PLOCKS P2",
             "DELAY",
             "FX2 LOCK"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER TXTR", "MODULATION"),
)
