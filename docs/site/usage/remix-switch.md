## What it does

Boots an OS image from the card without writing the flash. Each `.RMX`
file in `/BRAIN/REMIXES/` is a raw OS image.

## How to use it

BRAIN > REMIXES lists the `.RMX` files, sorted. The one whose name
matches the running image (case and spaces ignored) has `RUNNING` at
the right. YES asks `BOOT <NAME>?`; YES boots it without writing the
flash. After a switch, a `FLASHED` separator shows the image a
power-cycle returns to.

A staged image need not carry this module: stock 1.40C itself is a
valid target.
