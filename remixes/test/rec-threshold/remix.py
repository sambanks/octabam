"""Stock effects plus REC THRESHOLD alone: TRIG THR with LEV and IN on RECORDING SETUP 2, no BRAIN."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="rec-threshold",
    family="mods", proof=Proof.HARDWARE, proof_note="Chupitnik's MKII, 11-13 Oct 2026, THR1 to THR9 from the card: armed with TRACK 1 + REC AB, silence never records, the input starts the take, a second press cancels, LEV and IN on RECORDING SETUP 2, TRIG moved off THR while armed drops the arm and the blink, an armed track's icon blinks, armed inside RECORDING SETUP 1 it records; THR9 is this code",
    doc="stock effects with the threshold-armed recorder TRIG THR, its LEV and an IN meter: the image for a unit.",
    # ATA WRITE GUARD: stock's first-sector card write has an IRQ window a timing shift
    # can land a port run in (TRAPS.md trap-first-sector-irq; it hung hooks-free-loop)
    modules=("REC THRESHOLD", "ATA WRITE GUARD", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
