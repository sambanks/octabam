"""DRUMMER and ANALOG BD in one image: MACHINES gives the track's machine list seven rows, DRUMMER on row 5 and ANALOG BD on row 6, and the list scrolls."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="machines",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="modules/machines/verify.py",
        note="verify.py: MACHINES's list, SRC SETUP, commits and validator under Unicorn, and its sites in this image"),),
    doc="DRUMMER and ANALOG BD in one image: MACHINES gives the track's machine list seven rows, DRUMMER on row 5 and ANALOG BD on row 6, and the list scrolls.",
    modules=("DRUMMER", "ANALOG BD", "MACHINES", "STORE", "PAGES", "EVENTS",
             *stock.effects("SPRING REV")),
    fallback="NONE",
)
