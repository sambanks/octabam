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

Copy an existing `remixes/<name>/remix.py` and edit its `modules` (the FX2
chooser, in row order) and, optionally, `fx1`. `make modules` lists every
module key and the compatibility matrix. See the
[composing guide](https://github.com/sambanks/octabam/blob/main/docs/guide/COMPOSING.md)
for every field and the costs.

Select **USB** for USB MIDI and optional audio in either direction. Its
TRACKS, MAIN, CUE, MASTER, IN and MIDI settings are changed on the unit in PROJ > BRAIN > SETTINGS
and take effect at the next boot. A remix can fix one with a `Pin`.

## 3. Record and check the remix

Add `remixes/<name>/README.md` describing what the remix includes and what
has been tested. Update the remix index, then run:

```bash
make docs
make check REMIX=<name>
```

`make check` builds the image, runs its gates and boots it under the port.
It is the minimum check before flashing; a successful build alone does not
show that the remix works on hardware. For image creation and installation,
continue to [Build and Install](web-builder.md#install-the-image).

## Next steps

- [Octabam v0.2](remix-octabam.md) is the ready-made selection.
- [Developer documentation](https://github.com/sambanks/octabam/blob/main/CONTRIBUTING.md)
  and [writing a module](https://github.com/sambanks/octabam/blob/main/docs/contributing/MODULES.md)
  if you want to add a new feature or share a module.
