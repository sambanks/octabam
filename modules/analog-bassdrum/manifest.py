"""Analog BD: native source synthesis, one machine with 808/909 models."""
from remix.schema import ArenaReserve, Category, Detour, Gate, Kind, Linked, Module, Evidence, Level, SymbolRef
H=bytes.fromhex


MODULE=Module(
    name="analog-bassdrum", key="ANALOG BD", kind=Kind.CF_PATCH,
    # the pre-boot DSP uploads' destinations and stages
    # (tools/build/ab_image.py PRE: 0x40b00000..0x40bc0000 + 0x40000)
    arena_reserves=(ArenaReserve("pre-boot upload scratch", 0x40B00000, 0x100000),),
    requires=("MEMORY", "MACHINES"),     # the machine row is MACHINES's (a client: CLIENTS there)
    category=Category.MACHINES, author="repeat98", author_url="https://github.com/repeat98",
    doc="Analog BD track machine: switchable 808/909 circuit-informed synthesis.",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); source/AMP/main on both cores and engine-"
             "browser/hidden-control gates"),),
    pressure_blocker="DSP source engines are outside the FX pressure pricer; "
                     "see modules/analog-bassdrum/CPU.md and benchmark_analog_bd.py",
    dsp_source="tools/build/ab_image.py",
    linked=(
        Linked("abmachine", "modules/analog-bassdrum/machine.s", dram=True),
        Linked("abcontrol", "modules/analog-bassdrum/control.s", dram=True),
        Linked("abengine", "modules/analog-bassdrum/engine.s", dram=True),
    ),
    symbol_refs=(SymbolRef(0x400d6438,0x40004008,"abcontrol","ab_render",
                           note="FLEX renderer: signed AB tracks synthesize source samples"),
                 SymbolRef(0x400ce10e,0,"abcontrol","ab_engine_left",
                           note="LEFT from Analog BD engine pool to machine chooser"),
                 SymbolRef(0x400cf714,0x4007909c,"abcontrol","ab_engine_right",
                           note="RIGHT on Analog BD enters its engine pool")),
    detours=(
        Detour(0x40077B5C, H("7c01bc80650e"), "abmachine", "ab_pool_title",
               "show the stock right-chevron for the Analog BD engine pool"),
        Detour(0x4006D784, H("4fefffe848d73c0c"), "abmachine", "ab_list_draw",
               "draw the Analog BD engine browser in the stock pool layout", pad_to=8),
        Detour(0x400791E4, H("2f0a4ab9460e70e0"), "abmachine", "ab_pool_open",
               "track double-tap opens the Analog BD engine list", pad_to=8),
    ),
    gates=(Gate("tools/verify/verify_analog_bassdrum.py", remix_arg=False),
           Gate("tools/harness/bd909.py", remix_arg=False),
           Gate("tools/harness/bd808.py", remix_arg=False),
           Gate("tools/harness/verify_analog_bd_exact.py", remix_arg=False),
           Gate("tools/harness/verify_analog_bd_levels.py", remix_arg=False),
           Gate("tools/harness/verify_analog_bd_reverbs.py", remix_arg=False, stage="image"),
           Gate("tools/verify/verify_analog_bassdrum_cf.py", remix_arg=False,
                venv=True, stage="image"),
           Gate("tools/verify/verify_analog_bassdrum_port.py", remix_arg=False,
                stage="image"),
           Gate("tools/verify/verify_analog_bassdrum_ui.py", remix_arg=False,
                stage="image")),
)
