"""ext-probe -- the core modules and all stock effects but EQUALIZER, with EXTPROBE on FX1: how far into its slot does a stock reverb write?

A measurement build (modules/extprobe/README.md). EXTPROBE takes EQUALIZER's id and sits in the window gap below LOAD METER; no
demand loader is in this image, so nothing but the reverb under test writes the slot at T8.
"""
from remix.schema import Pin, Proof, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD", "EVENTS",
        "LOAD METER")
STOCK13 = ("FILTER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
           "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV")

REMIX = Remix(
    name="ext-probe",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="octabam's core and stock effects (EQUALIZER's id is the probe's) with EXTPROBE on FX1: the highest window word a reverb writes.",
    modules=CORE + ("LOFI AMF FIX", "MODE DEFAULTS") + STOCK13 + ("EXTPROBE",),
    fx1=("EXTPROBE", "FILTER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    window=(("EXTPROBE", 0x33DA3), ("LOAD METER", 0x37DA3), ("LOAD METER:B", 0x37E50)),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
