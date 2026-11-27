"""stock effects with TRIG MUTE: mute a single trig without deleting it."""

from remix.schema import Proof, Remix
from remix import stock

REMIX = Remix(
    name="trig-mute",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with TRIG MUTE: mute a single trig without deleting it.",
    modules=("TRIG MUTE",
             *stock.EFFECTS),
    fallback="NONE",
)
