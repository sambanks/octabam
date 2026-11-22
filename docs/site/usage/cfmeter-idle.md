Measures how much of the ColdFire's time is idle, for CF Meter's idle-time
readout. It times main's idle loop. Main is the priority-0 task and never
blocks, so it runs only when no other task is ready and no interrupt is
being served.

## Access

No menu and no screen of its own. It works with CF Meter, in the test
remixes that carry both (for example `cfmeter`, `cfmeter-post` and `cfmeter-tracks`); the
idle figure appears in CF Meter's readout. Not in an official remix.

## Operation

- It replaces main's last init call and the `bras .` after it with the call
  and a loop that reads DMA timer 3.
- A step shorter than twice the shortest step seen, plus 8 counts, is added
  to CF Meter's idle counter. A longer step was taken by an interrupt or a
  task. The shortest step goes to slot 6.
- Under the port the loop boots and loads a project. The idle slot's number
  needs the unit: once a borrowed call returns to the stock `bras .`, main
  parks there and the loop's accounting stops.
