from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="scales",
    family="mods",
    evidence=(Evidence(Level.EMULATOR, ref="verify_scales",
        note="verify_scales"),),
    doc="SCALES alone, on the 14 stock effects: ARP SETUP's KEY, the chooser, the snapped notes and the CHROMATIC keys.",
    modules=("SCALES", "STORE", *stock.EFFECTS),
    fallback="NONE",
)
