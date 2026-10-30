# Working in this repository

octabam is a remixer for the Octatrack's OS: it composes modules, each
credited to its author, into one image built from the user's own 1.40C.
`README.md` says what each module and remix is and where it has run;
`CHANGELOG.md` records each flashed image. `docs/README.md` lists every doc
by reader; `docs/contributing/PLACEMENT.md` is the architecture record for
where code goes and what is measured about the memory.

The repo is organised as **modules** (`modules/<name>/manifest.py` declares one
contribution) composed into **remixes** (`remixes/<name>/remix.py` selects a
set, `README.md` beside it says where it has run; `remixes/test/<name>/`
carries one module for its gates).
`make modules` lists them, with the compatibility matrix.
`docs/contributing/MODULES.md` is the contributor guide and
`CONTRIBUTING.md` the contract. The build refuses to start when two selected
modules claim the same cave, hook or detour span, poke, table or
symbol ref, runtime write, kept stock bytes, grown stock table,
core-private Y word, per-core FX2 buffer region or DSP data range
(`Claims.dsp_ranges`), or declare each other a conflict — by name.

**Modules come in kinds, and the traps below say which they belong to.** A
**ColdFire module** (linked GNU-as units, detours by symbol, a runtime in
DRAM: KITS, midi-scenes, tempo-sync) never touches the DSP and none of the DSP traps
apply to it; its own traps are the ColdFire half of
`docs/contributing/TRAPS.md`. On the DSP side an
insert has no bus role, no shared-window claim, sits in both payloads and
runs on any track; a **server** pays for the rotation, the housekeeping
election, the auto-gain and the payload asymmetry, and most of the DSP
traps are a server's.

**A port is a proof.** The author's own build is the oracle: `pinned`,
`reference(addr)` and `Linked.reference` are three forms of one rule, and
the build refuses on drift. Never "port" by
rewriting; run their build against the shared stock image first.

**If you change the BUILD rather than a module, prove it changed nothing:**
`scripts/refhash.sh check` — 24 configurations, artifacts and build reports,
bit-identical against the baseline of your branch's merge-base with
origin/main (`tools/verify/refhash_store.py` saves it once per merge-base for
every worktree; `REFHASH_LOCAL=1` compares against a `save` of this tree).
(Since 10 Sep 2026 the report
prints tool paths; a path change is a report change and needs a re-save
after the artifacts are shown identical.)

**Never an Elektron byte in the repo** — no image, no slice, no `.syx`, in a
commit or on an issue. `.incbin` from the user's stock image at build time
is the pattern.

## Build and check

```bash
make modules                    # the index, the compatibility matrix, the remixes
make check REMIX=<name>         # build + cycles + every gate + boot under the port, no hardware
OT_PROJECT=<dir> [OT_BANK=2] make check REMIX=<name>   # + that project on the image under the port: ids, page-2 delivery, chain audio, main out
make bus REMIX=<name>           # THE build (XBUS=1 SPEC=1) -> out/mainos_bus.bin
make render REMIX=<name>        # hear the bus locally, ~6x real time
make reverb IN=loop.wav ARGS='--wet --mode all'
```

Never claim something works because it assembled or linked. `make check` (run by CI) is
the floor; `docs/contributing/TESTING.md` says what each gate proves and what
none of them can see.

**Before opening a PR, and again before merging one:** rebase onto
`origin/main`. CI's reach job runs the gates the diff reaches, and the
`refhash` bit-identity pass for a build change, on every push to `main` and every
PR, fork PRs included, on a runner that downloads the 1.40C for that run
(`CONTRIBUTING.md` "Before you open a PR" is the rule and the reason); the
PR body links the run and lists each gate's result from its log. A first-time
contributor's run waits for maintainer approval. **Run no whole-remix check
and no reach or refhash pass locally before a PR: they take hours and CI runs
them.** Locally, run only the one gate script for the change
(`python3 tools/verify/verify_<name>.py <remix>`), push, and read
`gh pr checks`; a local whole-remix run is for a failure CI has reported that
the one script cannot reproduce. A change to
`.github/`, `scripts/` or the Makefile runs every CI job. Passes whose image
and inputs did not move are reported `cached`.

**A change that alters what a remix does — its modules, effects, menus,
costs or proof status — updates the hand-written manual site pages under
`docs/site/` in the same PR.** The generated reference pages update
themselves from the manifests (`tools/site/gen_pages.py`).

**Screenshots:** after a rebase, and before the PR, check whether the diff
changes a screen a shot shows; `docs/contributing/SCREENSHOTS.md` has the
check and the `capture_manual.py` groups.

## Worktrees and the shared checkout

**ALWAYS WORK IN A GIT WORKTREE, never in the main checkout.** Several
sessions share this repository at once; the main checkout's working tree,
index and stash list are theirs as much as yours. Start every task with
`git worktree add .claude/worktrees/<name> -b <branch> origin/main`, work
and run the gates there, and open the PR from it. Never `git stash` or
`git stash pop` in the main checkout: on 13 Sep 2026 a pop there took
another session's stash (`o14 port edits`) instead of the caller's own
and a `stash drop` removed it from the list -- restored by commit SHA,
but only because the dangling commits were still there. In a worktree:
`vendor/` and `.venv/` are symlinks to the main checkout's (gitignored,
and excluded in `.git/info/exclude`); `out/raw/section_3_MAIN_OS.bin`
must be there too (`make os && make recon`, or copy it); without them the
selftest reports "remix X does not build" and every gate fails before it
starts. `git submodule update --init` in the worktree as well. **Do NOT
symlink `out/emu`**: its CMake cache names the main checkout's sources,
so `cmake --build` there compiles THEIR `tools/emu/ot_emu`, not yours
(14 Sep 2026: a port edit "built" fine and the binary did not have it).
Build the port into the worktree: `make emu-cf` (a fresh cache, ~1 min).
`out/cache/` is the build's memo (the packed runtimes, keyed by the sha256
of their inputs; `tools/remix/pack.py`), per worktree and safe to
delete; `OCTABAM_NO_CACHE=1` builds cold when a build result is in doubt.
**The same holds for `dsp_host` and `dsp_asm`:** `scripts/setup.sh` builds
them from a COPY staged into `vendor/dsp56300/source/dsp_host/`, so in a
worktree the shared binary is the main checkout's, whatever the branch's
`tools/harness/dsp_host/dsp_host.cpp` says, and `dsp_host` ignores an
option it does not know (PR #356 was reviewed twice, 21–22 Sep 2026, as
"MOD has no effect, residual 0.000": its `-paramfile` never ran and every
render used default knobs). A branch that changes `dsp_host.cpp` is built
in an isolated tree, never into `vendor/` — the CMake recipe is
`docs/contributing/TOOLING.md` section 1 — then point the harness at it
(`benchmark_reverbs.HOST`, `send_probe`'s host path) for that run.

## The trap register

The traps that have already cost real work live in
[`docs/contributing/TRAPS.md`](docs/contributing/TRAPS.md): symptom, what
it cost, the fix, and what now gates each one. Add a new trap there the
moment it costs real work, and add its line here.

**DSP side**

- [The assembler mis-encodes instructions, silently](docs/contributing/TRAPS.md#trap-asm) — `tfr a,b`→`rnd b`; unknown `mpy` operand orders→`mpysu` (second operand unsigned); `cmp a,b`→`max a,b`. Disassemble what you assemble.
- [Reading `a0` exposes the fractional left shift](docs/contributing/TRAPS.md#trap-a0) — integer use of a0 is 2× the multiplier. Pin it with a predictable-arithmetic test.
- [`asr #n,a,a` leaves the remainder in a0 and Z tests all 56 bits](docs/contributing/TRAPS.md#trap-asr-a0) — reload clean (`move a,x1 / move x1,a / tst a`) before a `teq`/`cmp` snap.
- [A logical op leaves A2 stale; the next store saturates](docs/contributing/TRAPS.md#trap-a2-stale) — use the Tcc conditional transfers, not hand-rolled sign masks.
- [A Tcc pair sharing one compare breaks if arithmetic lands between](docs/contributing/TRAPS.md#trap-tcc-pair) — park the compare's result; check what the code below assumed about condition codes.
- [`move a,b` limits; `tfr a,b` moves all 56 bits](docs/contributing/TRAPS.md#trap-move-tfr) — interchangeable only when the source fits 24 bits.
- [`Tcc` takes a register source; `clr` takes an accumulator](docs/contributing/TRAPS.md#trap-tcc-operands) — move the value through `x0`.
- [`lua (rN+d)` takes d in −64..63 and wraps silently](docs/contributing/TRAPS.md#trap-lua) — past ±63: `move r7,r5 / move #imm,n5 / move (r5)+n5`.
- [`dsp_asm` resolves labels by prefix](docs/contributing/TRAPS.md#trap-label-prefix) — no new label may have an existing label as its prefix (`warmz2` next to `warmz` branched into hyperspace).
- [Build-time markers and base literals count in comments](docs/contributing/TRAPS.md#trap-markers) — don't spell `$30000` or the `; X` markers in comments.
- [A form the chip has never run is not proven by the port](docs/contributing/TRAPS.md#trap-chip-form) — grep stock payloads before using a form.
- [No `rep` in `init`/`proc`; no dense X work in a DMA's 8K block](docs/contributing/TRAPS.md#trap-rep-dma) — `tools/build/norep.py` refuses the former; the port models neither.
- [`SPEC=1` requires `XBUS=1`](docs/contributing/TRAPS.md#trap-spec-xbus) — build-guarded; do not ungate.
- [The track↔core mapping is inverted](docs/contributing/TRAPS.md#trap-track-core) — A = tracks 5-8 (BusVerb), B = 1-4 (BusDelay). Test reverb on track 5.
- [SEND's `DEL` and `REV` are separate knobs](docs/contributing/TRAPS.md#trap-send-knobs) — `x:(r6+0)` and `x:(r6+1)`.
- [A cloned descriptor inherits the donor's formatter, and it outranks the value count](docs/contributing/TRAPS.md#trap-formatter) — `verify_menu` checks renderer against count.
- [Stock Unicorn halves fractional EMAC multiplies and adds where `msac` subtracts](docs/contributing/TRAPS.md#trap-unicorn-frac) — 2×/½-off ColdFire arithmetic → suspect the instrument; `emac_selftest` pins it.
- [Unicorn's MAC-with-load decode has three defects](docs/contributing/TRAPS.md#trap-unicorn-macload) — the per-site shim stays.
- [MACSR S/U is bit 6: 16-bit rounding on the ACC read-out](docs/contributing/TRAPS.md#trap-macsr) — read the CFPRM's MOVCLR pseudocode before touching `accRead`.
- [The vendored AGU mis-stepped a pre-decrement from a modulo base](docs/contributing/TRAPS.md#trap-agu-modulo) — fixed in `agu.h`; the bit-identity gates audit it.
- [A rewritten trampoline is not retranslated](docs/contributing/TRAPS.md#trap-trampoline) — never rewrite emulated code in place (`r.emac_slots`).
- [A measurement can be structurally blind to what it rules out](docs/contributing/TRAPS.md#trap-blind-instrument) — before a null result, ask what the instrument cannot see.
- [A bus client that registers and writes zero steals everyone's level](docs/contributing/TRAPS.md#trap-bus-zero-client) — N/(N+1) dilution; gate registration on the knob.
- [r7 scratch `$00..$83` is the per-instance block; `$84+` hangs the unit](docs/contributing/TRAPS.md#trap-r7-scratch) — the slot census of the source is the truth, not the header map.
- [A dump can resolve a dispatch entry for an effect it does not contain](docs/contributing/TRAPS.md#trap-dump-alias) — `SPEC=1` aliases the absent server to SEND; check which code the entry points at before believing negatives.
- [Payload A's half of the shared window is fully owned](docs/contributing/TRAPS.md#trap-shared-window) — no delay lines below `0x38000`.
- [An FX2 id is also an FX1 id](docs/contributing/TRAPS.md#trap-fx2-id) — schema refuses stock ids; a client keys its slot on r7, never X:$213.
- [A module's id is the remix's, not the manifest's](docs/contributing/TRAPS.md#trap-module-id) — `registry.bound(remix)` for ids, `idspace` for the FX2 table and dispatch addresses; a 64-id image moves both.
- [`dsp_host`'s default audio block sits in stock scratch](docs/contributing/TRAPS.md#trap-audio-block) — `-audio 0` for a stock render.
- [An absolute stock-table address is right in A and 13 words off in B](docs/contributing/TRAPS.md#trap-stock-tables) — declare table addresses; audit both payloads.
- [A knob word under an LFO has non-zero low bits](docs/contributing/TRAPS.md#trap-lfo-word) — mask with `and #>$7f0000`; store from `a1`/`b1`.
- [A descriptor name filling its field leaves no NUL](docs/contributing/TRAPS.md#trap-name-nul) — fault PC = the field's ASCII; `schema.MenuEntry` refuses over-lengths.
- [A part saved under an older slot layout stalls the sequencer](docs/contributing/TRAPS.md#trap-part-layout) — `stamp-defaults` on the card before play.
- [The emulated load's part is not the part that plays](docs/contributing/TRAPS.md#trap-otemu-part) — write fixtures into every part of every bank.
- [The harness's dispatcher model is not the dispatcher](docs/contributing/TRAPS.md#trap-dispatcher-model) — measure dispatcher facts under the port.
- [An effect's `init` must preserve r1](docs/contributing/TRAPS.md#trap-init-r1) — `verify_init_regs` refuses; zero through r5.
- [A slot can draw a knob and publish nothing](docs/contributing/TRAPS.md#trap-knob-publish) — panel and DSP are separate; `docs/firmware/PARAM_PAGES.md`.
- [Flash cycles are expensive](docs/contributing/TRAPS.md#trap-flash) — render locally and measure first.
- [The unit misbehaves](docs/contributing/TRAPS.md#trap-failure-modes) — `docs/contributing/FAILURE_MODES.md` first; add new failures the moment they are seen.
- [Window code above `0x37f00` is wiped at boot; below `0x33da3` DARK REV can write it](docs/contributing/TRAPS.md#trap-window-zero) — resident code in `0x33da3..0x37eff`; the build refuses the rest.
- [A host write at the frame interrupt's entry is lost on every other frame](docs/contributing/TRAPS.md#trap-host-mask) — send to core B on ping-0 frames; never to core A.
- [`dsp_asm` does not assemble a backward `bra`](docs/contributing/TRAPS.md#trap-bra-back) — trampolines go before their target.
- [A persistent slot init doesn't clear holds the previous effect's state](docs/contributing/TRAPS.md#trap-dirty-state) — zero every slot the sample loop reads; `verify_dirty_state` refuses.
- [`dsp_asm` puts a label's absolute address in `brclr`'s displacement word](docs/contributing/TRAPS.md#trap-brclr) — write the displacement as a number; the roundtrip cannot see it.
- [A zero CS1 with a valid settings tail boots stock's settings as zeros](docs/contributing/TRAPS.md#trap-cs1-zero) — lay the early block over `cs1_boot(image)`.
- [`in_slot` lost its `lsll #5`: four packet buffers 3 bytes apart](docs/contributing/TRAPS.md#trap-in-slot) — a gate that passed and now fails: run the old commit under today's tools first.
- [The stock echo-freeze mix rewrites arena region 7 every frame](docs/contributing/TRAPS.md#trap-region7) — poke region 7 AND its staging zero in a tap check; expect zero on src-7.
- [A gate that models a setting must boot that setting](docs/contributing/TRAPS.md#trap-post-cs1) — `--cs1-in` the block; an empty run reports which watch was empty, never crashes.
- [The bench socket drops a large reply on EAGAIN](docs/contributing/TRAPS.md#trap-bench-socket) — poll POLLOUT in the write loop; a short line in the port log is display-only.
- [Payload B's frame routine writes `x:$3f7f..$3fbf` every frame](docs/contributing/TRAPS.md#trap-stock-x-scratch) — the guard's base cells were there; read what the stock writes before putting state in X, and read the cells back on a unit.

**ColdFire / DRAM side**

- [A nonzero popup pointer is not an open FX SETUP window](docs/contributing/TRAPS.md#trap-popup-redraw) — check the open flag and geometry; verify held-lock edits on the decoded LCD.

- [A branch can enter the middle of a displaced span](docs/contributing/TRAPS.md#trap-detour-interior) — whole instructions are insufficient: keep shared branch targets; the MIDI CHROMATIC gate exercises both paths.

- [A write-watch on cached addresses is blind to the uncached-alias clear](docs/contributing/TRAPS.md#trap-watch-alias) — `machine.h` folds the alias.
- [The boot verifier booted the wrong image](docs/contributing/TRAPS.md#trap-boot-verifier) — a verifier that reads `out/` must know who wrote it last.
- [`make … | grep | tail` reports tail's exit code](docs/contributing/TRAPS.md#trap-pipe-exit) — `> log; echo $?`.
- [Matching an author's bytes with GNU as](docs/contributing/TRAPS.md#trap-gnu-as) — `lea SYM:l` for same-unit labels; `moveq`; the `-Ttext` 2-mod-4 `nop`.
- [A bank-file fixture edits the file; the firmware parses it into a different RAM layout](docs/contributing/TRAPS.md#trap-work-file-ram) — anchor fixture edits to a known-good write; RAM addresses from the routine's arithmetic.
- [A loader draft clobbered d0 and reused a0 after the hash](docs/contributing/TRAPS.md#trap-loader-regs) — `verify_dram_boot` watches entry and `fatal`.
- [Fixed `/tmp` names corrupted parallel builds](docs/contributing/TRAPS.md#trap-tmp-race) — mkdtemp per process now; a failure moving between remixes is a shared-scratch race.
- [The memory word-count fixture can race reach and shard snapshots](docs/contributing/TRAPS.md#trap-word-fixture) — ignore its scratch path so it is not planned or copied as a real remix.
- [Replacing a stock routine can halt every other caller](docs/contributing/TRAPS.md#trap-stock-callee) — diff the routine and its callers with `tools/build/where.py`.
- [A forked port shares its DSP memory with its siblings](docs/contributing/TRAPS.md#trap-fork-shm) — `unshareRanges`; new shared maps need the same.
- [The port ran under Rosetta and nothing said so](docs/contributing/TRAPS.md#trap-rosetta) — `file out/emu/ot_emu` is the check.
- [The report is API and prints paths](docs/contributing/TRAPS.md#trap-report-api) — re-save refhash only after the artifacts are shown identical.
- [Id 0 is FX1 NONE too: a stock fallback ran on every empty FX1 slot](docs/contributing/TRAPS.md#trap-stock-fallback) — the sequencer held its first step; `registry.remix` refuses a stock fallback.
- [A frame count past $7fffff reaches `move a,n1` with A2 stale; the unit's frame interrupt stopped 50.7 min after power-up](docs/contributing/TRAPS.md#trap-frame-count) — keep the count below bit 23; preset it to test (`LM_FRAME0`).
- [An EP0 reply is DMA'd from memory the cache may not have written; a 64-multiple reply breaks the next request](docs/contributing/TRAPS.md#trap-ep0-dma) — copy through `+UNCACHED`; never answer a multiple of 64 bytes.
- [Same-named labels across units resolve by nm table order](docs/contributing/TRAPS.md#trap-nm-order) — per-unit tables; a ref naming a symbol its unit does not define is refused.
- [`moveml %sp@` is the mode-2 form and stores at sp unchanged](docs/contributing/TRAPS.md#trap-movem-sp) — the lea-framed save/restore idiom, or `%sp@-`/`%sp@+`.
- [cfgsel served one MAIN and one CUE short of the declared nch](docs/contributing/TRAPS.md#trap-cfgsel-nch) — 16 × TRACKS + 2 × (MAIN + CUE + MASTER); every consumer agrees on usb_nch.
- [At .Lf_nomaster the branch was inverted](docs/contributing/TRAPS.md#trap-producer-stride) — the slot advance walks what was WRITTEN: 24 with tracks, 88 without.
- [`--watch-mem` is one string](docs/contributing/TRAPS.md#trap-watchmem) — a second flag replaces the first; comma-join the ranges.
- [A completion IRQ in the first-sector write window polls DRQ on the stale count](docs/contributing/TRAPS.md#trap-first-sector-irq) — the guard keeps the sector and its bookkeeping inside the existing mask; `verify_ata_write` gates it.
- [The stock Part validator clamps a stored FX2 id to 31](docs/contributing/TRAPS.md#trap-id-clamp) — a poke bypasses it, a project does not; `idspace.convert` raises the two immediates to 63; `verify_ids64_load` loads a project.
- [A floating cave rounded past the clone window landed on the chooser list](docs/contributing/TRAPS.md#trap-cave-round) — `… not free` names the victim; the overflow fallback takes any floating cave ending past the limit, starting past DELAY's kept bytes.
- [A DRAM clone's `CLONE_<key>` export is its staging address](docs/contributing/TRAPS.md#trap-dram-clone-stage) — repointed only at the end; compare runtime addresses from `_psyms`.
- [The machine list's key handlers clamp the cursor to 5](docs/contributing/TRAPS.md#trap-machine-clamp) — a sixth row fits by accident, a seventh needs the ten `moveq`s; a port key held 0.25 s repeats.
- [Narrowing the port's DMA arm rule broke a gate whose image never moved](docs/contributing/TRAPS.md#trap-dma-arm) — a port change is every port gate's instrument; CI's cached passes hide it.

- [Resident relinks can republish imported staging addresses](docs/contributing/TRAPS.md#trap-resident-import-exports) — publish only owned exports; `midi-follow-events` exercises descriptor relocation with MIDI Part State.
- [A ColdFire save frame sized for the wrong register count overwrites the return address](docs/contributing/TRAPS.md#trap-cf-frame) — `lea -4N(%sp)` + `movem.l regs,(%sp)`; no pre-decrement `movem`, no `eor <mem>,Dn`, no `st <mem>`, no `move.b #imm,abs.l`.
- [An unused-looking project byte can be rewritten on save](docs/contributing/TRAPS.md#trap-unused-bytes) — mark, load, save, diff before using one.
- [`--watch-mem` given to a `--scenario` child logs nothing](docs/contributing/TRAPS.md#trap-scenario-watch) — watch with a direct run.

## How claims are written here

The project has been burned by stale confident numbers more than once — a
cycle budget of 1080 that was never a ceiling, a burn probe that measured an
engine we do not ship, a blocker our own bisect had already falsified.

So: **separate measured from inferred.** `docs/firmware/CHIP.md` marks every number with
a confidence marker and keeps retracted values beside current ones. Do the
same. Say what would falsify a claim. Do not write "found it" for something
you have inferred, and when a retraction lands, propagate it to every document
that repeated the old number — not just the one you were editing.

## Removed files stay cited

The tree was pruned hard in the octabam refactor (~350 files of ColdFire
archaeology, emulator scratch, voicing snapshots) and `docs/history/` (18
closed records) was removed 16 Sep 2026; all are still reachable in git.
Comments cite removed probes (`dsp/baseprobe.asm`, `dsp/ymemprobe.asm`) as
the provenance of a measurement, and those statements remain true. Recover
one with:

```bash
git log --all --oneline -- dsp/baseprobe.asm
git show <sha>:dsp/baseprobe.asm
```

Leave those citations alone — rewriting one to remove a filename erases
how the number was obtained. A citation of a removed file uses the form
`git show <sha>:<path>` (`docs/history/` records: sha `3ceba41`).


- [Audio and MIDI playing Parts are independent](docs/contributing/TRAPS.md#trap-part-engine-context) — use the matching STORE context reader; seed different engine Parts in fixtures.
- [A MIDI-only fixture leaves audio frame checks with no playing Part](docs/contributing/TRAPS.md#trap-midi-only-frame-fixture) — activate an audio trig within the probe and use the selected module's actual parameters.

