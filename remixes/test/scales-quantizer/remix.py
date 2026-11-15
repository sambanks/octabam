from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="scales-quantizer",
    family="mods",
    evidence=(Evidence(Level.EMULATOR, ref="verify_scales",
        note="verify_scales"),),
    doc="SCALES beside SCALE QUANTIZER: the audio tracks' CHROMATIC keys light SCALE on ROOT.",
    modules=("SCALES", "STORE", "SCALE QUANTIZER", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
