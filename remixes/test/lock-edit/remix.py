"""Stock effects plus LOCK EDIT: [TRIG]+[BANK] in grid recording opens the audio editor on the step's sample and slice"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="lock-edit",
    family="mods", proof=Proof.CHECK, proof_note="verify_lock_edit under the port; the module itself on 8thmyth's MKI in test/octabam-lazy-chop (OCTABAMHC, 14 Nov 2026)",
    doc="stock effects with LOCK EDIT ([TRIG]+[BANK] in grid recording opens the audio editor on the step's sample and slice).",
    modules=("LOCK EDIT",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
