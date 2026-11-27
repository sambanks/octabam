"""stock effects with QUANTIZE_LIVE_REC_TOGGLE: QUANTIZE LIVE REC from [REC] + [PLAY]."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="quantize-live-rec-toggle",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with QUANTIZE_LIVE_REC_TOGGLE: QUANTIZE LIVE REC from [REC] + [PLAY].",
    modules=("QUANTIZE_LIVE_REC_TOGGLE",
             *stock.EFFECTS),
    fallback="NONE",
)
