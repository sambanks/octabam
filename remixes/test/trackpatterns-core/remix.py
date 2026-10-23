"""TRACK PATTERNS on octabam-core: the core ColdFire modules (KITS and
DIRECT_JUMP_KYOTI among them) and the 14 stock effects, for running the
module beside the modules it shares handlers with."""

from remix.schema import Pin, Proof, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "EDIT EVENTS", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD")
STOCK14 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
           "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV")

REMIX = Remix(
    name="trackpatterns-core",
    family="mods", proof=Proof.PORT,
    proof_note="MKII, OCTABAM8, 22 Oct 2026: gesture on T1 and M1, global change, save and power cycle passed (contributor's report); EDIT EVENTS migration: software only, hardware pending",
    doc="TRACK PATTERNS on octabam-core (KITS, DIRECT_JUMP_KYOTI and the other core modules).",
    modules=("TRACK PATTERNS",) + CORE + ("LOFI AMF FIX",) + STOCK14,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): Pin("OFF"),
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
