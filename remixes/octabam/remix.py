"""octabam -- the core ColdFire modules, every other ColdFire module that fits, all 14 stock effects, and MODULATION, SPECTRUM and CHARACTER loaded on demand. TRANSIENT, DISTORX and SIDECHAIN_COMPRESSOR are not in this remix."""
from remix.schema import Pin, Proof, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES", "PATTERN MUTE",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD", "EVENTS",
        "LOAD METER")
STOCK14 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
           "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV")
OURS = ("MODULATION", "SPECTRUM", "CHARACTER")
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
COLDFIRE = ("OCTA303", "MORPH", "REC THRESHOLD", "BUFFER SAVER", "COPY PROJECT", "EUCLID FILL",
            "TRACK PATTERNS", "VARISPEED")
STOCK_FX1 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
             "COMB FILTER", "COMPRESSOR", "LO-FI")

REMIX = Remix(
    name="octabam",
    family="mods", proof=Proof.HARDWARE,
    proof_note="Sam's MKII, image OCTABAMR3 (this remix before the rebase onto fa49e92f), USB TRACKS PRE, 1 Nov 2026: "
               "ot_suite.py phases pre-meter, pre-transport, pre-usb, dsp-watch, fx01-fx03 (74 layouts, no crash), "
               "loader01-02, kits-identity, scenes-sweep, scenes-latency, djump-off/on/burst; mix-soak and the manual "
               "plan not run (docs/contributing/HARDWARE_SUITE.md)",
    doc="The core ColdFire modules and every other ColdFire module that fits, all 14 stock effects, and SPECTRUM, CHARACTER and MODULATION, loaded on demand.",
    modules=CORE + ("LOFI AMF FIX", "MODE DEFAULTS", "DLPUMP", "DLCOPY") + STOCK14 + OURS
            + COLDFIRE,
    # The window words no stock effect writes (docs/proposals/DEMAND_LOAD.md): the top of each FX2
    # slot from 0x3da3 up, and below 0x37f00, where payload B's boot zero loop starts. DLCOPY is the
    # lowest upload; the stub and the reverb guards follow it (window_loader); LOAD METER's DSP half
    # fills the next gap. The three effects sit at offset 0x3820 of three of the four slots (core A tracks 7
    # and 8, core B tracks 3 and 4) and are not uploaded: PLATE REV writes up to offset 0x37ff and SPRING REV up to 0xfff,
    # so only DARK REV (0x3da2) reaches the code.
    fx1=("SPECTRUM", "CHARACTER", "MODULATION") + STOCK_FX1,   # the chooser order on FX1; the stations also run live on FX2 (SLOTS pin below)
    # DLCOPY follows the three demand entries (x:$33da3 + 8 k, k = 0..2).
    window=(("DLCOPY", 0x33DBB), ("LOAD METER", 0x37DA3), ("LOAD METER:B", 0x37E50),
            ("SPECTRUM", 0x33820), ("CHARACTER", 0x37820), ("MODULATION", 0x3B820)),
    # DLPUMP loads in this order, and the first free home wins.
    window_demand=("MODULATION", "SPECTRUM", "CHARACTER"),
    # The other homes: each effect can be loaded into any block it fits (the code is assembled once per home). The loader
    # sends the first home whose block holds no other demand effect and whose FX2 slot is not a stock reverb that reaches
    # the code, and moves a loaded effect when such a reverb arrives. MODULATION (1,561 words) needs a block with 2,016
    # words above 0x3820, which the third and fourth have; the first two end at the loader (1,411 words).
    window_homes=(("MODULATION", 0x3F820),
                  ("SPECTRUM", 0x37820), ("SPECTRUM", 0x3B820), ("SPECTRUM", 0x3F820),
                  ("CHARACTER", 0x33820), ("CHARACTER", 0x3B820), ("CHARACTER", 0x3F820)),
    window_guard=("PLATE REV", "DARK REV", "SPRING REV"),
    window_loader=0x33E66,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM"),
              # no bus here, so the cycle envelope is not priced with the stations on FX1 only
              **{(f"octabam.{k.lower()}", "SLOTS"): Pin("FX1+FX2")
                 for k in ("SPECTRUM", "CHARACTER", "MODULATION")}},
)
