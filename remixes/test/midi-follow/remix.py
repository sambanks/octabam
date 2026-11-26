"""Stock effects and the experimental per-track MIDI root follower."""
from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="midi-follow", family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="Per-track RFOL source selection on MIDI NOTE SETUP; Part-owned bass following.",
    modules=("EVENTS", "STORE", "MIDI FOLLOW", *stock.EFFECTS),
    fallback="NONE",
)
