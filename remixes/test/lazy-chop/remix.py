"""Stock effects plus LAZY CHOP and BUFFER SAVER: chop a recorder take by tapping the trig keys, save it with its slices.

ATA WRITE GUARD rides along as in remixes/test/buffer-saver.
"""

from remix.schema import Proof, Remix
from remix import stock

REMIX = Remix(
    name="lazy-chop",
    family="mods", proof=Proof.CHECK, proof_note="verify_lazy_chop under the port; the module on 8thmyth's MKI in test/octabam-lazy-chop (OCTABAMHC, 14 Nov 2026)",
    doc="stock effects with LAZY CHOP (tap TRIG 1..16 to slice a take) and BUFFER SAVER.",
    modules=("LAZY CHOP", "BUFFER SAVER", "ATA WRITE GUARD", *stock.EFFECTS),
    fallback="NONE",
)
