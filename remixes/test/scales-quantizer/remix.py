from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="scales-quantizer",
    family="mods",
    evidence=(Evidence(Level.EMULATOR, ref="verify_scales",
        note="verify_scales"),),
    doc="SCALES beside SCALE QUANTIZER: the audio tracks' CHROMATIC keys light SCALE on ROOT.",
    modules=("SCALES", "STORE", "SCALE QUANTIZER", *stock.EFFECTS),
    fallback="NONE",
)
