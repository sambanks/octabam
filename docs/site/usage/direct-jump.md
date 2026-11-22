A pattern change lands at the next step instead of at the end of the
pattern, as on the Analog Four and Rytm. It adds one option to an existing
setting and has no menu row of its own. It is off by default.

## Access

PROJECT > CONTROL > SEQUENCER > CHAIN AFTER: the option DIRECT sits as
option 2, between PAT.LEN and 2/16. Not in an official remix; several test
remixes carry it.

## Operation

- With DIRECT selected, a pattern chosen while the sequencer runs
  (PATTERN + TRIG, BANK + TRIG, or a MIDI program change) takes over at the
  next step boundary, at the step count the old pattern had reached,
  instead of at the old pattern's end or after its CHAIN AFTER length.
- A project that never selects DIRECT plays exactly as stock.

Built from timhastie/octatrick-modules (v2.9).
