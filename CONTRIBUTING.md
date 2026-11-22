# Contributing

The contract a module signs, the rule every port lives by, and the
etiquette for building from somebody else's repository.

## The one rule

**Never an Elektron byte.** Not an OS image, not a `.syx`, not a slice of
either, not in a commit and not attached to an issue or PR. Describe it,
hash it, or name the commit that built it. Anything a module needs from
the stock firmware is taken from the user's copy at build time
(`.incbin`). `.gitignore` refuses `*.bin`,
`*.syx`, `downloads/` and `out/`. The web builder's patches
(`docs/site/builder/patches/*.obp`) are committed under the same rule: each
holds octabam's bytes and instructions to copy stock bytes from the user's own
file in the browser, and `tools/web/obpatch.py` refuses a patch whose literal bytes
contain a stock sequence of 16 bytes or more (`MIN_STOCK`).

One exception: the few stock instructions a ColdFire hook overwrites and
replays (`CfPatch.hook_stock`, six to ten bytes a site). The build checks
the image holds them, which keeps a hook off the wrong OS. Keep a hook to
whole instructions and the shortest span; anything longer comes from the
user's image at build time.

## Your first pull request

1. Fork `sambanks/octabam` on GitHub. Clone `sambanks/octabam` itself
   with its submodules and add your fork as the remote you push to, so
   `origin/main` (the base `make reach` and `make identity` use) is the
   project's main:

   ```bash
   git clone --recurse-submodules https://github.com/sambanks/octabam
   cd octabam
   git remote add fork https://github.com/<you>/octabam
   ```

2. Install and build the toolchain, and unpack **your own** copy of OS
   1.40C: [BUILDING.md sections 0–2](docs/guide/BUILDING.md#0-what-you-need)
   (`make setup`, `make emu-setup`, `make os && make recon`; `make emu-cf`
   for the gates that boot the image). The OS never leaves your machine.
3. Branch from `origin/main`, write the module (next section), and run
   the gates in [Before you open a PR](#before-you-open-a-pr).
4. `git push fork <branch>` and open the PR against `sambanks/octabam:main`.
   **One module per PR** (with its `remixes/test/<name>/` remix, gate and
   docs): several modules, even ones written together, are several PRs,
   each reviewed, gated and reverted on its own. A remix of your own that
   combines them is a PR of its own after they land
   ([Remixes](#remixes)).
   The template asks for the gates you ran and what was measured. CI runs
   on it; GitHub holds a first-time contributor's first CI run until a
   maintainer approves it.

[GitHub Issues](https://github.com/sambanks/octabam/issues) take bug reports,
module proposals and hardware test reports (`.github/ISSUE_TEMPLATE/`).
A question about a change under review goes in its PR.

## A module

One directory, `modules/<name>/`:

```
manifest.py     declares the module -- exports MODULE (tools/remix/schema.py is the vocabulary)
README.md       what it does, how to use it, how it works, its limits
<sources>       .s for the ColdFire, .asm for the DSP -- or `upstream/`, a submodule
```

plus a remix that carries it (`remixes/test/<name>/remix.py`, a remix of
that one module, or an existing remix of the project's; and a
`README.md` beside it saying what is in it;
`docs/guide/COMPOSING.md`) and, for anything with behaviour worth pinning, a gate
(`tools/verify/verify_<name>.py`, named in the manifest's `gates`, run by
`make check` for every remix that carries the module). Nothing else
registers it: the registry discovers every `modules/*/manifest.py`, and
refuses two modules on one key. A module's `fx2_id` is its preferred id;
the remix settles clashes (`registry.assign_ids`).

The manifest's `category`, `author` and `author_url` make its row in
[modules/README.md](modules/README.md) (`make docs` renders it and the
remix index; `verify_docs` refuses a stale copy). A remix declares its
`family` (`rig`, `effects`, `mods`, `reference`, `probes`). An optional
`evidence` entry is read only by the instruction-form gates
(`docs/contributing/MODULES.md`).

### Remixes

There are three places a remix can live, and a contributor's goes in one of two:

- `remixes/<name>/`: the project's own remixes (`octabam`, `octabam-bus`,
  `octabam-verbs`, ...). The `octabam` name and the `octabam-` prefix are
  theirs; a contributed remix uses neither.
- `remixes/test/<name>/`: one module (or one combination its gates need) on
  the stock effects, for that module's gates. Every module arrives with
  one, or in an existing remix the project keeps.
- `remixes/community/<name>/`: a contributor's own selection for a card, such as
  the image they flashed, or the modules they use together. Name it after
  yourself or its purpose (`8thmyth-chop`, not `octabam-chop`); its
  `README.md` says what is in it. `make reach` leaves
  these out unless `TESTS=1`, and the selftest does not count one as a
  module's remix, so a module still needs a `test/` remix of its own.
  Keeping one working is its author's job: CI does not build it, so run
  `make check REMIX=<name>` before its PR and give the result in the PR
  body. The web builder offers every community remix that passes
  `make check` in the publish run (`tools/web/publish.py`), and leaves out
  one that does not. The unit shows `<image_name or name> <BUILD>`, upper
  case, at most 15 characters, so a name longer than 12 characters sets
  `image_name`. The manual's Community Remixes page is generated from
  `remix.py`: its `doc` line is the summary there, and no page under
  `docs/site/` needs editing.

Settings a module keeps on the card (a checkbox, a profile) go in BRAIN
(`modules/brain`; `docs/specs/BRAIN.md` is the design), and in no
file of the module's own; `docs/contributing/MODULES.md` "Settings on the
card".

Two skeletons and two worked examples:

| you are writing | copy | then read |
|---|---|---|
| a ColdFire modification (parts, kits, menus, MIDI, fixes) | `modules/_template_cf/` | `modules/direct-jump-kyoti/` (one linked DRAM unit and detours), then `modules/midi-scenes/` (built from its author's repo as a submodule) |
| a DSP effect | `modules/_template/` | `modules/character/` (an in-place insert, its own render gate `verify_character`) |

`docs/contributing/MODULES.md` is the full guide; `docs/contributing/PLACEMENT.md` says
where the bytes land and how much room there is.

**Declare what it is, not where it goes.** A ColdFire module is `Linked`
units (GNU-as, symbols, no absolute addresses of its own) reached by
`Detour`s that name those symbols, plus `Poke`s and `TableGrow`s for the
OS-image edits — each asserted against stock before anything is written.
`dram=True` is the default place for code: a 10 MB reserve carved off the
unit's sample/recorder pool, placed by the build, the way midisc and
KITS live (`docs/contributing/PLACEMENT.md`). The ~8 KB of free ROM
inside the OS image is for what must be ROM-resident, and it is shared
with everyone.

**`key` is API.** It appears in the build report, and tools parse the
report. Renaming a key, or rewording a report line, is a breaking change.

**A module may not crash or degrade the unit in any configuration the user
can select.** A module that does is not accepted. Selectable
configurations include the number of instances, the tracks they sit on,
parameter ranges, and combinations with other modules in the same remix.
A guard removes the configuration (a refused selection, a clamp, a bypass on
overrun); documenting the failure does not. `DspSection.max_per_core` declares
an instance ceiling for the cycle price and the unit does not enforce it, so
it is not a guard. The module README names the guard.

**A new module may not duplicate the function of an accepted one.** Once a
module is accepted, changes to that behaviour are enhancements and bugfixes
to that module. A separate module doing similar things is not accepted. Two
exceptions: a proposal to replace an abandoned or buggy module, where the PR
says which module it replaces and why; and a module that does the job in a
suitably different fashion, where the PR states what differs (the method,
the sound, the cost, what it can do that the accepted one cannot) and the
module README says what differs. Modules that overlap
and cannot share an image declare a `conflicts` pair (see Etiquette).

## The oracle rule

**A port is done when the author's build and this repo's build agree byte for byte.**
The form depends on the module:

| the module carries | the oracle |
|---|---|
| ratified hex (`CavePatch.pinned`) with a `.s` | the build assembles and links the source at its resolved address and refuses if the bytes differ |
| a floating source-linked cave | `reference(addr)` — the ratified bytes *at that address*, checked every build |
| `Linked` units | `reference=(addr, sha256)`: the unit re-linked at the author's own address, compared every build |

The reference comparison above is the standing proof; write the
equivalent gate for yours. When you port someone
else's mod, run their build against the shared stock image first and use
its output as the oracle.

## Building from an author's repository

The preferred shape for a module that has a repository of its own,
because the author keeps developing where they are:

- The repo is a git submodule at `modules/<name>/upstream`, **pinned to a
  commit**; a branch is named in `.gitmodules` when the port lives on one.
  `git submodule update --init` fetches it.
- **Nothing inside `upstream/` is edited here.** A change the port needs
  goes to the author as a PR (or, with their agreement, to a fork branch
  that will become one — midi-scenes's `octabam-gas` is the pattern). A
  bump is a commit here that moves the pin, with the oracle still holding.
- The author's repo stays under its own terms. Nothing from it is
  vendored or relicensed; octabam's MIT covers octabam.
- What makes a repo easy to build from: GNU-as sources (or a recipe the
  build can drive), symbols rather than absolute addresses for anything
  the build might place, an artifact of the author's own build to prove
  against, and no Elektron bytes.

## Gates

[`docs/contributing/TESTING.md`](docs/contributing/TESTING.md) is the mechanism:
what `make check` runs, what each gate proves, what none of them can see.
The contract:

**`make check REMIX=<name>` is the floor**, for every remix the change
reaches; CI runs it for each of them ("Before you open a PR"). No make target has a default remix: every target that builds or checks an
image takes `REMIX=<name>` and refuses without it (`make modules` lists
them); `make reach` and CI check `octabam`, the golden master, for every module
it carries. It builds, prices cycles, runs the gates every remix gets (the
ledger selftest, the stock-id audit, the docs, the knob census, the
dirty-state render, the menu, the boot under the ColdFire port, a project
under the port, USB) and then every gate the selected modules declare in
their manifests (`schema.Gate`). A remix without a module never runs that
module's gates; a module without gates has only the shared ones. Never
claim something works because it assembled.

**`make reach`** reads the branch's diff against `origin/main` and prints
the gates it reaches, in order; `RUN=1` runs them. By default it runs the
QUICK tier (the remixes users flash that carry the change, no identity, no
`make accept`, two shards, nice 10); `FULL=1` runs every gate
at full speed, when you choose to (`docs/contributing/TESTING.md` section 6 says what
quick gives up). Remixes under `remixes/test/` and `remixes/community/` are
left out unless `TESTS=1`. It refuses a tree that
is not rebased onto the base. A change to a module reaches every remix
that carries it; a change to the build reaches `scripts/refhash.sh check`,
`make identity` and the cover (the fewest remixes that carry every
module); a change to a gate reaches the remixes that run it; a doc change
reaches `verify_docs`. TESTING.md section 4 has the full routing.

**`make accept`** is the strict form of the same gates: it refuses a
`[SKIP]`, a swallowed failure or a missing instrument, prices every
selectable layout, renders the dearest, and writes a versioned JSON report
(`docs/contributing/TESTING.md`). `STRESS_SOURCE=<a local project>` generates
the fixture for the remix; `OT_PROJECT=<dir>` uses a project you prepared.
The pressure stages run only when every DSP module in the selection
declares its dearest settings (`schema.Module.dear`); a module without them
blocks the remix, by name, never a render at defaults.

**If you changed the build rather than a module, prove it changed
nothing**: `scripts/refhash.sh check` (24 configurations, artifacts *and*
build reports, bit-identical, against the baseline of your branch's
merge-base with origin/main, saved once for every worktree), and `make identity` (every remix, base against
head).

**Docs state what the code does now**: no proof levels, run histories,
dates or PR numbers (`AGENTS.md` "How docs are written here"). When a fact
changes, change it in every doc that repeats it.

**Flashing is the author's own step, on their own unit**, and it is
expensive: bump `BUILD` so the unit's version string maps to a commit,
stamp projects after any parameter-layout change (`tools/hw/ot_project.py
stamp-defaults`), read `docs/guide/BUILDING.md` first, and record
anything that goes wrong in `docs/contributing/FAILURE_MODES.md` the moment it
is seen.

## Before you open a PR

Rebase onto current main. Gates run before the rebase are not a result: a
branch that merges without a conflict can still fail on main.

**CI runs the gates; you run the one for your change.** The whole-remix
checks, `make reach` and the `refhash` pass take hours on one machine, and
CI runs every one the diff reaches on each push, fork PRs included, against
the 1.40C it downloads for that run. Locally:

```bash
git fetch origin && git rebase origin/main
python3 tools/verify/verify_<name>.py <remix>   # the one gate script for the change
make verify-docs                                # after a manifest, selection or doc change
git push fork <branch>
```

Then open the PR and read its checks. A local `make check REMIX=<name>` or
`make reach RUN=1` is for a failure CI reported that the one script cannot
reproduce; `make reach` (without `RUN=1`) only prints what the diff reaches,
and is quick. A first-time contributor's run waits for maintainer approval.
In the PR body, link the run and list each gate's result from its log (the
template asks for it). A remix with a DSP module that declares no `dear`
makes `make accept` report `blocked` with the module's name; say so in the PR.

PRs merge one at a time, oldest ready first. Before a merge, the maintainer
updates the branch only when main has moved under it since its last green
run, in a file the PR also changed or in a module, hook, cave or remix its
gates build with; a PR main has not moved under merges as it stands.

A change that alters what a remix does — its modules, effects, menus,
or costs (memory pages, DSP words) — updates the
hand-written manual site pages under `docs/site/` in the same PR. The
generated reference pages update themselves from the manifests.

The usage fragment `docs/site/usage/<name>.md` (`<name>` = the module
dir) is included into the module's page of the manual, so it is authored for
that page: `##` headings only (the page owns the title), links and images
written two levels below the site root (`../../img/<name>/<screen>.png`,
`../../safety.md`), a link to another module's fragment by its bare file name
(`kits.md`; the manual turns it into a link to that module's page, or into
plain text when the module is not in the manual), no section signs, no bare
repo paths, no nested includes. Write it for a musician: no commands, file
names or test status.
Screenshots are LCD captures from the emulator (`tools/site/capture_manual.py`;
`tools/emu/live_shots.py` and the scripts in `tools/site/shots/` are the
probe walks); a UI change re-captures them in the
same PR, and so does a rebase onto a main that changed a screen they show
([SCREENSHOTS.md](docs/contributing/SCREENSHOTS.md)). `mkdocs build --strict --config-file docs/site/mkdocs.yml` is
the local check for the fragments themselves.

A manifest, remix selection or module README change leaves the generated
copies stale: `make docs` renders `modules/README.md`, `remixes/README.md` and
`remixes/test/README.md` from the manifests and the selections. Run
`make docs` and commit the result; `make verify-docs` is the local
check, and CI's `📚 Docs, Site and Web Patches` job refuses a stale copy.

## What CI checks

`.github/workflows/ci.yml` runs on every PR, on `main` and by hand. `🔍
Classify Changes` decides from the diff which jobs run; `🗺️ Plan Gates`
builds each reached remix's image and splits the gates `make reach` plans
into units, leaving out the ones whose pass is recorded for the same image and
inputs (reported `cached`); `🧪 Gates — <unit>` runs each unit on a runner of
its own; and `🧪 Gates — make reach` is the one check that stands for all of
them. The plan and the units fetch the 1.40C from Elektron's site into the
runner on each run, with the zip hash pinned; every other job runs without
Elektron bytes. `📚 Docs, Site and Web Patches` checks the generated tables,
every link, the web builder's patches and, when the diff reaches it, the
manual site (`mkdocs build --strict`). [TESTING.md section 11](docs/contributing/TESTING.md#11-what-github-actions-checks)
lists each job and what it proves. **A green CI run says nothing about a
remix unless `Gates — make reach` ran.** Actions are pinned to commit SHAs; a bump
is a PR that changes the SHA and the version comment beside it.

Two more workflows: `.github/workflows/pages.yml` builds the manual site and
deploys it to [sambanks.github.io/octabam](https://sambanks.github.io/octabam/)
on every push to `main`; `.github/workflows/fuzz.yml` (`🎲 Port stress`, by hand only)
replays stress sequences of program changes and CCs under the ColdFire port over many runners.

## Etiquette

- Read the traps in `docs/contributing/TRAPS.md` before trusting an assembler, an
  emulator, or a null result.
- Collisions are refused by name; `make modules` prints the matrix. If
  your module cannot share an image with another although no claim
  overlaps (two designs of one behaviour), declare it:
  `conflicts=(("<KEY>", "<why>"),)`. Bytes your module relies on staying
  stock are a `Keep`, not a poke that writes what it expects.
- Keep the report text stable, keep `priority` stable (it is
  byte-load-bearing), keep `key` stable.
- A PR that touches a submodule pin says which upstream commit and why.
