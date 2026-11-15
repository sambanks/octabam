"""DISTORX on FX1 and FX2, beside the stock effects (CHORUS, PLATE REV and SPRING REV give up their words)."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="distorx",
    family="effects",
    evidence=(Evidence(Level.UNIT, unit="MKI", date="2026-10-22",
        note="image DTXPR3 (BUILD 96, this remix, on 0x05), 22 Oct 2026: T1 for more than four minutes with four "
             "DISTORX at once, no clicks; before, DTXPR1 (BUILD 91, on 0x0a), 21 Oct 2026: every knob in every "
             "MODE, MODE changed while playing without a click, FX1 and FX2, four at once on both cores for 5 "
             "minutes, an LFO on DRIV/TONE, a scene with another MODE through the crossfader, save and reload; "
             "verify_distorx (dsp_host)"),),
    doc="DISTORX on FX1 and FX2, beside the stock effects but CHORUS, PLATE REV and SPRING REV, whose words it takes.",
    modules=(
        "DISTORX",
        "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
        "COMB FILTER", "COMPRESSOR", "LO-FI",
        "DELAY", "DARK REV",
    ),
    fx1=("DISTORX",
         "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
         "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
