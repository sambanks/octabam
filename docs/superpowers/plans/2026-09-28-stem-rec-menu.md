# STEM REC: the STEMS category in MAIN MENU, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** STEM REC gets a fifth MAIN MENU category, STEMS, with REC/STOP, a live status line, the take's PEAK, and T1 to T8, proven key by key under the port on the MKII and MKI panels, with CONTROL back to stock.

**Architecture:** The manifest grows MAIN MENU's root list (a `TableGrow` of the four stock rows plus STEMS, and a `Poke` of the count 4 to 5) instead of CONTROL's. `stems.s` carries the category's icon, its list descriptor (shipped filled in) and eleven rows in DRAM. Every row label is a pointer the module switches with one aligned long write: the actions switch fixed strings at once, and the writer task formats the numbers (`REC mm:ss`, `DONE mm:ss`, `PEAK n%`) into the buffer not showing. A new gate drives the real panel through `ot_emu --interactive`.

**Tech Stack:** m68k assembly (`stems.s`, GNU as `-mcpu=54455`, the bare-metal `m68k-elf` binutils 2.47), Python 3 (the verifier, the panel driver, the gate), the ColdFire port `ot_emu` (unchanged), WSL2 Ubuntu.

**Spec:** `docs/superpowers/specs/2026-09-28-stem-rec-menu-design.md`

## Global Constraints

- "The recorder's logic doesn't change: the state machine, the hook, the streaming, the files. Every existing check still passes."
- "Every value that moves is a finding: re-measured, explained, and written down, never loosened to pass."
- "Every gate runs on a committed tree, and its log's first line shows it."
- "The build uses the bare-metal `m68k-elf` toolchain (binutils 2.47, GCC 16.1.0), as upstream's authors do."
- "No Elektron byte in the repository." "Nothing is pushed." Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- The category: `STEMS`, a fifth root category under MIDI, a record-dot icon, 11 rows, 7 visible.
- The rows: 1 `REC` / `CANCEL` / `STOP` / `SAVING`; 2 the status; 3 `PEAK n%`; 4 to 11 `T1 [X]` to `T8 [X]` (`[ ]` when off). Rows 2 and 3 carry action 0.
- The status texts: `READY`, `ARMED`, `REC mm:ss`, `SAVING`, `DONE mm:ss`, `NO CARD`, and the error names `RING FULL`, `PATH FAILED`, `OPEN FAILED`, `SAME MINUTE`, `WRITE FAILED`, `SEEK FAILED`, `CLOSE FAILED`, `TASK FAILED`.
- The track rows are locked while recording or saving. One take per REC: after it, READY until REC again.
- Prose follows the Microsoft Writing Style Guide. Counts from logs go through a script file, never an inline `$(grep -c)` through `wsl.exe`.

## Review Focus

These five inputs follow from the spec, and no step of it tests them. Each line names the task that adds its test.

1. **Every track turned off.** Expected: the last track that's on can't be turned off, so a take always has a track and the rows show exactly what records (the hook's "no track: T1" fallback never fires from the menu). Test: Task 5's gate turns T1 to T8 off in turn and finds T8 still on.
2. **REC pressed while the take is saving.** Expected: nothing changes; the take finishes and ends on its result. Test: Task 4 adds a call of the action during `overflow`'s long FINISHING.
3. **A track turned off while armed.** Expected: the take records without it. Test: Task 5's gate arms with T3 off and finds seven files, T3's missing.
4. **UP from T1.** Expected: the cursor lands on REC, never on the status or PEAK row, whose ENTER would call address 0. Test: Task 5's gate, both ways.
5. **A take that reaches the 60-minute cap.** Expected: `DONE 60:00` fits and shows. Test: Task 4 adds the label check to `cap`.

---

## Conventions

- **Trees.** Git work in the worktree `.claude/worktrees/stem-rec-p3` (branch `stem-rec-p3`). Builds and runs in a WSL worktree `/home/yvez/stemrec3` of the clone `/home/yvez/stemrec2`, made in Task 1. Sync with `bash .superpowers/v2/sync-p3.sh`; run with `bash .superpowers/v2/wslrun-3 NAME CMD...`, which logs to `/home/yvez/xcheck/v3-NAME.log` with the HEAD and the dirty count on its first line. Tell Yves each long run's log path when it starts.
- **The template.** Every verifier run sets `STEMS_TEMPLATE="/home/yvez/stemrec3/out/projects/Ultimate FX 1.5.3"`.
- **Commits.** Stage by name; check `git status --porcelain` shows only the intended files staged before each commit.
- **Sam's runner.** Full verifier runs go through `make check-remix-gates REMIX=stems JOBS=2` (every per-remix gate, each in its own shard); quick runs use `verify_stems.py --static` or `--only=NAME,...` (Task 3 adds both).
- **Assembly.** `stems.s` assembles with `-mcpu=54455`. ColdFire instructions are at most six bytes, so an immediate can't be stored to an absolute address in one instruction: load it into a register first (`lea lbl,%a0` / `move.l %a0,addr`). `divu.l` and `mulu.l` take a register, never an immediate.

---

### Task 1: The toolchain, the WSL tree, and piece 2 again on the new toolchain

**Files:**
- Create (local): `.superpowers/v2/tc-switch.sh`, `.superpowers/v2/wsl-p3-wt.sh`, `.superpowers/v2/sync-p3.sh`, `.superpowers/v2/wsl-sync-p3.sh`, `.superpowers/v2/run-3.sh`, `.superpowers/v2/wslrun-3`
- Modify: `docs/firmware/STEM_REC.md` (a new section 15.5), `docs/remixes/BUILDING.md` (section 1a)

**Interfaces:**
- Produces: `/usr/local/bin/m68k-elf-*` naming `/opt/m68k-elf/bin`; the WSL worktree `/home/yvez/stemrec3` with its own port; `wslrun-3`.

- [ ] **Step 1: Wait for piece 2's long run, then switch the links**

The run `v2-p2-final2-long.log` must show its `# exit` line first (nothing may rebuild under it). Record it in the ledger (Task 9 of piece 2). Then write `.superpowers/v2/tc-switch.sh`:
```bash
#!/bin/bash
# The m68k-elf-* links in /usr/local/bin: from Ubuntu's m68k-linux-gnu tools
# to the bare-metal toolchain in /opt/m68k-elf (28 Sep 2026). The old
# targets are kept for a rollback.
set -euo pipefail
ls -l /usr/local/bin/m68k-elf-* > /home/yvez/xcheck/tc-links-before.txt
for f in /opt/m68k-elf/bin/m68k-elf-*; do
  sudo -n ln -sf "$f" /usr/local/bin/"$(basename "$f")"
done
for t in as ld objcopy nm objdump gcc; do m68k-elf-$t --version | head -1; done
cd /home/yvez/stemrec2 && scripts/disasm.sh emac 0x40003664 8
```
Run: `MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash -c "tr -d '\r' < /mnt/c/Projects/Octabam/.superpowers/v2/tc-switch.sh > /tmp/tc-switch.sh && bash /tmp/tc-switch.sh"`
Expected: `GNU assembler (GNU Binutils) 2.47.20260726`, `m68k-elf-gcc (GCC) 16.1.0`, and the disassembly prints `msacl`, not `invalid`.

- [ ] **Step 2: The WSL worktree for piece 3**

`.superpowers/v2/wsl-p3-wt.sh` (the recipe of `wsl-merge-wt.sh`, for branch `stem-rec-p3`):
```bash
#!/bin/bash
set -euo pipefail
SRC=/home/yvez/stemrec2
WT=/home/yvez/stemrec3
cd "$SRC"
git fetch -q origin stem-rec-p3
if [ -d "$WT" ]; then git -C "$WT" checkout -q --detach FETCH_HEAD
else git worktree add -q --detach "$WT" FETCH_HEAD; fi
cd "$WT"
for d in vendor .venv; do [ -e "$d" ] || ln -s "$SRC/$d" "$d"; done
mkdir -p out/raw out/projects
cp --update=none "$SRC/out/raw/section_3_MAIN_OS.bin" out/raw/
[ -d "out/projects/Ultimate FX 1.5.3" ] || cp -r "$SRC/out/projects/Ultimate FX 1.5.3" out/projects/
git submodule update --init --recursive -q
make emu-cf > /tmp/p3-emu-cf.log 2>&1 || { tail -5 /tmp/p3-emu-cf.log; exit 1; }
echo "stemrec3: HEAD $(git rev-parse --short HEAD), $(git status --porcelain | wc -l) file(s) differ"
```
`sync-p3.sh` is `sync-up.sh` with three names changed: `WT=/c/Projects/Octabam/.claude/worktrees/stem-rec-p3`, the branch test `[ "$BR" = stem-rec-p3 ]`, the list file `$V/sync-p3-list.txt`, and the WSL script it runs, `wsl-sync-p3.sh`. `wsl-sync-p3.sh` is `wsl-sync-up.sh` with:
```bash
SRC=/mnt/c/Projects/Octabam/.claude/worktrees/stem-rec-p3
LIST=/mnt/c/Projects/Octabam/.superpowers/v2/sync-p3-list.txt
DST=/home/yvez/stemrec3
cd "$DST"
git fetch -q origin stem-rec-p3          # in the worktree itself: FETCH_HEAD is per worktree
git reset -q --hard FETCH_HEAD
```
and the rest (the loop over the list, the closing `echo`) unchanged. `run-3.sh` and `wslrun-3` are `run-m.sh` and `wslrun-m` with `cd /home/yvez/stemrec3`, the log `/home/yvez/xcheck/v3-$name.log`, and the temporary script `/tmp/v3-run-$name.sh`.
Run: `bash .superpowers/v2/wslrun-m p3-wt bash /mnt/c/Projects/Octabam/.superpowers/v2/wsl-p3-wt.sh`, then `bash .superpowers/v2/sync-p3.sh`.
Expected: `stemrec3: HEAD <the plan's commit>, 0 file(s) differ` (the symlinks are excluded since Task 3u2).

- [ ] **Step 3: Piece 2's gates on the new toolchain**

Run: `bash .superpowers/v2/wslrun-3 p3-newtc-gates env STEMS_TEMPLATE="/home/yvez/stemrec3/out/projects/Ultimate FX 1.5.3" make check-remix-gates REMIX=stems JOBS=2`
Expected: `every gate of stems passed`; `gate:verify_stems` 152 PASS, 0 FAIL, 0 SKIP (count them with a script file, as `.superpowers/v2/count-gate.sh` does, pointed at `/home/yvez/stemrec3/out/check_shards/stems/gate_verify_stems.log`).

- [ ] **Step 4: Every moved value, explained**

Diff the check lines against piece 2's run on the Ubuntu toolchain (`/home/yvez/stemrec2/out/check_shards/stems/gate_verify_stems.log`, 4601774): strip the `0x...` addresses the new layout moves and compare the rest (the method of `compare5.sh`). Known before the run: the hook at `0x40a95a28` (was `0x40a95a2c`), `stems_ata_first` at `0x40a95c38` (was `0x40a95c52`), the stage end, and the runtime 48 bytes shorter (`.text` `0xd84`, was `0xdb4`). Any other value that moves (the `cardfail` poll count is the likeliest: the writer's instruction fetches changed) is written down with its cause, or measured until it has one.

- [ ] **Step 5: Record it**

In `docs/firmware/STEM_REC.md`, a section 15.5 "The bare-metal toolchain": the finding (the bare-metal assembler reads a same-section global PC-relative, 4 bytes, where Ubuntu's `m68k-linux-gnu` keeps an absolute read with an `R_68K_32`, 6 bytes, because a Linux target leaves globals preemptible), the size and addresses above, the rerun's result and every moved value. In `docs/remixes/BUILDING.md` 1a, after the paragraph on the apt tools: the bare-metal route, measured, with its commands:
```bash
sudo apt install -y libgmp-dev libmpfr-dev libmpc-dev libisl-dev zlib1g-dev libzstd-dev pkgconf texinfo
# binutils 2.47 and GCC 16.1.0 from ftp.gnu.org, each checked with gpgv against gnu-keyring.gpg
../binutils-2.47/configure --target=m68k-elf --prefix=/opt/m68k-elf --with-system-zlib --with-zstd --disable-nls
make -j2 && sudo make install
../gcc-16.1.0/configure --target=m68k-elf --prefix=/opt/m68k-elf --disable-nls --without-headers \
  --with-as=/opt/m68k-elf/bin/m68k-elf-as --with-ld=/opt/m68k-elf/bin/m68k-elf-ld \
  --enable-languages=c --with-system-zlib --with-zstd
make -j2 all-gcc && sudo make install-gcc && make -j2 all-target-libgcc && sudo make install-target-libgcc
for f in /opt/m68k-elf/bin/m68k-elf-*; do sudo ln -sf "$f" /usr/local/bin/; done
```
and what it proved: Octakit's rebuilt runtime matches its recipe, and USB MIDI's unit matches its author's build (1,124 B). Keep the apt paragraph, marked as the older route with its two refusals.
Run: `bash .superpowers/v2/sync-p3.sh && bash .superpowers/v2/wslrun-3 p3-docs1 python3 tools/verify/verify_docs.py`
Expected: `0 problems`.

- [ ] **Step 6: Commit**

```bash
git add docs/firmware/STEM_REC.md docs/remixes/BUILDING.md
git commit -m "STEM_REC 15.5, BUILDING 1a: the bare-metal m68k-elf toolchain -- STEM REC's bytes move (PC-relative reads of its globals), piece 2's gates pass on it; Octakit and USB MIDI match their authors" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The panel driver, and what the design assumes, measured

**Files:**
- Create: `tools/verify/stems_panel.py`, `tools/verify/stems_menu_probe.py`
- Modify: `docs/firmware/STEM_REC.md` (a new section 16.1), `docs/firmware/MAINMENU.md` (section 1's icon plane)

**Interfaces:**
- Produces: `stems_panel.MenuPort(image, card, set_name, project, mkii, log_path=None, extra=())`, a context manager, with `settle()`, `open_menu()`, `press(name, hold=60, settle=200)`, `chord(hold_name, name, settle=300)`, `key(name, down)`, `run(ms)`, `peek(addr, n) -> bytes`, `long(addr) -> int`, `cstr(addr, n=32) -> str`, `poke(addr, data)`, `screen() -> list[list[bool]]` (64 rows of 128), `png(path)`, `card_flush() -> str`; `stems_panel.MENU_FOCUS = 0x400cbda8`; `stems_panel.diff_box(a, b) -> (x0, x1, y0, y1) | None`.

- [ ] **Step 1: Write the driver**

`tools/verify/stems_panel.py`:
```python
#!/usr/bin/env python3
"""The port's panel, one key at a time, for a gate (STEM REC piece 3).

    from stems_panel import MenuPort
    with MenuPort(image, card, "STEMS", "ULTFX", mkii=True) as p:
        p.settle()                  # CLOCK RECEIVE cleared, the date prompt dismissed, frames on
        p.open_menu()               # PROJ on an MKII, FUNC+MIXER on an MKI
        p.press("down")
        p.png("out/stems_runs/menu.png")

Built on tools/panel/panel_server.py's PortProc and PortRt (`ot_emu
--interactive`: `run <ms>`, `key <row> <mask>`, `peek`, `poke`) and
panel_link.PanelLink (the screen, decoded from the bytes the CPU sends the
panel). Emulated time advances only in run(), in exact steps, so a run is
deterministic. A key is a bit in its matrix row, and the port takes a row's
whole bitmap, so held keys are kept per row. Key names:
tools/panel/key_map.json."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(ROOT / "tools" / "panel"))
from panel_link import PanelLink  # noqa: E402
from panel_server import PORT_BIN, PortProc, PortRt  # noqa: E402

KEYS = json.loads((ROOT / "tools/panel/key_map.json").read_text())["keys"]
MENU_FOCUS = 0x400cbda8     # the list descriptor the menu's cursor is in (MAINMENU.md 4)


def diff_box(a, b):
    """The box around every pixel that differs between two screens, as
    (x0, x1, y0, y1), or None when they are the same."""
    pts = [(x, y) for y in range(64) for x in range(128) if a[y][x] != b[y][x]]
    if not pts:
        return None
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    return min(xs), max(xs), min(ys), max(ys)


class MenuPort:
    def __init__(self, image, card, set_name, project, mkii, log_path=None, extra=()):
        self.mkii = mkii
        argv = [str(PORT_BIN), "--image", str(image), "--card", str(card), "--set", set_name,
                "--project", project, "--load-ms", "20000", "--dsp", "--card-rw", "--interactive",
                *(["--mkii"] if mkii else []), *extra]
        self.proc = PortProc(argv, log_path=log_path)
        self.proc.wait_ready(900)
        self.rt = PortRt(self.proc)
        self.link = PanelLink()
        self.pos = 0
        self.held = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            self.proc.command("quit", "ok", timeout=60)
        except Exception:
            self.proc.kill()

    def run(self, ms):
        self.rt.run(ms=ms)
        self.rt.poll_tx()
        tx = self.rt.uart64.tx
        self.link.feed(bytes(tx[self.pos:]))
        self.pos = len(tx)

    def key(self, name, down):
        row, bit = KEYS[name]
        m = self.held.get(row, 0)
        m = m | (1 << bit) if down else m & ~(1 << bit)
        self.held[row] = m
        self.proc.command(f"key {row:#x} {m:#x}", "ok")

    def press(self, name, hold=60, settle=200):
        self.key(name, True)
        self.run(hold)
        self.key(name, False)
        self.run(settle)

    def chord(self, hold_name, name, settle=300):
        self.key(hold_name, True)
        self.run(60)
        self.press(name, settle=60)
        self.key(hold_name, False)
        self.run(settle)

    def settle(self):
        """What the panel server does before play (panel_server.py): CLOCK
        RECEIVE cleared, 300 ms, the boot's SET DATE/TIME prompt dismissed
        with NO, then the frame interrupt on for good, so PLAY steps the
        sequencer."""
        self.rt.internal_clock()
        self.run(300)
        self.press("no", settle=300)
        self.rt.frame = True
        self.run(300)

    def open_menu(self):
        if self.mkii:
            self.press("proj", settle=400)
        else:
            self.chord("func", "mixer", settle=400)

    def peek(self, addr, n):
        return bytes(self.rt.uc.mem_read(addr, n))

    def long(self, addr):
        return int.from_bytes(self.peek(addr, 4), "big")

    def cstr(self, addr, n=32):
        return self.peek(addr, n).split(b"\0")[0].decode("latin1")

    def poke(self, addr, data):
        self.rt.uc.mem_write(addr, bytes(data))

    def screen(self):
        return [list(r) for r in self.link.lcd_rows()]

    def png(self, path):
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.link.render_png(3))

    def card_flush(self):
        return self.proc.command("card flush", "card")
```

- [ ] **Step 2: Write the probe**

`tools/verify/stems_menu_probe.py` measures, on the current build (STEM REC still in CONTROL), the six facts the design stands on. It's run by hand, like `stems_sweep.py`:
```python
#!/usr/bin/env python3
"""What STEMS's menu design assumes, measured under the port (piece 3,
Task 2; docs/superpowers/specs/2026-09-28-stem-rec-menu-design.md).

    python3 tools/verify/stems_menu_probe.py [--mki]

Builds REMIX=stems and the fixtures, boots the one-track fixture card
under `ot_emu --interactive`, and prints:
1. MAIN MENU opens (PROJ on an MKII, FUNC+MIXER on an MKI) on the root.
2. YES enters a category's list and NO leaves it (the focus pointer).
3. A label changed while the menu shows it redraws with no key: the live
   screen octalab's MENU.md reports.
4. The clip edge of the root column and of the list pane: a row's label
   set to an empty string, then to 24 Ws; the box of what changed.
5. A heading row: CONTROL's row 1 (INPUT) with its action poked to 0 --
   the cursor goes from AUDIO to SEQUENCER, and the PNG shows its drawing.
6. PLAY and STOP with the menu open: the transport word.
PNGs go to out/stems_runs/probe-<model>-*.png."""
import json
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_stems as vs  # noqa: E402
from stems_panel import MENU_FOCUS, MenuPort, diff_box  # noqa: E402

ROOT_DESC, ROOT_ROWS, CONTROL_DESC = 0x400cbd8c, 0x400cc698, 0x400cbd54
SEL, TRANSPORT = 0x0c, 0x800065b8
WORK = pathlib.Path("out/stems_runs")


def label_box(p, label_at, scratch, text):
    """Point the row whose label pointer is at `label_at` at `text` (written
    to `scratch`), let the menu redraw, and return the screen."""
    p.poke(scratch, text.encode("latin1") + b"\0")
    p.poke(label_at, scratch.to_bytes(4, "big"))
    p.run(500)
    return p.screen()


def main():
    model = "mki" if "--mki" in sys.argv else "mkii"
    env = {**os.environ, "REMIX": "stems", "XBUS": "1", "SPEC": "1"}
    subprocess.run([sys.executable, "tools/build/build_bus.py"], check=True, capture_output=True, env=env)
    if not vs.fixtures():
        sys.exit("no fixture template (STEMS_TEMPLATE)")
    s = vs.syms()
    fx = json.loads(vs.FIXTURE.read_text())
    card = WORK / f"probe-{model}.img"
    WORK.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fx["card"], card)
    scratch = s["stems_fpath"]            # 256 bytes the runtime uses only while a take starts
    with MenuPort(vs.IMAGE, card, fx["set"], fx["project"], model == "mkii",
                  log_path=WORK / f"probe-{model}.log") as p:
        p.settle()
        p.open_menu()
        p.png(WORK / f"probe-{model}-root.png")
        print(f"1. focus {p.long(MENU_FOCUS):#x} (root {ROOT_DESC:#x}), root selection {p.long(ROOT_DESC + SEL)}")
        for _ in range(2):
            p.press("down")
        p.press("yes")
        ctl = p.long(MENU_FOCUS)
        p.press("no")
        print(f"2. YES on CONTROL: focus {ctl:#x} (CONTROL {CONTROL_DESC:#x}); NO: focus {p.long(MENU_FOCUS):#x}")
        rows = p.long(CONTROL_DESC + 0x18)
        before = p.screen()
        after = label_box(p, rows, scratch, "LIVE TEST")
        print(f"3. a label changed with no key: screen changed {diff_box(before, after)}")
        p.png(WORK / f"probe-{model}-live.png")
        audio = p.long(rows)                 # AUDIO's label pointer, put back after
        empty = label_box(p, rows, scratch, "")
        wide = label_box(p, rows, scratch, "W" * 24)
        print(f"4a. list pane: 24 Ws against empty, box {diff_box(empty, wide)}")
        p.png(WORK / f"probe-{model}-pane.png")
        for text in ("SAME MINUTE", "WRITE FAILED", "CLOSE FAILED", "DONE 60:00", "PEAK 100%", "T8 [X]"):
            print(f"    {text!r}: box {diff_box(empty, label_box(p, rows, scratch, text))}")
        p.poke(rows, audio.to_bytes(4, "big"))
        root_label = ROOT_ROWS + 3 * 24     # MIDI's label pointer (the stock root rows)
        stock = p.long(root_label)
        empty = label_box(p, root_label, scratch, "")
        wide = label_box(p, root_label, scratch, "W" * 24)
        print(f"4b. root column: 24 Ws against empty, box {diff_box(empty, wide)}")
        print(f"    'STEMS': box {diff_box(empty, label_box(p, root_label, scratch, 'STEMS'))}")
        p.png(WORK / f"probe-{model}-root-wide.png")
        p.poke(root_label, stock.to_bytes(4, "big"))
        p.poke(rows + 24 + 8, bytes(4))     # INPUT's action := 0, a heading
        p.press("yes")
        seen = [p.long(CONTROL_DESC + SEL)]
        p.press("down"); seen.append(p.long(CONTROL_DESC + SEL))
        p.press("up"); seen.append(p.long(CONTROL_DESC + SEL))
        p.png(WORK / f"probe-{model}-heading.png")
        print(f"5. CONTROL selection: start, down, up = {seen} (a skipped heading reads [0, 2, 0])")
        t0 = p.long(TRANSPORT)
        p.press("play", settle=600)
        t1 = p.long(TRANSPORT)
        p.press("stop", settle=600)
        print(f"6. transport with the menu open: {t0} -> PLAY {t1} -> STOP {p.long(TRANSPORT)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it on both panels**

Run: `bash .superpowers/v2/sync-p3.sh && bash .superpowers/v2/wslrun-3 p3-probe-mkii env STEMS_TEMPLATE="/home/yvez/stemrec3/out/projects/Ultimate FX 1.5.3" .venv/bin/python3 tools/verify/stems_menu_probe.py`, then the same with `--mki` (log `p3-probe-mki`).
Expected: 1 focus `0x400cbd8c`, selection 0; 2 focus `0x400cbd54` after YES and `0x400cbd8c` after NO; 3 a box (the screen changed with no key); 4a and 4b two boxes whose right edges (`x1`) are the clip edges; each listed text's `x1` below 4a's; `'STEMS'`'s `x1` below 4b's; 5 `[0, 2, 0]`; 6 transport `0 -> PLAY 1 -> STOP` 0 or 2.

- [ ] **Step 4: Decide, from the numbers**

- **If 3 printed `None`** (no redraw without a key), STOP: the design's live status depends on it. Raise it with Yves with the PNGs before any other task.
- **If 5 isn't `[0, 2, 0]`**, STOP: a heading row the cursor can land on would call address 0. Raise it with Yves.
- **The error names.** If every long name's `x1` is below the pane's clip edge, Tasks 3 and 4 use them. Otherwise they use the short forms, all ten characters or fewer: `RING FULL`, `PATH FAIL`, `OPEN FAIL`, `SAME MIN`, `WRITE FAIL`, `SEEK FAIL`, `CLOSE FAIL`, `TASK FAIL`. Write the choice into the ledger.
- **YES and NO.** If 2 differs, the gate in Task 5 uses whatever enters and leaves a list (RIGHT and LEFT are the next candidates); record which.
- **If 6 shows PLAY doing nothing with the menu open**, the gate closes the menu before PLAY and STOP (it does so anyway: Task 5).

- [ ] **Step 5: Record it**

`docs/firmware/STEM_REC.md` section 16.1, "What the menu design stands on, measured": the six results on both panels, the clip edges in pixels, the PNG names, and the error-name choice. `docs/firmware/MAINMENU.md` section 1: the icon's planes are 19 LONGS (a plane is `0x4c` bytes; the second starts `0x4c` after the first in all four stock icons), each holding the column in its top byte, and the second plane is `0xff800000` in every column; mark the old "19 words" retracted. Add a line to section 4: a label pointer changed while the menu shows it redraws with no key (measured under the port, MKII and MKI).
Run: `bash .superpowers/v2/sync-p3.sh && bash .superpowers/v2/wslrun-3 p3-docs2 python3 tools/verify/verify_docs.py` → `0 problems`.

- [ ] **Step 6: Commit**

```bash
git add tools/verify/stems_panel.py tools/verify/stems_menu_probe.py docs/firmware/STEM_REC.md docs/firmware/MAINMENU.md
git commit -m "stems_panel, stems_menu_probe: the port's panel key by key; STEM_REC 16.1: the live redraw, the clip edges, a heading row, the keys -- measured on the MKII and MKI" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The category: STEMS in the root, its rows, the track action

**Files:**
- Modify: `modules/stems/stems.s` (the menu section, the track action), `modules/stems/manifest.py` (root instead of CONTROL), `tools/verify/verify_stems.py` (`static`, `menu_static`, `runtime_at`, `--static`, `--only=`)

**Interfaces:**
- Consumes: Task 2's error-name choice.
- Produces: symbols `stems_cat_label`, `stems_icon`, `stems_icon_p0`, `stems_icon_p1`, `stems_list`, `stems_rows`, `stems_track_action`, `stems_zero` (global); `.equ ROW_LEN 24`, `MENU_ROWS 11`, `ROW_TRK0 3`, `LIST_SEL 0x0c`; tables `rec_by_state`, `st_by_state`, `err_names`, `trk_on`, `trk_off`; strings `lbl_rec`, `lbl_cancel`, `lbl_stop`, `lbl_saving`, `lbl_ready`, `lbl_armed`, `lbl_nocard`, `lbl_peak0`, `err_ring`..`err_task`, `trk1_on`..`trk8_off`. Python: `verify_stems.runtime_at(s, addr, n) -> bytes`, `verify_stems.MENU_ROWS = 11`, `verify_stems.ROW_TRK0 = 3`.

- [ ] **Step 1: Write the failing checks**

In `tools/verify/verify_stems.py`, below `CONTROL_DESC, ...`:
```python
ROOT_DESC, ROOT_ROWS, ROOT_N = 0x400cbd8c, 0x400cc698, 4      # MAIN MENU's root (MAINMENU.md 2)
MENU_ROWS, ROW_TRK0, MENU_VISIBLE = 11, 3, 7                   # stems.s: the STEMS list
```
Replace `static()`'s first six checks (the CONTROL ones, up to "row 7 window, pad, child and id are 0") with:
```python
    n = rd32(img, ROOT_DESC)
    check("MAIN MENU has five categories", n == 5, f"{n}")
    rows = rd32(img, ROOT_DESC + 0x18)
    check("the root rows moved", rows != ROOT_ROWS, f"0x{rows:08x}")
    a, b = rows - BASE, ROOT_ROWS - BASE
    check("the four stock categories came across byte for byte",
          img[a:a + ROW_LEN * ROOT_N] == stock[b:b + ROW_LEN * ROOT_N])
    r5 = [rd32(img, rows + ROW_LEN * ROOT_N + 4 * k) for k in range(6)]
    check("category 5 is STEMS: its label, its icon and its list; no action, getter or id",
          r5 == [s["stems_cat_label"], s["stems_icon"], 0, 0, s["stems_list"], 0], f"{[hex(x) for x in r5]}")
    c = CONTROL_DESC - BASE
    check("CONTROL is stock: its descriptor byte for byte (six rows, its own row array)",
          img[c:c + 0x1c] == stock[c:c + 0x1c], f"count {rd32(img, CONTROL_DESC)}")
```
Replace `runtime_long` with two helpers:
```python
def runtime_at(s, addr, n):
    """n bytes of the linked runtime as built (out/platform/runtime.raw), by address."""
    from remix import platform_build
    lay = json.loads((LAYOUT_DIR / platform_build.LAYOUT).read_text())
    raw = (LAYOUT_DIR / "runtime.raw").read_bytes()
    return raw[addr - lay["base"]:addr - lay["base"] + n]


def runtime_long(s, name):
    """A long of the linked runtime as built, by symbol."""
    return int.from_bytes(runtime_at(s, s[name], 4), "big")
```
Add after `static()`:
```python
def menu_static(s):
    """The STEMS list as it ships: filled in (the boot's set-up covers only
    the stock lists), eleven rows, REC's and the tracks' actions, two
    headings, every label as at boot, the record-dot icon."""
    lng = lambda a: int.from_bytes(runtime_at(s, a, 4), "big")
    txt = lambda a: runtime_at(s, a, 32).split(b"\0")[0].decode("latin1")
    lst = [lng(s["stems_list"] + 4 * k) for k in range(7)]
    check("the STEMS list ships filled in: 11 rows, 7 visible, its rows",
          lst == [MENU_ROWS, 0, 0, 0, MENU_VISIBLE, MENU_ROWS, s["stems_rows"]], f"{[hex(x) for x in lst]}")
    rows = [[lng(s["stems_rows"] + ROW_LEN * r + 4 * k) for k in range(6)] for r in range(MENU_ROWS)]
    check("row 1 runs stems_action, rows 2 and 3 are headings, T1-T8 run stems_track_action",
          [r[2] for r in rows] == [s["stems_action"], 0, 0] + [s["stems_track_action"]] * 8,
          f"{[hex(r[2]) for r in rows]}")
    check("no row has a window, a getter, a child or a page id",
          all(r[1] == r[3] == r[4] == r[5] == 0 for r in rows))
    texts = [txt(r[0]) for r in rows]
    check("the rows ship as REC, READY, PEAK 0%, T1 [X] .. T8 [X]",
          texts == ["REC", "READY", "PEAK 0%"] + [f"T{k} [X]" for k in range(1, 9)], f"{texts}")
    check("the category is labelled STEMS", txt(s["stems_cat_label"]) == "STEMS")
    icon = [lng(s["stems_icon"] + 4 * k) for k in range(5)]
    p0 = [lng(s["stems_icon_p0"] + 4 * k) for k in range(19)]
    p1 = [lng(s["stems_icon_p1"] + 4 * k) for k in range(19)]
    check("the icon is 19 x 9 with two planes, a dot the same upside down, the stock mask",
          icon == [0x13, 9, 1, s["stems_icon_p0"], s["stems_icon_p1"]] and p0 == p0[::-1]
          and all(c & 0x80ffffff == 0 for c in p0) and any(p0) and p1 == [0xff800000] * 19,
          f"{[hex(c >> 24) for c in p0]}")
```
In `main()`, after `static(img, stock, s)`: `menu_static(s)`. Then add the two options, replacing the list of port runs with a table, so a run can be named:
```python
    if "--static" in sys.argv:
        return 1 if fails else 0
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    runs = [("probe", probe), ("thru", thru), ("tap", tap), ("full", full), ("rowstop", rowstop),
            ("stream", stream), ("wrap", wrap), ("cap", cap), ("eight", eight)]
    runs += [(f"mask{m:02x}", lambda s, m=m: mask_take(s, m, f"mask{m:02x}"))
             for m in (0x01, 0x03, 0x0F, 0xFF, 0xA5)]
    runs += [("cut", cut), ("exists", exists), ("overflow", overflow), ("cardfail", cardfail)]
    if "--long" in sys.argv:
        runs += [("limit", limit)]
        runs += [(f"mask{m:02x}", lambda s, m=m: mask_take(s, m, f"mask{m:02x}"))
                 for m in (0x07, 0x1F, 0x3F, 0x7F, 0x80)]
        runs += [("latch", latch), ("wrap8", wrap8), ("overflow8", overflow8), ("slow8", slow8)]
    if "--fat32" in sys.argv:
        runs += [("fat32", fat32)]
```
and in the `elif fixtures():` branch: `for name, fn in runs: if only is None or name in only: fn(s)`. The order is today's. Update the module docstring's first paragraph: "Static, from the built image: MAIN MENU has five categories, the four stock ones byte for byte and STEMS fifth; CONTROL is stock; the STEMS list ships filled in ... `--static` stops after the static checks; `--only=NAME,...` runs only the named port runs."

- [ ] **Step 2: Run them to see them fail**

Run: `bash .superpowers/v2/sync-p3.sh && bash .superpowers/v2/wslrun-3 p3-cat-red .venv/bin/python3 tools/verify/verify_stems.py stems --static`
Expected: `[FAIL] MAIN MENU has five categories  4`, and `menu_static` stops with a `KeyError: 'stems_list'` (the symbol doesn't exist yet). Both are the expected red.

- [ ] **Step 3: The category's data and the track action in `stems.s`**

Replace the section `| ---- the menu row ---...` (the `stems_label` block, lines "the menu row" to the `.balign 2` after it) with:
```asm
| ---- the STEMS category (docs/superpowers/specs/2026-09-28-stem-rec-menu-design.md)
| A fifth MAIN MENU category. The manifest's TableGrow gives the root a row
| pointing at stems_cat_label, stems_icon and stems_list. The list and its
| rows live here, in DRAM: the menu engine writes the list's cursor
| fields, and STEM REC rewrites the rows' labels. A label changes by one
| aligned long write to the row's +0x00, so a redraw reads a whole old
| label or a whole new one.
        .equ    ROW_LEN,       24           | a menu row (MAINMENU.md 1)
        .equ    MENU_ROWS,     11
        .equ    MENU_VISIBLE,  7            | a submenu pane's rows
        .equ    ROW_TRK0,      3            | T1's row
        .equ    LIST_SEL,      0x0c         | a list's absolute selection: the row under the cursor
        .global stems_cat_label, stems_icon, stems_icon_p0, stems_icon_p1, stems_list, stems_rows, stems_zero
        .equ    stems_zero, 0               | the root row's action, getter and id
stems_cat_label:
        .asciz  "STEMS"
        .balign 4
stems_icon:                                 | 19 x 9, two planes (MAINMENU.md 1)
        .long   0x13, 0x09, 0x01, stems_icon_p0, stems_icon_p1
stems_icon_p0:                              | a record dot: one long a column, the column in its top byte
        .long   0, 0, 0, 0, 0, 0
        .long   0x1c000000, 0x3e000000, 0x7f000000, 0x7f000000, 0x7f000000, 0x3e000000, 0x1c000000
        .long   0, 0, 0, 0, 0, 0
stems_icon_p1:                              | the stock icons' second plane, every column
        .rept   19
        .long   0xff800000
        .endr
stems_list:                                 | shipped filled in: the boot's set-up covers only stock lists
        .long   MENU_ROWS, 0, 0, 0, MENU_VISIBLE, MENU_ROWS, stems_rows
stems_rows:                                 | label, window, action, getter, child, page id
        .long   lbl_rec,   0, stems_action, 0, 0, 0
        .long   lbl_ready, 0, 0, 0, 0, 0    | the status: action 0, a heading the cursor skips
        .long   lbl_peak0, 0, 0, 0, 0, 0    | PEAK: a heading
        .long   trk1_on, 0, stems_track_action, 0, 0, 0
        .long   trk2_on, 0, stems_track_action, 0, 0, 0
        .long   trk3_on, 0, stems_track_action, 0, 0, 0
        .long   trk4_on, 0, stems_track_action, 0, 0, 0
        .long   trk5_on, 0, stems_track_action, 0, 0, 0
        .long   trk6_on, 0, stems_track_action, 0, 0, 0
        .long   trk7_on, 0, stems_track_action, 0, 0, 0
        .long   trk8_on, 0, stems_track_action, 0, 0, 0
rec_by_state:   .long   lbl_rec, lbl_cancel, lbl_stop, lbl_saving       | row 1, by state
st_by_state:    .long   lbl_ready, lbl_armed, 0, lbl_saving             | the status; RECORDING is the task's
err_names:      .long   0, err_ring, err_path, err_open, err_exists, err_write, err_seek, err_close, err_task
trk_on:         .long   trk1_on, trk2_on, trk3_on, trk4_on, trk5_on, trk6_on, trk7_on, trk8_on
trk_off:        .long   trk1_off, trk2_off, trk3_off, trk4_off, trk5_off, trk6_off, trk7_off, trk8_off
lbl_rec:        .asciz  "REC"
lbl_cancel:     .asciz  "CANCEL"
lbl_stop:       .asciz  "STOP"
lbl_saving:     .asciz  "SAVING"
lbl_ready:      .asciz  "READY"
lbl_armed:      .asciz  "ARMED"
lbl_nocard:     .asciz  "NO CARD"
lbl_peak0:      .asciz  "PEAK 0%"
err_ring:       .asciz  "RING FULL"         | ERR_OVERFLOW
err_path:       .asciz  "PATH FAILED"       | ERR_PATH
err_open:       .asciz  "OPEN FAILED"       | ERR_OPEN
err_exists:     .asciz  "SAME MINUTE"       | ERR_EXISTS
err_write:      .asciz  "WRITE FAILED"      | ERR_WRITE
err_seek:       .asciz  "SEEK FAILED"       | ERR_SEEK
err_close:      .asciz  "CLOSE FAILED"      | ERR_CLOSE
err_task:       .asciz  "TASK FAILED"       | ERR_TASK
trk1_on:  .asciz "T1 [X]"
trk1_off: .asciz "T1 [ ]"
trk2_on:  .asciz "T2 [X]"
trk2_off: .asciz "T2 [ ]"
trk3_on:  .asciz "T3 [X]"
trk3_off: .asciz "T3 [ ]"
trk4_on:  .asciz "T4 [X]"
trk4_off: .asciz "T4 [ ]"
trk5_on:  .asciz "T5 [X]"
trk5_off: .asciz "T5 [ ]"
trk6_on:  .asciz "T6 [X]"
trk6_off: .asciz "T6 [ ]"
trk7_on:  .asciz "T7 [X]"
trk7_off: .asciz "T7 [ ]"
trk8_on:  .asciz "T8 [X]"
trk8_off: .asciz "T8 [ ]"
        .balign 2
```
If Task 2 chose the short error names, the eight `err_*` strings take them instead. After `stems_action`'s `rts` (the end of the menu action), add the track action:
```asm
| ---- a track row's action: action(0), in the UI task --------------------
| The row under the cursor names the track (the list's absolute selection,
| less T1's row, as octalab's checkbox rows do). Locked while a take
| records or saves: the take keeps the mask it latched at its start, and
| the rows show what records. The last track that's on stays on, so a take
| always has a track the rows show. The test and the flip run with
| interrupts masked, so the hook can't latch between them.
        .global stems_track_action
stems_track_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  stems_list+LIST_SEL,%d3
        subq.l  #ROW_TRK0,%d3               | track k, 0..7
        moveq   #8,%d0
        cmp.l   %d0,%d3
        bcc.s   .Lk_out                     | not a track row (unsigned: below T1 too)
        move.w  %sr,%d2
        move.w  #0x2700,%sr
        move.l  stems_state,%d1
        moveq   #ST_RECORDING,%d0
        cmp.l   %d0,%d1
        bcc.s   .Lk_keep                    | RECORDING or FINISHING: locked
        moveq   #1,%d0
        lsl.l   %d3,%d0                     | the track's bit
        move.l  stems_tracks,%d1
        eor.l   %d0,%d1
        tst.b   %d1
        beq.s   .Lk_keep                    | the last track on: it stays on
        move.l  %d1,stems_tracks
        move.w  %d2,%sr
        lea     trk_off,%a0
        and.l   %d0,%d1
        beq.s   .Lk_label
        lea     trk_on,%a0
.Lk_label:
        move.l  (%a0,%d3.l*4),%d0           | the label
        move.l  %d3,%d1
        addq.l  #ROW_TRK0,%d1
        lsl.l   #3,%d1                      | row * 8
        movea.l %d1,%a1
        adda.l  %d1,%a1
        adda.l  %d1,%a1                     | row * 24
        adda.l  #stems_rows,%a1
        move.l  %d0,(%a1)                   | the row's label pointer
        bra.s   .Lk_out
.Lk_keep:
        move.w  %d2,%sr
.Lk_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts
```
Change the file's header comment line "stems_action      MAIN MENU > CONTROL > STEM REC, in the UI task" to "stems_action      MAIN MENU > STEMS > REC, in the UI task; stems_track_action T1-T8".

- [ ] **Step 4: The manifest: the root, not CONTROL**

In `modules/stems/manifest.py`, replace the CONTROL constants and comment with:
```python
# MAIN MENU's root (docs/firmware/MAINMENU.md sections 1-5): count at
# +0x00, row array pointer at +0x18. TableGrow copies the four stock
# categories from the user's image at build time and appends STEMS: a
# category row has a window (its icon) and a child (its list), no action,
# no getter, id 0. The STEMS list and its rows are in stems.s.
ROOT_DESC = 0x400CBD8C
ROOT_ROWS = 0x400CC698
ROOT_N, ROW_WORDS = 4, 6
```
and the `tables=`/`pokes=` arguments with:
```python
    tables=(TableGrow("MAIN MENU root + STEMS", old=ROOT_ROWS,
                      count=ROOT_N * ROW_WORDS,
                      symbols=(("stems", "stems_cat_label"), ("stems", "stems_icon"),
                               ("stems", "stems_zero"), ("stems", "stems_zero"),
                               ("stems", "stems_list"), ("stems", "stems_zero")),
                      refs=((ROOT_DESC + 0x18, ROOT_ROWS),)),),
    pokes=(Poke(ROOT_DESC, expect=(ROOT_N).to_bytes(4, "big"),
                write=(ROOT_N + 1).to_bytes(4, "big"), note="MAIN MENU categories 4 -> 5 (STEMS)"),),
```
In the module docstring, "MAIN MENU > CONTROL > STEM REC arms a recording" becomes "MAIN MENU > STEMS > REC arms a recording", and "No module upstream hooks the frame site or rewrites the CONTROL list" becomes "No module upstream hooks the frame site or grows MAIN MENU's root". `doc=` becomes `"MAIN MENU > STEMS: every track to the card while the sequencer plays (streamed: 16-bit, up to 60 min)."`.

- [ ] **Step 5: Run the checks to see them pass**

Run: `bash .superpowers/v2/sync-p3.sh && bash .superpowers/v2/wslrun-3 p3-cat-green .venv/bin/python3 tools/verify/verify_stems.py stems --static`
Expected: every line PASS, the new ones included, exit 0. If the assembler reports a branch out of range, lengthen that one branch (`.s` to `.w`); if it refuses an instruction form, disassemble (`m68k-elf-objdump -d out/platform/runtime/runtime.elf`) before changing anything.

- [ ] **Step 6: The selftest and the other remixes**

Run: `bash .superpowers/v2/wslrun-3 p3-cat-selftest python3 tools/remix/selftest.py`
Expected: the selftest passes; every remix builds or is skipped by name as before (the new toolchain: expect fewer skips than the 15 of 28 Sep, since Octakit and USB MIDI now build).

- [ ] **Step 7: Commit**

```bash
git add modules/stems/stems.s modules/stems/manifest.py tools/verify/verify_stems.py
git commit -m "stems: STEMS as MAIN MENU's fifth category instead of the CONTROL row -- the root grown, the list shipped filled in, eleven rows, the record-dot icon, the track rows' action; verify_stems --static and --only" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The labels that change

**Files:**
- Modify: `modules/stems/stems.s` (`stems_action`, `stems_ui_state`, `stems_ui`, the task loop, the UI words), `tools/verify/verify_stems.py` (`port()`'s `steps` and `calls_before`, `ui_mems`, `ui_step`, `ui_read`, `mmss`, `labels`, `nocard`, and label checks in `exists`, `overflow`, `cap`)

**Interfaces:**
- Consumes: Task 3's rows, tables and strings.
- Produces: symbols `stems_took`, `stems_ui_bufs` (global); `stems_ui` (the task's, every pass), `stems_ui_state` (the actions'). Python: `port(..., steps=())` (each a `--step` argument), `calls_before=()` means no call before play; `ui_mems(s, when)`, `ui_step(s, frame, tag, when)`, `ui_read(s, tag, when) -> (texts, words)`, `mmss(frames) -> str`.

- [ ] **Step 1: Write the failing checks**

In `tools/verify/verify_stems.py`, `port()`: add the parameter `steps=()` and, after the `--poke-before-play` lines, `for st in steps: args += ["--step", st]`. Replace the `--call-before-play` element of `args` so an empty tuple means none:
```python
    before = (s["stems_action"],) if calls_before is None else tuple(calls_before)
```
with `*(["--call-before-play", ",".join(f"0x{a:x}:0" for a in before)] if before else [])` in the list. Add to its docstring: "`steps` are upstream's `--step FRAME:call|poke|dump:SPEC` scripts, frames counted from the transport start like `calls`. `calls_before=()` arms nothing."

Add after `run_path`:
```python
UI_BUFS = 64        # stems.s: stems_ui_bufs, two status and two PEAK buffers of 16 bytes


def ui_mems(s, when):
    """port(mems=...) for the menu at the end of a run: the rows, the
    buffers and the first seven state words, into <tag>.<when>.*"""
    return ((s["stems_rows"], ROW_LEN * MENU_ROWS, f"{when}.rows"),
            (s["stems_ui_bufs"], UI_BUFS, f"{when}.bufs"),
            (s["stems_state"], 28, f"{when}.state"))


def ui_step(s, frame, tag, when):
    """The same dump as a --step, `frame` frames after the transport start."""
    return f"{frame}:dump:" + ";".join(f"0x{a:x},{n}={run_path(tag, name)}" for a, n, name in ui_mems(s, when))


def ui_read(s, tag, when):
    """(the eleven rows' texts, the seven state words) from a ui_mems or
    ui_step dump: a label pointing into the buffers is read from the dump,
    any other from the linked runtime (the fixed strings never change).
    (None, None) when the dump is missing."""
    paths = [run_path(tag, f"{when}.{x}") for x in ("rows", "bufs", "state")]
    if not all(p.exists() for p in paths):
        return None, None
    rows, bufs, st = (p.read_bytes() for p in paths)
    texts = []
    for k in range(MENU_ROWS):
        ptr = int.from_bytes(rows[ROW_LEN * k:ROW_LEN * k + 4], "big")
        b0 = s["stems_ui_bufs"]
        src = bufs[ptr - b0:] if b0 <= ptr < b0 + UI_BUFS else runtime_at(s, ptr, 32)
        texts.append(src.split(b"\0")[0].decode("latin1"))
    return texts, [int.from_bytes(st[i:i + 4], "big") for i in range(0, 28, 4)]


def mmss(frames):
    """A take's length as the status shows it: whole seconds, mm:ss."""
    t = frames * 16 // 44100
    return f"{t // 60:02d}:{t % 60:02d}"
```
Add the two new runs after `cut()`:
```python
LABEL_STOP, LABEL_FRAMES = 3000, 3400


def labels(s):
    """The labels one take shows, read from memory at frames 100 and 2,900
    and at the end. While it records: STOP, and REC mm:ss with the take's
    whole seconds or one less (the writer task rewrites the line at most a
    pass late), rising from 00:00 to 00:01. After it: REC, DONE mm:ss with
    the take's length, and PEAK n% from the recorder's own peak (one track:
    a 65,536-frame ring)."""
    tag = "labels"
    log, _, _, words, _ = port(s, LABEL_FRAMES, stop_at=LABEL_STOP, tag=tag, dump_blocks=False,
                               steps=[ui_step(s, 100, tag, "a"), ui_step(s, 2900, tag, "b")],
                               mems=ui_mems(s, "end"))
    secs = []
    for when in ("a", "b"):
        t, w = ui_read(s, tag, when)
        if t is None:
            check(f"labels: the frame dump '{when}' exists", False)
            return
        now = w[5] * 16 // 44100
        allowed = {f"REC {mmss(w[5])}", f"REC {(now - 1) // 60:02d}:{(now - 1) % 60:02d}"}
        check(f"labels ({when}): STOP, and REC with the take's seconds", t[0] == "STOP" and t[1] in allowed,
              f"{t[:3]}, {w[5]} frames")
        secs.append(int(t[1][-2:]) if t[1].startswith("REC ") else -1)
    check("labels: the seconds rise while it records", secs[0] == 0 and secs[1] >= 1, f"{secs}")
    t, w = ui_read(s, tag, "end")
    pct = w[6] * 100 // (RING_SIZE_T1 // 64)
    check("labels (end): REC, DONE with the take's length, PEAK from its peak",
          t is not None and w[0] == ST_IDLE and t[:3] == ["REC", f"DONE {mmss(w[5])}", f"PEAK {pct}%"],
          f"{t[:3] if t else None}, {w[5] if w else None} frames, peak {w[6] if w else None}")


def nocard(s):
    """REC with no card: the status reads NO CARD and nothing else changes
    (IDLE, no task made). Nothing is armed before play; the card-mounted
    word is poked to 0 at frame 30 and the action runs at 31."""
    tag = "nocard"
    zero = ";".join(f"0x{CARD_READY + i:x}=0" for i in range(4))
    port(s, 120, tag=tag, calls_before=(), dump_blocks=False, steps=[f"30:poke:{zero}"],
         calls=((31, s["stems_action"]),), mems=ui_mems(s, "end"))
    t, w = ui_read(s, tag, "end")
    check("nocard: REC shows NO CARD, the state stays IDLE, no task is made",
          t is not None and t[:2] == ["REC", "NO CARD"] and w[0] == ST_IDLE and w[2] == 0,
          f"{t[:2] if t else None}, state {w[0] if w else None}, task {w[2] if w else None}")
```
In `exists()`, add `mems=ui_mems(s, "end")` to its `port()` call and, at its end:
```python
    t, _ = ui_read(s, "exists", "end")
    check("exists: the status names the refusal", t is not None and t[:2] == ["REC", "SAME MINUTE"],
          f"{t[:2] if t else None}")
```
In `overflow()`, add `steps=[ui_step(s, OVERFLOW_FRAMES - 210, "overflow", "pre")]` (after the task's IDLE, measured about frame 5,300, and before the re-arm), make its `mems` `ui_mems(s, "end") + ((s["stems_peak"], 4, "peak"),)`, and add a call of the action at frame 1000, inside the task's long FINISHING (the Review Focus's REC while saving): `calls=((1000, s["stems_action"]), (OVERFLOW_FRAMES - 200, s["stems_action"]))`. Then:
```python
    check("overflow: REC while it saved changed nothing",
          states == [ST_ARMED, ST_RECORDING, ST_FINISHING, ST_IDLE, ST_ARMED], f"state writes {states}")
    t, _ = ui_read(s, "overflow", "pre")
    check("overflow: the status names the full ring", t is not None and t[:2] == ["REC", "RING FULL"],
          f"{t[:2] if t else None}")
    t, _ = ui_read(s, "overflow", "end")
    check("overflow: the re-arm shows CANCEL, ARMED and PEAK 0%",
          t is not None and t[:3] == ["CANCEL", "ARMED", "PEAK 0%"], f"{t[:3] if t else None}")
```
In `cap()`, add `mems=ui_mems(s, "end")` and:
```python
    t, _ = ui_read(s, "cap", "end")
    check("cap: the status reads DONE 60:00", t is not None and t[:2] == ["REC", "DONE 60:00"],
          f"{t[:2] if t else None}")
```
Add `("labels", labels), ("nocard", nocard)` to `runs` after `("cut", cut)`, and `stems_took`, `stems_ui_bufs` checks to `main()` after the `stems_peak` one:
```python
    check("the menu's words are in the runtime: stems_took 0, the buffers",
          "stems_took" in s and runtime_long(s, "stems_took") == 0 and "stems_ui_bufs" in s)
```

- [ ] **Step 2: Run them to see them fail**

Run: `bash .superpowers/v2/sync-p3.sh && bash .superpowers/v2/wslrun-3 p3-ui-red env STEMS_TEMPLATE="/home/yvez/stemrec3/out/projects/Ultimate FX 1.5.3" .venv/bin/python3 tools/verify/verify_stems.py stems --only=labels,nocard,cap`
Expected: `[FAIL] the menu's words are in the runtime` and a `KeyError: 'stems_ui_bufs'` from the first run: the red.

- [ ] **Step 3: The UI words, and the action's labels**

In `stems.s`, after `stems_probe_res: .space 28`:
```asm
        .global stems_took, stems_ui_bufs
stems_took:      .long   0          | a take ended since the last arm: IDLE shows its result
ui_key:          .long   -1         | what the labels last showed, packed (stems_ui)
stems_ui_bufs:                      | two buffers for each formatted line
stat_buf0:       .space  16
stat_buf1:       .space  16
peak_buf0:       .space  16
peak_buf1:       .space  16
```
With the strings, after `trk8_off`:
```asm
fmt_rec:        .asciz  "REC %02d:%02d"
fmt_done:       .asciz  "DONE %02d:%02d"
fmt_peak:       .asciz  "PEAK %d%s"         | "%" as an argument: %% is untested in the stock sprintf
pct_sign:       .asciz  "%"
```
In `stems_action`, the no-card test becomes `beq.w .La_nocard`; the create failure `beq.w .La_notask`; the IDLE branch gains `clr.l stems_took` after `clr.l stems_status`; and the end becomes:
```asm
.La_set:
        move.l  %d1,stems_state
.La_unmask:
        move.w  %d2,%sr
        bsr.w   stems_ui_state      | row 1 and the status, at once
.La_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts
.La_nocard:                         | no card: say so, and change nothing else
        lea     lbl_nocard,%a0
        move.l  %a0,stems_rows+ROW_LEN
        bra.s   .La_out
.La_notask:                         | the task couldn't be made: stay IDLE, say so
        lea     err_task,%a0
        move.l  %a0,stems_rows+ROW_LEN
        bra.s   .La_out

| ---- row 1 and the status from the state, at once (the actions) ---------
| Fixed strings only, in the UI task. The action never leaves the state
| RECORDING (the hook makes it), so st_by_state's RECORDING entry is 0: the
| task's line, left alone. Arming also shows a new take's PEAK 0%.
stems_ui_state:
        move.l  stems_state,%d0
        lea     rec_by_state,%a0
        move.l  (%a0,%d0.l*4),%d1
        move.l  %d1,stems_rows
        lea     st_by_state,%a0
        move.l  (%a0,%d0.l*4),%d1
        beq.s   .Lv_peak
        move.l  %d1,stems_rows+ROW_LEN
.Lv_peak:
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .Lv_out
        lea     lbl_peak0,%a0
        move.l  %a0,stems_rows+2*ROW_LEN
.Lv_out:
        rts
```

- [ ] **Step 4: The task's labels**

Before `| ---- the name: YYMMDD-HHMM`:
```asm
| ---- the labels, from the task (every pass) -----------------------------
| Row 1, the status and PEAK from the state. A line is rewritten only when
| what it shows changes: the state, whether a take has ended, the error,
| the take's whole seconds and the PEAK percent, packed into ui_key. A
| number is formatted into the buffer its row isn't showing, and the row's
| label pointer then switches. NO CARD and TASK FAILED change nothing in
| the key, so they stay until the next change.
stems_ui:
        lea     -28(%sp),%sp
        movem.l %d2-%d6/%a2-%a3,(%sp)
        move.l  stems_state,%d2             | d2: the state
        move.l  stems_frames,%d3
        lsl.l   #4,%d3                      | 16 samples a frame
        move.l  #44100,%d0
        divu.l  %d0,%d3                     | d3: whole seconds
        moveq   #0,%d4                      | d4: PEAK percent, 0 before any take
        move.l  stems_rframes,%d0
        beq.s   .Lu_pct
        move.l  stems_peak,%d4
        moveq   #100,%d1
        mulu.l  %d1,%d4
        divu.l  %d0,%d4
.Lu_pct:
        move.l  %d3,%d5                     | d5: secs<<16 | pct<<8 | status<<3 | took<<2 | state
        moveq   #16,%d0
        lsl.l   %d0,%d5
        move.l  %d4,%d0
        lsl.l   #8,%d0
        or.l    %d0,%d5
        move.l  stems_status,%d0
        lsl.l   #3,%d0
        or.l    %d0,%d5
        move.l  stems_took,%d0
        lsl.l   #2,%d0
        or.l    %d0,%d5
        or.l    %d2,%d5
        cmp.l   ui_key,%d5
        beq.w   .Lu_out
        move.l  %d5,ui_key
        lea     rec_by_state,%a0            | row 1
        move.l  (%a0,%d2.l*4),%d0
        move.l  %d0,stems_rows
        moveq   #ST_RECORDING,%d0           | the status
        cmp.l   %d0,%d2
        beq.s   .Lu_rec
        tst.l   %d2
        bne.s   .Lu_fixed                   | ARMED, SAVING
        tst.l   stems_took
        beq.s   .Lu_fixed                   | IDLE, no take since the arm: READY
        move.l  stems_status,%d0
        beq.s   .Lu_done
        lea     err_names,%a0               | IDLE after a take that failed: its error
        move.l  (%a0,%d0.l*4),%d0
        bra.s   .Lu_stat
.Lu_fixed:
        lea     st_by_state,%a0
        move.l  (%a0,%d2.l*4),%d0
        bra.s   .Lu_stat
.Lu_rec:
        lea     fmt_rec,%a3
        bra.s   .Lu_time
.Lu_done:
        lea     fmt_done,%a3
.Lu_time:
        lea     stat_buf0,%a2               | the buffer the row isn't showing
        cmpa.l  stems_rows+ROW_LEN,%a2
        bne.s   .Lu_sbuf
        lea     stat_buf1,%a2
.Lu_sbuf:
        move.l  %d3,%d6
        moveq   #60,%d1
        divu.l  %d1,%d6                     | minutes
        move.l  %d6,%d0
        mulu.l  %d1,%d0
        move.l  %d3,%d1
        sub.l   %d0,%d1                     | seconds
        move.l  %d1,-(%sp)
        move.l  %d6,-(%sp)
        move.l  %a3,-(%sp)
        move.l  %a2,-(%sp)
        jsr     SPRINTF
        lea     16(%sp),%sp
        move.l  %a2,%d0
.Lu_stat:
        move.l  %d0,stems_rows+ROW_LEN
        lea     peak_buf0,%a2               | PEAK, formatted with every change
        cmpa.l  stems_rows+2*ROW_LEN,%a2
        bne.s   .Lu_pbuf
        lea     peak_buf1,%a2
.Lu_pbuf:
        pea     pct_sign
        move.l  %d4,-(%sp)
        pea     fmt_peak
        move.l  %a2,-(%sp)
        jsr     SPRINTF
        lea     16(%sp),%sp
        move.l  %a2,stems_rows+2*ROW_LEN
.Lu_out:
        movem.l (%sp),%d2-%d6/%a2-%a3
        lea     28(%sp),%sp
        rts
```
In `stems_task`, after `addq.l #8,%sp` (after `K_DELAY`): `bsr.w stems_ui              | the menu's labels, every pass`. At `.Lt_idle` and `.Lt_drop`, before `clr.l stems_state`:
```asm
        moveq   #1,%d0
        move.l  %d0,stems_took      | the take ended: IDLE shows its result
```
and make both following `bra.s .Lt_loop` a `bra.w .Lt_loop`.

- [ ] **Step 5: Run the checks to see them pass**

Run: `bash .superpowers/v2/sync-p3.sh && bash .superpowers/v2/wslrun-3 p3-ui-green env STEMS_TEMPLATE="/home/yvez/stemrec3/out/projects/Ultimate FX 1.5.3" .venv/bin/python3 tools/verify/verify_stems.py stems --only=full,labels,nocard,exists,overflow,cap`
Expected: every line PASS, exit 0 (`exists` needs `full`'s card, so both run). A label check that fails is read against the dump's words before any change; disassemble a surprise before editing code.

- [ ] **Step 6: The whole verifier through Sam's runner**

Run: `bash .superpowers/v2/wslrun-3 p3-ui-gates env STEMS_TEMPLATE="/home/yvez/stemrec3/out/projects/Ultimate FX 1.5.3" make check-remix-gates REMIX=stems JOBS=2`
Expected: `every gate of stems passed`; `gate:verify_stems` 0 FAIL, 0 SKIP, and every line of Task 1's run still present with its value (the labels and nocard lines added). A value that moved is a finding: the task now runs `stems_ui` every pass, so `cardfail`'s poll count may move; explain it (the writer's per-pass instructions) before accepting it.

- [ ] **Step 7: Commit**

```bash
git add modules/stems/stems.s tools/verify/verify_stems.py
git commit -m "stems: the labels that change -- the actions switch fixed strings at once, the writer task formats REC mm:ss, DONE mm:ss and PEAK into the buffer not showing; verify_stems reads them from memory mid-take and after (labels, nocard, exists, overflow, cap)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The gate on both panels

**Files:**
- Create: `tools/verify/verify_stems_menu.py`
- Modify: `modules/stems/manifest.py` (the gate)

**Interfaces:**
- Consumes: `stems_panel.MenuPort`, `diff_box`, `MENU_FOCUS`; `verify_stems.check`, `syms`, `fixtures`, `FIXTURE`, `IMAGE`, `take_files`, `runtime_at`, `ROW_LEN`, `MENU_ROWS`, `ROW_TRK0`, `ST_*`; Task 2's keys for entering and leaving a list (YES and NO unless Task 2 recorded otherwise).
- Produces: `Gate("tools/verify/verify_stems_menu.py", venv=True)` in STEM REC's manifest.

- [ ] **Step 1: Write the gate**

`tools/verify/verify_stems_menu.py`:
```python
#!/usr/bin/env python3
"""STEMS in MAIN MENU, key by key under the port, on both panels.

    python3 tools/verify/verify_stems_menu.py [remix]      (default: stems)

Builds the remix and the fixtures (STEMS_TEMPLATE), then boots the image
twice under `ot_emu --interactive` on a copy of the one-track fixture card:
as an MKII (MAIN MENU = PROJ) and as an MKI (FUNC+MIXER). Each boot:
- the cursor walks the five categories, STEMS fifth;
- SYSTEM opens and the cursor reaches OS UPGRADE, the recovery path; ENTER
  is never pressed there;
- STEMS opens on REC; DOWN lands on T1 and UP on REC, the status and PEAK
  rows skipped both ways; DOWN reaches T8;
- every track row turned off in turn leaves T8 on (the last track stays);
  T3 off, then every other track on again;
- REC arms (CANCEL, ARMED) and cancels (REC, READY), then arms;
- with the menu closed, PLAY; the menu reopened on STEMS shows STOP and
  REC mm:ss, which changes with no key; T3 is locked;
- with the menu closed, STOP; the take ends DONE, and its folder holds
  seven files, T3's missing;
- every text the module can show, drawn in the status row, ends left of
  the pane's clip edge, and STEMS left of the root column's.
A PNG of the screen at each step goes to out/stems_runs/menu-<model>-*.png.
Pass or fail comes from memory, never from a picture.

What it cannot see: the unit's key timing, its card speed while the menu
is open, and the MKII's hardware (flash A)."""
import json
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_stems as vs  # noqa: E402
from stems_panel import MENU_FOCUS, MenuPort, diff_box  # noqa: E402

ROOT_DESC, SYSTEM_DESC, SEL = 0x400cbd8c, 0x400cbd1c, 0x0c
OS_UPGRADE = 1                  # SYSTEM's row 1 (MAINMENU.md 2)
ENTER, BACK = "yes", "no"       # Task 2 measured which keys enter and leave a list
WORK = pathlib.Path("out/stems_runs")
ERRS = ["RING FULL", "PATH FAILED", "OPEN FAILED", "SAME MINUTE", "WRITE FAILED",
        "SEEK FAILED", "CLOSE FAILED", "TASK FAILED"]
TEXTS = (["REC", "CANCEL", "STOP", "SAVING", "READY", "ARMED", "NO CARD", "PEAK 0%", "PEAK 100%",
          "REC 60:00", "DONE 60:00"] + ERRS + [f"T{k} [{m}]" for k in range(1, 9) for m in "X "])


def texts(p, s):
    return [p.cstr(p.long(s["stems_rows"] + vs.ROW_LEN * k)) for k in range(vs.MENU_ROWS)]


def box_of(p, label_at, scratch, text):
    p.poke(scratch, text.encode("latin1") + b"\0")
    p.poke(label_at, scratch.to_bytes(4, "big"))
    p.run(500)
    return p.screen()


def widths(p, s, model):
    """Every text in the status row, and STEMS in the root column, against
    24 Ws: each must end left of the clip edge. The label pointers are put
    back after."""
    scratch = s["stems_fpath"]
    for label_at, pane, items in ((s["stems_rows"] + vs.ROW_LEN, "the list pane", TEXTS),
                                  (p.long(ROOT_DESC + 0x18) + vs.ROW_LEN * 4, "the root column", ["STEMS"])):
        keep = p.long(label_at)
        empty = box_of(p, label_at, scratch, "")
        clip = diff_box(empty, box_of(p, label_at, scratch, "W" * 24))
        over = []
        for t in items:
            b = diff_box(empty, box_of(p, label_at, scratch, t))
            if clip is None or b is None or b[1] >= clip[1]:
                over.append((t, b[1] if b else None))
        p.poke(label_at, keep.to_bytes(4, "big"))
        p.run(300)
        vs.check(f"{model}: every text ends inside {pane}", clip is not None and not over,
                 f"clip {clip[1] if clip else None}, over {over}")


def walk(model, s, fx):
    card = WORK / f"menu-{model}.img"
    shutil.copyfile(fx["card"], card)
    lst = s["stems_list"]
    with MenuPort(vs.IMAGE, card, fx["set"], fx["project"], model == "mkii",
                  log_path=WORK / f"menu-{model}.log") as p:
        def shot(name):
            p.png(WORK / f"menu-{model}-{name}.png")

        def sel(desc):
            return p.long(desc + SEL)

        p.settle()
        p.open_menu()
        shot("root")
        seen = [sel(ROOT_DESC)]
        for _ in range(4):
            p.press("down")
            seen.append(sel(ROOT_DESC))
        shot("stems")
        vs.check(f"{model}: MAIN MENU opens on the root and the cursor walks five categories",
                 p.long(MENU_FOCUS) == ROOT_DESC and seen == [0, 1, 2, 3, 4], f"{seen}")
        for _ in range(3):
            p.press("up")
        p.press(ENTER)
        p.press("down")
        shot("os-upgrade")
        vs.check(f"{model}: SYSTEM opens and the cursor reaches OS UPGRADE",
                 p.long(MENU_FOCUS) == SYSTEM_DESC and sel(SYSTEM_DESC) == OS_UPGRADE,
                 f"focus {p.long(MENU_FOCUS):#x}, selection {sel(SYSTEM_DESC)}")
        p.press(BACK)
        for _ in range(3):
            p.press("down")
        p.press(ENTER)
        vs.check(f"{model}: STEMS opens on REC", p.long(MENU_FOCUS) == lst and sel(lst) == 0,
                 f"focus {p.long(MENU_FOCUS):#x}, selection {sel(lst)}")
        p.press("down")
        down = sel(lst)
        p.press("up")
        up = sel(lst)
        vs.check(f"{model}: DOWN from REC lands on T1 and UP from T1 on REC", (down, up) == (3, 0),
                 f"{(down, up)}")
        walked = []
        for _ in range(8):
            p.press("down")
            walked.append(sel(lst))
        vs.check(f"{model}: DOWN reaches T8", walked[:8] == list(range(3, 11)), f"{walked}")
        for _ in range(7):
            p.press("up")                               # T8 -> T1
        for k in range(8):                              # every track off in turn, T1 to T8
            p.press(ENTER)
            if k < 7:
                p.press("down")                         # no DOWN past T8: it might wrap
        left = p.long(s["stems_tracks"]) & 0xFF
        vs.check(f"{model}: turning every track off leaves the last one on", left == 0x80, f"mask {left:#04x}")
        shot("tracks-off")
        for _ in range(7):
            p.press("up")                               # T8 -> T1; then T1 .. T7 on again, T3 stays off
        for k in range(7):
            if k != 2:
                p.press(ENTER)
            p.press("down")
        t = texts(p, s)
        mask = p.long(s["stems_tracks"]) & 0xFF
        vs.check(f"{model}: T3 off, every other track on, the rows say so",
                 mask == 0xFB and t[3:11] == [f"T{k} [{' ' if k == 3 else 'X'}]" for k in range(1, 9)],
                 f"mask {mask:#04x}, {t[3:11]}")
        for _ in range(8):
            p.press("up")                               # REC
        p.press(ENTER)
        a = texts(p, s)[:2] + [p.long(s["stems_state"])]
        p.press(ENTER)
        c = texts(p, s)[:2] + [p.long(s["stems_state"])]
        p.press(ENTER)
        shot("armed")
        vs.check(f"{model}: REC arms and cancels", a == ["CANCEL", "ARMED", vs.ST_ARMED]
                 and c == ["REC", "READY", vs.ST_IDLE] and p.long(s["stems_state"]) == vs.ST_ARMED,
                 f"{a}, {c}")
        p.press(BACK)
        p.press(BACK)
        p.press("play", settle=1500)
        p.open_menu()
        t0 = texts(p, s)
        before = p.screen()
        shot("recording")
        p.run(2500)
        t1 = texts(p, s)
        after = p.screen()
        vs.check(f"{model}: reopened on STEMS: STOP and REC mm:ss, redrawn with no key",
                 p.long(MENU_FOCUS) == lst and t0[0] == "STOP" and t0[1].startswith("REC ")
                 and t1[1] != t0[1] and diff_box(before, after) is not None, f"{t0[:2]} -> {t1[:2]}")
        for _ in range(3):
            p.press("down")                             # 0 -> 3 -> 4 -> 5: T3
        p.press(ENTER)
        vs.check(f"{model}: T3 is locked while it records",
                 p.long(s["stems_tracks"]) & 0xFF == 0xFB and texts(p, s)[5] == "T3 [ ]")
        p.press(BACK)
        p.press(BACK)
        p.press("stop", settle=500)
        for _ in range(60):
            if p.long(s["stems_state"]) == vs.ST_IDLE:
                break
            p.run(500)
        p.open_menu()
        t = texts(p, s)
        shot("done")
        vs.check(f"{model}: after STOP: IDLE, REC and DONE mm:ss",
                 p.long(s["stems_state"]) == vs.ST_IDLE and t[0] == "REC" and t[1].startswith("DONE "),
                 f"state {p.long(s['stems_state'])}, {t[:3]}")
        for _ in range(3):
            p.press("up")                               # the cursor back to REC, rows 0-6 showing
        widths(p, s, model)
        p.card_flush()
    names = [n.upper() for n, _ in vs.take_files(str(card))]
    vs.check(f"{model}: the take holds seven files, T3's missing",
             names == [f"T{k}.WAV" for k in (1, 2, 4, 5, 6, 7, 8)], f"{names}")


def main():
    from remix import registry
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    name = args[0] if args else "stems"
    if "STEM REC" not in registry.remix(name).modules:
        print(f"  [ -- ] {name} does not carry STEM REC -- nothing to check")
        return 0
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], capture_output=True, text=True, env=env)
    if r.returncode:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    if not vs.EMU.exists():
        print("  [SKIP] the menu under the port: build the port (make emu-cf)")
        return 0
    if not vs.TEMPLATE.is_dir():
        print(f"  [SKIP] the menu under the port: no project template at {vs.TEMPLATE} (STEMS_TEMPLATE=<dir>)")
        return 0
    if not vs.fixtures():
        return 1
    s = vs.syms()
    fx = json.loads(vs.FIXTURE.read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    for model in ("mkii", "mki"):
        walk(model, s, fx)
    return 1 if vs.fails else 0


if __name__ == "__main__":
    sys.exit(main())
```
If Task 2 chose the short error names, `ERRS` holds them. If Task 2 found other keys enter and leave a list, `ENTER` and `BACK` name them. The cursor positions the walk assumes: T1 to T7 on again ends on T8 (row 10), and eight UPs from there reach REC (rows 9 to 3, then 0).

- [ ] **Step 2: Run it before it's declared**

Run: `bash .superpowers/v2/sync-p3.sh && bash .superpowers/v2/wslrun-3 p3-menu-gate env STEMS_TEMPLATE="/home/yvez/stemrec3/out/projects/Ultimate FX 1.5.3" .venv/bin/python3 tools/verify/verify_stems_menu.py stems`
Expected: every line PASS on `mkii` and on `mki`, exit 0, and the PNGs `out/stems_runs/menu-mkii-*.png` and `menu-mki-*.png`. Look at `menu-mkii-stems.png` and `menu-mki-recording.png` before going on: the icon and the rows must read as the spec says. A failure is read against the screen and the words first; the key sequence is the likeliest fault, the module the least.

- [ ] **Step 3: Declare it**

In `modules/stems/manifest.py`, `gates=`:
```python
    gates=(Gate("tools/verify/verify_card_reader.py", remix_arg=False, venv=True),
           Gate("tools/verify/verify_stems.py", venv=True),
           Gate("tools/verify/verify_stems_menu.py", venv=True)),
```
and extend the comment above it: "verify_stems_menu boots the image twice (MKII, MKI) under `ot_emu --interactive` and presses the menu's keys; it SKIPs by name without the port or the template."
Run: `bash .superpowers/v2/sync-p3.sh && bash .superpowers/v2/wslrun-3 p3-gates2 env STEMS_TEMPLATE="/home/yvez/stemrec3/out/projects/Ultimate FX 1.5.3" make check-remix-gates REMIX=stems JOBS=2`
Expected: `every gate of stems passed`, `gate:verify_stems_menu` among them.

- [ ] **Step 4: Commit**

```bash
git add tools/verify/verify_stems_menu.py modules/stems/manifest.py
git commit -m "verify_stems_menu: STEMS key by key on the MKII and MKI panels -- five categories, SYSTEM to OS UPGRADE, the headings skipped, the last track kept, arm and cancel, a take with T3 off and the menu reopened live, DONE, seven files, every text inside its pane" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The records

**Files:**
- Modify: `docs/firmware/STEM_REC.md` (section 16), `docs/firmware/MAINMENU.md` (section 5), `modules/stems/README.md`, `remixes/stems/README.md`, `docs/remixer/FAILURE_MODES.md`, `README.md` and `docs/remixes/README.md` (by `make docs`)

- [ ] **Step 1: STEM_REC.md section 16**

16.2 "The category as built": the root grown to five, the list and its rows, the icon, the label switching, who writes which line, the key `ui_key`; the Task 4 and Task 5 runs with their logs and every value measured; any value that moved, explained. 16.3 "What the gate can't see": the unit's key timing, the card while the menu is open, the MKII hardware.

- [ ] **Step 2: MAINMENU.md section 5**

Add: a fifth category runs under the port on the MKII and the MKI (STEMS, `verify_stems_menu`), and a list whose rows' labels are rewritten live (`stems.s`), with a pointer to STEM_REC.md 16.

- [ ] **Step 3: The READMEs and the failure register**

`modules/stems/README.md`: the first line says MAIN MENU › STEMS; "How to use it" becomes: open MAIN MENU (MAIN MENU key on the MKII, FUNC+MIXER on the MKI) and go to STEMS; REC arms (or starts, if playing); the status line and PEAK; T1 to T8 and their lock; the take stops with the sequencer, STOP, 60 minutes or a full ring; wait for DONE before pulling the card (replacing "wait at least 5 seconds"). "Limits": drop "There's no menu to pick tracks yet" and "No screen feedback, and no error report on the unit"; add "The track choices reset to all eight at every boot". Add `verify_stems_menu` to the Status list. `remixes/stems/README.md`: MAIN MENU › STEMS. `docs/remixer/FAILURE_MODES.md`, "The unit hangs when STEM REC is selected": the symptom names MAIN MENU › STEMS › REC.

- [ ] **Step 4: Render and check the docs**

Run: `bash .superpowers/v2/sync-p3.sh && bash .superpowers/v2/wslrun-3 p3-docs3 bash -c "make docs && python3 tools/verify/verify_docs.py && git status --porcelain"`
Expected: `0 problems`; `make docs` changed only the stems rows of `README.md` and `docs/remixes/README.md` (copy them back to the Windows worktree if the sync doesn't carry them: they are generated from the manifest's `doc`).

- [ ] **Step 5: Commit**

```bash
git add docs/firmware/STEM_REC.md docs/firmware/MAINMENU.md modules/stems/README.md remixes/stems/README.md docs/remixer/FAILURE_MODES.md README.md docs/remixes/README.md
git commit -m "STEM_REC 16, MAINMENU 5, READMEs: STEMS in MAIN MENU -- how to use it, what the gate saw on both panels, what it can't see" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Sam's procedure, on the whole branch

**Files:**
- Modify (local): the ledger, with each command and its result

- [ ] **Step 1: Up to date with upstream**

```bash
git fetch origin
git log --oneline -1 origin/main
```
If `origin/main` moved past `f331c30`, merge it (as Tasks 3u and 3u2 did: a merge keeps the ledger's commit ranges), resolve, and commit the merge with each conflict's resolution in its message. Then sync.

- [ ] **Step 2: The list**

Run: `bash .superpowers/v2/wslrun-3 p3-reach make reach BASE=<origin/main's commit>`
Expected: the gates the branch reaches, `verify_stems_menu` among STEM REC's; `make accept REMIX=stems` listed.

- [ ] **Step 3: The baseline for refhash**

The branch changes the build's inputs (`ledger.py`, `schema.py`, `platform_build.py`, `build_bus.py` since piece 1), so refhash compares against upstream's own tree. In a clean worktree of upstream's commit in WSL (`git -C /home/yvez/stemrec2 worktree add --detach /home/yvez/stemrec-base <commit>`, with the `vendor`/`.venv` symlinks, the stock slice and the submodules, as in Task 1 Step 2, without the port): run `scripts/refhash.sh save`, then copy the baseline across with `mkdir -p /home/yvez/stemrec3/out/refhash && cp -r /home/yvez/stemrec-base/out/refhash/baseline /home/yvez/stemrec3/out/refhash/` (`refhash.sh check` reads `out/refhash/baseline/manifest.txt` of the tree it runs in).

- [ ] **Step 4: Run every gate**

Run: `bash .superpowers/v2/wslrun-3 p3-reach-run env STRESS_SOURCE="/home/yvez/stemrec3/out/projects/Ultimate FX 1.5.3" STEMS_TEMPLATE="/home/yvez/stemrec3/out/projects/Ultimate FX 1.5.3" make reach BASE=<commit> RUN=1 KEEP=1 JOBS=2`
Expected: the table at the end, every line `ok`. A red line is read before it is believed: a USB gate that fails under load is rerun alone (`docs/remixer/TESTING.md` section 9).

- [ ] **Step 5: Record it**

In the ledger: each command, its log path, and its result. A draft PR body in the ledger (not pushed, not opened): the summary, the gates and results as TESTING.md section 10 asks, and "hardware_validated: false". In `docs/remixes/BUILDING.md` 1a, if `make accept REMIX=stems` passed: "`make accept` passes on this route with the bare-metal toolchain (measured <date>)", replacing the sentence that says it doesn't.

- [ ] **Step 6: Commit**

```bash
git add docs/remixes/BUILDING.md
git commit -m "BUILDING 1a: make accept passes on the Linux route with the bare-metal toolchain (stems, measured)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
(Only if Step 5 changed it.)
