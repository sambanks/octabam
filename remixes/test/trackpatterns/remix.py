"""TRACK PATTERNS with the stock effects: a pattern per track, clip style."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="trackpatterns",
    family="mods", evidence=(Evidence(Level.UNIT, unit="MKII", image="OCTABAM3", date="2026-10-21",
        note="functional tests and trig LEDs passed (contributor's report)"),),
    doc="TRACK PATTERNS with the stock effects: hold TRACK + PATTERN + TRIG for a pattern per track.",
    modules=("TRACK PATTERNS",
             *stock.EFFECTS),
    fallback="NONE",
)
