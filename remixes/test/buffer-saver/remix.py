"""Stock effects plus BUFFER SAVER alone: SAVE PROJECT offers to save unsaved recorder buffers, no BRAIN."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="buffer-saver",
    family="mods", proof=Proof.HARDWARE, proof_note="Chupitnik's MKII, 15-16 Oct 2026, AUTOSAVE1 and AUTOSAVE2 from the card (the module under its first name): after a take FUNC + PROJ and PROJECT > SAVE ask SAVE SAMPLES?; YES saves R<n>-YYMMDD-HHMM and assigns it to its buffer, two buffers in one save, an immediate re-save does not ask, a reload brings the takes back, NO saves as stock",
    doc="stock effects with SAVE PROJECT offering to save the recorder buffers' unsaved takes, each assigned to itself.",
    modules=("BUFFER SAVER", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
