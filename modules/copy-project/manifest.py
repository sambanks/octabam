"""COPY PROJECT -- duplicate a project on the card without opening it.

PROJECT > COPY PROJECT (after SAVE TO NEW): pick a project in the mounted
set, name the copy, confirm. The live project stays loaded; an engine job
copies the source folder byte-for-byte (stock files and module sidecars).
"""

from remix.schema import Category, Kind, Linked, Module, Poke, Proof, TableGrow

# PROJECT list (docs/firmware/MAINMENU.md): count + rows pointer
PROJ_DESC = 0x400CBCAC
PROJ_ROWS = 0x400CC308
PROJ_N, ROW_WORDS = 15, 6
# After SAVE TO NEW (stock index 5): insert before EXPORT TO SET.
INSERT_AT = 6

MODULE = Module(
    name="copy-project",
    key="COPY PROJECT",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES,
    author="iliamurzinov",
    author_url="https://github.com/iliamurzinov",
    proof=Proof.HARDWARE,
    proof_note="flashed with CF card update and tested on author's MKII (17 Oct 2026)",
    doc="PROJECT > COPY PROJECT: duplicate a project folder on the card without loading it.",
    requires=("STORE",),  # STORE's encoder hook: LEVEL scrolls the project LISTPOP
    linked=(Linked("cp", "modules/copy-project/copyproj.s", cpu="5475", dram=True),),
    tables=(
        TableGrow(
            "PROJECT + COPY PROJECT",
            old=PROJ_ROWS,
            count=PROJ_N * ROW_WORDS,
            insert_at=INSERT_AT * ROW_WORDS,
            symbols=(
                ("cp", "cp_lbl"), ("cp", "cp_zero"), ("cp", "cp_menu"),
                ("cp", "cp_zero"), ("cp", "cp_zero"), ("cp", "cp_zero"),
            ),
            refs=((PROJ_DESC + 0x18, PROJ_ROWS),),
        ),
    ),
    pokes=(
        Poke(PROJ_DESC, expect=(PROJ_N).to_bytes(4, "big"),
             write=(PROJ_N + 1).to_bytes(4, "big"),
             note="PROJECT rows 15 -> 16 (COPY PROJECT after SAVE TO NEW)"),
    ),
)
