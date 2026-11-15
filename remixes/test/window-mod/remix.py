"""MODULATION in the shared window, beside the stock effects, with LOAD METER.

A measurement build: MODULATION's code is one copy at P:0x36300 (payload A's half of the shared window, the
words octabam-bus leaves free) instead of two in the harvested region, so its slot cost on the unit is
the cost of running from the window, to set against the same code in internal P (window-ctl,
modules/modulation/README.md). PLATE REV, SPRING REV and DARK REV give up their words to LOAD METER's DSP
half and the CORE modules; no module here has an FX2 buffer, so the window words are not another effect's."""
from remix.schema import Pin, Evidence, Level, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD", "EVENTS",
        "LOAD METER")

REMIX = Remix(
    name="window-mod", family="effects", evidence=(Evidence(Level.EMULATOR),),
    doc="CORE with LOAD METER and MODULATION in the shared window beside the stock effects (all but CHORUS, whose id it takes, and the three reverbs).",
    modules=CORE + ("MODULATION", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
                    "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY"),
    fx1=("MODULATION", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
         "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    window=(("MODULATION", 0x36300),),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
