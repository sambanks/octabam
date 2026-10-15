## What it does

A new RLEN value one past MAX, drawn PLEN, that makes a recording exactly
one loop of the track's pattern on the track's own scale. With TRIG ONE
and QREC PLEN, one REC press records the next pass and stops.

Why it exists: RLEN counts master-clock 16ths and stops at 64, so a 1/4X
track cannot give its 16-bar pattern a fixed length; MAX has no length
and ends at the next recorder trig.

## How to use it

In RECORDING SETUP, turn RLEN one past MAX (the drawn PLEN label is not
yet verified on the unit). Set TRIG to ONE and QREC to PLEN: one REC
press records the next pass and stops.

RLEN 0–64 keep their stock meaning; saved parts need no restamp.

## Notes

- Not flashed to a unit yet.
- PER TRACK mode: the length is the track's own length on its own scale;
  whether one loop should be the track's or the master's is open.
