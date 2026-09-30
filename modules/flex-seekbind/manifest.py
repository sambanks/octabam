"""FLEX SEEK BIND -- a same-buffer FLEX re-bind tells the DSP "seek", not
"new note".

The bind (0x4000f450) decides at its tail whether a re-bind is the same
sample (return 0) or a new one (return 0x100) from its slot/type/generation
verdict (sp@55) and a position compare against a settings field
(0x4000f8cc..0x4000f8ea). On a recorder-buffer voice re-trigged every bar
the verdict holds and the compare fails, so every bar is a new note and the
DSP restarts the voice (a chirp, then hash at 140 % of the signal over 300
samples). This cave, hooked on the verdict test, takes the same-sample
continuation with result 1 whenever the verdict holds and the stock
"different" path otherwise. The position reset and everything else stay
stock. On hardware as OCTABAM81/82/83 (modules/recorder-hold/README.md, "The loop click").
"""

from remix.schema import Category, Proof, CavePatch, Kind, Module

HOOK = 0x4000f8cc
HOOK_STOCK = bytes.fromhex("4a2f0037" "6718")       # tstb (55,sp) / beqs 0x4000f8ea

MODULE = Module(
    name="flex-seekbind",
    key="FLEX SEEK BIND",
    kind=Kind.CF_PATCH,
    category=Category.FIXES, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="OCTABAM83, 12 Sep 2026",
    doc="ColdFire cave: a same-slot/type/generation FLEX re-bind takes the bind's "
        "same-sample path (DSP seek) instead of becoming a new note.",
    cf_patches=(
        CavePatch(
            label="seek-bind cave",
            # Pinned in the tail of the 338 B zero run 0x400c45b0..0x400c4702
            # (docs/contributing/PLACEMENT.md), after SPECTRUM's SHPE formatter (89 B
            # at 0x400c45b0): seek-bind 0x400c460c, counter 0x400c4624, spacing
            # 0x400c4634..0x400c46c6. The floating clone window has no room
            # beside the rig's clones and label formatters. 28 Sep 2026.
            cave_addr=0x400c460c,
            pinned=bytes.fromhex("4a2f003b670a7001588f4ef94000f8ec588f4ef94000f8ea"),
            source="modules/flex-seekbind/seekbind.s",
            hook_addr=HOOK,
            hook_stock=HOOK_STOCK,
            report_note=" (same-sample re-bind -> seek path)",
        ),
    ),
)
