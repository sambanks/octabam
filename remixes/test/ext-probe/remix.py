"""ext-probe -- the core modules and all stock effects but EQUALIZER, with EXTPROBE on FX1: how far into its slot does a stock reverb write?

A measurement build (modules/extprobe/README.md). EXTPROBE takes EQUALIZER's id and sits in the window gap below LOAD METER; no
demand loader is in this image, so nothing but the reverb under test writes the slot at T8.
"""
from remix.schema import Pin, Evidence, Level, Remix
from remix import stock

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD", "EVENTS",
        "LOAD METER")
STOCK13 = stock.effects("EQUALIZER")

REMIX = Remix(
    name="ext-probe",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="octabam's core and stock effects (EQUALIZER's id is the probe's) with EXTPROBE on FX1: the highest window word a reverb writes.",
    modules=CORE + ("LOFI AMF FIX", "MODE DEFAULTS") + STOCK13 + ("EXTPROBE",),
    fx1=("EXTPROBE", *stock.fx1_effects("EQUALIZER")),
    window=(("EXTPROBE", 0x33DA3), ("LOAD METER", 0x37DA3), ("LOAD METER:B", 0x37E50)),
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
