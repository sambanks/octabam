from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="chords",
    family="mods",
    evidence=(Evidence(Level.EMULATOR, ref="verify_chords",
        note="verify_chords"),),
    doc="CHORDS FACTORY with SCALES, on the 14 stock effects: the chord atelier on SRC, a chord step "
        "played as written, the FUNC keyboard in the scale's colours.",
    modules=("CHORDS FACTORY", "SCALES", "STORE", "PAGES", "FILTER", "EQUALIZER",
             "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
