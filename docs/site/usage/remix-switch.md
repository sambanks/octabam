Boots an OS image from the card without writing the flash. Each `.RMX`
file in `/BRAIN/REMIXES/` is a raw OS image.

## Operation

BRAIN > REMIXES lists the `.RMX` files in order. The one whose name
matches the running image (case and spaces ignored) shows `RUNNING` at the
right. Press [YES] to be asked `BOOT <NAME>?`; [YES] again boots it
without writing the flash. After a switch, a `FLASHED` separator shows the
image that a power-cycle returns to.

If the DSP has stopped (no sound, the sequencer stuck on a step), the
switch is refused with `DSP STOPPED: REBOOT`, and the unit is not
reset. The choice is already saved, so a power-cycle boots it. A card
read that comes up short is refused with `IO ERROR`.

The image you switch to need not carry this module: stock 1.40C itself is
a valid target.
