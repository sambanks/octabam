"""cxosc -- CX OSC complex-oscillator machine on the stock effects.

Milestone 1 gate: the local CX OSC module alone (conflicts with SYNTH
MACHINE). Stock FX chooser.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="cxosc",
    family="mods", proof=Proof.HARDWARE,
    proof_note=(
        "same module proof: MKII CX 41 (full tip) + CX 28 / VRCS-CX VS; "
        "gate remix for verify_cxosc (PLAYBACK FINE/FOLD/MIX, SETUP morphs, 4 MAX)"
    ),
    doc="CX OSC (machine list, no marker): PLAYBACK PTCH RATO INDX FINE FOLD MIX; SETUP CMOR MMOR DEC SYMM FDBK; stock FX.",
    modules=("CX OSC",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
