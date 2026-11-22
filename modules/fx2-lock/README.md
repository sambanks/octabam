# `fx2-lock` — FX2 LOCK

The FX2 chooser cannot change a track's effect. One poke in the chooser
window's key table (`0x400bc370`: `31 00` YES → `0x40052474`, the select
handler; `0x400bc38c`: `32 00` NO → `0x4003d440`, close): YES's entry
points at NO's handler, so YES closes the chooser and the select handler
(cursor → list entry → the Part's FX2 id, page defaults, SRAM twin, dirty
bits) never runs. The chooser still opens and scrolls.

A poke inside the handler (the "same effect" exit made unconditional at
`0x400524ba`) was tried first: Octakit wraps the handler's entry
(`machine-selection-001-at-40052474`) and halted in
`gk_machine_selection_fatal` on YES under the port. The table sits before
her wrapper.

Untouched: FX1's handler (`0x400526e4`, its own cursor and list), Part
and pattern paste, Kit load, the project's stored ids, `ot_project.py
host` / `set-fx` from a computer.

For a rig whose engines are locked to their tracks (bottleservice:
BusDelay on T1, BusVerb on T5, the stock DELAY on T8). Image 99, 4 Oct
2026: an FX2 change on T5 took the reverb off the track, and with the
engines hidden from the chooser there was no row to put it back.
