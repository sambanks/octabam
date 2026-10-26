"""octabam -- the core ColdFire modules, all 14 stock effects and our effects.

CORE (BRAIN, STORE, KITS, MIDI SCENES, SCENES P2, PLOCKS P2, CC MAP, CC FEEDBACK,
USB at MAIN CUE, the recorder and bug fixes, MUTE_MODES from DRAM, SCALE QUANTIZER,
TUNER, DIRECT_JUMP_KYOTI, RELOAD_FROM_PROJECT, RLEN PLEN, LOAD METER) with all 14
stock effects and LOFI AMF FIX. SPECTRUM, CHARACTER, MODULATION and TRANSIENT are loaded
into the shared P window while a track uses them (docs/proposals/DEMAND_LOAD.md); the
stock reverbs are wrapped so they never run over loaded code. LOAD METER's DSP half, the
loader's stubs, copier and wrappers sit in the window words no stock effect writes.
No bus and no SEND (fallback NONE).
"""
from remix.schema import Pin, Proof, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD", "EVENTS",
        "LOAD METER")
STOCK14 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
           "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV")
OURS = ("MODULATION", "SPECTRUM", "CHARACTER", "TRANSIENT")
STOCK_FX1 = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
             "COMB FILTER", "COMPRESSOR", "LO-FI")

REMIX = Remix(
    name="octabam",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="The core ColdFire modules, all 14 stock effects, and SPECTRUM, CHARACTER, MODULATION and TRANSIENT, loaded on demand.",
    modules=CORE + ("LOFI AMF FIX", "MODE DEFAULTS", "DLPUMP", "DLCOPY") + STOCK14 + OURS,
    # The window words no stock effect writes (docs/proposals/DEMAND_LOAD.md): the top of each FX2
    # slot from 0x3da3 up, and below 0x37f00, where payload B's boot zero loop starts. DLCOPY is the
    # lowest upload; the stub and the reverb guards follow it (window_loader); LOAD METER's DSP half
    # fills the next gap. The four effects sit at the top of the four slots (core A tracks 7
    # and 8, core B tracks 3 and 4), from offset 0x3820 (TRANSIENT 0x3e00), and are not uploaded: PLATE REV writes
    # up to offset 0x37ff and SPRING REV up to 0xfff, so only DARK REV (0x3da2) reaches the code, and not TRANSIENT's.
    fx1=("SPECTRUM", "CHARACTER", "MODULATION") + STOCK_FX1,   # the stations run on FX1 only (an FX2 instance renders dry)
    window=(("DLCOPY", 0x33DC3), ("LOAD METER", 0x37DA3), ("LOAD METER:B", 0x37E50),
            ("SPECTRUM", 0x33820), ("CHARACTER", 0x37820), ("MODULATION", 0x3B820), ("TRANSIENT", 0x3FE00)),
    window_demand=("MODULATION", "SPECTRUM", "CHARACTER", "TRANSIENT"),
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
    window_loader=0x33E56,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
