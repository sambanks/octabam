"""FREE LOOP beside REC_TRIG_MUTE and REC THRESHOLD: HOOKS chains the status icons, the icon drawer and the step handler's recorder-trig test."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="hooks-free-loop",
    family="mods", proof=Proof.PORT,
    proof_note="verify_hooks: the bridged sites in this image and the chains under Unicorn; verify_free_loop under the port",
    doc="FREE LOOP beside REC_TRIG_MUTE and REC THRESHOLD: HOOKS chains the status icons, the icon drawer and the step handler's recorder-trig test.",
    modules=("STORE", "RLEN PLEN", "FREE LOOP", "REC_TRIG_MUTE", "REC THRESHOLD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
