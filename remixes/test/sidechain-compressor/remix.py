"""stock effects with SIDECHAIN_COMPRESSOR in COMPRESSOR's row: MON, KEY, KGN, KBAS and KWID on page 2;
SPRING REV gives up its words for the DSP section, as in the standalone build."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="sidechain-compressor",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with SIDECHAIN_COMPRESSOR in COMPRESSOR's row: MON, KEY, KGN, KBAS and KWID on page 2.",
    modules=(
             *stock.fx1_effects("COMPRESSOR", "LO-FI"), "SIDECHAIN_COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "DARK REV"),
    fallback="NONE",
)
