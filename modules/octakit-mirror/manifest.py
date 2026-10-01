"""OCTAKIT MIRROR -- page CLEAR and PASTE on an Octakit image without the
VEC:04 halt.

Octakit's load path stages her Kit into the working part and leaves stock's
SRAM mirror of it as the file had it; her page-clipboard check requires the
two byte-equal and halts (`illegal`, gk_page_clipboard_fatal) on every
page-key + CLEAR (docs/contributing/FAILURE_MODES.md). This brings the mirror
level with the working part just before her CLEAR/PASTE wrapper runs, as a
stock edit would have left it. Her runtime is not touched: the fix sits at a
stock site she does not claim and reads her two layer records at run time.

Added to every remix that carries OCTAKIT (tools/remix/registry.py), as OS
SWITCH is to every remix; `requires` refuses it without her. When Octakit's
load path writes the mirror itself upstream, this module goes.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex

MODULE = Module(
    name="octakit-mirror",
    key="OCTAKIT MIRROR",
    kind=Kind.CF_PATCH,
    category=Category.FIXES, author="sanderlegit", author_url="https://github.com/sanderlegit",
    proof=Proof.HARDWARE,
    proof_note="an MKII, 30 Sep 2026 (RIGPF4BP, bottleservice-pf): page-key + CLEAR works where "
               "RIGPF3BP halted with VEC:04; `verify_octakit_mirror` (a control without it halts)",
    doc="Octakit images: page-key + CLEAR/PASTE no longer halt (VEC:04); stock's SRAM part mirror "
        "is synced with the working part before her wrapper runs.",
    requires=("OCTAKIT",),
    linked=(Linked("octakit_mirror", "modules/octakit-mirror/mirror.s", dram=True),),
    detours=(
        Detour(0x4003191C, H("2f042f024e90"), "octakit_mirror", "osm_dispatch",
               "the input layer's key dispatch: before Octakit's page CLEAR/PASTE wrapper, "
               "the current part's SRAM mirror is synced with its working bytes"),
    ),
    # needs a project Octakit has staged a Kit into (kits3a/kits3b): it runs
    # a control build without this module first and SKIPs when that does not
    # halt, rather than pass on a project that cannot show the fault
    gates=(Gate("tools/verify/verify_octakit_mirror.py", venv=True),),
)
