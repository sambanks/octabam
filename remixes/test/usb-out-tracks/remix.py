"""usb-out-tracks -- stock effects plus USB MIDI and USB AUDIO OUT TRACKS, nothing else.

usb-out-tracks-main-cue with the sixteen track channels only (no MAIN/CUE): the layout
image 69 ran. For testing USB AUDIO OUT TRACKS on a unit that runs stock
projects. Local test remix (27 Sep 2026).
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="usb-out-tracks",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock + USB (TRACKS) (16 ch: the tracks).",
    modules=("USB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
