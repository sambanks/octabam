"""cx-poly -- Ilia's CX OSC poly handoff: same stack as cx, VOICES=POLY.

This keeps the modules and settings from `cx` and opts into CX OSC polyphony.
The LFO page uses VOIC and CHRD in place of LFO 3 SPD3 and DEP3.
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
    name="cx-poly",
    family="mods",
    proof=Proof.CHECK,
    proof_note="CX OSC VOICES=POLY + SHATTER + VOID + SCOPE + DARK + COPY; stock DELAY; stock COMP; port/check only until HW.",
    doc="CORE + STEM REC + CX OSC (VOICES=POLY, selector cap 4) + SHATTER + VOID + SCOPE + DARK REV + DELAY + COPY PROJECT + stock COMP.",
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
        "DARK REV",
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
