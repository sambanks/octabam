"""LAZY CHOP TEMPO -- after LAZY CHOP's YES, the tempo the chops point to.

LAZY CHOP's slice-count popup comes first, as before; when it ends a second
popup says the tempo: "BPM 115 (58)". The first number is the reading the
chops support best; the bracket holds the next one, a 4:3 / 3:2 neighbour
that fits as plainly (with a dot when it is the dotted / triplet reading of
a 3:2), else half or double time. It stays until the next key, and that key
still does its job. Nothing is written to the sample.

The reading is tools/hw/chop_tempo.py's in whole numbers
(tools/hw/chop_tempo_int.py): the gaps between the slices scored against
every tempo 60.0..200.0 BPM on a 16th / triplet grid, a prior around 120,
the take's length when it is a loop, and a plainer-neighbour check.
choptempo.s has the detail. It needs LAZY CHOP (the hook is LAZY CHOP's,
under LC_TEMPO, built when this module is selected).
"""
import math

from remix.schema import Category, Detour, Evidence, Gate, Kind, Level, Linked, Module

# The UI task's 1/60 s tick 0x40056c28: `move.l 0x460d1e6c,%d0 ; beq.s ; subq.l #1,%d0 ;
# move.l %d0,0x460d1e6c ; bne.s rts ; bra close (0x40056bec)`. RELOAD_FROM_PROJECT and FREE LOOP detour
# the read at 0x40056c28 and go on at 0x40056c2e (modules/hooks); this module takes the decrement and
# the store at 0x40056c30 (8 bytes), which run only while a popup is up.
TICK_DEC = 0x40056C30

Q = 16384
C_LO, C_HI, C_STEP = 6000, 20000, 10


def ct_inc(modules, remix):
    """remix.inc: the cos, prior and loop-agreement tables, as tools/hw/chop_tempo_int.py builds them."""
    cos = [round(Q * math.cos(2 * math.pi * i / 1024)) for i in range(1024)]
    prior = [round(Q * math.exp(-0.5 * (math.log((C_LO + i * C_STEP) / 100 / 120.0) / 0.5) ** 2))
             for i in range((C_HI - C_LO) // C_STEP + 1)]
    la = [round(Q * (0.15 + 0.85 * math.exp(-0.5 * ((e / Q) / 0.012) ** 2))) for e in range(1024)]
    out = ["| remix.inc -- LAZY CHOP TEMPO's tables (modules/chop-tempo/manifest.py)", "        .data",
           "        .balign 4"]
    for name, vals in (("ct_cos", cos), ("ct_prior_t", prior), ("ct_la_t", la)):
        out.append(f"{name}:")
        for i in range(0, len(vals), 16):
            out.append("        .short  " + ", ".join(str(v) for v in vals[i:i + 16]))
        out.append("        .balign 4")
    return "\n".join(out) + "\n"


MODULE = Module(
    name="chop-tempo",
    key="LAZY CHOP TEMPO",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES, author="8thmyth", author_url="https://github.com/8thmyth",
    evidence=(Evidence(Level.EMULATOR, who="8thmyth", date="2026-11-17", ref="tools/verify/verify_chop_tempo.py",
                       note="46 of 8thmyth's chops give tools/hw/chop_tempo_int.py's line under the port; not yet on a unit"),),
    requires=("LAZY CHOP",),
    doc="After LAZY CHOP's YES and its slice-count popup, a popup with the tempo the chops point to (BPM 115 (58)) until the next key.",
    linked=(Linked("choptempo", "modules/chop-tempo/choptempo.s", dram=True, include=ct_inc),),
    detours=(
        Detour(TICK_DEC, bytes.fromhex("538023c0460d1e6c"), "choptempo", "ct_tick",
               "UI task's popup countdown: the tempo popup after LAZY CHOP's count, closed by the next key",
               kind="jsr", pad_to=8),
    ),
    gates=(Gate("tools/verify/verify_chop_tempo.py", venv=True, stage="image"),),
)
