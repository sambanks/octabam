"""BROWSE PATH GUARD -- the sample browser's path builders stop at their
260-byte buffers. A file whose full path passed 259 characters overwrote
the browser's current folder, and the browser stopped opening until a power
cycle (#1258). guard.s has the routines; three stock address operands are
pointed at them.
"""
from remix.schema import Category, Evidence, Gate, Kind, Level, Linked, Module, SymbolRef

U = "browse_path_guard"

MODULE = Module(
    name="browse-path-guard",
    key="BROWSE PATH GUARD",
    kind=Kind.CF_PATCH,
    category=Category.FIXES, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.EMULATOR),),
    doc="The sample browser no longer breaks on a file whose path is longer than the card allows: the file "
        "shows ERR and the browser keeps working.",
    linked=(Linked(U, "modules/browse-path-guard/guard.s", cpu="5475", dram=True),),
    symbol_refs=(
        SymbolRef(0x4006A59A, 0x40013F94, U, "bpg_cat",
                  "the browser's folder + '/' + name into 0x460e48f0: strcat, bounded at 260 bytes"),
        SymbolRef(0x4006A7E0, 0x40013A08, U, "bpg_join",
                  "the file row's path into 0x460e4afc (the next buffer is the current folder): sprintf, bounded"),
        SymbolRef(0x4006A8A0, 0x40013A08, U, "bpg_join",
                  "the cursor file's path into 0x460e49f8: sprintf, bounded"),
    ),
    gates=(Gate("tools/verify/verify_browse_path_guard.py", stage="image", venv=True),),
)
