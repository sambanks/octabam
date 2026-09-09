"""FLEX seek-bind, counter half -- pair with FLEX SEEK BIND (RTOS_FORK 10.48
lever B). On a same-sample re-bind leave the per-voice counter (+0x90) alone
so the frame builder does not re-send the voice as new; the +0x98 store is
always replayed. Hook 0x4000f834 (addql #1,(144,a2) / movel a0,(152,a2)).
Unflashed."""

from remix.schema import CavePatch, Kind, Module

MODULE = Module(
    name="flex-seekbind-ctr",
    key="FLEX SEEK BIND CTR",
    kind=Kind.CF_PATCH,
    doc="ColdFire cave: on a same-sample FLEX re-bind, do not bump the voice's "
        "per-bind counter (pairs with FLEX SEEK BIND).",
    cf_patches=(
        CavePatch(
            label="seek-bind counter cave",
            cave_addr=None,
            pinned=bytes.fromhex("4a2f003b660452aa0090254800984e75"),
            source="modules/flex-seekbind-ctr/seekbind_ctr.s",
            hook_addr=0x4000f834,
            hook_stock=bytes.fromhex("52aa0090" "25480098"),
            report_note=" (same-sample re-bind keeps +0x90)",
        ),
    ),
)
