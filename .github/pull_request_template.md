<!-- CONTRIBUTING.md has the contract; "Before you open a PR" has the gates. -->

## What this changes

<!-- The module(s) or tool(s), and what they do now. -->

Modules: <!-- keys, e.g. MIDI SCENES -->
Remixes reached: <!-- every remix that carries a changed module -->

## Measured / inferred

<!-- What you measured (and how), what you inferred, what would falsify it. -->

## Gates (on a tree rebased onto current main)

<!-- `make reach` prints the list for this diff; paste each command with its result. -->

- `make reach` (quick unless you chose `FULL=1`):
- `make check REMIX=<name>`:
- `make test-acceptance`:
- `make accept REMIX=<name> …`:
- `scripts/refhash.sh check` (build changes):
- `make verify-docs` (manifest, remix selection or docs changes):

## Manual site

<!-- docs/site/: the manual for musicians. A new module, or a change a user
can see, ships its docs in the same PR. -->

- [ ] `docs/site/usage/<name>.md` added or updated (new module or a user-visible change)
- [ ] Screenshots re-captured when the UI changed: `tools/emu/live_shots.py` (see `tools/site/shots/`)
- [ ] `mkdocs build --strict --config-file docs/site/mkdocs.yml` passes

## Hardware

<!-- Flashed? Which unit (MKI/MKII), which BUILD number, what was tried. "Not flashed" is a fine answer. -->

## Checklist

- [ ] No Elektron bytes in the diff (no image, slice, `.syx`, or firmware dump)
- [ ] Submodule pin changes name the upstream commit and why
- [ ] The module README says what was measured and what was inferred
- [ ] Generated docs are current: `make docs` then `make verify-docs` passes (CI refuses stale READMEs)
