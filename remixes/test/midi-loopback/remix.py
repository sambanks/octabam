"""Loopback routing on stock effects, isolated from personal remixes."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="midi-loopback", family="mods", proof=Proof.PORT,
    proof_note='routing previously tested on MKII; STORE Part migration requires new hardware qualification',
    doc="Stock effects plus the Part-scoped per-track MIDI loopback routing.",
    modules=("STORE", "MIDI LOOPBACK", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
