"""AUTO's references: samples on the user's disk (never committed) and the zones the user named.

Each reference: the sample, how its slices are found (its .ot, or kitmaker's cut at silences), and the
zone of every slice the user named (None: not named, any zone is accepted). The firmware AUTO and the
host's are the same code (autokit.c); verify_autokit.py --refs scores it on every reference found.
"""
import pathlib

DRUMS = pathlib.Path("/home/djib/Musique/SAMPLES/DRUMS_LOOPS")

REFS = {
    # the user's 93 BPM two-bar loop, 16 grid slices (its .ot); the hand analysis of phase 3 (5 Nov 2026):
    # half-hits and fills are sounds too, so only the clear slices are named
    "storm": dict(
        wav=DRUMS / "STORM_Orage et pluie 3 (ID 2717)_LS.wav", slices="ot",
        zones={1: "KICK", 6: "KICK", 9: "KICK", 14: "KICK", 3: "SNARE", 7: "SNARE", 11: "SNARE", 15: "SNARE",
               5: "HATC", 13: "HATC"}),
    # a free acoustic kit, 35 one-shots end to end at 48 kHz; every slice named by the user (8 Nov 2026):
    # chinas, splash, mini and cut crashes as CRASH; hi-hat foot HATC, open foot HATO; rim shot SNARE
    "acoustic": dict(
        wav=DRUMS / "FREE 𝗔𝗖𝗢𝗨𝗦𝗧𝗜𝗖 DRUM KIT  SAMPLE PACK FOR PRODUCERS.wav", slices="cut",
        zones=dict(enumerate(
            "KICK KICK CRASH CRASH TOM TOM RIDE RIDE RIDE RIDE RIDE SNARE SNARE SNARE SNARE SNARE SNARE SNARE "
            "CRASH CRASH CRASH CRASH HATC HATO HATO HATO HATC HATC HATC SNARE SNARE RIDE CRASH CRASH CRASH".split(),
            start=1))),
}
