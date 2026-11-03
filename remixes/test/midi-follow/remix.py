"""Stock effects and the experimental per-track MIDI root follower."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="midi-follow", family="mods", proof=Proof.PORT,
    proof_note='',
    doc="Per-track RFOL source selection on MIDI NOTE SETUP; Part-owned bass following.",
    modules=("EVENTS", "STORE", "MIDI FOLLOW", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
