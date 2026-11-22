# `cfmeter-idle` — CF METER IDLE

Measures how much of the ColdFire's time is idle, for
[CF METER](../cfmeter/README.md)'s idle-time readout: main's idle loop,
timed. It replaces main's last init call (`0x4001fc96`, `jsr 0x40098a2c`)
and the `bras .` after it with the call and a loop that reads DMA timer 3.
A step shorter than twice the shortest step seen, + 8 counts, is added to
CF METER's idle counter; a longer step was taken by an interrupt or a
task. The shortest step goes to slot 6.

Main is the priority-0 task and never blocks (`docs/firmware/KERNEL.md`),
so it runs only when no other task is ready and no interrupt is being
served.
