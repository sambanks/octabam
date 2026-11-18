# `page-loop` — PAGE LOOP

Author: [Hteah](https://github.com/Hteah).

Loop one 16-step page of one track while you work on it, the way newer
Elektron machines can. In **GRID RECORDING**, hold **PAGE** and tap **trig 1–4**:
the current track (audio or MIDI) loops that page while every other track
plays the full pattern. The same combo again ends it; so does a pattern or bank
change. When it ends, the track is exactly where it would have been, still in
time with the rest. A toast says `LOOP PAGE n`, `LOOP OFF` or `NO SUCH PAGE`.

- One loop at a time. It stays on its track when you switch tracks, and keeps
  looping outside GRID RECORDING until you end it.
- A short last page (a 40-step pattern's page 3) loops the steps it has.
- On stock, PAGE + trig in GRID RECORDING places a trig and flips the page on
  release. With PAGE LOOP that combo is the loop switch instead. PAGE + REC /
  PLAY / STOP (page copy, clear, paste) are unchanged.

**Known limit:** with a loop on, the first step after PLAY plays step 1 of
the pattern, not the page's first step. The sequencer builds each track's next
trig one step ahead, and the first one is built while stopped; from the second
step on the page loops. Starting the loop while playing has no such step.

## How

The play step `0x800064d0[t]` (audio `t` = 0..7, MIDI 8..15) is each track's
position: the tick adds one per step and clears it at the track's length, and
every reader (the trig build, locks, micro timing, the playhead LED) uses it.
Nothing else counts the position, so for the looped track this module keeps the
true position in a shadow (`pl_true`) and stores `page·16 + (true & 15) % span`
in its place. The length compare still sees the true position, so the
pattern's end is stock's.

| site | stock | PAGE LOOP |
|---|---|---|
| `0x400a3d72` / `0x400a3e8c` | step + 1 (audio / MIDI) | the looped track: shadow + 1, the page's step stored |
| `0x400a3d90` / `0x400a3eb0` | clear at the length | the looped track: the page's first step, shadow 0 |
| `0x4009bcb6` / `0x4009bde6` | transport start sets the steps | the looped track's next and playing steps mapped |
| `0x400beef4` (SymbolRef) | PAGE held layer: REC / PLAY / STOP | the same three rows + trig 1..4 → `pl_key` |

A step value that is not the one PAGE LOOP stored was written by someone else
(a resync), and becomes the true position. Leaving stores the true position at
the track's next step. The tick-side code reads and writes only its own `.data`
and the step bytes: no UI or kernel calls there.

## Proof

`tools/verify/verify_page_loop.py` under the port (MKI panel, blank project,
64-step pattern): the combo sets the loop with no page flip and no trig placed;
while T1 loops page 2 its step is always `16 + (T2's step % 16)` and a trig on
step 18 fires (live AMP VOL from its lock); without the combo it does not yet;
the combo again, a stop-and-start, and ending it mid-play or after the pattern's
wrap all put T1 back level with T2; a 40-step pattern refuses page 4 and loops
page 3's 8 steps; a MIDI track loops; a pattern change ends it.
Run on an Octatrack MKI since ACCLOOP6 (25 Oct 2026), in every image through ACCLOOP32.
