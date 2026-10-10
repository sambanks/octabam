# Documentation

Where each doc is, by who reads it. A module's own page is
`modules/<name>/README.md`, a remix's `remixes/<name>/README.md`, a tool's
`tools/<dir>/README.md`.

## Building and flashing a remix

| doc | what it is |
|---|---|
| [guide/BUILDING.md](guide/BUILDING.md) | what to install (macOS, Linux/WSL2), the toolchain, your own OS 1.40C, building an image, flashing from the card or over MIDI, after the flash, recovery, back to stock |
| [../remixes/README.md](../remixes/README.md) | the remixes you can flash, with where each has run |
| [guide/REMIXER.md](guide/REMIXER.md) | composing your own remix: the `make remix` TUI, or a `remix.py` by hand |

## Writing a module or changing the build

| doc | what it is |
|---|---|
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | the contract: the one rule, your first PR, the oracle rule, the gates before a PR |
| [contributing/MODULES.md](contributing/MODULES.md) | writing a module: manifests, descriptors, DSP and ColdFire declarations, the ledger |
| [contributing/PLACEMENT.md](contributing/PLACEMENT.md) | where a module's code goes and what is free, measured |
| [contributing/TESTING.md](contributing/TESTING.md) | every gate, what it proves and cannot see; `make check`, `make reach`, shards, `make accept`, bit-identity, CI |
| [contributing/TOOLING.md](contributing/TOOLING.md) | every tool by pipeline stage, and which README each tool directory has |
| [contributing/FAILURE_MODES.md](contributing/FAILURE_MODES.md) | what has gone wrong on a unit: symptom, cause, fix, the gate that catches it |
| [../AGENTS.md](../AGENTS.md) | working rules and the traps that have cost real work (for people and coding agents) |

## The tools

| doc | what it is |
|---|---|
| [../tools/remix/README.md](../tools/remix/README.md) | the remix engine: schema, registry, ledger, the DRAM platform, the remixer's internals |
| [../tools/harness/README.md](../tools/harness/README.md) | hearing and measuring the DSP side locally: `dsp_host`, `send_probe`, `rig_render`, `pressure`, the stress project |
| [../tools/emu/README.md](../tools/emu/README.md) | the ColdFire emulators: the port (`ot_emu`) and Tier-0 (Unicorn) |
| [../tools/panel/README.md](../tools/panel/README.md) | the virtual front panel over the port; [KEYMAP.md](../tools/panel/KEYMAP.md) the key and LED map |
| [../tools/ghidra/README.md](../tools/ghidra/README.md) | the Ghidra project over the OS and both DSP payloads |

## The firmware, reverse-engineered

[firmware/](firmware/): OS 1.40C as measured here. Start at
[ARCHITECTURE.md](firmware/ARCHITECTURE.md); [CHIP.md](firmware/CHIP.md)
is the silicon and the cycle budget, [DSP.md](firmware/DSP.md) the audio
DSP, and the rest one subsystem each (kernel, tables, parameter pages,
menus, panel, MIDI, LFO, level law, recorder, sample save, storage,
the MIDI tracks' setup record, writers, outgoing MIDI and CTRL labels in [MIDI_TRACKS.md](firmware/MIDI_TRACKS.md), Parts and pattern changes in [PARTS.md](firmware/PARTS.md), step locks, the ColdFire delay routine in [COLDFIRE_DELAY.md](firmware/COLDFIRE_DELAY.md),
REPITCH in [REPITCH.md](firmware/REPITCH.md)).

## Proposals

[proposals/](proposals/): [BRAIN.md](proposals/BRAIN.md), the design for
settings, defaults and templates (6 Oct 2026, not implemented), and the two
OTX documents it starts from, nordseele's shared settings store (draft, not
implemented): [OTX_PROJECT_PROPOSAL.md](proposals/OTX_PROJECT_PROPOSAL.md)
and [OTX_MODULE_GUIDELINES.md](proposals/OTX_MODULE_GUIDELINES.md).

[proposals/remixes/](proposals/remixes/README.md): remix proposals, each
taken on hardware to verified stable before it lands under `remixes/`.

## History

[../CHANGELOG.md](../CHANGELOG.md) has one entry per image that reached a
unit. Records that were closed and removed are cited in place as
`git show <sha>:<path>`.
