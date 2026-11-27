"""stock effects with BATCH_BUGFIXES: the MIDI Plays-Free trig, empty-pattern LED and Part-change carryover fixes."""

from remix.schema import Evidence, Level, Remix
from remix import stock

REMIX = Remix(
    name="batch-bugfixes",
    family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="stock effects with BATCH_BUGFIXES: the MIDI Plays-Free trig, empty-pattern LED and Part-change carryover fixes.",
    modules=("BATCH_BUGFIXES",
             *stock.EFFECTS),
    fallback="NONE",
)
