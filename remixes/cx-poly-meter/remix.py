"""cx-poly-meter -- cx-poly with the CF METER readout for on-unit profiling.

CF METER takes the DSP words used by DARK REV, so this diagnostic build leaves
DARK REV out and adds CF METER plus its idle-time counter.
"""

from remix.schema import Pin, Proof, Remix

CORE = (
    "BRAIN", "STORE", "KITS", "MIDI SCENES", "SCENES P2", "PLOCKS P2",
    "CC MAP", "CC FEEDBACK", "USB",
    "RECORDER LOOP FIX", "BATCH_BUGFIXES", "ERASE_EMPTY_TRIGLESS_LOCKS",
    "QUANTIZE_LIVE_REC_TOGGLE", "REC_TRIG_MUTE", "MUTE_MODES",
    "SCALE QUANTIZER", "TUNER", "DIRECT_JUMP_KYOTI", "RELOAD_FROM_PROJECT",
    "RLEN PLEN",
    "ATA WRITE GUARD", "EVENTS",
    "RND NAME",
    "SEQ",
    "COPY PROJECT",
    "PERSISTENT BUFFERS",
    "REMIX SWITCH",
    "SCOPE",
    "SCREEN",
)

REMIX = Remix(
    name="cx-poly-meter",
    family="mods",
    proof=Proof.CHECK,
    proof_note="CX OSC VOICES=POLY + CF METER + CF METER IDLE; DARK REV omitted for meter DSP space; port/check only until HW.",
    doc="cx-poly with CF METER on T8's FX2 and CF METER IDLE for ColdFire performance measurement; DARK REV omitted to free the meter's DSP words.",
    modules=CORE + (
        "MEMORY",
        "STEM REC",
        "CX OSC",
        "SHATTER",
        "VOID",
        "LOFI AMF FIX",
        "FILTER",
        "EQUALIZER",
        "DJ EQ",
        "PHASER",
        "FLANGER",
        "CHORUS",
        "SPATIALIZER",
        "COMPRESSOR",
        "LO-FI",
        "DELAY",
        "CF METER",
        "CF METER IDLE",
    ),
    fx1=(
        "FILTER",
        "EQUALIZER",
        "DJ EQ",
        "PHASER",
        "FLANGER",
        "CHORUS",
        "VOID",
        "COMPRESSOR",
        "LO-FI",
    ),
    fallback="NONE",
    settings={
        ("octabam.usb", "TRACKS"): "OFF",
        ("octabam.usb", "MAIN"): 1,
        ("octabam.usb", "CUE"): 0,
        ("octabam.usb", "MASTER"): 0,
        ("octabam.usb", "IN"): "OFF",
        ("kyoti.mute-modes", "PLACE"): Pin("DRAM"),
        ("ilia.cxosc", "VOICES"): "POLY",
    },
)
