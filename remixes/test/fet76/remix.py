"""FET76 (modelled on the 1176LN) on FX1 and FX2, beside the stock effects (CHORUS, SPATIALIZER, PLATE REV and SPRING REV give up their words)."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="fet76",
    family="effects",
    evidence=(Evidence(Level.EMULATOR, ref="verify_fet76",
        note="verify_fet76 (dsp_host, bit-exact against the fixed-point model); this remix not yet on a unit"),),
    doc="FET76 (modelled on the UREI 1176LN FET limiter) on FX1 and FX2, beside the stock effects but CHORUS, SPATIALIZER, PLATE REV and SPRING REV.",
    modules=(
        "FET76",
        *stock.effects("CHORUS", "SPATIALIZER", "PLATE REV", "SPRING REV"),
    ),
    fx1=("FET76",
         *stock.fx1_effects("CHORUS", "SPATIALIZER")),
    fallback="NONE",
)
