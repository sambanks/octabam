"""bottleservice-pf -- bottleservice-ret plus POST FADER.

The bus sends follow each track's fader, mute and solo (modules/post-fader):
DEL/REV x (LEVEL/128)^2 in the DSP-bound record, a muted track sends
nothing. Not flashed.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="bottleservice-pf",
    family="rig", proof=Proof.CHECK, proof_note="make check, 29 Sep 2026; not flashed",
    doc="bottleservice-ret + POST FADER: the bus sends follow each track's fader, mute and solo.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE", "USB CROSSBAR", "USB AUDIO IN CD",
             "OCTAKIT", "SCENES KITS",
             "SCENES P2", "SCENES P2 KITS",
             "FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING", "RLEN PLEN",
             "RETURNS", "POST FADER"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER", "RETURNS"),
    named=("RETURNS",),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
