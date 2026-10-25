"""MIDI Follow with both production EVENTS clients."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="midi-follow-events", family="probes", proof=Proof.PORT,
    doc="MIDI Follow with EUCLID and PLOCKS P2 sharing EVENTS notifications.",
    modules=("EVENTS", "MIDI FOLLOW", "MIDI PART STATE", "EUCLID",
             "BRAIN", "STORE", "SCENES P2", "PLOCKS P2",
             "MIDI SCALES", "MIDI LOOPBACK", "FILTER", "COMPRESSOR", "PLATE REV"),
    fx1=("EUCLID", "FILTER", "COMPRESSOR"), fallback="NONE",
)
