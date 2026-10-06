"""input-hold -- INPUT HOLD alone, for its gates."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="input-hold",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="INPUT HOLD alone: inputs keep their levels across a project change.",
    modules=("INPUT HOLD",),
    fallback="NONE",
)
