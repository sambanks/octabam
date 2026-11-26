"""stock effects with QUANTIZE_LIVE_REC_TOGGLE, ERASE_EMPTY_TRIGLESS_LOCKS and BATCH_BUGFIXES together."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="kyoti-fixes",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with QUANTIZE_LIVE_REC_TOGGLE, ERASE_EMPTY_TRIGLESS_LOCKS and BATCH_BUGFIXES together.",
    modules=("QUANTIZE_LIVE_REC_TOGGLE", "ERASE_EMPTY_TRIGLESS_LOCKS", "BATCH_BUGFIXES",
             *stock.EFFECTS),
    fallback="NONE",
)
