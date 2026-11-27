"""stock effects with ERASE_EMPTY_TRIGLESS_LOCKS: an emptied trigless lock disappears."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="erase-empty-trigless-locks",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with ERASE_EMPTY_TRIGLESS_LOCKS: an emptied trigless lock disappears.",
    modules=("ERASE_EMPTY_TRIGLESS_LOCKS",
             *stock.EFFECTS),
    fallback="NONE",
)
