"""<Module name> -- one line on what it changes in the firmware.

THE SKELETON OF A COLDFIRE MODULE: code the build links and places for
you, reached from stock code by detours you name by SYMBOL. Copy this
directory to modules/<yourname>/ and edit. Directories starting with `_`
are skipped by the registry, so this file is never built.

For a finished one small enough to read in one sitting, see
modules/hello-dram/ (one unit, no hooks -- the loader canary); for the
real thing, modules/midi-scenes/ (seven units built from the author's own
repository as a submodule, 35 detours, two pokes). docs/remixer/MODULES.md
"Declaring a ColdFire module" carries the reasoning these comments only
summarise; docs/remixer/PLACEMENT.md says where the bytes go and why.

Say here what the module IS, which stock routines it changes, what was
measured and what is inferred. Then delete every comment below that you
have answered -- a template's leftovers read as fact to the next person.
"""

from remix.schema import Detour, Kind, Linked, Module, Poke

MODULE = Module(
    # `name` MUST equal the directory name. `key` is the build identifier and
    # appears in the build report, which other tools parse -- so it is API.
    name="_template_cf",
    key="TEMPLATE CF",
    kind=Kind.CF_PATCH,             # no DSP code, no chooser row
    doc="One line, shown by `make modules`.",

    # ---- the code: GNU-as units, linked by the build ----------------------
    # ORDER IS LINK ORDER: a unit may reference symbols of units before it.
    # `dram=True` puts the unit in the platform runtime (linked with every
    # other DRAM unit in the remix, appended behind the loader, depacked at
    # boot into the never-cleared window -- tens of KB available; where
    # anything bigger than a few hundred bytes belongs). `dram=False` places
    # it in one of the OS image's free zero runs (~8 KB, shared by everyone)
    # for code that must be ROM-resident. Sources are `.s` for m68k-elf-as;
    # `cpu="5407"` and "5475" encode this ISA subset identically.
    linked=(
        Linked("unit", "modules/_template_cf/unit.s", dram=True),
        # Building from someone else's repository? Add it as a submodule
        # under modules/<name>/upstream and point `source` into it; the
        # sources stay theirs and an update is a submodule bump.
        # `reference=(addr, sha256)` re-links the unit at the AUTHOR'S own
        # address on every build and compares, so a drift from the bytes
        # they ratified fails loudly.
    ),

    # ---- how stock code reaches it: detours, wired by symbol --------------
    # `site` is a stock instruction; `expect` its bytes (whole instructions,
    # asserted before anything is written -- a site that has moved stops
    # the build). `kind`: "jmp" for a stub that replays what it displaced
    # and jumps on (the common case), "jsr" for a callable that returns,
    # "lea" to rewrite a six-byte `lea abs.l,An`'s operand. `pad_to` nops
    # the rest of a displaced span longer than six bytes.
    detours=(
        # Detour(0x400xxxxx, bytes.fromhex("..."), "unit", "my_hook",
        #        "what this hook is for", kind="jsr", pad_to=None),
    ),

    # ---- plain asserted rewrites ------------------------------------------
    pokes=(
        # Poke(0x400xxxxx, expect=bytes.fromhex("6612"),
        #      write=bytes.fromhex("6012"), note="bne -> bra: never re-apply"),
    ),

    # A stock pointer array that needs more entries: TableGrow relocates it
    # into free space with your symbols appended and repoints every
    # reference (busscreen's menu-state table is the worked example).
    # tables=(TableGrow("...", old=0x400xxxxx, count=16,
    #                   symbols=(("unit", "my_row"),),
    #                   refs=((0x400xxxxx, 0x400xxxxx),)),),
)
