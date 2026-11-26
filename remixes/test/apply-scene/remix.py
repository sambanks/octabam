"""apply-scene -- APPLY SCENE beside BRAIN, KITS and SCENES P2 on the stock effects.

The scene keys' gestures (SCENE + YES, SCENE with trigs held, SCENE A +
SCENE B + trig) next to the modules that share the scene and Part state:
KITS (the Part a pattern plays), SCENES P2 (bytes 30-31 of each scene) and
BRAIN (the TRACKS and COMMIT settings). No DSP module; the 14 stock effects keep the
FX choosers stock's.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="apply-scene",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_apply_scene",
        note="verify_apply_scene under the port"),),
    doc="APPLY SCENE with BRAIN, KITS and SCENES P2 on the stock effects.",
    modules=("APPLY SCENE", "BRAIN", "STORE", "KITS", "SCENES P2", "BATCH_BUGFIXES",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
