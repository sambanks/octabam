"""DLCOPY -- the demand loader's copier: a frame hook on payload B that moves a block the ColdFire has
staged into the shared window and publishes it (docs/contributing/DEMAND_LOADER.md).
"""
from remix.schema import Category, Claims, DspHook, DspRange, DspSection, Gate, Kind, Module, Proof

MODULE = Module(
    name="dlcopy",
    key="DLCOPY",
    kind=Kind.HYBRID,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.CHECK, proof_note="",
    doc="Frame hook on payload B: copies a staged block into the shared window (demand loader).",
    claims=Claims(dsp_ranges=(
        DspRange("x", 0x2900, 0x1456, "the staging area the ColdFire's host write fills: doorbell, header, 2 words per code word"),
        DspRange("x", 0x3F00, 0x50, "the stub's per-instance flags and saved registers"),
        DspRange("x", 0x3DC0, 0x80, "the reverb guard's per-instance state words (x:$3dc0 + idx) and base cells (x:$3e00 + idx)"),
        DspRange("x", 0x3FD0, 0x1B, "the reverb trampolines' words, the guard's kept registers and the copier's saved b"),
    )),
    dsp=DspSection(
        asm="modules/dlcopy/dlcopy.asm",
        priority=22,
        payloads=frozenset({"B"}),
        hooks=(DspHook({"B": 0x76}, (0x667000, 0x000207), "dlc_start",
                       "frame head, after the host handlers' masks are set: the staged block is copied"),),
    ),
    gates=(Gate("tools/verify/verify_dlstub.py"), Gate("tools/verify/verify_dlwrap.py"), Gate("tools/verify/verify_dlhook.py")),
)
