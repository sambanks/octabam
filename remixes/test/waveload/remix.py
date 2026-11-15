"""waveload -- CF METER + CF METER IDLE + WAVE LOAD on stock: what K
4-voice wave engines cost in the frame interrupt, and how many fit,
read out over USB audio from track 8. DARK REV is off the chooser: its
words hold the readout insert."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="waveload",
    family="probes", evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-03",
        note="image 92, Sam's MKII, 3 Oct 2026"),),
    doc="CF METER + WAVE LOAD on stock: T8's FX2 BURN = K 4-voice wave engines per frame interrupt, read over USB.",
    modules=("USB", "CF METER", "CF METER IDLE", "WAVE LOAD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
