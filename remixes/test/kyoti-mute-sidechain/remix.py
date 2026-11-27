"""stock effects with MUTE_MODES and SIDECHAIN_COMPRESSOR together: a muted KEY track keeps feeding the compressor (SC_KEY)."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="kyoti-mute-sidechain",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with MUTE_MODES and SIDECHAIN_COMPRESSOR together: a muted KEY track keeps feeding the compressor (SC_KEY).",
    modules=("MUTE_MODES",
             *stock.fx1_effects("COMPRESSOR", "LO-FI"), "SIDECHAIN_COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "DARK REV"),
    fallback="NONE",
)
