"""usb-out-main-cue -- stock effects plus USB MIDI and USB AUDIO OUT MAIN CUE, nothing else.

usb-out-tracks-main-cue with MAIN L/R + CUE L/R only, at the 250 us cadence (not
USB AUDIO OUT MASTER's 1 ms). For testing USB AUDIO OUT MAIN CUE on a unit that runs
stock projects. Local test remix (27 Sep 2026).
"""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="usb-out-main-cue",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock + USB (MAIN CUE) (4 ch: MAIN + CUE).",
    modules=("USB",
             *stock.EFFECTS),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
