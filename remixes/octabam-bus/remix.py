"""octabam-bus -- the core ColdFire modules plus the delay and reverb bus.

CORE (see octabam-inserts) with the bus effects: BusDelay on T1's FX2,
BusVerb on T5's FX2, SEND on every other track's FX2, the stock DELAY on T8,
SPECTRUM, CHARACTER and MODULATION on FX1, TEMPO SYNC, TEMPO BUS, MODE DEFAULTS,
RIG HOSTS and FX2 LOCK. USB is MAIN CUE.
"""

from remix.schema import Pin, Proof, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "EDIT EVENTS", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD",
        "LOAD METER")

REMIX = Remix(
    name="octabam-bus",
    family="rig", proof=Proof.PORT, proof_note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); EDIT EVENTS migration: software only, hardware pending",
    doc="CORE + the delay and reverb bus (BusDelay on T1's FX2, BusVerb on T5's FX2, SEND on every other track's FX2, the stock DELAY on T8) + SPECTRUM, CHARACTER and MODULATION on FX1.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "DELAY",       # the stock DELAY keeps its chooser row: T8 hosts it
             "FX2 LOCK") + CORE,   # the chooser cannot change any track's FX2
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
