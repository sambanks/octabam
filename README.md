# octabam

[![CI](https://github.com/sambanks/octabam/actions/workflows/ci.yml/badge.svg)](https://github.com/sambanks/octabam/actions/workflows/ci.yml)

octabam is a community remixer for the Elektron Octatrack's operating system.
You pick the features you want, and octabam builds them into one firmware
image from your own copy of OS 1.40C. Each feature is a **module**, credited to
its author. A named set of modules is a **remix**.

octabam is unofficial: it is not made, endorsed or supported by Elektron. You
can always go back to the stock OS
([Safety and Recovery](https://sambanks.github.io/octabam/safety.html)).

## Start here

| you want to | read |
|---|---|
| put octabam on your Octatrack | [Build and Install](https://sambanks.github.io/octabam/web-builder.html): build in the browser, then install from the card or over MIDI |
| learn what a feature does | [the manual](https://sambanks.github.io/octabam/) |
| build a remix from source | [docs/guide/BUILDING.md](docs/guide/BUILDING.md) |
| choose your own modules | [docs/guide/COMPOSING.md](docs/guide/COMPOSING.md) |
| see every module | [modules/README.md](modules/README.md) |
| see every remix | [remixes/README.md](remixes/README.md) |
| write a module or port a mod | [CONTRIBUTING.md](CONTRIBUTING.md), then [docs/contributing/MODULES.md](docs/contributing/MODULES.md) |
| look up a term | [docs/GLOSSARY.md](docs/GLOSSARY.md) |
| find any other doc | [docs/README.md](docs/README.md) |

## How it works

```
modules/<name>/manifest.py   one contribution: its code, and what memory, hooks and ids it claims
remixes/<name>/remix.py      a selection of modules, in chooser order
tools/build/build_bus.py     the build: assembles, links, places and wires the code into one image
tools/verify/                the gates: every check a change must pass before it merges
```

A module declares what it is, not where it goes; the build places it. The
build refuses two modules that claim the same memory, hook or effect id, and
names both. A module ported from an existing mod is rebuilt at its author's
address and compared byte for byte with the author's own build.

Everything is checked without hardware. The build runs the whole unit (the
ColdFire, both DSP cores, the card, the panel, MIDI and USB) in an emulator
called **the port** (`tools/emu/`), and renders the DSP side to audio
(`tools/harness/`). CI runs every gate a change reaches on every pull request.
[docs/contributing/TESTING.md](docs/contributing/TESTING.md) says what each
gate checks.

```bash
make modules                 # every module, the compatibility matrix, the remixes
make image REMIX=<name> BUILD=1   # build the image from your own OS 1.40C
make check REMIX=<name>      # build it and run its gates under the port
make panel REMIX=<name>      # a virtual front panel with sound at localhost:8563
```

## No Elektron bytes

No Elektron binary is in this repository, and none may be added. A built
`.bin` or `.syx` contains Elektron's OS, so never share one: share the
repository and let everyone build their own.

*Octatrack* and *Elektron* are trademarks of Elektron Music Machines MAV AB,
used here only to name the hardware this project targets.

## Repository layout

```
modules/           the contributions, one directory each
remixes/           the remixes; remixes/test/ holds one-module remixes for gates
docs/site/         the manual site: hand-written pages, usage fragments, screenshots, the web builder
docs/guide/        building, flashing and composing a remix
docs/contributing/ writing a module, testing, placement, tooling, the trap and failure registers
docs/specs/        the contracts between modules (STORE, EVENTS, HOOKS, BRAIN)
docs/firmware/     the Octatrack firmware, reverse-engineered
tools/             the build, the gates, the emulators, the site generator (docs/contributing/TOOLING.md)
scripts/           toolchain setup and the OS fetch
.github/           CI and the PR and issue templates
```

`AGENTS.md` holds the working rules for coding agents and people.

## Credit

Every module's author is credited in [modules/README.md](modules/README.md)
and in the manual's [Credits](https://sambanks.github.io/octabam/reference/manual/credits.html).

octabam began as a fork of [mxldyn/octamax](https://github.com/mxldyn/octamax)
by Maxolydian, whose reverse engineering of the OS format, memory map and
parameter tables made all of this possible.

**Em** ([emuyia](https://github.com/emuyia)) designed Octakit and the
loader-appended DRAM runtime octabam uses for large modules;
`tools/remix/loader.S` and `tools/remix/pack.py` are derived from hers. KITS
(`modules/kits`) follows Octakit's design and reads its files.

BRAIN's LOAD view follows the LOAD view Hamish Renton
([SamplesAndSnacks](https://github.com/SamplesAndSnacks)) designed for the
Machinedrum.

`vendor/` pulls in [dsp56300](https://github.com/dsp56300/dsp56300),
[mc68k](https://github.com/joelanders/mc68k-md-mm) and
[elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool).

## License

[MIT](LICENSE) for this repository's own code and documentation. It does not
cover Elektron's firmware, which is not distributed here, or the
repositories referenced as submodules, which stay under their authors' terms.
[THIRD_PARTY.md](THIRD_PARTY.md) lists every transcribed DSP source, submodule
and vendored tool, with its licence.
