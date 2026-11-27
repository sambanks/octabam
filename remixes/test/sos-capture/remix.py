"""sos-capture -- the recorder loop fix with a digital test signal in and the track outputs out over USB.

RECORDER LOOP FIX on usb-io-tracks-ab: the host plays a signal into inputs
A/B (USB IN AB) and records the sixteen track channels (USB TRACKS), so a sound-on-sound loop is captured sample-exact on the unit and
compared with the same input under the port
(`tools/hw/sos_capture.py`).
"""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="sos-capture",
    family="mods", evidence=(Evidence(Level.EMULATOR,
        note="`make check` under the port; not on hardware in this form"),),
    doc="recorder fixes + USB (TRACKS out, AB in) (stock effects minus SPATIALIZER).",
    modules=("RECORDER LOOP FIX",
             "USB",
             *stock.effects("SPATIALIZER")),
    fx1=stock.fx1_effects("SPATIALIZER"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "AB"},
)
