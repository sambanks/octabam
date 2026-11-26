from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="pattern-mute-modes",
    family="test",
    evidence=(Evidence(Level.EMULATOR,
        note="PATTERN MUTE beside MUTE_MODES"),),
    doc="smoke: PATTERN MUTE and MUTE_MODES together, stock effects",
    modules=("PATTERN MUTE", "MUTE_MODES", "STORE",
             *stock.EFFECTS),
    fallback="NONE",
)
