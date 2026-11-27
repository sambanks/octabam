"""stock effects with TRACK TRIG MODE: Hteah's single-mode track trig editing."""

from remix.schema import Proof, Remix
from remix import stock

REMIX = Remix(
    name="track-trig-mode",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with TRACK TRIG MODE: Hteah's single-mode track trig editing.",
    modules=("TRACK TRIG MODE",
             *stock.EFFECTS),
    fallback="NONE",
)
