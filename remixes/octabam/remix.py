"""octabam -- the core ColdFire modules, all 14 stock effects and our effects.

CORE (BRAIN, STORE, KITS, MIDI SCENES, SCENES P2, PLOCKS P2, CC MAP, CC FEEDBACK,
USB at MAIN CUE, the recorder and bug fixes, MUTE_MODES from DRAM, PATTERN MUTE, SCALE QUANTIZER,
TUNER, DIRECT_JUMP_KYOTI, RELOAD_FROM_PROJECT, RLEN PLEN, LOAD METER) with all 14
stock effects and LOFI AMF FIX. SPECTRUM, CHARACTER, MODULATION and TRANSIENT are loaded
into the shared P window while a track uses them (docs/proposals/DEMAND_LOAD.md); the
stock reverbs are wrapped so they never run over loaded code. LOAD METER's DSP half, the
loader's stubs, copier and wrappers sit in the window words no stock effect writes.
Every other ColdFire module that can share the image (COLDFIRE below). No bus and no SEND
(fallback NONE).
"""
from remix.schema import Pin, Proof, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES", "PATTERN MUTE",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD", "EVENTS",
        "LOAD METER")
# COMPRESSOR's row is SIDECHAIN_COMPRESSOR's: stock COMPRESSOR with a side-chain KEY on page 2, its DSP
# loaded on demand while a track uses COMPRESSOR (docs/proposals/SC_DEMAND_LOAD.md)
STOCK14 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
           "COMB FILTER", "SIDECHAIN_COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV")
OURS = ("MODULATION", "SPECTRUM", "CHARACTER", "TRANSIENT")
# Every other ColdFire module that can share this image (the ledger; HOOKS joins the pairs that
# share a stock site). Not here: ANALOG BD (its fixed pre-boot DSP scratch 0x40b00000 is under
# this much DRAM code), CX OSC and SYNTH MACHINE (the cave 0x400d24d0 the stock DELAY reads),
# CF METER IDLE and WAVE LOAD (CF METER's FX2 id is MODULATION's),
# MIDI LOOPBACK (MIDI SCENES), DIRECT JUMP and PERSISTENT BUFFERS (DIRECT_JUMP_KYOTI and BUFFER
# SAVER do their jobs), and the bus and diagnostic modules (TEMPO SYNC, TEMPO BUS, RIG HOSTS, BOOT TRACE).
COLDFIRE = ("OCTA303", "MORPH", "REC THRESHOLD", "BUFFER SAVER", "COPY PROJECT", "EUCLID FILL",
            "FX2 LOCK", "MIDI SCALES", "RND NAME", "SCOPE", "TRACK PATTERNS",
            "VARISPEED", "STEM REC")
STOCK_FX1 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
             "COMB FILTER", "SIDECHAIN_COMPRESSOR", "LO-FI")

REMIX = Remix(
    name="octabam",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="The core ColdFire modules and every other ColdFire module that fits, all 14 stock effects, and SPECTRUM, CHARACTER, MODULATION and TRANSIENT, loaded on demand.",
    modules=CORE + ("LOFI AMF FIX", "MODE DEFAULTS", "DLPUMP", "DLCOPY", "SC LOAD METER BRIDGE") + STOCK14 + OURS
            + COLDFIRE,
    # The window words no stock effect writes (docs/proposals/DEMAND_LOAD.md): the top of each FX2
    # slot from 0x3da3 up, and below 0x37f00, where payload B's boot zero loop starts. DLCOPY is the
    # lowest upload; the stub and the reverb guards follow it (window_loader); LOAD METER's DSP half
    # fills the next gap. The four effects sit at the top of the four slots (core A tracks 7
    # and 8, core B tracks 3 and 4), from offset 0x3820 (TRANSIENT 0x3e00), and are not uploaded: PLATE REV writes
    # up to offset 0x37ff and SPRING REV up to 0xfff, so only DARK REV (0x3da2) reaches the code, and not TRANSIENT's.
    fx1=("SPECTRUM", "CHARACTER", "MODULATION") + STOCK_FX1,   # the chooser order on FX1; the stations also run live on FX2 (SLOTS pin below)
    # DLCOPY follows the five demand entries (x:$33da3 + 8 k, k = 0..4). SIDECHAIN_COMPRESSOR's one copy (the
    # shared form: code, its two tables, then its key window and counters as zero words, 1,711 words) has one
    # home, the fourth block's top, which only DARK REV on T4's FX2 reaches; its four hooks go to resident stubs.
    window=(("DLCOPY", 0x33DCB), ("LOAD METER", 0x37DA3), ("LOAD METER:B", 0x37E50),
            ("SPECTRUM", 0x33820), ("CHARACTER", 0x37820), ("MODULATION", 0x3B820), ("TRANSIENT", 0x3FE00),
            ("SIDECHAIN_COMPRESSOR", 0x3F820)),
    # DLPUMP loads in this order, and the first free home wins: SIDECHAIN_COMPRESSOR has one home, the fourth block,
    # TRANSIENT four, so SC comes first and TRANSIENT moves to another block when both are in use.
    window_demand=("MODULATION", "SPECTRUM", "CHARACTER", "SIDECHAIN_COMPRESSOR", "TRANSIENT"),
    # The other homes: each effect can be loaded into any block it fits (the code is assembled once per home). The loader
    # sends the first home whose block holds no other demand effect and whose FX2 slot is not a stock reverb that reaches
    # the code, and moves a loaded effect when such a reverb arrives. MODULATION (1,561 words) needs a block with 2,016
    # words above 0x3820, which the third and fourth have; the first two end at the loader (1,411 words). TRANSIENT
    # (357 words) also fits at 0x3e00 of the third block, above DARK REV's highest word.
    window_homes=(("MODULATION", 0x3F820),
                  ("SPECTRUM", 0x37820), ("SPECTRUM", 0x3B820), ("SPECTRUM", 0x3F820),
                  ("CHARACTER", 0x33820), ("CHARACTER", 0x3B820), ("CHARACTER", 0x3F820),
                  ("TRANSIENT", 0x3BE00), ("TRANSIENT", 0x33820), ("TRANSIENT", 0x37820)),
    window_guard=("PLATE REV", "DARK REV", "SPRING REV"),
    window_loader=0x33E5E,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM"),
              ("octabam.sidechain-compressor", "FORM"): Pin("SHARED"),
              ("octabam.sidechain-compressor", "PLACE"): Pin("DRAM"),
              # no bus here, so the cycle envelope is not priced with the stations on FX1 only
              **{(f"octabam.{k.lower()}", "SLOTS"): Pin("FX1+FX2")
                 for k in ("SPECTRUM", "CHARACTER", "MODULATION")}},
)
