from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="chords-alone",
    family="mods",
    evidence=(Evidence(Level.EMULATOR, ref="verify_chords",
        note="verify_chords"),),
    doc="CHORDS FACTORY without SCALES, on the 14 stock effects: the atelier alone "
        "on SRC, chords played as written (no scale).",
    modules=("CHORDS FACTORY", "STORE", "PAGES", "FILTER", "EQUALIZER",
             "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
