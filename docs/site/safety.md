# Safety and recovery

## Recovery procedure

The Startup Menu is separate from the operating system and provides a way
to reinstall stock if the modified OS will not boot. Recovery requires a
working Startup Menu, a DIN MIDI interface, and a copy of the stock OS:

1. Power off. Hold FUNC and power on → STARTUP MENU.
2. TRIG 3 → MIDI UPGRADE → "READY TO RECEIVE MIDI UPGRADE".
3. Send `downloads/extracted/OCTATRACK_OS1.40C.syx` (the stock OS, from
   `make os`) over DIN MIDI, from a SysEx app or
   `make midi-flash PORT=<port> SYX=downloads/extracted/OCTATRACK_OS1.40C.syx`.
4. Wait through PREPARING FLASH → UPDATING FLASH. Do not power off.

If the unit still boots far enough to enter USB DISK MODE, you can also
install from the CF card. The Octatrack's USB port cannot send an OS
upgrade.

TRIG 2 → EMPTY RESET clears battery-backed RAM and settings, not the card.

## FAQ

**Is this official Elektron firmware?**
No. Nothing here is endorsed by, supported by, or affiliated with
Elektron.

**Does flashing touch my card or projects?**
No. An OS upgrade does not touch the CF card. Two exceptions: a remix
carrying KITS writes `kits.work` into each project it loads (a stock OS
ignores the file), and BRAIN writes its `card.work` / `card.strd`.

**MKI or MKII?**
Both run the same OS 1.40C file, and both can flash an octabam image.
octabam's own effects have only been tested on an MKII.

**Has any of the three remixes run on a unit?**
No. Each is verified under the port: the emulator boots the image and
every gate passes, but the emulator is not the hardware. The closest
thing to a hardware run is bottleservice — the same delay and reverb bus
without the core modules — which ran on Sam's MKII.

**Why can I not download a built image?**
A built `.bin` or `.syx` contains Elektron's OS. Distributing it would
distribute their software, so you build it yourself from your own copy.

**Where are hardware failures recorded?**
The [failure register](https://github.com/sambanks/octabam/blob/main/docs/contributing/FAILURE_MODES.md)
records observed failures, causes and fixes. It cannot guarantee that a
particular unit or flash attempt will recover.
