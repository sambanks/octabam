"""BLACKPYRAMIDS_303 (BLKPYRAMD, a TB-303 voice as a track machine) with the stock effects, SPRING REV given up."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="blackpyramids-303",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="BLACKPYRAMIDS_303 (BLKPYRAMD, a TB-303 voice as a track machine) with the stock effects, SPRING REV given up.",
    modules=("BLACKPYRAMIDS_303",
             *stock.effects("SPRING REV")),
    fallback="NONE",
)
