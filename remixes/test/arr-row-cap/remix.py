"""stock effects with ARR ROW CAP: the arranger's append stops at 256 rows."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="arr-row-cap",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with ARR ROW CAP: the arranger's append stops at 256 rows.",
    modules=("ARR ROW CAP",
             *stock.EFFECTS),
    fallback="NONE",
)
