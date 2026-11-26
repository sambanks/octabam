"""APPLY SCENE -- a scene's locks, or the crossfader's blend, into the Part, onto steps, or into a scene.

Hold SCENE A or SCENE B (or both) and press YES: that scene's locked page-1
values become the Part's own (both: the crossfader's blend), and those
parameters' locks leave the two assigned scenes (the commit). In GRID
RECORDING a SCENE key pressed with trig keys held writes the same values as
step locks on the held steps. SCENE A + SCENE B + a trig key
saves the blend into that scene. The idea is Nathaniel Pavel's Apply Scene
for Modwerk; this module is a reimplementation (README "Credit").

No detours. Each scene key's held layer gets a table of its own, copied at
build time from the user's 1.40C (keys_inc): the stock encoder and
REC/STOP/PLAY records unchanged, the sixteen trig records wrapped (stock's
assign unless both scene keys are held), a YES record added. The four
base SCENE records' press goes through aps_scene_press, which then calls
stock's press. One table per scene serves MKI and MKII: both models' records
name the same layers (0x400bb2a2, 0x400bb2b6). Everything runs in the UI
task, from key handlers; the engine is C (apply.c, host-tested by
verify.py), generate.py builds apply_unit.s from it, adapter.c and hooks.s.
"""

import os
import pathlib

from remix.schema import (Apply, Category, Evidence, Gate, Kind, Level, Linked, Module, Option, Scope, Setting,
                          Store, SymbolRef)

_HERE = os.path.relpath(os.path.dirname(os.path.realpath(__file__)))
STORE_ID = "octabam.apply-scene"

BASE = 0x40000400                        # the MAIN OS section's load address
RECORD = 0x1a                            # a key record (MAINMENU.md section 6c)
KEYS_A, KEYS_B = 0x400BABC6, 0x400BAF34  # the SCENE A / B held layers' keys
LAYER_KEYS_A, LAYER_KEYS_B = 0x400BB2A6, 0x400BB2BA   # the layers' keys fields (0x400bb2a2 + 4, 0x400bb2b6 + 4)
ASSIGN = {"a": 0x40052A18, "b": 0x40052944}           # stock's SCENE + trig (the scene into A / B)
ENCODERS = tuple(range(0x38, 0x3F))      # records 0-6: the encoders' pushes (lock clears)
TRIGS = tuple(range(16))                 # records 7-22: the trig keys
TRANSPORT = (0x29, 0x27, 0x28)           # records 23-25: REC, STOP, PLAY (scene copy / paste / clear)
SCENE_PRESS = 0x4004348C                 # the SCENE keys' press, both keys, both models
SCENE_RECORDS = (0x400C051A, 0x400C0534, 0x400BFF36, 0x400BFF50)   # MKII A, B; MKI A, B


def _stock():
    from remix import schema
    return pathlib.Path(schema.__file__).resolve().parents[2] / "out/raw/section_3_MAIN_OS.bin"


def _table(img, side, keys):
    """One scene layer's table, refused when the stock table is not the one
    read (codes, order, the trig records' handlers)."""
    rec = lambda i: img[keys - BASE + i * RECORD:keys - BASE + (i + 1) * RECORD]
    codes = ENCODERS + TRIGS + TRANSPORT
    for i, code in enumerate(codes):
        if rec(i)[0] != code:
            raise ValueError(f"APPLY SCENE: SCENE {side.upper()}'s key {i} is {rec(i)[0]:#x}, not {code:#x}")
    if rec(len(codes))[0] != 0xFF:
        raise ValueError(f"APPLY SCENE: SCENE {side.upper()}'s table does not end after {len(codes)} keys")
    for i in TRIGS:
        if int.from_bytes(rec(7 + i)[2:6], "big") != ASSIGN[side] or any(rec(7 + i)[6:]):
            raise ValueError(f"APPLY SCENE: SCENE {side.upper()}'s trig {i + 1} is not stock's assign")
    stock = str(_stock())
    out = ["        .balign 2", f"        .globl  aps_keys_{side}", f"aps_keys_{side}:",
           f'        .incbin "{stock}", 0x{keys - BASE:x}, {len(ENCODERS) * RECORD}']
    for i in TRIGS:
        out += [f"        .byte   0x{i:02x}, 0", f"        .long   aps_trig_{side}, 0, 0, 0, 0, 0"]
    out += [f'        .incbin "{stock}", 0x{keys - BASE + (7 + len(TRIGS)) * RECORD:x}, {len(TRANSPORT) * RECORD}',
            "        .byte   0x31, 0", "        .long   aps_yes, aps_yes, 0, 0, 0",
            "        .short  0, 0",
            "        .byte   0xff, 0", "        .long   0, 0, 0, 0, 0, 0"]
    return out


def keys_inc(modules, remix):
    """remix.inc: the TRACKS setting's read (get_tracks), whether SCENES P2 is in the remix (APS_P2: page 2 is applied
    and its cache dropped through p2s_changed), the remix's FX2 descriptor
    table (APS_DESC2) and the two scene layers' tables."""
    from remix import brain
    import idspace
    img = _stock().read_bytes()
    mods = modules if isinstance(modules, dict) else {}
    out = ["| remix.inc -- APPLY SCENE (modules/apply-scene/manifest.py)",
           brain.read_macro(remix, mods, STORE_ID, "TRACKS", "get_tracks").rstrip("\n"),
           f"        .set    APS_P2, {1 if 'SCENES P2' in modules else 0}",
           f"        .set    APS_DESC2, {idspace.fx2_ids(remix):#x}",
           "        .data"]
    out += _table(img, "a", KEYS_A) + _table(img, "b", KEYS_B)
    out.append("        .text")
    return "\n".join(out) + "\n"


MODULE = Module(
    name="apply-scene",
    key="APPLY SCENE",
    kind=Kind.CF_PATCH,
    category=Category.PARTS,
    author="Skalskis",
    author_url="https://github.com/Skalskis",
    evidence=(Evidence(Level.EMULATOR, note="tools/verify/verify_apply_scene.py under the port; modules/apply-scene/verify.py"),),
    doc=("SCENE A / B (or both) + YES: the scene's locks (or the crossfader's blend) become the Part's own, "
         "and those locks leave the assigned scenes. With SCENES P2, FX1 and FX2 page 2 as well. GRID RECORDING: SCENE pressed with trigs held writes them as step locks. "
         "TRACKS: the edited track or ALL for SCENE + YES. SCENE A + "
         "SCENE B + trig: the blend saved into that scene."),
    linked=(Linked("aps", os.path.join(_HERE, "apply_unit.s"), cpu="5475", dram=True, include=keys_inc),),
    symbol_refs=(
        SymbolRef(LAYER_KEYS_A, KEYS_A, "aps", "aps_keys_a", "SCENE A held: the layer's keys, with YES added and the trigs wrapped"),
        SymbolRef(LAYER_KEYS_B, KEYS_B, "aps", "aps_keys_b", "SCENE B held: the layer's keys, with YES added and the trigs wrapped"),
    ) + tuple(SymbolRef(r + 2, SCENE_PRESS, "aps", "aps_scene_press",
                        "a SCENE key's press: step locks in GRID RECORDING with trigs held, then stock's press")
              for r in SCENE_RECORDS),
    gates=(Gate("modules/apply-scene/verify.py", remix_arg=False),
           Gate("tools/verify/verify_apply_scene.py", venv=True, stage="image")),
    store=Store(STORE_ID),
    settings=(Setting(1, "TRACKS", Option("ACTIVE", "ALL"), default="ACTIVE", scope=Scope.CARD,
                      apply=Apply.LIVE,
                      doc="SCENE + YES: the edited track (ACTIVE) or every audio track (ALL)"),),
)
