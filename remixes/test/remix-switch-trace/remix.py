"""remix-switch plus BOOT TRACE: the notes on MIDI OUT say where a boot after
a switch stops."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="remix-switch-trace",
    family="probes", proof=Proof.PORT, proof_note="the notes under the port (verify_boottrace)",
    doc="remix-switch + BOOT TRACE: a MIDI note per boot stage, to find where a boot after a switch hangs.",
    modules=("BRAIN", "REMIX SWITCH", "BOOT TRACE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
