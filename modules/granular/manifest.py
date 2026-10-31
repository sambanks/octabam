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
    proof=Proof.CHECK,
    proof_note=(
        "Granular image built and booted to the RTOS handoff under the ColdFire port; "
        "synthetic-source gate runs under Unicorn; real-firmware port run with a generated project (controls, retrigger, MIDI Stop, stock passthrough); full make check and hardware testing "
        "not run."
    ),
    linked=(
        Linked(
            "gr_engine",
            "modules/granular/granular.s",
            dram=True,
            boot_mutable=(
                ("gr_state", 8 * (13 * 4 + 4 * 8 * 4)),
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
    ),
    gates=(
        Gate("tools/verify/verify_granular.py", remix_arg=False, venv=True),
    ),
)
