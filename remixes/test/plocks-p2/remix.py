"""plocks-p2 -- PLOCKS P2 with SCENES P2 on the stock effects.

Page-2 parameter locks need SCENES P2 (its dial hooks draw a held step's
lock). No DSP module; the 14 stock effects keep the FX choosers stock's.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="plocks-p2",
    family="mods", proof=Proof.PORT, proof_note="verify_plocks_p2 under the port; EDIT EVENTS migration: software only, hardware pending; shared EVENTS migration is software-only, not hardware-tested",
    doc="Page-2 parameter locks (PLOCKS P2) and page-2 scene locks (SCENES P2), stock effects.",
    modules=("SCENES P2", "STORE", "EVENTS", "PLOCKS P2",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
