"""stock effects with DIRECT_JUMP_KYOTI: [PTN] + [YES] toggles an immediate, clock-locked pattern change."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="direct-jump-kyoti",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with DIRECT_JUMP_KYOTI: [PTN] + [YES] toggles an immediate, clock-locked pattern change.",
    modules=("DIRECT_JUMP_KYOTI", "BATCH_BUGFIXES",
             *stock.EFFECTS),
    fallback="NONE",
)
