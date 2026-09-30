"""Standalone native Analog BD machine with stock track effects."""
from remix.schema import Remix, Proof
REMIX=Remix(name="analog-bassdrum", family="mods", proof=Proof.PORT,
    proof_note="source/UI under the port; earlier ANALOGBD1 auditioned on MK1, current revision unflashed",
    doc="Analog BD source machine, switchable 808/909, stock AMP and FX.",
    modules=("ANALOG BD", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "PLATE REV", "DARK REV"),
    fallback="NONE",
    # ANALOG BD composes with stock effects only (build_bus refuses any
    # other DSP section) and OS SWITCH's DSP park is one: kept out until
    # the two are shown to share the dead vectors (30 Sep 2026).
    os_switch=False)
