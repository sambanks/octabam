"""Stock effects plus SRC3 KEY: [MIDI] in the audio editor records SRC3 on the MKI"""

from remix.schema import Proof, Remix
from remix import stock

REMIX = Remix(
    name="src3-key",
    family="mods", proof=Proof.CHECK, proof_note="verify_src3_key under the port; the module itself on 8thmyth's MKI in test/octabam-lazy-chop (OCTABAMHC, 14 Nov 2026)",
    doc="stock effects with SRC3 KEY ([MIDI] in the audio editor records SRC3 on the MKI).",
    modules=("SRC3 KEY", "BUFFER SAVER", "ATA WRITE GUARD",
             *stock.EFFECTS),
    fallback="NONE",
)
