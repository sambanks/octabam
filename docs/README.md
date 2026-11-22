# Documentation

Every doc, by who reads it. Musicians want
[the manual](https://sambanks.github.io/octabam/); everything here is for
building from source and contributing. Terms are in
[GLOSSARY.md](GLOSSARY.md).

Each module, remix and tool also has its own page:
`modules/<name>/README.md`, `remixes/<name>/README.md` and
`tools/<dir>/README.md`. The indexes are [modules/README.md](../modules/README.md)
and [remixes/README.md](../remixes/README.md).

## Build and flash from source

| doc | what it is |
|---|---|
| [guide/BUILDING.md](guide/BUILDING.md) | from a fresh machine to a flashed unit, and back to stock |
| [guide/COMPOSING.md](guide/COMPOSING.md) | choosing your own modules: writing a `remix.py` |

## Write a module

| doc | what it is |
|---|---|
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | the rules every pull request follows, and your first one |
| [contributing/MODULES.md](contributing/MODULES.md) | how to write a module: the manifest, the kinds of module, DSP and ColdFire declarations |
| [contributing/TESTING.md](contributing/TESTING.md) | every gate and what it checks; `make check`, `make reach`, CI |
| [contributing/TRAPS.md](contributing/TRAPS.md) | mistakes that have cost real work, and the gate that now catches each |
| [contributing/FAILURE_MODES.md](contributing/FAILURE_MODES.md) | faults seen on a unit: symptom, cause, fix |
| [contributing/PLACEMENT.md](contributing/PLACEMENT.md) | where a module's code goes, and what memory is free |
| [contributing/DEMAND_LOADER.md](contributing/DEMAND_LOADER.md) | how effects are loaded into the DSP while a track uses them |
| [contributing/COSTS.md](contributing/COSTS.md) | what each effect costs in DSP time, and a remix's worst case |
| [contributing/CYCLE_SCAN.md](contributing/CYCLE_SCAN.md) | where each effect spends its DSP cycles |
| [contributing/DSP_AUDIT.md](contributing/DSP_AUDIT.md) | techniques for shorter, cheaper DSP code, and findings per module |
| [contributing/COLDFIRE_FORMS.md](contributing/COLDFIRE_FORMS.md) | the ColdFire instruction forms a module may use |
| [contributing/TOOLING.md](contributing/TOOLING.md) | every tool, by stage of the build |
| [contributing/SCREENSHOTS.md](contributing/SCREENSHOTS.md) | capturing the manual's screenshots |
| [../tools/site/README.md](../tools/site/README.md) | how the manual site and the web builder are generated |
| [../AGENTS.md](../AGENTS.md) | working rules for coding agents and people |

## Test on a unit

| doc | what it is |
|---|---|
| [contributing/HARDWARE_TESTING.md](contributing/HARDWARE_TESTING.md) | testing a remix on your own Octatrack, and recovering from a failure |
| [contributing/HARDWARE_MATRIX.md](contributing/HARDWARE_MATRIX.md) | running one remix in many configurations over one USB cable |
| [contributing/HARDWARE_SUITE.md](contributing/HARDWARE_SUITE.md) | the `octabam` remix's automated hardware suite |
| [contributing/HARDWARE_MANUAL.md](contributing/HARDWARE_MANUAL.md) | the checks done by hand: panel gestures, listening, the card, MIDI controllers |

## Specs

The contracts between modules: what is guaranteed, and what a client must
do. [specs/README.md](specs/README.md).

| doc | what it is |
|---|---|
| [specs/SHARED_SITES.md](specs/SHARED_SITES.md) | two modules on one stock site: which of STORE, EVENTS, HOOKS or `Override` to use |
| [specs/STORE.md](specs/STORE.md) | saving and loading a module's data with the project |
| [specs/EVENTS.md](specs/EVENTS.md) | transport, MIDI, editor and copy events |
| [specs/HOOKS.md](specs/HOOKS.md) | every shared hook, its site and the modules on it |
| [specs/BRAIN.md](specs/BRAIN.md) | settings: declarations, layers, files and their format |

## Tools

| doc | what it is |
|---|---|
| [../tools/remix/README.md](../tools/remix/README.md) | the remix engine: schema, registry, ledger, the DRAM platform |
| [../tools/harness/README.md](../tools/harness/README.md) | hearing and measuring DSP code locally |
| [../tools/emu/README.md](../tools/emu/README.md) | the emulators: the port and the Unicorn harness |
| [../tools/panel/README.md](../tools/panel/README.md) | the virtual front panel; [KEYMAP.md](../tools/panel/KEYMAP.md) maps its keys |
| [../tools/ghidra/README.md](../tools/ghidra/README.md) | the Ghidra project over the OS and both DSP payloads |

## The firmware, reverse-engineered

How OS 1.40C works. Start at [firmware/ARCHITECTURE.md](firmware/ARCHITECTURE.md).

| doc | subject |
|---|---|
| [firmware/CHIP.md](firmware/CHIP.md) | the chips, and the cycle budget |
| [firmware/DSP.md](firmware/DSP.md) | the DSP programs |
| [firmware/BOOT.md](firmware/BOOT.md) | reset, boot and OS entry |
| [firmware/KERNEL.md](firmware/KERNEL.md) | the kernel |
| [firmware/TABLES.md](firmware/TABLES.md) | the parameter tables |
| [firmware/PARAM_PAGES.md](firmware/PARAM_PAGES.md) | parameter pages and what they publish to the DSP |
| [firmware/MAINMENU.md](firmware/MAINMENU.md) | the menus |
| [firmware/PANEL.md](firmware/PANEL.md) | keys, LEDs and the screen |
| [firmware/PARTS.md](firmware/PARTS.md) | Parts and pattern changes |
| [firmware/STEP_LOCKS.md](firmware/STEP_LOCKS.md) | parameter locks |
| [firmware/LFO.md](firmware/LFO.md) | the LFOs |
| [firmware/LEVEL_LAW.md](firmware/LEVEL_LAW.md) | the level law |
| [firmware/MIDI.md](firmware/MIDI.md) | MIDI in and out |
| [firmware/MIDI_TRACKS.md](firmware/MIDI_TRACKS.md) | MIDI tracks |
| [firmware/MIDI_SCENES.md](firmware/MIDI_SCENES.md) | scenes on MIDI tracks |
| [firmware/RECORDER.md](firmware/RECORDER.md) | the recorders |
| [firmware/SAMPLE_SAVE.md](firmware/SAMPLE_SAVE.md) | saving samples |
| [firmware/STORAGE.md](firmware/STORAGE.md) | the card and the file layer |
| [firmware/STEM_REC.md](firmware/STEM_REC.md) | the stock routines STEM REC uses |
| [firmware/COLDFIRE_DELAY.md](firmware/COLDFIRE_DELAY.md) | the ColdFire delay routine |
| [firmware/REPITCH.md](firmware/REPITCH.md) | REPITCH |

## Proposals

[proposals/remixes/](proposals/remixes/README.md): proposed remixes.

[../CHANGELOG.md](../CHANGELOG.md) lists each release.
