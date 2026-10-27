# Handover: verify_brain on `octabam`, and the CI project jobs

Written 28 Oct 2026 for a cloud agent. Facts only; "inferred" marks what was not measured. Repo: `sambanks/octabam`.
Read `AGENTS.md` first (worktree rule, gate rule: run only the one gate script locally, CI runs the rest).

## Goal (Sam, the owner)

`octabam` is the golden master remix; `octabam-bus` is Sam's personal one with fewer users. `tools/verify/verify_brain.py`
(the BRAIN module's gate) must pass on `octabam` and run in CI at a reasonable time, on a project the CI runner generates.

## State at time of writing

- `origin/main` is `b36afa2c` (#940 merged: `octabam` default remix in reach, project jobs in their own unit, cached fresh
  project, split units). #917 and #939 are closed/merged; #917's commits are on `main` via #940.
- **#941** (open, `ci/stamp-fresh-project`, head `2a8d0d59`, base `main`, CI clean): `tools/hw/ot_fresh.py` stamps the generated
  project (`MIDI_PROGRAM_CHANGE_RECEIVE=1`, `_RECEIVE_CH=0`, `MIDI_CLOCK_RECEIVE=1`, `MIDI_TRANSPORT_RECEIVE=1` in `project.work`
  and `project.strd`, widths kept: `-1` becomes `00`) and writes `OUT/REMIX/fresh.key` (the cache key) on a miss and on a hit,
  which `gate_cache.project_stamp` (de97eb68, on `main`) uses so the project gates can hit the pass cache. Tests:
  `tools/verify/tests/test_ot_fresh.py`.
- **Local only, not pushed:** branch `fix/verify-brain-octabam`, commit `28cf11e7` on top of #941 (patch at the end of this file).
- Another Claude session (`octabam-bd`) owns the CI split (`reach.py`, `ci.yml`, `check_shards.py`); coordinate before editing those.

## What was measured

| run (local unless stated) | project | gate remix | result |
|---|---|---|---|
| CI run 40345783683 (old head) | generated, unstamped | `octabam-bus` (gate default) | 9 failures; `image` shard 96 min |
| generated project, stamped, generated on `octabam-bus` | `out/fresh/octabam-bus/NOPROJ` | `octabam-bus` | **0 failures**, 18 min 8 s |
| generated project, stamped, generated on `octabam` | `out/fresh/octabam/NOPROJ` | `octabam-bus` | **8 failures**, 16 min 41 s |
| same project | stamped, `octabam` | `octabam`, `--only-cases`, with the stage-1 patch | **0 failures** (53 checks), 5 min 47 s |

- `verify_brain` is registered `Gate("tools/verify/verify_brain.py", remix_arg=False, ...)` (modules/brain/manifest.py), so CI runs
  it with no remix argument and the script's default is `octabam-bus` (`ap.add_argument("remix", nargs="?", default="octabam-bus")`).
- The generated project's bank files depend on the remix it was generated on (32 bank files differ by 626 bytes between the
  `octabam` and `octabam-bus` projects, plus `brain.*` and `kits.*`). The 8 failures on the `octabam`-generated project are DELAY's page
  (`2f 00 7f ...` against `34 05 7f ...`), four `save` checks and the panel `menu` SAVE FX DEFAULT check (inferred: the gate
  expects the bus remix's T1 FX2 defaults).
- The firmware makes a project with MIDI program change/clock/transport receive off; Sam's real project (`~/.octabam_project` =
  `OCTABAM89_setgate`) has them on. With them off, `verify_brain`'s `log` case (a program change) fails. #941 fixes that.
- Earlier "26-27 failures with the real project" figures were measured on `octabam` with the unstamped gate and are NOT a CI reproduction.

## Why the gate does not work on `octabam` yet

1. **Select path (fixed in the stage-1 patch below).** The panel script opens T2's FX2 chooser on the track's own row and presses DOWN once, so
   T2 has to start on the row above DELAY (SEND in `octabam-bus`; LO-FI in `octabam`). The patch reads the FX2 chooser's rows from the built
   image (`LIST_REF = 0x400375f4`, descriptor id word low byte) and starts T2's FX2 on the row above DELAY.
2. **Five parts use the bus remix's DELAY SERVER and fail with a `KeyError` on `octabam` (not carried), about 19 references:**
   `stock clamps` (plants out-of-count bytes in page-2 slots 0 and 3), `save` (SAVE FX DEFAULT on T1's FX2 then card.strd and the second
   boot), `menu` (SAVE/CLEAR FX DEFAULT from the panel on T1's FX2), `project` (project-record cases) and `mode` (a GRAIN record, FX2
   page-2 editor, `bd.mode_slot`, `bd.mode_views`). Stock DELAY cannot be the stand-in: the `work` card already holds a DELAY record and
   the `save` case checks it is left untouched byte for byte.
3. **In `octabam` only MODULATION and SPECTRUM have `mode_views`, and both are `fx1_only=True`** (`Claims(fx1_only=True)`; the FX2
   chooser has no row for them).

## Sam's position on the stations

SPECTRUM, CHARACTER, MODULATION (and TRANSIENT) should be on FX1 **and** FX2 in `octabam`. `remixes/octabam/README.md` already says so
(table ✓ in both columns; "The stations have their `SLOTS` build setting at `FX1+FX2`") but `remixes/octabam/remix.py` has no `SLOTS`
setting (its settings: `octabam.usb` TRACKS/MAIN/CUE/MASTER/IN and `kyoti.mute-modes` PLACE) and its comment on `fx1=` says "the stations
run on FX1 only (an FX2 instance renders dry)". `git log -S'FX1+FX2' -- remixes/octabam/remix.py` finds nothing. The form is in
`remixes/test/stations-fx2/remix.py`:

    settings={(f"octabam.{k.lower()}", "SLOTS"): Pin("FX1+FX2") for k in ("SPECTRUM", "CHARACTER", "MODULATION")}

Sam has not yet said "go" to changing the shipped remix; ask before doing it. It changes DSP (the dry flag is replaced) and adds live FX2
rows; per `AGENTS.md` it needs the `docs/site/` pages updated and the gates checked (`verify_stations_fx2`, `verify_menu` and what
`make reach` selects). The CPU catalog (`tools/remix/slot_costs.json`, `python3 tools/remix/costs.py table`) already prices MODULATION's
worst slot on FX2 (8.96), so cost is covered; `costs.py check octabam` returns UNKNOWN (no measured base for `octabam`).

## Next steps, in order

1. **Ask Sam to confirm** the `SLOTS=FX1+FX2` pins for `octabam`, then make that its own PR from `main` (remix.py, the stale comment, docs/site
   pages, gates).
2. **Push the stage-1 branch** (apply the patch below on top of #941's head `2a8d0d59`), open it stacked on #941 or after it merges.
3. **Port the five DELAY SERVER parts** to a stand-in: with the stations live on FX2, use SPECTRUM (or MODULATION) as the T1 FX2 host, which
   also keeps the `mode` case on the FX2 page-2 editor path (`FX2_EDITOR`, `bd.mode_slot - 6`). If the pins are refused, the alternatives are
   stock PLATE REV (few stepped slots), TRANSIENT, or `[SKIP]` with a reason on `octabam`.
4. **Change the script default remix to `octabam`** only when the gate passes end to end on it (`#940`'s commit 4f45cfe9 put it back to
   `octabam-bus` on purpose).
5. **CI wiring (with `octabam-bd`):** `verify_brain` is 18 min locally and 2869 s (`cxosc-core`) in CI; `octabam-bd` proposes its own unit,
   e.g. `reach.SPLIT_REMIX_JOBS = {"brain": ("image",)}` giving `check-remix octabam (brain)` with its own Fresh Project step. `ci.yml`'s step
   condition is `contains(matrix.name, ' (project)')` and strips `${remix% (project)}`; both need the new suffix. The project must be generated
   on the remix the gate builds (`octabam` once step 4 is done). Tests: `tools/verify/tests/test_reach.py`, `test_check_shards.py`.
6. After each change, measure CI time per unit; the target is that `check-remix octabam` units finish near the longest of them.

## Commands

    make emu-cf                                                   # the port, built into the worktree (not shared)
    python3 tools/hw/ot_fresh.py --remix octabam --out out/fresh   # generated + stamped project; cached under <git common dir>/octabam-fresh-cache
    python3 tools/verify/verify_brain.py octabam --project $PWD/out/fresh/octabam/NOPROJ --only-cases   # with the patch: ~6 min
    python3 tools/verify/verify_brain.py --project $PWD/out/fresh/octabam-bus/NOPROJ                    # as CI runs it today: ~18 min
    python3 -m unittest tools/verify/tests/test_ot_fresh.py tools/verify/tests/test_gate_cache.py
    python3 tools/verify/verify_docs.py

## Traps hit this session

- Always a worktree (`git worktree add .claude/worktrees/<name> -b <branch> origin/main`); link `vendor`, `.venv`, `downloads` from the main
  checkout, copy `out/raw/section_3_MAIN_OS.bin`, run `git submodule update --init`, build the port with `make emu-cf` in the worktree.
  `git worktree remove` needs `--force` once submodules are initialised (check them for changes first).
- `verify_brain`, `verify_load_meter` and `verify_remix_switch` share `out/` scratch: run one at a time. Two overlapping `selftest.py` runs
  produced three bogus `xhfixture` failures.
- A `make image` build tag is one or two characters (`H10` is refused).
- The unit and the port rewrite the project they load; run gates on copies. The gate copies the project itself.
- A gate's `[SKIP] ... no project` is what CI printed for every project gate before #940; check the log, not the exit code.
- Merge PRs pinned: `gh pr merge N --repo sambanks/octabam --merge --match-head-commit <sha>`. Pushing to a contributor's fork branch was
  denied by the permission classifier once; ask Sam rather than working around it.
- `gh pr view --json mergeable` can read UNKNOWN for a while after a merge; `git merge-tree --write-tree origin/main <ref>` answers it.

## Stage-1 patch (tools/verify/verify_brain.py, `28cf11e7`)

```diff
diff --git a/tools/verify/verify_brain.py b/tools/verify/verify_brain.py
index 721422ad..951053e6 100644
--- a/tools/verify/verify_brain.py
+++ b/tools/verify/verify_brain.py
@@ -57,6 +57,7 @@ OUT = ROOT / "out/coreverify"
 BASE = 0x40000400
 LANES, IDS = 0x80000810, 0x80000ec4
 FX2_TABLE, FX1_TABLE = 0x400d5fdc, 0x400d5f58
+LIST_REF = 0x400375f4        # the operand of FUN_40052474 that holds the FX2 chooser list's address
 K = dict(no=0x32, fx1=0x25, fx2=0x26, down=0x20, yes=0x31, t2=0x11)
 PAGE = {"fx1": (0x12, 0x32, 0), "fx2": (0x18, 0x38, 8)}
 COUNTERS = ("loads", "state", "records", "applied", "values", "skip_id", "skip_layout",
@@ -92,6 +93,8 @@ def main():
     ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
     ap.add_argument("--set-name", default="BRAINSET")       # not BRAIN: that is the store's directory
     ap.add_argument("--name", default="BRAINPRJ")
+    ap.add_argument("--only-cases", action="store_true",
+                    help="run the eight card cases (none .. settings_bad) and stop: minutes, not the whole gate")
     a = ap.parse_args()
     project = a.project
     if not project and pathlib.Path("~/.octabam_project").expanduser().is_file():
@@ -128,6 +131,17 @@ def main():
         P = struct.unpack(">I", rd(table + 4 * fx, 4))[0]
         return P, rd(P + 0x5e, 12), struct.unpack(">12I", rd(P + 0x9a, 48))
 
+    def fx2_chooser_ids():
+        """The id on each row of the FX2 chooser, top to bottom, read from the built image: the list the
+        chooser walks holds each row's descriptor, whose first word's low byte is the id it stores."""
+        lst = struct.unpack(">I", rd(LIST_REF, 4))[0]
+        ids = []
+        while True:
+            ptr = struct.unpack(">I", rd(lst + 4 * len(ids), 4))[0]
+            if not ptr:
+                return ids
+            ids.append(struct.unpack(">I", rd(ptr, 4))[0] & 0xff)
+
     pdir = pathlib.Path(project).expanduser()
     copy = OUT / "project"
     shutil.rmtree(copy, ignore_errors=True)
@@ -142,6 +156,12 @@ def main():
     spm = mods["SPECTRUM"]
     ot_project.set_fx(copy, "fx1", 2, "SPECTRUM", page=[p.default or 0 for p in spm.params[:6]],
                       page2=[p.default or 0 for p in spm.params[6:12]], guard=False)
+    # The panel script opens T2's FX2 chooser on the track's own row and presses DOWN once, so the track has to start
+    # on the row above DELAY: SEND in the bus remix, whatever sits above it in the others (LO-FI in octabam).
+    rows = fx2_chooser_ids()
+    if 0x08 not in rows[1:]:
+        sys.exit(f"verify_brain: DELAY (0x08) is not below the first row of {a.remix}'s FX2 chooser {rows}")
+    ot_project.set_fx(copy, "fx2", 2, rows[rows.index(0x08) - 1], guard=False)
     delay, character = mods["DELAY"], mods["CHARACTER"]
     want = {"DELAY": {"TIME": 52, "FB": 5, "X": 1, "TAPE": 0}, "CHARACTER": {"DRV": 9, "MIX": 77}}
     work = ot_brain.set_default(None, delay, want["DELAY"])
@@ -287,6 +307,9 @@ def main():
         if name == "none":
             check(f"settings: no card store, the defaults of layers 1 and 2 (values {svals}: APPLY DFLTS, MIDI LOG)",
                   svals == (1, 0))
+    if a.only_cases:
+        print(f"verify_brain: {'ok' if not fails else 'FAILED'} ({fails} failure(s)) -- the eight card cases only")
+        return 1 if fails else 0
     # ---- stock clamps: why the brain has no clamp of its own ----------------
     # The Part validator 0x40002318 rewrites every FX page byte outside its
     # descriptor's [min, min + count - 1] to the nearer end during the load
```
