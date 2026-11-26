"""Standalone native Analog BD machine with stock track effects."""
from remix.schema import Remix, Evidence, Level
from remix import stock
REMIX=Remix(name="analog-bassdrum", family="mods", evidence=(Evidence(Level.EMULATOR,
    note="source/UI under the port; earlier ANALOGBD1 auditioned on MK1, current revision unflashed"),),
    doc="Analog BD source machine, switchable 808/909, stock AMP and FX.",
    modules=("ANALOG BD", "MACHINES", *stock.effects("SPRING REV")),
    fallback="NONE")
