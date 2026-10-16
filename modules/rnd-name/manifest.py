"""RND NAME -- FUNC+CUE random name on project name editors.

CREATE / SAVE PROJECT AS / CHOOSE NEW PROJECT NAME: FUNC+CUE fills YYMMDD
(unit RTC), a space, and two pool words (<=26 chars). SAVE SAMPLE AS,
NEW DIR / SET: words only. KITS SAVE KIT: one short word. Press again for
another. YES accepts; typing still edits.

Rename is unchanged. Stock name-editor FUNC+REC/PLAY/STOP (PASTE/CLEAR/
COPY NAME) stay. The name-editor FUNC-held key table at 0x400d0916 is
repointed to our copy with CUE added; editors are gated on callback slot
0x460e761a.
"""

from remix.schema import Category, Gate, Kind, Linked, Module, Proof, SymbolRef

MODULE = Module(
    name="rnd-name",
    key="RND NAME",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES,
    author="iliamurzinov",
    author_url="https://github.com/iliamurzinov",
    proof=Proof.HARDWARE,
    proof_note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); " "FUNC+CUE on CREATE under the port (verify_rnd_name); pools from unit",
    doc="Project name editors: FUNC+CUE fills YYMMDD + random pool name.",
    linked=(Linked("rnd", "modules/rnd-name/rnd.s", dram=True),),
    symbol_refs=(
        SymbolRef(
            0x400D08F2, 0x400D0916, "rnd", "rnd_func_keys",
            "name-editor FUNC-held keys: stock + CUE -> rnd_chord",
        ),
    ),
    gates=(Gate("tools/verify/verify_rnd_name.py", venv=True, once=True),),
)
