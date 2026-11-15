"""REMOTE -- event records a host reads from a unit, so a hardware test waits
for the event it caused instead of for a time (tools/hw/ot_events.py).

One detour on the frame interrupt's entry 0x4000aad0 (BOOT TRACE's, FRAME
GUARD's and LOAD METER's site: beside any of them HOOKS owns it and calls
rmt_in built to return, last, so LOAD METER's duration includes it), and
STORE's load and save events as a STORE client. The records go to a ring
the USB module answers 0xc0/0x5a with. remote.s has the record and the cells.
"""

from remix.schema import Category, Detour, Evidence, Gate, Kind, Level, Linked, Module

H = bytes.fromhex


def _hooks_inc(modules, remix):
    """HOOKS's flags (modules/hooks): beside another module on the frame
    interrupt's entry, the routine returns and HOOKS replays the prologue."""
    from remix import hooks_flags
    return hooks_flags.inc("REMOTE", modules)


MODULE = Module(
    name="remote", key="REMOTE", kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT_MEASURED, unit="MKII", who="sambanks", image="N1", date="2026-11-15",
                       commit="95e52aee",
                       note="records, the trace, the card log and COMMAND 1 to 4 read on the unit; ColdFire share "
                            "playing 64.48 % and 64.94 % against 64.85 % without the module; 1 of 6 COMMAND 3 "
                            "boots stopped on the boot screen"),
              Evidence(Level.EMULATOR, ref="verify_remote", date="2026-11-15",
                       note="a project load, a save, a transport start and a program change read back as records "
                            "over 0xc0/0x5a; PEEK, the frame trace and COMMAND 1 to 4"),),
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
