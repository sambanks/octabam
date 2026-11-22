"""stock effects with TRACK TRIG MODE: Hteah's single-mode track trig editing."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="track-trig-mode",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with TRACK TRIG MODE: Hteah's single-mode track trig editing.",
    modules=("TRACK TRIG MODE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
