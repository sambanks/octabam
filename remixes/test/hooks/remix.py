"""HOOKS's bridges: MORPH, REC_TRIG_MUTE and REC THRESHOLD in one image, with STORE and the stock effects.

Each pair here claims one stock site; the registry appends HOOKS, which owns both
sites and calls each module's own routine (modules/hooks).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="hooks",
    family="mods", proof=Proof.PORT,
    proof_note="verify_hooks: the bridged chain and table under Unicorn, and this image's sites",
    doc="MORPH, REC_TRIG_MUTE and REC THRESHOLD together (HOOKS bridges the [TRACK] key layer and the status icons) with STORE and the stock effects.",
    # ATA WRITE GUARD: stock's first-sector card write has an IRQ window a timing shift
    # can land a port run in (TRAPS.md trap-first-sector-irq; it hung hooks-free-loop)
    modules=("MORPH", "REC_TRIG_MUTE", "REC THRESHOLD", "STORE", "ATA WRITE GUARD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
