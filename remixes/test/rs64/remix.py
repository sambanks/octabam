"""remix-switch in a 64-id image: REMIX SWITCH's DSP park and re-upload across the grown payloads, with BBD on id 0x25."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="rs64", family="probes", proof=Proof.PORT, proof_note="the chainload and the DSP re-upload under the port in the 64-id layout (verify_remix_switch)",
    doc="remix-switch with id_space=64 and BBD on FX2 id 0x25 in the shared window: the gate for REMIX SWITCH's DSP upload in a grown image.",
    modules=("BRAIN", "REMIX SWITCH", "BBD", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE", id_space=64, ids={"BBD": 0x25},
    window=(("BBD", 0x35000),),
)
