"""XF CURVE alone, CURVE pinned to S-CURVE (no BRAIN): the gate's fixed-curve image."""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="xfcurve-scurve",
    family="mods", proof=Proof.CHECK, proof_note="tools/verify/verify_xfcurve.py",
    doc="XF CURVE pinned to S-CURVE, without BRAIN, on the stock effects.",
    modules=("XF CURVE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    settings={("octabam.xfcurve", "CURVE"): Pin("S-CURVE")},
    fallback="NONE",
)
