# TRIG MUTE

Mute single trigs, as on the newer Elektron boxes. A muted trig stays on the
grid with its locks and its condition, but does not play.

- In GRID RECORDING on an audio track, hold a step key and press FUNC: its
  trig is muted (TRIG MUTED). Again: unmuted (TRIG UNMUTED). Several held
  steps toggle together.
- A muted trig's red LED blinks.
- Holding an empty step and pressing FUNC places a muted trig.
- The trig's condition still shows and edits as usual (step + LEVEL).
- Removing the trig removes the mute; placing a trig starts unmuted.
- 7:8 and 8:8 trigs cannot be muted (CAN'T MUTE 7:8 8:8).

The mute is kept in the pattern itself, in the trig's condition value:
stock uses 0..64, and a muted trig holds its condition + 65. So it is saved
with the bank, copied and pasted with the trig or pattern, and kept over a
power cycle (the battery copy of the bank), with nothing of its own on the
card or in battery RAM. Stock firmware reads a value above 64 as "no
condition": there, a muted trig plays and its condition shows ERR.

Hooks (1.40C): the step handler's condition test (a muted trig fails it,
as a failed condition does: no trig, no locks; recorder trigs still run),
the condition label and edit, the lock-flash pass (the blink), and the
trig-held layer's key rows (stock's plus FUNC).

Not done: MIDI tracks (FUNC there is stock's).

Measured under the port (`tools/verify/verify_trig_mute.py`). Run on an
Octatrack MKI since ACCLOOP16 (28 Oct 2026): mute/unmute, save and power cycle keep the mutes.
