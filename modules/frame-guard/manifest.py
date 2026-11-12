"""FRAME GUARD -- a frame interrupt that enters 110-190 us late waits until
it is 190 us late, so the DSP skips one frame instead of stalling.

One detour on the frame interrupt's entry 0x4000aad0 (LOAD METER's and BOOT
TRACE's site: beside either, HOOKS owns it and calls fg_in built to return,
before LOAD METER's entry so the demand loader's pump keeps its place after
the wait). guard.s has the measurements and the arithmetic.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex


def _hooks_inc(modules, remix):
    """HOOKS's flags (modules/hooks): beside another module on the frame
    interrupt's entry, the routine returns and HOOKS replays the prologue."""
    from remix import hooks_flags
    return hooks_flags.inc("FRAME GUARD", modules)


MODULE = Module(
    name="frame-guard", key="FRAME GUARD", kind=Kind.CF_PATCH,
    category=Category.FIXES, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE,
    proof_note="Sam's MKII, 12 Nov 2026, octabam with a 20-channel USB capture open: 16 first STARTs and 96 program "
               "changes without a stall (1 in 8 and 1 in 27 without it); as test code inside LOAD METER's entry",
    doc="A late frame interrupt waits out the window in which the DSP's frame exchange stalls at START "
        "and at a program change.",
    linked=(Linked("frameguard", "modules/frame-guard/guard.s", cpu="5475", dram=True, include=_hooks_inc),),
    detours=(
        Detour(0x4000AAD0, H("4fefff0448d77fff"), "frameguard", "fg_in",
               "the frame interrupt's entry: its prologue replayed, then the wait when it entered late", pad_to=8),
    ),
    gates=(Gate("tools/verify/verify_frame_guard.py", remix_arg=False, venv=True),),
)
