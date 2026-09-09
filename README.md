# octabam

**A remixer for the Elektron Octatrack's operating system.** Pick the
modifications you want — the community's and this project's own — and build
them into one firmware image from your own copy of the stock OS.

The Octatrack runs OS 1.40C on a ColdFire CPU and a two-core DSP. Several
people modify it: new effects, MIDI scene locks, 256 Kits per project, bug
fixes. Each started from the same reverse-engineering and each built their
own way, so no two of them could share a unit. octabam is the common
toolkit: **a modification is a module, a selection of modules is a remix,
and the build composes a remix into an image** — placing code, wiring hooks
by symbol, refusing collisions by name, and proving every port against its
author's own build byte for byte.

No firmware is distributed here, and none may be. You supply your own
1.40C; every image is derived from it, reproducibly, on your machine.

---

## What it carries

**From the community**, built from the authors' own repositories:

| module | author | what it does | how it is built |
|---|---|---|---|
| **MIDI SCENES** | [bkkbrls-del/midisc](https://github.com/bkkbrls-del/midisc) | per-scene parameter locks driven over MIDI — a second lock table the panel never had | his sources (a git submodule, GNU-as form), seven units linked into DRAM, 35 hooks; every region proven equal to his own encoder's bytes |
| **OCTAKIT** | [emuyia/ems-octakit](https://github.com/emuyia/ems-octakit) | 256 Kits per Project in place of 64 bank-tied Parts, with names, copy/paste, undo, and migration of old projects | her recipe (a submodule) compiled, packed and appended by the build; stock + her writes + her append reproduces her own OS image exactly |
| **LOFI AMF FIX** | [bryantysinger/octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt) | the stock LO-FI's AMF knob jumps the pitch backwards at certain settings; with the fix it sweeps the way the knob says it should | two asserted pokes on the stock effect's own code, disassembled against stock (the technical story is in `modules/lofi-amf-fix/README.md`) |

**From this project** — the DSP effects it began as, and the ColdFire
patches that grew around them:

| | |
|---|---|
| **BusVerb / BusDelay / Send** | a cross-core send bus: one reverb and one multi-mode delay serve all eight tracks, delay → reverb in series — a route the stock firmware has no path for. Hardware-confirmed. |
| **Six inserts** | WarpFold, Ripple, Rungs, Streamz, BodeShift, Nimbus — Mutable-Instruments-flavoured per-track effects that stack. Verified by local render; never flashed. |
| **Tempo sync, CC→page 2, the bus screen, menu shortcut** | ColdFire patches: a tempo-division TIME dial, MIDI CC reaching page-2 knobs, a MAIN MENU editor for both engines. On the unit. |
| **Hello World / Hello DRAM** | the two reference modules — one DSP knob, one DRAM unit — small enough to read in one sitting, kept building as canaries. |

`make modules` prints the authoritative index, the compatibility matrix
(which ColdFire-side modules can share an image, from the same check the
build makes) and every remix. A README is a copy of that; when they
disagree, the tool is right.

## Quick start

```bash
make setup          # toolchain: DSP56300 assembler + emulator, m68k-elf, firmware tool (macOS + Homebrew)
make os             # download the official 1.40C — your own copy
make recon          # unpack it -> out/raw/section_3_MAIN_OS.bin
make modules        # what exists, what composes with what, the remixes
make check REMIX=ported      # MIDI SCENES + LOFI AMF FIX: build, gate, boot under the emulator
make image REMIX=ported BUILD=101   # repack as a card-flashable .bin, version-stamped
```

`git submodule update --init` fetches the community sources the first time.
`make remix` opens the TUI remixer (`make emu-setup` provisions it): the
library of everything that could be in an image, the choosers the unit
will show, every effect auditionable by ear, and the built image booted in
the local ColdFire emulator. `docs/remixer/REMIXER.md` is its manual.

### What ships as a remix

| remix | contains | why |
|---|---|---|
| **`ported`** | MIDI SCENES + LOFI AMF FIX | every community mod known to coexist, together — the pick-and-choose proof |
| **`octakit`** / **`octakit-fix`** | Em's Octakit, alone / with the LO-FI fix | her mod through this pipeline; must reproduce her identities |
| **`midi-scenes`** | MIDI SCENES alone | his mod through this pipeline |
| **`bamsep26`** (default) | the bus rig: both engines, send, stations, tempo sync, menu shortcut | what goes on Sam's unit |
| **`bus`** | BusVerb + BusDelay + Send + tempo sync | the plain two-server image; the bit-identity gate's subject |
| **`mutables`** | five inserts | a card of stacking effects, no servers |
| **`hello`** / **`hello-dram`** | one module each | the reference minimal builds |

⚠️ **OCTAKIT and MIDI SCENES cannot share an image yet** — both hook the
same stock routine (`apply_part`, `0x40009094`), and beyond the hook his
code addresses the Part window that hers replaces. The build refuses the
pair by name; detour chaining and a Kits-aware scenes port are the two
halves of the fix (`PLAN.md`).

## How it works, in one screen

```
modules/<name>/manifest.py   what a module IS and what it claims   (yours, or a pointer into an author's repo)
remixes/<name>.py            which modules, in which chooser order
tools/remix/ledger.py        refuses two modules that claim one address, hook, id or buffer — by name
tools/build/build_bus.py     THE build: assembles, links, places, wires, verifies -> out/mainos_bus.bin
tools/verify/*               the gates: oracles, the boot under the ColdFire port, menu, cycles, identity
```

A module's code lands in one of three places, and the build decides which
bytes go where — a module declares what it is, not an address:

| class | declared as | where |
|---|---|---|
| ROM cave | `CavePatch` — a `.s` source, or ratified hex | one of the OS image's free zero runs, ~8 KB total shared by everyone |
| **DRAM unit** | `Linked(..., dram=True)` — a GNU-as unit | linked with every other DRAM unit in the remix into one runtime, packed, appended behind octabam's loader, depacked at boot into a **10 MB reserve carved off stock's 85.5 MB sample/recorder pool** — the placement two community authors have proven on hardware |
| appended runtime | `Runtime` — a recipe (Octakit's `firmware.json`) | its own reserve of the same pool (`ArenaReserve`), as a second payload of the same loader |

The OS-image edits every class needs — a detour at a stock instruction, a
poke, a grown table — are `Detour`, `Poke`, `TableGrow`, wired by symbol
and asserted against stock before a byte is written. `docs/remixer/PLACEMENT.md`
is the map: what is free, what was measured, and the one retraction.

**A port is a proof.** The build re-links every unit at the author's own
address and compares, rebuilds Em's runtime to the identities her recipe
pins, and refuses on any drift. What the community gets is not a copy of
their work but their work, placed by a build that can see everyone
else's. What the DSP side has always had — `make check`, the local render
at ~6× real time, the 26-configuration bit-identity gate for changes to
the build itself — the ColdFire side now has too: every DRAM remix boots
under the ColdFire port and its window is read back against the linked
image before the image is called built.

## Bringing your mod in

Two shapes, both worked examples in the tree:

- **Build from your repository.** Your repo becomes a submodule under
  `modules/<name>/upstream`; the manifest points `Linked` units at your
  `.s` files (or a `Runtime` at your recipe). You keep developing where
  you are; an update here is a submodule bump plus your oracle still
  holding. `modules/midi-scenes` and `modules/octakit` are this.
- **Write the module here.** Copy `modules/_template_cf/` (ColdFire) or
  `modules/_template/` (a DSP effect), read `modules/hello-dram/` or
  `modules/hello/`, follow `docs/remixer/MODULES.md`.

What makes either painless: code in GNU-as with symbols rather than
absolute addresses, an artifact of your own build to prove against, and
never an Elektron byte in your repo — `.incbin` what you need from the
user's stock image at build time, as Octakit does. **[CONTRIBUTING.md](CONTRIBUTING.md)**
has the whole contract, the gates and the etiquette.

## Hearing and checking without a flash

A flash is manual and slow, so the project is built around not needing one
to make a judgement. The DSP side renders locally on the real assembled
instruction stream (`make render`, `make render-rig`, `make reverb
IN=loop.wav`; `docs/remixer/HARNESS.md`); the ColdFire side boots the built
image under a headless port of the machine (`make emu-cf`;
`docs/firmware/COLDFIRE_PORT.md`) and, for the firmware's own screens, under
Unicorn (`docs/remixer/EMU.md`). `make check` runs everything that can be
checked without hardware. It is the floor, not the ceiling: what the
emulators structurally cannot see — caches, the recorder, cross-core
timing — is listed beside every gate that is blind to it.

## ⚠️ Before you flash anything

**Writing a non-official OS to an Octatrack can leave it unusable, and it
puts your warranty in question.** Nothing here is endorsed by, supported by,
or affiliated with Elektron. If you flash a modified image you do so
entirely at your own risk. `docs/remixer/FLASHING.md` has the recovery
path — read it *before* you need it — and `docs/remixer/FAILURE_MODES.md`
the register of what has gone wrong on a unit and why.

**Nothing built by the new ColdFire pipeline has been flashed yet** (10 Sep
2026). The community authors' own builds are what has run on hardware;
this project's bus engines and ColdFire patches are on Sam's unit. Back up
projects before flashing anything that changes them (Octakit migrates
Parts to Kits on load; downgrading may lose Kit data — her warning, and it
applies).

**MKI and MKII run the same 1.40C image** (hash-verified), so an image
should run on either; everything here has only ever been *tested* on an
MKII.

**No Elektron binary is redistributed here — and none may be.** `make os`
downloads your own copy; the tooling regenerates Elektron's image
byte-for-byte before it will produce a modified one. The same rule binds
you onward: **a built `.bin` or `.syx` contains Elektron's OS — do not
share built images.** Share the repo; everyone builds their own.

*Octatrack* and *Elektron* are trademarks of Elektron Music Machines MAV
AB, used here only to identify the hardware this project targets.

## Repository layout

```
PLAN.md            Read this first: the programme, where it stands, the ground, the work order.
CONTRIBUTING.md    The module contract, the oracle rule, the gates, submodule etiquette.
modules/           The contributions -- one directory each. This is the product.
remixes/           Named selections of modules, in chooser order.
tools/remix/       The toolkit: schema, registry, ledger, the loader, the DRAM platform, the TUI.
tools/build/       The image build (build_bus.py) and the tools that understand the OS layout.
tools/verify/      The gates.
tools/harness/     Hear and measure the DSP side locally (dsp_host, send_probe, rig_render).
tools/emu/         The ColdFire emulators: the headless port (ot_emu) and the Unicorn bring-up.
tools/hw/          The unit and its card: MIDI control, capture, project files, MIDI flashing.
tools/patches/     Local patches to the vendored toolchains.
scripts/           Toolchain setup, OS fetch and recon, the bit-identity gate.
dsp/               Shared DSP infrastructure: the null stub and the probes.
docs/remixer/      Using and extending the remixer: MODULES, PLACEMENT, REMIXER, TOOLING, FLASHING.
docs/firmware/     The firmware, reverse-engineered: ARCHITECTURE, DSP, CHIP, PARAM_PAGES, MAINMENU, the port.
docs/effects/      The effects programme: REVERB, BUS, XBUS, VOICING, CAPTURE, FLASHPLAN.
docs/history/      Closed records, kept for provenance -- including the effects-era PLAN.
```

## Credit

**Em** ([emuyia](https://github.com/emuyia)) designed Octakit, and with it
the loader-appended DRAM runtime that octabam adopted whole as its
large-payload placement: her early loader, stage, hash gate and
post-clear relocation are the measured reverse-engineering this platform
stands on; `tools/remix/loader.S` is derived from hers with attribution.
Her repository explicitly invites being used as a submodule to combine
with other efforts; that is what this is.

**bkkbrls-del** wrote midisc and was game for its rebuild in GNU-as form;
the `octabam-gas` branch waits on his own finishing touches before it goes
back to him as a PR.

**Bryan T** answered the project's oldest open question — where the stock
Echo Freeze Delay lives (in ColdFire SDRAM, eight 1.4 MB rings, the very
region the DRAM measurement then found being cleared at boot) — along with
the timestretch architecture, the DSP data-table atlas and the recorders'
control path, recorded with its own confidence markers in
`docs/firmware/EXTERNAL.md`. He also contributed `modules/hello`, and the AMF
fix is his.

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
