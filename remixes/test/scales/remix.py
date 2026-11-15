from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="scales",
    family="mods",
    evidence=(Evidence(Level.EMULATOR, ref="verify_scales",
        note="verify_scales"),),
    doc="SCALES alone, on the 14 stock effects: ARP SETUP's KEY, the chooser, the snapped notes and the CHROMATIC keys.",
    modules=("SCALES", "STORE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
