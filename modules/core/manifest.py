"""CORE -- the OBAM store's run-time layers on the unit (docs/proposals/STORE.md).

This increment: card-layer FX page defaults, read-only. At each LOAD PROJECT
and at the power-up's bank load the core reads /OCTABAM/card.work (card.strd
by the pair rule) and writes each valid default record over its effect's
descriptor defaults; the choosers and the new-part initialiser read them
from there. Written by tools/hw/ot_store.py on a computer; the unit's own
SAVE AS DEFAULT, the SETTINGS list, the project pair and the CS1 block are
the next increments. README.md.
"""
import pathlib
import sys

from remix import schema
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex
SOURCE = "modules/core/core.s"


def fx_inc(modules):
    """The `remix.inc` core.s includes: core_fx[], one 36-byte entry per
    selected effect with knobs (store.fx_targets): layout hash, store id
    pointer, twelve keys, fx id, id length."""
    sys.path.insert(0, str(pathlib.Path(schema.__file__).resolve().parents[1]))
    from remix import store
    mods = modules if isinstance(modules, dict) else {}
    targets = [m for m in mods.values() if m.menu is not None and len(m.params) == 12]
    out = ["| remix.inc -- core_fx: the effects in this image (modules/core/manifest.py)",
           "        .section .rodata", "        .balign 4", "        .globl  core_fx, core_fx_n",
           f"core_fx_n: .long {len(targets)}", "core_fx:"]
    for i, m in enumerate(targets):
        keys = ", ".join(str(k) for k in store.fx_keys(m))
        out += [f"        .long   0x{store.fx_layout(m):08x}, core_id_{i}",
                f"        .word   {keys}",
                f"        .byte   0x{m.menu.fx2_id:02x}, {len(store.fx_store_id(m))}",
                "        .word   0"]
    for i, m in enumerate(targets):
        out.append(f'core_id_{i}: .ascii "{store.fx_store_id(m)}"')
    return "\n".join(out) + "\n        .text\n"


MODULE = Module(
    name="core", key=schema.CORE_KEY, kind=Kind.CF_PATCH,
    category=Category.SETTINGS, author="Sam Banks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="`verify_core` under the port (6 Oct 2026); not on hardware",
    doc="The settings store on the unit: card-wide knob defaults read from OCTABAM/card.work at each project load (docs/proposals/STORE.md).",
    # MODEDEF_TABLE: MODE DEFAULTS' view table, 0 without that module.
    linked=(Linked("core", SOURCE, cpu="5475", dram=True, include=fx_inc,
                   defsyms=(("MODEDEF_TABLE", 0),)),),
    detours=(
        Detour(0x40085342, H("721b2d41fdc6"), "core", "core_on_load",
               "LOAD PROJECT, before the empty-project init: the card's defaults onto the descriptors", kind="jsr"),
        Detour(0x40084d4a, H("73b980000002"), "core", "core_on_bankload",
               "the bank load the power-up runs: the card's defaults onto the descriptors", kind="jsr"),
        Detour(0x4008485e, H("7192722db280"), "core", "core_on_job",
               "the engine task's job switch: type 0x41 runs SAVE AS DEFAULT"),
        *(Detour(site, H("4eb94008ee74"), "core", "core_on_store",
                 "SAVE PROJECT's project store: card.work copied to card.strd", kind="jsr")
          for site in (0x40085642, 0x400856dc, 0x40085780)),
    ),
    gates=(Gate("tools/verify/verify_core.py", remix_arg=False, venv=True, stage="image"),),
)
