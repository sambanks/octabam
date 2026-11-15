"""OCTA303 + dEVILish beside the stock effects (PHASER, whose id dEVILish takes, gives up its words)."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="devilish",
    family="mods",
    evidence=(Evidence(Level.UNIT, unit="MKI", date="2026-10-22",
        note="image DEVPR2 (BUILD 93, this remix), 22 Oct 2026: every dEVILish knob, an LFO, a scene, a lock, save"
             " and reload; test_octa303 and verify_octa303_ui under the port"),),
    doc="OCTA303 and dEVILish (the Devil Fish mods on FX1 or FX2 of an OCTA-303 track) beside the stock effects but PHASER.",
    modules=(
        "OCTA303", "DEVILISH",
        "FILTER", "EQUALIZER", "DJ EQ", "FLANGER", "CHORUS",
        "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
        "DELAY", "PLATE REV", "SPRING REV", "DARK REV",
    ),
    fx1=("DEVILISH",
         "FILTER", "EQUALIZER", "DJ EQ", "FLANGER", "CHORUS",
         "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
