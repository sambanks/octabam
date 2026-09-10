# STEM REC POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A flashable octabam remix, `stems`, whose MAIN MENU > CONTROL > STEM REC row records track 1 to the card as a 16-bit stereo WAV while the sequencer plays, for at most 15 seconds.

**Architecture:** One DRAM unit (`modules/stems/stems.s`) holds everything: a menu action, a per-frame hook detoured in at `0x40004b12` that packs T1's post-FX2 read-back block into a 4 MiB ring, and an RTOS task of its own that drains the ring to the card through the stock buffered file API. The ring and the task's stack sit at the free top of the platform's existing 10 MiB arena reserve, which needs one small build change (`schema.DramRegion`). Everything is proven under the ColdFire port (`out/emu/ot_emu`) before the one flash.

**Tech Stack:** GNU as for ColdFire (`m68k-elf-as -mcpu=5407`), Python 3 (the build, the verifiers), C++17 (the ColdFire port), WSL Ubuntu.

**Spec:** `docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md`. Read it first; this plan argues from it.

## Global Constraints

- T1 only, stereo, 16-bit, 44,100 Hz. `MAX_FRAMES = 41344` (15.0 s). Ring 4 MiB (`0x400000`). Stack 8 KB (`0x2000`). Task priority 1. File buffer 512 bytes.
- File: `<set>/AUDIO/YYMMDD-HHMM/T1.wav`, or `<set>/AUDIO/YYMMDD-HHMM.wav` when no folder routine is found (Task 7). No seconds.
- The interrupt code calls nothing and uses no RTOS service. The task uses absolute paths only and never changes directory. The task never uses stock's global I/O buffer `0x460263e0`.
- **Never an Elektron byte in the repo.** Stock rows and code are read from `out/raw/section_3_MAIN_OS.bin` at build time, never copied into a source file.
- **Disassemble with `scripts/disasm.sh emac` only, never r2.** Gate first: `scripts/disasm.sh emac 0x40003664 8` must print `msacl`.
- **Measured versus inferred.** Every firmware fact goes into `docs/firmware/STEM_REC.md` with ✅ / 🟡 / ❌ and a falsifier, the image SHA-256 `164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e` in its method line.
- **One commit per finding.** Commit locally. **Never push** (Yves's standing instruction).
- **A change to the build proves it changed nothing:** `scripts/refhash.sh save` before Task 12, `scripts/refhash.sh check` after it.
- `make check REMIX=stems` is the floor. "It assembled" is never evidence.
- Write every document to the Microsoft style guide: short sentences, define terms, no spaced dashes.

## Where the work happens

The Windows clone (`C:\Projects\Octabam`) does not build. The build runs in WSL. Its old tree `~/octabam` is on the 3 Sep `main` and must not be disturbed. Task 0 makes a **fresh clone at `~/octabam-stems`** on branch `stem-rec-poc`, and that clone is the working tree for this whole plan:

- Edit files through `\\wsl$\Ubuntu\home\yvez\octabam-stems\...` (the files stay LF).
- Run commands through a script in the scratchpad, never inline (`$` is mangled by `wsl.exe`):
  `MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash /mnt/c/Users/rosiu/AppData/Local/Temp/claude/<session>/scratchpad/run.sh`
  with `run.sh` starting `cd ~/octabam-stems || exit 1`.
- Commit in `~/octabam-stems`. At the end, the Windows clone fetches the branch from it (Task 18).
- Capture exit codes with `> log 2>&1; echo $?`, never `| tail` (CLAUDE.md).

## File map

| file | what it is | task |
|---|---|---|
| `docs/firmware/STEM_REC.md` | every stock fact the module stands on, with evidence | 2 to 8, 11 |
| `tools/emu/emu_card.py` | + `read_file(image, path)`, a FAT16 reader | 9 |
| `tools/verify/verify_card_reader.py` | round-trip test of the reader | 9 |
| `tools/emu/ot_emu/{main.cpp,card.h,card.cpp}` | + `--card-out`, `--call-before-play`, `--at`, `--card-fail-after` | 10 |
| `tools/remix/schema.py` | + `DramRegion`, `Module.dram_regions` | 12 |
| `tools/remix/platform_build.py` | places regions at the reserve's top, refuses a misfit | 12 |
| `tools/build/build_bus.py` | collects regions, prints them | 12 |
| `tools/remix/ledger.py`, `tools/remix/selftest.py` | refuses one region symbol claimed twice | 12 |
| `modules/stems/manifest.py` | the module: unit, detour, table, poke, regions | 13 |
| `modules/stems/stems.s` | the unit: action, hook, task, writer | 13 to 16 |
| `modules/stems/README.md` | what it is, how to use it, what is measured | 17 |
| `remixes/stems.py` | the remix: STEM REC alone | 13 |
| `tools/verify/verify_stems.py` | static checks, then the port runs | 13 to 16 |
| `Makefile` | `verify` runs `verify_stems.py` | 13 |

---

## Phase 0: a build that works

### Task 0: The WSL working tree and the m68k toolchain

`docs/WSL.md` "Limits" says `make check` is unverified on WSL since 9 Sep: the build needs `m68k-elf-as`, `ld`, `objcopy`, `nm` (and `m68k-elf-gcc` for Octakit's runtime), and the apt route has them only as `m68k-linux-gnu-*`. This task finds out whether the apt binaries satisfy the build, using the authors' own oracles as the judge.

**Files:**
- Modify: `docs/WSL.md` (the "Limits" section, with the result)

- [ ] **Step 1: Ask Yves before touching WSL.** This installs apt packages and writes symlinks into `/usr/local/bin`. It does not touch `~/octabam`. Proceed only on his yes.

- [ ] **Step 2: Clone and stage the stock image.**

```bash
git clone /mnt/c/Projects/Octabam ~/octabam-stems
cd ~/octabam-stems
git checkout stem-rec-poc
git config user.name "Yves Rosius"; git config user.email "rosiusyves@gmail.com"
mkdir -p out/raw
cp ~/octabam/out/raw/section_3_MAIN_OS.bin out/raw/
sha256sum out/raw/section_3_MAIN_OS.bin
```

Expected: `164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e`. Any other hash: stop.

- [ ] **Step 3: Install the cross tools and name them the way the build asks.**

```bash
sudo apt install -y binutils-m68k-linux-gnu gcc-m68k-linux-gnu
for t in as ld objcopy nm objdump gcc; do
  sudo ln -sf "$(command -v m68k-linux-gnu-$t)" /usr/local/bin/m68k-elf-$t
done
m68k-elf-as --version | head -1
```

- [ ] **Step 4: Run setup, skipping only the Homebrew step.** Read `scripts/setup.sh` first. If it stops at `brew install`, run its remaining steps by hand (the vendored builds and `uv sync`), and write down exactly which. Then `make emu-cf` to build the ColdFire port.

- [ ] **Step 5: The oracles judge the toolchain.**

```bash
make check REMIX=hello-dram  > /tmp/c1.log 2>&1; echo "hello-dram $?"
make check REMIX=midi-scenes > /tmp/c2.log 2>&1; echo "midi-scenes $?"
make check REMIX=octakit     > /tmp/c3.log 2>&1; echo "octakit $?"
grep -n "FAIL\|refusing\|drift" /tmp/c1.log /tmp/c2.log /tmp/c3.log
```

Expected: three `0`, no `FAIL`. `midi-scenes` re-links every unit at its author's address and compares with his bytes, and `octakit` compares with her `output.os`, so a pass means the apt tools produce the authors' bytes. A drift failure means they do not: stop and report to Yves. Do not patch around it.

- [ ] **Step 6: Record the result in `docs/WSL.md`.** Replace the "Limits" section's "has not been tried" paragraph with what Step 5 measured: the packages, the six symlinks, which setup steps ran by hand, and the three `make check` results. Keep the old claim beside it marked ❌ if it is now wrong.

- [ ] **Step 7: Commit.**

```bash
git add docs/WSL.md
git commit -m "WSL: the apt m68k-linux-gnu tools, linked as m68k-elf-*, pass hello-dram, midi-scenes and octakit's oracles"
```

### Task 1: The bit-identity baseline

- [ ] **Step 1: Save the reference hashes before any build change.**

```bash
scripts/refhash.sh save > /tmp/rh.log 2>&1; echo $?
tail -5 /tmp/rh.log
```

Expected: exit 0 and 26 configurations saved. This is the baseline Task 12 must match. Nothing to commit: refhash keeps its reference outside git (read `scripts/refhash.sh` to confirm where, and write that path in the Task 12 notes).

---

## Phase A: the firmware facts

Every task here reads the image, writes one section of `docs/firmware/STEM_REC.md`, and commits it. Each ends with a line for the `stems.s` header, the **interface** later tasks consume. If a finding contradicts the shape the code in Phase D assumes, stop and revise this plan before writing code.

Start the document in Task 2 with this header:

```markdown
# The stock facts STEM REC stands on

Every address, argument and behaviour the STEM REC module
(`modules/stems/`, design in `docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md`)
relies on, with the evidence for each.

**Method.** Read from `out/raw/section_3_MAIN_OS.bin`, SHA-256
`164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e`, load base
`0x40000400`, with `scripts/disasm.sh emac` (objdump `-m m68k:cfv4e`), never r2.
Confidence markers as in `CHIP.md`: ✅ measured, 🟡 inferred with a
falsifier stated, ❌ retracted.
```

A helper to find every absolute reference to an address, for Tasks 2 to 8:

```bash
# refs.sh ADDR: every offset in the image where ADDR appears as a 32-bit word
python3 - "$1" <<'PY'
import sys
img = open("out/raw/section_3_MAIN_OS.bin", "rb").read()
want = int(sys.argv[1], 16).to_bytes(4, "big")
i = img.find(want)
while i >= 0:
    print(f"0x{0x40000400 + i:08x}")
    i = img.find(want, i + 1)
PY
```

A hit is the operand of an instruction that starts 2 bytes earlier (or 4, for `move.l #imm,abs`). Disassemble 32 bytes before each hit to find the instruction boundary; the stream must decode cleanly from a known instruction start.

### Task 2: The transport word

The lead: `tools/emu/emu_rtos.py` names `TRANSPORT = 0x800065b8`, a longword that goes 0 to 1 when the transport starts (RTOS_FORK §9.4). The hook needs both edges.

**Files:**
- Create: `docs/firmware/STEM_REC.md` (header above, section 1)

- [ ] **Step 1: Find every writer of `0x800065b8`.** Run `refs.sh 0x800065b8` and disassemble each site. Classify each as read, write-1, write-0 or write-other.
- [ ] **Step 2: Confirm the stop edge.** Among the writers, find the store of 0 reached from the STOP key handler `0x4000a1e0` (the per-key table at `0x400d2d54`, index 26). Follow the call chain with `scripts/disasm.sh emac`.
- [ ] **Step 3: Measure it under the port.** Run the Task 11 fixture if it exists yet, otherwise any card with a project:

```bash
out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card <card.img> --set <SET> \
  --project <PROJ> --sequencer --frames 50 --load-ms 20000 --peek 0x800065b8
```

  and read the value after the transport start. (`--peek` prints one word; check its exact syntax in `main.cpp`.)
- [ ] **Step 4: Write section 1, "The transport word".** State the size, the values for stopped and running, every writer by address, and the stop edge's path. Falsifier: a transport stop that leaves the word non-zero.
- [ ] **Step 5: Commit.** `git commit -m "STEM_REC: the transport word 0x800065b8 -- <what was measured>"`

**Interface produced:** `.equ TRANSPORT, 0x800065b8` and the rule the hook uses (`tst.l TRANSPORT`, zero = stopped). If the word is not a long, or stopped is not zero, revise Task 14's hook before writing it.

### Task 3: Which half of the read-back block holds the current frame

The block is `0x80003190 + ping * 0x400` (DSP.md). The per-frame routine `0x400031a0` reads `0x800000e0` into `sp@(44)` at `0x400031d0`.

- [ ] **Step 1: Read `0x400031a0` to where it addresses `0x80003190`.** `scripts/disasm.sh emac 0x400031a0 0x400` and `refs.sh 0x80003190`, `refs.sh 0x80003590`. Write down how the half is computed from `0x800000e0`.
- [ ] **Step 2: Find who flips `0x800000e0`,** and whether the flip comes before or after the frame routine in the interrupt at `0x40004af0..0x40004b1a`. The half the stock routine reads is the one the DMA has finished; that is the half the hook must read.
- [ ] **Step 3: Write section 2, "The read-back half".** Say what the port cannot show: a DMA that completes instantly never tears a half, so a wrong half choice looks correct under the port, one frame late. The static reading is the evidence here.
- [ ] **Step 4: Commit.**

**Interface produced:** `.equ PING, 0x800000e0`, `.equ PING_XOR, 0` or `1`, and the rule `half = (PING ^ PING_XOR) & 1`, byte offset `half * 0x400`. If the stock routine computes the half some other way (for example `PING` already holds `0` or `0x400`), write the exact rule instead, and change the four `.Lh_room` instructions in Task 14 to match.

### Task 4: Creating and starting a task

The lead, read on 10 Sep 2026: `0x400005fc(tcb, entry, prio, stack, size)` builds the first frame, sets `tcb+8 = 0x800068dc + 4*prio`, `tcb+72` = the stack pointer, clears `tcb+76` and `tcb+80`, returns 1. `0x4000063c(tcb)` masks interrupts and updates `0x800068d8`.

- [ ] **Step 1: Find the create sites.** `refs.sh 0x400005fc` gives the `jsr` sites; RTOS_FORK §3 says five more call through a register. Disassemble the `sys` task's creation of the storage task (`0x40061a94` onward, TCB `0x460bcc2c`).
- [ ] **Step 2: Write down the full sequence** stock uses: arguments, what it calls after create, and in what order.
- [ ] **Step 3: Measure the TCB size.** The largest offset any kernel routine touches in a TCB (read `0x4000063c`, the scheduler's `rte` path, and the create routine), rounded up to 4. Cross-check against the gaps between stock TCBs in RTOS_FORK §3's table.
- [ ] **Step 4: Check that priority 1 can hold one more task.** Three tasks already share it, so the ready structure is a list per priority. Confirm from `0x4000063c`.
- [ ] **Step 5: Write section 3, "Creating a task".** Commit.

**Interface produced:**
`.equ K_CREATE, 0x400005fc`, `.equ K_START, <address>` with its argument list, `.equ TCB_SIZE, <bytes>`. Task 15's `stems_task_create` calls exactly this sequence.

### Task 5: The kernel's tick delay

❌ `0x40020c7c` is not a sleep (spec section 6). The task needs the call that blocks the caller for N ticks and lets lower-priority tasks run.

- [ ] **Step 1: Read the three blocking primitives** `0x40000818`, `0x400007a4`, `0x40000d00` (named in `tools/emu/emu_rtos.py` near `KEY_STOP`). For each: arguments, what it waits on, and whether a timeout argument exists.
- [ ] **Step 2: Find a stock task that sleeps periodically.** The key-repeat task `0x4005593c` waits on a counting semaphore (RTOS_FORK §9.1); follow what posts it. A timed wait with a tick count is the call wanted.
- [ ] **Step 3: Measure the tick period.** PIT0 is the tick (RTOS_FORK §3, source 43). Read its reload value where it is programmed, and compute the period at the 132 MHz bus clock (`cfprobe`'s figure, 47,891 ticks per 362.8 µs frame).
- [ ] **Step 4: Write section 4, "Sleeping for N ticks".** Commit.

**Interface produced:** `.equ K_DELAY, <address>` with its argument convention, the tick period in ms, and `.equ TASK_TICKS, <n>` chosen so the task wakes about every 10 ms. At 176,400 B/s a 64 KB chunk fills every 371 ms, so 10 ms is ample and costs little. If the only timed wait is "pend on an event with a timeout", use a private event that nothing posts, and write that sequence here.

### Task 6: The name and the folder path

- [ ] **Step 1: The clock.** Read the name builder `0x400819fc`: how it calls `0x4001c4d8` (argument on the stack or in a register, what `d0` returns) and `0x4001c31c`, and the `sprintf` call with the format at `0x400b77bb`. Check whether `0x4001c4d8` takes any lock (a caller in another task could be mid-transaction).
- [ ] **Step 2: The set folder.** Read the stock save's path build (the caller of `sprintf` with `0x400b3a85`, `%s/AUDIO/%s.wav`, near `0x40084e24`): what fills the first `%s`. Compare with `0x40025230(0, 0)`, which Octakit uses as the project directory prefix on hardware (`persistence.c` line 425: it appends `/kits3a.work`).
- [ ] **Step 3: Confirm the return register** of `0x40025230` (`d0`, `a0` or both) from its own `rts` path.
- [ ] **Step 4: Write section 5, "The name and the path".** Commit.

**Interface produced:**
`.equ CLK_READ, 0x4001c4d8` (stack argument: field index; returns BCD in `d0`), `.equ BCD2BIN, 0x4001c31c`, `.equ NAME_FMT, 0x400b77bb`, `.equ SPRINTF, 0x40013a08`, `.equ PROJ_DIR, 0x40025230` (`(0, 0)`, returns the project directory in `d0`), and the rule "set folder = project directory up to its last `/`". If the stock save uses a different source for the set folder, use that source and change `stems_make_path` in Task 15.

### Task 7: A folder-creation routine (time box: one session)

Stock creates folders: CREATE NEW PROJECT makes `<set>/<project>/`. So a routine exists.

- [ ] **Step 1: Start from the new-project path.** Find the strings the project creation uses (`project.work`, `markers.work`) with a byte search of the image, then their callers, then the call that runs before the first file open in the new folder.
- [ ] **Step 2: Confirm it creates a directory:** it must write a directory entry with attribute `0x10` (read the FAT code it calls, or run it under the port on a scratch card and read the image back with Task 9's reader).
- [ ] **Step 3: Write section 6.** Either the routine, its arguments and return convention, or "not found in one session" with where the search stopped. Commit.

**Interface produced:** `.equ HAVE_MKDIR, 1` and `.equ FS_MKDIR, <address>` with its signature, or `.equ HAVE_MKDIR, 0`. With 0, the file is `<set>/AUDIO/YYMMDD-HHMM.wav` (spec section 2).

### Task 8: The FAT layer's locking, and the card-mounted word

- [ ] **Step 1: The lock.** Read the entries of open `0x40016864` and write `0x400166b8` for a pend on a mutex or semaphore before they touch FAT state. The ATA layer's lock is `0x460bae18` (EMU.md).
- [ ] **Step 2: The card-mounted word.** `0x460d1cb8` reads 1 after the mount (EMU.md). Find its writers with `refs.sh 0x460d1cb8`: its size, and whether a card removal clears it.
- [ ] **Step 3: Write section 7, "Two tasks on one card", and section 8, "Is a card mounted".** If the FAT layer has no lock, say so plainly: the POC proceeds, the risk goes into the flash notes, and the first flash uses a spare card (spec section 8). Commit.

**Interface produced:** `.equ CARD_MOUNTED, 0x460d1cb8` with its size (`tst.l` or `tst.b` in Task 13's action).

---

## Phase B: the instruments

### Task 9: Read a file back out of a FAT16 card image

The port's card is a FAT16 image built by `emu_card.build_image`. Nothing reads one yet.

**Files:**
- Modify: `tools/emu/emu_card.py` (add `read_file` after `build_image`)
- Create: `tools/verify/verify_card_reader.py`

- [ ] **Step 1: Write the failing test.**

```python
#!/usr/bin/env python3
"""The FAT16 reader returns what the builder wrote, byte for byte.

    python3 tools/verify/verify_card_reader.py

The reader is how every STEM REC port run gets its WAV back, so it is held
to the builder that made the image: a tree of files of awkward sizes (0, 1,
one cluster, one cluster + 1, many clusters), a long name and a nested
folder, built, read back and compared.
"""
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import emu_card as ec  # noqa: E402


def main():
    fails = 0
    with tempfile.TemporaryDirectory() as t:
        tree = pathlib.Path(t) / "tree"
        files = {
            "PRESETS/PROJ/project.work": b"",
            "PRESETS/AUDIO/a.wav": b"\x01",
            "PRESETS/AUDIO/Long Name Recording.wav": os.urandom(4096),
            "PRESETS/AUDIO/250910-1432/T1.wav": os.urandom(4097),
            "big.bin": os.urandom(300_000),
        }
        for rel, data in files.items():
            p = tree / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        img = pathlib.Path(t) / "card.img"
        img.write_bytes(ec.build_image(str(tree), 16))
        for rel, data in files.items():
            got = ec.read_file(img.read_bytes(), "/" + rel)
            ok = got == data
            fails += 0 if ok else 1
            print(f"  [{'PASS' if ok else 'FAIL'}] /{rel} ({len(data):,} B)")
        missing = ec.read_file(img.read_bytes(), "/PRESETS/AUDIO/none.wav")
        ok = missing is None
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] a missing file reads as None")
        names = sorted(ec.list_dir(img.read_bytes(), "/PRESETS/AUDIO") or [])
        want = sorted(["a.wav", "Long Name Recording.wav", "250910-1432"])
        ok = [n.lower() for n in names] == [n.lower() for n in want]
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] list_dir /PRESETS/AUDIO  {names}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
```

Check first that `build_image` returns the image bytes (read its `return`); if it writes a file instead, adapt the two lines that call it.

- [ ] **Step 2: Run it and see it fail.** `python3 tools/verify/verify_card_reader.py` → `AttributeError: module 'emu_card' has no attribute 'read_file'`.

- [ ] **Step 3: Write the reader.** Add to `tools/emu/emu_card.py`:

```python
def read_file(image: bytes, path: str):
    """The contents of `path` (absolute, '/'-separated, case-insensitive)
    in a FAT16 card image, or None if it is not there. Reads the MBR's
    first partition, the BPB, and follows the FAT chain; long names are
    matched through their VFAT entries, short names directly. The inverse
    of build_image, and held to it by tools/verify/verify_card_reader.py."""
    return _walk(image, path, want_dir=False)


def list_dir(image: bytes, path: str):
    """The entry names in directory `path` of a FAT16 card image, without
    '.' and '..', or None if it is not a directory."""
    return _walk(image, path, want_dir=True)


def _walk(image: bytes, path: str, want_dir: bool):
    import struct
    part = struct.unpack_from("<I", image, 0x1be + 8)[0] * 512
    bps, spc = struct.unpack_from("<HB", image, part + 11)
    reserved, nfats, nroot = struct.unpack_from("<HBH", image, part + 14)
    spf = struct.unpack_from("<H", image, part + 22)[0]
    fat = part + reserved * bps
    root = fat + nfats * spf * bps
    data = root + nroot * 32
    csize = spc * bps

    def chain(c):
        while 2 <= c < 0xfff8:
            yield data + (c - 2) * csize
            c = struct.unpack_from("<H", image, fat + 2 * c)[0]

    def entries(raw):
        lfn = []
        for o in range(0, len(raw), 32):
            e = raw[o:o + 32]
            if e[0] == 0:
                return
            if e[0] == 0xe5:
                lfn = []
                continue
            if e[11] == 0x0f:
                part_ = e[1:11] + e[14:26] + e[28:32]
                lfn.insert(0, part_.decode("utf-16-le", "ignore"))
                continue
            short = e[0:8].decode("ascii", "ignore").rstrip()
            ext = e[8:11].decode("ascii", "ignore").rstrip()
            long_ = "".join(lfn).split("\x00")[0].rstrip("\uffff") if lfn else None
            lfn = []
            name = long_ or (short + ("." + ext if ext else ""))
            yield name, e[11], struct.unpack_from("<H", e, 26)[0], struct.unpack_from("<I", e, 28)[0]

    raw = image[root:root + nroot * 32]
    parts = [p for p in path.split("/") if p]
    for i, want in enumerate(parts):
        hit = next((x for x in entries(raw) if x[0].lower() == want.lower()), None)
        if hit is None:
            return None
        _, attr, cluster, size = hit
        body = b"".join(image[a:a + csize] for a in chain(cluster))
        if not attr & 0x10:                      # a file
            return body[:size] if (i == len(parts) - 1 and not want_dir) else None
        raw = body
    if not want_dir:
        return None                              # the path named a directory
    return [n for n, _, _, _ in entries(raw) if n not in (".", "..")]
```

- [ ] **Step 4: Run it and see it pass.** Expected: eight `[PASS]`, exit 0. If the builder puts the BPB somewhere else (read `build_image`'s `part_start`), fix the reader, not the test.

- [ ] **Step 5: Commit.**

```bash
git add tools/emu/emu_card.py tools/verify/verify_card_reader.py
git commit -m "emu_card: read_file and list_dir, a FAT16 reader held byte for byte to build_image"
```

### Task 10: Four port flags: save the card, call a routine, press a key mid-run, fail a write

The port keeps the card in memory and never writes it back. The STEM REC runs also need to call the module's menu action before play and STOP during play, and to see a write error.

**Files:**
- Modify: `tools/emu/ot_emu/card.h`, `tools/emu/ot_emu/card.cpp`, `tools/emu/ot_emu/main.cpp`

- [ ] **Step 1: The card model: expose the image, fail writes on request.** In `card.h`, inside `class AtaCard`'s public section, add:

```cpp
		// --card-out: the image with every sector the firmware wrote.
		const std::vector<uint8_t>& image() const { return m_img; }
		// --card-fail-after N: every WRITE SECTORS after N sectors have been
		// written ends in ERR + ABRT, the way a full or failing card answers.
		void failWritesAfter(const int64_t _n) { m_failAfter = _n; }
```

and in its private section `int64_t m_failAfter = -1;`. In `card.cpp`, at the top of `case 0x30:` add:

```cpp
			if(m_failAfter >= 0 && static_cast<int64_t>(m_writes) >= m_failAfter)
			{
				m_error = 0x04;			// ABRT
				m_status |= 0x01;		// ERR, no DRQ: the command is refused
				m_log.push_back({"WRITE-FAIL", lba(), count()});
				return;
			}
```

- [ ] **Step 2: The flags.** In `main.cpp`, next to `std::string memDump;` declare:

```cpp
	std::string cardOut;		// --card-out FILE: the card image at the end of the run
	std::string callBeforePlay;	// --call-before-play ADDR[:ARG][,...]: callAsMain after the load, before the transport start
	std::string atFrames;		// --at FRAME:ADDR[:ARG][,...]: callAsMain at that frame after the transport start
	long long cardFailAfter = -1;	// --card-fail-after N
```

and in the argument loop, before the final `else`:

```cpp
		else if(a == "--card-out" && i + 1 < _argc)		cardOut = _argv[++i];
		else if(a == "--call-before-play" && i + 1 < _argc)	callBeforePlay = _argv[++i];
		else if(a == "--at" && i + 1 < _argc)			atFrames = _argv[++i];
		else if(a == "--card-fail-after" && i + 1 < _argc)	cardFailAfter = std::atoll(_argv[++i]);
```

After `card = std::make_unique<ot::AtaCard>(std::move(bytes));` add `if(cardFailAfter >= 0) card->failWritesAfter(cardFailAfter);`.

Add a parser above `main`:

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
			Call c;
			std::vector<std::string> f;
			size_t r = 0;
			while(r <= one.size()) { auto k = one.find(':', r); if(k == std::string::npos) k = one.size(); f.push_back(one.substr(r, k - r)); r = k + 1; }
			size_t n = 0;
			if(_withFrame) c.frame = std::strtoull(f[n++].c_str(), nullptr, 0);
			c.addr = static_cast<uint32_t>(std::strtoul(f[n++].c_str(), nullptr, 0));
			if(n < f.size()) c.arg = static_cast<uint32_t>(std::strtoul(f[n].c_str(), nullptr, 0));
			out.push_back(c);
		}
		return out;
	}
```

- [ ] **Step 3: Call before play.** Immediately before `if(!rtos.startTransportLive())`, add:

```cpp
				for(const auto& c : parseCalls(callBeforePlay, false))
				{
					uint32_t d0 = 0;
					const bool ok = rtos.callAsMain(c.addr, {c.arg}, d0, 200000000);
					std::printf("call       : %#x(%#x) before play -> %s, d0 %#x\n", c.addr, c.arg,
						ok ? "returned" : rtos.why().c_str(), d0);
				}
```

- [ ] **Step 4: Call at a frame.** Replace the single `const auto rs2 = rtos.runUntil(...)` with a loop over the `--at` calls in frame order, then the remaining run:

```cpp
					auto calls = parseCalls(atFrames, true);
					std::sort(calls.begin(), calls.end(), [](const Call& x, const Call& y) { return x.frame < y.frame; });
					for(const auto& c : calls)
					{
						const auto at = frame0 + c.frame;
						rtos.runUntil(c.frame * ot::g_framePeriod / ot::g_sampleHz * 1000.0 * 5 + 2000.0,
							[&] { return rtos.frameCount() >= at; });
						rtos.runToMainSpin(1000.0);
						uint32_t d0 = 0;
						const bool ok = rtos.callAsMain(c.addr, {c.arg}, d0, 200000000);
						std::printf("call       : %#x(%#x) at frame %llu -> %s, d0 %#x\n", c.addr, c.arg,
							static_cast<unsigned long long>(rtos.frameCount() - frame0),
							ok ? "returned" : rtos.why().c_str(), d0);
					}
					const auto rs2 = rtos.runUntil(frames * ot::g_framePeriod / ot::g_sampleHz * 1000.0 * 5 + 2000.0,
						[&] { return rtos.frameCount() >= target; });
```

Check that `runToMainSpin` is public in `rtos.h`; if it is not, make it public (one line) and say so in the commit.

- [ ] **Step 5: Save the card.** Next to the `memDump` handling at the end of `main`, add:

```cpp
	if(!cardOut.empty() && card)
	{
		std::ofstream co(cardOut, std::ios::binary);
		co.write(reinterpret_cast<const char*>(card->image().data()), static_cast<std::streamsize>(card->image().size()));
		std::printf("card out   : %s (%llu sectors written in the run)\n", cardOut.c_str(),
			static_cast<unsigned long long>(card->sectorsWritten()));
	}
```

  (`card` must still be in scope there; if it is declared in an inner block, move the save into that block's end.)

- [ ] **Step 6: Build and prove each flag against the stock image.** `make emu-cf`, then with any project card:

```bash
out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card <card.img> --set <SET> --project <PROJ> \
  --sequencer --frames 400 --load-ms 20000 --at 200:0x4000a1e0:0 --card-out /tmp/after.img \
  > /tmp/f.log 2>&1; echo $?
grep -n "call \|card out" /tmp/f.log
cmp <card.img> /tmp/after.img | head -1
```

  Expected: the STOP call returns at frame 200; `card out` reports the sectors the load wrote (the firmware's own log file, EMU.md); `cmp` reports a difference. Find the log with Task 9's reader: `list_dir` the root and the set folder of both images, and `read_file` the file that exists only in `/tmp/after.img` or grew there. It must be readable text naming the project. That proves `--card-out` and the reader together. With `--card-fail-after 0`, the log shows `WRITE-FAIL` lines; write down what the firmware then does (retries, error, hang). That behaviour is stock's, and Task 16 depends on it.

- [ ] **Step 7: Commit.**

```bash
git add tools/emu/ot_emu/card.h tools/emu/ot_emu/card.cpp tools/emu/ot_emu/main.cpp
git commit -m "ot_emu: --card-out, --call-before-play, --at FRAME:ADDR:ARG, --card-fail-after"
```

### Task 11: The fixture, and T1's layout in the read-back block

COLDFIRE_PORT O10 renders a kick on T1 sample-exact under the port: the RIG project, T1 = FLEX on slot 1 in banks 1 and 2, all parts and mirrors, T1 FX1 and FX2 = SEND, the kick from `scripts/make_test_audio.py kick` staged at slot 1's card path, `--poke-trig 2 --main-level 64`, and with `TSMODE=0` "the record IS the file".

**Files:**
- Modify: `docs/firmware/STEM_REC.md` (section 9)
- Create: `tools/verify/stems_fixture.py` (builds the card)

- [ ] **Step 1: Find the RIG project.** `ls ~/octabam/out/ ~/octabam/out/_emu_rtos_tree 2>/dev/null` and COLDFIRE_PORT O10's text. If no copy of the RIG project exists on this machine, ask Yves for a project folder from his card (his own data, not Elektron's) and use it instead; any project whose T1 can be made FLEX works.
- [ ] **Step 2: Write `tools/verify/stems_fixture.py`,** which copies the project into a scratch folder, applies `tools/hw/ot_project.py` edits (FLEX on T1 with `set_machine_type`, SEND in both FX slots with `set-fx`, `TSMODE=0` for slot 1 in `project.work`), makes the kick with `scripts/make_test_audio.py kick`, and calls `emu_rtos.stage_project(project, set_name, name, audio=[f"{kick}:{slot_path}"])`. It prints the card path, the set and the project. Keep every edit in the script so the fixture is reproducible from one command.
- [ ] **Step 3: Dump the block.**

```bash
python3 tools/verify/stems_fixture.py > /tmp/fx.txt; cat /tmp/fx.txt
out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card <card> --set <SET> --project <PROJ> \
  --sequencer --internal-clock --frames 300 --load-ms 20000 --dsp --main-level 64 --pre-roll 40 \
  --poke-trig 2 --block-dump /tmp/t1.dump > /tmp/t1.log 2>&1; echo $?
python3 tools/scratch/blockdump.py summary /tmp/t1.dump
```

- [ ] **Step 4: Settle the layout.** The read-back classes are the DSP-to-ColdFire ones at `ram` `0x80003190` and `0x80003590`. Extract T1's first 64 words per frame and compare the even words `w[0], w[2], ..., w[62]` with the kick's samples (`kick.wav`, 16-bit): the lag that makes them match, and the residual. Then check that the odd words are the low 8 bits shifted left by 8.
- [ ] **Step 5: Write section 9, "T1 in the read-back block".** State: T1's offset in the half, the word order (L high, L low, R high, R low), the lag in frames, the residual, and the fixture command. Falsifier: any frame where the even words differ from the kick at the fitted lag. Commit both files.

**Interface produced:** `.equ READBACK, 0x80003190`, `.equ T1_OFFSET, <bytes>`, the fixture command, and a Python helper for Task 14 to reuse, written into `tools/verify/verify_stems.py` in Task 14:

```python
def t1_frames(dump_path):
    """T1's 16-bit stereo frames from a --block-dump, in frame order: the even
    words of T1's 64-word block in each read-back. One entry per frame, each
    32 signed samples, L R L R ..."""
    import blockdump
    out = []
    for d, frame, ch, core, ram, w in blockdump.read(dump_path):
        if ram in (0x80003190, 0x80003590) and d == READBACK_DIR:
            base = T1_OFFSET // 2
            out.append((frame, [x - 65536 if x >= 32768 else x for x in w[base:base + 64:2]]))
    return [s for _, s in sorted(out)]
```

  with `READBACK_DIR` the direction character the summary printed for those classes.

---

## Phase C: the build change

### Task 12: `DramRegion`: uninitialised DRAM at the top of the platform's reserve

**Files:**
- Modify: `tools/remix/schema.py` (new dataclass after `ArenaReserve`, new `Module` field)
- Modify: `tools/remix/platform_build.py` (`build`)
- Modify: `tools/build/build_bus.py` (section 1e)
- Modify: `tools/remix/ledger.py` (after the arena section)
- Modify: `tools/remix/selftest.py` (one case)

- [ ] **Step 1: Write the failing ledger test.** In `selftest.py`, extend the import to `from remix.schema import (CavePatch, Claims, DramRegion, DspSection, Kind, Linked, MenuEntry, Module, Param, YBase)`, add after `_cave`:

```python
def _region(name, symbol):
    return Module(
        name=name, key=name.upper(), kind=Kind.CF_PATCH, doc="fixture",
        linked=(Linked(name, "does/not/exist.s", dram=True),),
        dram_regions=(DramRegion(symbol, 0x1000),),
    )
```

and append to `CASES`:

```python
    ("two modules claiming one DRAM region symbol",
     [_region("alpha", "ring"), _region("beta", "ring")], "DRAM region"),
```

- [ ] **Step 2: Run it and see it fail.** `python3 tools/remix/selftest.py` → `ImportError: cannot import name 'DramRegion'`.

- [ ] **Step 3: The schema.** In `schema.py`, after `class ArenaReserve`:

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

  In `class Module`, next to `linked`, add `dram_regions: tuple[DramRegion, ...] = ()`. If `Module` validates itself in a `__post_init__`, add: a module with `dram_regions` and no `dram=True` unit raises `ValueError("... declares DRAM regions but has no DRAM unit to name them")`.

- [ ] **Step 4: The ledger.** In `ledger.py`, after the arena section and before the function returns:

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

- [ ] **Step 5: Run the selftest and see it pass.** Expected: the new case `[PASS]` naming `alpha` and `beta`, every other case unchanged.

- [ ] **Step 6: The platform build.** In `platform_build.build`, change the signature to `def build(units, payloads, work: pathlib.Path, reserve=None, defsyms=None, regions=()):`, document `regions: [(symbol, size, align)]` in the docstring, and inside `if units:` after `defs.update(defsyms or {})`:

```python
        # DramRegions: stacked down from the ceiling, named to the link.
        placed = {}
        top = ceiling
        for sym, size, align in regions:
            top = (top - size) & ~(align - 1)
            placed[sym] = (top, size)
        defs.update({s: a for s, (a, _) in placed.items()})
```

  and after the existing `if stage_end > ceiling:` check:

```python
        if placed:
            floor_sym, (floor, _) = min(placed.items(), key=lambda kv: kv[1][0])
            if stage_end > floor:
                sys.exit(f"platform build: the runtime and its stage end at 0x{stage_end:08x}, "
                         f"above DRAM region {floor_sym} at 0x{floor:08x} -- shrink the regions "
                         f"or reserve more pages (tools/remix/arena.py PLATFORM_PAGES).")
```

  and in the `layout.update(...)` call's neighbourhood, only when there are regions (so every existing layout file stays byte-identical):

```python
        if placed:
            layout["regions"] = {s: [a, n] for s, (a, n) in placed.items()}
```

- [ ] **Step 7: The build.** In `build_bus.py` section 1e, before `if _dram or _payloads:`:

```python
    _regions = [(_r.symbol, _r.size, _r.align) for _k in REMIX.modules
                for _r in getattr(remix_modules()[_k], "dram_regions", ())]
```

  pass `regions=_regions` to `platform_build.build(...)`, and after the existing `platform runtime:` print:

```python
        for _s, _n, _al in _regions:
            print(f"  dram region: {_s} {_n:,} B at 0x{_psyms[_s]:08x}")
```

- [ ] **Step 8: Prove the build changed nothing.**

```bash
scripts/refhash.sh check > /tmp/rh2.log 2>&1; echo $?
tail -30 /tmp/rh2.log
```

  Expected: exit 0, all 26 configurations bit-identical, artifacts and reports. No existing module declares a region, so any difference is a bug in Steps 6 and 7.

- [ ] **Step 9: Commit.**

```bash
git add tools/remix/schema.py tools/remix/platform_build.py tools/build/build_bus.py tools/remix/ledger.py tools/remix/selftest.py
git commit -m "DramRegion: uninitialised DRAM at the top of the platform reserve, refused on a misfit or a shared symbol -- refhash 26/26 identical"
```

---

## Phase D: the module

The unit grows over Tasks 13 to 16. The equates marked **(Task N)** take the values Phase A recorded. Keep the section order: facts, constants, data, action, hook, task, writer.

### Task 13: The row, the action, the remix

**Files:**
- Create: `modules/stems/manifest.py`, `modules/stems/stems.s`, `remixes/stems.py`, `tools/verify/verify_stems.py`
- Modify: `Makefile` (`verify` target)

- [ ] **Step 1: Write the failing static check.** `tools/verify/verify_stems.py`:

```python
#!/usr/bin/env python3
"""STEM REC -- the row, the tap and the file, checked without hardware.

    python3 tools/verify/verify_stems.py [remix]      (default: stems)

Static, from the built image: CONTROL has seven rows, the six stock ones
byte for byte, the seventh labelled STEM REC with the module's action and
id 0; the frame site jumps to the hook; the ring and the stack sit at the
top of the platform reserve, above the runtime's stage. Then, when the
port is built and the fixture exists (tools/verify/stems_fixture.py), the
runs of Tasks 14 to 16.
"""
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
BASE = 0x40000400
IMAGE = pathlib.Path("out/mainos_bus.bin")
STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
RUNTIME_ELF = pathlib.Path("out/platform/runtime/runtime.elf")
LAYOUT = pathlib.Path("out/platform")          # platform_build.LAYOUT lives here
CONTROL_DESC, CONTROL_ROWS, ROW_LEN, STOCK_N = 0x400cbd54, 0x400cc5a8, 24, 6
FRAME_SITE = 0x40004b12
fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def syms():
    out = subprocess.run(["m68k-elf-nm", str(RUNTIME_ELF)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def rd32(img, a):
    return int.from_bytes(img[a - BASE:a - BASE + 4], "big")


def static(img, stock, s):
    check("CONTROL count is 7", rd32(img, CONTROL_DESC) == 7, f"{rd32(img, CONTROL_DESC)}")
    rows = rd32(img, CONTROL_DESC + 0x18)
    check("CONTROL rows moved", rows != CONTROL_ROWS, f"0x{rows:08x}")
    a, b = rows - BASE, CONTROL_ROWS - BASE
    check("the six stock rows came across byte for byte",
          img[a:a + ROW_LEN * STOCK_N] == stock[b:b + ROW_LEN * STOCK_N])
    r7 = [rd32(img, rows + ROW_LEN * STOCK_N + 4 * k) for k in range(6)]
    check("row 7 label is stems_label", r7[0] == s["stems_label"], f"0x{r7[0]:08x}")
    check("row 7 action is stems_action", r7[2] == s["stems_action"], f"0x{r7[2]:08x}")
    check("row 7 window, pad, child and id are 0", r7[1] == r7[3] == r7[4] == r7[5] == 0, f"{r7}")
    want = b"\x4e\xb9" + s["stems_frame_hook"].to_bytes(4, "big") + b"\x4e\x71"
    got = img[FRAME_SITE - BASE:FRAME_SITE - BASE + 8]
    check("0x40004b12 is jsr stems_frame_hook; nop", got == want, got.hex())


def regions(s):
    lay = json.loads(next(LAYOUT.glob("*.json")).read_text())
    ring, stack = s["stems_ring"], s["stems_stack"]
    check("ring is 4 MiB ending at the reserve ceiling", ring + 0x400000 == lay["ceiling"],
          f"0x{ring:08x} + 4 MiB vs ceiling 0x{lay['ceiling']:08x}")
    check("stack sits just below the ring", stack + 0x2000 <= ring, f"0x{stack:08x}")
    check("the runtime's stage ends below the stack", lay["stage_end"] <= stack,
          f"stage end 0x{lay['stage_end']:08x}")


def main():
    from remix import registry
    name = sys.argv[1] if len(sys.argv) > 1 else "stems"
    if "STEM REC" not in registry.remix(name).modules:
        print(f"  [ -- ] {name} does not carry STEM REC -- nothing to check")
        return 0
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], capture_output=True, text=True, env=env)
    if r.returncode:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    img, stock, s = IMAGE.read_bytes(), STOCK.read_bytes(), syms()
    static(img, stock, s)
    regions(s)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
```

  Check the layout file's real name (`platform_build.LAYOUT`) and the ceiling/stage key names against `platform_build.build`, and fix the three lines in `regions()` if they differ.

- [ ] **Step 2: Run it and see it fail.** `python3 tools/verify/verify_stems.py` → `KeyError: 'stems'` or "does not carry" (no remix yet).

- [ ] **Step 3: The remix.** `remixes/stems.py`:

```python
"""STEMS -- the STEM REC proof of concept, alone.

T1 to the card while the sequencer plays, from MAIN MENU > CONTROL > STEM
REC (docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md). Nothing
else, so a first flash can only fail in one module's ways.
"""

from remix.schema import Remix

REMIX = Remix(
    name="stems",
    doc="STEM REC proof of concept: T1 to the card, alone.",
    modules=("STEM REC",),
    fallback="NONE",
)
```

- [ ] **Step 4: The manifest.** `modules/stems/manifest.py`:

```python
"""STEM REC -- T1 to the card while the sequencer plays (proof of concept).

MAIN MENU > CONTROL > STEM REC arms a recording, or starts one if the
sequencer is running; selecting it again stops it, and so does the
sequencer stopping or 15 seconds. The file is <set>/AUDIO/YYMMDD-HHMM/T1.wav,
16-bit stereo. Design: docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md.
Every stock fact the unit uses: docs/firmware/STEM_REC.md.

HOW, in one breath: a detour at the per-frame routine's only call site
(0x40004b12) packs T1's post-FX2 read-back block into a 4 MiB ring each
frame; an RTOS task of the module's own drains the ring to the card
through the stock buffered file API; the ring and the task's stack are
DramRegions at the free top of the platform reserve, so the module costs
no sample memory beyond what any DRAM remix already gives up.

⚠️ UNFLASHED. It shares the frame site with CF PROBE and the CONTROL list
with MENU SHORTCUT; the ledger refuses both pairings by name.
"""

from remix.schema import Detour, DramRegion, Kind, Linked, Module, Poke, TableGrow

# The per-frame routine's only call site, inside the audio interrupt at
# IPL 5: `jsr %pc@(0x400031a0)` then `move.w #0x2700,%sr` (cfprobe's site).
# The hook performs both, so a jsr + nop replaces them.
FRAME_SITE = 0x40004B12
FRAME_STOCK = bytes.fromhex("4ebae68c" "46fc2700")

# The CONTROL list (docs/firmware/MAINMENU.md sections 2-5): count at +0x00,
# row array pointer at +0x18, six rows of six longs (label, window, action,
# 0, child, id). TableGrow copies the stock rows from the user's image at
# build time and appends ours; an ACTION row has window, child and id 0.
CONTROL_DESC = 0x400CBD54
CONTROL_ROWS = 0x400CC5A8
ROW_N, ROW_WORDS = 6, 6

MODULE = Module(
    name="stems",
    key="STEM REC",
    kind=Kind.CF_PATCH,
    doc="MAIN MENU > CONTROL > STEM REC: T1 to the card while the sequencer plays "
        "(POC: 16-bit, 15 s).",
    linked=(Linked("stems", "modules/stems/stems.s", dram=True),),
    detours=(Detour(FRAME_SITE, FRAME_STOCK, "stems", "stems_frame_hook",
                    "per-frame tap: T1 into the ring, then the stock routine",
                    kind="jsr", pad_to=8),),
    tables=(TableGrow("CONTROL rows + STEM REC", old=CONTROL_ROWS,
                      count=ROW_N * ROW_WORDS,
                      symbols=(("stems", "stems_label"), ("stems", "stems_zero"),
                               ("stems", "stems_action"), ("stems", "stems_zero"),
                               ("stems", "stems_zero"), ("stems", "stems_zero")),
                      refs=((CONTROL_DESC + 0x18, CONTROL_ROWS),)),),
    pokes=(Poke(CONTROL_DESC, expect=(ROW_N).to_bytes(4, "big"),
                write=(ROW_N + 1).to_bytes(4, "big"), note="CONTROL count 6 -> 7"),),
    dram_regions=(DramRegion("stems_ring", 0x400000),
                  DramRegion("stems_stack", 0x2000)),
)
```

- [ ] **Step 5: The unit, first slice: facts, constants, data, the action, and a hook that only runs the stock routine.** `modules/stems/stems.s`:

```asm
| STEM REC -- T1 to the card while the sequencer plays (proof of concept).
|
| Design: docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md.
| Every stock address below, with its evidence: docs/firmware/STEM_REC.md.
|
| Three parts share the state words below:
|   stems_action      MAIN MENU > CONTROL > STEM REC, in the UI task
|   stems_frame_hook  the per-frame tap, in the audio interrupt at IPL 5
|   stems_task        our own RTOS task: the ring to the card
| The state is one aligned long, so every read and write of it is one
| instruction. The action and the hook write it; the task writes only IDLE.

| ---- stock facts (docs/firmware/STEM_REC.md) ----------------------------
        .equ    TRANSPORT,     0x800065b8   | long; 0 = stopped            (Task 2)
        .equ    CARD_MOUNTED,  0x460d1cb8   | 0 = no card                  (Task 8)
        .equ    FRAME_ROUTINE, 0x400031a0   | the displaced call
        .equ    MODE_W,        0x400b328b   | "w": opens without truncating

| ---- constants -----------------------------------------------------------
        .equ    ST_IDLE,       0
        .equ    ST_ARMED,      1
        .equ    ST_RECORDING,  2
        .equ    ST_FINISHING,  3

        .text

| ---- state -----------------------------------------------------------------
        .balign 4
        .global stems_state, stems_status, stems_task_made
stems_state:     .long   ST_IDLE
stems_status:    .long   0          | the last error, 0 = none
stems_task_made: .long   0
stems_wr:        .long   0          | bytes the hook has put in the ring
stems_rd:        .long   0          | bytes the task has taken out
stems_frames:    .long   0          | frames recorded

| ---- the menu row -------------------------------------------------------
        .global stems_label, stems_zero
        .equ    stems_zero, 0       | the row's window, pad, child and id
stems_label:
        .asciz  "STEM REC"
        .balign 2

| ---- the menu action: action(0), in the UI task ------------------------
| d0-d1/a0-a1 are scratch; everything else is preserved.
        .global stems_action
stems_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        tst.l   CARD_MOUNTED        | no card: do nothing at all
        beq.s   .La_out
        move.w  %sr,%d2
        move.w  #0x2700,%sr         | no frame hook between read and write
        move.l  stems_state,%d0
        tst.l   %d0
        bne.s   .La_busy
        clr.l   stems_wr            | IDLE: a fresh recording
        clr.l   stems_rd
        clr.l   stems_frames
        clr.l   stems_status
        moveq   #ST_ARMED,%d1
        tst.l   TRANSPORT
        beq.s   .La_set
        moveq   #ST_RECORDING,%d1   | already playing: start at the next frame
        bra.s   .La_set
.La_busy:
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .La_notarmed
        moveq   #ST_IDLE,%d1        | ARMED: cancel
        bra.s   .La_set
.La_notarmed:
        moveq   #ST_RECORDING,%d1
        cmp.l   %d1,%d0
        bne.s   .La_unmask          | FINISHING: ignored
        moveq   #ST_FINISHING,%d1   | RECORDING: stop
.La_set:
        move.l  %d1,stems_state
.La_unmask:
        move.w  %d2,%sr
.La_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts

| ---- the frame hook: in the audio interrupt, IPL 5 ---------------------
| Reached by `jsr` from 0x40004b12. Performs the two instructions it
| displaced: the call to the per-frame routine, then the SR write.
        .global stems_frame_hook
stems_frame_hook:
        jsr     FRAME_ROUTINE
        move.w  #0x2700,%sr
        rts
```

  If Task 8 found `CARD_MOUNTED` is a byte, write `tst.b`.

- [ ] **Step 6: Build and run the static check.**

```bash
make bus REMIX=stems > /tmp/b.log 2>&1; echo $?
grep -n "STEM REC\|dram region\|table\|poke" /tmp/b.log
python3 tools/verify/verify_stems.py
```

  Expected: the build prints the detour, the table (36 + 6 entries, 1 ref repointed), the poke, and two `dram region:` lines; every static check `[PASS]`. If the table's zero entries do not resolve, the absolute symbol `stems_zero` is missing from the platform link's `nm`: check `platform_build._nm`, which keeps three-field rows, and that `.global stems_zero` is present.

- [ ] **Step 7: Disassemble what you assembled.** Every instruction of the action and the hook, from the built image at `stems_action` and `stems_frame_hook` (`scripts/disasm.sh emac <addr> <len>` on `out/mainos_bus.bin`, or objdump on `out/platform/runtime/runtime.elf`). Every mnemonic must be the one written.

- [ ] **Step 8: Wire the verifier into `make verify`.** In the `Makefile`'s `verify` target, next to the `verify_menushortcut.py` line, add the same shape:

```make
	@$(PY) tools/verify/verify_stems.py $(REMIX) 2>/dev/null || \
	  $(PY) tools/verify/verify_stems.py $(REMIX)
```

  (Copy the exact shape of the menushortcut line; the one above is its pattern.)

- [ ] **Step 9: The floor.** `make check REMIX=stems > /tmp/k.log 2>&1; echo $?` → 0. Also `make modules` must list STEM REC and show it refused beside MENU SHORTCUT and CF PROBE in the matrix.

- [ ] **Step 10: Commit.**

```bash
git add modules/stems remixes/stems.py tools/verify/verify_stems.py Makefile
git commit -m "stems: the CONTROL row, the action's state machine, and a pass-through frame hook -- static checks pass"
```

### Task 14: The tap: T1 into the ring every frame

**Files:**
- Modify: `modules/stems/stems.s` (the hook; new facts and constants)
- Modify: `tools/verify/verify_stems.py` (the tap run)

- [ ] **Step 1: Write the failing port check.** Add to `verify_stems.py` the `t1_frames` helper from Task 11 (with its two constants), and:

```python
EMU = pathlib.Path("out/emu/ot_emu")
FIXTURE = pathlib.Path("out/stems_fixture.json")   # written by tools/verify/stems_fixture.py
KEY_STOP = 0x4000a1e0


def port(s, frames, stop_at=None, extra=(), tag="run", ring_bytes=0, calls=()):
    """One fixture run under the port: the module's action called before
    play, STOP at `stop_at` (None = no STOP), any further `calls` as
    (frame, addr). Dumps the six state words and, when `ring_bytes`, the
    start of the ring. Returns (log text, dump, card, state words, ring bytes)."""
    fx = json.loads(FIXTURE.read_text())
    work = pathlib.Path("out/stems_runs"); work.mkdir(parents=True, exist_ok=True)
    dump, card = work / f"{tag}.dump", work / f"{tag}.img"
    mem, ring = work / f"{tag}.mem", work / f"{tag}.ring"
    dumps = f"0x{s['stems_state']:x},24={mem}"
    if ring_bytes:
        dumps += f";0x{s['stems_ring']:x},{ring_bytes}={ring}"
    at = [f"{f}:0x{a:x}:0" for f, a in calls]
    if stop_at is not None:
        at.append(f"{stop_at}:0x{KEY_STOP:x}:0")
    args = [str(EMU), "--image", str(IMAGE), "--card", fx["card"], "--set", fx["set"],
            "--project", fx["project"], "--sequencer", "--internal-clock",
            "--frames", str(frames), "--load-ms", "20000", "--dsp", "--main-level", "64",
            "--pre-roll", "40", "--poke-trig", "2", "--block-dump", str(dump),
            "--call-before-play", f"0x{s['stems_action']:x}:0",
            "--card-out", str(card), "--mem-dump", dumps, *extra]
    if at:
        args += ["--at", ",".join(at)]
    r = subprocess.run(args, capture_output=True, text=True)
    m = mem.read_bytes() if mem.exists() else b"\0" * 24
    words = [int.from_bytes(m[i:i + 4], "big") for i in range(0, 24, 4)]
    return (r.stdout + r.stderr, dump, card, words,
            ring.read_bytes() if ring_bytes and ring.exists() else b"")


def tap(s):
    log, dump, _, words, raw = port(s, 400, stop_at=300, tag="tap", ring_bytes=64 * 400)
    st, status, _, wr, rd, nfr = words
    check("the hook recorded frames", nfr > 200, f"{nfr} frames, wr {wr}")
    check("wr is 64 bytes per frame", wr == 64 * nfr, f"{wr} vs {64 * nfr}")
    check("the stop moved RECORDING on", st != 2, f"state {st}, status {status}")
    got = [[int.from_bytes(raw[f * 64 + 2 * k:f * 64 + 2 * k + 2], "big", signed=True)
            for k in range(32)] for f in range(nfr)]
    want = t1_frames(dump)
    lag = next((L for L in range(0, 8) if want[L:L + nfr] == got), None)
    check("every ring frame equals T1's read-back at one fixed lag", lag is not None,
          f"lag {lag}" if lag is not None else "no lag 0..7 matches")
    check("the signal is not silence", any(any(x) for x in got), "non-zero samples present")
```

  The ring is dumped before the task exists, so it is still big-endian here. The last check guards against the instrument blindness CLAUDE.md warns about: two silent streams compare equal.

  In `main()`, after `regions(s)`, add:

```python
    if EMU.exists() and FIXTURE.exists():
        tap(s)
    else:
        print("  [SKIP] port runs: build the port (make emu-cf) and the fixture "
              "(python3 tools/verify/stems_fixture.py)")
```

  and make `stems_fixture.py` write `out/stems_fixture.json` with the keys `card`, `set`, `project`.

- [ ] **Step 2: Run it and see it fail.** Expected: `[FAIL] the hook recorded frames  0 frames` (the hook is still a pass-through).

- [ ] **Step 3: Write the hook.** In `stems.s`, add to the facts:

```asm
        .equ    PING,          0x800000e0   | the read-back half selector  (Task 3)
        .equ    PING_XOR,      0            | half = (PING ^ PING_XOR) & 1  (Task 3)
        .equ    READBACK,      0x80003190   | core 1's read-back, tracks 1-4
        .equ    T1_OFFSET,     0            | T1's block in a half, bytes   (Task 11)
```

  to the constants:

```asm
        .equ    RING_SIZE,     0x400000     | = DramRegion stems_ring
        .equ    FRAME_BYTES,   64           | 16 stereo 16-bit samples
        .equ    MAX_FRAMES,    41344        | 15.0 s
        .equ    ERR_OVERFLOW,  1
```

  and replace `stems_frame_hook` with:

```asm
| ---- the frame hook: in the audio interrupt, IPL 5 ---------------------
| Reached by `jsr` from 0x40004b12. Calls nothing but the routine it
| displaced; uses no RTOS service; loops are bounded. In IDLE its whole
| cost is one test and one branch. The copy runs BEFORE the stock routine,
| which reads the same block (spec section 4).
        .global stems_frame_hook
stems_frame_hook:
        tst.l   stems_state
        beq.w   .Lh_stock           | IDLE
        lea     -32(%sp),%sp
        movem.l %d0-%d5/%a0-%a1,(%sp)
        move.l  stems_state,%d0
        moveq   #ST_FINISHING,%d1
        cmp.l   %d1,%d0
        beq.w   .Lh_out             | FINISHING: the task owns the ring now
        move.l  TRANSPORT,%d2       | 0 = stopped
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .Lh_rec
        tst.l   %d2                 | ARMED
        beq.w   .Lh_out             | still stopped
        moveq   #ST_RECORDING,%d0   | the first playing frame is recorded
        move.l  %d0,stems_state
        bra.s   .Lh_copy
.Lh_rec:                            | RECORDING
        tst.l   %d2
        bne.s   .Lh_copy
        moveq   #ST_FINISHING,%d0   | the sequencer stopped
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_copy:
        move.l  stems_wr,%d3
        move.l  %d3,%d0
        sub.l   stems_rd,%d0        | bytes in the ring
        cmpi.l  #RING_SIZE-FRAME_BYTES,%d0
        bls.s   .Lh_room
        moveq   #ERR_OVERFLOW,%d0   | would overwrite unwritten audio: stop
        move.l  %d0,stems_status
        moveq   #ST_FINISHING,%d0
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_room:
        move.l  PING,%d4            | the half holding this frame (Task 3)
        eori.l  #PING_XOR,%d4
        moveq   #1,%d5
        and.l   %d5,%d4
        moveq   #10,%d5
        lsl.l   %d5,%d4             | * 0x400
        movea.l %d4,%a0
        adda.l  #READBACK+T1_OFFSET,%a0
        move.l  %d3,%d0
        andi.l  #RING_SIZE-1,%d0
        movea.l %d0,%a1
        adda.l  #stems_ring,%a1
| Each sample is one long on the host port: its top 16 bits, then its low
| 8 bits shifted up. Keep the top halves of L and R as one long.
        .rept   16
        move.l  (%a0)+,%d0          | L
        move.l  (%a0)+,%d1          | R
        swap    %d1
        move.w  %d1,%d0             | L top 16 : R top 16
        move.l  %d0,(%a1)+
        .endr
        moveq   #FRAME_BYTES,%d0
        add.l   %d0,%d3
        move.l  %d3,stems_wr        | publish after the data
        move.l  stems_frames,%d0
        addq.l  #1,%d0
        move.l  %d0,stems_frames
        cmpi.l  #MAX_FRAMES,%d0
        bcs.s   .Lh_out
        moveq   #ST_FINISHING,%d0   | 15 seconds
        move.l  %d0,stems_state
.Lh_out:
        movem.l (%sp),%d0-%d5/%a0-%a1
        lea     32(%sp),%sp
.Lh_stock:
        jsr     FRAME_ROUTINE
        move.w  #0x2700,%sr
        rts
```

  Use the rule Task 3 recorded for the half; if it is not the XOR form, replace the five instructions after `move.l PING,%d4`.

- [ ] **Step 4: Rebuild, disassemble, run.** `make bus REMIX=stems`, then disassemble `stems_frame_hook` in full. Check in particular that `eori.l #0` and `cmpi.l` came out as written, and that the `.rept` body is five instructions sixteen times. Then `python3 tools/verify/verify_stems.py`. Expected: every tap check `[PASS]`, with the lag printed.

  The task does not exist yet, so nothing drains the ring. That is fine for 300 frames (19,200 bytes).

- [ ] **Step 5: Count the hook's cost.** Run once more with `--watch-pc` or `--coverage` on the hook's range, and write down the instructions per frame in IDLE, in ARMED, and in RECORDING in `docs/firmware/STEM_REC.md` section 10, "The hook's cost". Commit that separately.

- [ ] **Step 6: Commit.**

```bash
git add modules/stems/stems.s tools/verify/verify_stems.py tools/verify/stems_fixture.py
git commit -m "stems: the tap -- T1 into the ring every frame, equal to the read-back at a fixed lag under the port"
```

### Task 15: The writer task: the ring to `T1.wav`

**Files:**
- Modify: `modules/stems/stems.s` (task creation in the action; the task; the writer)
- Modify: `tools/verify/verify_stems.py` (the file run)

- [ ] **Step 1: Write the failing check.** Add to `verify_stems.py`:

```python
import struct

def wav_check(card_path, nfr, dump, tag):
    import emu_card as ec
    img = pathlib.Path(card_path).read_bytes()
    fx = json.loads(FIXTURE.read_text())
    audio = f"/{fx['set']}/AUDIO"
    names = [n for n in (ec.list_dir(img, audio) or []) if n not in fx.get("staged", [])]
    check(f"{tag}: one new recording in {audio}", len(names) == 1, f"{names}")
    if not names:
        return
    path = f"{audio}/{names[0]}/T1.wav" if HAVE_MKDIR else f"{audio}/{names[0]}"
    data = ec.read_file(img, path)
    check(f"{tag}: {path} exists", data is not None)
    if data is None:
        return
    riff, size, wave_, fmt, flen, pcm, ch, rate, brate, align, bits, dtag, dlen = \
        struct.unpack_from("<4sI4s4sIHHIIHH4sI", data, 0)
    check(f"{tag}: header fields", (riff, wave_, fmt, flen, pcm, ch, rate, brate, align, bits, dtag) ==
          (b"RIFF", b"WAVE", b"fmt ", 16, 1, 2, 44100, 176400, 4, 16, b"data"))
    check(f"{tag}: data size = frames x 64", dlen == 64 * nfr, f"{dlen} vs {64 * nfr}")
    check(f"{tag}: RIFF size = 36 + data", size == 36 + dlen, f"{size}")
    check(f"{tag}: file length = 44 + data", len(data) == 44 + dlen, f"{len(data)}")
    got = [[v for v in struct.unpack_from("<32h", data, 44 + 64 * f)] for f in range(nfr)]
    want = t1_frames(dump)
    lag = next((L for L in range(0, 8) if want[L:L + nfr] == got), None)
    check(f"{tag}: every sample equals T1's read-back at one fixed lag", lag is not None,
          f"lag {lag}")
```

  `HAVE_MKDIR` mirrors the unit's equate from Task 7. `stems_fixture.py` must add a key `staged` to `out/stems_fixture.json`: the names it put in the set's AUDIO folder itself (the kick's folder), so the check counts only new names.

  Add a second run beside `tap()`, long enough for the task to finish after STOP:

```python
def full(s):
    log, dump, card, words, _ = port(s, 700, stop_at=400, tag="full")
    st, status, made, wr, rd, nfr = words
    check("full: the task finished (state IDLE, no error)", st == 0 and status == 0,
          f"state {st}, status {status}")
    check("full: the task drained everything", rd == wr, f"rd {rd}, wr {wr}")
    wav_check(card, nfr, dump, "full")
```

  and call `full(s)` after `tap(s)`. The 300 frames after STOP give the task time to finish. From this task on, `tap()` sees the ring after the task has swapped it to little-endian if the task ran first; keep `tap()` as it is (its run stops at frame 300 and its dump is taken at the end, so compare only while `rd == 0`, and skip the ring comparison with a `[ -- ]` line when `rd > 0`).

- [ ] **Step 2: Run it and see it fail.** Expected: `[FAIL] full: the task finished` (state stays FINISHING: there is no task).

- [ ] **Step 3: The task and the writer.** Add to the facts in `stems.s`, with the values Phase A recorded:

```asm
        .equ    K_CREATE,      0x400005fc   | (tcb, entry, prio, stack, size) -> 1   (Task 4)
        .equ    K_START,       0x4000063c   | (tcb)                                  (Task 4)
        .equ    TCB_SIZE,      96           |                                        (Task 4)
        .equ    K_DELAY,       0x40000000   | (ticks)  -- REPLACE with Task 5's      (Task 5)
        .equ    TASK_TICKS,    10           | about 10 ms                            (Task 5)
        .equ    F_OPEN,        0x40016864   | (obj, path, mode, buf, size) <0 = error
        .equ    F_WRITE,       0x400166b8   | (obj, src, len) 1 = success
        .equ    F_SEEK,        0x4001660c   | (obj, offset) <0 = error
        .equ    F_CLOSE,       0x4001677c   | (obj) <0 = error
        .equ    PROJ_DIR,      0x40025230   | (0, 0) -> project directory     (Task 6)
        .equ    CLK_READ,      0x4001c4d8   | (field) -> BCD                   (Task 6)
        .equ    BCD2BIN,       0x4001c31c   | (bcd) -> binary                  (Task 6)
        .equ    NAME_FMT,      0x400b77bb   | "%02d%02d%02d-%02d%02d"           (Task 6)
        .equ    SPRINTF,       0x40013a08   | (buf, fmt, ...)
        .equ    HAVE_MKDIR,    0            |                                  (Task 7)
        .equ    FS_MKDIR,      0            | (path)                           (Task 7)
```

  **`K_DELAY` must be replaced with Task 5's address before this step is run.** The `0x40000000` is there only so the file assembles if someone builds out of order, and `verify_stems.py` must refuse to run the port when the unit's `K_DELAY` symbol equals `0x40000000`: add that guard at the top of `full()`, reading the value with `m68k-elf-nm` on `out/platform/runtime/runtime.elf` after marking it `.global` (use `.global K_DELAY` beside the `.equ`).

  Add to the constants:

```asm
        .equ    CHUNK,         0x10000      | 64 KB per write
        .equ    STACK_SIZE,    0x2000       | = DramRegion stems_stack
        .equ    TASK_PRIO,     1
        .equ    FBUF_SIZE,     512
        .equ    PATH_MAX,      256
        .equ    ERR_PATH,      2
        .equ    ERR_OPEN,      3
        .equ    ERR_EXISTS,    4
        .equ    ERR_WRITE,     5
        .equ    ERR_SEEK,      6
        .equ    ERR_CLOSE,     7
        .equ    ERR_TASK,      8
        .equ    STACK_FILL,    0x5354454d   | "STEM": the untouched stack
```

  Add to the state (after `stems_frames`, so the 24-byte `--mem-dump` still covers the first six words in order):

```asm
stems_file_open: .long   0
stems_le:        .long   0          | a size, little-endian, for the header
stems_file:      .space  24         | the stock buffered file object
stems_tcb:       .space  TCB_SIZE
stems_name:      .space  16         | YYMMDD-HHMM
stems_path:      .space  PATH_MAX
stems_fbuf:      .space  FBUF_SIZE
| The 44-byte header, little-endian as RIFF wants. The two sizes are
| written at stop (spec section 6).
stems_hdr:
        .ascii  "RIFF"
        .long   0                   | 36 + data, at stop
        .ascii  "WAVEfmt "
        .byte   16,0,0,0            | fmt chunk size
        .byte   1,0                 | PCM
        .byte   2,0                 | stereo
        .byte   0x44,0xac,0,0       | 44,100
        .byte   0x10,0xb1,0x02,0    | 176,400 bytes per second
        .byte   4,0                 | block align
        .byte   16,0                | bits
        .ascii  "data"
        .long   0                   | data, at stop
        .equ    HDR_SIZE, 44
fmt_dir:   .asciz  "/AUDIO/%s"
fmt_file:  .asciz  "/T1.wav"
fmt_flat:  .asciz  ".wav"
        .balign 2
```

  Byte swap: ColdFire `byterev` is ISA_A+ and `-mcpu=5407` does not accept it, so encode it (opcode `0x02C0 | reg`, SAMPLE_SAVE.md section 3):

```asm
        .macro  BYTEREV reg          | reg = 0..7, a data register number
        .short  0x02c0 + \reg
        .endm
```

  In `stems_action`, after the `CARD_MOUNTED` test and before `move.w %sr,%d2`, create the task once:

```asm
        tst.l   stems_task_made
        bne.s   .La_made
        bsr.w   stems_task_create   | d0 = 1 when the task exists
        tst.l   %d0
        beq.w   .La_out             | could not create it: stay IDLE
        moveq   #1,%d0
        move.l  %d0,stems_task_made
.La_made:
```

  And the rest of the unit, after the hook:

```asm
| ---- creating the task (from the action, in the UI task) ---------------
| The sequence is stock's own (docs/firmware/STEM_REC.md section 3).
stems_task_create:
        lea     stems_stack,%a0     | fill the stack so its peak can be read
        move.l  #STACK_SIZE/4,%d0
        move.l  #STACK_FILL,%d1
.Lc_fill:
        move.l  %d1,(%a0)+
        subq.l  #1,%d0
        bne.s   .Lc_fill
        move.l  #STACK_SIZE,-(%sp)
        pea     stems_stack
        pea     TASK_PRIO
        pea     stems_task
        pea     stems_tcb
        jsr     K_CREATE
        lea     20(%sp),%sp
        moveq   #1,%d1
        cmp.l   %d1,%d0
        bne.s   .Lc_fail
        pea     stems_tcb
        jsr     K_START
        addq.l  #4,%sp
        moveq   #1,%d0
        rts
.Lc_fail:
        moveq   #ERR_TASK,%d0
        move.l  %d0,stems_status
        moveq   #0,%d0
        rts

| ---- the task ------------------------------------------------------------
| Wakes every TASK_TICKS. Owns the file. Writes stems_state only to IDLE.
stems_task:
.Lt_loop:
        pea     TASK_TICKS
        jsr     K_DELAY
        addq.l  #4,%sp
        move.l  stems_state,%d0
        moveq   #ST_RECORDING,%d1
        cmp.l   %d1,%d0
        blt.s   .Lt_loop            | IDLE or ARMED: nothing to write
        tst.l   stems_file_open
        bne.s   .Lt_drain
        moveq   #ST_FINISHING,%d1
        cmp.l   %d1,%d0
        bne.s   .Lt_open
        tst.l   stems_frames
        beq.s   .Lt_idle            | stopped before a frame: no file
.Lt_open:
        bsr.w   stems_open
        tst.l   %d0
        bmi.s   .Lt_fail
.Lt_drain:
        bsr.w   stems_drain
        tst.l   %d0
        bmi.s   .Lt_fail
        moveq   #ST_FINISHING,%d1
        cmp.l   stems_state,%d1
        bne.s   .Lt_loop
        bsr.w   stems_finish        | the hook has stopped: wr is final
        tst.l   %d0
        bmi.s   .Lt_fail
.Lt_idle:
        clr.l   stems_state
        bra.s   .Lt_loop
.Lt_fail:                           | stems_status says why
        tst.l   stems_file_open
        beq.s   .Lt_idle
        pea     stems_file
        jsr     F_CLOSE
        addq.l  #4,%sp
        clr.l   stems_file_open
        bra.s   .Lt_idle

| ---- the name: YYMMDD-HHMM, from the clock -----------------------------
        .macro  CLOCK field
        pea     \field
        jsr     CLK_READ
        addq.l  #4,%sp
        move.l  %d0,-(%sp)
        jsr     BCD2BIN
        addq.l  #4,%sp
        .endm
stems_make_name:
        lea     -20(%sp),%sp
        movem.l %d2-%d6,(%sp)
        CLOCK   2
        move.l  %d0,%d2             | minute
        CLOCK   3
        move.l  %d0,%d3             | hour
        CLOCK   5
        move.l  %d0,%d4             | day
        CLOCK   6
        move.l  %d0,%d5             | month
        CLOCK   7
        move.l  %d0,%d6             | year, two digits
        move.l  %d2,-(%sp)
        move.l  %d3,-(%sp)
        move.l  %d4,-(%sp)
        move.l  %d5,-(%sp)
        move.l  %d6,-(%sp)
        pea     NAME_FMT
        pea     stems_name
        jsr     SPRINTF
        lea     28(%sp),%sp
        movem.l (%sp),%d2-%d6
        lea     20(%sp),%sp
        rts

| ---- the path: <set>/AUDIO/<name>/T1.wav, or <set>/AUDIO/<name>.wav ----
| set = the project directory up to its last '/'. d0 = 0, or -1 (too long).
stems_make_path:
        lea     -12(%sp),%sp
        movem.l %d2/%a2-%a3,(%sp)
        clr.l   -(%sp)
        clr.l   -(%sp)
        jsr     PROJ_DIR
        addq.l  #8,%sp
        tst.l   %d0
        beq.s   .Lp_fail
        movea.l %d0,%a0
        lea     stems_path,%a1
        suba.l  %a2,%a2             | the last '/' seen
        move.l  #PATH_MAX-40,%d1    | room left for /AUDIO/name/T1.wav
.Lp_copy:
        move.b  (%a0)+,%d0
        beq.s   .Lp_end
        move.b  %d0,(%a1)
        moveq   #0x2f,%d2           | '/'
        cmp.b   %d2,%d0
        bne.s   .Lp_char
        movea.l %a1,%a2             | where the last '/' went
.Lp_char:
        addq.l  #1,%a1
        subq.l  #1,%d1
        bne.s   .Lp_copy
        bra.s   .Lp_fail            | the project path is too long
.Lp_end:
        move.l  %a2,%d0
        beq.s   .Lp_fail            | no '/': not an absolute path
        pea     stems_name          | <set>/AUDIO/<name>
        pea     fmt_dir
        move.l  %a2,-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        .if     HAVE_MKDIR
        pea     stems_path          | the folder; an error here is left to
        jsr     FS_MKDIR            | the open, which fails if it is absent
        addq.l  #4,%sp
        lea     fmt_file,%a0
        .else
        lea     fmt_flat,%a0
        .endif
        lea     stems_path,%a1      | append the file part
.Lp_find:
        tst.b   (%a1)+
        bne.s   .Lp_find
        subq.l  #1,%a1
.Lp_app:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lp_app
        moveq   #0,%d0
        bra.s   .Lp_out
.Lp_fail:
        moveq   #-1,%d0
.Lp_out:
        movem.l (%sp),%d2/%a2-%a3
        lea     12(%sp),%sp
        rts

| ---- open, refuse a file that has content, write the header -------------
stems_open:
        bsr.w   stems_make_name
        bsr.w   stems_make_path
        tst.l   %d0
        bmi.s   .Lo_path
        pea     FBUF_SIZE
        pea     stems_fbuf
        pea     MODE_W
        pea     stems_path
        pea     stems_file
        jsr     F_OPEN
        lea     20(%sp),%sp
        tst.l   %d0
        bmi.s   .Lo_open
        moveq   #1,%d0
        move.l  %d0,stems_file_open
        tst.l   stems_file+16       | word 4: the logical length (Octakit)
        bne.s   .Lo_exists          | same minute as an earlier recording
        pea     HDR_SIZE
        pea     stems_hdr
        pea     stems_file
        jsr     F_WRITE
        lea     12(%sp),%sp
        moveq   #1,%d1
        cmp.l   %d1,%d0
        bne.s   .Lo_write
        moveq   #0,%d0
        rts
.Lo_path:   moveq   #ERR_PATH,%d0
        bra.s   .Lo_err
.Lo_open:   moveq   #ERR_OPEN,%d0
        bra.s   .Lo_err
.Lo_exists: moveq   #ERR_EXISTS,%d0
        bra.s   .Lo_err
.Lo_write:  moveq   #ERR_WRITE,%d0
.Lo_err:
        move.l  %d0,stems_status
        moveq   #-1,%d0
        rts

| ---- write d1 bytes from the ring's read index, little-endian ----------
| d1: a multiple of 4 that does not cross the ring's end. d0 = 0 or -1.
stems_write_run:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  %d1,%d3
        beq.s   .Lw_done
        move.l  stems_rd,%d0
        andi.l  #RING_SIZE-1,%d0
        movea.l %d0,%a0
        adda.l  #stems_ring,%a0
        movea.l %a0,%a1
        move.l  %d3,%d2
        lsr.l   #2,%d2              | longs
.Lw_swap:                           | [L1 L0 R1 R0] -> [L0 L1 R0 R1]
        move.l  (%a1),%d0
        BYTEREV 0
        swap    %d0
        move.l  %d0,(%a1)+
        subq.l  #1,%d2
        bne.s   .Lw_swap
        move.l  %d3,-(%sp)
        move.l  %a0,-(%sp)
        pea     stems_file
        jsr     F_WRITE
        lea     12(%sp),%sp
        moveq   #1,%d1
        cmp.l   %d1,%d0
        bne.s   .Lw_err
        add.l   %d3,stems_rd
.Lw_done:
        moveq   #0,%d0
        bra.s   .Lw_out
.Lw_err:
        moveq   #ERR_WRITE,%d0
        move.l  %d0,stems_status
        moveq   #-1,%d0
.Lw_out:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts

| ---- every whole 64 KB chunk in the ring --------------------------------
stems_drain:
        move.l  stems_wr,%d0
        sub.l   stems_rd,%d0
        cmpi.l  #CHUNK,%d0
        bcs.s   .Ld_done
        move.l  #CHUNK,%d1
        bsr.w   stems_write_run
        tst.l   %d0
        bpl.s   stems_drain
        rts
.Ld_done:
        moveq   #0,%d0
        rts

| ---- the tail, the two sizes, close -------------------------------------
stems_finish:
        move.l  stems_wr,%d1
        sub.l   stems_rd,%d1        | < CHUNK, starts on a CHUNK boundary
        bsr.w   stems_write_run
        tst.l   %d0
        bmi.s   .Lf_ret
        move.l  stems_wr,%d0        | data bytes: the hook started wr at 0
        moveq   #36,%d1
        add.l   %d0,%d1             | RIFF size
        move.l  %d1,%d0
        BYTEREV 0
        move.l  %d0,stems_le
        moveq   #4,%d0
        bsr.s   .Lf_patch
        bmi.s   .Lf_ret
        move.l  stems_wr,%d0
        BYTEREV 0
        move.l  %d0,stems_le
        moveq   #40,%d0
        bsr.s   .Lf_patch
        bmi.s   .Lf_ret
        pea     stems_file
        jsr     F_CLOSE
        addq.l  #4,%sp
        clr.l   stems_file_open
        tst.l   %d0
        bmi.s   .Lf_close
        moveq   #0,%d0
.Lf_ret:
        rts
.Lf_close:
        moveq   #ERR_CLOSE,%d0
        move.l  %d0,stems_status
        moveq   #-1,%d0
        rts
| seek to d0, write stems_le there; d0 = 0 or -1, flags set from d0
.Lf_patch:
        move.l  %d0,-(%sp)
        pea     stems_file
        jsr     F_SEEK
        addq.l  #8,%sp
        tst.l   %d0
        bmi.s   .Lf_seek
        pea     4
        pea     stems_le
        pea     stems_file
        jsr     F_WRITE
        lea     12(%sp),%sp
        moveq   #1,%d1
        cmp.l   %d1,%d0
        bne.s   .Lf_pwrite
        moveq   #0,%d0
        rts
.Lf_seek:
        moveq   #ERR_SEEK,%d0
        bra.s   .Lf_perr
.Lf_pwrite:
        moveq   #ERR_WRITE,%d0
.Lf_perr:
        move.l  %d0,stems_status
        moveq   #-1,%d0
        rts
```

  Replace the CLOCK field numbers, the `PROJ_DIR` return register and the `FS_MKDIR` call with what Tasks 6 and 7 recorded. A `.Lf_close` path that sets `stems_file_open` to 0 before the close result is checked is deliberate: a failed close must not be retried by `.Lt_fail`.

- [ ] **Step 4: Disassemble what you assembled.** The whole unit. Check four things by eye: `BYTEREV 0` is the word `02c0`; every `cmp.l` has its operands the way round the branch after it expects (`cmp.l %d1,%d0` then `blt` means `d0 < d1`); `pea TASK_TICKS` and `pea 4` push the numbers; the `.Lp_copy` loop copies the project path byte for byte (step through it once under the port with `--watch-pc` if in doubt).

- [ ] **Step 5: Run the check.** `make bus REMIX=stems && python3 tools/verify/verify_stems.py`. Expected: every `full:` check `[PASS]`. If the file is missing, read `stems_status` from the mem dump first: its value names the step that failed. If the port hangs in `K_DELAY` or `K_CREATE`, the Task 4 or 5 reading is wrong; go back to it, do not guess.

- [ ] **Step 6: Arm while stopped, and stop from the row.** Add two runs to `verify_stems.py`: (a) the action called before play (already the case: ARMED, then PLAY moves it to RECORDING) is `full`; (b) `rowstop`: action before play, then `--at 200:<stems_action>:0` (the row stops it), then STOP at 400. Expected for (b): a file of about 200 frames, state IDLE, status 0.

- [ ] **Step 7: Commit.**

```bash
git add modules/stems/stems.s tools/verify/verify_stems.py tools/emu/emu_card.py tools/verify/verify_card_reader.py
git commit -m "stems: the writer task -- T1.wav on the port's card equals T1's read-back sample for sample"
```

### Task 16: The limits and the errors

**Files:**
- Modify: `tools/verify/verify_stems.py` (four runs; the long one behind a flag)

- [ ] **Step 1: The 15-second limit.** A run of 43,000 frames with no STOP: `port(s, 43000, stop_at=None, tag="limit")`. Expected: `nfr == 41344` exactly, the file's data size `41344 * 64 = 2,646,016`, state IDLE, status 0. This run is long under the port: put it behind `verify_stems.py --long` and keep it out of `make check`.

- [ ] **Step 2: An existing file is not overwritten.** Run `full` twice on the same card (the second run's `--card` is the first run's `--card-out`: give `port()` a `card=` parameter defaulting to the fixture's), with the clock in the same minute (check that the port's clock reads the same minute in both runs). Expected second run: status `ERR_EXISTS` (4), state IDLE, and the first run's file byte-identical to what it was.

- [ ] **Step 3: The overflow guard.** The POC cannot overflow a 4 MiB ring in 15 seconds, so make the ring look nearly full instead of building a small one: poke `stems_rd` right after the transport start so that `wr - rd` is `RING_SIZE - 6400`, which the hook sees as full about 100 frames later. `--poke` writes bytes (`addr=byte;...`), so write the four bytes of `(-(0x400000 - 6400)) & 0xffffffff` at `stems_rd`, most significant first. Expected: status `ERR_OVERFLOW` (1), set by the hook; `nfr` between 90 and 100; the state goes on to IDLE (the task drains what it believes is there and closes the file); the task is still alive afterwards (a second `--at` action call arms again: state 1). The file's content is not checked here, because the poke made the task drain bytes the hook never wrote.

- [ ] **Step 4: A card write error.** `full` with `--card-fail-after` set just past the load's own writes plus the header. Expected: status `ERR_WRITE` (5), state IDLE, the task alive (a second action call arms again). If Task 10 found that stock's driver hangs on a write error, this test records that fact instead and the spec's section 7 gets a line saying so.

- [ ] **Step 5: Commit.** One commit per test that passes, message naming what it proved.

### Task 17: The stack, the numbers, the documents

**Files:**
- Modify: `docs/firmware/STEM_REC.md` (sections 10 and 11)
- Create: `modules/stems/README.md`
- Modify: `docs/remixer/FAILURE_MODES.md`, `PLAN.md`

- [ ] **Step 1: The stack's peak.** After the `full` run, `--mem-dump` the 8 KB at `stems_stack` and count the longs still equal to `0x5354454d` from the bottom. Peak = 8192 minus 4 times that count. Write it in section 11. If the peak is above 6 KB, raise the stack to 16 KB before flashing.
- [ ] **Step 2: The README.** What it does, how to use it (the three workflows from spec section 2), the file name, the limits (15 s, T1, 16-bit, no screen feedback, same-minute refusal, no project load while recording), and "measured under the port, unflashed" with the numbers from sections 10 and 11.
- [ ] **Step 3: FAILURE_MODES.** Add the entries a flash could hit, each as symptom, likely cause, first check: "no file after a recording" (read the status word under the port first), "the unit hangs when STEM REC is selected" (task creation), "audio drops while recording" (the hook's cost, the storage task's load), "the file is empty after a power cut" (known, header sizes written at stop).
- [ ] **Step 4: PLAN.md.** Update item 8 with where it stands.
- [ ] **Step 5: Commit** each document separately.

### Task 18: The flash

This task needs Yves and the unit.

- [ ] **Step 1: Build the image.** `make image REMIX=stems BUILD=<next>` (read `docs/remixer/FLASHING.md` for the current `BUILD` number and naming). Record the SHA-256 of the result.
- [ ] **Step 2: Bring the branch to the Windows clone.** `git -C /c/Projects/Octabam fetch //wsl$/Ubuntu/home/yvez/octabam-stems stem-rec-poc` then fast-forward it there. Do not push anywhere.
- [ ] **Step 3: Write the flash notes** for Yves, in `docs/effects/FLASHPLAN.md`'s format: the image, the card to use (backed up or spare), and the three tests from spec section 11 in order, each with what to look at and what to report back.
- [ ] **Step 4: After the flash,** record every result, good and bad, in `docs/firmware/STEM_REC.md` (a "Hardware" section) and `FAILURE_MODES.md`, then update `PLAN.md`.

---

## Self-review notes

- Spec coverage: section 2 workflows (Tasks 13, 15 Step 6), section 3 states and race (13), section 4 tap (14), section 5 ring and placement (12, 14, 16), section 6 task and file API (4 to 8, 15), section 7 stops and errors (14, 16), section 8 crash safety (13 card check, 14 bounded hook, 15 checked results, 17 stack), section 9 unknowns (2 to 8, 11), section 10 verification (9, 10, 13 to 17), section 11 flash (18), section 12 TODO (unchanged, in the spec).
- The one value that cannot be written ahead is `K_DELAY`: Task 15 guards it so a stale `0x40000000` refuses to run rather than hanging the port.
