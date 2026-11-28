# Build Your Own Remix

You can build a custom remix from any compatible combination of modules in
octabam. A remix defines which modules are included and which effects appear in
the FX1 and FX2 menus. If you pick conflicting modules, the build stops and
names the conflict.

This page covers combining existing modules. If you want to write or port a new
module, start with the
[developer documentation](https://github.com/sambanks/octabam/blob/main/CONTRIBUTING.md)
and the
[module author guide](https://github.com/sambanks/octabam/blob/main/docs/contributing/MODULES.md).

## 1. Prepare the build environment

Follow the
[build guide](https://github.com/sambanks/octabam/blob/main/docs/guide/BUILDING.md)
to install the toolchain and unpack your copy of OS 1.40C.

## 2. Select modules and effects

Copy an existing `remix.py` (such as `remixes/octabam/remix.py`) into a new
directory at `remixes/community/<name>/`. Name it after yourself or its purpose
rather than `octabam-*`. Edit `name`, `modules` (which sets the FX2 chooser in
row order), and optionally `fx1`. Run `make modules` to list all module keys and
the compatibility matrix. See the
[composing guide](https://github.com/sambanks/octabam/blob/main/docs/guide/COMPOSING.md)
for all available fields and DSP word costs.

Include **USB** if you want USB MIDI and optional USB audio in either direction.
Its TRACKS, MAIN, CUE, MASTER, IN, and MIDI settings can be changed on the unit
under **PROJ → BRAIN → SETTINGS** (taking effect on the next boot), or locked
to a fixed value in your remix with `Pin`.

## 3. Record and check the remix

Add a `remixes/community/<name>/README.md` summarizing what the remix includes,
update the remix index, and run the verification suite:

```bash
make docs
make check REMIX=<name>
```

`make check` builds the image, runs all verification gates, and boots it in the
emulator. Treat it as the minimum bar before flashing; assembling cleanly does
not guarantee that a remix behaves properly on hardware.

## 4. Build the image and install it

Because the web builder only builds published remixes, build custom remixes from
source:

```bash
make image REMIX=<name> BUILD=1
```

This creates `out/OCTATRACK_OCTABAM1.bin` (CF card image),
`out/OCTATRACK_OS1.40C_OCTABAM1.syx` (MIDI image), and an `.RMX` file. See the
[build guide](https://github.com/sambanks/octabam/blob/main/docs/guide/BUILDING.md)
for details on the `BUILD` tag, and follow
[Install the image](web-builder.md#install-the-image) to install.

## Next steps

- Ready-made remixes: [Octabam v0.6](remix-octabam.md),
  [Octabam Verbs](remix-octabam-verbs.md), and
  [Octabam Bus](remix-octabam-bus.md).
- Browse [Community Remixes](reference/community.md) shared by other users, or
  open a pull request with your `remixes/community/<name>/` directory to share
  yours.
- Read the
  [developer documentation](https://github.com/sambanks/octabam/blob/main/CONTRIBUTING.md)
  and
  [writing a module](https://github.com/sambanks/octabam/blob/main/docs/contributing/MODULES.md)
  if you want to create or contribute a new feature.
