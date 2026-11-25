"""ARR ROW CAP -- the arranger's row insert at END OF ARR. refuses past 256
rows (ROW LIMIT REACHED), as stock's insert elsewhere in the list does.
Stock's append has no check, and the 257th row was written over the next
arrangement's name and row count, then saved there (#1257). cap.s has the
routine.
"""
from remix.schema import Category, Detour, Evidence, Gate, Kind, Level, Linked, Module

H = bytes.fromhex
U = "arr_row_cap"

MODULE = Module(
    name="arr-row-cap",
    key="ARR ROW CAP",
    kind=Kind.CF_PATCH,
    category=Category.FIXES, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.EMULATOR),),
    doc="The arranger stops at 256 rows when you add a row at END OF ARR., instead of writing a 257th row over "
        "the next arrangement.",
    linked=(Linked(U, "modules/arr-row-cap/cap.s", cpu="5475", dram=True),),
    detours=(
        Detour(0x4009E50C, H("71c0b6806642"), U, "arc_insert",
               "the arranger's row insert, append path: the middle path's 256-row check first"),
    ),
    gates=(Gate("tools/verify/verify_arr_row_cap.py", stage="image"),),
)
