"""The late frame-interrupt guard on the stock effects."""
from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="frame-guard", family="mods", evidence=(Evidence(Level.EMULATOR,
        note="the guard's arithmetic under Unicorn; the module ran on a unit inside octabam, this remix has not"),),
    doc="Stock effects with a late frame interrupt held out of the DSP's stall window.",
    modules=("FRAME GUARD", *stock.EFFECTS),
    fallback="NONE",
)
