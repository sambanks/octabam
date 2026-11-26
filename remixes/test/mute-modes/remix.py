"""stock effects with MUTE_MODES: PERSONALIZE > MUTE MODE (OT, OTFX, OTFX-T, DT-T)."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="mute-modes",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with MUTE_MODES: PERSONALIZE > MUTE MODE (OT, OTFX, OTFX-T, DT-T).",
    modules=("MUTE_MODES",
             *stock.EFFECTS),
    fallback="NONE",
)
