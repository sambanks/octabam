"""stock effects with VARISPEED: STATIC/FLEX TSTR VARI, QUAN on PTCH; nothing emulated, the DSP
stock (SPRING REV kept). STORE because VARISPEED is its client at the PART menu's CLEAR."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="varispeed",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with VARISPEED: TSTR VARI, QUAN on PTCH.",
    modules=("VARISPEED", "STORE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
