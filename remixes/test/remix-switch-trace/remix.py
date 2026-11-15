"""remix-switch plus BOOT TRACE: the notes on MIDI OUT say where a boot after
a switch stops."""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="remix-switch-trace",
    family="probes", evidence=(Evidence(Level.EMULATOR, ref="verify_boot_trace",
        note="the notes under the port (verify_boot_trace)"),),
    doc="remix-switch + BOOT TRACE: a MIDI note per boot stage, to find where a boot after a switch hangs.",
    modules=("BRAIN", "REMIX SWITCH", "BOOT TRACE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
