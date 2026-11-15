"""ANALOG BD and OCTA303 in one image: HOOKS gives the track's machine list seven rows, ANALOG BD on row 5 and OCTA-303 on row 6, and the list scrolls."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="hooks-machines",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_hooks",
        note="verify_hooks: the bridged machine sites in this image; the two machines' UI gates under the port"),),
    doc="ANALOG BD and OCTA303 in one image: HOOKS gives the track's machine list seven rows, ANALOG BD on row 5 and OCTA-303 on row 6, and the list scrolls.",
    modules=("ANALOG BD", "OCTA303",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "DARK REV"),
    fallback="NONE",
)
