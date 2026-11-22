<!-- CONTRIBUTING.md has the contract; "Before you open a PR" has the gates.
One module per PR. A remix of your own goes under remixes/community/<name>/,
never named octabam-* (CONTRIBUTING.md "Remixes"). -->

## What this changes

<!-- The module(s) or tool(s), and what they do now. -->

Modules: <!-- keys, e.g. MIDI SCENES -->
Remixes reached: <!-- every remix that carries a changed module -->

## Gates (on a tree rebased onto current main)

<!-- Link the `Gates — make reach` run and list each gate's result from its log. -->

CI run:

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
- [ ] Screenshots re-captured when the UI changed, or main changed a screen a capture shows (`docs/contributing/SCREENSHOTS.md`): groups, project and remix run:
- [ ] `mkdocs build --strict --config-file docs/site/mkdocs.yml` passes

## Checklist

- [ ] No Elektron bytes in the diff (no image, slice, `.syx`, or firmware dump)
- [ ] Submodule pin changes name the upstream commit and why
- [ ] The module README says what it does, how to use it and how it works (no test logs: `AGENTS.md` "How docs are written here")
- [ ] No selectable configuration (instance count, tracks, parameters, remix combination) crashes or degrades the unit; the guard is named in the module README
- [ ] This module does not duplicate the function of an accepted module; or the PR says which module it replaces, or what makes its method different
- [ ] Generated docs are current: `make docs` then `make verify-docs` passes (CI refuses stale READMEs)
