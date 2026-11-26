"""All twelve keys and seven modes in the native ARP SETUP KEY control."""
from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="midi-scales", family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="All twelve keys and seven modes in the native ARP SETUP KEY control.",
    modules=("MIDI SCALES", *stock.EFFECTS),
    fallback="NONE",
)
