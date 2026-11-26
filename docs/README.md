# Documentation

This index groups the repository's documentation by audience. Musicians looking
for usage instructions should read
[the manual](https://sambanks.github.io/octabam/); the files listed here cover
building from source and contributing. Project terminology is defined in
[GLOSSARY.md](GLOSSARY.md).

Individual modules, remixes, and tools also have their own READMEs at
`modules/<name>/README.md`, `remixes/<name>/README.md`, and
`tools/<dir>/README.md`. See [modules/README.md](../modules/README.md) and
[remixes/README.md](../remixes/README.md) for the generated indexes.

## Build and flash from source

| Document | Description |
|---|---|
| [guide/BUILDING.md](guide/BUILDING.md) | Step-by-step guide from a fresh machine to flashing a unit and returning to stock |
| [guide/COMPOSING.md](guide/COMPOSING.md) | How to choose modules and write a custom `remix.py` |

## Write a module

| Document | Description |
|---|---|
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Contribution rules and pull request workflow |
| [contributing/MODULES.md](contributing/MODULES.md) | Writing a module: manifests, module types, and DSP/ColdFire declarations |
| [contributing/TESTING.md](contributing/TESTING.md) | Verification gates, `make check`, `make reach`, and CI |
| [contributing/TRAPS.md](contributing/TRAPS.md) | Known pitfalls encountered during development and the gates that catch them |
| [contributing/FAILURE_MODES.md](contributing/FAILURE_MODES.md) | Hardware faults observed on a unit: symptoms, causes, and fixes |
| [contributing/PLACEMENT.md](contributing/PLACEMENT.md) | Where module code is placed and how much memory is available |
| [contributing/DEMAND_LOADER.md](contributing/DEMAND_LOADER.md) | How effects are loaded into the DSP on demand while a track uses them |
| [contributing/COSTS.md](contributing/COSTS.md) | Per-effect DSP cycle costs and worst-case remix budgets |
| [contributing/CYCLE_SCAN.md](contributing/CYCLE_SCAN.md) | Breakdown of where each effect spends its DSP cycles |
| [contributing/DSP_AUDIT.md](contributing/DSP_AUDIT.md) | Techniques for smaller, faster DSP code and per-module audit notes |
| [contributing/COLDFIRE_FORMS.md](contributing/COLDFIRE_FORMS.md) | ColdFire instruction forms allowed in modules |
| [contributing/TOOLING.md](contributing/TOOLING.md) | Overview of build and verification tools by stage |
| [contributing/SCREENSHOTS.md](contributing/SCREENSHOTS.md) | How to capture screenshots for the manual |
| [../tools/site/README.md](../tools/site/README.md) | How the manual site and web builder are generated |
| [../AGENTS.md](../AGENTS.md) | Working rules for contributors and coding agents |

## Test on a unit

| Document | Description |
|---|---|
| [contributing/HARDWARE_TESTING.md](contributing/HARDWARE_TESTING.md) | Testing a remix on your Octatrack and recovering from failures |
| [contributing/HARDWARE_MATRIX.md](contributing/HARDWARE_MATRIX.md) | Running a remix across multiple configurations over USB |
| [contributing/HARDWARE_SUITE.md](contributing/HARDWARE_SUITE.md) | Automated hardware test suite for the `octabam` remix |
| [contributing/HARDWARE_MANUAL.md](contributing/HARDWARE_MANUAL.md) | Manual hardware checks: front panel, listening tests, CF card, and MIDI controllers |

## Specs

Contracts between modules, covering what each service guarantees and what
clients must do. Start with [specs/README.md](specs/README.md).

| Document | Description |
|---|---|
| [specs/SHARED_SITES.md](specs/SHARED_SITES.md) | Sharing a stock code site between modules: choosing STORE, EVENTS, HOOKS, or `Override` |
| [specs/STORE.md](specs/STORE.md) | Saving and loading module data alongside a project |
| [specs/EVENTS.md](specs/EVENTS.md) | Transport, MIDI, editor, and copy events |
| [specs/HOOKS.md](specs/HOOKS.md) | Shared hook registry, sites, and attached modules |
| [specs/BRAIN.md](specs/BRAIN.md) | Settings system: declarations, layers, and on-card file formats |

## Tools

| Document | Description |
|---|---|
| [../tools/remix/README.md](../tools/remix/README.md) | Remix engine: schema, registry, claim ledger, and DRAM runtime |
| [../tools/harness/README.md](../tools/harness/README.md) | Local DSP audio rendering and measurement harness |
| [../tools/emu/README.md](../tools/emu/README.md) | Emulators: the full-unit port and the Unicorn harness |
| [../tools/panel/README.md](../tools/panel/README.md) | Virtual front panel; [KEYMAP.md](../tools/panel/KEYMAP.md) documents its keyboard shortcuts |
| [../tools/ghidra/README.md](../tools/ghidra/README.md) | Ghidra project covering the OS and both DSP payloads |

## The firmware, reverse-engineered

Technical notes on how stock OS 1.40C works. Start with
[firmware/ARCHITECTURE.md](firmware/ARCHITECTURE.md).

| Document | Subject |
|---|---|
| [firmware/CHIP.md](firmware/CHIP.md) | Hardware chips and cycle budget |
| [firmware/DSP.md](firmware/DSP.md) | DSP programs |
| [firmware/BOOT.md](firmware/BOOT.md) | Reset, boot sequence, and OS entry |
| [firmware/KERNEL.md](firmware/KERNEL.md) | Operating system kernel |
| [firmware/TABLES.md](firmware/TABLES.md) | Parameter tables |
| [firmware/PARAM_PAGES.md](firmware/PARAM_PAGES.md) | Parameter pages and how values are sent to the DSP |
| [firmware/MAINMENU.md](firmware/MAINMENU.md) | Main menus |
| [firmware/PANEL.md](firmware/PANEL.md) | Keys, LEDs, and display |
| [firmware/PARTS.md](firmware/PARTS.md) | Parts and pattern changes |
| [firmware/STEP_LOCKS.md](firmware/STEP_LOCKS.md) | Parameter locks |
| [firmware/LFO.md](firmware/LFO.md) | LFOs |
| [firmware/LEVEL_LAW.md](firmware/LEVEL_LAW.md) | Level scaling law |
| [firmware/MIDI.md](firmware/MIDI.md) | MIDI input and output |
| [firmware/MIDI_TRACKS.md](firmware/MIDI_TRACKS.md) | MIDI tracks |
| [firmware/MIDI_SCENES.md](firmware/MIDI_SCENES.md) | Scenes on MIDI tracks |
| [firmware/RECORDER.md](firmware/RECORDER.md) | Track recorders |
| [firmware/SAMPLE_SAVE.md](firmware/SAMPLE_SAVE.md) | Saving samples |
| [firmware/STORAGE.md](firmware/STORAGE.md) | CF card and filesystem layer |
| [firmware/STEM_REC.md](firmware/STEM_REC.md) | Stock routines used by STEM REC |
| [firmware/COLDFIRE_DELAY.md](firmware/COLDFIRE_DELAY.md) | ColdFire delay routine |
| [firmware/REPITCH.md](firmware/REPITCH.md) | REPITCH |

## Proposals

See [proposals/remixes/](proposals/remixes/README.md) for proposed remixes.

Release history is recorded in [../CHANGELOG.md](../CHANGELOG.md).
