from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="chords",
    family="mods",
    evidence=(Evidence(Level.EMULATOR, ref="verify_chords",
        note="verify_chords"),),
    doc="CHORDS FACTORY with SCALES, on the 14 stock effects: the chord atelier on SRC, a chord step "
        "played as written, the FUNC keyboard in the scale's colours.",
    modules=("CHORDS FACTORY", "SCALES", "STORE", "PAGES", *stock.EFFECTS),
    fallback="NONE",
)
