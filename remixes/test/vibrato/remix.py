"""VIBRATO on FX1 beside the stock effects: PLATE REV gives up its words."""
from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    family="effects",
    evidence=(Evidence(Level.EMULATOR),),
    name="vibrato",
    doc="VIBRATO on FX1 beside the stock effects (all but PLATE REV).",
    modules=("VIBRATO",
             *stock.effects("PLATE REV")),
    fx1=("VIBRATO",
         *stock.FX1),
    fallback="NONE",
)
