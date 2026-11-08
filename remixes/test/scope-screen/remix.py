"""scope-screen -- SCOPE + SCREEN (+ USB) on stock FX for on-unit screendump."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="scope-screen",
    family="mods",
    proof=Proof.CHECK,
    proof_note="minimal SCOPE+SCREEN+USB for unit screendump; not a stack handoff",
    doc="stock FX + TUNER + SCOPE + USB + SCREEN (SysEx screendump on DIN or USB).",
    modules=(
        "USB",
        "SCREEN",
        "TUNER",
        "SCOPE",
        "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
        "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
        "DELAY", "PLATE REV", "SPRING REV", "DARK REV",
    ),
    fallback="NONE",
    settings={
        ("octabam.usb", "TRACKS"): "OFF",
        ("octabam.usb", "MAIN"): 0,
        ("octabam.usb", "CUE"): 0,
        ("octabam.usb", "MASTER"): 0,
        ("octabam.usb", "IN"): "OFF",
    },
)
