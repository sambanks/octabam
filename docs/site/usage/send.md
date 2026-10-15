## What it does

The bus client: two knobs that send this track to the two engines. DEL is
this track's level into the delay (track 1), REV its level into the reverb
(track 5). Each engine's wet comes out on the track that hosts it. DEL 0
and REV 0 is indistinguishable from no effect.

## Where to find it

On every track except 1, 5 and 8, FX2 is SEND (a new part is born that
way; the FX2 chooser cannot change it). Page 1 has the two knobs.

## How to use it

- Raise DEL to hear the track in the delay's repeats; raise REV for the
  reverb tail.
- The reverb also hears the delay's repeats through the reverb's DLY knob
  (TEMPO window): with DLY up, a delayed signal washes into the tail.
- Track 1's and track 5's FX2 pages draw these same two knobs, and nothing
  else: DEL feeds the delay, REV feeds the reverb.
- The delay follows the project tempo; its TIME knob sticky-snaps to tempo
  divisions.

## Knobs

| knob | range | default | what it does |
|---|---|---|---|
| DEL | 0–127 | 0 | this track's level into the delay |
| REV | 0–127 | 0 | this track's level into the reverb |

## Screens

![SEND's page on a track: the DEL and REV knobs](../../img/send/main.png)
