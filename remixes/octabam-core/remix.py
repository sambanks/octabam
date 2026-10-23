"""octabam-core -- the core ColdFire modules on the 14 stock effects.

CORE (BRAIN, STORE, KITS, MIDI SCENES, SCENES P2, PLOCKS P2, CC MAP, CC FEEDBACK,
USB at MAIN CUE, the recorder and bug fixes, MUTE_MODES from
DRAM, SCALE QUANTIZER, TUNER, DIRECT_JUMP_KYOTI, RELOAD_FROM_PROJECT, RLEN PLEN, ATA WRITE GUARD)
with all 14 stock effects and LOFI AMF FIX. No LOAD METER (its DSP half needs
156 words per payload; the 14 stock effects leave none). USB IN (default OFF) runs
from the tail of payload A (DspSection.tail).
"""

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
    name="octabam-core",
    family="mods", proof=Proof.HARDWARE, proof_note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); EDIT EVENTS held-edit/copy paths on radiohagen's MKII, PLK858 (22 Oct); scoped operator report",
    doc="The core ColdFire modules on the 14 stock effects, with LOFI AMF FIX.",
    modules=CORE + ("LOFI AMF FIX",) + STOCK14,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
