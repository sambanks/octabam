"""os-switch plus BOOT TRACE: the notes on MIDI OUT say where a boot after
a switch stops."""

from remix.schema import Proof, Remix

# DARK REV is off the chooser: its words hold OS SWITCH's DSP loader.
REMIX = Remix(
    name="os-switch-trace",
    family="probes", proof=Proof.PORT, proof_note="the notes under the port (verify_boottrace)",
    doc="os-switch + BOOT TRACE: a MIDI note per boot stage, to find where a boot after a switch hangs.",
    modules=("OS SWITCH", "BOOT TRACE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV"),
    fallback="NONE",
)
