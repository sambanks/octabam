"""octabam-verbs -- octabam with VERBERATION in place of the three stock reverbs: the core ColdFire modules, every other ColdFire module that fits, the 11 other stock effects, and MODULATION, SPECTRUM, CHARACTER, SHATTER and COMPRESSOR's side-chain loaded on demand, and VIBRATO, TRANSIENT and RESONATOR resident in the reverbs' words. PLATE REV, SPRING REV and DARK REV are off both choosers and their ids are VERB PLATE, VERB ROOM and VERB HALL: VERBERATION's code starting in PLATE, ROOM and HALL mode."""
from remix.schema import Pin, Proof, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES", "PATTERN MUTE",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD", "EVENTS",
        "LOAD METER")
# COMPRESSOR's row is SIDECHAIN_COMPRESSOR's: stock COMPRESSOR with a side-chain KEY on page 2, its DSP
# loaded on demand while a track uses COMPRESSOR (docs/contributing/DEMAND_LOADER.md). Out 1 Nov 2026 (433e22e)
# with TRANSIENT and DISTORX, back 4 Nov 2026: KEY reads "--" while the side-chain is not loaded (#934).
STOCK11 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
           "COMB FILTER", "SIDECHAIN_COMPRESSOR", "LO-FI", "DELAY")
OURS = ("MODULATION", "SPECTRUM", "CHARACTER", "SHATTER", "VERBERATION", "VERB PLATE", "VERB ROOM", "VERB HALL")
# Resident beside VERBERATION in the stock reverbs' harvested words (2,724 a payload; with these, about 560 free on
# each): not demand-loaded, so the window layout below is octabam's unchanged. VIBRATO and TRANSIENT on FX1 and
# FX2, RESONATOR on FX1 (its FX2 instance is a dry pass). octabam keeps every stock effect, so it has no such words.
RESIDENT = ("VIBRATO", "TRANSIENT", "RESONATOR")
# VERB PARTS converts a Part saved with a stock reverb to its row's defaults as the firmware applies it.
VERB_PARTS = ("VERB PARTS",)
# Every other ColdFire module that can share this image (the ledger; HOOKS joins the pairs that
# share a stock site). Not here: ANALOG BD (its fixed pre-boot DSP scratch 0x40b00000 is under
# this much DRAM code), SYNTH MACHINE (the cave 0x400d24d0 the stock DELAY reads, and OCTA303's
# renderer and resolver), CX OSC (with a host reading the USB audio, a continuous MIDI clock and a program change
# before START it stopped the DSP frame loop in every image that had it, 1 Nov 2026),
# CF METER IDLE and WAVE LOAD (CF METER's FX2 id is MODULATION's),
# MIDI LOOPBACK (MIDI SCENES), DIRECT JUMP and PERSISTENT BUFFERS (DIRECT_JUMP_KYOTI and BUFFER
# SAVER do their jobs), and the bus and diagnostic modules (TEMPO SYNC, TEMPO BUS, RIG HOSTS, BOOT TRACE).
# STEM REC, SCOPE, MIDI SCALES and RND NAME are not here either: images with them left program changes
# unapplied in a loader soak (2 to 5 of 32 transitions; none in the images without them) on Sam's MKII, 1 Nov 2026.
# FX2 LOCK is not here: it makes the FX2 chooser's YES close without selecting, and this remix has no engine to lock to a track.
# Added 7 Nov 2026 (each builds beside the rest; not yet soaked here): SCALES, as in octabam; CHORDS FACTORY with PAGES, the page
# key it cycles; SCREEN, SLOW LFO, BAR LED and REC CS1 SKIP.
COLDFIRE = ("SCALES", "OCTA303", "MORPH", "REC THRESHOLD", "BUFFER SAVER", "COPY PROJECT", "EUCLID FILL",
            "TRACK PATTERNS", "VARISPEED",
            "CHORDS FACTORY", "TRIG MODES", "PAGES", "SCREEN", "SLOW LFO", "BAR LED", "REC CS1 SKIP")
STOCK_FX1 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
             "COMB FILTER", "SIDECHAIN_COMPRESSOR", "LO-FI")

REMIX = Remix(
    name="octabam-verbs",
    family="mods", proof=Proof.CHECK,
    proof_note="not flashed; `make check` (CI)",
    doc="octabam with VERBERATION and its PLATE, ROOM and HALL rows in place of PLATE REV, SPRING REV and DARK REV: the core ColdFire modules and every other ColdFire module that fits, the 11 other stock effects, and SPECTRUM, CHARACTER, MODULATION, SHATTER and COMPRESSOR's side-chain loaded on demand, with VIBRATO, TRANSIENT and RESONATOR resident in the reverbs' words.",
    modules=CORE + ("LOFI AMF FIX", "MODE DEFAULTS", "DLPUMP", "DLCOPY", "SC LOAD METER BRIDGE",
                     "KEYBUS", "SC KEYBUS BRIDGE") + STOCK11 + OURS
            + RESIDENT + COLDFIRE + VERB_PARTS,
    # The window layout is octabam's (docs/contributing/DEMAND_LOADER.md): DLCOPY, the stub and LOAD METER's DSP
    # half resident above offset 0x3da3 of the slots and below 0x37f00, where payload B's boot zero loop
    # starts; the demand effects at offset 0x3820 of the four FX2 slots in the window (core A tracks 7 and 8,
    # core B tracks 3 and 4). What writes there is different. The stock reverbs are off both choosers, so
    # their code is harvested and no window_guard is needed: the remaining stock effects stop by offset 0xbff,
    # MODULATION's FX2 buffer is 2,048 words, and VERBERATION's ring is 14,366 words, to offset 0x381d,
    # just below the homes (modules/verberation/README.md). So every home is always free of a reverb, and
    # SIDECHAIN_COMPRESSOR's one home, the fourth block's top, is never under one either.
    fx1=("SPECTRUM", "CHARACTER", "MODULATION") + RESIDENT + STOCK_FX1,   # the chooser order on FX1; the stations also run live on FX2 (SLOTS pin below)
    # DLCOPY follows the five demand entries (x:$33da3 + 8 k, k = 0..4).
    window=(("DLCOPY", 0x33DCB), ("KEYBUS", 0x33E5E), ("LOAD METER", 0x37DA3), ("LOAD METER:B", 0x37E50),
            ("SPECTRUM", 0x33820), ("CHARACTER", 0x37820), ("MODULATION", 0x3B820),
            ("SIDECHAIN_COMPRESSOR", 0x3F820), ("SHATTER", 0x37C10)),
    # DLPUMP loads in this order, and the first free home wins: SIDECHAIN_COMPRESSOR has one home, the fourth
    # block, which the others reach only as their second or later home.
    # SHATTER (378 words, FX2 only) first goes to the second block behind CHARACTER's 1,008 words, so its first
    # address is no other demand effect's (each id-dispatched effect needs its own); the fourth block, SC's only
    # home, is its last.
    window_demand=("MODULATION", "SPECTRUM", "CHARACTER", "SIDECHAIN_COMPRESSOR", "SHATTER"),
    # The other homes: each effect can be loaded into any block it fits (the code is assembled once per home). The loader
    # sends the first home whose block holds no other demand effect (no reverb here reaches a home). MODULATION (1,561 words) needs a block with 2,016
    # words above 0x3820, which the third and fourth have; the first two end at the loader (1,411 words).
    window_homes=(("MODULATION", 0x3F820),
                  ("SPECTRUM", 0x37820), ("SPECTRUM", 0x3B820), ("SPECTRUM", 0x3F820),
                  ("CHARACTER", 0x33820), ("CHARACTER", 0x3B820), ("CHARACTER", 0x3F820),
                  ("SHATTER", 0x33820), ("SHATTER", 0x3B820), ("SHATTER", 0x3F820)),
    # KEYBUS (17 words) fills DLCOPY's tail gap and the loader follows it; SC's bridged stubs then
    # end at 0x33FFF, the block's last resident word.
    window_loader=0x33E6F,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM"),
              ("octabam.sidechain-compressor", "FORM"): Pin("SHARED"),
              ("octabam.sidechain-compressor", "PLACE"): Pin("DRAM"),
              # no bus here, so the cycle envelope is not priced with the stations on FX1 only
              **{(f"octabam.{k.lower()}", "SLOTS"): Pin("FX1+FX2")
                 for k in ("SPECTRUM", "CHARACTER", "MODULATION", "VIBRATO")}},
)
