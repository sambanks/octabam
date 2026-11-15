"""stations-fx2 -- SPECTRUM, CHARACTER and MODULATION live on FX1 and FX2.

Each station's SLOTS build setting pinned to FX1+FX2 (tools/remix/stations.py):
an FX2 instance runs the station instead of passing dry. The fixture of
tools/verify/verify_stations_fx2.py. Stock DELAY is listed; every other stock
effect gives up its words. No bus: fallback NONE, no SEND.
"""

from remix.schema import Pin, Evidence, Level, Remix

STATIONS = ("SPECTRUM", "CHARACTER", "MODULATION")

REMIX = Remix(
    name="stations-fx2",
    family="effects", evidence=(Evidence(Level.EMULATOR, ref="verify_stations_fx2",
        note="`verify_stations_fx2` (dsp_host); not on a unit"),),
    doc="SPECTRUM, CHARACTER and MODULATION on FX1 and FX2, beside the stock DELAY.",
    modules=STATIONS + ("DELAY",),
    fallback="NONE",
    fx1=STATIONS,
    settings={(f"octabam.{k.lower()}", "SLOTS"): Pin("FX1+FX2") for k in STATIONS},
)
