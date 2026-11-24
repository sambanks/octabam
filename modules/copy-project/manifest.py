"""COPY PROJECT -- duplicate a project on the card without opening it.

CHANGE project list > FUNC+BANK > COPY: the selected folder is the source;
name the copy, confirm. The live project stays loaded; an engine job copies
the source folder byte-for-byte (stock files and module sidecars).

Re-homed from PROJECT menu TableGrow (issue #931): the RENAME/DELETE LISTPOP
grows 2→3 instead of PROJECT 15→16.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Evidence, Level, TableGrow

# CHANGE → FUNC+BANK LISTPOP (docs/firmware/PANEL.md)
HANDLERS = 0x400CBAAC
LABELS = 0x400CBAB4
OPEN_PEA_HANDLERS = 0x4006418A  # pea handlers[] absolute
OPEN_PEA_LABELS = 0x40064190    # pea labels[] absolute
OPEN_COUNT_IMM = 0x400641A2     # pea #2 immediate (count)

H = bytes.fromhex

MODULE = Module(
    name="copy-project",
    key="COPY PROJECT",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES,
    author="ilia-murzinov",
    author_url="https://github.com/ilia-murzinov",
    evidence=(Evidence(Level.UNIT, unit="MKII", date="2026-10-27",
        note="FUNC+BANK (#931); CORE CP on MKII 27 Oct 2026: COPY + OPEN IT? loads/closes CHOOSE, no save prompt"),),
    doc="CHANGE project list > FUNC+BANK > COPY: duplicate the selected project folder on the card.",
    requires=("STORE",),  # STORE's encoder hook: LEVEL scrolls LISTPOP (name pick unused now; keep for confirm paths)
    linked=(Linked("cp", "modules/copy-project/copyproj.s", cpu="5475", dram=True),),
    detours=(
        Detour(0x40085012, H("4eb940013f40"), "cp", "cp_sa_cap_stub",
               "SAVE TO NEW, the call that overwrites the project name: the old folder's path is kept",
               kind="jsr"),
        Detour(0x400850EE, H("2f02206efdee"), "cp", "cp_sa_copy_stub",
               "SAVE TO NEW, after the last stock write: the old folder's other files go into the new one"),
    ),
    tables=(
        TableGrow(
            "FUNC+BANK handlers + COPY",
            old=HANDLERS,
            count=2,
            symbols=(("cp", "cp_from_change"),),
            refs=((OPEN_PEA_HANDLERS, HANDLERS),),
        ),
        TableGrow(
            "FUNC+BANK labels + COPY",
            old=LABELS,
            count=2,
            symbols=(("cp", "cp_lbl"),),
            refs=((OPEN_PEA_LABELS, LABELS),),
        ),
    ),
    pokes=(
        Poke(OPEN_COUNT_IMM, expect=(2).to_bytes(2, "big"),
             write=(3).to_bytes(2, "big"),
             note="FUNC+BANK LISTPOP count 2 -> 3 (RENAME/DELETE/COPY)"),
    ),
    gates=(Gate("tools/verify/verify_copy_project.py", venv=True, once=True, project=True),),
)
