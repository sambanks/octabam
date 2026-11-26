This module boots an OS image directly from the CF card without writing to
flash memory. Each `.RMX` file in `/BRAIN/REMIXES/` is a raw OS image.

## Operation

Open **BRAIN > REMIXES** to see the `.RMX` files listed in order. The entry
whose name matches the currently running image (ignoring case and spaces) is
marked `RUNNING` on the right. Press **[YES]** to bring up the `BOOT <NAME>?`
prompt, then press **[YES]** again to boot it without writing to flash. After
switching images, a `FLASHED` separator indicates the image that the unit will
return to after a power cycle.

If the DSP has stopped (no audio output and the sequencer is stuck on a step),
the switch is blocked with `DSP STOPPED: REBOOT` and the unit does not reset.
Your selection is already saved, so power-cycling the unit boots it. If a card
read comes up short, the switch fails with `IO ERROR`.

The target image does not need to include this module; stock 1.40C is a valid
target.
