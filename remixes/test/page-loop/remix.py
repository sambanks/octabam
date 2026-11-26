"""stock effects with PAGE LOOP: loop one page of one track, in time."""

from remix.schema import Proof, Remix
from remix import stock

REMIX = Remix(
    name="page-loop",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with PAGE LOOP: loop one page of one track, in time.",
    modules=("PAGE LOOP",
             *stock.EFFECTS),
    fallback="NONE",
)
