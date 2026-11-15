"""Stock effects plus BUFFER SAVER (and ATA WRITE GUARD): SAVE PROJECT offers to save unsaved recorder buffers, no BRAIN.

ATA WRITE GUARD, as the official remixes carry it: without it the port
hung in verify_buffer_saver's project saves when a build shifted the
boot timing (the stock first-sector race, modules/ata-write-guard/README.md).
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="buffer-saver",
    family="mods", evidence=(Evidence(Level.UNIT, unit="MKII", who="Chupitnik", date="2026-10-16",
        note="15-16 Oct 2026, AUTOSAVE1 and AUTOSAVE2 from the card (the module under its first name): after a "
             "take FUNC + PROJ and PROJECT > SAVE ask SAVE SAMPLES?; YES saves R<n>-YYMMDD-HHMM and assigns it to "
             "its buffer, two buffers in one save, an immediate re-save does not ask, a reload brings the takes "
             "back, NO saves as stock"),),
    doc="stock effects with SAVE PROJECT offering to save the recorder buffers' unsaved takes, each assigned to itself.",
    modules=("BUFFER SAVER", "ATA WRITE GUARD", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
