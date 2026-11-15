"""stock effects with SIDECHAIN_COMPRESSOR in COMPRESSOR's row: MON, KEY, KGN, KBAS and KWID on page 2;
SPRING REV gives up its words for the DSP section, as in the standalone build."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="sidechain-compressor",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with SIDECHAIN_COMPRESSOR in COMPRESSOR's row: MON, KEY, KGN, KBAS and KWID on page 2.",
    modules=(
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "SIDECHAIN_COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "DARK REV"),
    fallback="NONE",
)
