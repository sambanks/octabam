"""cxosc -- CX OSC complex-oscillator machine on the stock effects.

Milestone 1 gate: the local CX OSC module alone (conflicts with SYNTH
MACHINE). Stock FX chooser.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="cxosc",
    family="mods", proof=Proof.CHECK,
    proof_note="port check: marker-less machine list; PLAYBACK PTCH RATO INDX FINE FOLD MIX; SETUP CMOR/MMOR/DEC/SYMM/FDBK",
    doc="CX OSC (machine list, no marker): PLAYBACK PTCH RATO INDX FINE FOLD MIX; SETUP CMOR MMOR DEC SYMM FDBK; stock FX.",
    modules=("CX OSC",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
