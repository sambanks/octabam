"""v06-rig -- CX OSC, VCA160 and KEYBUS with the modules a host needs to read and switch the unit (REMOTE, USB, REMIX SWITCH)."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="v06-rig",
    family="mods", evidence=(Evidence(Level.EMULATOR, note="not run on a unit"),),
    doc="CX OSC, VCA160 and KEYBUS beside the stock effects but PLATE REV, with REMOTE, USB and REMIX SWITCH for tools/hw/ot_v06.py.",
    modules=("REMOTE", "STORE", "USB", "BRAIN", "MEMORY", "REMIX SWITCH", "CX OSC", "VCA160", "KEYBUS",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER",
             "COMPRESSOR", "LO-FI", "DELAY", "SPRING REV", "DARK REV"),
    fx1=("VCA160", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER",
         "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
