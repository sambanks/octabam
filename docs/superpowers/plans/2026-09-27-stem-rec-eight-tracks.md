# STEM REC: eight tracks under the emulator, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** STEM REC records all eight tracks by default and keeps its peak ring fill, proven sample-exact under the emulator on a fixture with sound in every frame, at every track count, with a card-speed sweep of where the ring runs out.

**Architecture:** `stems.s` gains `stems_peak` and a default mask of `0xFF`. A new fixture puts eight THRU machines on distinct mixes of inputs A to D, fed a four-channel noise WAV through `ot_emu --audio-in`, with the THRU inputs and amp set over MIDI CC after the transport start. `verify_stems.py` gains one generic mask-take check, run for several masks, with an exact peak check rebuilt from the port's watch log. A separate `stems_sweep.py` runs track counts against `--ata-latency` values.

**Tech Stack:** m68k assembly (`stems.s`, GNU as), Python 3 (fixture, verifier, sweep), the ColdFire port `ot_emu` (C++, unchanged here), WSL2 Ubuntu.

**Spec:** `docs/superpowers/specs/2026-09-27-stem-rec-eight-tracks-design.md`

## Global Constraints

- "`stems.s` changes only as section 3 says. Every existing check still passes."
- "Every value that moves is a finding: re-measured, explained and written down, never loosened to pass."
- "Every gate runs on a committed tree, and its log's first line shows it."
- "No Elektron byte in the repository. The WAV and every card image stay in `out/`."
- "Nothing is pushed." Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- "If the input routing can't be made to work, the fallback is the port's built-in tones, and that change is raised with Yves before it is made."
- Masks: `make check` runs 1, 2, 4 and 8 tracks (the first n) and `0xA5`; `--long` adds 3, 5, 6 and 7, the eight-track wrap and the eight-track overflow.
- Sweep: 1, 2, 4 and 8 tracks at `--ata-latency` 8, 16, 24, 32, 48 and 64; each a 5-second take.
- Prose follows the Microsoft Writing Style Guide. Counts from logs go through a script file, never an inline `$(grep -c)` through `wsl.exe` (27 Sep 2026: two such counts were wrong).

## Review Focus

These five inputs follow from the spec, and no check in it covers them. Each line names the task that adds its test.

1. **T8 alone (`0x80`).** Expected: one file, `T8.wav`, equal to track 8's read-back; the highest ring slot and the last file name work alone. Test: Task 6 adds `0x80` to the `--long` masks.
2. **The mask poked while a take records.** Expected: the take keeps the mask it latched at its start; the new mask applies from the next arm. Test: Task 6, `latch`.
3. **The peak across a re-arm.** Expected: arming resets `stems_peak` to 0, so a new take never shows the old take's peak. Test: Task 4 adds it to the existing `overflow` check, which re-arms at its end.
4. **The peak at overflow.** Expected: the largest value the hook writes to `stems_peak` equals the ring's capacity in frames (`stems_rframes`) when the guard trips. Test: Task 6, `overflow8`, reading `stems_peak`'s writes from the watch log.
5. **A card slow enough to fill the ring without overflowing it.** Expected: the peak reads close to capacity and the take still ends IDLE with no error. Test: Task 7's sweep reports every run's peak share; its table shows which runs came close.

---

## Conventions

- **Branch and trees.** Git work in the Windows checkout on branch `stem-rec-p2`; builds and runs in the WSL clone `/home/yvez/stemrec2`, synced with `bash .superpowers/v2/sync.sh`. Runs use `bash .superpowers/v2/wslrun NAME CMD...` and log to `/home/yvez/xcheck/v2-NAME.log`; tell Yves each long run's log path when it starts. **From Task 3u on** (28 Sep 2026): git work in the worktree `.claude/worktrees/stem-rec-p2-up` on branch `stem-rec-p2-up` (piece 2 with upstream `2a849af` merged in), synced with `bash .superpowers/v2/sync-up.sh`; every `sync.sh` below means `sync-up.sh`, and every `git` command runs in the worktree.
- **The fixtures.** From Task 3u on, `verify_stems.py` builds its four fixture cards itself at the start of every run, from `STEMS_TEMPLATE` (default `out/projects/Ultimate FX 1.5.3`). A helper script that bypasses `main()` calls `v.fixtures()` after it builds the image.
- **Commits.** Stage by name; check `git status --porcelain` shows only the intended files staged before each commit. After a `git checkout <rev> -- <path>`, unstage with `git reset -q`.
- **The port runs.** Every `port()` call in `verify_stems.py` builds on the image the verifier built at its start (`REMIX=stems`). A helper script that bypasses `main()` builds the image itself first.

---

### Task 1: Setup, and the input routing measured

**Files:**
- Modify (local): `.superpowers/v2/sync.sh` (accept branch `stem-rec-p2`)
- Modify: `tools/verify/stems_fixture.py` (the WAV writer, the MIDI file writer, `build_thru`)
- Create (local): `.superpowers/v2/thru-map.py`

**Interfaces:**
- Produces: `stems_fixture.write_input_wav(path, live=(0, 1, 2, 3), seconds=30, seed=0x57E4)`; `stems_fixture.write_thru_midi(path, inputs)`; `stems_fixture.THRU_INPUTS: dict[int, tuple[int, int]]` (track → (INAB value, INCD value)); `stems_fixture.build_thru(project_dir)` writing `out/stems_fixture_thru.json` with keys `card`, `set`, `project`, `staged`, `audio_in`, `midi`.

- [ ] **Step 1: Let the sync follow the new branch, and save the remix-hash baseline**

In `.superpowers/v2/sync.sh`, change `case "$BR" in main|stem-rec-v2) ;;` to `case "$BR" in main|stem-rec-v2|stem-rec-p2) ;;` and its message to name all three. Then:
```bash
bash .superpowers/v2/sync.sh
bash .superpowers/v2/wslrun p2-remixhash-save bash /mnt/c/Projects/Octabam/.superpowers/v2/remixhash.sh save
```
Expected: `wsl: HEAD` = the plan's commit, `0 file(s) differ`; the baseline lists every remix, `stems` built from `ed486b3`'s `stems.s` (Task 9 compares against it).

- [ ] **Step 1b: Give `port()` the fixture's input**

In `tools/verify/verify_stems.py`'s `port()`, after the `args = [...]` list:
```python
    if fx.get("audio_in"):
        args += ["--audio-in", fx["audio_in"]]
    if fx.get("midi"):
        args += ["--midi", fx["midi"]]
```
and add to its docstring: "A fixture with `audio_in`/`midi` feeds the port's inputs and MIDI IN." The existing fixtures have neither key, so their runs don't change.

- [ ] **Step 2: Write the fixture's WAV and MIDI writers**

In `tools/verify/stems_fixture.py`, after the `FILLER_BYTES` constant:
```python
THRU_JSON = ROOT / "out" / "stems_fixture_thru.json"
THRU_CARD = ROOT / "out" / "stems_fixture_thru_card.img"
SCRATCH_THRU = ROOT / "out" / "task_thru" / "fixture_src"
INPUT_WAV = ROOT / "out" / "test_audio" / "stems_in4.wav"
THRU_MIDI = ROOT / "out" / "stems_thru.midi"
THRU_MTYPE = 2          # ot_project.MACHINES
# Each track's THRU inputs: (INAB, INCD), the playback page's first and
# fourth knobs (docs/firmware/PARAM_PAGES.md: INAB VOL --- INCD VOL ---),
# sent as CC 16 and CC 19 on the track's MIDI channel (the template's
# MIDI_TRIG_CH1..8 = channels 1..8). Values: 0 off, 1 A+B / C+D, 2 A / C,
# 3 B / D -- the order Task 1 measured (STEM_REC.md 15.1).
THRU_INPUTS = {1: (2, 0), 2: (3, 0), 3: (0, 2), 4: (0, 3),
               5: (1, 0), 6: (0, 1), 7: (2, 2), 8: (3, 3)}
# The transport start re-applies the part, which reverts CC edits
# (tools/hw/hw_flash7.py), so the CCs land this many frames after it.
CC_FRAME = 2


def write_input_wav(path, live=(0, 1, 2, 3), seconds=30, seed=0x57E4):
    """Four channels of independent seeded noise at -12 dBFS peak, 44.1 kHz,
    16-bit: inputs A to D through `ot_emu --audio-in`. A channel not in
    `live` is silent (Task 1's routing probe). Noise never repeats, so a take
    can match its track only at the true offset."""
    import array
    import random
    import wave
    rng = [random.Random(seed + c) for c in range(4)]
    amp = 8192
    n = 44100 * seconds
    data = array.array("h", (rng[c].randint(-amp, amp) if c in live else 0
                             for _ in range(n) for c in range(4)))
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(4)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(data.tobytes())


def write_thru_midi(path, inputs=None):
    """`ot_emu --midi` lines, all at CC_FRAME after the transport start: per
    track its THRU inputs and their levels (CC 16/17, 19/20) and an amp that
    stays open (CC 22 ATK 0, CC 23 HOLD inf, CC 24 REL max, CC 25 VOL 100 --
    the recipe measured on the unit, tools/hw/hw_flash7.py)."""
    lines = []
    for t, (inab, incd) in (inputs or THRU_INPUTS).items():
        st = 0xB0 + t - 1
        for cc, v in ((16, inab), (17, 127), (19, incd), (20, 127),
                      (22, 0), (23, 127), (24, 127), (25, 100)):
            lines.append(f"{CC_FRAME} {st:02X} {cc:02X} {v:02X}")
    pathlib.Path(path).write_text("\n".join(lines) + "\n")
```

- [ ] **Step 3: Write `build_thru`**

After `build8`:
```python
def build_thru(project_dir=DEFAULT_PROJECT):
    """Every track a THRU machine (every part of banks 1 and 2), a trig on
    step 1 of every pattern, FX1 and FX2 SEND; the card, the input WAV and
    the MIDI file that routes each track's inputs (THRU_INPUTS)."""
    import shutil
    if SCRATCH_THRU.exists():
        shutil.rmtree(SCRATCH_THRU)
    SCRATCH_THRU.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(project_dir, SCRATCH_THRU)
    for bank in FIXTURE_BANKS:
        for part in (1, 2, 3, 4):
            for t in range(1, 9):
                ot_project.set_machine_type(SCRATCH_THRU, bank, part, t, THRU_MTYPE, mirror=True, guard=False)
        for pat in range(16):
            for t in range(8):
                ot_project.set_pattern_trig(SCRATCH_THRU, bank, pat, t, 1, guard=False)
    for t in range(1, 9):
        ot_project.set_fx(SCRATCH_THRU, "fx1", t, "SEND", guard=False)
        ot_project.set_fx(SCRATCH_THRU, "fx2", t, "SEND", guard=False)
    card_bytes, name = emu_card.stage_project(SCRATCH_THRU, SET_NAME, PROJECT_NAME,
                                              tree=str(STAGE_TREE))
    THRU_CARD.write_bytes(card_bytes)
    write_input_wav(INPUT_WAV)
    write_thru_midi(THRU_MIDI)
    result = {"card": str(THRU_CARD), "set": SET_NAME, "project": name, "staged": [],
              "audio_in": str(INPUT_WAV), "midi": str(THRU_MIDI)}
    THRU_JSON.write_text(json.dumps(result, indent=2) + "\n")
    print(f"card:    {result['card']}")
    print(f"-> {THRU_JSON}")
    return result
```
In `__main__`, add before `else`:
```python
    elif len(sys.argv) > 1 and sys.argv[1] == "--thru":
        build_thru(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROJECT)
```
and add `--thru` to the usage line in the docstring.

- [ ] **Step 4: Measure the routing**

`.superpowers/v2/thru-map.py` builds the THRU fixture, then runs the port four times, each with a WAV whose only live channel is 0, 1, 2 or 3, and prints which tracks' read-back L and R sound:
```python
#!/usr/bin/env python3
"""Which WAV channel reaches which THRU track, L and R: four port runs, one
live input channel each. Run from the clone's root."""
import json
import os
import pathlib
import subprocess
import sys
sys.path.insert(0, "tools"); import toolpath  # noqa: E402,F401
sys.path.insert(0, "tools/verify")
import stems_fixture as fxm  # noqa: E402
import verify_stems as v  # noqa: E402

env = {**os.environ, "REMIX": "stems", "XBUS": "1", "SPEC": "1"}
subprocess.run([sys.executable, "tools/build/build_bus.py"], env=env, check=True, capture_output=True)
fxm.build_thru()
fx = json.loads(fxm.THRU_JSON.read_text())
s = v.syms()
for ch in range(4):
    wav = pathlib.Path(f"out/test_audio/stems_in4_ch{ch}.wav")
    fxm.write_input_wav(wav, live=(ch,), seconds=5)
    tmp = pathlib.Path(f"out/stems_thru_ch{ch}.json")
    tmp.write_text(json.dumps({**fx, "audio_in": str(wav)}))
    _, dump, _, _, _ = v.port(s, 300, tag=f"thru-ch{ch}", fixture=str(tmp),
                              calls_before=(s["stems_action"], s["stems_action"]))
    row = []
    for k in range(8):
        fr = v.slot_frames(dump, k)
        l = max((abs(x) for f in fr for x in f[0::2]), default=0)
        r = max((abs(x) for f in fr for x in f[1::2]), default=0)
        row.append(f"T{k + 1} {'L' if l else '-'}{'R' if r else '-'}")
    print(f"WAV channel {ch}: " + "  ".join(row))
```
Run:
```bash
bash .superpowers/v2/sync.sh
bash .superpowers/v2/wslrun thru-map .venv/bin/python3 /mnt/c/Projects/Octabam/.superpowers/v2/thru-map.py
```
Read the four lines. With the candidate table, expected: channel 0 (A) reaches T1, T5, T7; channel 1 (B) reaches T2, T5, T8; channel 2 (C) reaches T3, T6, T7; channel 3 (D) reaches T4, T6, T8.
- **If a mapping differs** (for example INAB 2 is B, not A, or the WAV's channel 0 is input C), correct `THRU_INPUTS` and its comment so each track gets its spec'd mix, and run again.
- **If no track sounds in any run,** stop and report to Yves: the fallback (tones) needs his approval (spec section 4).

Record the four lines, the value order found and the channel-to-input order in `.superpowers/v2/runlog.md` for STEM_REC.md 15.1.

- [ ] **Step 5: Commit**

```bash
git add tools/verify/stems_fixture.py tools/verify/verify_stems.py
git commit -m "stems_fixture --thru: eight THRU tracks on distinct mixes of inputs A-D, a four-channel noise WAV, the inputs and amp set over MIDI CC after the transport start -- routing measured

<the four measured lines, and any correction to THRU_INPUTS>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The THRU fixture's proof

**Files:**
- Modify: `tools/verify/verify_stems.py` (`FIXTURE_THRU`, `thru()`, called from `main()`)

**Interfaces:**
- Consumes: `THRU_JSON` (Task 1), `port()` with `audio_in`/`midi` (Task 1, Step 1b).
- Produces: `thru(s)`; checks named `thru: T<n> sounds in every frame ...` and `thru: the eight signals are distinct`.

- [ ] **Step 1: Write the proof**

After `FIXTURE32 = ...`:
```python
FIXTURE_THRU = pathlib.Path("out/stems_fixture_thru.json")   # stems_fixture.py --thru
```
Before `def main():`:
```python
def thru(s):
    """The THRU fixture's proof: every track's read-back sounds in every
    frame from its first sounding frame, and the eight signals differ. The
    recorder stays IDLE (armed, then cancelled): this is the fixture, not
    STEM REC."""
    if not FIXTURE_THRU.exists():
        check("thru: the THRU fixture exists (stems_fixture.py --thru)", False)
        return
    _, dump, _, _, _ = port(s, 400, tag="thru", fixture=FIXTURE_THRU,
                            calls_before=(s["stems_action"], s["stems_action"]))
    tracks = [slot_frames(dump, k) for k in range(8)]
    firsts = []
    for k, frames in enumerate(tracks):
        first = next((i for i, f in enumerate(frames) if any(f)), None)
        firsts.append(first)
        silent = [i for i in range(first + 1, len(frames)) if not any(frames[i])] if first is not None else []
        check(f"thru: T{k + 1} sounds in every frame from its first",
              first is not None and not silent and len(frames) - first > 200,
              f"from frame {first}, {len(silent)} silent frame(s) after it")
    if None in firsts:
        return
    start = max(firsts)
    sigs = {tuple(map(tuple, fr[start:])) for fr in tracks}
    check("thru: the eight signals are distinct", len(sigs) == 8, f"{len(sigs)} distinct of 8")
```
In `main()`, after `probe(s)`:
```python
        thru(s)
```

- [ ] **Step 2: Watch it fail without the fixture, then pass with it**

```bash
bash .superpowers/v2/sync.sh
bash .superpowers/v2/wslrun thru-red bash -c 'rm -f out/stems_fixture_thru.json && .venv/bin/python3 tools/verify/verify_stems.py stems'
```
Expected: `[FAIL] thru: the THRU fixture exists`. Then build it and run the proof alone:
```bash
bash .superpowers/v2/wslrun fixture-thru .venv/bin/python3 tools/verify/stems_fixture.py --thru
```
and a script `.superpowers/v2/thru-only.py` that builds the stems image, calls `v.thru(v.syms())` and exits 1 on `v.fails`:
```python
#!/usr/bin/env python3
import os, subprocess, sys
sys.path.insert(0, "tools"); import toolpath  # noqa: E402,F401
sys.path.insert(0, "tools/verify")
import verify_stems as v  # noqa: E402
env = {**os.environ, "REMIX": "stems", "XBUS": "1", "SPEC": "1"}
subprocess.run([sys.executable, "tools/build/build_bus.py"], env=env, check=True, capture_output=True)
v.thru(v.syms())
sys.exit(1 if v.fails else 0)
```
```bash
bash .superpowers/v2/wslrun thru-green .venv/bin/python3 /mnt/c/Projects/Octabam/.superpowers/v2/thru-only.py
```
Expected: nine `[PASS]` lines: eight `sounds in every frame` and `8 distinct of 8`. A pair that is equal: raise one track's level (its CC 17 or CC 20 value in `write_thru_midi`, per track) and run again.

- [ ] **Step 3: Commit**

```bash
git add tools/verify/verify_stems.py
git commit -m "verify_stems: the THRU fixture's proof -- eight tracks sound in every frame, eight distinct signals

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Today's checks pinned to T1

**Files:**
- Modify: `tools/verify/verify_stems.py` (`port()` gains `mask`; `eight()` uses `mask`)
- Modify (local): `.superpowers/v2/hookcost.py`

**Interfaces:**
- Produces: `port(..., mask=0x01)`: a `--poke-before-play` of `stems_tracks`'s low byte, before any other `pokes_before`; `mask=None` pokes nothing.

- [ ] **Step 1: Give `port()` a mask**

In `port()`'s signature add `mask=0x01` after `pokes_before=()`. After `fx = json.loads(...)`:
```python
    pokes_before = ([(s["stems_tracks"] + 3, mask)] if mask is not None else []) + list(pokes_before)
```
Document it in `port()`'s docstring: "`mask` is the track mask poked before play (default T1: every check written for one track keeps its meaning with the build's all-eight default)."

In `eight()`, replace `pokes_before=[(s["stems_tracks"] + 3, 0xff)]` with `mask=0xFF`.

In `.superpowers/v2/hookcost.py`, the 1-track run gets `["--poke-before-play", f"0x{s['stems_tracks'] + 3:x}=0x01"]` as its extra.

- [ ] **Step 2: Every check still passes, pinned**

```bash
bash .superpowers/v2/sync.sh
bash .superpowers/v2/wslrun p2-pinned .venv/bin/python3 tools/verify/verify_stems.py stems
```
Run in the background; tell Yves the log. Expected: the 94 checks of `ed486b3` pass, plus Task 2's nine; the default is still `0x01`, so the pin changes nothing yet. Compare the check lines with `/home/yvez/xcheck/v2-mg2-check-remix-stems.log` through a script file: every shared line equal.

- [ ] **Step 3: Commit**

```bash
git add tools/verify/verify_stems.py
git commit -m "verify_stems: every one-track check pins stems_tracks to T1 before play -- ready for the all-eight default

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3u: Upstream's gate runner (added 28 Sep 2026)

Yves: "bamshanks did some more work upstream on the testing procedures. Can you pull changes on the Octabam repo and implement the new testing?" Upstream `2a849af` (53 commits) runs gates differently: `make accept REMIXES=...` runs the shared half of `make check` once; `make reach` places a change by what depends on it, with the cover as its floor; `make check-remix-gates REMIX=<name>` runs one remix's gates side by side in kept worktrees (`out/shards/<i>`, each with `out/` wiped except `emu/` and `raw/`); `make identity` builds every remix from the base and from this tree and compares the bytes.

**Files:**
- Modify: `tools/verify/verify_stems.py` (`TEMPLATE`, `fixtures()`, `main()`'s port-run guard)
- Modify: `modules/stems/manifest.py` (the gate comment), `modules/stems/README.md` (where the fixtures come from)
- Create (local): `.superpowers/v2/sync-up.sh`, `.superpowers/v2/wsl-sync-up.sh`

- [ ] **Step 1: Merge upstream into piece 2, in a worktree**

`git worktree add .claude/worktrees/stem-rec-p2-up -b stem-rec-p2-up <Task 3's commit>`, then `git merge --no-ff origin/main` there. Sync with `sync-up.sh`, then `make emu-cf` (upstream changed the port) and `make test-acceptance`. Expected: a clean merge; the runner's tests pass.

- [ ] **Step 2: See the gap**

`make reach BASE=2a849af` in WSL. Expected: `tools/verify/stems_fixture.py [no gate depends on it]`: `verify_stems` reads fixtures built by hand. Then `make check-remix-gates REMIX=stems JOBS=2`: in a shard, `out/` holds no fixture, so `gate:verify_stems` reports a SKIP of every port run.

- [ ] **Step 3: The verifier builds its fixtures**

`fixtures()` runs `stems_fixture.py` in its four modes from `TEMPLATE` at the start of every run, and one check line records the build. Without a template, the port runs SKIP by name. The four cards rebuild byte for byte in about 30 s (measured first: `.superpowers/v2/fixture-repro.sh`).

- [ ] **Step 4: The runner, green**

```bash
bash .superpowers/v2/sync-up.sh
bash .superpowers/v2/wslrun up-gates-green env STEMS_TEMPLATE="/home/yvez/stemrec2/out/projects/Ultimate FX 1.5.3" make check-remix-gates REMIX=stems JOBS=2
bash .superpowers/v2/wslrun up-reach2 make reach BASE=2a849af
```
Expected: every gate `ok`, and `gate:verify_stems` with no SKIP and the check lines of Task 3's run, plus the fixture line; `reach` places `stems_fixture.py` under `verify_stems`. Then `make identity BASE=2a849af` (`up-identity`): every remix that builds here is identical except `stems`, which the base lacks; and `make accept REMIX=stems STRESS_SOURCE=<the template>` (`up-accept`): the first acceptance report of the stems remix, with `verify_set` on a real project.

- [ ] **Step 5: Commit**

```bash
git add tools/verify/verify_stems.py modules/stems/manifest.py modules/stems/README.md docs/superpowers/plans/2026-09-27-stem-rec-eight-tracks.md
git commit -m "verify_stems: the fixtures built from the template at the start of every run -- a shard of check-remix-gates has none, and reach now sees stems_fixture.py

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: All eight by default, and the peak ring fill

**Files:**
- Modify: `modules/stems/stems.s` (the default mask; `stems_peak`; its reset at the arm; its update in the hook)
- Modify: `tools/verify/verify_stems.py` (`runtime_long`, two static checks; the peak in `stream` and `overflow`; `rebuilt_peak`)

**Interfaces:**
- Produces: the global `stems_peak` (a long right after `stems_frames`, so `watched(s, span=28)` covers it); `verify_stems.rebuilt_peak(ws) -> int`; `verify_stems.runtime_long(s, name) -> int`.

- [ ] **Step 1: Write the failing checks**

In `verify_stems.py`, after `regions()`:
```python
def runtime_long(s, name):
    """A long of the linked runtime as built (out/platform/runtime.raw), by symbol."""
    from remix import platform_build
    lay = json.loads((LAYOUT_DIR / platform_build.LAYOUT).read_text())
    raw = (LAYOUT_DIR / "runtime.raw").read_bytes()
    off = s[name] - lay["base"]
    return int.from_bytes(raw[off:off + 4], "big")


def rebuilt_peak(ws):
    """The largest ring fill the hook saw, from the watch log: each write
    of stems_wr (word 3) less the last write of stems_rd (word 4). The hook
    runs at IPL 5, so stems_rd can't change inside it."""
    rd, peak = 0, 0
    for _, w, val in ws:
        if w == 4:
            rd = val
        elif w == 3 and val:
            peak = max(peak, val - rd)
    return peak
```
In `main()`, after the card-out parse check:
```python
    check("the build records all eight tracks by default", runtime_long(s, "stems_tracks") == 0xFF,
          f"0x{runtime_long(s, 'stems_tracks'):02x}")
    check("stems_peak is in the runtime, 0 at boot", "stems_peak" in s and runtime_long(s, "stems_peak") == 0)
```
In `stream()`, add `mems=((s["stems_peak"], 4, "peak"),)` to its `port()` call, and after its existing checks:
```python
    raw = run_path("stream", "peak")
    peak = int.from_bytes(raw.read_bytes(), "big") if raw.exists() else None
    check("stream: stems_peak is the largest fill the hook saw", peak == rebuilt_peak(ws),
          f"stems_peak {peak}, rebuilt {rebuilt_peak(ws)}")
```
In `overflow()`, add `mems=((s["stems_peak"], 4, "peak"),)` to its `port()` call, and after its checks:
```python
    raw = run_path("overflow", "peak")
    peak = int.from_bytes(raw.read_bytes(), "big") if raw.exists() else None
    check("overflow: the re-arm reset stems_peak to 0", peak == 0, f"stems_peak {peak}")
```
(`stems_peak` isn't a key of `s` yet: `stream()` and `overflow()` would raise, so guard both with `if "stems_peak" in s:` and let the static check carry the failure.)

- [ ] **Step 2: Watch them fail**

```bash
bash .superpowers/v2/sync.sh
bash .superpowers/v2/wslrun p2-peak-red .venv/bin/python3 tools/verify/verify_stems.py stems
```
Expected: `[FAIL] the build records all eight tracks by default  0x01` and `[FAIL] stems_peak is in the runtime`.

- [ ] **Step 3: Change `stems.s`**

In the state block, after `stems_frames:    .long   0          | frames recorded (= stems_wr)`:
```
stems_peak:      .long   0          | the take's largest ring fill, frames; reset at the arm
```
and add `stems_peak` to that block's `.global` line. Change the default:
```
stems_tracks:    .long   0xFF       | the track mask, bit k = track k+1; latched at the start
```
In `stems_action`'s IDLE branch, after `clr.l   stems_frames`:
```
        clr.l   stems_peak
```
In the hook, at `.Lh_room:` (where `d0` still holds `stems_wr - stems_rd`), before `move.l  PING,%d4`:
```
        addq.l  #1,%d0              | frames in the ring with this one
        cmp.l   stems_peak,%d0
        bls.s   .Lh_nopeak
        move.l  %d0,stems_peak      | the take's largest fill (the menu's status row)
.Lh_nopeak:
```
Update the file's header comment where it says the build enables T1: it records all eight tracks by default.

- [ ] **Step 4: Watch them pass, and every other check too**

```bash
bash .superpowers/v2/sync.sh
bash .superpowers/v2/wslrun p2-peak-green .venv/bin/python3 tools/verify/verify_stems.py stems
```
Run in the background. Expected: the two static checks, `stream: stems_peak ...` and `overflow: the re-arm reset ...` pass; every check of Task 3's run passes with the same values. A moved value is a finding (Global Constraints).

- [ ] **Step 5: Commit**

```bash
git add modules/stems/stems.s tools/verify/verify_stems.py
git commit -m "stems: all eight tracks by default, and stems_peak -- the take's largest ring fill, reset at the arm, exact against the watch log

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The mask takes in `make check`

**Files:**
- Modify: `tools/verify/verify_stems.py` (`THRU_STOP`, `THRU_FRAMES`, `mask_take()`, the `make check` masks in `main()`)
- Create (local): `.superpowers/v2/mask-negative.py`

**Interfaces:**
- Consumes: `port(..., mask=)`, `slot_frames`, `take_files(card, fixture)`, `writes`, `watched`, `rebuilt_peak`, `run_path`.
- Produces: `mask_take(s, mask, tag, stop_at=THRU_STOP, frames=THRU_FRAMES, pokes=())`.

- [ ] **Step 1: Write `mask_take`**

Before `def main():`:
```python
# A mask take: at least three chunks (512 frames each) while recording,
# then the time the writer needs at the port's card speed (8 samples a
# sector: STEM_REC.md 13.3). Measured for eight tracks in Task 5, Step 3.
THRU_STOP = 1700
THRU_FRAMES = 3000


def mask_take(s, mask, tag, stop_at=THRU_STOP, frames=THRU_FRAMES, pokes=()):
    """One take on the THRU fixture with `mask`: a file per enabled track,
    each equal to its own track's read-back at one fixed offset, sound in
    every frame from its first, no two alike, the writer writing during the
    take, IDLE with no error, and stems_peak exact against the watch log."""
    if not FIXTURE_THRU.exists():
        check(f"{tag}: the THRU fixture exists (stems_fixture.py --thru)", False)
        return
    log, dump, card, words, _ = port(s, frames, stop_at=stop_at, tag=tag, fixture=FIXTURE_THRU,
                                     mask=mask, pokes=pokes, extra=watched(s, span=28),
                                     mems=((s["stems_peak"], 4, "peak"),))
    st, status, _, wr, rd, nfr = words
    want = [k for k in range(8) if mask >> k & 1]
    check(f"{tag}: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    files = take_files(card, FIXTURE_THRU)
    check(f"{tag}: one file per enabled track", [n.upper() for n, _ in files] == [f"T{k + 1}.WAV" for k in want],
          f"{[n for n, _ in files]}")
    datas = []
    for k, (name, data) in zip(want, files):
        got = [list(struct.unpack_from("<32h", data, 44 + 64 * f)) for f in range((len(data) - 44) // 64)]
        ref = slot_frames(dump, k)
        lag = next((L for L in range(len(ref) - len(got) + 1) if ref[L:L + len(got)] == got), None)
        first = next((i for i, f in enumerate(got) if any(f)), None)
        silent = [i for i in range(first + 1, len(got)) if not any(got[i])] if first is not None else []
        check(f"{tag}: {name} equals track {k + 1}'s read-back at one offset, sound in every frame from its first",
              nfr > 0 and len(got) == nfr and lag is not None and first is not None and not silent,
              f"{len(got)} frames, lag {lag}, first sound {first}, {len(silent)} silent after")
        datas.append(data[44:])
    check(f"{tag}: no two files alike", len(set(datas)) == len(datas), f"{len(set(datas))} distinct of {len(datas)}")
    ws = writes(s, log, span=28)
    fin = next((x for x, w, val in ws if w == 0 and val == ST_FINISHING), None)
    mid = [x for x, w, val in ws if w == 4 and fin is not None and x < fin]
    check(f"{tag}: the task wrote during the take", len(mid) >= 2, f"{len(mid)} rd writes before FINISHING")
    raw = run_path(tag, "peak")
    peak = int.from_bytes(raw.read_bytes(), "big") if raw.exists() else None
    check(f"{tag}: stems_peak is the largest fill the hook saw", peak == rebuilt_peak(ws) and peak > 0,
          f"stems_peak {peak}, rebuilt {rebuilt_peak(ws)}")
```
In `main()`, after `eight(s)`:
```python
        for mask in (0x01, 0x03, 0x0F, 0xFF, 0xA5):
            mask_take(s, mask, f"mask{mask:02x}")
```

- [ ] **Step 2: Prove the check can fail**

`mask_take` checks behavior STEM REC already has, so it can pass on its first run. `.superpowers/v2/mask-negative.py` shows it can fail: it takes mask `0x02` but compares with track 1's read-back, and expects the equality line to FAIL:
```python
#!/usr/bin/env python3
import os, subprocess, sys
sys.path.insert(0, "tools"); import toolpath  # noqa: E402,F401
sys.path.insert(0, "tools/verify")
import verify_stems as v  # noqa: E402
env = {**os.environ, "REMIX": "stems", "XBUS": "1", "SPEC": "1"}
subprocess.run([sys.executable, "tools/build/build_bus.py"], env=env, check=True, capture_output=True)
s = v.syms()
real = v.slot_frames
v.slot_frames = lambda dump, k: real(dump, 0)      # every file compared with T1
v.mask_take(s, 0x02, "negative")
print("NEGATIVE CONTROL " + ("FAILED AS IT MUST" if v.fails else "PASSED -- the check is blind"))
```
```bash
bash .superpowers/v2/sync.sh
bash .superpowers/v2/wslrun mask-negative .venv/bin/python3 /mnt/c/Projects/Octabam/.superpowers/v2/mask-negative.py
```
Expected: `[FAIL] negative: T2.WAV equals track 1's ...` and `NEGATIVE CONTROL FAILED AS IT MUST`.

- [ ] **Step 3: Run the masks, and measure the eight-track drain**

```bash
bash .superpowers/v2/wslrun p2-masks .venv/bin/python3 tools/verify/verify_stems.py stems
```
Run in the background. Expected: every check passes. For `maskff`, read from its watch log (through a script) the frames from FINISHING to IDLE, and confirm `THRU_FRAMES - THRU_STOP` exceeds it by at least half; if not, raise `THRU_FRAMES` and write the measured drain into the constant's comment.

- [ ] **Step 4: Commit**

```bash
git add tools/verify/verify_stems.py
git commit -m "verify_stems: the mask takes on the THRU fixture -- 1, 2, 4, 8 tracks and 0xA5, each file sample-exact against its track, sound in every frame, the peak exact

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The `--long` masks, the latch, the wrap and the overflow at eight tracks

**Files:**
- Modify: `tools/verify/verify_stems.py` (`--long` masks; `latch()`; `wrap8()`; `overflow8()`)

**Interfaces:**
- Consumes: `mask_take`, `port`, `writes`, `watched`, `take_files`, `rebuilt_peak`.

- [ ] **Step 1: Write the four checks**

In `main()`'s `if "--long" in sys.argv:` block, after `limit(s)`:
```python
            for mask in (0x07, 0x1F, 0x3F, 0x7F, 0x80):
                mask_take(s, mask, f"mask{mask:02x}")
            latch(s)
            wrap8(s)
            overflow8(s)
```
Before `def main():`:
```python
def latch(s):
    """The mask poked to 0xFF while a T1 take records (a --poke lands about
    25 frames into play): the take keeps the mask it latched at its start."""
    pokes = [(s["stems_tracks"] + 3, 0xFF)]
    mask_take(s, 0x01, "latch", pokes=pokes)


def wrap8(s):
    """An eight-track take past the ring's 8,192 frames: the ring wraps, and
    every file still equals its track."""
    mask_take(s, 0xFF, "wrap8", stop_at=9000, frames=10500)


RING_FRAMES_8 = 0x400000 // 512      # 8,192


def overflow8(s):
    """The overflow check at eight tracks: the writer held, the ring made to
    look nearly full; the guard trips at 100 frames, eight complete files
    are written and closed, and the largest value the hook ever wrote to
    stems_peak is the ring's capacity (the watch log, span 28)."""
    used = RING_FRAMES_8 - 100
    rd = (-used) & 0xffffffff
    rd_off = 100 * 512
    pokes = [(s["stems_hold"] + 3, 1)]
    pokes += [(s["stems_rd"] + i, (rd >> (24 - 8 * i)) & 0xff) for i in range(4)]
    pokes += [(s["stems_rd_off"] + i, (rd_off >> (24 - 8 * i)) & 0xff) for i in range(4)]
    log, _, card, words, _ = port(s, 9200, stop_at=OVERFLOW_STOP, tag="overflow8", mask=0xFF,
                                  fixture=FIXTURE_THRU, pokes=pokes, dump_blocks=False,
                                  calls=((9000, s["stems_action"]),), extra=watched(s, span=28))
    st, status, _, wr, rd_end, _ = words
    ws = writes(s, log, span=28)
    statuses = [val for x, w, val in ws if w == 1]
    peaks = [val for x, w, val in ws if w == 6]
    check("overflow8: the hook stopped with ERR_OVERFLOW", ERR_OVERFLOW in statuses, f"status writes {statuses}")
    check("overflow8: stems_peak reached the ring's capacity", max(peaks, default=0) == RING_FRAMES_8,
          f"largest stems_peak write {max(peaks, default=0)} of {RING_FRAMES_8}")
    files = take_files(card, FIXTURE_THRU)
    sizes = [len(d) for _, d in files]
    check("overflow8: eight files, each the whole ring's share",
          len(files) == 8 and all(sz == 44 + RING_FRAMES_8 * 64 for sz in sizes), f"{sizes}")
    check("overflow8: the task went IDLE and the row armed again", st == ST_ARMED,
          f"state {st}, state writes {[val for x, w, val in ws if w == 0]}")
```
`writes()` reports word 6 (`stems_peak`) once the span is 28 bytes.

- [ ] **Step 2: Run `--long`**

```bash
bash .superpowers/v2/sync.sh
bash .superpowers/v2/wslrun p2-long .venv/bin/python3 tools/verify/verify_stems.py stems --long
```
Run in the background; tell Yves the log. Expected: every check passes. For `overflow8`, read from its watch log the frames from FINISHING to IDLE: the row at 9,000 must come after IDLE; if not, move the row and the end later and write the measured drain in a comment. `latch`'s files must be `T1.WAV` only.

- [ ] **Step 3: Commit**

```bash
git add tools/verify/verify_stems.py
git commit -m "verify_stems --long: 3, 5, 6, 7 tracks and T8 alone, the mask latched at the start, an eight-track wrap, and the overflow at eight tracks with the peak at capacity

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The card-speed sweep

**Files:**
- Create: `tools/verify/stems_sweep.py`

**Interfaces:**
- Consumes: `verify_stems.port`, `watched`, `writes`, `rebuilt_peak`, `FIXTURE_THRU`, `syms`.
- Produces: `python3 tools/verify/stems_sweep.py [--counts 1,2,4,8] [--latencies 8,16,24,32,48,64] [--seconds 5]`, printing a Markdown table and writing `out/stems_sweep.json`.

- [ ] **Step 1: Write the sweep**

`tools/verify/stems_sweep.py`:
```python
#!/usr/bin/env python3
"""STEM REC against the emulated card's speed: which track counts the 4 MiB
ring survives at which card delay.

    python3 tools/verify/stems_sweep.py [--counts 1,2,4,8] [--latencies 8,16,24,32,48,64] [--seconds 5]

Each run is a take of --seconds on the THRU fixture (stems_fixture.py
--thru) under `ot_emu --ata-latency N` (samples between a card sector and
its interrupt; 8 is the port's default, STEM_REC.md 13.3). From the port's
watch log of the state words it reports the peak fill (frames, and a share
of the ring), whether and when the take overflowed, the writer's rate while
recording, and, when the fill still rises at the end, its growth and the
time left to overflow. The emulated card has a constant delay per sector; a
real card stalls, so this gives steady-rate limits only. Not a gate.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_stems as v  # noqa: E402

FPS = 44100 / 16            # frames a second
RING = 0x400000


def run(s, n, lat, seconds):
    mask = (1 << n) - 1
    stop = int(seconds * FPS)
    tag = f"sweep-{n}t-{lat}"
    log, _, _, words, _ = v.port(s, stop + 300, stop_at=stop, tag=tag, fixture=v.FIXTURE_THRU,
                                 mask=mask, dump_blocks=False,
                                 extra=(*v.watched(s, span=28), "--ata-latency", str(lat)))
    ws = v.writes(s, log, span=28)
    t0 = next((x for x, w, val in ws if w == 0 and val == v.ST_RECORDING), None)
    over = next((x for x, w, val in ws if w == 1 and val == v.ERR_OVERFLOW), None)
    rframes = RING // (64 * n)
    rd, fills = 0, []
    for x, w, val in ws:
        if w == 4:
            rd = val
        elif w == 3 and val:
            fills.append((x, val - rd))
    peak = v.rebuilt_peak(ws)
    rec = [(x, f) for x, f in fills if t0 is not None and x >= t0]
    end = rec[-1] if rec else (0, 0)
    back = [p for p in rec if p[0] <= end[0] - 44100]
    slope = (end[1] - back[-1][1]) if back else 0            # frames a second, over the last second
    rd_end = next((val for x, w, val in reversed(ws) if w == 4 and (over is None or x <= over)), 0)
    span_s = ((over or end[0]) - (t0 or 0)) / 44100 or 1
    return {
        "tracks": n, "latency": lat, "peak": peak, "peak_share": peak / rframes,
        "overflow_s": None if over is None or t0 is None else (over - t0) / 44100,
        "writer_MBps": rd_end * 64 * n / span_s / 1e6,
        "slope_fps": slope,
        "to_overflow_s": (rframes - end[1]) / slope if slope > 0 and over is None else None,
        "state": words[0], "status": words[1],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", default="1,2,4,8")
    ap.add_argument("--latencies", default="8,16,24,32,48,64")
    ap.add_argument("--seconds", type=float, default=5.0)
    a = ap.parse_args()
    env = {**os.environ, "REMIX": "stems", "XBUS": "1", "SPEC": "1"}
    subprocess.run([sys.executable, "tools/build/build_bus.py"], env=env, check=True, capture_output=True)
    s = v.syms()
    if not v.fixtures():
        sys.exit(f"stems_sweep: no fixtures (a project template at {v.TEMPLATE}: STEMS_TEMPLATE=<dir>)")
    rows = []
    for n in map(int, a.counts.split(",")):
        for lat in map(int, a.latencies.split(",")):
            r = run(s, n, lat, a.seconds)
            rows.append(r)
            print(json.dumps(r), flush=True)
    pathlib.Path("out/stems_sweep.json").write_text(json.dumps(rows, indent=2) + "\n")
    print("\n| Tracks | Latency | Peak fill | Overflow | Writer | Fill growth | To overflow |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['tracks']} | {r['latency']} | {r['peak_share']:.0%} ({r['peak']:,}) | "
              f"{'at %.2f s' % r['overflow_s'] if r['overflow_s'] is not None else 'no'} | "
              f"{r['writer_MBps']:.2f} MB/s | {r['slope_fps']:+,} frames/s | "
              f"{'%.1f s' % r['to_overflow_s'] if r['to_overflow_s'] else '-'} |")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: A short trial**

```bash
bash .superpowers/v2/sync.sh
bash .superpowers/v2/wslrun sweep-trial .venv/bin/python3 tools/verify/stems_sweep.py --counts 8 --latencies 8,64 --seconds 1
```
Expected: two JSON lines and a two-row table. At latency 8, eight tracks keep up (no overflow, peak well under 100%). At 64 the card is about eight times slower than the default, so eight tracks should overflow or show a positive fill growth. Any number that makes no sense against the arithmetic (for example a writer faster than the card allows) is a defect in the script: fix it before the full run.

- [ ] **Step 3: Commit, then the full sweep**

```bash
git add tools/verify/stems_sweep.py
git commit -m "stems_sweep: STEM REC against the emulated card's speed -- track counts against --ata-latency, the peak fill, overflow, the writer's rate

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
bash .superpowers/v2/sync.sh
bash .superpowers/v2/wslrun sweep .venv/bin/python3 tools/verify/stems_sweep.py
```
Run in the background (about 2 to 3 hours); tell Yves the log `/home/yvez/xcheck/v2-sweep.log`. Keep the printed table for Task 8.

---

### Task 8: The records

**Files:**
- Modify: `docs/firmware/STEM_REC.md` (section 15), `modules/stems/README.md`, `remixes/stems/README.md`, `modules/stems/manifest.py` (its docstring and `doc`), `docs/remixer/FAILURE_MODES.md` (the STEM REC block, only if a run showed a new failure mode), `README.md` and `docs/remixes/README.md` (re-rendered by `make docs`)
- Modify (local): `.superpowers/v2/hookcost.py`

- [ ] **Step 1: Measure the hook's cost**

```bash
bash .superpowers/v2/wslrun p2-hookcost .venv/bin/python3 /mnt/c/Projects/Octabam/.superpowers/v2/hookcost.py
bash .superpowers/v2/wslrun p2-hooktail .venv/bin/python3 /mnt/c/Projects/Octabam/.superpowers/v2/hooktail.py
```
Expected: the tail-excluded sums grow by about 3 to 4 instructions a frame over 12.2's 52,400 and 296,000 (the peak's `addq`, `cmp`, `bls`, and `move` while it rises). Record both.

- [ ] **Step 2: Write section 15**

Append to `docs/firmware/STEM_REC.md`:
```markdown
## 15. Eight tracks under the emulator

Piece 2 (`docs/superpowers/specs/2026-09-27-stem-rec-eight-tracks-design.md`).
The build records all eight tracks by default, and `stems_peak` keeps the
take's largest ring fill.

### 15.1 THRU input routing, measured ✅
### 15.2 The eight-track takes ✅
### 15.3 The hook's cost ✅
### 15.4 The card-speed sweep
```
Fill each subsection from the runlog and the logs, each claim marked ✅ or 🟡:
- **15.1:** Task 1's four measured lines; the INAB/INCD value order; which WAV channel is which input; the CC frame and why (the transport start reverts CC edits).
- **15.2:** every mask's result (`make check` and `--long`), the negative control, the eight-track drain measured in Tasks 5 and 6, the latch, the wrap and the overflow at eight tracks.
- **15.3:** Step 1's sums against 12.2's.
- **15.4:** the sweep's table, its method line (the command, the commit, the date), and its limit (a constant delay per sector, not stalls), with OctaLab's 1.2 s writes and 1.4 to 2.1 MB/s as the real card's reference (their `docs/OTX_PROJECT_PROPOSAL.md`).

- [ ] **Step 3: Say all eight tracks where the docs say T1**

- `modules/stems/manifest.py`: in the docstring, "this build enables T1 (stems_tracks = 0x01)" becomes "this build records all eight (stems_tracks = 0xFF)"; `doc=` becomes `"MAIN MENU > CONTROL > STEM REC: every track to the card while the sequencer plays (streamed: 16-bit, up to 60 min)."`; the frame-site Detour's note "per-frame tap: T1 into the ring" becomes "per-frame tap: the enabled tracks into the ring".
- `remixes/stems/remix.py`: `doc` and its docstring say every track, not T1.
- `modules/stems/README.md` and `remixes/stems/README.md`: "This build enables T1" becomes "This build records all eight tracks"; add a line on `stems_peak`.
- Re-render the tables: `bash .superpowers/v2/wslrun p2-docs make docs`, then copy `README.md` and `docs/remixes/README.md` back with `wsl.exe -- cat` as in piece 1.

- [ ] **Step 4: Commit**

```bash
git add docs/firmware/STEM_REC.md modules/stems/README.md remixes/stems/README.md remixes/stems/remix.py modules/stems/manifest.py README.md docs/remixes/README.md
git commit -m "STEM_REC 15: eight tracks under the emulator -- the THRU routing, every mask, the hook's cost, the card-speed sweep; the docs say all eight

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The final gates

- [ ] **Step 1: Both trees on the last commit**

`git status --porcelain` prints nothing; `bash .superpowers/v2/sync.sh` shows the same HEAD and `0 file(s) differ`.

- [ ] **Step 2: Run the gates**

In the background, one after another, each log's path told to Yves. Upstream's runner since Task 3u: `check-remix-gates` in place of `check-remix`, `accept` for the remix that carries the module, and `identity` in place of the local remix hash:
```bash
T="/home/yvez/stemrec2/out/projects/Ultimate FX 1.5.3"
bash .superpowers/v2/wslrun p2-final-gates env STEMS_TEMPLATE="$T" make check-remix-gates REMIX=stems JOBS=2
bash .superpowers/v2/wslrun p2-final-accept make accept REMIX=stems STRESS_SOURCE="$T"
bash .superpowers/v2/wslrun p2-final-long .venv/bin/python3 tools/verify/verify_stems.py stems --long --fat32
bash .superpowers/v2/wslrun p2-final-identity make identity BASE=2a849af
bash .superpowers/v2/wslrun p2-final-reach make reach BASE=2a849af
```
Expected: every gate of `check-remix-gates` is `ok` and `gate:verify_stems` has no SKIP; `accept` reports `passed`; `--long --fat32` has no FAIL; `identity` finds every remix that builds here identical except `stems`, which the base lacks; `reach` lists the gates for the record (the whole list, with the cover, is a pull request's run, not this piece's).

- [ ] **Step 3: Check the spec's "done when" list**

Each line of the spec's section 10 with its log and the line that proves it, into `.superpowers/v2/runlog.md`.

- [ ] **Step 4: The whole-branch review and the handoff**

Per the chosen execution skill. Then update the memory note, and report to Yves: the gates, every finding and ruling, and the sweep's table.
