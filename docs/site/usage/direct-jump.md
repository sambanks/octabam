With Direct Jump enabled, pattern changes take effect on the next step instead
of waiting for the end of the pattern, similar to the Analog Four and Rytm. It
adds a single option to an existing setting rather than a menu row of its own,
and is off by default.

## Access

Open PROJECT > CONTROL > SEQUENCER > CHAIN AFTER. The DIRECT option appears as
option 2, between PAT.LEN and 2/16. This module is not included in the official
remixes, though several test remixes include it.

## Operation

- When DIRECT is selected, a pattern chosen while the sequencer is running (via
  PATTERN + TRIG, BANK + TRIG, or a MIDI program change) takes over at the next
  step boundary, continuing from the step count the old pattern had reached
  instead of waiting for the old pattern's end or its CHAIN AFTER length.
- A project that never selects DIRECT plays identically to stock OS.

Built from timhastie/octatrick-modules (v2.9).
