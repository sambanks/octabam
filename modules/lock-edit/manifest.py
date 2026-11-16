"""LOCK EDIT -- [TRIG] + [BANK] in grid recording opens the audio editor on that step's sample and slice.

Hold a trig in grid recording and press [BANK]: the audio editor opens on
the step's sample (its sample lock, else the track's own) on the SLICE page,
with the slice the step plays selected and the whole slice in view (SLIC on:
slice STRT / 2; otherwise the frame STRT / 128 of the trim, the slice starting
there, or the view centred on it). While the trig is held, the page's
encoders edit that slice. lockedit.s has the detail.
"""

from remix.schema import Category, Gate, Kind, Linked, Module, Proof, SymbolRef

# [BANK]'s press in both MKI key tables (records 0x400c00a2 and 0x400c0686,
# code 0x2f; the press long at +2 is stock 0x4007af80, referenced by nothing
# else; the second record is the MKII layer's). le_bank opens the editor on a
# held trig's sample in grid recording, else jumps to stock's. Read from 1.40C.
BANK_PRESS_SLOTS, BANK_PRESS = (0x400C00A4, 0x400C0688), 0x4007AF80
# The grid's TRIG 1-16 records (0x400bfd96 + 26k, code k; press, hold and
# hold longs at +2/+6/+10 all stock 0x40060ce0; the key task calls +10 with
# event 2 (0x400316e0), referenced by nothing else). Held long enough on a
# step with a sample lock, the hold event opens the lock popup, whose window
# shuts the editor [TRIG]+[BANK] just opened (measured under the port,
# 11 Nov 2026). le_trighold drops a trig's hold while the editor is up and
# passes every other to stock's.
TRIG_HOLD_SLOTS, TRIG_HOLD = tuple(0x400BFD96 + 26 * k + 10 for k in range(16)), 0x40060CE0

MODULE = Module(
    name="lock-edit",
    key="LOCK EDIT",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES, author="8thmyth", author_url="https://github.com/8thmyth",
    proof=Proof.HARDWARE,
    proof_note="8thmyth's MKI, image OCTABAMHC (remix test/octabam-lazy-chop), 14 Nov 2026: STRT locks with SLIC on and off, "
               "sample locks on FLEX and STATIC tracks; verify_lock_edit under the port",
    doc="[TRIG]+[BANK] in grid recording opens the audio editor on the step's sample, its slice selected and in view.",
    linked=(Linked("lockedit", "modules/lock-edit/lockedit.s", dram=True),),
    symbol_refs=(
        *(SymbolRef(a, BANK_PRESS, "lockedit", "le_bank",
                    "[BANK] press: in grid recording with a trig held, the editor on that step's sample and slice")
          for a in BANK_PRESS_SLOTS),
        *(SymbolRef(a, TRIG_HOLD, "lockedit", "le_trighold",
                    "grid TRIG hold: dropped while the editor is up (the lock popup would shut it)")
          for a in TRIG_HOLD_SLOTS),
    ),
    gates=(Gate("tools/verify/verify_lock_edit.py", venv=True, stage="image"),),
)
