"""BBD beside 12 stock effects: SPRING REV and PLATE REV give up their words for BBD's code."""
from remix.schema import Evidence, Level, Remix
from remix import stock
REMIX = Remix(family="effects", evidence=(Evidence(Level.UNIT, unit="MKII", date="2026-10-17",
    note="JamCones' MKII, BBDOB4 (BUILD 4), 17 Oct 2026"),),
              name="bbd", doc="BBD beside the stock effects (all but SPRING REV and PLATE REV, whose words it takes).",
              modules=("BBD",
                       *stock.effects("PLATE REV", "SPRING REV")),
              fallback="NONE")
