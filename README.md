# octabam

[![CI](https://github.com/sambanks/octabam/actions/workflows/ci.yml/badge.svg)](https://github.com/sambanks/octabam/actions/workflows/ci.yml)

octabam is a community firmware remixer for the Elektron Octatrack. You pick the
features you want, and octabam builds them into a single firmware image from
your own copy of OS 1.40C. Each feature is a **module** credited to its author,
and a named set of modules is a **remix**.

octabam is unofficial and is not made, endorsed, or supported by Elektron. You
can return to the stock OS at any time
([Safety and Recovery](https://sambanks.github.io/octabam/safety.html)).

## Start here

| Goal | Document |
|---|---|
| Put octabam on your Octatrack | [Build and Install](https://sambanks.github.io/octabam/web-builder.html): build in your browser, then install from the CF card or over MIDI |
| Learn what a feature does | [The manual](https://sambanks.github.io/octabam/) |
| Build a remix from source | [docs/guide/BUILDING.md](docs/guide/BUILDING.md) |
| Choose your own modules | [docs/guide/COMPOSING.md](docs/guide/COMPOSING.md) |
| Browse all modules | [modules/README.md](modules/README.md) |
| Browse all remixes | [remixes/README.md](remixes/README.md) |
| Write a module or port a mod | [CONTRIBUTING.md](CONTRIBUTING.md), then [docs/contributing/MODULES.md](docs/contributing/MODULES.md) |
| Look up a term | [docs/GLOSSARY.md](docs/GLOSSARY.md) |
| Find another document | [docs/README.md](docs/README.md) |

## How it works

```
modules/<name>/manifest.py   one contribution: its code and the memory, hooks, and ids it claims
remixes/<name>/remix.py      a selection of modules, listed in chooser order
tools/build/build_bus.py     the build: assembles, links, places, and wires modules into an image
tools/verify/                the gates: automated checks a change must pass before merging
```

Modules declare what they need rather than hardcoding where they go, and the
build handles placement. If two modules claim the same memory, hook, or effect
ID, the build fails with an error naming both. When a module is ported from an
existing mod, the build re-links it at the original author's address and
compares the output byte for byte against the author's build.

Changes are tested without hardware. The build boots the full unit (ColdFire
CPU, both DSP cores, CF card, front panel, MIDI, and USB) in an emulator called
**the port** (`tools/emu/`), and renders DSP audio locally (`tools/harness/`).
CI runs all affected gates on every pull request. See
[docs/contributing/TESTING.md](docs/contributing/TESTING.md) for what each gate
checks.

```bash
make modules                      # list modules, compatibility matrix, and remixes
make image REMIX=<name> BUILD=1   # build an image from your own OS 1.40C
make check REMIX=<name>           # build the remix and run its gates under the port
make panel REMIX=<name>           # open a virtual front panel with audio at localhost:8563
```

## No Elektron bytes

This repository contains no Elektron binaries, and none may be added. Because a
built `.bin` or `.syx` file includes Elektron's OS, never distribute one. Share
the repository instead so others can build from their own copy of OS 1.40C.

*Octatrack* and *Elektron* are trademarks of Elektron Music Machines MAV AB,
used here only to identify the target hardware.

## Repository layout

```
modules/           individual feature modules, one directory per module
remixes/           remix definitions; remixes/test/ holds single-module remixes for gates
docs/site/         manual site: hand-written pages, usage fragments, screenshots, and web builder
docs/guide/        guides for building, flashing, and composing remixes
docs/contributing/ contributor docs: writing modules, testing, placement, tooling, traps, and failures
docs/specs/        contracts between modules (STORE, EVENTS, HOOKS, BRAIN)
docs/firmware/     reverse-engineered Octatrack firmware notes
tools/             build scripts, verification gates, emulators, and site generator (docs/contributing/TOOLING.md)
scripts/           toolchain setup and stock OS download scripts
.github/           CI workflows and PR/issue templates
```

See `AGENTS.md` for repository working rules for contributors and coding agents.

## Credit

Module authors are credited in [modules/README.md](modules/README.md) and on the
manual's [Credits](https://sambanks.github.io/octabam/reference/manual/credits.html)
page.

octabam started as a fork of [mxldyn/octamax](https://github.com/mxldyn/octamax)
by Maxolydian, whose reverse engineering of the OS format, memory map, and
parameter tables made this project possible.

**Em** ([emuyia](https://github.com/emuyia)) designed Octakit and the
loader-appended DRAM runtime that octabam uses for large modules.
`tools/remix/loader.S` and `tools/remix/pack.py` are derived from her work, and
KITS (`modules/kits`) follows Octakit's design and reads its files.

BRAIN's LOAD view follows the LOAD view designed by Hamish Renton
([SamplesAndSnacks](https://github.com/SamplesAndSnacks)) for the Machinedrum.

`vendor/` includes [dsp56300](https://github.com/dsp56300/dsp56300),
[mc68k](https://github.com/joelanders/mc68k-md-mm), and
[elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool).

## License

The repository's own code and documentation are released under the
[MIT](LICENSE) license. This does not cover Elektron's firmware (which is not
distributed here) or submodule repositories, which remain under their authors'
licenses. See [THIRD_PARTY.md](THIRD_PARTY.md) for the full list of
transcribed DSP sources, submodules, and vendored tools with their licenses.
