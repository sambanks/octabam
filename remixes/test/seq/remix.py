"""STORE + PLOCKS P2 + SEQ (seq.work client) with the stock effects."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="seq",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="STORE + PLOCKS P2 + SEQ (seq.work client) with the stock effects.",
    modules=("STORE", "SCENES P2", "EVENTS", "PLOCKS P2", "SEQ",
             *stock.EFFECTS),
    fallback="NONE",
)
