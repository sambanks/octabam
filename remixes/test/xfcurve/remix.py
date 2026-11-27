"""XF CURVE with BRAIN and STORE on the stock effects: the curve chosen in PROJ > BRAIN > SETTINGS."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="xfcurve",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_xfcurve",
        note="builds; tools/verify/verify_xfcurve.py"),),
    doc="XF CURVE (the crossfader's curve, a BRAIN setting) with BRAIN, STORE and the stock effects.",
    modules=("XF CURVE", "BRAIN", "STORE", *stock.EFFECTS),
    fallback="NONE",
)
