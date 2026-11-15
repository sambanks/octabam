"""usb-out-master -- stock effects plus USB MIDI and USB AUDIO OUT MASTER, nothing else.

usb-out-tracks-main-cue with track 8's two channels only (the master track, post-FX
pre-fader). For testing USB AUDIO OUT MASTER on a unit that runs stock
projects. Local test remix (27 Sep 2026).
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="usb-out-master",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock + USB (MASTER) (2 ch: track 8).",
    modules=("USB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "OFF", ("octabam.usb", "MAIN"): 0,
              ("octabam.usb", "CUE"): 0, ("octabam.usb", "MASTER"): 1,
              ("octabam.usb", "IN"): "OFF"},
)
