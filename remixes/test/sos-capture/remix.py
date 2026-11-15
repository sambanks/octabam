"""sos-capture -- the recorder loop fix with a digital test signal in and the track outputs out over USB.

RECORDER LOOP FIX on usb-io-tracks-ab: the host plays a signal into inputs
A/B (USB IN AB) and records the sixteen track channels (USB TRACKS), so a sound-on-sound loop is captured sample-exact on the unit and
compared with the same input under the port
(`tools/hw/sos_capture.py`).
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="sos-capture",
    family="mods", evidence=(Evidence(Level.EMULATOR,
        note="`make check` under the port; not on hardware in this form"),),
    doc="recorder fixes + USB (TRACKS out, AB in) (stock effects minus SPATIALIZER).",
    modules=("RECORDER LOOP FIX",
             "USB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "AB"},
)
