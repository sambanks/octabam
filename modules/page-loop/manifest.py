"""PAGE LOOP -- loop one 16-step page of one track while you edit, in time.

In GRID RECORDING, hold PAGE and tap trig 1..4: the current track (audio
or MIDI) loops that page while every other track plays the full pattern.
The same combo again ends it, as does a pattern or bank change; the track
is then exactly where it would have been, because the firmware's own
position counter never stopped. A toast says LOOP PAGE n / LOOP OFF.

Six detours: the transport start's step set (0x4009bcb6 / 0x4009bde6), the tick's step advance (0x400a3d72 / 0x400a3e8c, audio /
MIDI) and wrap (0x400a3d90 / 0x400a3eb0): the looped track's play step
0x800064d0[t] holds its page's step while a shadow keeps the true
position (the play step IS the position; nothing else counts it). The PAGE held layer's
key rows repointed (SymbolRef 0x400beef4) to a copy of stock's three rows
plus trig 1..4. On stock, PAGE + trig in grid recording places a trig and
flips the page on release; with PAGE LOOP it toggles the loop instead.

Sites read from the disassembly of 1.40C; behaviour measured under the
port by verify_page_loop (MKI panel). Run on an Octatrack MKI since ACCLOOP6 (25 Oct 2026), in every image through ACCLOOP32.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof, SymbolRef

H = bytes.fromhex

MODULE = Module(
    name="page-loop",
    key="PAGE LOOP",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="Hteah",
    author_url="https://github.com/Hteah",
    proof=Proof.PORT,
    proof_note="verify_page_loop: loop on / off, play step looping, in time on exit, "
               "other tracks untouched, pattern change ends it, under the port (MKI)",
    doc="GRID REC: PAGE + trig 1-4 loops that page of the current track, in time; "
        "again to stop.",
    linked=(Linked("pl", "modules/page-loop/pageloop.s", dram=True),),
    detours=(
        Detour(0x400a3d72, H("1011528012001280"), "pl", "pl_inc_a",
               "audio step + 1: the looped track steps through its page", pad_to=8),
        Detour(0x400a3d90, H("206f00984210"), "pl", "pl_wrap_a",
               "audio wrap at the track's length: the page's first step"),
        Detour(0x400a3e8c, H("1012528012001480"), "pl", "pl_inc_m",
               "MIDI step + 1: the looped track steps through its page", pad_to=8),
        Detour(0x400a3eb0, H("42122f034eb9400a536c"), "pl", "pl_wrap_m",
               "MIDI wrap at the track's length: the page's first step", pad_to=10),
        Detour(0x4009bcb6, H("266f00301751 0020".replace(" ", "")), "pl", "pl_start_a",
               "transport start / resync set the audio steps: map the looped one", pad_to=8),
        Detour(0x4009bde6, H("1d50002850c0"), "pl", "pl_start_m",
               "transport start / resync set the MIDI steps: map the looped one"),
    ),
    symbol_refs=(
        SymbolRef(0x400beef4, 0x400bee88, "pl", "PL_KEYS",
                  "PAGE held layer (grid recording): stock rows + trig 1..4"),
    ),
    gates=(Gate("tools/verify/verify_page_loop.py", venv=True, stage="image"),),
)
