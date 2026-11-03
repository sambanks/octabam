"""REC CS1 SKIP -- the recorder's control-record update (stock 0x4000432c,
called from the write path about 1.5 times a recording track a frame) with
its CS1 writes skipped when CS1 already holds the value. CS1 costs about
0.5 us an access on a MKII, and in steady play almost every one of the
routine's six writes stores the value already there. [r+300] and [r+308] are
compared with the values the routine reads anyway; [r+276], [r+280],
[r+296].b and [r+304] with a copy in DRAM that one CS1 read a call, in turn,
keeps honest. skip.s has the routine and the argument; README.md what was
measured.
"""
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex
U = "rec_cs1_skip"

MODULE = Module(
    name="rec-cs1-skip",
    key="REC CS1 SKIP",
    kind=Kind.CF_PATCH,
    category=Category.FIXES, author="bryantysinger", author_url="https://github.com/bryantysinger",
    proof=Proof.HARDWARE,
    proof_note="Bryan T's MKII, test builds recording up to eight tracks at once (1-2 Nov 2026); "
               "verify_rec_cs1_skip against stock's routine under unicorn; under the port, a project "
               "recording through pattern changes, a stop and a start leaves all of CS1 as stock does",
    doc="The recorder's per-frame control-record update without its redundant CS1 writes: less ColdFire "
        "time per recording track.",
    linked=(Linked(U, "modules/rec-cs1-skip/skip.s", cpu="5475", dram=True),),
    detours=(
        Detour(0x4000432c, H("2f032f02222f000c"), U, "rcs_update",
               "the recorder control-record update: the whole routine, CS1 writes skipped when unchanged",
               pad_to=8),
    ),
    gates=(Gate("tools/verify/verify_rec_cs1_skip.py", remix_arg=False, venv=True),),
)
