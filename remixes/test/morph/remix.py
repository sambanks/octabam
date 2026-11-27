"""MORPH alone: track + UP / DOWN runs a track's scene morph by itself, with STORE and the stock effects."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="morph",
    family="mods", evidence=(Evidence(Level.UNIT, unit="MKI", date="2026-10-23",
        note="image MRPPR1 (BUILD 98, this remix), 23 Oct 2026: the window, the start on the release, x to 16, "
             "saving through a power cycle, RELOAD and another project; tools/morph/test_morph.py and "
             "tools/morph/port_morph.py"),),
    doc="MORPH (track + UP / DOWN: the scene morph by itself, saved with the project) with STORE and the stock effects.",
    modules=("MORPH", "STORE", *stock.EFFECTS),
    fallback="NONE",
)
