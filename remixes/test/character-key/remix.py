"""stock effects with KEYBUS and CHARACTER on FX1: CHARACTER's KEY reads T1..T8 from KEYBUS's words."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="character-key",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with KEYBUS and CHARACTER: CHARACTER's KEY reads T1..T8 from KEYBUS's shared key words.",
    modules=(
             *stock.effects("PLATE REV", "SPRING REV", "DARK REV"), "KEYBUS", "CHARACTER"),
    fallback="NONE",
)
