"""FLEX seek-bind -- a same-buffer FLEX re-bind tells the DSP "seek", not
"new note" (RTOS_FORK 10.48 hypothesis, 10 Sep 2026; unflashed, port gates
in 10.49).

The bind (0x4000f450) decides at its tail whether a re-bind is the same
sample (return 0) or a new one (return 0x100) from its own slot/type/
generation verdict (sp@55) AND a position compare against a settings field
(0x4000f8cc..0x4000f8ea). On a recorder-buffer voice re-trigged every bar the
verdict holds but the compare plausibly fails, so every bar is a new note and
the DSP restarts the voice -- the chirp-then-click of 10.48. This cave, hooked
on the verdict test, takes the same-sample continuation with result 1 whenever
the verdict holds and the stock "different" path otherwise. The position reset
and everything else stay stock.
"""

from remix.schema import CavePatch, Kind, Module

HOOK = 0x4000f8cc
HOOK_STOCK = bytes.fromhex("4a2f0037" "6718")       # tstb (55,sp) / beqs 0x4000f8ea

MODULE = Module(
    name="flex-seekbind",
    key="FLEX SEEK BIND",
    kind=Kind.CF_PATCH,
    doc="ColdFire cave: a same-slot/type/generation FLEX re-bind takes the bind's "
        "same-sample path (DSP seek) instead of becoming a new note.",
    cf_patches=(
        CavePatch(
            label="seek-bind cave",
            cave_addr=None,
            pinned=bytes.fromhex("4a2f003b670a7001588f4ef94000f8ec588f4ef94000f8ea"),
            source="modules/flex-seekbind/seekbind.s",
            hook_addr=HOOK,
            hook_stock=HOOK_STOCK,
            report_note=" (same-sample re-bind -> seek path)",
        ),
    ),
)
