"""PATTERN MUTE -- a second mute layer saved with the pattern, as on the Digitakt II.

Stock keeps one mute state per project (bits 8-15 of 0x80000008 for audio
tracks, of 0x8000000c for MIDI tracks). This module keeps two layers:
GLOBAL, stock's state, saved in project.work; and PATTERN, saved in the
pattern. A track is muted when either layer mutes it. Double-pressing FUNC
chooses which layer the next mute edit (FUNC+track, the MIXER trig keys,
MIDI) changes, with a toast. The word stock and every other module read is
the OR of the two, so MUTE MODE and the LEDs need no change.

Sites: the 22 + 8 stores that follow a stock write of a mute word (the
battery-SRAM mirror stores), the project writer's two loads of the mute
bytes (so project.work keeps the GLOBAL layer), the UI-side pattern commit
(0x40062142), and FUNC's press record in the MKI and MKII key tables.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof, SymbolRef

# (site, register of the stock store) of `move.l %dN,0x100b14d4` / `...d8`.
# 0x4000fe6c / 0x4000fe82 clamp the mirror at power-up and are not hooked.
_MIRROR_A = (
    (0x4000ed60, 0), (0x400238f0, 0), (0x4003d314, 0), (0x4003d3d8, 1), (0x4003d400, 0),
    (0x4004034c, 1), (0x400403b2, 0), (0x40043e5a, 1), (0x40043e82, 0), (0x40045440, 0),
    (0x4005e432, 0), (0x4005e4b0, 0), (0x4006298c, 0), (0x40065534, 0), (0x40065574, 0),
    (0x4007d1ec, 1), (0x4007d61c, 0), (0x4007d778, 1), (0x4007d81a, 2),
)
# the project load's settings parser: always the GLOBAL layer
_LOAD_A = ((0x40088028, 0), (0x40088084, 0), (0x400880de, 0))
_LOAD_M = ((0x4008813a, 0), (0x40088196, 0))
_MIRROR_M = (
    (0x4000f256, 0), (0x4003d340, 0), (0x4004545c, 0), (0x4007d208, 0), (0x4007d670, 0),
    (0x4007d6ec, 2),
)


def _mirror(sites, tail, symbol, what):
    return tuple(
        Detour(a, bytes.fromhex(f"23c{r}100b14{tail}"), "pm", symbol,
               f"{what}: the mirror store after a stock write", kind="jsr")
        for a, r in sites)


MODULE = Module(
    name="pattern-mute",
    key="PATTERN MUTE",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="sambanks",
    author_url="https://github.com/sambanks",
    proof=Proof.PORT,
    proof_note="verify_pattern_mute under the port, 20 Oct 2026; not flashed",
    doc="Double-press FUNC: mute edits go to a PATTERN layer saved with the pattern, "
        "beside the GLOBAL layer (Digitakt II PATTERN MUTE / GLOBAL MUTE).",
    linked=(Linked("pm", "modules/pattern-mute/pm.s", dram=True, include=lambda modules, remix: ""),),
    detours=(
        _mirror(_MIRROR_A, "d4", "pm_mirror_a", "audio mute")
        + _mirror(_MIRROR_M, "d8", "pm_mirror_m", "MIDI mute")
        + _mirror(_LOAD_A, "d4", "pm_load_a", "audio mute, project load")
        + _mirror(_LOAD_M, "d8", "pm_load_m", "MIDI mute, project load")
        + (
            Detour(0x40089020, bytes.fromhex("71b98000000a"), "pm", "pm_save_a",
                   "project writer: TRACK_MUTE_MASK saves the GLOBAL layer", kind="jsr"),
            Detour(0x4008908c, bytes.fromhex("71b98000000e"), "pm", "pm_save_m",
                   "project writer: MIDI_TRACK_MUTE_MASK saves the GLOBAL layer", kind="jsr"),
            Detour(0x40062142, bytes.fromhex("13c080000003"), "pm", "pm_pat_commit",
                   "UI pattern commit: load the PATTERN layer of the current pattern", kind="jsr"),
            Detour(0x40052228, bytes.fromhex("4eb9400316a0"), "pm", "pm_ui_tick",
                   "UI loop: light the second colour of the current track key in the PATTERN layer",
                   kind="jsr"),
        )
    ),
    gates=(Gate("tools/verify/verify_pattern_mute.py", venv=True, once=True),),
    symbol_refs=(
        SymbolRef(0x400BFC12, 0x4004E954, "pm", "pm_func_press", "MKI key table: FUNC press"),
        SymbolRef(0x400C01F6, 0x4004E954, "pm", "pm_func_press", "MKII key table: FUNC press"),
    ),
)
