"""drummer -- DRUMMER alone on the stock effects (its gates)."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="drummer",
    family="mods", proof=Proof.HARDWARE,
    proof_note="the author's MKII, images 52-78 (Nov 2026); modules/drummer/verify_port.py and the module's gates",
    doc="DRUMMER alone: T1's sliced loop played as a drummer.",
    modules=("DRUMMER", "STORE", "PAGES",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
