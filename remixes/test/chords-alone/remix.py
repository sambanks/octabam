from remix.schema import Proof, Remix

REMIX = Remix(
    name="chords-alone",
    family="mods",
    proof=Proof.CHECK,
    proof_note="verify_chords",
    doc="CHORDS FACTORY without SCALES, on the 14 stock effects: the atelier alone "
        "on SRC, chords played as written (no scale).",
    modules=("CHORDS FACTORY", "TRIG MODES", "STORE", "PAGES", "FILTER", "EQUALIZER",
             "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
