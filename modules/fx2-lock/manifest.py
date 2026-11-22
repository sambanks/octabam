"""FX2 LOCK -- the FX2 chooser cannot change a track's effect.

The chooser window's key table holds YES -> the select handler
(`0x400bc370`: `31 00`, `0x40052474`) and NO -> close (`0x400bc38c`: `32
00`, `0x4003d440`). One poke points YES at NO's handler: YES closes the
chooser and the select handler (cursor -> list entry -> the Part's FX2 id,
page defaults, SRAM twin, dirty bits) never runs. Octakit wraps that
handler's entry (`machine-selection-001-at-40052474`) and halts
(`gk_machine_selection_fatal`) when the select is short-circuited inside
it, which is why the lock sits in the table, before her wrapper. FX1's
chooser is separate and untouched; a Part or pattern paste, a Kit load and
the project's stored ids still set FX2.

For a rig whose engines are locked to their tracks (bottleservice: BusDelay
on T1, BusVerb on T5, the stock DELAY on T8): on image 99 an FX2 change on
T5 took the reverb off the track with no row to put it back (4 Oct 2026).
"""

from remix.schema import Category, Gate, Kind, Module, Poke, Evidence, Level

H = bytes.fromhex

MODULE = Module(
    name="fx2-lock",
    key="FX2 LOCK",
    kind=Kind.CF_PATCH,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); verify_fx2_lock under the port, 4 Oct "
             "2026"),),
    doc="Locks each track's FX2 effect: the FX2 chooser cannot change it.",
    pokes=(
        Poke(0x400BC374, expect=H("40052474"), write=H("4003d440"),
             note="FX2 chooser key table: YES -> the NO (close) handler, not the select"),
    ),
    gates=(Gate("tools/verify/verify_fx2_lock.py", venv=True, stage="image", project=True),),
)
