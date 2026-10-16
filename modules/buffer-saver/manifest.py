"""BUFFER SAVER -- SAVE PROJECT offers to save the recorder buffers holding an unsaved take, each assigned to itself.

`bufsave.s` (one DRAM unit) has the detail. Three detours:

- the recorder's per-track take start (0x400069d6, where LIMIT is
  written): marks that track's buffer as holding a new take;
- the engine's LOAD PROJECT case (0x4008534c): clears the marks;
- the PROJECT menu's SAVE (0x40063890, which FUNC + PROJ also reaches):
  with a marked buffer that has audio and is not recording, a YES/NO
  dialog, SAVE SAMPLES?. YES saves each marked buffer to the card under
  stock's name R<n>-YYMMDD-HHMM (-2, -3 .. when taken; never an overwrite)
  through stock's own save-and-assign-to-self (mode 2, as SAVE ALL
  RECORDINGS), then runs stock's SAVE. NO runs stock's SAVE unchanged.

Stock 1.40C keeps no "unsaved take" flag (port, 15 Oct 2026: a take
writes only the slot's length and trim), hence the marks.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex

MODULE = Module(
    name="buffer-saver",
    key="BUFFER SAVER",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES, author="Chupitnik", author_url="https://github.com/Chupitnik",
    proof=Proof.HARDWARE, proof_note="Chupitnik's MKII, 15-16 Oct 2026, AUTOSAVE1 and AUTOSAVE2 from the card (the module under its first name): after a take FUNC + PROJ and PROJECT > SAVE ask SAVE SAMPLES?; YES saves R<n>-YYMMDD-HHMM and assigns it to its buffer, two buffers in one save, an immediate re-save does not ask, a reload brings the takes back, NO saves as stock",
    doc="SAVE PROJECT offers to save unsaved recorder takes, each back into its own buffer, so they reload with the project.",
    linked=(Linked("bufsave", "modules/buffer-saver/bufsave.s", dram=True),),
    detours=(
        Detour(0x400069D6, H("21803c007401"), "bufsave", "arm_mark",
               "recorder take start: mark the track's buffer as holding a new take"),
        Detour(0x4008534C, H("4eb9400909d8"), "bufsave", "load_clear",
               "engine LOAD PROJECT: clear the marks", kind="jsr"),
        Detour(0x40063890, H("4feffff42f02"), "bufsave", "save_gate",
               "PROJECT > SAVE (and FUNC + PROJ): ask SAVE SAMPLES? first"),
    ),
    gates=(Gate("tools/verify/verify_buffer_saver.py", remix_arg=False, venv=True, stage="image"),),
)
