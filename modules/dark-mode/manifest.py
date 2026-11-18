"""DARK MODE -- System-wide OLED-style Dark Mode for Octatrack MKI and MKII.

Hooks the display compositor flush routine at 0x40013cae:
Inverts the 1,024-byte display framebuffer immediately after all layers
(Page plane, Audio Editor, Mixer, Arranger, Menus, Popups, Step View) have
been composited and before the diff-and-send loop transmits blocks to UART1.

Configurable via setting 'DARK MODE' (default 1 / ON).
"""
import dataclasses
from remix.schema import (Apply, Binary, Category, Detour, Gate, Kind, Linked,
                          Module, Proof, Scope, Setting, Store)

STORE_ID = "octabam.dark-mode"


def dm_inc(modules, remix):
    import sys, pathlib
    from remix import schema
    sys.path.insert(0, str(pathlib.Path(schema.__file__).resolve().parents[1]))
    from remix import brain
    mods = modules if isinstance(modules, dict) else {}
    get = brain.read_macro(remix, mods, STORE_ID, "DARK MODE", "get_dark_mode").rstrip("\n")
    if "brain_v_" not in get:
        get = "        .macro  get_dark_mode reg\n        move.l  dm_enabled,\\reg\n        .endm"
    return "| remix.inc -- DARK MODE (modules/dark-mode/manifest.py)\n" + get + "\n"


_UNIT = Linked("darkmode", "modules/dark-mode/darkmode.s", dram=True, include=dm_inc)

MODULE = Module(
    name="dark-mode",
    key="DARK MODE",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES,
    author="8thmyth",
    author_url="https://github.com/8thmyth",
    proof=Proof.HARDWARE,
    proof_note="8thmyth's MKI, image OCTATRACK_METALSV8 / METALSV9, 18 Nov 2026; verify_dark_mode under the port",
    doc="Full Octa Dark Mode: inverted OLED-style display across all screens, menus, and popups.",
    linked=(_UNIT,),
    store=Store(STORE_ID),
    settings=(
        Setting(1, "DARK MODE", Binary(), default=0, scope=Scope.CARD, apply=Apply.LIVE,
                doc="System-wide Dark Mode: 1 = dark (white on black), 0 = stock (black on white)"),
    ),
    gates=(Gate("tools/verify/verify_dark_mode.py"),),
    detours=(
        Detour(0x40013cae, bytes.fromhex("2a79400b9710"), "darkmode", "dm_flush_hook",
               "hook after layer composite to invert backbuffer for system-wide dark mode", kind="jmp"),
    ),
)
