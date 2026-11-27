"""waveload-port -- waveload without CF METER IDLE, for the port gate: the
port advances its clock only at main's stock `bras .`."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="waveload-port",
    family="probes", evidence=(Evidence(Level.EMULATOR,
        note="the load path under the port"),),
    doc="waveload without the idle loop: the port gate for the wave engines in the frame interrupt.",
    modules=("USB", "CF METER", "WAVE LOAD",
             *stock.effects("DARK REV")),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
