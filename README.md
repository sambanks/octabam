# octabam

> **A personal research project, shared in case it is useful to you.** I
> work on this for my own unit and publish it so others can build on it.
> Pull requests are very welcome — a module, a port of someone's mod, a
> fix, a doc correction. Issues and feature requests are not something I
> can take on — this is a spare-time project and the queue is already my
> own. If there is something you want the remixer to do, the way to get
> it is to build it (`CONTRIBUTING.md`, `docs/remixer/MODULES.md`) and
> send the PR; I will gladly review it.

A remixer for the Elektron Octatrack's operating system: pick the
modifications you want — the community's and this project's own — and build
them into one firmware image from your own copy of OS 1.40C.

A modification is a **module** (`modules/<name>/`), a selection of modules
is a **remix** (`remixes/<name>.py`), and `make image REMIX=<name>` composes
a remix into a card-flashable image: placing code, wiring hooks by symbol,
refusing collisions by name, and proving every ported module against its
author's own build byte for byte. No firmware is distributed here; every
image is derived from the user's own 1.40C on the user's machine.

**[docs/remixes/BUILDING.md](docs/remixes/BUILDING.md)** is the step-by-step
guide from a fresh machine to a flashed unit.
**[docs/remixes/README.md](docs/remixes/README.md)** lists every remix with
its contents and hardware status.

## What it carries

**From the community**, built from the authors' own repositories:

| module | author | what it does | proof |
|---|---|---|---|
| **MIDI SCENES** | [bkkbrls-del/midisc](https://github.com/bkkbrls-del/midisc) | per-scene parameter locks driven over MIDI | his sources (submodule, GNU-as form), thirteen units in DRAM, 38 detours, 4 pokes; every region equals his encoder's bytes |
| **OCTAKIT** | [emuyia/ems-octakit](https://github.com/emuyia/ems-octakit) | 256 Kits per Project in place of 64 bank-tied Parts, with names, copy/paste, undo, migration of old projects | her recipe (submodule) compiled, packed and appended by the build; stock + her writes + her append reproduces her own OS image |
| **LOFI AMF FIX** | [bryantysinger/octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt) | stock LO-FI's AMF knob jumps the pitch backwards at some settings; two DSP words fix it | both words disassembled against stock |

`ok-ms` (Octakit + MIDI SCENES) ran on hardware on 14 Sep 2026, confirmed by
midisc's author on his own unit.

**From this project:**

| | |
|---|---|
| **BusVerb / BusDelay / Send** | one aux bus: every track's SEND knob → a multi-mode delay → an eight-line FDN reverb, each engine's wet on the track that hosts it. A route the stock firmware has no path for. On Sam's unit. |
| **Spectrum / Character / Modulation** | three FX1 stations replacing FILTER, LO-FI and CHORUS: a filter pedal, a saturation/compressor/width chain, a modulation pedal. On Sam's unit. |
| **Six inserts** | WarpFold, Ripple, Rungs, Streamz, BodeShift, Nimbus: Mutable-Instruments-flavoured per-track effects that stack. Verified by local render; never flashed. |
| **Tempo sync, CC→page 2** | ColdFire patches: BusDelay's TIME reads as a division; MIDI CC 62–73 reach page-2 knobs. On the unit. |
| **The recorder click fix** | three ColdFire caves that remove the click at a recorder loop's seam. On hardware. |
| **Hello World / Hello DRAM** | the two reference modules, one DSP knob and one DRAM unit, kept building as canaries. |

`make modules` prints the index, the compatibility matrix (which ColdFire
modules can share an image, from the same check the build makes; `✓*` is a
pair that needs the named bridge) and every remix.

## Quick start

```bash
git clone --recurse-submodules https://github.com/sambanks/octabam
cd octabam
make setup                          # toolchain (macOS + Homebrew; docs/WSL.md for Linux)
make os && make recon               # your own 1.40C -> out/raw/section_3_MAIN_OS.bin
make image REMIX=ok-ms BUILD=1      # -> out/OCTATRACK_OCTABAM1.bin
```

`make check REMIX=<name>` runs every gate and boots the image under the
local ColdFire emulator. `make remix` opens the TUI remixer
(`docs/remixer/REMIXER.md`).

## How it works

```
modules/<name>/manifest.py   what a module is and what it claims (yours, or a pointer into an author's repo)
remixes/<name>.py            which modules, in which chooser order
tools/remix/ledger.py        refuses two modules that claim one address, hook, id or buffer, by name
tools/build/build_bus.py     the build: assembles, links, places, wires, verifies -> out/mainos_bus.bin
tools/verify/*               the gates: oracles, the boot under the ColdFire port, menu, cycles, identity
```

A module's code lands in one of three places; the build decides which bytes
go where, and a module declares what it is, not an address:

| class | declared as | where |
|---|---|---|
| ROM cave | `CavePatch`: a `.s` source, or ratified hex | one of the OS image's free zero runs, ~8 KB total shared by everyone |
| DRAM unit | `Linked(..., dram=True)`: a GNU-as unit | linked with every other DRAM unit in the remix into one runtime, packed, appended behind octabam's loader, depacked at boot into a 10 MB reserve carved off stock's 85.5 MB sample/recorder pool |
| appended runtime | `Runtime`: a recipe (Octakit's `firmware.json`) | its own reserve of the same pool, as a second payload of the same loader |

The OS-image edits every class needs — a detour at a stock instruction, a
poke, a grown table — are `Detour`, `Poke`, `TableGrow`, wired by symbol and
asserted against stock before a byte is written. `docs/remixer/PLACEMENT.md`
is the map of what is free and what was measured.

**A port is a proof.** The build re-links every unit at the author's own
address and compares, rebuilds Octakit's runtime to the identities her
recipe pins, and refuses on any drift. `CONTRIBUTING.md` is the contract;
`docs/remixer/MODULES.md` the guide to writing a module.

## Checking without a flash

The DSP side renders locally on the assembled instruction stream (`make
render`, `make render-rig`; `docs/remixer/HARNESS.md`); the ColdFire side
boots the built image under a headless port of the machine (`make emu-cf`;
`docs/remixer/EMU.md`) and, for the firmware's own screens, under
Unicorn (`docs/remixer/EMU.md`). What the emulators cannot see — caches, the
recorder, cross-core timing — is listed beside every gate that is blind to
it.

## Before you flash anything

**Writing a non-official OS to an Octatrack can leave it unusable and puts
your warranty in question.** Nothing here is endorsed by, supported by, or
affiliated with Elektron. `docs/remixer/FLASHING.md` has the recovery path;
`docs/remixer/FAILURE_MODES.md` is the register of what has gone wrong on a
unit and why. Back up projects before flashing anything that changes them
(Octakit migrates Parts to Kits on load; downgrading may lose Kit data).

MKI and MKII run the same 1.40C image (hash-verified). This project's own
effects have only been tested on an MKII; the DRAM platform has run on an
MKI ([octalab](https://github.com/nordseele/octalab-notes), 11 Sep 2026)
and on midisc's author's unit (`ok-ms`, 14 Sep 2026).

**No Elektron binary is redistributed here, and none may be.** A built
`.bin` or `.syx` contains Elektron's OS: do not share built images. Share
the repo; everyone builds their own.

*Octatrack* and *Elektron* are trademarks of Elektron Music Machines MAV
AB, used here only to identify the hardware this project targets.

## Repository layout

```
PLAN.md            what octabam is, where it stands, the work order
CONTRIBUTING.md    the module contract, the oracle rule, the gates, submodule etiquette
modules/           the contributions, one directory each
remixes/           named selections of modules, in chooser order
docs/remixes/      one page per remix, and the build guide
tools/remix/       the toolkit: schema, registry, ledger, the loader, the DRAM platform, the TUI
tools/build/       the image build (build_bus.py) and the tools that understand the OS layout
tools/verify/      the gates
tools/harness/     hear and measure the DSP side locally (dsp_host, send_probe, rig_render)
tools/emu/         the ColdFire emulators: the headless port (ot_emu) and the Unicorn bring-up
tools/hw/          the unit and its card: MIDI control, capture, project files, MIDI flashing
tools/patches/     local patches to the vendored toolchains
scripts/           toolchain setup, OS fetch and recon, the bit-identity gate
dsp/               shared DSP infrastructure: the null stub and the probes
docs/remixer/      using and extending the remixer: MODULES, PLACEMENT, REMIXER, TOOLING, FLASHING
docs/firmware/     the firmware, reverse-engineered: ARCHITECTURE, KERNEL, DSP, CHIP, TABLES, PARAM_PAGES, MAINMENU, PANEL, MIDI, EXTERNAL
docs/effects/      the effects: XBUS (the bus), REVERB, MASTER, PORTS
```

## Credit

**Em** ([emuyia](https://github.com/emuyia)) designed Octakit and the
loader-appended DRAM runtime octabam adopted as its large-payload placement;
`tools/remix/loader.S` is derived from hers with attribution. Her repository
invites use as a submodule to combine with other efforts.

**bkkbrls-del** wrote midisc and rebuilt it in GNU-as form for this
remixer.

**Bryan T** located the stock Echo Freeze delay (ColdFire SDRAM, eight
1.4 MB rings), documented the timestretch architecture, the DSP data-table
atlas and the recorders' control path (`docs/firmware/EXTERNAL.md`),
contributed `modules/hello`, and wrote the AMF fix.

**nordseele**'s octalab is a DRAM module of this remixer and its first
hardware run.

This began as a fork of [mxldyn/octamax](https://github.com/mxldyn/octamax)
by Maxolydian, whose reverse engineering of the OS format, memory map and
parameter tables made any of this reachable; the upstream history is in
this repository's log.

`vendor/` pulls in [dsp56300](https://github.com/dsp56300/dsp56300),
[mc68k](https://github.com/joelanders/mc68k-md-mm) and
[elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool).

## License

[MIT](LICENSE) for this repository's own code and documentation. It does
not extend to Elektron's firmware, which is not distributed here, nor to
the community repositories referenced as submodules, which remain their
authors' under their own terms.
[THIRD_PARTY.md](THIRD_PARTY.md) lists every transcribed DSP source
(Airwindows, JClones, Mutable Instruments, ChowDSP, jpcima, audiojs), the
submodules and the vendored tools, each with its licence.
