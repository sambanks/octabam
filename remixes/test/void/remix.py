"""VOID replaces COMB FILTER; PLATE REV words host its DSP."""
from remix.schema import Proof, Remix

REMIX = Remix(
    family="effects",
    proof=Proof.CHECK,
    proof_note="verify_void.py SCRAPE path",
    name="void",
    doc="VOID replaces COMB FILTER; PLATE REV words host its DSP.",
    modules=("VOID",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMPRESSOR", "LO-FI",
             "DELAY", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
