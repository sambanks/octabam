"""LOFI2 beside 12 stock effects: PLATE REV and SPRING REV give up their words for LOFI2's code
(856 words and a 516-word table; PLATE REV alone is 594)."""
from remix.schema import Evidence, Level, Remix
from remix import stock
REMIX = Remix(family="effects", evidence=(Evidence(Level.EMULATOR),),
              name="lofi2", doc="LOFI2 beside the stock effects (all but PLATE REV and SPRING REV, whose words it takes).",
              modules=("LOFI2",
                       *stock.effects("PLATE REV", "SPRING REV")),
              fallback="NONE")
