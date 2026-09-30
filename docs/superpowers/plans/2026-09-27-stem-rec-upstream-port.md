# STEM REC on current upstream: the port, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Carry STEM REC and the tool support it needs from branch `crosscheck` (`7dee174`) onto current upstream `main`, with no change in what STEM REC does, and run its take checks on a FAT32 card as well as FAT16.

**Architecture:** Each group of changes lands as its own commit on `stem-rec-v2`: cherry-picked from `crosscheck` where the commit still applies, and re-applied by hand where it doesn't. Git work happens in the Windows checkout. Builds, the port, and every gate run in a WSL clone that mirrors it. Build changes are proven inert with `scripts/refhash.sh` and a remix-wide hash, and the emulator change is proven additive by an old-binary against new-binary run.

**Tech Stack:** Python 3 (the remixer, the verifiers), C++17 (`tools/emu/ot_emu`, the ColdFire port), GNU as for ColdFire (`m68k-elf-*`, Ubuntu's `m68k-linux-gnu` tools under those names), bash and make, WSL2 Ubuntu.

**Spec:** `docs/superpowers/specs/2026-09-26-stem-rec-upstream-port-design.md`

## Global Constraints

- `crosscheck` stays at `7dee174`, untouched.
- `modules/stems/stems.s` moves byte for byte: its md5 on `stem-rec-v2` is `cf735ce0927b23e36b2fa04980cc7536`, the md5 at `7dee174`.
- "A build change proves it changed nothing." `scripts/refhash.sh save` before the first build change, `scripts/refhash.sh check` after the build-support commits: every configuration's artifacts and build reports bit-identical.
- "The emulator change is additive. Every existing flag keeps its meaning and its report text. A run without the new flags prints what it printed before."
- "No new behavior. Nothing from piece 2 on lands here."
- "A general fix found on the way goes in as its own commit, named as such."
- "Each overlap is compared on evidence, and the choice is written down." Equal copies: upstream's stays. Ours stays when it does more or is proven better.
- Every pinned value that moves is a finding: re-measured, explained, and written down in `docs/firmware/STEM_REC.md`, never loosened to pass.
- A FAT32 take check that fails is a finding, reported before any fix. The fix is its own commit.
- Never an Elektron byte in the repo (AGENTS.md). The stock image stays in `out/`.
- Never push. No pull request. Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Prose follows the Microsoft Writing Style Guide: short sentences, contractions, serial comma, no spaced dashes, sentence-case headings.
- Firmware claims are re-derived from `out/raw/section_3_MAIN_OS.bin` (SHA-256 `164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e`) with `scripts/disasm.sh emac`, never radare2.

## What changed since the spec

The spec was written against upstream `81126f7`. Upstream merged 48 more commits by 27 Sep 2026 (`68af650`), and three of them change this plan:

- **Remixes are folders** (`8648348`). A remix is `remixes/<name>/remix.py` with a `README.md` beside it, and `verify_docs` refuses a flat `remixes/<name>.py`. So `remixes/stems.py` becomes `remixes/stems/remix.py` plus `remixes/stems/README.md`.
- **Modules and remixes carry table fields** (`8648348`). The selftest refuses a module without `category`, `author`, `author_url`, and `proof`. `make docs` renders `README.md`'s module table and `docs/remixes/README.md` from them, and `verify_docs` refuses a stale copy.
- **`PLAN.md` is gone** (`0c982cf`), and there's no `docs/effects/FLASHPLAN.md`. `CHANGELOG.md` records flashed images only. So `crosscheck`'s `PLAN.md` item 8 has no home. Its status goes into `remixes/stems/README.md`, and Flash 13 goes into `modules/stems/FLASH.md`.

One line of `crosscheck` doesn't come across: its `.gitignore` entry for `Octatrack projects/`. The fixture's template lives in `out/projects/`, which upstream's `out/` line already ignores, and this checkout's `.git/info/exclude` covers the root folder. Committing the line would ignore a folder only this machine has.

Also gone upstream: `modules/hello-dram`, and the two modules STEM REC's docs name as neighbors, CF PROBE and MENU SHORTCUT. No upstream module touches STEM REC's sites today (a grep of `origin/main` for `0x40004b12`, `0x400cbd54`, `0x400cc5a8`, and `0x40014cfe` on 27 Sep 2026 found none in `modules/` or `tools/remix/`).

Task 1 rebases `stem-rec-v2` onto `origin/main` as it stands then. The branch holds only documents until then, so the rebase is free.

## The overlaps, compared

The spec asks the plan to record, for each job both trees do, what each copy does, what proves it, and what it costs.

| Overlap | What each does | Proof | Choice |
|---|---|---|---|
| `--card-out` | Both write the card model's image once, at the end. Report lines differ: ours `(23 sectors written in the run)`, upstream's `(67108864 bytes, 23 sector(s) written by the firmware)` | `verify_set` reads upstream's; `cardfail` reads the count | Upstream's. `cardfail`'s parse is rewritten and fails loudly on a line it can't read (Task 8) |
| `read_file`, `list_dir` against `extract_image` | Ours reads one file or one folder. Upstream's reads every file, and a folder with no files doesn't appear | Ours has a round-trip test. Upstream's has none, and `verify_set` uses it | Upstream's, with our round-trip test moved onto it (Task 6) |
| `--call-before-play`, `--at` against `--call`, `--call-at` | Ours: several calls, each from main's spin, after `--pre-roll`, and calls at chosen frames. Upstream's: one call before the pre-roll, or one at a frame | `verify_stems` makes up to three calls in one run (`overflow`) and arms after the pre-roll in every run | Ours, beside upstream's (Task 5) |
| Staging the fixture's card | `emu_rtos.stage_project` (deleted upstream) and `emu_card.stage_project` take the same arguments and have the same body. The spec's "other arguments" was wrong. Only the default scratch tree differs: `out/_emu_rtos_tree` against `out/_stage_tree` | The fixture's tap check (T1 is the only core-1 track that sounds) | Upstream's. The fixture passes its own tree, `out/_stems_stage_tree`, so `verify_set`'s staging can't overwrite it mid-run (Task 8) |
| `blockdump.read` | Moved from `tools/scratch/` to `tools/harness/`, same function | The verifier's lag checks | Upstream's location (Task 8) |
| Skipping what a machine can't build | Upstream's selftest stops early, with the fix, when a submodule is missing. Ours (`prereq.py`) skips, by name, a remix whose submodule is absent or whose runtime needs a toolchain this machine lacks, in the every-remix sweeps only | Task 1's baseline `make check` in WSL | Decided in Task 2 from that baseline |

## Review Focus

These five inputs or conditions follow from the spec, and no test exercised them before this plan. Each line names the task that adds its test.

1. **`cardfail` meets a `card out` line in a form its parse doesn't know.** Expected: the check fails and names the line, never passes on the byte count. Test: Task 8, Step 1 (`card_out_sectors` against both line forms, as a static check).
2. **The firmware doesn't mount the FAT32 card.** Expected: one check says "not mounted" and the take checks don't run, instead of eight checks each failing on "no new recording". Test: Task 10, Step 7 (the mount byte, with FAT16 as the control).
3. **A take folder that holds no file.** Expected: the check says no new recording was found, because `extract_image` lists files only. Test: Task 6, Step 1 (an empty folder in the round-trip tree, pinned as absent).
4. **The refhash baseline and check run different script versions.** Expected: both run the committed GNU-safe script. Test: Task 1, Step 8, and Task 3, Step 8 (the script's blob hash recorded at save and compared at check).
5. **A gate runs on a WSL tree that isn't the Windows commit.** Expected: every gate run starts with the WSL `HEAD` equal to the Windows `HEAD` and no file differing. Test: Task 1, Step 3 (`run.sh` prints the `HEAD` and the count of differing files on each log's first line), and each task's gate step reads that line.

---

## Conventions for every task

**Two trees.** Edit and commit in the Windows checkout, `C:\Projects\Octabam` (branch `stem-rec-v2`). Build and run in the WSL clone, `/home/yvez/stemrec2`. Never edit in WSL: `sync.sh` resets it to the Windows commit.

**The helpers** (written in Task 1, kept in `.superpowers/v2/`, which Git ignores here):

- `wslsync`: run `bash .superpowers/v2/sync.sh` from the Windows checkout in Git Bash. It resets the clone to the Windows `HEAD`, then copies every uncommitted file over it.
- `wslrun NAME CMD...`: run this from Git Bash:
  ```bash
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash -c "tr -d '\r' < /mnt/c/Projects/Octabam/.superpowers/v2/run.sh > /tmp/v2-run.sh && bash /tmp/v2-run.sh NAME CMD..."
  ```
  It runs `CMD` in the clone, unbuffered, into `/home/yvez/xcheck/v2-NAME.log`, and prints the log's last 15 lines. A `$` in `CMD` is lost on the way into WSL: put such a command in a script under `.superpowers/v2/` and run the script.
- **Long runs** (any `make check`, `refhash.sh`, `remixhash.sh`, `verify_stems.py`): start them with the Bash tool's `run_in_background`, and tell Yves the log path in chat when each starts, so he can `tail -f` it.

**Before any gate counts,** the log's first line must show the same `HEAD` as `git rev-parse --short HEAD` on Windows and `dirty 0`.

**Commits** follow the repo's form, `area: what -- why`, and end with the trailer. Stage files by name, never `git add -A`.

---

### Task 1: Rebase, the WSL clone, and the baselines

**Files:**
- Create (local, not committed): `.superpowers/v2/sync.sh`, `.superpowers/v2/wsl-sync.sh`, `.superpowers/v2/run.sh`, `.superpowers/v2/wsl-clone.sh`, `.superpowers/v2/remixhash.sh`, `.superpowers/v2/runlog.md`
- Modify: `scripts/refhash.sh:97` (by cherry-pick of `634412b`)

**Interfaces:**
- Produces: the clone at `/home/yvez/stemrec2`; `out/emu/ot_emu.base` (upstream's port binary); baselines `out/refhash/baseline/`, `out/remixhash/baseline/`, `out/v2-index-before.txt`; `/home/yvez/xcheck/v2-check-bamsep26-base.log`; the runlog with the base SHA.

- [ ] **Step 1: Rebase `stem-rec-v2` onto current upstream**

In Git Bash:
```bash
cd /c/Projects/Octabam
git status --porcelain
git fetch origin
git rebase origin/main
git log --oneline -6
git rev-parse --short origin/main
```
Expected: `git status` prints nothing. The rebase replays the spec's three commits and this plan's commit with no conflict (documents only). Write the base SHA into `.superpowers/v2/runlog.md` as its first line: `base: <sha> (origin/main, <date>)`.

- [ ] **Step 2: Write the sync helpers**

`.superpowers/v2/sync.sh`:
```bash
#!/bin/bash
# Mirror this checkout's stem-rec-v2 into the WSL clone: the commit first,
# then every uncommitted file on top (CRs stripped from text files).
set -euo pipefail
cd /c/Projects/Octabam
[ "$(git rev-parse --abbrev-ref HEAD)" = stem-rec-v2 ] || { echo "not on stem-rec-v2"; exit 1; }
{ git diff --name-only HEAD; git ls-files -o --exclude-standard; } | sort -u > .superpowers/v2/sync-list.txt
echo "windows: HEAD $(git rev-parse --short HEAD), $(wc -l < .superpowers/v2/sync-list.txt) uncommitted file(s)"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash -c "tr -d '\r' < /mnt/c/Projects/Octabam/.superpowers/v2/wsl-sync.sh > /tmp/v2-sync.sh && bash /tmp/v2-sync.sh"
```

`.superpowers/v2/wsl-sync.sh`:
```bash
#!/bin/bash
# Runs inside WSL: reset the clone to the Windows commit, then lay the
# uncommitted files named in sync-list.txt over it.
set -euo pipefail
SRC=/mnt/c/Projects/Octabam
DST=/home/yvez/stemrec2
cd "$DST"
git fetch -q origin stem-rec-v2
git reset -q --hard FETCH_HEAD
while IFS= read -r f; do
  f=${f%$'\r'}
  [ -n "$f" ] || continue
  if [ -f "$SRC/$f" ]; then
    mkdir -p "$(dirname "$f")"
    if [ ! -s "$SRC/$f" ] || grep -Iq . "$SRC/$f"; then
      tr -d '\r' < "$SRC/$f" > "$f"
    else
      cp "$SRC/$f" "$f"
    fi
  else
    rm -f "$f"
  fi
done < "$SRC/.superpowers/v2/sync-list.txt"
echo "wsl:     HEAD $(git rev-parse --short HEAD), $(git status --porcelain | wc -l) file(s) differ from it"
```

- [ ] **Step 3: Write the run helper**

`.superpowers/v2/run.sh`:
```bash
#!/bin/bash
# wslrun NAME CMD...: CMD in the WSL clone, unbuffered, into
# /home/yvez/xcheck/v2-NAME.log. The first line names the HEAD and how many
# files differ from it, so a log proves which tree it ran on.
set -uo pipefail
name=$1; shift
cd /home/yvez/stemrec2
export PATH="$HOME/.local/bin:$PATH" PYTHONUNBUFFERED=1
log=/home/yvez/xcheck/v2-$name.log
echo "log: $log"
{
  echo "# $(date -Is)  HEAD $(git rev-parse --short HEAD)  dirty $(git status --porcelain | wc -l)  $*"
  "$@"
  rc=$?
  echo "# exit $rc"
} > "$log" 2>&1
tail -n 15 "$log"
exit "$rc"
```

- [ ] **Step 4: Create the clone**

`.superpowers/v2/wsl-clone.sh`:
```bash
#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
D=/home/yvez/stemrec2
[ -e "$D" ] && { echo "$D exists: stop and look before replacing it"; exit 1; }
git clone -q -b stem-rec-v2 /mnt/c/Projects/Octabam "$D"
cd "$D"
git config core.autocrlf false
GIT_TERMINAL_PROMPT=0 git submodule update --init --recursive
ln -s /home/yvez/octabam/downloads downloads
echo downloads >> .git/info/exclude
mkdir -p out/projects
cp -r "/home/yvez/xcheck/wt/out/projects/Ultimate FX 1.5.3" out/projects/
git log -1 --format='%h %s'
git submodule status
```
Run:
```bash
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash -c "tr -d '\r' < /mnt/c/Projects/Octabam/.superpowers/v2/wsl-clone.sh > /tmp/v2-clone.sh && bash /tmp/v2-clone.sh"
```
Expected: the clone's `HEAD` equals the Windows `HEAD`. All five submodules show a SHA, none prefixed with `-`.

- [ ] **Step 5: Provision the toolchain in the clone**

`make setup` calls Homebrew only when `binwalk`, `radare2`, or `m68k-elf-gcc` is missing. All three are on this machine, so it runs without brew.
```bash
wslrun setup make setup
wslrun emu-setup make emu-setup
wslrun os make os
wslrun recon make recon
wslrun sha sha256sum out/raw/section_3_MAIN_OS.bin
wslrun emu-cf make emu-cf
wslrun disasm-gate scripts/disasm.sh emac 0x40003664 8
```
Expected: each exits 0. The hash is `164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e`. `make emu-cf` ends at the M6a boot gate. The disassembly prints `msacl`, not `invalid`.

Then check the one-word displaced move (AGENTS.md: the binary isn't the source). The operand holds a `$`, so it goes in a script. `.superpowers/v2/asm-gate.sh`:
```bash
#!/bin/bash
# dsp_asm must emit the one-word displaced move (tools/patches/dsp56300.patch).
set -euo pipefail
cd /home/yvez/stemrec2
t=$(mktemp -d)
printf '        move    x:(r7+$15),a\n' > $t/mv.asm
vendor/dsp56300/build/source/dsp_host/dsp_asm -in $t/mv.asm -org 0 -out $t/mv.bin -sym $t/mv.sym -list > $t/mv.lst
od -An -tx1 $t/mv.bin
rm -rf $t
```
```bash
wslrun asm-gate bash /mnt/c/Projects/Octabam/.superpowers/v2/asm-gate.sh
```
Expected: `de 57 02` and nothing more (one word, `0x0257de`, stored low byte first, the way `build_bus.assemble` reads it). Six bytes mean the assembler predates the patch: run `scripts/setup.sh` again before going on.

- [ ] **Step 6: Keep upstream's port binary as the additive baseline**

```bash
wslrun emu-base cp out/emu/ot_emu out/emu/ot_emu.base
```

- [ ] **Step 7: Cherry-pick the refhash fix (a general fix)**

`scripts/refhash.sh:97` runs `sed -E -i ''`, which only BSD sed accepts. GNU sed reads `''` as a file name and fails, so no baseline can be saved in WSL. In Git Bash:
```bash
git cherry-pick 634412b
git show --stat HEAD
```
Expected: one line changed in `scripts/refhash.sh`: `sed -E -i.bak -e '...' "$1" && rm -f "$1.bak"`. Then `wslsync`.

- [ ] **Step 8: Save the refhash baseline**

```bash
wslrun refhash-save bash -c 'git hash-object scripts/refhash.sh && scripts/refhash.sh save'
```
An inner command always goes in single quotes, because `wslrun` wraps everything in double quotes.
Run it in the background and tell Yves the log path: `/home/yvez/xcheck/v2-refhash-save.log`. Expected: 26 cases listed with their `rc`, and `baseline -> out/refhash/baseline/manifest.txt`. Copy the blob hash on the log's second line into the runlog as `refhash script: <hash>`.

- [ ] **Step 9: Write the remix-wide hash, then save and null-check it**

`refhash.sh` builds only the default remix, `bamsep26`, which has no DRAM unit. DramRegion and the ledger fix touch the DRAM path and every remix, so this covers them. `.superpowers/v2/remixhash.sh`:
```bash
#!/bin/bash
# remixhash.sh save|check: every remix built with XBUS=1 SPEC=1, its image
# and its report hashed. A remix that fails to build is recorded with its rc,
# so the same failure before and after compares equal.
set -uo pipefail
cd /home/yvez/stemrec2
export PATH="$HOME/.local/bin:$PATH"
mode=$1
case "$mode" in save) out=out/remixhash/baseline ;; check) out=out/remixhash/current ;; *) echo "save|check"; exit 2 ;; esac
rm -rf "$out"; mkdir -p "$out"
names=$(python3 -c 'import sys; sys.path.insert(0, "tools"); import toolpath; from remix import registry; print(" ".join(n for n in registry.remix_names() if not n.startswith("_")))')
for n in $names; do
  rm -f out/mainos_bus.bin
  XBUS=1 SPEC=1 REMIX=$n python3 tools/build/build_bus.py > "$out/$n.log" 2>&1; rc=$?
  sed -E -i -e 's|File "[^"]*", line [0-9]+|File "<src>", line <n>|g' "$out/$n.log"
  if [ -f out/mainos_bus.bin ]; then img=$(sha256sum out/mainos_bus.bin | cut -d' ' -f1); else img=none; fi
  echo "$n rc=$rc image=$img report=$(sha256sum "$out/$n.log" | cut -d' ' -f1)" | tee -a "$out/manifest.txt"
done
if [ "$mode" = check ]; then
  diff -u out/remixhash/baseline/manifest.txt "$out/manifest.txt" && echo "ALL REMIXES IDENTICAL"
fi
XBUS=1 SPEC=1 python3 tools/build/build_bus.py > /dev/null 2>&1 || true
```
Run save, then check on the same tree (in the background, one after the other). The clone has no `.superpowers/`, so every helper runs from its Windows path:
```bash
wslrun remixhash-save bash /mnt/c/Projects/Octabam/.superpowers/v2/remixhash.sh save
wslrun remixhash-null bash /mnt/c/Projects/Octabam/.superpowers/v2/remixhash.sh check
```
Expected: the null check prints `ALL REMIXES IDENTICAL`. If it doesn't, a build report isn't deterministic: find the churning line in the two logs, extend the `sed` normalization to that line only, and repeat both runs before trusting any later check.

- [ ] **Step 10: Save the module index**

```bash
wslrun index-before bash -c 'python3 tools/remix/index.py > out/v2-index-before.txt'
```
Expected: the log ends `# exit 0`, and the file holds the module list and the compatibility matrix.

- [ ] **Step 11: Run the baseline `make check`**

```bash
wslrun check-bamsep26-base make check REMIX=bamsep26
```
Run in the background; tell Yves `/home/yvez/xcheck/v2-check-bamsep26-base.log`. Record the outcome in the runlog:
- **Exit 0:** upstream's check passes in WSL as it is. Task 2 is skipped.
- **Non-zero, and every failure names Octakit's runtime or a missing submodule** (for example `verify_replaces` failing only on remixes that carry OCTAKIT, or `verify_octakit` failing on the assembler): Task 2 applies.
- **Any other failure:** stop and report it to Yves with the log. It's upstream's, not ours, and the port can't be measured against a red baseline.

- [ ] **Step 12: Commit nothing, and check both trees**

This task commits only the cherry-picked refhash fix. Confirm:
```bash
git log --oneline -3
wslsync
```
Expected: `wsl: HEAD <same sha>, 0 file(s) differ from it`.

---

### Task 2: General fix: skip, by name, what this machine can't build

Only if Task 1, Step 11 found failures that are all Octakit's runtime or a missing submodule.

**Files:**
- Create: `tools/remix/prereq.py`
- Modify: `tools/verify/verify_octakit.py`, `tools/verify/verify_replaces.py`

**Interfaces:**
- Produces: `prereq.unbuildable(name: str) -> str | None`, `prereq.runtime_toolchain_problem() -> str | None`, `prereq.missing_submodule(mod) -> str | None`.

- [ ] **Step 1: Cherry-pick the commit**

```bash
git cherry-pick 16602f2
```
Expected: applies cleanly (Task 1's research found all three files apply). If it conflicts, resolve to the content of `git show 16602f2`.

- [ ] **Step 2: Check each other failing caller in the baseline log**

Every failure in `v2-check-bamsep26-base.log` must now be a `[SKIP]` naming the remix and the reason. If a caller other than `verify_replaces.py` and `verify_octakit.py` failed on the same cause, give it the same pattern `verify_octakit.py` uses:
```python
from remix import prereq  # noqa: E402
if prereq.runtime_toolchain_problem():
    print(f"  [SKIP] <script name>: {prereq.runtime_toolchain_problem()} (make setup)")
    sys.exit(0)
```
Put it where that script first needs the runtime, amend it into this commit with `git commit --amend --no-edit`, and name the script in the commit body.

- [ ] **Step 3: Run the check again**

```bash
wslsync
wslrun check-bamsep26-prereq make check REMIX=bamsep26
```
Expected: exit 0. The log names each skipped remix and its reason, for example `[SKIP] N remixes not built on this machine -- OCTAKIT: its runtime needs a bare-metal m68k-elf toolchain; m68k-elf-as here targets m68k-linux-gnu`.

- [ ] **Step 4: Write the commit body**

If the cherry-pick's message still describes midisc as private, amend the message: midisc is public now, so the submodule reason only fires on a clone without `git submodule update`. Keep the subject line.

---

### Task 3: DramRegion, the build support STEM REC's memory needs

**Files:**
- Modify: `tools/remix/schema.py` (a `DramRegion` class after `ArenaReserve`; a `dram_regions` field after `linked`; a check in `Module.__post_init__`)
- Modify: `tools/remix/platform_build.py` (`build()` gains `regions=()`)
- Modify: `tools/build/build_bus.py` (the `build()` call; a report line)
- Modify: `tools/remix/ledger.py` (a DRAM-region clash block)
- Modify: `tools/remix/selftest.py` (a `_region` fixture and a case)

**Interfaces:**
- Produces: `schema.DramRegion(symbol: str, size: int, align: int = 16)`; `Module.dram_regions: tuple[DramRegion, ...] = ()`; `platform_build.build(units, payloads, work, reserve=None, defsyms=None, includes=None, regions=())`, where `regions` is `[(symbol, size, align)]`, placed down from the reserve's ceiling, handed to the link as `--defsym`, and written to `LAYOUT` as `"regions": {symbol: [address, size]}`; the build report line `  dram region: <symbol> <size> B at 0x<address>`.

- [ ] **Step 1: Write the failing selftest case**

In `tools/remix/selftest.py`, extend the schema import:
```python
from remix.schema import (CavePatch, Claims, DramRegion, DspSection, Kind,  # noqa: E402
                          Linked, MenuEntry, Module, Param, YBase)
```
Add after `_cave`:
```python
def _region(name, symbol):
    return Module(
        name=name, key=name.upper(), kind=Kind.CF_PATCH, doc="fixture",
        linked=(Linked(name, "does/not/exist.s", dram=True),),
        dram_regions=(DramRegion(symbol, 0x1000),),
    )
```
Append to `CASES`, after the curve-bank case:
```python
    ("two modules claiming one DRAM region symbol",
     [_region("alpha", "ring"), _region("beta", "ring")], "DRAM region"),
```

- [ ] **Step 2: Run it and watch it fail**

```bash
wslsync
wslrun selftest-red python3 tools/remix/selftest.py
```
Expected: an `ImportError` naming `DramRegion`.

- [ ] **Step 3: Add `DramRegion` to the schema**

In `tools/remix/schema.py`, after class `ArenaReserve` (it ends with `raise ValueError("ArenaReserve.pages must be positive")`):
```python
@dataclass(frozen=True)
class DramRegion:
    """Uninitialised DRAM a module's DRAM units name by `symbol`.

    Placed by the platform build at the TOP of the platform's arena reserve
    (arena.PLATFORM_PAGES, which any remix with DRAM units already pays
    for), stacked downward in declaration order, and handed to the link as
    `--defsym symbol=address`. The build refuses when the runtime and its
    loader stage reach the lowest region. The loader never writes these
    bytes and nothing clears them: a region must not need initial contents.
    STEM REC's 4 MiB ring and its task's stack are the first users (docs/
    superpowers/specs/2026-09-10-stem-rec-poc-design.md, section 5)."""

    symbol: str
    size: int
    align: int = 16

    def __post_init__(self):
        if self.size <= 0:
            raise ValueError(f"DramRegion {self.symbol}: size must be positive")
        if self.align <= 0 or self.align & (self.align - 1):
            raise ValueError(f"DramRegion {self.symbol}: align must be a power of two")
```
In class `Module`, after `linked: tuple[Linked, ...] = ()`:
```python
    # Uninitialised DRAM this module's linked units name by symbol
    # (schema.DramRegion) -- requires at least one dram=True Linked unit,
    # since a region with no unit to name it can never be referenced.
    dram_regions: tuple[DramRegion, ...] = ()
```
In `Module.__post_init__`, right after the check that ends `f"params are READ from the stock descriptor, " f"never written)")`:
```python
        if self.dram_regions and not any(u.dram for u in self.linked):
            raise ValueError(f"{self.name}: declares DRAM regions but has no "
                             f"DRAM unit to name them")
```

- [ ] **Step 4: Add the ledger clash**

In `tools/remix/ledger.py`, at the end of `check()`, just before `return problems`:
```python
    # ---- DRAM regions (schema.DramRegion) ---------------------------------
    # A region is a linker symbol; two modules defining the same one would
    # both link against whichever --defsym came last, silently sharing it.
    regions: dict[str, str] = {}
    for m in selected:
        for r in getattr(m, "dram_regions", ()):
            if r.symbol in regions:
                clash("DRAM region", regions[r.symbol], m.name,
                      f"the symbol {r.symbol}")
            regions[r.symbol] = m.name
```

- [ ] **Step 5: Run the selftest and watch it pass**

```bash
wslsync
wslrun selftest-green python3 tools/remix/selftest.py
```
Expected: `[PASS] two modules claiming one DRAM region symbol`, every shipped remix clean, and `OK`.

- [ ] **Step 6: Place the regions in the platform build**

In `tools/remix/platform_build.py`, change the signature and docstring of `build`:
```python
def build(units, payloads, work: pathlib.Path, reserve=None, defsyms=None, includes=None,
          regions=()):
    """units: [(module key, Linked)] with dram=True, in link order.
    payloads: [dict(name, blob, stage, dst, rawlen, rhash, backup)] for
    payloads built elsewhere (Octakit): `blob` = signature + GKA3 stream.
    reserve: (base, size) of the arena reserve the runtime lives in;
    required when there are units. defsyms: extra {name: value} for the
    link (a bridge's continuation targets, schema.Override). regions:
    [(symbol, size, align)] of uninitialised DRAM (schema.DramRegion),
    stacked down from the reserve's ceiling and handed to the link as
    --defsym symbol=address. Returns (append bytes, symbols of the octabam
    runtime, boot poke, payload names) and writes LAYOUT."""
```
After `defs.update(defsyms or {})` and before the `link_runtime` call:
```python
        # DramRegions: stacked down from the ceiling, named to the link.
        placed = {}
        top = ceiling
        for r_sym, r_size, r_align in regions:
            top = (top - r_size) & ~(r_align - 1)
            placed[r_sym] = (top, r_size)
        defs.update({s: a for s, (a, _) in placed.items()})
```
After the `if stage_end > ceiling: sys.exit(...)` block:
```python
        if placed:
            floor_sym, (floor, _) = min(placed.items(), key=lambda kv: kv[1][0])
            if stage_end > floor:
                sys.exit(f"platform build: the runtime and its stage end at 0x{stage_end:08x}, "
                         f"above DRAM region {floor_sym} at 0x{floor:08x} -- shrink the regions "
                         f"or reserve more pages (tools/remix/arena.py PLATFORM_PAGES).")
```
After the `layout.update(base=base, ...)` call:
```python
        if placed:
            layout["regions"] = {s: [a, n] for s, (a, n) in placed.items()}
```

- [ ] **Step 7: Pass the regions from the build and report them**

In `tools/build/build_bus.py`, just before `if _dram or _payloads:` (the block that calls `platform_build.build`):
```python
    _regions = [(_r.symbol, _r.size, _r.align) for _k in REMIX.modules
                for _r in getattr(remix_modules()[_k], "dram_regions", ())]
```
In the call, after the `includes=` argument, add `regions=_regions`:
```python
            includes={_u.label: _u.include({_k: remix_modules()[_k] for _k in REMIX.modules})
                      for _m, _u in _dram if _u.include is not None},
            regions=_regions)
```
After the `print(f"  platform runtime: ..." if _reserve else f"  platform loader: ...")` statement, still inside the block:
```python
        for _s, _n, _al in _regions:
            print(f"  dram region: {_s} {_n:,} B at 0x{_psyms[_s]:08x}")
```

- [ ] **Step 8: Prove the build changed nothing**

```bash
wslsync
wslrun selftest-dram python3 tools/remix/selftest.py
wslrun refhash-dram bash -c 'git hash-object scripts/refhash.sh && scripts/refhash.sh check'
wslrun remixhash-dram bash /mnt/c/Projects/Octabam/.superpowers/v2/remixhash.sh check
```
Run the two hash checks in the background and give Yves the log paths. Expected: selftest `OK`; the refhash script's blob hash equals the runlog's `refhash script:` line, and `ALL 26 CASES BIT-IDENTICAL`; `ALL REMIXES IDENTICAL`.

- [ ] **Step 9: Commit**

The crosscheck commits `2406515` and `3aa976d` carried this change; their content is what Steps 1 to 7 wrote. Commit it as one:
```bash
git add tools/remix/schema.py tools/remix/platform_build.py tools/build/build_bus.py tools/remix/ledger.py tools/remix/selftest.py
git commit -m "DramRegion: uninitialised DRAM at the top of the platform reserve, refused on a misfit or a shared symbol -- refhash 26/26 and every remix identical

From crosscheck 2406515 and 3aa976d, re-applied by hand: build_bus's call
takes an includes= argument upstream now.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: General fix: the ledger registers a hook site even when its cave floats

**Files:**
- Modify: `tools/remix/ledger.py` (the "ColdFire caves and hook sites" loop in `check()`)
- Modify: `tools/remix/selftest.py` (a `_detour` fixture and two cases)

**Interfaces:**
- Consumes: `_cave`, `_region` from `selftest.py` (Task 3).

Upstream's loop skips a floating cave with `continue` before its `hook_addr` is registered, so no floating cave's hook site is ever checked. Every hook-based cave upstream floats.

- [ ] **Step 1: Write the failing cases**

In `tools/remix/selftest.py`, add `Detour` to the schema import (alphabetical, after `Claims`). Add after `_region`:
```python
def _detour(name, site):
    return Module(
        name=name, key=name.upper(), kind=Kind.CF_PATCH, doc="fixture",
        linked=(Linked(name, "does/not/exist.s", dram=True),),
        detours=(Detour(site, b"\x4e\x71" * 4, name, "entry"),),
    )
```
Append to `CASES`:
```python
    # A hook site is a fixed address whether or not its cave floats. Every
    # hook-based cave upstream floats, and until the ledger registered
    # their sites, none of them was checked against anything.
    ("two floating caves hooking the same instruction",
     [_cave("alpha", None, hook_addr=0x40004d40),
      _cave("beta", None, hook_addr=0x40004d40)], "hook site"),
    ("a floating cave's hook and a detour at one site",
     [_cave("alpha", None, hook_addr=0x40004b12),
      _detour("beta", 0x40004b12)], "hook site"),
```

- [ ] **Step 2: Run them and watch them fail**

```bash
wslsync
wslrun selftest-hook-red python3 tools/remix/selftest.py
```
Expected: both new cases `[FAIL]`, each reporting that the ledger found no `hook site` clash.

- [ ] **Step 3: Cherry-pick the fix**

```bash
git cherry-pick --no-commit ff6395a
git diff --cached --stat
```
Expected: `tools/remix/ledger.py` only. The loop now reads:
```python
    for m in selected:
        for c in m.cf_patches:
            if c.cave_addr is not None:  # pinned: check for overlap against
                for start, length, owner, label in caves:  # every pinned cave
                    if _overlap(start, length, c.cave_addr, len(c.pinned)):
                        clash("ColdFire cave", f"{owner}'s {label}",
                              f"{m.name}'s {c.label}",
                              f"0x{max(start, c.cave_addr):08x}")
                caves.append((c.cave_addr, len(c.pinned), m.name, c.label))
            # A hook site is a fixed address whether or not the CAVE that
            # receives the jsr floats. ...
            if c.hook_addr is not None:
```
If the cherry-pick conflicts, write that content by hand, keeping upstream's lines around it.

- [ ] **Step 4: Run the selftest and watch it pass**

```bash
wslsync
wslrun selftest-hook-green python3 tools/remix/selftest.py
```
Expected: both new cases `[PASS]`, every shipped remix `[PASS] ... is clean`, and `OK`. A shipped remix that turns red here is a real clash upstream's ledger missed: stop, and report it to Yves with the two modules and the site before going on.

- [ ] **Step 5: Compare the module index**

```bash
wslrun index-after bash -c 'python3 tools/remix/index.py > out/v2-index-after.txt && diff out/v2-index-before.txt out/v2-index-after.txt'
```
Expected: no diff output, and the log ends `# exit 0`. A changed compatibility cell is the same kind of finding as Step 4.

- [ ] **Step 6: Prove the build changed nothing**

```bash
wslrun refhash-hook bash -c 'git hash-object scripts/refhash.sh && scripts/refhash.sh check'
wslrun remixhash-hook bash /mnt/c/Projects/Octabam/.superpowers/v2/remixhash.sh check
```
Expected: `ALL 26 CASES BIT-IDENTICAL` and `ALL REMIXES IDENTICAL`.

- [ ] **Step 7: Commit**

```bash
git add tools/remix/ledger.py tools/remix/selftest.py
git commit -m "ledger: register a hook site even when its cave floats -- a general fix; no floating cave's hook site was ever checked

From crosscheck ff6395a, with two selftest cases it lacked. Every shipped
remix stays clean; the module index is unchanged.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The port: several calls before play, calls at frames, a poke before play, a failing card

**Files:**
- Modify: `tools/emu/ot_emu/main.cpp` (a `parseCalls` helper above `main`; four option fields; four argument cases; the card hookup; calls and a poke before the transport start; the `Action` list)
- Modify: `tools/emu/ot_emu/card.h`, `tools/emu/ot_emu/card.cpp` (WRITE SECTORS refusal)
- Create (local): `.superpowers/v2/emu-additive.sh`

**Interfaces:**
- Produces, for `verify_stems.py` (Task 8):
  - `--call-before-play ADDR[:ARG][,...]`: each call runs as main, from main's spin, after `--pre-roll`, before the transport start. Prints `call       : 0x<addr>(0x<arg>) before play -> returned, d0 0x<d0>`.
  - `--poke-before-play "ADDR=BYTE;..."`: written after those calls, before the transport start. Prints `poke       : 0x<addr> <- 0x<v> (before play)`.
  - `--at FRAME:ADDR[:ARG][,...]`: each call runs as main at that many frames after the transport start. Prints `call       : 0x<addr>(0x<arg>) at frame <n> -> returned, d0 0x<d0>`.
  - `--card-fail-after N`: once N sectors are written, every WRITE SECTORS ends in ERR and ABRT with no DRQ, logged as `WRITE-FAIL`.
  - A malformed call spec exits 2 with `ot_emu: bad call spec '<spec>'`.

- [ ] **Step 1: Write the additive proof**

`.superpowers/v2/emu-additive.sh`:
```bash
#!/bin/bash
# The port change is additive: one batch run with upstream's binary and
# ours, same flags, none of them new. Then the new flags, and a malformed
# spec.
set -uo pipefail
cd /home/yvez/stemrec2
w=out/emu_additive
rm -rf $w; mkdir -p $w
.venv/bin/python3 - <<'EOF'
import sys, pathlib
sys.path.insert(0, "tools"); import toolpath  # noqa: F401
import emu_card as ec
img, name = ec.stage_project("out/projects/Ultimate FX 1.5.3", "STEMS", "ULTFX", tree="out/emu_additive/tree")
pathlib.Path("out/emu_additive/card.img").write_bytes(img)
print("staged", name)
EOF
COMMON="--image out/raw/section_3_MAIN_OS.bin --card $w/card.img --set STEMS --project ULTFX \
  --sequencer --internal-clock --frames 120 --load-ms 20000 --dsp --main-level 64 \
  --pre-roll 40 --poke-trig 2"
run() {  # $1 binary, $2 tag, then extra flags
  local bin=$1 tag=$2; shift 2
  $bin $COMMON --block-dump $w/$tag.dump --card-out $w/$tag.img \
    --mem-dump 0x80000000,64=$w/$tag.mem "$@" > $w/$tag.log 2>&1
  echo "$tag: exit $?"
}
OLD="--poke 0x80000029=1 --call 0x4000a1e0 --call-at 60 --watch-mem 0x80000028,4"
run out/emu/ot_emu.base base $OLD
run out/emu/ot_emu new $OLD
strip() { grep -v -E 'wall|real time|M instr/s' "$1"; }
if diff <(strip $w/base.log) <(strip $w/new.log); then echo "REPORTS IDENTICAL (timing lines aside)"; fi
for x in dump img mem; do
  if cmp -s $w/base.$x $w/new.$x; then echo "$x identical"; else echo "$x DIFFERS"; fi
done
# The new flags. The STOP handler returns at once while 0x80000029 is 0, so
# the calls before play are harmless; the one at frame 30 stops the
# sequencer, the one at frame 50 finds it stopped.
run out/emu/ot_emu flags --call-before-play 0x4000a1e0,0x4000a1e0:0 \
  --poke-before-play "0x80000029=1" --at 30:0x4000a1e0,50:0x4000a1e0:0 --card-fail-after 0
grep -E '^(call|poke) ' $w/flags.log
out/emu/ot_emu $COMMON --at 5 > $w/bad.log 2>&1
echo "malformed: exit $? -- $(grep 'bad call spec' $w/bad.log)"
```

- [ ] **Step 2: Run it and watch the new flags fail**

```bash
wslsync
wslrun additive-red bash /mnt/c/Projects/Octabam/.superpowers/v2/emu-additive.sh
```
Expected, before the change: `REPORTS IDENTICAL`, three `identical` lines (both runs are upstream's binary). The `flags` run prints a usage message, and no `call ... before play` line appears.

- [ ] **Step 3: Add the call parser**

In `tools/emu/ot_emu/main.cpp`, immediately above `int main(int _argc, char** _argv)`:
```cpp
// "FRAME:ADDR:ARG,..." (FRAME omitted for --call-before-play). ARG defaults to 0.
struct Call { uint64_t frame = 0; uint32_t addr = 0, arg = 0; };
static std::vector<Call> parseCalls(const std::string& _s, const bool _withFrame)
{
	std::vector<Call> out;
	size_t q = 0;
	while(q < _s.size())
	{
		auto e = _s.find(',', q); if(e == std::string::npos) e = _s.size();
		std::string one = _s.substr(q, e - q); q = e + 1;
		if(one.empty())
			continue;
		Call c;
		std::vector<std::string> f;
		size_t r = 0;
		while(r <= one.size()) { auto k = one.find(':', r); if(k == std::string::npos) k = one.size(); f.push_back(one.substr(r, k - r)); r = k + 1; }
		if(f.size() < (_withFrame ? 2u : 1u))
		{
			std::fprintf(stderr, "ot_emu: bad call spec '%s'\n", one.c_str());
			std::exit(2);
		}
		size_t n = 0;
		if(_withFrame) c.frame = std::strtoull(f[n++].c_str(), nullptr, 0);
		c.addr = static_cast<uint32_t>(std::strtoul(f[n++].c_str(), nullptr, 0));
		if(n < f.size()) c.arg = static_cast<uint32_t>(std::strtoul(f[n].c_str(), nullptr, 0));
		out.push_back(c);
	}
	return out;
}
```

- [ ] **Step 4: Add the options**

After the field `std::string cardOut;` (its comment names `emu_card.extract_image`):
```cpp
	std::string pokeBeforePlay;	// --poke-before-play: "addr=byte;..." written after the --call-before-play calls and before the transport start, so a take's first frame sees it
	std::string callBeforePlay;	// --call-before-play ADDR[:ARG][,...]: each called AS MAIN from main's spin, after --pre-roll, before the transport start (STEM REC arms a take here)
	std::string atFrames;		// --at FRAME:ADDR[:ARG][,...]: each called AS MAIN that many frames after the transport start (several, where --call-at makes one)
	long long cardFailAfter = -1;	// --card-fail-after N: once N sectors are written, every WRITE SECTORS ends in ERR + ABRT, no DRQ
```
After the line `else if(a == "--call-at" && i + 1 < _argc)	callAt = std::atoi(_argv[++i]);`:
```cpp
		else if(a == "--poke-before-play" && i + 1 < _argc)	pokeBeforePlay = _argv[++i];
		else if(a == "--call-before-play" && i + 1 < _argc)	callBeforePlay = _argv[++i];
		else if(a == "--at" && i + 1 < _argc)			atFrames = _argv[++i];
		else if(a == "--card-fail-after" && i + 1 < _argc)	cardFailAfter = std::atoll(_argv[++i]);
```
After `card = std::make_unique<ot::AtaCard>(std::move(bytes));`:
```cpp
			if(cardFailAfter >= 0) card->failWritesAfter(cardFailAfter);
```

- [ ] **Step 5: Call and poke before play**

In the sequencer path, right after the `if(preRoll > 0) { ... }` block and before `if(!rtos.startTransportLive())`:
```cpp
				for(const auto& c : parseCalls(callBeforePlay, false))
				{
					// The pre-roll stops the instant the last frame's
					// interrupt is taken, never at main's spin, so
					// callAsMain's own guard refused every call here
					// whenever --pre-roll was given (measured 12 Sep 2026 on
					// crosscheck). Run to the spin first; a no-op when the
					// PC is already there.
					rtos.runToMainSpin(1000.0);
					uint32_t d0 = 0;
					const bool ok = rtos.callAsMain(c.addr, {c.arg}, d0, 200000000);
					std::printf("call       : %#x(%#x) before play -> %s, d0 %#x\n", c.addr, c.arg,
						ok ? "returned" : rtos.why().c_str(), d0);
				}
				pokeBytes(pokeBeforePlay, "before play");
```

- [ ] **Step 6: Calls at frames, in upstream's action list**

Replace the struct line:
```cpp
				struct Action { uint64_t frame; bool call; std::vector<uint8_t> bytes; };
```
with:
```cpp
				struct Action { uint64_t frame; bool call; std::vector<uint8_t> bytes; uint32_t addr = 0, arg = 0; bool at = false; };
```
After the loop that pushes the MIDI events (`actions.push_back({ev.frame, false, ev.bytes});`):
```cpp
				for(const auto& c : parseCalls(atFrames, true))
					actions.push_back({c.frame, false, {}, c.addr, c.arg, true});
```
In the `for(const auto& act : actions)` loop, replace `if(act.call)` with a first branch for `--at`:
```cpp
					if(act.at)
					{
						const bool spun = rtos.runToMainSpin(1000.0) == ot::Rtos::Stop::Gate;
						uint32_t d0 = 0;
						const bool ok = spun && rtos.callAsMain(act.addr, {act.arg}, d0, 200000000);
						std::printf("call       : %#x(%#x) at frame %llu -> %s, d0 %#x\n", act.addr, act.arg,
							static_cast<unsigned long long>(rtos.frameCount() - frame0),
							ok ? "returned" : rtos.why().c_str(), d0);
					}
					else if(act.call)
```
The `std::stable_sort` already there keeps calls at one frame in the order given.

- [ ] **Step 7: Let the card refuse writes**

In `tools/emu/ot_emu/card.h`, after `const std::vector<uint8_t>& image() const { return m_img; }`:
```cpp
		// --card-fail-after N: once N sectors are written, every WRITE
		// SECTORS ends in ERR + ABRT with no DRQ, the way a failing card
		// refuses one.
		void failWritesAfter(const int64_t _n) { m_failAfter = _n; }
```
After `uint64_t m_reads = 0, m_writes = 0;`:
```cpp
		int64_t m_failAfter = -1;
```
In `tools/emu/ot_emu/card.cpp`, at the top of `case 0x30:`, before `const auto l = lba(), n = count();`:
```cpp
			if(m_failAfter >= 0 && static_cast<int64_t>(m_writes) >= m_failAfter)
			{
				m_error = 0x04;			// ABRT
				m_status |= 0x01;		// ERR, no DRQ: the command is refused
				note({"WRITE-FAIL", lba(), count()});
				return;
			}
```

- [ ] **Step 8: Build, and prove the change additive**

```bash
wslsync
wslrun emu-cf-new make emu-cf
wslrun additive-green bash /mnt/c/Projects/Octabam/.superpowers/v2/emu-additive.sh
```
Expected:
- `REPORTS IDENTICAL (timing lines aside)`, and `dump identical`, `img identical`, `mem identical`. A diff in a line that only reports time is the filter's gap: add that line's pattern to `strip()` and run again. Any other diff means the change isn't additive: fix it before going on.
- The `flags` run prints, in this order: two `call       : 0x4000a1e0(0) before play -> returned` lines, `poke       : 0x80000029 <- 0x1 (before play)`, `call       : 0x4000a1e0(0) at frame 30 -> returned`, and `call       : 0x4000a1e0(0) at frame 50 -> returned`.
- `malformed: exit 2 -- ot_emu: bad call spec '5'`.

- [ ] **Step 9: Commit**

```bash
git add tools/emu/ot_emu/main.cpp tools/emu/ot_emu/card.h tools/emu/ot_emu/card.cpp
git commit -m "ot_emu: --call-before-play, --poke-before-play, --at FRAME:ADDR:ARG, --card-fail-after -- additive: a run without them is byte-identical to upstream's

From crosscheck ba11c66, 05f1929 and 3dcb90a, re-applied by hand: --card-out
and the pokeBytes helper exist upstream now, and --at joins upstream's
action list beside --call-at and --midi.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The card reader's round trip, on upstream's reader

**Files:**
- Create: `tools/verify/verify_card_reader.py`

**Interfaces:**
- Consumes: `emu_card.build_image(tree_dir, size_mb) -> bytes`, `emu_card.extract_image(img) -> {path: bytes}` (upstream's).
- Produces: `python3 tools/verify/verify_card_reader.py`, exit 0 when every file reads back; in it, `FILES`, `EMPTY`, `FAT16_SHA`, `build_tree(root)`, and `main()`'s `check(label, ok, detail="")`, which Task 10 extends.

The round-trip checks pin behavior that already exists, so they pass on the first run. One fails only if `extract_image` has a defect, which is a finding. The last check pins the FAT16 image upstream's builder makes, so Task 10 can change the builder and prove FAT16 unchanged.

- [ ] **Step 1: Write the test**

`tools/verify/verify_card_reader.py`:
```python
#!/usr/bin/env python3
"""The card reader returns what the builder wrote, byte for byte.

    python3 tools/verify/verify_card_reader.py

`emu_card.extract_image` is how every STEM REC port run gets its WAV back,
so it is held to the builder that made the image: files of awkward sizes (0,
1, one cluster, one cluster + 1, many clusters), a long name and nested
folders, built, read back and compared. It also pins what the reader cannot
show: a folder with no file in it does not appear (it lists files), so a
take that made its folder and wrote nothing reads as no take at all. And it
pins the FAT16 image itself, by hash, so a change to the builder that moves
one byte of it is seen.
"""
import hashlib
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import emu_card as ec  # noqa: E402


def _bytes(n):
    """n bytes of a fixed pattern, so the image, and its hash, repeat."""
    return bytes(range(256)) * (n // 256) + bytes(range(n % 256))


FILES = {
    "PRESETS/PROJ/project.work": b"",
    "PRESETS/AUDIO/a.wav": b"\x01",
    "PRESETS/AUDIO/Long Name Recording.wav": _bytes(4096),
    "PRESETS/AUDIO/250910-1432/T1.wav": _bytes(4097),
    "big.bin": _bytes(300_000),
}
EMPTY = "PRESETS/AUDIO/250910-1433"
FAT16_SHA = ""        # the 16 MB image of build_tree(), from upstream's builder


def build_tree(root):
    for rel, data in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    (root / EMPTY).mkdir(parents=True)


def main():
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    with tempfile.TemporaryDirectory() as t:
        tree = pathlib.Path(t) / "tree"
        build_tree(tree)
        img16 = ec.build_image(str(tree), 16)
        got = ec.extract_image(img16)
        for rel, data in FILES.items():
            check(f"/{rel} ({len(data):,} B)", got.get(rel) == data,
                  "" if rel in got else "missing")
        check("nothing read back that was not written", set(got) == set(FILES),
              f"{sorted(set(got) - set(FILES))}")
        check(f"an empty folder ({EMPTY}) does not appear",
              not any(p.startswith(EMPTY) for p in got))
        sha = hashlib.sha256(img16).hexdigest()
        check("FAT16: the image is what upstream's builder made", sha == FAT16_SHA, sha)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it, and watch only the hash check fail**

```bash
wslsync
wslrun card-reader .venv/bin/python3 tools/verify/verify_card_reader.py
```
Expected: seven `[PASS]` lines, then `[FAIL] FAT16: the image is what upstream's builder made  <64 hex digits>`. A `[FAIL]` on any other line is a defect in upstream's reader: report it before any fix, and fix it in its own commit.

- [ ] **Step 3: Pin the hash, and run again**

Set `FAT16_SHA` to the 64 hex digits the failing line printed. Then:
```bash
wslsync
wslrun card-reader-pinned .venv/bin/python3 tools/verify/verify_card_reader.py
```
Expected: eight `[PASS]` lines, exit 0. Run it once more to see the hash repeat; a second, different hash means the builder isn't deterministic, which is a finding.

- [ ] **Step 4: Commit**

```bash
git add tools/verify/verify_card_reader.py
git commit -m "verify_card_reader: the round trip, moved onto upstream's extract_image -- the empty folder it cannot show, and the FAT16 image by hash, pinned

crosscheck 2a45748 held its own read_file and list_dir to build_image;
upstream's extract_image does the same job for verify_set, with no test.
One reader, held by this test.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The module and its remix

**Files:**
- Create: `modules/stems/stems.s`, `modules/stems/manifest.py`, `modules/stems/README.md` (from `7dee174`)
- Create: `remixes/stems/remix.py`, `remixes/stems/README.md`
- Modify: `README.md`, `docs/remixes/README.md` (rendered by `make docs`)

**Interfaces:**
- Consumes: `schema.DramRegion`, `Module.dram_regions` (Task 3).
- Produces: the remix `stems` (`REMIX=stems`); the module key `STEM REC`; runtime symbols `stems_frame_hook`, `stems_ata_first`, `stems_action`, `stems_label`, `stems_zero`, `stems_state`, `stems_ring`, `stems_stack`, `stems_buf`, `stems_layout`, `stems_tracks`, `stems_wr`, `stems_rd`, `stems_wr_off`, `stems_rd_off`, `stems_hold`, `stems_probe`, `stems_probe_res`.

- [ ] **Step 1: Bring the module across**

```bash
git checkout 7dee174 -- modules/stems/stems.s modules/stems/manifest.py modules/stems/README.md
git hash-object modules/stems/stems.s
git rev-parse 7dee174:modules/stems/stems.s
```
Expected: the two hashes are equal. (The Windows working copy has CRLF line endings, so its md5 differs; the blob is what gets committed. The md5, `cf735ce0927b23e36b2fa04980cc7536`, is checked in WSL in Step 6 and Task 11.)

- [ ] **Step 2: Give the manifest upstream's table fields, and fix its neighbors**

In `modules/stems/manifest.py`, change the import:
```python
from remix.schema import Category, Detour, DramRegion, Kind, Linked, Module, Poke, Proof, TableGrow
```
In `MODULE = Module(`, after `kind=Kind.CF_PATCH,`:
```python
    category=Category.MACHINES, author="yvesrosius", author_url="https://github.com/yvesrosius",
    proof=Proof.PORT, proof_note="`verify_stems` under the ColdFire port; never flashed",
```
In the docstring, replace:
```
⚠️ UNFLASHED. It shares the frame site with CF PROBE and the CONTROL list
with MENU SHORTCUT; the ledger refuses both pairings by name.
```
with:
```
⚠️ UNFLASHED. No module upstream hooks the frame site or rewrites the
CONTROL list (27 Sep 2026); the ledger refuses one that does, by name.
```
`Category.MACHINES` ("machines and the sequencer") is the closest of upstream's eight categories: STEM REC records what the sequencer plays. Yves may prefer another.

- [ ] **Step 3: Fix the module README's neighbors**

In `modules/stems/README.md`:
- Replace `Flash 13's 60-second take is the first test with sound throughout.` with `The first flash's 60-second take (FLASH.md) is the first test with sound throughout.`
- Replace `Once STEM REC has been selected since power-on, don't run CF PROBE or an OS upgrade until you've power cycled.` (it wraps across two lines) with `Once STEM REC has been selected since power-on, don't run an OS upgrade until you've power cycled.`
- Replace the last two lines, `It shares the frame site with CF PROBE and the CONTROL list with MENU SHORTCUT. The ledger refuses both pairings by name.`, with `No module upstream hooks the frame site or rewrites the CONTROL list (27 Sep 2026). The ledger refuses one that does, by name.`

Re-check the claim first:
```bash
git grep -n -i -E '0x40004b1[0-9a-f]|0x400cbd54|0x400cc5a8|0x40014cfe' -- modules tools/remix ':!modules/stems'
```
Expected: no output. Any hit makes the new sentences false: stop and report it.

- [ ] **Step 4: Write the remix as a folder**

`remixes/stems/remix.py`:
```python
"""STEMS -- STEM REC alone.

T1 to the card while the sequencer plays, from MAIN MENU > CONTROL > STEM
REC, streamed while it records (docs/superpowers/specs/2026-09-22-stem-rec-
streaming-design.md). Nothing else, so a first flash can only fail in one
module's ways.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="stems",
    family="mods", proof=Proof.PORT, proof_note="`verify_stems` under the ColdFire port; never flashed",
    doc="STEM REC alone: T1 to the card while the sequencer plays, streamed.",
    modules=("STEM REC",),
    fallback="NONE",
)
```
`remixes/stems/README.md`:
```markdown
# `stems`: STEM REC alone

One ColdFire module and nothing else. For recording what the tracks play to the card, while the sequencer runs, as one file per track.

## What is in it

- **STEM REC.** MAIN MENU > CONTROL > STEM REC arms a take, or starts one if the sequencer is running. Selecting it again stops the take, and so does stopping the sequencer or reaching 60 minutes. Each enabled track is a 16-bit stereo file, `<set>/AUDIO/YYMMDD-HHMM/T<n>.wav`. This build enables T1. `modules/stems/README.md`.

## Status

Never flashed. Measured under the ColdFire port: `python3 tools/verify/verify_stems.py stems` records takes and checks every sample against the track's own audio. The first flash's plan is `modules/stems/FLASH.md`. The stock facts it stands on are in `docs/firmware/STEM_REC.md`.

## Build

```bash
make image REMIX=stems BUILD=1    # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=stems` runs every gate first.
```

- [ ] **Step 5: Render the tables**

```bash
wslsync
wslrun docs make docs
```
Expected: exit 0. The render ran in WSL, so bring the two files back to Windows:
```bash
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- cat /home/yvez/stemrec2/README.md > README.md
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- cat /home/yvez/stemrec2/docs/remixes/README.md > docs/remixes/README.md
git diff --stat README.md docs/remixes/README.md
```
Expected: `README.md` gains a STEM REC row under "Machines and the sequencer", and `docs/remixes/README.md` gains a `stems` entry under the mods family. Nothing else changes.

- [ ] **Step 6: Build it, and check what the build says**

```bash
wslsync
wslrun md5-stems md5sum modules/stems/stems.s
wslrun bus-stems make bus REMIX=stems
wslrun selftest-stems python3 tools/remix/selftest.py
wslrun docs-gate python3 tools/verify/verify_docs.py
```
Expected: `cf735ce0927b23e36b2fa04980cc7536  modules/stems/stems.s`. The build exits 0 and prints three lines of this form, with addresses that stack down from the reserve's ceiling:
```
  dram region: stems_ring 4,194,304 B at 0x........
  dram region: stems_stack 8,192 B at 0x........
  dram region: stems_buf 270,336 B at 0x........
```
The selftest ends `OK`, with `[PASS] remix 'stems' is clean` and `[PASS] every module declares category, author, author_url, proof`. `verify_docs` passes.

- [ ] **Step 7: Prove the assembler change didn't touch STEM REC's code**

On `crosscheck` a DRAM unit was assembled with `-mcpu=5407`. Upstream assembles every DRAM unit with `-mcpu=54455` (the chip). `.superpowers/v2/asm-same.sh`:
```bash
#!/bin/bash
# stems.s assembled both ways: section contents and relocations must match.
set -euo pipefail
cd /home/yvez/stemrec2
t=$(mktemp -d)
for c in 5407 54455; do
  m68k-elf-as -mcpu=$c -o $t/$c.o modules/stems/stems.s
  m68k-elf-objdump -s -r $t/$c.o | tail -n +3 > $t/$c.txt
done
if cmp -s $t/5407.txt $t/54455.txt; then echo "SAME: 5407 and 54455 assemble stems.s identically"; else diff $t/5407.txt $t/54455.txt | head -20; fi
rm -rf $t
```
```bash
wslrun asm-same bash /mnt/c/Projects/Octabam/.superpowers/v2/asm-same.sh
```
Expected: `SAME`. A difference is a finding: the hook's instructions would differ from the ones every `crosscheck` measurement ran.

- [ ] **Step 8: Commit**

```bash
git add modules/stems/stems.s modules/stems/manifest.py modules/stems/README.md remixes/stems/remix.py remixes/stems/README.md README.md docs/remixes/README.md
git commit -m "stems: STEM REC on upstream -- stems.s byte for byte from 7dee174 (md5 cf735ce0), the manifest with upstream's table fields, the remix as a folder

The docs no longer name CF PROBE or MENU SHORTCUT, which upstream does not
have. Assembled with -mcpu=54455 as upstream assembles every DRAM unit: the
same bytes and relocations as crosscheck's -mcpu=5407.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The fixture, the verifier, and the gate in `make verify`

**Files:**
- Create: `tools/verify/stems_fixture.py`, `tools/verify/verify_stems.py` (from `7dee174`, then edited)
- Modify: `Makefile` (the `verify:` target)
- Create (local): `.superpowers/v2/hookcost.py`

**Interfaces:**
- Consumes: `emu_card.stage_project(project, set_name, name, tree=..., audio=(), image_mb=64) -> (bytes, name)`; `emu_card.extract_image(img) -> {path: bytes}`; the port's flags from Task 5; the remix `stems` from Task 7.
- Produces: `stems_fixture.build(project_dir)`, `stems_fixture.build8(project_dir)`, writing `out/stems_fixture.json` and `out/stems_fixture8.json` (keys `card`, `set`, `project`, `staged`); in `verify_stems.py`, `card_files(card_path) -> {path: bytes}`, `card_get(files, path) -> bytes | None`, `new_entries(files, fixture=None) -> list[str]`, `card_out_sectors(log: str) -> int | None`.

- [ ] **Step 1: Bring the verifier across, and write the parser test**

```bash
git checkout 7dee174 -- tools/verify/verify_stems.py tools/verify/stems_fixture.py
```
In `verify_stems.py`, add `import re` to the imports. After the `writes()` function, add:
```python
CARD_OUT = re.compile(r"^card out\s*:.*\((\d+) bytes, (\d+) sector\(s\) written by the firmware\)")
CARD_OUT_UPSTREAM = ("card out   : out/stems_runs/cardfail.img "
                     "(67108864 bytes, 23 sector(s) written by the firmware)")
CARD_OUT_CROSSCHECK = "card out   : out/stems_runs/cardfail.img (23 sectors written in the run)"


def card_out_sectors(log):
    """The sector count on the port's `card out` line, or None when no line
    has upstream's form. crosscheck's port printed "(23 sectors written in
    the run)", and its parse -- the first word after "(" -- would read the
    BYTE count from upstream's line and pass cardfail whatever happened."""
    for line in log.splitlines():
        m = CARD_OUT.match(line)
        if m:
            return int(m.group(2))
    return None
```
In `main()`, right after `regions(s)`:
```python
    check("the card-out parse reads upstream's line and refuses crosscheck's",
          card_out_sectors(CARD_OUT_UPSTREAM) == 23 and card_out_sectors(CARD_OUT_CROSSCHECK) is None)
```

- [ ] **Step 2: Run the static checks**

```bash
wslsync
wslrun stems-static .venv/bin/python3 tools/verify/verify_stems.py stems
```
Expected: 13 `[PASS]` lines (the 8 image checks, the 4 region checks, and the parse check), then `[SKIP] port runs: build the port (make emu-cf) and the fixture (python3 tools/verify/stems_fixture.py)`, because the clone has no fixture yet. The verifier builds the `stems` image itself first. To see the parse check fail, set `CARD_OUT_UPSTREAM`'s count to 24 once and run again; put it back.

- [ ] **Step 3: Rebuild the fixture on upstream's staging**

In `tools/verify/stems_fixture.py`, replace the two `sys.path.insert` lines and the imports:
```python
sys.path.insert(0, str(ROOT / "tools" / "hw"))
sys.path.insert(0, str(ROOT / "tools" / "emu"))

import ot_project      # noqa: E402
import emu_rtos         # noqa: E402
```
with:
```python
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401

import ot_project      # noqa: E402
import emu_card        # noqa: E402
```
After `KICK_NAME = "kick.wav"`, add:
```python
# Our own staging tree: emu_card.stage_project's default, out/_stage_tree,
# is verify_set's too, and each call deletes the tree first.
STAGE_TREE = ROOT / "out" / "_stems_stage_tree"
```
Replace both calls. In `build()`:
```python
    card_bytes, name = emu_card.stage_project(
        SCRATCH, SET_NAME, PROJECT_NAME, tree=str(STAGE_TREE),
        audio=[f"{kick_src}:AUDIO/{KICK_NAME}"])
```
In `build8()`:
```python
    card_bytes, name = emu_card.stage_project(SCRATCH8, SET_NAME, PROJECT_NAME,
                                              tree=str(STAGE_TREE), audio=audio)
```
Run both fixtures:
```bash
wslsync
wslrun fixture .venv/bin/python3 tools/verify/stems_fixture.py
wslrun fixture8 .venv/bin/python3 tools/verify/stems_fixture.py --eight
```
Expected: each prints `card:`, `set:    STEMS`, `project: ULTFX`, and writes its JSON.

- [ ] **Step 4: Read the card through upstream's reader**

In `verify_stems.py`, delete the line `sys.path.insert(0, "tools/scratch")   # blockdump.py lives here (t1_frames, below)`. `toolpath` puts `tools/harness`, where `blockdump.py` lives now, on the path.

Before `def wav_check`, add:
```python
def card_files(card_path):
    """Every file on a card image, {path: bytes}, paths as the card spells
    them, without a leading slash ('STEMS/AUDIO/000000-0000/T1.wav'). A
    folder with no file in it does not appear: emu_card.extract_image lists
    files (verify_card_reader.py pins that)."""
    import emu_card as ec
    return ec.extract_image(pathlib.Path(card_path).read_bytes())


def card_get(files, path):
    """The file at `path` (case-insensitive, leading slash optional), or None."""
    want = path.lstrip("/").lower()
    return next((d for p, d in files.items() if p.lower() == want), None)


def new_entries(files, fixture=None):
    """What this run added to <set>/AUDIO: the first path component under it
    of every file there, minus what the fixture staged, as the card spells
    it. An empty take folder cannot be seen, so it is not counted."""
    fx = json.loads(pathlib.Path(fixture or FIXTURE).read_text())
    audio = f"{fx['set']}/AUDIO/".lower()
    staged = {n.lower() for n in fx.get("staged", [])}
    names = {p[len(audio):].split("/", 1)[0] for p in files if p.lower().startswith(audio)}
    return sorted(n for n in names if n.lower() not in staged)
```
Replace the card reads, one function at a time.

`wav_check`: replace from `import emu_card as ec` through `data = ec.read_file(img, path)` with:
```python
    files = card_files(card_path)
    fx = json.loads(FIXTURE.read_text())
    audio = f"/{fx['set']}/AUDIO"
    names = new_entries(files)
    check(f"{tag}: one new recording in {audio}", len(names) == 1, f"{names}")
    if not names:
        return
    path = f"{audio}/{names[0]}/T1.wav"
    data = card_get(files, path)
```

`cut`: delete its first line, `import emu_card as ec`. Keep the `port(...)` line and the `st, status, ...` unpacking. Replace the five lines after them, from `img = pathlib.Path(card).read_bytes()` through `data = ec.read_file(...)`, with:
```python
    files = card_files(card)
    fx = json.loads(FIXTURE.read_text())
    names = new_entries(files)
    data = card_get(files, f"{fx['set']}/AUDIO/{names[0]}/T1.wav") if len(names) == 1 else None
```

`take_files`: replace its body with:
```python
    files = card_files(card_path)
    fx = json.loads(pathlib.Path(fixture).read_text())
    names = new_entries(files, fixture)
    if len(names) != 1:
        return []
    folder = f"{fx['set']}/AUDIO/{names[0]}/".lower()
    return sorted((p[len(folder):], d) for p, d in files.items()
                  if p.lower().startswith(folder) and "/" not in p[len(folder):]
                  and p.upper().endswith(".WAV"))
```

`take`: replace its body with:
```python
    files = card_files(card_path)
    fx = json.loads(FIXTURE.read_text())
    names = new_entries(files)
    return card_get(files, f"{fx['set']}/AUDIO/{names[0]}/T1.wav") if len(names) == 1 else None
```

`probe`: delete `import emu_card` at its top, and replace `data = emu_card.read_file(card.read_bytes(), f"/{fx['set']}/PROBE.BIN")` with:
```python
    data = card_get(card_files(card), f"{fx['set']}/PROBE.BIN")
```

`cardfail`: replace the `sectors = next(...)` line and the final check with:
```python
    sectors = card_out_sectors(log)
    # The port refuses a command that STARTS at or past the 20th sector; a
    # raw write of several sectors that starts below it completes.
    check("cardfail: a refused raw write hangs the writer in the stock driver's DRQ poll (known)",
          st == ST_FINISHING and sectors is not None and sectors >= 20 and polls > 100000,
          f"state {st}, {sectors if sectors is not None else 'no card-out line in upstream form:'} "
          f"sectors written, {polls} polls at 0x{DRIVER_DRQ_POLL:x}")
```
Check nothing still reads the old way:
```bash
grep -n -E 'read_file|list_dir|emu_rtos|tools/scratch' tools/verify/verify_stems.py tools/verify/stems_fixture.py
```
Expected: no output.

- [ ] **Step 5: Hook it into `make verify`**

In `Makefile`, at the end of the `verify:` recipe, after the `verify_scenesp2.py` line:
```make
	@# STEM REC: its row, hooks and DRAM regions in the built image, then
	@# (with the port built and tools/verify/stems_fixture.py's cards on
	@# disk) its takes under the port; a remix without it is a one-line pass.
	@# The card reader's round trip first: every take is read back through it.
	@if [ -x .venv/bin/python3 ]; then \
	  .venv/bin/python3 tools/verify/verify_card_reader.py && \
	  .venv/bin/python3 tools/verify/verify_stems.py $(REMIX); \
	else echo "  [SKIP] card reader / STEM REC: no .venv (make emu-setup)"; fi
```

- [ ] **Step 6: Run the whole verifier**

```bash
wslsync
wslrun verify-stems .venv/bin/python3 tools/verify/verify_stems.py stems
```
Run it in the background and tell Yves `/home/yvez/xcheck/v2-verify-stems.log`. Expected: 94 `[PASS]` lines (crosscheck's 93 plus the parse check) and no `[FAIL]`.

- [ ] **Step 7: Compare every value with crosscheck's run**

The reference is `crosscheck`'s last full run, `/home/yvez/xcheck/fx-verify.log` (26 Sep 2026, `7dee174`'s content: 93 PASS, 0 FAIL). `.superpowers/v2/compare.sh`:
```bash
#!/bin/bash
# Every check line of the two runs, side by side: a label that differs, or a
# detail (lag, frames, sectors, polls, stack bytes, peaks) that moved.
a=/home/yvez/xcheck/fx-verify.log
b=/home/yvez/xcheck/v2-verify-stems.log
diff <(grep -E '^\s+\[(PASS|FAIL)\]' "$a") <(grep -E '^\s+\[(PASS|FAIL)\]' "$b")
echo "diff rc $?"
```
```bash
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash -c "tr -d '\r' < /mnt/c/Projects/Octabam/.superpowers/v2/compare.sh > /tmp/v2-compare.sh && bash /tmp/v2-compare.sh"
```
Expected: one added line (the parse check), and no other difference. Values known from the reference: the tap's lag 40 frames, `rowstop` 227 frames, the writer's stack 1052 of 8192 bytes, `cardfail` 23 sectors and 3,562,923 polls, `eight` lag 40 over 342 frames. Each other differing line is a finding. For each one:
1. Re-run that one check's port run and confirm the new value repeats.
2. Find the cause in upstream's changes since 9 Sep (the DSP scheduling defaults, the retired RTOS route, the other author's port changes). Read the run's `out/stems_runs/<tag>.log` beside `crosscheck`'s `/home/yvez/xcheck/wt/out/stems_runs/<tag>.log`.
3. Write the old value, the new value, and the cause into the runlog, for STEM_REC.md section 13 (Task 9).
4. Never widen a check's bound to make it pass. If the cause can't be found, stop and report to Yves.

- [ ] **Step 8: Re-measure the hook's cost**

STEM_REC.md 12.2 gives the raw sums over 400 recording frames: 52,397 instructions at 1 track, 296,000 at 8. `.superpowers/v2/hookcost.py`:
```python
#!/usr/bin/env python3
"""STEM REC's hook cost on this tree, by STEM_REC.md 10.0 and 12.2's method:
400 frames armed before play, no STOP, --coverage, and the raw sum of hits
from stems_frame_hook up to stems_layout. Run from the clone's root after
verify_stems has built the stems image; both fixtures must exist."""
import json
import subprocess

nm = subprocess.run(["m68k-elf-nm", "out/platform/runtime/runtime.elf"],
                    capture_output=True, text=True, check=True).stdout
s = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
lo, hi = s["stems_frame_hook"], s["stems_layout"]
for label, fixture, extra in (
        ("1 track", "out/stems_fixture.json", []),
        ("8 tracks", "out/stems_fixture8.json",
         ["--poke-before-play", f"0x{s['stems_tracks'] + 3:x}=0xff"])):
    fx = json.load(open(fixture))
    cov = f"out/stems_runs/hookcost-{label[0]}.cov"
    subprocess.run(["out/emu/ot_emu", "--image", "out/mainos_bus.bin", "--card", fx["card"],
                    "--set", fx["set"], "--project", fx["project"], "--sequencer",
                    "--internal-clock", "--frames", "400", "--load-ms", "20000", "--dsp",
                    "--main-level", "64", "--pre-roll", "40", "--poke-trig", "2",
                    "--poke", "0x80000029=1", "--call-before-play", f"0x{s['stems_action']:x}:0",
                    "--coverage", cov, *extra], capture_output=True, check=True)
    hits = [(int(a, 16), int(n)) for a, n in (l.split() for l in open(cov))]
    entry = next((n for a, n in hits if a == lo), 0)
    total = sum(n for a, n in hits if lo <= a < hi)
    print(f"{label}: entry hit {entry} times; {total:,} instructions, {total / 400:.2f} per frame")
```
```bash
wslrun hookcost .venv/bin/python3 /mnt/c/Projects/Octabam/.superpowers/v2/hookcost.py
```
Expected: `1 track: entry hit 400 times; 52,397 instructions` and `8 tracks: entry hit 400 times; 296,000 instructions`. A different sum is a finding, handled as in Step 7.

- [ ] **Step 9: Commit**

```bash
git add tools/verify/stems_fixture.py tools/verify/verify_stems.py Makefile
git commit -m "verify_stems: the takes under upstream's port -- read through extract_image, staged by emu_card.stage_project, a card-out parse that cannot pass on the byte count

94 checks (crosscheck's 93 and the parse). Every value compared with
crosscheck's run of 26 Sep: <write 'none moved' or list each moved value
with its cause>. The hook's cost: <the two sums>.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Fill the two angle-bracket lines from Steps 7 and 8 before committing.

---

### Task 9: The documents

**Files:**
- Create: `docs/firmware/STEM_REC.md`, `docs/firmware/CROSSCHECK.md` (from `7dee174`); `docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md`, `docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md`, `docs/superpowers/plans/2026-09-10-stem-rec-poc.md`, `docs/superpowers/plans/2026-09-22-stem-rec-streaming.md`, `docs/superpowers/plans/2026-09-22-crosscheck.md` (from `7dee174`); `modules/stems/FLASH.md`
- Modify: `docs/remixer/FAILURE_MODES.md` (append), `docs/WSL.md`, `docs/proposals/MULTITRACK_TO_CARD.md`, `docs/firmware/STEM_REC.md` (a new section 13)

- [ ] **Step 1: Bring the records across unchanged**

```bash
git checkout 7dee174 -- docs/firmware/STEM_REC.md docs/firmware/CROSSCHECK.md \
  docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md \
  docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md \
  docs/superpowers/plans/2026-09-10-stem-rec-poc.md \
  docs/superpowers/plans/2026-09-22-stem-rec-streaming.md \
  docs/superpowers/plans/2026-09-22-crosscheck.md
```
These are records. Their citations of `FLASHPLAN.md`, `PLAN.md`, `emu_rtos`, `tools/scratch`, CF PROBE, and MENU SHORTCUT stay as written: AGENTS.md's history rule keeps a citation as the provenance of what it sits beside.

- [ ] **Step 2: Carry Flash 13 into the module**

```bash
{ printf '# STEM REC: the first flash\n\nCarried from `docs/effects/FLASHPLAN.md` on branch `crosscheck` (`7dee174`), which upstream does not have: upstream records flashed images in `CHANGELOG.md`, and this one has not been flashed. Read the old file with `git show 7dee174:docs/effects/FLASHPLAN.md`.\n\n'
  git show 7dee174:docs/effects/FLASHPLAN.md | sed -n '/^## Flash 13 /,$p'
} > modules/stems/FLASH.md
head -12 modules/stems/FLASH.md
```
Expected: the file starts with the new title and paragraph, then `## Flash 13 — \`stems\`, tag 28: ...`.

- [ ] **Step 3: Append the failure-mode block**

```bash
git show 7dee174:docs/remixer/FAILURE_MODES.md | sed -n '/^## STEM REC (`modules\/stems`, remix `stems`)/,$p' > /tmp/v2-fm.md
head -3 /tmp/v2-fm.md
printf '\n' >> docs/remixer/FAILURE_MODES.md
cat /tmp/v2-fm.md >> docs/remixer/FAILURE_MODES.md
grep -n -E 'FLASHPLAN|Flash 13|CF PROBE|MENU SHORTCUT' docs/remixer/FAILURE_MODES.md
```
FAILURE_MODES is a live register, so its references must resolve upstream. Change each `docs/effects/FLASHPLAN.md` Flash 13 reference the grep finds to `modules/stems/FLASH.md`, and drop a CF PROBE or MENU SHORTCUT mention the same way Task 7, Step 3 did.

- [ ] **Step 4: Apply the WSL and proposal edits**

```bash
git diff 1667995 7dee174 -- docs/WSL.md docs/proposals/MULTITRACK_TO_CARD.md > /tmp/v2-docs.patch
git apply --3way /tmp/v2-docs.patch
git status --short docs/WSL.md docs/proposals/MULTITRACK_TO_CARD.md
```
Expected: both files modified. Where a hunk conflicts, keep upstream's newer text (for example its removal of `hello-dram` from the list of remixes with linked units) and add `crosscheck`'s content around it.

- [ ] **Step 5: Write STEM_REC.md section 13, on upstream**

Append to `docs/firmware/STEM_REC.md`:
```markdown
## 13. On upstream (branch `stem-rec-v2`)

STEM REC was carried from `crosscheck` (`7dee174`) onto upstream `main` at
`<base sha from the runlog>` on <date> (spec:
`docs/superpowers/specs/2026-09-26-stem-rec-upstream-port-design.md`).
`stems.s` is byte-identical (md5 `cf735ce0927b23e36b2fa04980cc7536`). Image
SHA-256 `164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e`.

### 13.1 What the port changed around the module ✅

- The runtime is assembled with `-mcpu=54455`, as upstream assembles every
  DRAM unit, where `crosscheck` used `-mcpu=5407`. Both give the same section
  contents and relocations for `stems.s` (Task 7's check, <date>).
- The verifier reads takes with `emu_card.extract_image`, stages its card
  with `emu_card.stage_project`, and runs the port's own flags for several
  calls before play (`--call-before-play`), calls at frames (`--at`), a poke
  before play, and a failing card.
- `extract_image` can't see a folder with no file in it. A take that makes
  its folder and writes nothing reads as no take.

### 13.2 The pinned values, against `crosscheck`'s run of 26 Sep 2026

| Value | `crosscheck` | `stem-rec-v2` | Cause |
|---|---|---|---|
```
Fill one row per value from the runlog: every value Task 8, Step 7 listed (the lag, `rowstop`'s frames, the stack, `cardfail`'s sectors and polls, `eight`'s lag and frames) and Task 8, Step 8's two sums. A value that didn't move gets `same` in the Cause column. Mark each row ✅ measured. If a cause is inferred, say so with 🟡 and name what would falsify it.

- [ ] **Step 6: Check the prose**

```bash
grep -n -E ' -- | — |There (is|are)' modules/stems/FLASH.md remixes/stems/README.md
sed -n '/^## 13\. On upstream/,$p' docs/firmware/STEM_REC.md | grep -n -E ' -- | — |There (is|are)'
```
Expected: no hit in the prose this task wrote. Text carried from `crosscheck` stays as it was.

- [ ] **Step 7: Commit**

```bash
git add docs/firmware/STEM_REC.md docs/firmware/CROSSCHECK.md docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md docs/superpowers/plans/2026-09-10-stem-rec-poc.md docs/superpowers/plans/2026-09-22-stem-rec-streaming.md docs/superpowers/plans/2026-09-22-crosscheck.md modules/stems/FLASH.md docs/remixer/FAILURE_MODES.md docs/WSL.md docs/proposals/MULTITRACK_TO_CARD.md
git commit -m "docs: STEM REC's records on upstream -- STEM_REC.md with section 13 (the values against crosscheck's run), Flash 13 as modules/stems/FLASH.md, its failure modes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: The FAT32 run

**Files:**
- Modify: `tools/emu/emu_card.py` (`_Fat16` gains `EOC` and `_store_root`; a `_Fat32` class; `build_image` and `stage_project` gain `fat`; `extract_image` reads FAT32)
- Modify: `tools/verify/verify_card_reader.py` (FAT32 cases)
- Modify: `tools/verify/stems_fixture.py` (`--fat32`)
- Modify: `tools/verify/verify_stems.py` (`--fat32`: the mount check, then the take checks on FAT32)
- Modify: `docs/firmware/STEM_REC.md` (a new section 14)

**Interfaces:**
- Consumes: `card_files`, `card_get`, `new_entries`, `port` (Task 8).
- Produces: `emu_card.build_image(tree_dir, size_mb=64, label="OCTABAM", part_start=2048, log=None, fat=16, part_type=None) -> bytes`; `emu_card.stage_project(..., fat=16)`; `extract_image` reading FAT16 and FAT32; `stems_fixture.build(project_dir, fat=16)`, writing `out/stems_fixture32.json` and `out/stems_fixture32_card.img` when `fat=32`; `verify_stems.py stems --fat32`.

- [ ] **Step 1: Read the firmware's mount code first**

The emulator's card code says the mount at `0x400168e8` accepts partition types 4, 6, and 0x0e, and the BPB check at `0x40017ad4` needs a FAT of at most 16,384 sectors. FAT32's types are 0x0b and 0x0c. Before building any image, read both routines:
```bash
wslrun mount-read bash -c 'scripts/disasm.sh emac 0x400168e8 512 && echo ---- && scripts/disasm.sh emac 0x40017ad4 768'
```
The length is in decimal bytes: `disasm.sh` hands it to `dd`, which reads `0x200` as 0 times 200.
From the listing, answer and record in the runlog, each with the instruction addresses that show it:
1. Which partition-type bytes the mount compares, and what happens on each.
2. Whether the BPB check branches on `FATSz16 == 0` (offset 22) to read `FATSz32` (offset 36) and `RootClus` (offset 44).
3. Whether the 16,384-sector limit applies to FAT32. The unit's 64 GB card with 32 KB clusters has 2,097,152 clusters, a FAT of exactly 16,384 sectors.
4. Whether the cluster count decides the FAT type, and at what threshold.
5. Whether the mount reads the FSInfo sector (offset 48).

Follow each `jsr` the answers depend on. If the listing shows the mount refuses FAT32 outright, stop and report to Yves before Step 2: the unit's own card would then need explaining first.

- [ ] **Step 2: Write section 14's reading**

Append to `docs/firmware/STEM_REC.md`:
```markdown
## 14. FAT32

Every take before this section ran on a FAT16 image. The unit's card is
FAT32.

### 14.1 The mount, read from the image ✅

Method: `scripts/disasm.sh emac` over `0x400168e8` and `0x40017ad4`, image
SHA-256 `164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e`.
```
Then one paragraph per answer from Step 1, each citing its addresses, each marked ✅ where the listing shows it and 🟡 where it's inferred. Commit:
```bash
git add docs/firmware/STEM_REC.md
git commit -m "STEM_REC 14.1: the firmware's FAT32 mount, read from the image before building a FAT32 card

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 3: Write the failing FAT32 round trip**

In `tools/verify/verify_card_reader.py`, add `import struct`. In `main()`, after the FAT16 hash check and still inside the `with` block:
```python
        img32 = ec.build_image(str(tree), 64, fat=32)
        check("FAT32: the partition type is 0x0c", img32[446 + 4] == 0x0C, f"0x{img32[446 + 4]:02x}")
        part = struct.unpack_from("<I", img32, 446 + 8)[0] * 512
        check("FAT32: the BPB says FAT32", img32[part + 82:part + 90] == b"FAT32   ",
              repr(img32[part + 82:part + 90]))
        got32 = ec.extract_image(img32)
        for rel, data in FILES.items():
            check(f"FAT32: /{rel} ({len(data):,} B)", got32.get(rel) == data,
                  "" if rel in got32 else "missing")
        check("FAT32: nothing read back that was not written", set(got32) == set(FILES),
              f"{sorted(set(got32) - set(FILES))}")
        try:
            ec.build_image(str(tree), 16, fat=32)
            check("FAT32: a 16 MB image is refused (too few clusters)", False)
        except ValueError as e:
            check("FAT32: a 16 MB image is refused (too few clusters)", "not FAT32" in str(e), str(e))
```
Run the test:
```bash
wslsync
wslrun card-reader-32-red .venv/bin/python3 tools/verify/verify_card_reader.py
```
Expected: the eight FAT16 checks pass, including Task 6's hash, and then a `TypeError: build_image() got an unexpected keyword argument 'fat'`.

- [ ] **Step 4: Build and read FAT32**

In `tools/emu/emu_card.py`, class `_Fat16`: add the class attribute `EOC = 0xFFFF` under `class _Fat16:`. In `alloc_chain`, replace `else 0xFFFF` with `else self.EOC`. In `_chain_len`, replace `while c != 0xFFFF and c != 0` with `while c != self.EOC and c != 0`. In `build_dir`, replace the root branch:
```python
        if is_root:
            if len(entries) > len(self.root):
                raise ValueError("too many root entries")
            self.root[:len(entries)] = entries
            return bytes(entries), 0
```
with:
```python
        if is_root:
            return self._store_root(entries)
```
and add the method to `_Fat16`:
```python
    def _store_root(self, entries):
        if len(entries) > len(self.root):
            raise ValueError("too many root entries")
        self.root[:len(entries)] = entries
        return bytes(entries), 0
```
After `_Fat16`, add:
```python
class _Fat32(_Fat16):
    """The same builder, FAT32 as a formatter lays it out: 32 reserved
    sectors (the boot sector, FSInfo at 1, the backup boot sector at 6),
    32-bit FAT entries, and the root directory as a cluster chain from
    cluster 2, with FAT16's capacity of 512 entries."""

    EOC = 0x0FFFFFFF

    def __init__(self, total_sectors, sectors_per_cluster, part_start):
        self.spc = sectors_per_cluster
        self.cluster_bytes = SECTOR * self.spc
        self.reserved = 32
        self.nfats = 2
        self.root_entries = 0
        self.root_sectors = 0
        self.total = total_sectors
        clusters = (self.total - self.reserved) // self.spc
        self.spf = ((clusters + 2) * 4 + SECTOR - 1) // SECTOR
        self.data_start = self.reserved + self.nfats * self.spf
        self.nclusters = (self.total - self.data_start) // self.spc
        if self.nclusters < 65525:
            raise ValueError(f"{self.nclusters} clusters is not FAT32 (65525 or more); "
                             "make the image larger or the clusters smaller")
        self.fat = [0] * (self.nclusters + 2)
        self.fat[0] = 0x0FFFFFF8
        self.fat[1] = 0x0FFFFFFF
        self.next_free = 2
        self.data = bytearray(self.nclusters * self.cluster_bytes)
        self.root = bytearray()
        self.part_start = part_start
        self.root_cluster = self.alloc_chain(b"\x00" * (512 * 32))

    def _store_root(self, entries):
        if len(entries) > self.cluster_bytes * self._chain_len(self.root_cluster):
            raise ValueError("too many root entries")
        off = (self.root_cluster - 2) * self.cluster_bytes
        self.data[off:off + len(entries)] = entries
        return bytes(entries), 0

    def volume(self, label):
        bpb = bytearray(SECTOR)
        bpb[0:3] = b"\xEB\x58\x90"
        bpb[3:11] = b"MSWIN4.1"
        struct.pack_into("<HBHBHHBHHHII", bpb, 11, SECTOR, self.spc, self.reserved,
                         self.nfats, 0, 0, 0xF8, 0, 63, 255, self.part_start, self.total)
        struct.pack_into("<IHHIHH", bpb, 36, self.spf, 0, 0, self.root_cluster, 1, 6)
        bpb[64] = 0x80
        bpb[66] = 0x29
        struct.pack_into("<I", bpb, 67, 0x0C7A0BA8)          # volume serial
        bpb[71:82] = label.upper().ljust(11)[:11].encode("ascii")
        bpb[82:90] = b"FAT32   "
        bpb[510:512] = b"\x55\xAA"
        info = bytearray(SECTOR)
        struct.pack_into("<I", info, 0, 0x41615252)
        struct.pack_into("<III", info, 484, 0x61417272,
                         self.nclusters + 2 - self.next_free, self.next_free)
        struct.pack_into("<I", info, 508, 0xAA550000)
        head = bytearray(self.reserved * SECTOR)
        head[0:SECTOR] = bpb
        head[SECTOR:2 * SECTOR] = info
        head[6 * SECTOR:7 * SECTOR] = bpb
        head[7 * SECTOR:8 * SECTOR] = info
        fat = bytearray(self.spf * SECTOR)
        struct.pack_into(f"<{len(self.fat)}I", fat, 0, *self.fat)
        return bytes(head) + bytes(fat) * self.nfats + bytes(self.data)
```
Replace `build_image`'s signature, docstring, and first five lines:
```python
def build_image(tree_dir, size_mb=64, label="OCTABAM", part_start=2048, log=None, fat=16,
                part_type=None):
    """MBR + one FAT16 partition holding the directory tree at `tree_dir`;
    fat=32 builds FAT32 instead (512-byte clusters, partition type 0x0c
    unless `part_type` says otherwise)."""
    total = size_mb * 1024 * 1024 // SECTOR
    part_sectors = total - part_start
    if fat == 32:
        fs = _Fat32(part_sectors, 1, part_start)
        ptype = 0x0C if part_type is None else part_type
    elif fat == 16:
        spc = 4 if size_mb <= 128 else (8 if size_mb <= 256 else 16)
        fs = _Fat16(part_sectors, spc, part_start)
        ptype = 0x06 if part_type is None else part_type
    else:
        raise ValueError(f"fat={fat}: 16 or 32")
```
In its `struct.pack_into("<BBBBBBBBII", mbr, 446, ...)` call, replace the literal `0x06` with `ptype`. If Step 1 found the mount takes 0x0b and not 0x0c, make 0x0b the FAT32 default here and in the test.

In `stage_project`, add `fat=16` after `image_mb=64` in the signature, and pass it on: `return build_image(str(tree), image_mb, fat=fat), name`.

In `extract_image`, replace the lines from `root_sectors = ...` through the `chain` function with:
```python
    fat32 = spf == 0 and root_entries == 0
    if fat32:
        spf = struct.unpack_from("<I", bpb, 36)[0]
        root_cluster = struct.unpack_from("<I", bpb, 44)[0]
    root_sectors = root_entries * 32 // bps
    fat_off = (part_start + reserved) * bps
    fat = struct.unpack_from(f"<{spf * bps // (4 if fat32 else 2)}{'I' if fat32 else 'H'}", img, fat_off)
    root_off = (part_start + reserved + nfats * spf) * bps
    data_off = root_off + root_sectors * bps
    cb = spc * bps
    eoc = 0x0FFFFFF8 if fat32 else 0xFFF8

    def chain(c):
        out = []
        while 2 <= c < eoc and len(out) < 100000:
            out.append(c)
            c = fat[c] & 0x0FFFFFFF if fat32 else fat[c]
        return out
```
Replace `walk(img[root_off:data_off], "")` with:
```python
    walk(cluster_bytes(root_cluster) if fat32 else img[root_off:data_off], "")
```
Update the module docstring's first item to say the builder writes FAT16, or FAT32 with `fat=32`.

- [ ] **Step 5: Run the round trip and watch it pass**

```bash
wslsync
wslrun card-reader-32 .venv/bin/python3 tools/verify/verify_card_reader.py
```
Expected: every check passes, including `FAT16: the image is what upstream's builder made`. That check, pinned in Task 6 before the builder changed, proves the FAT16 path unchanged. Commit:
```bash
git add tools/emu/emu_card.py tools/verify/verify_card_reader.py
git commit -m "emu_card: FAT32 images, built and read back -- the FAT16 builder byte-identical (pinned by hash)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Stage the fixture on FAT32**

In `tools/verify/stems_fixture.py`, after `FIXTURE_JSON = ...`:
```python
CARD32_OUT = ROOT / "out" / "stems_fixture32_card.img"
FIXTURE32_JSON = ROOT / "out" / "stems_fixture32.json"
```
Change `def build(project_dir=DEFAULT_PROJECT):` to `def build(project_dir=DEFAULT_PROJECT, fat=16):`. In it, pass `fat=fat` to `emu_card.stage_project`, and choose the outputs:
```python
    card_out, fixture_json = (CARD32_OUT, FIXTURE32_JSON) if fat == 32 else (CARD_OUT, FIXTURE_JSON)
```
Use `card_out` and `fixture_json` where the function wrote `CARD_OUT` and `FIXTURE_JSON`, including the `"card"` key and the final `print`. In the `__main__` block, add before the `else`:
```python
    elif len(sys.argv) > 1 and sys.argv[1] == "--fat32":
        build(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROJECT, fat=32)
```
```bash
wslsync
wslrun fixture32 .venv/bin/python3 tools/verify/stems_fixture.py --fat32
```
Expected: `card:    .../out/stems_fixture32_card.img`, and `out/stems_fixture32.json` written.

- [ ] **Step 7: The mount check, with FAT16 as its control**

`FW_CARD_READY` (`0x460d1cb8`, `emu_card.py`) is set to 1 after the firmware's card init and mount. A FAT16 run must read 1 there first; otherwise the byte doesn't mean that under this port, and a 0 on FAT32 proves nothing.

In `tools/verify/verify_stems.py`, after `FIXTURE8 = ...`:
```python
FIXTURE32 = pathlib.Path("out/stems_fixture32.json")   # tools/verify/stems_fixture.py --fat32
CARD_READY = 0x460d1cb8     # emu_card.FW_CARD_READY: := 1 after the firmware's card init and mount
SUFFIX = ""                 # appended to every run's tag: "32" while the FAT32 checks run


def run_path(tag, ext):
    """A file a run wrote: out/stems_runs/<tag><SUFFIX>.<ext>."""
    return pathlib.Path("out/stems_runs") / f"{tag}{SUFFIX}.{ext}"
```
In `port()`, make the first line of the body `tag = f"{tag}{SUFFIX}"`. Replace each fixed run path with `run_path`: in `full`, `pathlib.Path("out/stems_runs/full.stack")` becomes `run_path("full", "stack")`; in `wrap`, `pathlib.Path("out/stems_runs/wrap.offs")` becomes `run_path("wrap", "offs")`; in `exists`, `pathlib.Path("out/stems_runs/full.img")` becomes `run_path("full", "img")`; in `probe`, both `pathlib.Path("out/stems_runs") / "probe.res"` become `run_path("probe", "res")`. `cardfail` isn't run on FAT32 and keeps its path.

Add after `probe`:
```python
def fat32(s):
    """The take checks on a FAT32 card (the unit's card is FAT32; every take
    before this ran on FAT16). First the mount byte, on the FAT16 card as a
    control and then on the FAT32 card: if the firmware did not mount the
    card, one check says so and no take check runs, since each would fail on
    'no new recording' for that one reason."""
    global FIXTURE, SUFFIX
    if not FIXTURE32.exists():
        check("fat32: the FAT32 fixture exists (stems_fixture.py --fat32)", False)
        return
    ready = {}
    for fixture, tag in ((FIXTURE, "mount16"), (FIXTURE32, "mount32")):
        port(s, 50, tag=tag, dump_blocks=False, fixture=fixture, mems=((CARD_READY, 4, "ready"),))
        raw = run_path(tag, "ready")
        ready[tag] = raw.read_bytes() if raw.exists() else b""
    check("fat32: control -- the FAT16 card reads as mounted", ready["mount16"][:1] == b"\x01",
          ready["mount16"].hex())
    mounted = ready["mount32"][:1] == b"\x01"
    check("fat32: the firmware mounted the FAT32 card", mounted, ready["mount32"].hex())
    if not (mounted and ready["mount16"][:1] == b"\x01"):
        return
    saved = FIXTURE
    FIXTURE, SUFFIX = FIXTURE32, "32"
    try:
        print("  -- the take checks on FAT32 --")
        probe(s)
        full(s)
        rowstop(s)
        stream(s)
        wrap(s)
        cap(s)
        cut(s)
        exists(s)
        overflow(s)
    finally:
        FIXTURE, SUFFIX = saved, ""
```
`probe` isn't in the spec's list. It's here because it's the smallest direct test of the raw file routines, and FAT32 is where they're new.

In `main()`, after the `if "--long" in sys.argv: limit(s)` lines (inside the port-runs branch):
```python
        if "--fat32" in sys.argv:
            fat32(s)
```
Add `--fat32` to the module docstring's usage line.

- [ ] **Step 8: Run the FAT32 checks**

```bash
wslsync
wslrun verify-stems-fat32 .venv/bin/python3 tools/verify/verify_stems.py stems --fat32
```
Run in the background; tell Yves `/home/yvez/xcheck/v2-verify-stems-fat32.log`. Read the result in this order:
1. **The control fails:** the byte doesn't mean "mounted" under this port. Stop, find a marker that reads as mounted on FAT16 (for example, the fixture's project loading), and use it instead. Report it as a finding in the runlog.
2. **The FAT32 mount fails:** a finding. Record what the port's log shows about the mount (`out/stems_runs/mount32.log`), and compare it with section 14.1's reading.
3. **A take check fails:** a finding. Record the check, its detail, and the run's log.

Report every finding to Yves before writing any fix. A fix, once agreed, is its own commit, named for the defect.

- [ ] **Step 9: Write section 14's results, and commit**

Append to STEM_REC.md section 14:
```markdown
### 14.2 The take checks on FAT32

Method: `python3 tools/verify/verify_stems.py stems --fat32`, <date>, a
64 MB image with 512-byte clusters (`stems_fixture.py --fat32`).
```
Then list each check's result and each finding, with its evidence. Add this known gap as its own paragraph: the unit's 64 GB card uses 32 KB clusters, and a FAT32 image needs at least 65,525 clusters, so 32 KB clusters need an image of at least 2 GB. This run used 512-byte clusters, which cross a cluster boundary every sector. Commit:
```bash
git add tools/verify/stems_fixture.py tools/verify/verify_stems.py docs/firmware/STEM_REC.md
git commit -m "verify_stems --fat32: STEM REC's takes on a FAT32 card, the mount checked first against a FAT16 control -- <result in a few words>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: The final gates

**Files:** none new. Records go in the runlog and the last commit's message.

- [ ] **Step 1: Both trees on the last commit**

```bash
git status --porcelain
wslsync
```
Expected: `git status` prints nothing; `wsl: HEAD <same sha>, 0 file(s) differ from it`.

- [ ] **Step 2: Run the gates**

Start each in the background, one after another, and tell Yves each log path as it starts:
```bash
wslrun final-check-stems make check REMIX=stems
wslrun final-check-bamsep26 make check REMIX=bamsep26
wslrun final-stems-long .venv/bin/python3 tools/verify/verify_stems.py stems --long --fat32
wslrun final-dram-boot env REMIX=stems python3 tools/verify/verify_dram_boot.py
wslrun final-refhash bash -c 'git hash-object scripts/refhash.sh && scripts/refhash.sh check'
wslrun final-remixhash bash /mnt/c/Projects/Octabam/.superpowers/v2/remixhash.sh check
wslrun final-md5 md5sum modules/stems/stems.s
```
Expected:
- Both `make check` runs exit 0 and end `all runnable checks passed`. Each `[SKIP]` line names what it skipped and why.
- `--long --fat32`: 94 FAT16 checks and the `limit` check pass; the FAT32 part passes, or each failure is a finding already reported in Task 10.
- `verify_dram_boot`: both `[PASS]` lines, the loader ran once, its fatal hang 0x.
- `ALL 26 CASES BIT-IDENTICAL`.
- `remixhash`: every line identical except one added line for `stems`.
- `cf735ce0927b23e36b2fa04980cc7536  modules/stems/stems.s`.

- [ ] **Step 3: Check the spec's "done when" list**

Go through the spec's section 7 line by line, and write each line with its evidence (the log path and the line that proves it) into the runlog. Any line without evidence isn't done.

- [ ] **Step 4: Update the memory note, and hand over**

Update `stem-rec-v2-in-progress.md` in the memory folder: piece 1 done (or what's open), the branch's last commit, the logs that prove it, and that nothing was pushed. Then report to Yves: the gates and their results, each finding, and the decisions waiting for him (the FAT32 result, whether FAT32 joins `make check`, whether to offer `DramRegion` and the two general fixes upstream).
