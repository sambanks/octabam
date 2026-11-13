"""FREE LOOP beside RELOAD_FROM_PROJECT: HOOKS chains the UI task's tick 0x40056c28 (FREE LOOP, then RELOAD_FROM_PROJECT)."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="hooks-reload",
    family="mods", proof=Proof.PORT,
    proof_note="verify_hooks: the bridged site in this image and the chain under Unicorn",
    doc="FREE LOOP beside RELOAD_FROM_PROJECT: HOOKS chains the UI task's tick 0x40056c28 (FREE LOOP, then RELOAD_FROM_PROJECT).",
    # ATA WRITE GUARD: stock's first-sector card write has an IRQ window a timing shift
    # can land a port run in (TRAPS.md trap-first-sector-irq), as in hooks and hooks-free-loop
    modules=("STORE", "RLEN PLEN", "FREE LOOP", "RELOAD_FROM_PROJECT", "ATA WRITE GUARD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
