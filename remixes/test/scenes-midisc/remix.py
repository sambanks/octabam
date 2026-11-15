"""scenes-midisc -- MIDI SCENES beside SCENES P2 and PLOCKS P2, with KITS.

The pair the ledger refused until 10 Oct 2026: SCENES P2 kept its page-2
locks in the Part bytes MIDI SCENES stores in. Its cells are now bytes 30
and 31 of the stock scene block. The 14 stock effects keep the FX choosers
stock's.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="scenes-midisc",
    family="mods", evidence=(Evidence(Level.EMULATOR, ref="verify_scenes_p2",
        note="verify_scenes_p2 and verify_plocks_p2 under the port"),),
    doc="MIDI SCENES + KITS + page-2 scene locks (SCENES P2) + page-2 parameter locks (PLOCKS P2), stock effects.",
    modules=("MIDI SCENES", "STORE", "KITS", "SCENES P2", "EVENTS", "PLOCKS P2",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
