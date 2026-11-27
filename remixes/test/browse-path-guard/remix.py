"""stock effects with BROWSE PATH GUARD: the sample browser stops at its 260-byte path buffers."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="browse-path-guard",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with BROWSE PATH GUARD: the sample browser stops at its 260-byte path buffers.",
    modules=("BROWSE PATH GUARD",
             *stock.EFFECTS),
    fallback="NONE",
)
