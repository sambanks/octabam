"""cxosc-poly -- CX OSC with VOICES=POLY on the stock effects.

Gate remix for verify_cxosc poly path (Tim VOIC/CHRD on LFO page).
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="cxosc-poly",
    family="mods",
    proof=Proof.CHECK,
    proof_note="CX OSC VOICES=POLY gate remix for verify_cxosc; port/check only until HW",
    doc="CX OSC VOICES=POLY: PLAYBACK PTCH RATO INDX FINE FOLD MIX; SETUP CAR MOD DEC SYMM FDBK PWM; LFO VOIC/CHRD; stock FX.",
    modules=("CX OSC",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    settings={
        ("ilia.cxosc", "PLACE"): Pin("DRAM"),
        ("ilia.cxosc", "VOICES"): "POLY",
    },
)
