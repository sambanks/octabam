# Safety and Recovery

Read this page before flashing, and keep your recovery files and MIDI interface
on hand whenever you install modified firmware.

## Recovery requirements

Octabam is community-maintained and is not supported by Elektron. Flashing
modified firmware carries a risk of data loss or leaving the unit unable to boot
until you reinstall stock OS.

Recovering from a bad flash requires a working Startup Menu, a 5-pin DIN MIDI
interface, and a copy of stock OS 1.40C. Although the Startup Menu is stored
separately from the main OS, this procedure cannot recover a unit if its Startup
Menu or MIDI input is not working.

## Reinstall stock OS over MIDI

1. Power off the unit, then hold **FUNC** while powering on to open the
   **STARTUP MENU**.
2. Press **TRIG 3** (MIDI UPGRADE) and wait for "READY TO RECEIVE MIDI UPGRADE".
3. Send `downloads/extracted/OCTATRACK_OS1.40C.syx` (from `make os`, or
   Elektron's official download) over DIN MIDI using a SysEx app, or run:

   ```bash
   make midi-flash PORT=<port> SYX=downloads/extracted/OCTATRACK_OS1.40C.syx
   ```
4. Wait through PREPARING FLASH and UPDATING FLASH without powering off.

If the Octatrack still boots far enough to enter USB DISK MODE, you can also
reinstall stock OS from the CF card. The Octatrack's USB port cannot receive OS
upgrades.

`TRIG 2 → EMPTY RESET` clears battery-backed RAM and settings without touching
the CF card.

## Resolve a saved-data file warning

If a project's extra data file for FX page 2 parameter locks, Kits, or MIDI
scenes is unreadable or incompatible, the Octatrack displays a warning naming
the affected data and file. This can happen with corrupted, incomplete, or
older-format files. Standard stock projects without these extra files do not
trigger this warning.

Press **NO** to dismiss the warning and leave the existing file untouched, or
press **YES** to open the recovery menu. Turn **LEVEL** to pick an option and
press **YES**:

| Choice | Result |
|---|---|
| KEEP FILE / SKIP SAVED DATA | Leaves the file untouched on disk. That feature's saved data will not be loaded for this session. |
| START FRESH / REPLACE FILE | Continues without the old data and overwrites the file on the next save. For Kits, the project's stock Parts become the starting Kits. |
| BACKUP FILE THEN START FRESH | Starts fresh, copying the original file to a `.bak` backup before overwriting it on the next save. |

None of these options repair or migrate old data. Choose KEEP FILE if you want
to inspect or recover the file later on a computer. Pressing **NO** from the
choice menu also leaves the file untouched until the next project load.

## Common questions

**Is this official Elektron firmware?**
No. Octabam is not made, endorsed, supported by, or affiliated with Elektron.

**Does flashing touch my card or projects?**
No. Installing an OS update does not modify your CF card. Note that once
installed, Kits write a `kits.work` file into each project they load (which
stock OS ignores), and BRAIN stores its settings and templates on the card.

**MKI or MKII?**
Both models use the same OS 1.40C file and can run Octabam images.

**Why can I not download a prebuilt image?**
A built `.bin` or `.syx` file contains Elektron's operating system. Sharing it
would redistribute Elektron's software, so you build the image locally from your
own copy of OS 1.40C.

**Where are hardware failures recorded?**
Known hardware faults, causes, and fixes are tracked in the
[failure register](https://github.com/sambanks/octabam/blob/main/docs/contributing/FAILURE_MODES.md).
It does not guarantee that every unit or flash failure can be recovered.
