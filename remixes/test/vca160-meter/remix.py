"""stock-meter-b's image with VCA160: LOAD METER and the core modules, VCA160 on its own id, and the stock
effects but SPATIALIZER (the meter's DSP half takes its words, as in stock-meter-b) and PLATE REV (VCA160's
code runs in its words, as in test/vca160). The image for reading VCA160's slot cost on a unit with
tools/hw/ot_matrix.py, against the same BASE as stock-meter-b."""
from remix.schema import Evidence, Level, Pin, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD", "EVENTS",
        "LOAD METER")
STOCK = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
         "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV")
DROPPED = ("SPATIALIZER", "PLATE REV")

REMIX = Remix(
    name="vca160-meter",
    family="effects", evidence=(Evidence(Level.BUILD, note="not flashed; the image for reading VCA160's slot cost on a unit"),),
    doc="stock-meter-b with VCA160 (its own id) in PLATE REV's words: VCA160's slot cost on a unit.",
    modules=CORE + ("LOFI AMF FIX", "VCA160") + tuple(e for e in STOCK if e not in DROPPED),
    fx1=("VCA160",) + tuple(e for e in STOCK[:10] if e not in DROPPED),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
