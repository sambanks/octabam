"""stock effects with SLOW LFO: LFO MULT 1/2X, 1/4X and 1/8X. Its gate's remix."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="slow-lfo",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with SLOW LFO: LFO MULT gains 1/2X, 1/4X and 1/8X on audio and MIDI tracks.",
    modules=("SLOW LFO",
             *stock.EFFECTS),
    fallback="NONE",
)
