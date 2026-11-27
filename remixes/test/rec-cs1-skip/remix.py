"""stock effects with REC CS1 SKIP: the recorder's control-record update without its redundant CS1 writes."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="rec-cs1-skip",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with REC CS1 SKIP: the recorder's control-record update without its redundant CS1 writes.",
    modules=("REC CS1 SKIP",
             *stock.EFFECTS),
    fallback="NONE",
)
