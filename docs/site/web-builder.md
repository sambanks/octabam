# Build and Install

This page builds an Octabam v0.5 firmware image directly in your browser from
your own copy of Octatrack OS 1.40C. You can build [Octabam](remix-octabam.md),
[Octabam Verbs](remix-octabam-verbs.md), [Octabam Bus](remix-octabam-bus.md), or
any of the [Community Remixes](reference/community.md) listed under Community.
Select your target under **Remix** before building. Your OS file is processed
entirely in the browser and is never uploaded.

!!! note "Community remixes"
    Community remixes are maintained by their individual contributors rather
    than tested on every project CI run. A community remix appears here only if
    it passed `make check` when this page's patches were published.

!!! tip "Back up your projects"
    Back up your CF card before installing, or test with a fresh project first.
    Octabam's Kits write a `kits.work` file into each project they load.
    Projects created on the Octatrack after installation need no preparation;
    existing projects may need one preparation step covered in the
    [build guide](https://github.com/sambanks/octabam/blob/main/docs/guide/BUILDING.md).

## What you need

- `OCTATRACK_OS1.40C_dist.zip` from Elektron's Octatrack MKI or MKII download
  page, or the `OCTATRACK_OS1.40C.syx` file extracted from it.
- A modern desktop browser such as Chrome.
- A CompactFlash card in your Octatrack for CF card installation, or a 5-pin
  DIN MIDI interface connected to MIDI IN for MIDI installation.

## Build

<div id="octabam-builder">This page needs JavaScript.</div>
<script type="module" src="builder/page.js"></script>

The build takes a few seconds and produces three files:

| File | Use |
|---|---|
| `OCTATRACK_OCTABAM<tag>.bin` | CF card install: copy to the root of your CF card, then run PROJECT → SYSTEM → OS UPGRADE. |
| `OCTATRACK_OS1.40C_OCTABAM<tag>.syx` | DIN MIDI install. |
| `OCTABAM <tag>.RMX` (`OCTABAM-VRB <tag>.RMX`, `OCTABAM-BUS <tag>.RMX`) | Optional card-boot image: boots without flashing on a unit already running an Octabam image. See [Switch with an RMX file](#switch-with-an-rmx-file). |

Because these output files contain Elektron's OS, do not share or redistribute
them.

## Install the image

### From the CF card

Use this method when your Octatrack boots normally:

1. On the Octatrack, go to **PROJECT → SYSTEM → USB DISK MODE → YES**.
2. Copy the `.bin` file to the root of the mounted CF card, not inside a
   subfolder.
3. Safely eject the card from your computer, then exit USB DISK MODE on the
   Octatrack so all writes finish flushing.
4. Go to **PROJECT → SYSTEM → OS UPGRADE → YES** and confirm.
5. Wait for the unit to finish upgrading and restart, then power-cycle it once
   more before testing, since an OS upgrade does not clear DSP RAM.

### Over DIN MIDI

Use this method if your unit cannot boot into USB DISK MODE, or if you prefer
upgrading over MIDI:

1. Connect your MIDI interface's **MIDI OUT** to the Octatrack's **MIDI IN**.
2. Power off the unit, then hold **FUNC** while powering on to open the
   STARTUP MENU.
3. Press **TRIG 3** for MIDI UPGRADE and wait for "READY TO RECEIVE MIDI
   UPGRADE".
4. Send the `.syx` file using a SysEx utility. Do not send MIDI clock or merge
   other MIDI traffic onto that port. If the unit reports a checksum error,
   re-enter the Startup Menu and resend at a slower speed.
5. Wait through PREPARING FLASH and UPDATING FLASH without powering off or
   disconnecting the cable.
6. Let the unit finish booting, then power-cycle it once more.

### Switch with an RMX file

An `.RMX` file is a complete OS image that BRAIN can boot directly from the CF
card without rewriting flash memory. You can use this instead of flashing if
your unit is already running an Octabam image:

1. Copy the `.RMX` file to `/BRAIN/REMIXES/` on the CF card, creating the
   folders if needed.
2. On the unit, open **PROJ → BRAIN → REMIXES**, select the image name, and
   press **YES** at `BOOT <NAME>?`.
3. Your choice persists across reboots. To switch back to the flashed firmware,
   choose the entry under the FLASHED separator in the same menu.

See [BRAIN: Remixes](reference/manual/brain/remixes.md) for details.

## Confirm the installation

Check the boot screen or **SYSTEM STATUS → OS VERSION**. It should display
`OCTABAM` followed by the build tag from the filename. If it still says `1.40C`,
the stock OS is still installed.

To return to stock OS, install Elektron's official `.bin` from the CF card
using the steps above, or follow [Safety and recovery](safety.md).

## How it works

This page stores a compact patch for each published and community remix,
consisting of Octabam's new bytes plus instructions to copy stock ranges from
your local OS 1.40C file. It applies the patch to the MAIN OS section of your
file, repacks the firmware container using Elektron's container tool compiled to
WebAssembly, and wraps it for the CF card. If the input file does not match the
expected OS 1.40C MAIN OS image, the builder rejects it.

The generated files are byte-identical to running `make image` for the same
commit and build tag (displayed on this page). To build from source or customize
your module selection, see the
[build guide](https://github.com/sambanks/octabam/blob/main/docs/guide/BUILDING.md)
and [Create your own remix](own-remix.md).
