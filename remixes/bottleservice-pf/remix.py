"""bottleservice-pf -- bottleservice-ret plus POST FADER.

The bus sends follow each track's fader, mute and solo (modules/post-fader):
DEL/REV x (LEVEL/128)^2 in the DSP-bound record, a muted track sends
nothing. RETURNS is on the FX2 chooser (T8 only: a no-op anywhere else) and
MODE DEFAULTS is back. On an MKII as RIGPF7BP (30 Sep 2026).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="bottleservice-pf",
    family="rig", proof=Proof.HARDWARE, proof_note="an MKII, RIGPF7BP, 30 Sep 2026",
    doc="bottleservice-ret + POST FADER: the bus sends follow each track's fader, mute and solo.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE", "USB CROSSBAR", "USB AUDIO IN CD",
             "OCTAKIT", "SCENES KITS",
             "SCENES P2", "SCENES P2 KITS",
             "FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING", "RLEN PLEN",
             "RETURNS", "POST FADER", "MODE DEFAULTS", "HOST LOCK"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
