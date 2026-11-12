"""The late frame-interrupt guard on the stock effects."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="frame-guard", family="mods", proof=Proof.PORT,
    proof_note="the guard's arithmetic under Unicorn; the module ran on a unit inside octabam, this remix has not",
    doc="Stock effects with a late frame interrupt held out of the DSP's stall window.",
    modules=("FRAME GUARD", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
