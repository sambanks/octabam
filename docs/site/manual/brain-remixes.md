![BRAIN: Remixes](../../img/brain/remixes.png)

*BRAIN: Remixes*

REMIXES lets you boot another firmware image directly from the CF card without
flashing it. The web builder generates an `.RMX` file for each remix it builds
(see [Build and Install](../../web-builder.md)), and stock OS 1.40C is also
supported.

Copy `.RMX` files into the `BRAIN/REMIXES/` folder on your CF card. On macOS,
delete any hidden `._<name>` metadata files so they do not appear in the menu.

All `.RMX` files in that folder are listed alphabetically, with `RUNNING` shown
next to the image currently running (ignoring case and spaces). Press **YES** on
an entry to prompt `BOOT <NAME>?`, then press **YES** again to boot it without
writing to flash. Switching images stops playback, saves the current project
(just like OS UPGRADE), loads the chosen image, and restarts.

Your selection is remembered and automatically booted on subsequent startups
before the project loads. After switching, a `FLASHED` separator lists the
firmware installed in flash memory; select it to return to your flashed image
and clear the remembered boot target.

To bypass the remembered image for a single boot, hold **FUNC** while powering
on and choose **EXIT** in the stock STARTUP MENU, or remove the CF card.
