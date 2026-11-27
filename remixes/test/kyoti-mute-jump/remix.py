"""stock effects with MUTE_MODES and DIRECT_JUMP_KYOTI together."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="kyoti-mute-jump",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with MUTE_MODES and DIRECT_JUMP_KYOTI together.",
    modules=("MUTE_MODES", "DIRECT_JUMP_KYOTI", "BATCH_BUGFIXES",
             *stock.EFFECTS),
    fallback="NONE",
)
