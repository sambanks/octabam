This module adds a new **RLEN** setting one step past `MAX`, displayed as
`PLEN`. It records exactly one loop of the track's pattern at the track's own
scale. With **TRIG** set to `ONE` and **QREC** set to `PLEN`, a single press
of REC records the next pass and stops automatically.

Stock **RLEN** counts master-clock 16th notes and tops out at 64, so a 1/4X
track cannot set a fixed recording length for its 16-bar pattern, while `MAX`
has no fixed length and runs until the next recorder trig.

## Operation

In **RECORDING SETUP**, turn **RLEN** one step past `MAX` to select `PLEN`.
Set **TRIG** to `ONE` and **QREC** to `PLEN`; pressing REC once records the
next pass and stops.

**RLEN** values 0–64 keep their stock behavior, so saved Parts do not need to
be restamped.

## Notes

- In PER TRACK mode, `PLEN` uses the track's own length and scale. Whether one
  loop should follow the track length or the master length is still undecided.
