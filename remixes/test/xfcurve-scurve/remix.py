"""XF CURVE alone, CURVE pinned to S-CURVE (no BRAIN): the gate's fixed-curve image."""

from remix.schema import Pin, Evidence, Level, Remix

REMIX = Remix(
    name="xfcurve-scurve",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_xfcurve",
        note="tools/verify/verify_xfcurve.py"),),
    doc="XF CURVE pinned to S-CURVE, without BRAIN, on the stock effects.",
    modules=("XF CURVE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    settings={("octabam.xfcurve", "CURVE"): Pin("S-CURVE")},
    fallback="NONE",
)
