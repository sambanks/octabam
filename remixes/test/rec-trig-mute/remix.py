"""stock effects with REC_TRIG_MUTE: [TRACK]+[REC] mutes/unmutes a track's recorder trigs."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="rec-trig-mute",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with REC_TRIG_MUTE: [TRACK]+[REC] mutes/unmutes a track's recorder trigs.",
    modules=("REC_TRIG_MUTE",
             *stock.EFFECTS),
    fallback="NONE",
)
