# Build Your Own Remix

You can assemble a personal remix from modules already in octabam. A remix
chooses which modules are included and which effects appear in the FX1 and
FX2 menus. The build refuses incompatible selections by name.

This guide is for combining existing modules. If you want to create a new
feature or contribute a module, start with the
[developer documentation](https://github.com/sambanks/octabam/blob/main/CONTRIBUTING.md)
and the [module author guide](https://github.com/sambanks/octabam/blob/main/docs/contributing/MODULES.md).

## 1. Prepare the build environment

Follow the [build guide](https://github.com/sambanks/octabam/blob/main/docs/guide/BUILDING.md) through installing the toolchain and
preparing your own OS 1.40C.

## 2. Select modules and effects

Copy an existing remix's `remix.py` (for example `remixes/octabam/remix.py`) into a
directory of your own, `remixes/community/<name>/`, named after you or its purpose
(never `octabam-*`), and edit its `name`, its `modules` (the FX2 chooser, in row order)
and, optionally, `fx1`. `make modules` lists every
module key and the compatibility matrix. See the
[composing guide](https://github.com/sambanks/octabam/blob/main/docs/guide/COMPOSING.md)
for every field and the costs.

Select **USB** for USB MIDI and optional audio in either direction. Its
TRACKS, MAIN, CUE, MASTER, IN and MIDI settings are changed on the unit in PROJ > BRAIN > SETTINGS
and take effect at the next boot. A remix can fix one with a `Pin`.

## 3. Record and check the remix

Add `remixes/community/<name>/README.md` describing what the remix includes. Update the remix index, then run:

```bash
make docs
make check REMIX=<name>
```

`make check` builds the image, runs its gates and boots it under the port.
It is the minimum check before flashing; a successful build alone does not
show that the remix works on hardware.

## 4. Build the image and install it

The web builder builds only the released remixes, so build yours from source:

```bash
make image REMIX=<name> BUILD=1
```

This writes `out/OCTATRACK_OCTABAM1.bin` (the card image), `out/OCTATRACK_OS1.40C_OCTABAM1.syx`
(the MIDI image) and an `.RMX` file; the
[build guide](https://github.com/sambanks/octabam/blob/main/docs/guide/BUILDING.md) says what
`BUILD` is. Install them as in [Install the image](web-builder.md#install-the-image).

## Next steps

- [Octabam v0.5](remix-octabam.md) is the ready-made selection;
  [Octabam Verbs](remix-octabam-verbs.md) and [Octabam Bus](remix-octabam-bus.md) are two more.
- [Community Remixes](reference/community.md) lists the remixes other contributors have shared;
  open a pull request with your `remixes/community/<name>/` to add yours.
- [Developer documentation](https://github.com/sambanks/octabam/blob/main/CONTRIBUTING.md)
  and [writing a module](https://github.com/sambanks/octabam/blob/main/docs/contributing/MODULES.md)
  if you want to add a new feature or share a module.
