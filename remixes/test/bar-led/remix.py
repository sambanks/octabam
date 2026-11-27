"""stock effects with BAR LED: the tempo LED green on the pattern's 1. Its gate's remix."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="bar-led",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with BAR LED: the tempo LED flashes green on the pattern's 1 while playing.",
    modules=("BAR LED",
             *stock.EFFECTS),
    fallback="NONE",
)
