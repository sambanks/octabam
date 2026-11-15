"""TRACK PATTERNS on the core modules: the core ColdFire modules (KITS and
DIRECT_JUMP_KYOTI among them) and the 14 stock effects, for running the
module beside the modules it shares handlers with."""

from remix.schema import Pin, Evidence, Level, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2", "EVENTS",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD")
STOCK14 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
           "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV")

REMIX = Remix(
    name="trackpatterns-core",
    family="mods", evidence=(Evidence(Level.UNIT, unit="MKII", image="OCTABAM8", date="2026-10-22",
        note="gesture on T1 and M1, global change, save and power cycle passed (contributor's report)"),),
    doc="TRACK PATTERNS on the core modules (KITS, DIRECT_JUMP_KYOTI and the other core modules).",
    modules=("TRACK PATTERNS",) + CORE + ("LOFI AMF FIX",) + STOCK14,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): Pin("OFF"),
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
