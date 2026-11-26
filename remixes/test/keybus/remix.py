"""KEYBUS alone on the stock effects, for its gate."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="keybus",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="KEYBUS alone (every track's key level in eight shared words) on the stock effects.",
    modules=(
             *stock.effects("PLATE REV", "SPRING REV", "DARK REV"), "KEYBUS"),
    fallback="NONE",
)
