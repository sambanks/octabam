"""XF CURVE alone, CURVE pinned to S-CURVE (no BRAIN): the gate's fixed-curve image."""

from remix.schema import Pin, Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="xfcurve-scurve",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_xfcurve",
        note="tools/verify/verify_xfcurve.py"),),
    doc="XF CURVE pinned to S-CURVE, without BRAIN, on the stock effects.",
    modules=("XF CURVE", *stock.EFFECTS),
    settings={("octabam.xfcurve", "CURVE"): Pin("S-CURVE")},
    fallback="NONE",
)
