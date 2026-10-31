"""stock effects with FREE LOOP (and STORE, which it saves its settings through): its gates."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="free-loop",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with FREE LOOP: a loop pedal per track, the first free loop sets the tempo.",
    modules=("STORE", "RLEN PLEN", "FREE LOOP",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
