"""REMOTE -- event records a host reads from a unit, so a hardware test waits
for the event it caused instead of for a time (tools/hw/ot_events.py).

One detour on the frame interrupt's entry 0x4000aad0 (BOOT TRACE's, FRAME
GUARD's and LOAD METER's site: beside any of them HOOKS owns it and calls
rmt_in built to return, last, so LOAD METER's duration includes it), and
STORE's load and save events as a STORE client. The records go to a ring
the USB module answers 0xc0/0x5a with. remote.s has the record and the cells.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex


def _hooks_inc(modules, remix):
    """HOOKS's flags (modules/hooks): beside another module on the frame
    interrupt's entry, the routine returns and HOOKS replays the prologue."""
    from remix import hooks_flags
    return hooks_flags.inc("REMOTE", modules)


MODULE = Module(
    name="remote", key="REMOTE", kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.PORT,
    proof_note="under the port (verify_remote): a project load, a transport start and a program change each read "
               "back as records over 0xc0/0x5a; not run on a unit",
    doc="Project loads, saves, transport, pattern changes and screen redraws as timestamped records a host "
        "reads over USB.",
    requires=("STORE", "USB"),
    linked=(Linked("remote", "modules/remote/remote.s", cpu="5475", dram=True, include=_hooks_inc),),
    detours=(
        Detour(0x4000AAD0, H("4fefff0448d77fff"), "remote", "rmt_in",
               "the frame interrupt's entry: its prologue replayed, then the watched cells compared", pad_to=8),
    ),
    gates=(Gate("tools/verify/verify_remote.py", venv=True, stage="image"),),
)
