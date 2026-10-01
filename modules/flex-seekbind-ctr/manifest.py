"""FLEX SEEK BIND CTR -- pairs with FLEX SEEK BIND: on a same-sample re-bind
leave the per-voice counter (+0x90) alone so the frame builder does not
re-send the voice as new; the +0x98 store is always replayed. Hook
0x4000f834 (addql #1,(144,a2) / movel a0,(152,a2)). Removes the
+/-1.5-sample seam. On hardware as OCTABAM82/83.
"""

from remix.schema import Category, Proof, CavePatch, Kind, Module

MODULE = Module(
    name="flex-seekbind-ctr",
    key="FLEX SEEK BIND CTR",
    kind=Kind.CF_PATCH,
    category=Category.FIXES, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="OCTABAM83, 12 Sep 2026",
    doc="ColdFire cave: on a same-sample FLEX re-bind, do not bump the voice's "
        "per-bind counter (pairs with FLEX SEEK BIND).",
    cf_patches=(
        CavePatch(
            label="seek-bind counter cave",
            # Pinned in the tail of the 338 B zero run 0x400c45b0..0x400c4702
            # (docs/contributing/PLACEMENT.md), after SPECTRUM's SHPE formatter (89 B
            # at 0x400c45b0): seek-bind 0x400c460c, counter 0x400c4624, spacing
            # 0x400c4634..0x400c46c6. The floating clone window has no room
            # beside the rig's clones and label formatters. 28 Sep 2026.
            cave_addr=0x400c4624,
            pinned=bytes.fromhex("4a2f003b660452aa0090254800984e75"),
            source="modules/flex-seekbind-ctr/seekbind_ctr.s",
            hook_addr=0x4000f834,
            hook_stock=bytes.fromhex("52aa0090" "25480098"),
            report_note=" (same-sample re-bind keeps +0x90)",
        ),
    ),
)
