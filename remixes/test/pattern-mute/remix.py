from remix.schema import Proof, Remix

REMIX = Remix(
    name="pattern-mute",
    family="test",
    proof=Proof.CHECK,
    proof_note="PATTERN MUTE smoke",
    doc="smoke: PATTERN MUTE alone",
    modules=("PATTERN MUTE",),
    fallback="NONE",
)
