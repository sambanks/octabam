"""scenes-midisc -- MIDI SCENES beside SCENES P2 and PLOCKS P2, with KITS.

The pair the ledger refused until 10 Oct 2026: SCENES P2 kept its page-2
locks in the Part bytes MIDI SCENES stores in. Its cells are now bytes 30
and 31 of the stock scene block. The 14 stock effects keep the FX choosers
stock's.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="scenes-midisc",
    family="mods", proof=Proof.PORT, proof_note="verify_scenesp2 and verify_plocksp2 under the port",
    doc="MIDI SCENES + KITS + page-2 scene locks (SCENES P2) + page-2 parameter locks (PLOCKS P2), stock effects.",
    modules=("MIDI SCENES", "STORE", "KITS", "SCENES P2", "PLOCKS P2",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
