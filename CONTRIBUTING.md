# Contributing

The contract a module signs, the rule every port lives by, and the
etiquette for building from somebody else's repository.

## The one rule

**Never an Elektron byte.** Not an OS image, not a `.syx`, not a slice of
either, not in a commit and not attached to an issue or PR. Describe it,
hash it, or name the commit that built it. Anything a module needs from
the stock firmware is taken from the user's copy at build time (Octakit,
until 6 Oct 2026, `.incbin`'d 459 distinct `stock/NNNN.bin` files that
way). `.gitignore` refuses `*.bin`,
`*.syx`, `downloads/` and `out/`.

What the rule does not cover (decided 16 Sep 2026): the few displaced
instructions at a cave's hook site. A `CfPatch.hook_stock` is the six to
ten bytes the installer overwrites with its `jsr` and the cave replays; the
build refuses an image that does not hold them, which is the check that
keeps a cave off the wrong OS. Those opcodes (ten sites, 70 bytes in all: `recorder-loop-fix` eight
sites and 54 bytes, `tempo-sync` one site and 10 bytes, `rlen-plen` one
site and 6 bytes; the Kyoti upstream's `TS_HOOK_STOCK` in
`batch-bugfixes` is a further 18) are an
instruction, not a firmware, and every ColdFire module carries its own
the same way. Keep a hook to whole instructions and the minimum span; data
tables, routines and anything longer than the displaced instructions come
from the user's image at build time.

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
   The template asks for the gates you ran and what was measured. CI runs
   on it; GitHub holds a first-time contributor's first CI run until a
   maintainer approves it.

Issues are turned off (`README.md`): a question about your change goes in
its PR.

## A module

One directory, `modules/<name>/`:

```
manifest.py     declares the module -- exports MODULE (tools/remix/schema.py is the vocabulary)
README.md       what it is, what was MEASURED, what is INFERRED, what is open
<sources>       .s for the ColdFire, .asm for the DSP -- or `upstream/`, a submodule
```

plus a remix that carries it (`remixes/<name>/remix.py`, or
`remixes/test/<name>/remix.py` for a remix of that one module, and a
`README.md` beside it: what is in it, where it has run;
`docs/guide/REMIXER.md`) and, for anything with behaviour worth pinning, a gate
(`tools/verify/verify_<name>.py`, named in the manifest's `gates`, run by
`make check` for every remix that carries the module). Nothing else
registers it: the registry discovers every `modules/*/manifest.py`, and
refuses two modules on one key or one FX2 id.

The manifest's `category`, `author`, `author_url`, `proof` and `proof_note`
are the README's module table (`make docs` renders it and the remix index
from the manifests and the selections; the selftest refuses a module
without them, `verify_docs` a stale copy). `proof` is one of `CHECK`,
`RENDER`, `PORT`, `HARDWARE`; the note names the unit, image and date, or
the gate. A remix declares `family` (`rig`, `effects`, `mods`,
`reference`, `probes`) and the same `proof` pair.

Settings a module keeps on the card (a checkbox, a profile) go in the
brain once it exists (`docs/proposals/BRAIN.md`), and until then in no
file of the module's own; `docs/contributing/MODULES.md` "Settings on the
card".

Two skeletons and two worked examples:

| you are writing | copy | then read |
|---|---|---|
| a ColdFire modification (parts, kits, menus, MIDI, fixes) | `modules/_template_cf/` | `modules/repitch/` (one linked DRAM unit, detours and pokes), then `modules/midi-scenes/` (built from its author's repo as a submodule) |
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
reaches. There is no default remix: every target that builds or checks an
image takes `REMIX=<name>` and refuses without it (`make modules` lists
them). It builds, prices cycles, runs the gates every remix gets (the
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
quick gives up). Remixes under `remixes/test/` are left out unless
`TESTS=1`. It refuses a tree that
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
nothing**: `scripts/refhash.sh save` on a tree you trust, then
`scripts/refhash.sh check` (24 configurations, artifacts *and* build
reports, bit-identical), and `make identity` (every remix, base against
head).

**Say what was measured and what was inferred**, in the README, with what
would falsify each claim; retract in every document that repeated a
number, not just the one you are editing.

**Flashing is the author's own step, on their own unit**, and it is
expensive: bump `BUILD` so the unit's version string maps to a commit,
stamp projects after any parameter-layout change (`tools/hw/ot_project.py
stamp-defaults`), read `docs/guide/BUILDING.md` first, and record
anything that goes wrong in `docs/contributing/FAILURE_MODES.md` the moment it
is seen.

## Before you open a PR

Rebase onto current main, then run the gates on the rebased tree. Gates
run before the rebase are not a result: a branch that merges without a
conflict can still fail on main (PR #396's stress fixture named a knob
that #415 had renamed).

```bash
git fetch origin && git rebase origin/main
make reach RUN=1 KEEP=1      # QUICK: every module or tool change
STRESS_SOURCE=<a local project> make reach FULL=1 RUN=1 KEEP=1 JOBS=3
#   FULL=1 (optional): every gate, identity and accept included, at full speed
#   KEEP=1: every gate, then one table (instead of stopping at the first failure)
#   JOBS=3: the per-remix lines over three worktrees at a time
```

Without `STRESS_SOURCE` the accept line cannot run, so the list carries
the `make check` lines separately and names the accept line as blocked.
A remix with a DSP module that declares no `dear` makes `make accept`
report `blocked` with the module's name; say so in the PR. List each
command and its result in the PR body (`make reach`'s output is the list;
the PR template asks for it).

## What CI checks

`.github/workflows/ci.yml` runs on every PR, on `main` and by hand, with
no Elektron bytes. [TESTING.md section 11](docs/contributing/TESTING.md#11-what-github-actions-checks)
lists each job and what it proves. **A green CI run says nothing about a
remix**: building, booting and playing one needs 1.40C, which is why the
gates above run on your machine. Actions are pinned to commit SHAs; a bump
is a PR that changes the SHA and the version comment beside it.

## Etiquette

- Read the traps in `AGENTS.md` before trusting an assembler, an
  emulator, or a null result.
- Collisions are refused by name; `make modules` prints the matrix. If
  your module cannot share an image with another although no claim
  overlaps (two designs of one behaviour), declare it:
  `conflicts=(("<KEY>", "<why>"),)`. Bytes your module relies on staying
  stock are a `Keep`, not a poke that writes what it expects.
- Keep the report text stable, keep `priority` stable (it is
  byte-load-bearing), keep `key` stable.
- A PR that touches a submodule pin says which upstream commit and why.
