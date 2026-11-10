"""HOOKS's status_icon bridge: REC THRESHOLD and FREE LOOP in one image, with STORE and the stock effects.

Both replace the track status icon renderer's state-cache load; the registry appends
HOOKS, which owns the site and calls each module's own routine (modules/hooks).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="hooks",
    family="mods", proof=Proof.PORT,
    proof_note="verify_hooks: the bridged chain and table under Unicorn, and this image's sites",
    doc="REC THRESHOLD and FREE LOOP together (HOOKS bridges the status icons) with STORE and the stock effects.",
    # ATA WRITE GUARD: stock's first-sector card write has an IRQ window a timing shift
    # can land a port run in (TRAPS.md trap-first-sector-irq; it hung hooks-free-loop)
    modules=("REC THRESHOLD", "FREE LOOP", "STORE", "RLEN PLEN", "ATA WRITE GUARD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
