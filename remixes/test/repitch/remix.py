"""Stock effects plus the REPITCH TSTR firmware modification."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="repitch",
    # OS SWITCH needs DSP words for its park code (modules/os-switch/
    # dsp_park.asm), and this remix keeps every stock effect, so none are
    # free: it is left out. The image is still a valid switch TARGET (its
    # .OBI boots from any image that carries OS SWITCH).
    os_switch=False,
    family="mods", proof=Proof.HARDWARE, proof_note="repeat98's MKII, 16 Sep 2026 (OCTABAM81)",
    doc="stock effects with variable-speed REPITCH in the TSTR selector.",
    modules=("REPITCH", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
