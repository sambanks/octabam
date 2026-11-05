"""stock effects with SLOW LFO: LFO MULT 1/2X, 1/4X and 1/8X. Its gate's remix."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="slow-lfo",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with SLOW LFO: LFO MULT gains 1/2X, 1/4X and 1/8X on audio and MIDI tracks.",
    modules=("SLOW LFO",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
