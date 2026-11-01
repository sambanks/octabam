"""octabam-bus -- the core ColdFire modules plus the delay and reverb bus.

CORE and the extra ColdFire modules of octabam (OCTA303, MORPH, REC THRESHOLD, BUFFER SAVER,
COPY PROJECT, EUCLID FILL, FX2 LOCK, TRACK PATTERNS) with the bus effects: BusDelay on T1's FX2, BusVerb on T5's FX2,
SEND on every other track's FX2, the stock DELAY on T8, TEMPO SYNC, TEMPO BUS, MODE
DEFAULTS, RIG HOSTS and FX2 LOCK, and LOFI AMF FIX. USB is MAIN CUE.

FX1 lists SPECTRUM, CHARACTER and MODULATION and ten stock effects (FILTER,
EQUALIZER, DJ EQ, PHASER, FLANGER, CHORUS, SPATIALIZER, COMB FILTER, COMPRESSOR,
LO-FI). The stock effects stay in internal P untouched; the servers, SEND, the stations
and LOAD METER's DSP half run from the shared P window. The three stock reverbs have
no chooser row: FX2 is locked and BusVerb replaces them.
"""

from remix.schema import Pin, Proof, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2", "EVENTS",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES", "PATTERN MUTE",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD",
        "LOAD METER")
# The ColdFire modules octabam carries beyond CORE (FX2 LOCK is in MODULES below).
COLDFIRE = ("OCTA303", "MORPH", "REC THRESHOLD", "BUFFER SAVER", "COPY PROJECT", "EUCLID FILL",
            "TRACK PATTERNS")
STOCK_FX1 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
             "COMB FILTER", "COMPRESSOR", "LO-FI")

REMIX = Remix(
    name="octabam-bus",
    family="rig", proof=Proof.CHECK, proof_note="",
    doc="CORE + the extra ColdFire modules of octabam + the delay and reverb bus (BusDelay on T1's FX2, BusVerb on T5's FX2, SEND on every other track's FX2, the stock DELAY on T8) + SPECTRUM, CHARACTER and MODULATION and ten stock effects on FX1.",
    modules=("LOFI AMF FIX", "REVERB SERVER", "DELAY SERVER", "SEND", "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "DELAY",       # the stock DELAY keeps its chooser row: T8 hosts it
             "FX2 LOCK") + CORE + COLDFIRE,   # the chooser cannot change any track's FX2
    fallback="SEND",
    window=(("DELAY SERVER:B", 0x35800), ("SEND", 0x35df0), ("SEND:B", 0x35f00),
            ("MODULATION", 0x36200), ("SPECTRUM", 0x36820), ("CHARACTER", 0x36da0),
            ("REVERB SERVER", 0x371a0), ("LOAD METER", 0x37b00), ("LOAD METER:B", 0x37bc0)),
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION") + STOCK_FX1,
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
