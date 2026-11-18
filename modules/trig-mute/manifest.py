"""TRIG MUTE -- GRID RECORDING: hold a step and press FUNC to mute or unmute
its trig. A muted trig keeps its locks and condition but does not play;
its red LED blinks.

The mute is stored in the trig word's condition (bits 6-0): stock uses
0..64, a muted trig holds condition + 65. So the pattern carries it through
save, load, the battery copy (power cycle), copy and paste with no file or
battery RAM of its own. 7:8 and 8:8 (63, 64) leave no room and cannot be
muted. Stock firmware plays a muted trig (it reads > 64 as no condition)
and shows ERR for its condition.

Five detours, one poke and one key table, sites read from the disassembly
of 1.40C:
  0x4009d34e  step handler, the condition test: a muted trig fails it
  0x4002ce78  condition label: the trig's own condition
  0x4002daea / 0x4002db72  condition edit (audio): edits the trig's own
              condition, keeps the mute
  0x40034346  lock-flash pass exit: muted trigs' red LEDs blink
  0x4009a858  the pattern check after a load clamps a condition > 64 to 64
              (8:8): it now lets 65..127 through (found under the port:
              saved 65, reloaded 64)
  0x400bee78  the trig-held layer's key rows: stock's 16 + FUNC
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, SymbolRef

H = bytes.fromhex

MODULE = Module(
    name="trig-mute",
    key="TRIG MUTE",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="Hteah",
    author_url="https://github.com/Hteah",
    proof=Proof.PORT,
    proof_note="verify_trig_mute: hold step + FUNC mutes and unmutes, a muted trig does not "
               "fire, its condition survives edits, its LED blinks, save / reload / power cycle, "
               "under the port (MKI)",
    doc="GRID REC: hold a step + FUNC mutes or unmutes its trig (kept with the pattern; "
        "the LED blinks).",
    linked=(Linked("tmu", "modules/trig-mute/trigmute.s", dram=True),),
    detours=(
        Detour(0x4009d34e, H("4eb9400a5164"), "tmu", "tmu_gate",
               "step handler: a muted trig fails its condition test"),
        Detour(0x4002ce78, H("202f0020243c400b37df"), "tmu", "tmu_lbl",
               "condition label: show a muted trig's own condition", pad_to=10),
        Detour(0x4002daea, H("10300a01727fc081"), "tmu", "tmu_rd",
               "condition edit: read a muted trig's own condition", pad_to=8),
        Detour(0x4002db72, H("767fc483363c048d"), "tmu", "tmu_wr",
               "condition edit: keep the mute on write", pad_to=8),
        Detour(0x40034346, H("4cd73c7c4fef0024"), "tmu", "tmu_led",
               "lock-flash pass: blink muted trigs' red LEDs", pad_to=8),
    ),
    pokes=(
        Poke(0x4009a858, H("7e40"), H("7e7f"),
             "pattern check after a load: conditions up to 127 pass (stock clamps > 64 to 8:8)"),
    ),
    symbol_refs=(
        SymbolRef(0x400bee78, 0x400bec0a, "tmu", "TMU_KEYS",
                  "trig-held layer (grid recording): stock rows + FUNC"),
    ),
    gates=(Gate("tools/verify/verify_trig_mute.py", venv=True, stage="image"),),
)
