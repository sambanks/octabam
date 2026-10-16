"""stock effects with VARISPEED: STATIC/FLEX TSTR VARI, QUAN on PTCH; nothing emulated, the DSP
stock (SPRING REV kept)."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="varispeed",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with VARISPEED: TSTR VARI, QUAN on PTCH.",
    modules=("VARISPEED",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
