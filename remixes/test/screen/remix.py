"""stock effects with SCREEN: the Elektron screenshot SysEx request answered on MIDI OUT."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="screen",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with SCREEN.",
    modules=("SCREEN",
             *stock.EFFECTS),
    fallback="NONE",
)
