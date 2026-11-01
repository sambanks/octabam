"""Four-grain FLEX source engine using the stock sample pool."""
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof, SymbolRef

MODULE = Module(
    name="granular",
    key="GRANULAR",
    kind=Kind.CF_PATCH,
    requires=("MEMORY",),
    category=Category.MACHINES,
    author="sambanks/octabam",
    author_url="https://github.com/sambanks/octabam",
    doc="Four-grain sample source on FLEX tracks whose sample name begins GRAN.",
    proof=Proof.PORT,
    proof_note=(
        "Linked ABI/arithmetic and serialized initialization, actual DRAM boot, and "
        "generated-project firmware audio are port-gated: musical pitch, true mono/stereo "
        "16/24-bit pools, pitch locks/scenes/LFO, retrigger/Stop, stock identity and "
        "clean four-reference MAIN output. Not hardware-qualified; no full make check."
    ),
    linked=(
        Linked(
            "gr_engine",
            "modules/granular/granular.s",
            dram=True,
            boot_mutable=(
                ("gr_state", 8 * (13 * 4 + 4 * 9 * 4)),
                ("gr_page_descriptor", 0x192),
                ("gr_page_ready", 4),
            ),
        ),
        Linked("gr_hooks", "modules/granular/hooks.s", dram=True),
    ),
    symbol_refs=(
        SymbolRef(
            0x400D6438,
            0x40004008,
            "gr_engine",
            "gr_render",
            note="FLEX source renderer: GRAN*-named samples use the granular engine",
        ),
    ),
    detours=(
        Detour(
            0x40031ECE,
            bytes.fromhex("20300c006002"),
            "gr_hooks",
            "gr_page",
            "FLEX playback page resolver: clone and relabel the controls for GRAN* samples",
            kind="jmp",
        ),
    ),
    conflicts=(
        ("SYNTH MACHINE", "both replace the FLEX renderer and playback-page resolver"),
        ("OCTA303", "both replace the FLEX renderer and playback-page resolver"),
        ("ANALOG BD", "both replace the FLEX renderer"),
        ("BLACKPYRAMIDS_303", "both replace the FLEX renderer and playback-page resolver"),
        ("CX OSC", "both replace the FLEX renderer and playback-page resolver"),
    ),
    gates=(
        Gate("tools/verify/verify_granular.py", remix_arg=False, venv=True),
        Gate("tools/verify/verify_granular_port.py", stage="image", venv=True),
    ),
)
