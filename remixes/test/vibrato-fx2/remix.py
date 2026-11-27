"""VIBRATO live on FX1 and FX2 (SLOTS = FX1+FX2) beside the stock effects:
PLATE REV gives up its words. The fixture of verify_vibrato's FX2 checks."""
from remix.schema import Pin, Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    family="effects",
    evidence=(Evidence(Level.EMULATOR),),
    name="vibrato-fx2",
    doc="VIBRATO live on FX1 and FX2 beside the stock effects (all but PLATE REV).",
    modules=("VIBRATO",
             *stock.effects("PLATE REV")),
    fx1=("VIBRATO",
         *stock.FX1),
    fallback="NONE",
    settings={("octabam.vibrato", "SLOTS"): Pin("FX1+FX2")},
)
