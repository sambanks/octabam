"""stock effects with USB MIDI and SCREEN: the Elektron screenshot SysEx request answered over USB (or DIN)."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="screen-usb",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock + USB MIDI + SCREEN.",
    modules=("USB", "SCREEN",
             *stock.EFFECTS),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
