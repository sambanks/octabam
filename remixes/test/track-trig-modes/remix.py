from remix.schema import Proof, Remix

REMIX = Remix(
    name="track-trig-modes",
    family="test",
    proof=Proof.PORT,
    proof_note="verify_track_trig_modes",
    doc="smoke: TRACK TRIG MODES alone",
    modules=("TRACK TRIG MODES",),
    fallback="NONE",
)
