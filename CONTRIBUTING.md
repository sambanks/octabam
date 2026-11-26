# Contributing

This guide covers the rules for contributing modules, porting existing mods, and
opening pull requests.

## The one rule

Never include Elektron bytes in this repository. Do not commit an OS image, a
`.syx` file, or any slice of either, and do not attach them to issues or pull
requests. Describe the file, post its hash, or name the commit that built it
instead. Anything a module needs from stock firmware must be pulled from the
user's copy at build time using `.incbin`. `.gitignore` excludes `*.bin`,
`*.syx`, `downloads/`, and `out/`. The web builder patches
(`docs/site/builder/patches/*.obp`) follow the same rule: each patch stores only
octabam's bytes plus copy instructions that pull stock bytes from the user's
local file in the browser, and `tools/web/obpatch.py` rejects any patch whose
literal data contains 16 or more consecutive stock bytes (`MIN_STOCK`).

The only exception is the short sequence of stock instructions that a ColdFire
hook overwrites and replays (`CfPatch.hook_stock`, typically 6 to 10 bytes per
site). The build checks that the input image contains those exact bytes so a
hook cannot be applied to the wrong OS version. Keep hooks to whole instructions
and the shortest possible span; pull anything longer from the user's image at
build time.

## Your first pull request

1. Fork `sambanks/octabam` on GitHub. Clone `sambanks/octabam` with its
   submodules and add your fork as a separate remote (`fork`) so `origin/main`
   stays pointed at the upstream repository, which `make reach` and
   `make identity` use as their base:

   ```bash
   git clone --recurse-submodules https://github.com/sambanks/octabam
   cd octabam
   git remote add fork https://github.com/<you>/octabam
   ```

2. Install the toolchain and unpack your own copy of OS 1.40C by following
   [BUILDING.md sections 0–2](docs/guide/BUILDING.md#0-what-you-need)
   (`make setup`, `make emu-setup`, `make os && make recon`, plus `make emu-cf`
   for gates that boot the image). Your OS copy never leaves your machine.
3. Create a branch from `origin/main`, implement the module (described below),
   and run the local checks listed in
   [Before you open a PR](#before-you-open-a-pr).
4. Push to your fork (`git push fork <branch>`) and open a pull request against
   `sambanks/octabam:main`. Submit **one module per PR** along with its
   `remixes/test/<name>/` remix, verification gate, and documentation. Even if
   you wrote several modules together, submit each as its own PR so it can be
   reviewed, tested, and reverted independently. A custom remix combining them
   belongs in a separate PR after the modules merge ([Remixes](#remixes)).
   Fill out the PR template with the gates you ran and any measurements. CI
   runs automatically on PRs, though a first-time contributor's first CI run
   waits for maintainer approval.

Use [GitHub Issues](https://github.com/sambanks/octabam/issues) for bug reports,
module proposals, and hardware test reports (templates are in
`.github/ISSUE_TEMPLATE/`). Ask questions about an open change directly on its
pull request.

## A module

Each module lives in its own directory at `modules/<name>/`:

```
manifest.py     declares the module by exporting MODULE (schema in tools/remix/schema.py)
README.md       what the module does, how to use it, how it works, and its limits
<sources>       .s files for ColdFire, .asm files for DSP, or an `upstream/` submodule
```

A module also needs a remix that includes it—either a dedicated
`remixes/test/<name>/remix.py` (with a `README.md` beside it; see
`docs/guide/COMPOSING.md`) or an existing project remix—and a verification gate
(`tools/verify/verify_<name>.py`, listed in the manifest's `gates`) for any
behavior that should be checked automatically by `make check`. No separate
registration step is needed: the registry scans every `modules/*/manifest.py`
and rejects duplicate keys. A module's `fx2_id` is its preferred ID; if two
modules in a remix prefer the same ID, `registry.assign_ids` resolves the
conflict.

The manifest's `category`, `author`, and `author_url` fields populate
[modules/README.md](modules/README.md). Run `make docs` to regenerate both the
module and remix indexes; `verify_docs` fails if they are out of date. Each
remix declares a `family` (`rig`, `effects`, `mods`, `reference`, or `probes`).
The optional `evidence` field is used only by the instruction-form gates (see
`docs/contributing/MODULES.md`).

### Remixes

Remixes live in three locations, two of which are for contributor additions:

- `remixes/<name>/`: official project remixes (`octabam`, `octabam-bus`,
  `octabam-verbs`, etc.). Do not use the name `octabam` or the `octabam-`
  prefix for contributed remixes.
- `remixes/test/<name>/`: single-module (or minimal-combination) remixes built
  on top of stock effects for running a module's gates. Every new module should
  either add a test remix here or be included in an existing project remix.
- `remixes/community/<name>/`: personal selections shared by contributors, such
  as the image you flash to your own card or a favorite combination of modules.
  Name the directory after yourself or its purpose (for example
  `8thmyth-chop`, not `octabam-chop`), and add a `README.md` describing what it
  contains. `make reach` skips community remixes unless `TESTS=1` is set, and
  the selftest does not treat a community remix as a module's test remix, so
  individual modules still need their own entry under `remixes/test/`.
  Contributors are responsible for keeping their community remixes working: CI
  does not build them, so run `make check REMIX=<name>` locally before opening a
  PR and include the results in the PR description. The web builder includes any
  community remix that passes `make check` during the publish run
  (`tools/web/publish.py`), and drops it if it later fails. On the unit, the
  remix displays as `<image_name or name> <BUILD>` in uppercase, truncated to 15
  characters; set `image_name` (up to 12 characters) if the remix name is
  longer. The manual's Community Remixes page is generated automatically from
  each `remix.py` (using its `doc` string), so you do not need to edit files
  under `docs/site/`.

Any settings a module persists on the CF card (checkboxes, profiles, etc.) must
go through BRAIN (`modules/brain`, designed in `docs/specs/BRAIN.md`) rather
than a separate file of the module's own. See the "Settings on the card" section
of `docs/contributing/MODULES.md`.

Starting templates and reference modules:

| Module type | Template to copy | Examples to read |
|---|---|---|
| ColdFire mod (parts, kits, menus, MIDI, fixes) | `modules/_template_cf/` | `modules/direct-jump-kyoti/` (linked DRAM unit with detours), then `modules/midi-scenes/` (built from an upstream submodule) |
| DSP effect | `modules/_template/` | `modules/character/` (in-place insert with its own audio render gate `verify_character`) |

See `docs/contributing/MODULES.md` for the full module author guide and
`docs/contributing/PLACEMENT.md` for memory layout and free space details.

**Declare requirements instead of addresses.** ColdFire modules should be
written as `Linked` GNU-as units using symbols rather than hardcoded addresses,
connected with `Detour` entries that reference those symbols, plus `Poke` and
`TableGrow` entries for OS-image edits (all verified against stock bytes before
patching). Use `dram=True` by default: this places code in a 10 MB reserve
carved from the sample/recorder pool, as KITS and MIDI SCENES do
(`docs/contributing/PLACEMENT.md`). Save the ~8 KB of shared free ROM in the OS
image for code that genuinely must reside in ROM.

**Treat `key` as part of the public API.** Module keys appear in the build
report, which external tools parse. Renaming a key or changing the format of a
report line is a breaking change.

**Never crash or degrade the unit in any user-selectable configuration.** A
module that can hang or corrupt the unit under valid user settings will not be
accepted. This covers instance counts, track assignments, parameter ranges, and
combinations with other modules in the same remix. Add an explicit guard—such as
refusing an invalid selection, clamping values, or bypassing on overrun—rather
than merely documenting a failure mode. Note that `DspSection.max_per_core` is
only used for cycle budgeting and is not enforced by the unit, so it does not
count as a guard. Document your module's guards in its README.

**Do not duplicate an existing module.** Once a module is accepted, improvements
and bugfixes belong in that module rather than a competing duplicate. The two
exceptions are replacing an abandoned or broken module (explain which module it
replaces and why in the PR) or offering a genuinely different approach (explain
what differs—method, sound, resource cost, or capabilities—in both the PR and
the module README). If two modules overlap and cannot coexist in one image,
declare them as a `conflicts` pair (see [Etiquette](#etiquette)).

## The oracle rule

A ported mod is considered verified when this repository's build matches the
original author's build byte for byte. How that check is expressed depends on
the module type:

| Module type | Verification mechanism |
|---|---|
| Ratified hex (`CavePatch.pinned`) with `.s` source | Assembles and links the source at its resolved address and fails if any byte differs |
| Floating source-linked cave | `reference(addr)` checks the assembled output at that address against ratified bytes on every build |
| `Linked` units | `reference=(addr, sha256)` re-links the unit at the author's address and checks the hash on every build |

When porting someone else's mod, run their build against the stock OS image
first and use its output as your oracle, then add the corresponding reference
check to your manifest.

## Building from an author's repository

If a module already has its own repository, build from it directly so the author
can keep developing upstream:

- Add the author's repo as a git submodule at `modules/<name>/upstream`, pinned
  to a specific commit (and specify a branch in `.gitmodules` if the port tracks
  one). Contributors fetch it with `git submodule update --init`.
- Do not edit files inside `upstream/` in this repository. Send any needed
  changes upstream as a PR (or, with the author's agreement, to a fork branch
  intended to merge upstream, as with `midi-scenes`'s `octabam-gas` branch).
  Updating to a newer version is a commit that moves the submodule pin while
  keeping the oracle check passing.
- The author's repository remains under its own license. Nothing from it is
  vendored or relicensed; octabam's MIT license applies only to octabam's own
  files.
- To make an upstream repo easy to integrate: use GNU-as sources (or a build
  recipe octabam can invoke), use symbols instead of absolute addresses for
  relocatable code, provide a reference build artifact for the oracle check, and
  keep Elektron bytes out of the repo.

## Gates

See [`docs/contributing/TESTING.md`](docs/contributing/TESTING.md) for how
`make check` works, what each gate verifies, and what emulators cannot catch.

**`make check REMIX=<name>` is the baseline** for any remix a change affects,
and CI runs it for each reached remix (see
[Before you open a PR](#before-you-open-a-pr)). Build and check targets have no
default remix; you must pass `REMIX=<name>` (`make modules` lists available
names). `make reach` and CI always include `octabam` when a module it contains
changes. `make check` builds the image, computes cycle budgets, runs the shared
gates (ledger selftest, stock-ID audit, docs, knob census, dirty-state render,
menu checks, ColdFire port boot, project load under the port, and USB), and then
runs every module-specific gate declared via `schema.Gate`. Never assume a
change works just because it assembles cleanly.

**`make reach`** inspects your branch's diff against `origin/main` and lists the
affected gates in execution order; pass `RUN=1` to run them. By default it uses
the QUICK tier (published remixes only, skipping identity checks and
`make accept`, running across two shards at `nice 10`). Pass `FULL=1` to run
everything at full speed (see `docs/contributing/TESTING.md` section 6 for the
differences). Remixes under `remixes/test/` and `remixes/community/` are skipped
unless `TESTS=1` is set. `make reach` requires your branch to be rebased onto
its base. Roughly: module changes reach every remix containing that module;
build-system changes reach `scripts/refhash.sh check`, `make identity`, and a
minimal cover of remixes spanning all modules; gate changes reach remixes that
run that gate; doc changes reach `verify_docs`. See `TESTING.md` section 4 for
the complete routing rules.

**`make accept`** runs the strict acceptance suite: it fails on any `[SKIP]`,
swallowed error, or missing tool, checks cycle budgets across every selectable
layout, renders worst-case settings, and writes a versioned JSON report (see
`docs/contributing/TESTING.md`). Pass `STRESS_SOURCE=<local project>` to
generate a fixture or `OT_PROJECT=<dir>` to use an existing project. Stress
stages run only when every DSP module in the remix declares worst-case settings
(`schema.Module.dear`); missing `dear` metadata blocks the remix rather than
falling back to defaults.

**Build-system changes must prove bit-identity.** If you modify the build rather
than a module, run `scripts/refhash.sh check` (checks 24 configurations—both
artifacts and build reports—against your branch's `origin/main` merge-base) and
`make identity` (compares every remix between base and HEAD).

**Keep documentation current.** Docs should describe what the code does right
now, without proof levels, test run histories, dates, or PR numbers (see
"How docs are written here" in `AGENTS.md`). When behavior changes, update every
doc that mentions it.

**Hardware flashing is the author's responsibility.** Bump `BUILD` before
flashing so the version string on the unit maps cleanly to a commit, stamp
existing projects after any parameter-layout change
(`tools/hw/ot_project.py stamp-defaults`), read `docs/guide/BUILDING.md` first,
and log any hardware faults in `docs/contributing/FAILURE_MODES.md` as soon as
you observe them.

## Before you open a PR

Rebase onto current `origin/main` first. Gate results from before a rebase do
not count, because a branch can merge cleanly and still break on current main.

**Let CI run the full suite; run the targeted gate locally.** Full-remix checks,
`make reach`, and `refhash` can take hours on a single machine, and CI runs
every reached check automatically on every push (including fork PRs) using a
freshly downloaded copy of OS 1.40C. Locally, run:

```bash
git fetch origin && git rebase origin/main
python3 tools/verify/verify_<name>.py <remix>   # the gate for your change
make verify-docs                                # if you changed manifests, remixes, or docs
git push fork <branch>
```

Then open the PR and monitor CI. Only run `make check REMIX=<name>` or
`make reach RUN=1` locally if you need to reproduce a CI failure that the single
gate script does not catch. (`make reach` without `RUN=1` only prints the plan
and runs quickly.) First-time contributors' CI runs wait for maintainer
approval. In the PR description, link to the CI run and list the result of each
gate from its log. If a remix includes a DSP module without `dear` metadata,
`make accept` will report `blocked` and name the module—note that in the PR.

Pull requests merge one at a time, oldest ready first. Before merging,
maintainers only rebase a PR if `main` has changed a file the PR touches or a
module, hook, cave, or remix that its gates depend on; otherwise it merges as
is.

If your change alters what a remix does—its modules, effects, menus, or memory
and DSP costs—update the hand-written manual pages under `docs/site/` in the
same PR. Generated reference pages update automatically from manifests.

Usage fragments at `docs/site/usage/<name>.md` (matching the module directory
name) are included directly into each module's manual page. Follow these rules
when editing them:

- Use `##` headings only (the generated page provides the H1 title).
- Write links and image paths relative to two levels below the site root
  (`../../img/<name>/<screen>.png`, `../../safety.md`).
- Link to another module's fragment by its bare filename (such as `kits.md`);
  the site generator resolves it to that module's manual page, or renders plain
  text if the module is not in the manual.
- Do not use the section sign symbol, bare repository paths, or nested snippet
  includes.
- Write for musicians: omit CLI commands, source filenames, and test status.

Screenshots are captured from the emulator's LCD output using
`tools/site/capture_manual.py` (with probe scripts in `tools/emu/live_shots.py`
and `tools/site/shots/`). If your change alters any captured screen—or if you
rebase onto a `main` that did—recapture the affected screenshots in the same PR
(see [SCREENSHOTS.md](docs/contributing/SCREENSHOTS.md)). Run
`mkdocs build --strict --config-file docs/site/mkdocs.yml` locally to verify
fragments and links.

If you change a manifest, remix selection, or module README, run `make docs` and
commit the regenerated `modules/README.md`, `remixes/README.md`, and
`remixes/test/README.md`. You can verify them locally with `make verify-docs`;
CI's `📚 Docs, Site and Web Patches` job fails if they are stale.

## What CI checks

`.github/workflows/ci.yml` runs on every PR, on pushes to `main`, and on manual
dispatch:

- `🔍 Classify Changes` determines which jobs the diff requires.
- `🗺️ Plan Gates` builds images for each reached remix and splits the planned
  gates into parallel units, skipping gates whose cached pass matches the same
  image and inputs (reported as `cached`).
- `🧪 Gates — <unit>` executes each gate unit on its own runner.
- `🧪 Gates — make reach` aggregates all unit results into a single status
  check.

The planning and gate jobs download OS 1.40C from Elektron's site with a pinned
hash; all other jobs run without Elektron bytes. `📚 Docs, Site and Web Patches`
verifies generated index tables, links, web builder patches, and (when affected)
the MkDocs build (`mkdocs build --strict`). See
[TESTING.md section 11](docs/contributing/TESTING.md#11-what-github-actions-checks)
for the full job list. Note that a green CI run does not test remix behavior
unless `Gates — make reach` ran. GitHub Actions are pinned to commit SHAs; update
both the SHA and its version comment together when bumping an action.

Two additional workflows exist: `.github/workflows/pages.yml` builds and deploys
the manual site to
[sambanks.github.io/octabam](https://sambanks.github.io/octabam/) on pushes to
`main`, and `.github/workflows/fuzz.yml` (`🎲 Port stress`, manual trigger only)
replays stress sequences of program changes and CCs under the ColdFire emulator
across parallel runners.

## Etiquette

- Read `docs/contributing/TRAPS.md` before trusting an assembler, an emulator,
  or an unexpected null result.
- Resource collisions fail the build with both conflicting modules named; run
  `make modules` to inspect the compatibility matrix. If your module is
  functionally incompatible with another module even without overlapping claims,
  declare `conflicts=(("<KEY>", "<why>"),)`. If your module depends on specific
  stock bytes remaining unmodified, declare a `Keep` rather than poking the same
  bytes.
- Keep build report strings, `priority` values (which affect byte layout), and
  `key` names stable.
- When updating a submodule pin, note the upstream commit and reason in your PR.
