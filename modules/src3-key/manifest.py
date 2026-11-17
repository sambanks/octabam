"""SRC3 KEY -- [MIDI] in the audio editor starts / stops a SRC3 recording.

MKI only (the MKII has its own [REC3] key; there [MIDI] stays stock). With SRC3 KEY, [MIDI] pressed while the audio
editor is open starts the current track's recorder with SRC3 only (its
RECORDING SETUP source, QREC applies); pressed again it stops the take at
once, whatever RLEN. Outside the editor [MIDI] is stock's. With LAZY CHOP
in LIVE CHOP, TRIG 1 joins the take at the record head and YES stops it.
src3key.s has the detail.
"""

from remix.schema import Apply, Binary, Category, Gate, Kind, Linked, Module, Proof, Scope, Setting, Store, SymbolRef

# [MIDI]'s record in the MKI key table (0x400bfc10, the MKI layer's; record
# 0x400c0158, code 0x35): press +2 and release +6 both stock 0x40055678 (it
# tells them apart by its second argument). MKI only (8thmyth, 14 Nov 2026):
# the MKII has [REC3], so the MKII table's record (0x400c073c) stays stock,
# and the code checks the model flag as well. Read from 1.40C.
PRESS_SLOTS, RELEASE_SLOTS, MIDI_KEY = (0x400C015A,), (0x400C015E,), 0x40055678

STORE_ID = "octabam.src3-key"


def sk_inc(modules, remix):
    """remix.inc: get_on reads the ON setting (without BRAIN: on)."""
    import sys, pathlib
    from remix import schema
    sys.path.insert(0, str(pathlib.Path(schema.__file__).resolve().parents[1]))
    from remix import brain
    mods = modules if isinstance(modules, dict) else {}
    get = brain.read_macro(remix, mods, STORE_ID, "MIDI = SRC3", "get_on").rstrip("\n")
    if "brain_v_" not in get:
        get = "        .macro  get_on reg\n        move.l  sk_on,\\reg\n        .endm"
    return "| remix.inc -- SRC3 KEY (modules/src3-key/manifest.py)\n" + get + "\n"


MODULE = Module(
    name="src3-key",
    key="SRC3 KEY",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES, author="8thmyth", author_url="https://github.com/8thmyth",
    proof=Proof.HARDWARE, proof_note="8thmyth's MKI, image OCTABAMHC (remix test/octabam-lazy-chop), 14 Nov 2026; verify_src3_key under the port (MKI, and the MKII left stock)",
    doc="[MIDI] in the audio editor starts / stops a SRC3 recording on the track's recorder (MKI has no [REC3]).",
    linked=(Linked("src3key", "modules/src3-key/src3key.s", dram=True, include=sk_inc),),
    store=Store(STORE_ID),
    settings=(Setting(1, "MIDI = SRC3", Binary(), default=1, scope=Scope.CARD, apply=Apply.LIVE,
                      doc="MKI: [MIDI] in the audio editor is SRC3 record start / stop (on) or stock's MIDI page (off); the MKII keeps its own [REC3]"),),
    symbol_refs=(
        *(SymbolRef(a, MIDI_KEY, "src3key", "sk_press",
                    "[MIDI] press: in the audio editor, SRC3 record start / stop") for a in PRESS_SLOTS),
        *(SymbolRef(a, MIDI_KEY, "src3key", "sk_release",
                    "[MIDI] release: dropped in the audio editor") for a in RELEASE_SLOTS),
    ),
    gates=(Gate("tools/verify/verify_src3_key.py", venv=True, stage="image"),),
)
