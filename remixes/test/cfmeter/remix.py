"""cfmeter -- octatrick without TUNER and its USB input, plus CF METER and CF METER IDLE: the ColdFire's
spare time with SYNTH MACHINE voices running, read out over USB audio from
track 8.
DARK REV is off the chooser: its words hold the readout insert."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="cfmeter",
    family="probes", evidence=(Evidence(Level.EMULATOR,
        note="the readout chain under the port"),),
    doc="octatrick (less TUNER and the USB input) + CF METER on T8's FX2: ColdFire idle time and frame-interrupt duration, over USB.",
    modules=("DIRECT JUMP", "SCALE QUANTIZER", "SYNTH MACHINE",
             "USB", "CF METER", "CF METER IDLE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV"),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF"},
)
