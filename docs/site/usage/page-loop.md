Module author: [Hteah](https://github.com/Hteah). PR preparation and gate adaptation by 8thmyth.

PAGE LOOP lets you loop a single 16-step page of one track while you edit it.
The rest of the pattern continues playing normally, and the track returns in
sync when the loop ends.

## Access

In GRID RECORDING, hold PAGE and tap trig 1, 2, 3, or 4 to loop that page of
the current track. Repeat the same key combination to stop looping. This
module is not included in the standard remixes; build the `page-loop` remix or
include it in a custom remix.

## Operation

- A toast shows `LOOP PAGE n`, `LOOP OFF`, or `NO SUCH PAGE` if the pattern is
  shorter than the requested page.
- Only one track loops at a time. It continues looping when you switch tracks
  or leave GRID RECORDING, and stops when you change patterns or banks.
- When the loop ends, the track resumes at the exact step it would have
  reached without looping.
- Both audio and MIDI tracks can loop.
- When a loop is active at start, the first step after PLAY plays step 1 of the
  pattern, and page looping begins on step 2.
- PAGE + trig no longer places a trig and flips pages as on stock firmware;
  PAGE + REC, PLAY, and STOP remain unchanged.
