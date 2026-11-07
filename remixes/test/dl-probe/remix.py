"""dl-probe -- octabam with DLPROBE on FX1 in place of EQUALIZER: the demand loader's counters in the audio of the track it sits on.

A measurement build (modules/dlprobe/README.md). The loader sends on the frames the port delivers.
"""
from remix.schema import Pin, Proof, Remix

CORE = ("BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
        "CC MAP", "CC FEEDBACK", "USB",
        "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
        "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
        "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT", "RLEN PLEN",
        "ATA WRITE GUARD", "EVENTS",
        "LOAD METER")
STOCK14 = ("FILTER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
           "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV")
OURS = ("MODULATION", "SPECTRUM", "CHARACTER", "TRANSIENT")

REMIX = Remix(
    name="dl-probe",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="octabam with DLPROBE on FX1 in place of EQUALIZER (the loader as in octabam).",
    modules=CORE + ("LOFI AMF FIX", "MODE DEFAULTS", "DLPUMP", "DLCOPY", "DLPROBE") + STOCK14 + OURS,
    fx1=("DLPROBE", "SPECTRUM", "CHARACTER", "MODULATION", "FILTER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
         "COMB FILTER", "COMPRESSOR", "LO-FI"),
    # The window words no stock effect writes (docs/contributing/DEMAND_LOADER.md): the top of each FX2
    # slot from 0x3da3 up, and below 0x37f00, where payload B's boot zero loop starts. DLCOPY is the
    # lowest upload; the stub and the reverb guards follow it (window_loader); LOAD METER's DSP half
    # fills the next gap. The four effects sit at offset 0x1000 of the four slots (core A tracks 7
    # and 8, core B tracks 3 and 4) and are not uploaded.
    window=(("DLCOPY", 0x33DC3), ("LOAD METER", 0x37DA3), ("LOAD METER:B", 0x37E50),
            ("SPECTRUM", 0x31000), ("MODULATION", 0x35000), ("CHARACTER", 0x39000), ("TRANSIENT", 0x3D000)),
    window_demand=("MODULATION", "SPECTRUM", "CHARACTER", "TRANSIENT"),
    window_guard=("PLATE REV", "DARK REV", "SPRING REV"),
    window_loader=0x33E56,
    fallback="NONE",
    settings={("octabam.usb", "TRACKS"): "PRE", ("octabam.usb", "MAIN"): 1,
              ("octabam.usb", "CUE"): 1, ("octabam.usb", "MASTER"): 0,
              ("octabam.usb", "IN"): "OFF",
              ("kyoti.mute-modes", "PLACE"): Pin("DRAM")},
)
