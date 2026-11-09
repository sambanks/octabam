"""WAVE (ColdFire) alone: the 4-voice wavetable machine with the stock effects."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="wavecf",
    family="mods", proof=Proof.PORT,
    proof_note="built; the engine and note layer under Unicorn (modules/wavecf/test_wavecf.py); the machine's UI and sound under the port (verify_wavecf_ui.py, verify_wavecf_port.py); not flashed",
    doc="the WAVE machine (a 4-voice wavetable voice on the ColdFire) with the stock effects.",
    modules=("WAVE CF", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
