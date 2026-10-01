"""bottleservice-ret -- bottleservice-rec-plen plus RETURNS (stage A: the reverb return).

T8's FX2 is RETURNS: VRB, the reverb's return level, into T8's input with
MASTER TRACK on (T8's FX1 and fader process it) or into MAIN with it off;
T5 keeps its own sound only. docs/proposals/RETURNS.md.

RETURNS is on the FX2 chooser beside SEND (it runs on T8 only; on T5-T7 it
passes audio untouched and on T1-T4 its id is the payload's null stub), and
MODE DEFAULTS is back: its unit runs from DRAM, and the one-word branches
(`bra <label`, AGENTS.md) gave payload A the words Character KEY took.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="bottleservice-ret",
    family="rig", proof=Proof.HARDWARE, proof_note="an MKII, BSRET3, 29 Sep 2026",
    doc="bottleservice-rec-plen + RETURNS: the reverb return on T8's FX2 (VRB), into T8's input or MAIN, not onto T5.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE", "USB CROSSBAR", "USB AUDIO IN CD",
             "OCTAKIT", "SCENES KITS",
             "SCENES P2", "SCENES P2 KITS",
             "FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING", "RLEN PLEN",
             "RETURNS", "MODE DEFAULTS", "HOST LOCK"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
