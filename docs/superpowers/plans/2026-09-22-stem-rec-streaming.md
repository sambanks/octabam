# STEM REC streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** STEM REC writes each take to the card while it records, one WAV per enabled track, through the file layer's raw routines, with only T1 enabled.

**Architecture:** The frame hook copies each enabled track's 16 samples per frame into the 4 MiB ring (frame counters, offsets that wrap at a whole frame). The writer task drains the ring in 512-frame chunks while recording, de-interleaves per track into its own uncached sector buffers, writes whole sectors with the raw write, and at the end rewrites sector 0 with the real header, sets the exact length, and closes. A probe measures the five raw routines under the port before anything depends on them.

**Tech Stack:** ColdFire assembly (GNU `m68k-elf-as -mcpu=5407`), the octabam remix build (`make check REMIX=stems`), the ColdFire port (`out/emu/ot_emu`), Python verifiers (`tools/verify/verify_stems.py`).

**Spec:** `docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md` (amended in Task 1: the mask is a module word latched at the start, and the long test is 20 s).

## Global Constraints

- Branch `crosscheck` in the Windows clone `c:\Projects\Octabam`. Commit there, one commit per task. Never push.
- Build and test only in the WSL worktree `/home/yvez/xcheck/wt` (branch `crosscheck-wt` of `/home/yvez/octabam-stems`). Never build in `/home/yvez/octabam-stems` itself: its `out/` holds the staged Flash 13 artifacts.
- Sync a changed file to the worktree with `tr -d '\r' < /mnt/c/Projects/Octabam/<path> > /home/yvez/xcheck/wt/<path>`. Run WSL commands from a script file in the scratchpad (`$` is mangled inline); start with `MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash <script>`.
- Before any port run in a fresh worktree: `make emu-cf` and `python3 tools/verify/stems_fixture.py`.
- `make check REMIX=stems > log; echo $?` style: never read make's result through a pipe.
- Disassemble what you assemble when anything surprises you: `m68k-elf-objdump -d out/platform/runtime/runtime.elf`.
- Addresses of `stems_*` symbols move with every build: read them with `m68k-elf-nm out/platform/runtime/runtime.elf`. The verifier already does (`syms()`).
- Prose in docs follows the Microsoft style guide: short sentences, every term defined, no spaced dashes, markers ✅ 🟡 ❌.
- Raw routines (C calling convention, arguments pushed right to left, call through the pointer): open `*(0x46c8242a)(path, mode)` → handle 1..511 or negative; sector write `*(0x46c82402)(handle, buffer, sectors)` → negative on error; seek `*(0x46c8243e)(handle, offset)`; set length `*(0x46c82436)(handle, length)`; close `*(0x46c82422)(handle)`.
- The uncached alias is `address + 0x08000000`. Every processor access to a buffer the card reads goes through it.

---

### Task 1: Measure the raw file routines (the decision gate)

**Files:**
- Modify: `modules/stems/stems.s` (equates, data words, the probe routine, the task loop's probe check)
- Modify: `modules/stems/manifest.py` (a third DRAM region, `stems_buf`)
- Modify: `tools/verify/verify_stems.py` (`port()` gains `mems`; `regions()`; new `probe()`; `main()` runs it)
- Modify: `docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md` (the two amendments)
- Modify: `docs/firmware/STEM_REC.md` (new section 12.1 with the measured results)

**Interfaces:**
- Produces: `RAW_OPEN_PTR`, `RAW_WRITE_PTR`, `RAW_SEEK_PTR`, `RAW_SETLEN_PTR`, `RAW_CLOSE_PTR`, `UNCACHED`, `SBUF_SIZE`, `CHUNK_FRAMES` equates; data words `stems_probe`, `stems_probe_res` (7 longs), `stems_fpath` (PATH_MAX bytes); routine `stems_sbuf` (in: d1 = track slot j; out: a2 = uncached stream buffer j; clobbers d0); DRAM region `stems_buf` of 270,336 bytes; verifier `port(..., mems=())`.

- [ ] **Step 1: Amend the spec.** In section 2, replace the first paragraph with:

```markdown
`stems_tracks` is a word in the module, an 8-bit mask, bit k for track
k+1, default `0x01`. The frame hook latches it at the ARMED → RECORDING
edge, with the count of set bits (`NTRACKS`) and the ring's geometry for
that count. A mask of 0 counts as T1. Every per-track loop below runs over
the latched bits in order, T1 first. A frame in the ring is
`NTRACKS × 64` bytes. (Amended 22 Sep 2026: the build cannot pass
assembler symbols per unit, so the mask is a word a test can poke.)
```

In section 8, replace "A 60-second take" with "A 20-second take (`--long`: past the old 15 s)" and add a line: "**The ring's wrap.** A take started with the ring offsets poked near its end."

- [ ] **Step 2: Add the region.** In `modules/stems/manifest.py`, after `DramRegion("stems_stack", 0x2000)`, add `DramRegion("stems_buf", 270336, align=512),` and add to the module docstring: "The writer's sector buffers are a third region, `stems_buf`: eight 33,280-byte stream buffers and eight 512-byte sector-0 copies."

- [ ] **Step 3: Write the failing test.** In `tools/verify/verify_stems.py`:

Change `port()`'s signature to add `mems=()` after `stack=False`, and after the `if stack:` block add:

```python
    for addr, length, name in mems:
        dumps += f";0x{addr:x},{length}={work / (tag + '.' + name)}"
```

Replace `regions()` with:

```python
def regions(s):
    from remix import platform_build
    lay = json.loads((LAYOUT_DIR / platform_build.LAYOUT).read_text())
    ring, stack, buf = s["stems_ring"], s["stems_stack"], s["stems_buf"]
    check("ring is 4 MiB ending at the reserve ceiling", ring + 0x400000 == lay["ceiling"],
          f"0x{ring:08x} + 4 MiB vs ceiling 0x{lay['ceiling']:08x}")
    check("stack sits just below the ring", stack + 0x2000 <= ring, f"0x{stack:08x}")
    check("sector buffers sit below the stack, 512-aligned", buf + 270336 <= stack and buf % 512 == 0,
          f"0x{buf:08x}")
    check("the runtime's stage ends below the sector buffers", lay["stage_end"] <= buf,
          f"stage end 0x{lay['stage_end']:08x}")
```

Add, after `cardfail()`:

```python
def probe(s):
    """The five raw file routines, measured (STEM_REC.md 12.1). The action
    is called twice before play (arm, then cancel), so the writer task
    exists and is IDLE; stems_probe = 1 makes it run the probe once. The
    probe writes <set>/PROBE.BIN: sectors 0xAA 0xAA 0xAA with one raw
    write, then 0xBB with a second (does the position advance?), then a
    seek to 0 and 0xCC over sector 0, then length 1000, then close."""
    import emu_card
    res = s["stems_probe_res"]
    pokes = [(s["stems_probe"] + 3, 1)]
    log, _, card, _, _ = port(s, 300, tag="probe", pokes=pokes, dump_blocks=False,
                              mems=((res, 28, "res"),),
                              calls_before=(s["stems_action"], s["stems_action"]))
    raw = (pathlib.Path("out/stems_runs") / "probe.res").read_bytes() if \
        (pathlib.Path("out/stems_runs") / "probe.res").exists() else b"\0" * 28
    r = [int.from_bytes(raw[i:i + 4], "big", signed=True) for i in range(0, 28, 4)]
    check("probe: raw open returned a handle", 1 <= r[0] <= 511, f"d0 {r[0]}")
    check("probe: raw write of 3 sectors", r[1] >= 0, f"d0 {r[1]}")
    check("probe: raw write of 1 more sector", r[2] >= 0, f"d0 {r[2]}")
    check("probe: raw seek to 0", r[3] >= 0, f"d0 {r[3]}")
    check("probe: raw write over sector 0", r[4] >= 0, f"d0 {r[4]}")
    check("probe: set length 1000", r[5] >= 0, f"d0 {r[5]}")
    check("probe: raw close", r[6] >= 0, f"d0 {r[6]}")
    fx = json.loads(FIXTURE.read_text())
    data = emu_card.read_file(card.read_bytes(), f"/{fx['set']}/PROBE.BIN")
    check("probe: the file is exactly 1000 bytes (set length, shorter than written)",
          data is not None and len(data) == 1000, f"{None if data is None else len(data)} bytes")
    if data is not None and len(data) == 1000:
        check("probe: sector 0 is the rewrite (seek + write)", data[:512] == b"\xcc" * 512,
              f"first bytes {data[:4].hex()}")
        check("probe: sector 1 survived the rewrite, and the position advanced",
              data[512:1000] == b"\xaa" * 488, f"bytes 512.. {data[512:516].hex()}")
```

`port()` needs `calls_before`: add the parameter `calls_before=None` and replace the `"--call-before-play", f"0x{s['stems_action']:x}:0",` argument with:

```python
            "--call-before-play", ",".join(f"0x{a:x}:0" for a in (calls_before or (s["stems_action"],))),
```

In `main()`, add `probe(s)` right after `regions(s)` (before `tap(s)`), inside the same block that runs the port checks.

- [ ] **Step 4: Run it to see it fail.** Sync `tools/verify/verify_stems.py` and `modules/stems/manifest.py` to the worktree, then:

```bash
cd /home/yvez/xcheck/wt && make bus REMIX=stems > /home/yvez/xcheck/t1.log 2>&1; echo "bus $?"
python3 tools/verify/verify_stems.py stems > /home/yvez/xcheck/t1v.log 2>&1; echo "vs $?"; grep -E "FAIL|probe" /home/yvez/xcheck/t1v.log
```

Expected: `KeyError: 'stems_probe_res'` or FAIL lines for the probe: the symbols don't exist yet.

- [ ] **Step 5: Implement the probe.** In `modules/stems/stems.s`:

Add to the stock facts, after `ATA_RET`:

```asm
        .equ    RAW_OPEN_PTR,  0x46c8242a   | -> open(path, mode) -> handle 1..511, <0 error (STEM_REC.md 12.1)
        .equ    RAW_WRITE_PTR, 0x46c82402   | -> write(handle, buf, sectors) <0 error      (12.1)
        .equ    RAW_SEEK_PTR,  0x46c8243e   | -> seek(handle, offset)                       (12.1)
        .equ    RAW_SETLEN_PTR,0x46c82436   | -> setlen(handle, length)                     (12.1)
        .equ    RAW_CLOSE_PTR, 0x46c82422   | -> close(handle)                              (12.1)
        .equ    UNCACHED,      0x08000000   | the same RAM, data cache bypassed (PLAN.md, "The RAM")
```

Add to the constants:

```asm
        .equ    CHUNK_FRAMES,  512          | frames per write while recording
        .equ    SBUF_SIZE,     CHUNK_FRAMES*64+512   | one track's stream buffer: a chunk plus a carry
        .equ    SEC0_BASE,     8*SBUF_SIZE  | the sector-0 copies follow the eight stream buffers
```

Add to the state, after `stems_path:      .space  PATH_MAX`:

```asm
stems_fpath:     .space  PATH_MAX
        .global stems_probe, stems_probe_res
stems_probe:     .long   0          | test seam: non-zero runs stems_probe_run once
stems_probe_res: .space  28         | d0 of open, write 3, write 1, seek 0, write 1, setlen, close
probe_name:      .asciz  "/PROBE.BIN"
        .balign 2
```

Add after `stems_task_create`'s `.Lc_fail` block:

```asm
| ---- stream buffer j, uncached: d1 = j in, a2 = its address out -------
| Clobbers d0 only.
stems_sbuf:
        move.l  #SBUF_SIZE,%d0
        mulu.l  %d1,%d0
        movea.l %d0,%a2
        adda.l  #stems_buf+UNCACHED,%a2
        rts

| ---- the raw file routines, measured (a test seam; STEM_REC.md 12.1) -----
| Runs in the task when stems_probe is non-zero. Writes <set>/PROBE.BIN:
| three 0xAA sectors in one write, one 0xBB sector in a second write, a
| seek to 0, one 0xCC sector over sector 0, length 1000, close. Each
| routine's d0 goes to stems_probe_res, in that order.
        .macro  RAWCALL ptr
        movea.l \ptr,%a0
        jsr     (%a0)
        .endm
stems_probe_run:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        lea     stems_probe_res,%a0
        moveq   #7,%d0
.Lq_clr:
        clr.l   (%a0)+
        subq.l  #1,%d0
        bne.s   .Lq_clr
        lea     SET_PATH,%a0        | <set>/PROBE.BIN
        lea     stems_fpath,%a1
.Lq_set:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lq_set
        subq.l  #1,%a1
        lea     probe_name,%a0
.Lq_name:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lq_name
        moveq   #0,%d1              | stream buffer 0: AA AA AA BB CC
        bsr.w   stems_sbuf
        movea.l %a2,%a0
        move.l  #0xaaaaaaaa,%d0
        move.l  #384,%d1
.Lq_a:  move.l  %d0,(%a0)+
        subq.l  #1,%d1
        bne.s   .Lq_a
        move.l  #0xbbbbbbbb,%d0
        move.l  #128,%d1
.Lq_b:  move.l  %d0,(%a0)+
        subq.l  #1,%d1
        bne.s   .Lq_b
        move.l  #0xcccccccc,%d0
        move.l  #128,%d1
.Lq_c:  move.l  %d0,(%a0)+
        subq.l  #1,%d1
        bne.s   .Lq_c
        pea     MODE_W
        pea     stems_fpath
        RAWCALL RAW_OPEN_PTR
        addq.l  #8,%sp
        move.l  %d0,stems_probe_res
        move.l  %d0,%d2             | the handle
        ble.w   .Lq_out
        pea     3
        move.l  %a2,-(%sp)
        move.l  %d2,-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        move.l  %d0,stems_probe_res+4
        pea     1
        pea     1536(%a2)
        move.l  %d2,-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        move.l  %d0,stems_probe_res+8
        clr.l   -(%sp)
        move.l  %d2,-(%sp)
        RAWCALL RAW_SEEK_PTR
        addq.l  #8,%sp
        move.l  %d0,stems_probe_res+12
        pea     1
        pea     2048(%a2)
        move.l  %d2,-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        move.l  %d0,stems_probe_res+16
        pea     1000
        move.l  %d2,-(%sp)
        RAWCALL RAW_SETLEN_PTR
        addq.l  #8,%sp
        move.l  %d0,stems_probe_res+20
        move.l  %d2,-(%sp)
        RAWCALL RAW_CLOSE_PTR
        addq.l  #4,%sp
        move.l  %d0,stems_probe_res+24
.Lq_out:
        movem.l (%sp),%d2-%d3/%a2
        lea     12(%sp),%sp
        rts
```

In `stems_task`, right after `addq.l  #8,%sp` that follows `jsr K_DELAY`, insert:

```asm
        tst.l   stems_probe
        beq.s   .Lt_noprobe
        bsr.w   stems_probe_run
        clr.l   stems_probe
        bra.s   .Lt_loop
.Lt_noprobe:
```

- [ ] **Step 6: Run the test.** Sync `modules/stems/stems.s`, then run Step 4's commands again. Expected: every `probe:` line PASS, and every earlier check still PASS.

**Decision gate.** If any `probe:` line fails, STOP. Record what the routine did in STEM_REC.md 12.1 and bring it to Yves before Task 2. Do not work around it.

- [ ] **Step 7: Record the measurement.** Append to `docs/firmware/STEM_REC.md`:

```markdown
## 12. Streaming

### 12.1 The raw file routines, measured under the port ✅

Each call below went through the file layer's pointer, from STEM REC's
writer task, with the arguments the buffered layer uses (7.10): open
`(path, mode)`, sector write `(handle, buffer, sectors)`, seek `(handle,
offset)`, set length `(handle, length)`, close `(handle)`. The buffer was
addressed through the uncached alias. `verify_stems.py`'s `probe()` runs it.

| Step | Result |
|---|---|
| open `<set>/PROBE.BIN`, `"w"` | handle <FILL FROM RUN: r[0]> |
| write 3 sectors of `0xAA` | <r[1]> |
| write 1 sector of `0xBB` | <r[2]> |
| seek to 0 | <r[3]> |
| write 1 sector of `0xCC` | <r[4]> |
| set length 1000 | <r[5]> |
| close | <r[6]> |

The file read back from the card image is 1,000 bytes: sector 0 is `0xCC`,
and bytes 512 to 999 are `0xAA`. So the raw write advances the file's
position by itself, a seek to 0 then a one-sector write replaces sector 0
and leaves the rest, and set length sets the exact length, both below what
was written and above the position after the rewrite.
```

Replace each `<…>` with the value the run printed (the check lines show `d0 N`). These are measured values, not placeholders to leave.

- [ ] **Step 8: Commit.**

```bash
git add modules/stems/stems.s modules/stems/manifest.py tools/verify/verify_stems.py docs/firmware/STEM_REC.md docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md
git commit -m "stems: measure the five raw file routines under the port before streaming depends on them -- STEM_REC 12.1"
```

---

### Task 2: The streaming core

Replaces the hook's single-track copy, the byte-counted ring, the action's arming, and the write-after-stop writer. After this task STEM REC streams T1, and every existing check passes in its new form.

**Files:**
- Modify: `modules/stems/stems.s` (whole file below)
- Modify: `tools/verify/verify_stems.py` (`tap`, `full`, `rowstop`, `exists`, `overflow`, `cardfail`, `limit`; new `stream`, `wrap`, `cap`)

**Interfaces:**
- Consumes: Task 1's equates, `stems_sbuf`, `RAWCALL`, `stems_probe_run`, region `stems_buf`.
- Produces: state words in this order at `stems_state`: state, status, task_made, wr (frames the hook wrote), rd (frames the task took), frames (= wr). New words: `stems_tracks` (mask, default 1), `stems_hold`, `stems_mask`, `stems_nt`, `stems_fbytes`, `stems_rframes`, `stems_rlimit`, `stems_wr_off`, `stems_rd_off`. Files: `<set>/AUDIO/YYMMDD-HHMM/T<n>.wav`.

- [ ] **Step 1: Write the failing tests.** In `tools/verify/verify_stems.py`, add the constants after `STACK_LIMIT`:

```python
RING_SIZE_T1 = 0x400000            # T1 only: 65,536 frames of 64 bytes
MAX_FRAMES = 9922500               # 60 minutes
CHUNK_FRAMES = 512
```

Add `stream()`, `wrap()` and `cap()` after `rowstop()`:

```python
def stream(s):
    """A take long enough to cross three chunks: the task must write while
    the take runs. The write watch logs the state words; a write to rd
    (word 4) before the first FINISHING is a write during the take."""
    log, dump, card, words, _ = port(s, 1900, stop_at=1700, tag="stream", extra=watched(s))
    st, status, _, wr, rd, nfr = words
    ws = writes(s, log)
    fin = next((x for x, w, v in ws if w == 0 and v == ST_FINISHING), None)
    mid = [x for x, w, v in ws if w == 4 and fin is not None and x < fin]
    check("stream: the task wrote during the take", len(mid) >= 2, f"{len(mid)} rd writes before FINISHING")
    check("stream: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    check("stream: the task drained every frame", nfr > 3 * CHUNK_FRAMES and rd == wr,
          f"rd {rd}, wr {wr}, frames {nfr}")
    wav_check(card, nfr, dump, "stream")


def wrap(s):
    """The ring's offsets poked to three frames before its end (T1: frames
    are 64 bytes), after the action has armed: the hook and the task both
    wrap within the take, and the file must still equal the read-back."""
    off = RING_SIZE_T1 - 3 * 64
    pokes = [(s[w] + i, (off >> (24 - 8 * i)) & 0xff)
             for w in ("stems_wr_off", "stems_rd_off") for i in range(4)]
    log, dump, card, words, _ = port(s, 400, stop_at=300, tag="wrap", pokes=pokes)
    st, status, _, wr, rd, nfr = words
    check("wrap: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    wav_check(card, nfr, dump, "wrap")


def cap(s):
    """The 60-minute cap: wr and rd poked to 50 frames short of it after
    the action. The hook must end the take by itself, with no error."""
    v = MAX_FRAMES - 50
    pokes = [(s[w] + i, (v >> (24 - 8 * i)) & 0xff) for w in ("stems_wr", "stems_rd") for i in range(4)]
    log, _, card, words, _ = port(s, 300, tag="cap", pokes=pokes, dump_blocks=False, extra=watched(s))
    st, status, _, wr, rd, nfr = words
    check("cap: the hook ended the take at the cap", wr == MAX_FRAMES and st == ST_IDLE and status == 0,
          f"wr {wr}, state {st}, status {status}")
    data = take(card) or b""
    check("cap: the file holds the 50 frames", len(data) == 44 + 50 * 64, f"{len(data)} bytes")
```

Replace the body of `tap()` from `check("wr is 64 bytes per frame", ...)` to the end with:

```python
    check("wr counts frames", nfr > 0 and wr == nfr, f"wr {wr}, frames {nfr}")
    check("the stop moved RECORDING on", nfr > 0 and st in (ST_IDLE, ST_FINISHING),
          f"state {st}, status {status}")
    # The ring stays big-endian: the task swaps into its own buffers.
    got = [[int.from_bytes(raw[f * 64 + 2 * k:f * 64 + 2 * k + 2], "big", signed=True)
            for k in range(32)] for f in range(nfr)]
    peaks = core1_slot_peaks(dump)
    k1 = T1_OFFSET // 0x80
    check("T1's slot is the only core-1 slot with sound",
          peaks[k1] > 256 and all(p < 64 for i, p in enumerate(peaks) if i != k1),
          f"peaks by slot {peaks}, T1's slot {k1}")
    want = t1_frames(dump)
    lag = next((L for L in range(len(want) - nfr + 1) if want[L:L + nfr] == got), None)
    check("every ring frame equals T1's read-back at one fixed lag", nfr > 0 and lag is not None,
          f"lag {lag} frames (pre-roll {PRE_ROLL})" if lag is not None
          else f"no lag 0..{len(want) - nfr} matches")
    loud = any(any(x) for x in got)
    check("the signal is not silence", loud,
          "non-zero samples present" if loud else f"all {nfr} ring frames are zero")
```

In `full()` and `rowstop()`, replace the `rd {rd}, wr {wr}` drain check with `check(f"{tag}: the task drained every frame", rd == wr == nfr, f"rd {rd}, wr {wr}, frames {nfr}")` (use each function's own label text). In `wav_check()`, the data size check stays `frames × 64`.

Replace `overflow()` with:

```python
def overflow(s):
    """The writer held (stems_hold, a test seam) and the ring made to look
    nearly full after the action: rd poked 65,436 frames behind wr, and
    rd_off 100 frames past wr_off. The hook stops with ERR_OVERFLOW once
    100 frames are in. FINISHING ignores the hold, so the task writes all
    65,536 frames and closes a playable file. A STOP, then the row, arms
    again: the task came back to IDLE."""
    used = 65536 - 100
    rd = (-used) & 0xffffffff
    rd_off = 100 * 64
    pokes = [(s["stems_hold"] + 3, 1)]
    pokes += [(s["stems_rd"] + i, (rd >> (24 - 8 * i)) & 0xff) for i in range(4)]
    pokes += [(s["stems_rd_off"] + i, (rd_off >> (24 - 8 * i)) & 0xff) for i in range(4)]
    log, _, card, words, _ = port(s, OVERFLOW_FRAMES, stop_at=OVERFLOW_FRAMES - 400, tag="overflow",
                                  pokes=pokes, dump_blocks=False,
                                  calls=((OVERFLOW_FRAMES - 200, s["stems_action"]),),
                                  extra=watched(s, span=24))
    st, status, _, wr, rd_end, _ = words
    ws = writes(s, log, span=24)
    statuses = [v for x, w, v in ws if w == 1]
    states = [v for x, w, v in ws if w == 0]
    wrs = [v for x, w, v in ws if w == 3]
    check("overflow: the hook stopped with ERR_OVERFLOW", ERR_OVERFLOW in statuses,
          f"status writes {statuses}")
    check("overflow: 100 frames, then the guard", 100 in wrs and 101 not in wrs, f"wr reached {max(wrs, default=0)}")
    data = take(card) or b""
    ok = len(data) >= 44 and int.from_bytes(data[40:44], "little") == len(data) - 44 == 65536 * 64
    check("overflow: the file holds the whole ring and its header agrees", ok,
          f"{len(data)} bytes")
    check("overflow: the task wrote and went IDLE, and the row armed again",
          states[-2:] == [ST_IDLE, ST_ARMED] and st == ST_ARMED, f"state writes {states}, state {st}")
```

`take(card)` stays as it is: it returns the new take's `T1.wav` bytes, or `None`.

Replace `limit()` with:

```python
LIMIT_FRAMES = 55300                     # the --long take: about 20 s, past the old cap of 41,344


def limit(s):
    """A 20-second take, stopped by STOP: past the old 15-second cap. T1's
    ring (65,536 frames) does not wrap in 20 s, so the file's data must equal
    the ring's first frames with each 16-bit word byte-swapped: the ring is
    big-endian, the file little-endian. A sector sent twice or lost keeps
    the size and fails this."""
    import array
    frames = PRE_ROLL + LIMIT_FRAMES + 200
    log, _, card, words, ring = port(s, frames, stop_at=PRE_ROLL + LIMIT_FRAMES, tag="limit",
                                     dump_blocks=False, extra=watched(s), ring_bytes=RING_SIZE_T1)
    st, status, _, wr, rd, nfr = words
    check("limit: past the old cap of 41,344 frames", nfr > 41344, f"{nfr} frames")
    check("limit: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    data = take(card)
    n = 64 * nfr
    dlen = int.from_bytes(data[40:44], "little") if data and len(data) >= 44 else None
    check("limit: the file holds every frame", dlen == n and len(data) == 44 + dlen,
          f"data {dlen}, file {len(data) if data else None}")
    want = array.array("H", ring[:n])
    want.byteswap()
    want = want.tobytes()
    same = data is not None and len(want) == n and data[44:] == want
    bad = None
    if data is not None and not same:
        bad = next((i for i in range(0, min(len(want), len(data) - 44), 512)
                    if data[44 + i:44 + i + 512] != want[i:i + 512]), None)
    check("limit: the file's data is the ring, byte for byte", same,
          "" if same else f"first differing 512-byte block at data offset {bad}")
```

Delete the old module-level `MAX_FRAMES = 41344` (or whatever value the file defines for the old cap) if one exists; the new `MAX_FRAMES` above replaces it.

In `main()`, run `stream(s)`, `wrap(s)` and `cap(s)` after `rowstop(s)`.

- [ ] **Step 2: Run them to see them fail.** Sync `tools/verify/verify_stems.py`, run `python3 tools/verify/verify_stems.py stems`. Expected: `KeyError` on `stems_wr_off` / `stems_hold`, or FAIL lines for `stream`, `wrap`, `cap`.

- [ ] **Step 3: Replace `modules/stems/stems.s` with the streaming core.** The whole file:

```asm
| STEM REC -- the enabled tracks to the card while the sequencer plays.
|
| Design: docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md
| (streaming), over docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md.
| Every stock address below, with its evidence: docs/firmware/STEM_REC.md.
|
| Three parts share the state words below:
|   stems_action      MAIN MENU > CONTROL > STEM REC, in the UI task
|   stems_frame_hook  the per-frame tap, in the audio interrupt at IPL 5
|   stems_task        our own RTOS task: the ring to the card, while recording
| The state is one aligned long, so every read and write of it is one
| instruction. The action and the hook write it; the task writes IDLE, and
| FINISHING when a card write fails.

| ---- stock facts (docs/firmware/STEM_REC.md) ----------------------------
        .equ    TRANSPORT,     0x800065b8   | long; 1 = running, 0 or 2 = stopped (Task 2)
        .equ    TRANSPORT_RUNNING, 1        | the ONLY value that means playing   (Task 2)
        .equ    CARD_MOUNTED,  0x460d1cb8   | long; 0 = no card                   (Task 8)
        .equ    FRAME_ROUTINE, 0x400031a0   | the displaced call
        .equ    MODE_W,        0x400b328b   | "w": opens without truncating
        .equ    PING,          0x800000e0   | the read-back half selector  (Task 3)
        .equ    PING_XOR,      0            | half = (PING ^ PING_XOR) & 1  (Task 3)
        .equ    READBACK,      0x80003190   | track k's block at READBACK + half*0x400 + k*0x80 (9.2)
        .equ    K_CREATE,      0x400005fc   | (tcb, entry, prio, stack, size) -> 1   (Task 4)
        .equ    K_START,       0x4000063c   | (tcb)                                  (Task 4)
        .equ    TCB_SIZE,      84           |                                        (Task 4)
        .equ    K_DELAY,       0x40020c7c   | (us, wait) -> 0; -1 = timer busy, wait 0 (Task 5)
        .equ    K_DELAY_TRY,   0            | wait = 0: never block on the shared timer (Task 5)
        .equ    TASK_SLEEP_US, 10000        | one pass; MICROSECONDS, not ticks       (Task 5)
        .equ    FS_EXISTS_PTR, 0x46c823fa   | -> exists(path): 0 no, 1 file, 2 folder (6.11, 8.0)
        .equ    SET_PATH,      0x100f8480   | the current set's path, a C string in place (Task 6)
        .equ    CLK_READ,      0x4001c4d8   | (field) -> one BCD byte in d0; BLOCKS   (Task 6)
        .equ    BCD2BIN,       0x4001c31c   | (bcd) -> binary                          (Task 6)
        .equ    NAME_FMT,      0x400b77bb   | "%02d%02d%02d-%02d%02d"                  (Task 6)
        .equ    SPRINTF,       0x40013a08   | (buf, fmt, ...)
        .equ    FS_MKDIR_PTR,  0x46c8240a   | -> mkdir(path): 0 ok, <0 failed; call THROUGH it (Task 7)
        .equ    ATA_DATA,      0x900000a0   | the card's data register, 16 bits       (11.7)
        .equ    ATA_PTR,       0x46c8c594   | long; the PIO handler's next sector      (11.7)
        .equ    ATA_LEFT,      0x46c8c592   | byte; the sectors the handler still sends (11.7)
        .equ    ATA_RET,       0x40014d58   | the PIO write routine's return           (11.7)
        .equ    RAW_OPEN_PTR,  0x46c8242a   | -> open(path, mode) -> handle 1..511, <0 error (12.1)
        .equ    RAW_WRITE_PTR, 0x46c82402   | -> write(handle, buf, sectors) <0 error      (12.1)
        .equ    RAW_SEEK_PTR,  0x46c8243e   | -> seek(handle, offset)                       (12.1)
        .equ    RAW_SETLEN_PTR,0x46c82436   | -> setlen(handle, length)                     (12.1)
        .equ    RAW_CLOSE_PTR, 0x46c82422   | -> close(handle)                              (12.1)
        .equ    UNCACHED,      0x08000000   | the same RAM, data cache bypassed (PLAN.md, "The RAM")

| ---- constants -----------------------------------------------------------
        .equ    ST_IDLE,       0
        .equ    ST_ARMED,      1
        .equ    ST_RECORDING,  2
        .equ    ST_FINISHING,  3
        .equ    RING_SIZE,     0x400000     | = DramRegion stems_ring
        .equ    TRACK_BYTES,   64           | one track's frame: 16 stereo 16-bit samples
        .equ    MAX_FRAMES,    9922500      | 60 minutes
        .equ    CHUNK_FRAMES,  512          | frames per write while recording
        .equ    SBUF_SIZE,     CHUNK_FRAMES*64+512   | one track's stream buffer: a chunk plus a carry
        .equ    SEC0_BASE,     8*SBUF_SIZE  | the sector-0 copies follow the eight stream buffers
        .equ    STACK_SIZE,    0x2000       | = DramRegion stems_stack
        .equ    TASK_PRIO,     1
        .equ    PATH_MAX,      256
        .equ    ERR_OVERFLOW,  1
        .equ    ERR_PATH,      2
        .equ    ERR_OPEN,      3
        .equ    ERR_EXISTS,    4
        .equ    ERR_WRITE,     5
        .equ    ERR_SEEK,      6            | the seek in the header fix
        .equ    ERR_CLOSE,     7
        .equ    ERR_TASK,      8
        .equ    STACK_FILL,    0x5354454d   | "STEM": the untouched stack
        .equ    HDR_SIZE,      44

| ColdFire byterev is ISA_A+ and -mcpu=5407 does not accept it, so it is
| encoded by hand: opcode 0x02C0 | reg (SAMPLE_SAVE.md section 3).
        .macro  BYTEREV reg          | reg = 0..7, a data register number
        .short  0x02c0 + \reg
        .endm
        .macro  RAWCALL ptr
        movea.l \ptr,%a0
        jsr     (%a0)
        .endm

        .text

| ---- state -----------------------------------------------------------------
| The first six words are read as one 24-byte dump by verify_stems.py.
        .balign 4
        .global stems_state, stems_status, stems_task_made, stems_wr, stems_rd, stems_frames
stems_state:     .long   ST_IDLE
stems_status:    .long   0          | the last error, 0 = none
stems_task_made: .long   0
stems_wr:        .long   0          | frames the hook has put in the ring
stems_rd:        .long   0          | frames the task has taken out
stems_frames:    .long   0          | frames recorded (= stems_wr)
        .global stems_tracks, stems_hold, stems_wr_off, stems_rd_off, stems_probe, stems_probe_res
stems_tracks:    .long   0x01       | the track mask, bit k = track k+1; latched at the start
stems_hold:      .long   0          | test seam: non-zero pauses the writer while RECORDING
stems_mask:      .long   0          | the latched mask
stems_nt:        .long   0          | its bit count
stems_fbytes:    .long   0          | a ring frame: 64 x stems_nt
stems_rframes:   .long   0          | the ring's capacity in frames
stems_rlimit:    .long   0          | stems_rframes x stems_fbytes: offsets wrap here
stems_wr_off:    .long   0          | the hook's next frame, a byte offset into the ring
stems_rd_off:    .long   0          | the task's next frame
stems_nopen:     .long   0          | files open
stems_wfail:     .long   0          | a card write failed: finish without writing more
stems_handle:    .space  32         | one per open file, in track order
stems_slen:      .space  32         | bytes waiting in each stream buffer
stems_fpos:      .space  32         | bytes of each file on the card
stems_tcb:       .space  TCB_SIZE   | zero until the one create (STEM_REC.md 3.8)
stems_probe:     .long   0          | test seam: non-zero runs stems_probe_run once
stems_probe_res: .space  28
stems_name:      .space  16         | YYMMDD-HHMM
stems_path:      .space  PATH_MAX   | <set>/AUDIO/<name>
stems_fpath:     .space  PATH_MAX   | <set>/AUDIO/<name>/T<n>.wav
| The ring's capacity and wrap point for 1 to 8 tracks: whole frames only.
rframes_tab:
        .long   RING_SIZE/64, RING_SIZE/128, RING_SIZE/192, RING_SIZE/256
        .long   RING_SIZE/320, RING_SIZE/384, RING_SIZE/448, RING_SIZE/512
rlimit_tab:
        .long   (RING_SIZE/64)*64, (RING_SIZE/128)*128, (RING_SIZE/192)*192, (RING_SIZE/256)*256
        .long   (RING_SIZE/320)*320, (RING_SIZE/384)*384, (RING_SIZE/448)*448, (RING_SIZE/512)*512
| The 44-byte header, little-endian as RIFF wants, sizes 0: the placeholder
| every file starts with. The real sizes go into the sector-0 copy at the end.
stems_hdr:
        .ascii  "RIFF"
        .long   0
        .ascii  "WAVEfmt "
        .byte   16,0,0,0            | fmt chunk size
        .byte   1,0                 | PCM
        .byte   2,0                 | stereo
        .byte   0x44,0xac,0,0       | 44,100
        .byte   0x10,0xb1,0x02,0    | 176,400 bytes per second
        .byte   4,0                 | block align
        .byte   16,0                | bits
        .ascii  "data"
        .long   0
fmt_dir:   .asciz  "/AUDIO/%s"
fmt_file:  .asciz  "/T%d.wav"
probe_name: .asciz "/PROBE.BIN"
        .balign 2

| ---- the menu row -------------------------------------------------------
        .global stems_label, stems_zero
        .equ    stems_zero, 0       | the row's window, pad, child and id
stems_label:
        .asciz  "STEM REC"
        .balign 2

| ---- the menu action: action(0), in the UI task ------------------------
| IDLE arms: the hook starts the take at the first playing frame, which is
| the next frame if the sequencer already plays. ARMED cancels. RECORDING
| stops. FINISHING is ignored. Arming resets the counters and the ring's
| offsets; a test may poke them afterwards (the port's pokes land after
| this call).
        .global stems_action
stems_action:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        tst.l   CARD_MOUNTED        | no card: do nothing at all
        beq.s   .La_out
        tst.l   stems_task_made     | the writer task, created once (STEM_REC.md 3.8)
        bne.s   .La_made
        bsr.w   stems_task_create   | d0 = 1 when the task exists
        tst.l   %d0
        beq.w   .La_out             | could not create it: stay IDLE
        moveq   #1,%d0
        move.l  %d0,stems_task_made
.La_made:
        move.w  %sr,%d2
        move.w  #0x2700,%sr         | no frame hook between read and write
        move.l  stems_state,%d0
        tst.l   %d0
        bne.s   .La_busy
        clr.l   stems_wr            | IDLE: a fresh take
        clr.l   stems_rd
        clr.l   stems_frames
        clr.l   stems_status
        clr.l   stems_wr_off
        clr.l   stems_rd_off
        moveq   #ST_ARMED,%d1
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
| Reached by `jsr` from 0x40004b12. Calls nothing but the routine it
| displaced; uses no RTOS service; loops are bounded (8 tracks). In IDLE its
| whole cost is one test and one branch. The copy runs BEFORE the stock
| routine, which reads the same block.
        .global stems_frame_hook
stems_frame_hook:
        tst.l   stems_state
        beq.w   .Lh_stock           | IDLE
        lea     -36(%sp),%sp
        movem.l %d0-%d5/%a0-%a2,(%sp)
        move.l  stems_state,%d0
        moveq   #ST_FINISHING,%d1
        cmp.l   %d1,%d0
        beq.w   .Lh_out             | FINISHING: the hook adds nothing
        move.l  TRANSPORT,%d2       | running iff exactly 1 (Task 2)
        subq.l  #TRANSPORT_RUNNING,%d2   | Z set while the sequencer plays
        moveq   #ST_ARMED,%d1
        cmp.l   %d1,%d0
        bne.s   .Lh_rec
        tst.l   %d2                 | ARMED
        bne.w   .Lh_out             | still stopped (0 or 2)
        bsr.w   stems_layout        | latch the mask and the ring's geometry
        moveq   #ST_RECORDING,%d0   | the first playing frame is recorded
        move.l  %d0,stems_state
        bra.s   .Lh_copy
.Lh_rec:                            | RECORDING
        tst.l   %d2
        beq.s   .Lh_copy
        moveq   #ST_FINISHING,%d0   | the sequencer stopped: 0 (end, rewind) or 2 (STOP key)
        move.l  %d0,stems_state
        bra.w   .Lh_out
.Lh_copy:
        move.l  stems_wr,%d0
        sub.l   stems_rd,%d0        | frames in the ring
        cmp.l   stems_rframes,%d0
        bcs.s   .Lh_room            | fewer than capacity: one more fits
        moveq   #ERR_OVERFLOW,%d0   | the card fell behind: stop at the last whole frame
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
        addi.l  #READBACK,%d4       | this half's T1 block
        movea.l stems_wr_off,%a1
        adda.l  #stems_ring,%a1
        move.l  stems_mask,%d3
        moveq   #0,%d5              | track k's offset, k * 0x80
.Lh_trk:
        lsr.l   #1,%d3              | C = track k's bit
        bcc.w   .Lh_next
        movea.l %d4,%a0
        adda.l  %d5,%a0
| Each sample is one long on the host port: its top 16 bits, then its low
| 8 bits shifted up. Keep the top halves of L and R as one long.
        .rept   16
        move.l  (%a0)+,%d0          | L
        move.l  (%a0)+,%d1          | R
        swap    %d1
        move.w  %d1,%d0             | L top 16 : R top 16
        move.l  %d0,(%a1)+
        .endr
.Lh_next:
        addi.l  #0x80,%d5
        tst.l   %d3
        bne.w   .Lh_trk
        move.l  stems_wr_off,%d0
        add.l   stems_fbytes,%d0
        cmp.l   stems_rlimit,%d0
        bcs.s   .Lh_nowrap
        moveq   #0,%d0
.Lh_nowrap:
        move.l  %d0,stems_wr_off
        move.l  stems_wr,%d0
        addq.l  #1,%d0
        move.l  %d0,stems_wr        | publish after the data
        move.l  %d0,stems_frames
        cmpi.l  #MAX_FRAMES,%d0
        bcs.s   .Lh_out
        moveq   #ST_FINISHING,%d0   | the 60-minute cap
        move.l  %d0,stems_state
.Lh_out:
        movem.l (%sp),%d0-%d5/%a0-%a2
        lea     36(%sp),%sp
.Lh_stock:
        jsr     FRAME_ROUTINE
        move.w  #0x2700,%sr
        rts

| ---- the layout, latched at the start edge (in the hook) ---------------
| Uses d0, d1 and a0 only. Offsets poked past this layout's wrap go to 0.
stems_layout:
        move.l  stems_tracks,%d0
        andi.l  #0xff,%d0
        bne.s   .Ll_some
        moveq   #1,%d0              | no track: T1
.Ll_some:
        move.l  %d0,stems_mask
        moveq   #0,%d1
.Ll_pop:
        lsr.l   #1,%d0
        bcc.s   .Ll_zero
        addq.l  #1,%d1
.Ll_zero:
        tst.l   %d0
        bne.s   .Ll_pop
        move.l  %d1,stems_nt
        move.l  %d1,%d0
        lsl.l   #6,%d0
        move.l  %d0,stems_fbytes
        lea     rframes_tab,%a0
        move.l  -4(%a0,%d1.l*4),%d0
        move.l  %d0,stems_rframes
        lea     rlimit_tab,%a0
        move.l  -4(%a0,%d1.l*4),%d0
        move.l  %d0,stems_rlimit
        cmp.l   stems_wr_off,%d0
        bhi.s   .Ll_wr
        clr.l   stems_wr_off
.Ll_wr:
        cmp.l   stems_rd_off,%d0
        bhi.s   .Ll_rd
        clr.l   stems_rd_off
.Ll_rd:
        rts

| ---- the stock PIO write's first sector (docs/firmware/STEM_REC.md 11.7) --
| Reached by `jmp` from 0x40014cfe, in the task that issued a WRITE SECTORS,
| once the card has asked for data. Stock streams the first sector, then
| advances the interrupt handler's data pointer and sector count, with
| interrupts enabled: a card interrupt taken between the two runs the
| handler on the stale pair, which either sends a sector twice or leaves
| the handler waiting, masked, for a sector the card never asks for. This
| does the same work in the safe order. The card cannot interrupt for this
| command until the whole sector is in, so the handler always finds the
| pair already advanced. Registers as stock: d0, d1 and a0.
        .global stems_ata_first
stems_ata_first:
        movea.l ATA_PTR,%a0         | this sector (the displaced instruction)
        move.l  %a0,%d1
        addi.l  #512,%d1
        move.l  %d1,ATA_PTR         | the handler's next sector
        move.b  ATA_LEFT,%d0
        subq.l  #1,%d0
        move.b  %d0,ATA_LEFT        | the sectors the handler still sends
.Lw_word:
        move.w  (%a0)+,%d0
        move.w  %d0,ATA_DATA
        cmp.l   %a0,%d1
        bne.s   .Lw_word
        jmp     ATA_RET             | stock: return the count

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

| ---- buffers: d1 = slot j in; a2 (stream buffer) or a0 (sector-0 copy) out
| Both uncached: the card may read them by DMA (STEM_REC.md 11.8).
stems_sbuf:                         | clobbers d0
        move.l  #SBUF_SIZE,%d0
        mulu.l  %d1,%d0
        movea.l %d0,%a2
        adda.l  #stems_buf+UNCACHED,%a2
        rts
stems_sec0:                         | clobbers d0
        move.l  %d1,%d0
        lsl.l   #8,%d0
        add.l   %d0,%d0             | j * 512
        movea.l %d0,%a0
        adda.l  #stems_buf+UNCACHED+SEC0_BASE,%a0
        rts

| ---- the task ------------------------------------------------------------
| Wakes every TASK_SLEEP_US. Owns the files. While RECORDING it makes the
| files at the first wake, then writes whole chunks as they fill. At
| FINISHING it writes the rest, fixes each header, and goes IDLE.
| K_DELAY(us, wait): C order, so wait is pushed first (STEM_REC.md 4.4).
stems_task:
.Lt_loop:
        pea     K_DELAY_TRY
        pea     TASK_SLEEP_US
        jsr     K_DELAY             | d0 = -1 when the timer was busy: just loop
        addq.l  #8,%sp
        tst.l   stems_probe
        beq.s   .Lt_noprobe
        bsr.w   stems_probe_run
        clr.l   stems_probe
        bra.s   .Lt_loop
.Lt_noprobe:
        move.l  stems_state,%d0
        moveq   #ST_RECORDING,%d1
        cmp.l   %d1,%d0
        beq.s   .Lt_rec
        moveq   #ST_FINISHING,%d1
        cmp.l   %d1,%d0
        bne.s   .Lt_loop            | IDLE or ARMED
        tst.l   stems_nopen
        bne.s   .Lt_fin
        move.l  stems_wr,%d0
        cmp.l   stems_rd,%d0
        beq.s   .Lt_idle            | stopped before a frame: no files
        bsr.w   stems_start
        tst.l   %d0
        bmi.s   .Lt_drop
.Lt_fin:
        bsr.w   stems_finish
.Lt_idle:
        clr.l   stems_state
        bra.s   .Lt_loop
.Lt_rec:
        tst.l   stems_hold
        bne.s   .Lt_loop            | test seam: hold the writer
        tst.l   stems_nopen
        bne.s   .Lt_drain
        bsr.w   stems_start
        tst.l   %d0
        bmi.s   .Lt_drop
.Lt_drain:
        move.l  #CHUNK_FRAMES,%d1
        bsr.w   stems_drain         | whole chunks only while recording
        tst.l   %d0
        bpl.w   .Lt_loop
        moveq   #ST_FINISHING,%d0   | a write failed: stop, keep what reached the card
        move.l  %d0,stems_state
        bra.w   .Lt_loop
.Lt_drop:                           | no files could be made: drop the take
        clr.l   stems_state
        move.l  stems_wr,%d0
        move.l  %d0,stems_rd
        bra.w   .Lt_loop

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

| ---- the folder path: <set>/AUDIO/<name> ------------------------------
| set = the C string at SET_PATH, used exactly as the stock save uses it
| (STEM_REC.md 5.8). d0 = 0, or -1 (empty, or too long).
stems_make_folder:
        lea     SET_PATH,%a0
        lea     stems_path,%a1
        move.l  #PATH_MAX-40,%d1    | room for /AUDIO/name/T8.wav
.Lp_copy:
        move.b  (%a0)+,%d0
        beq.s   .Lp_end
        move.b  %d0,(%a1)+
        subq.l  #1,%d1
        bne.s   .Lp_copy
        bra.s   .Lp_fail            | the set path is too long
.Lp_end:
        clr.b   (%a1)
        move.l  %a1,%d0
        sub.l   #stems_path,%d0
        beq.s   .Lp_fail            | an empty set path: no set mounted
        pea     stems_name
        pea     fmt_dir
        move.l  %a1,-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        moveq   #0,%d0
        rts
.Lp_fail:
        moveq   #-1,%d0
        rts

| ---- a file path: stems_path + /T<k+1>.wav, k in d3 ---------------------
stems_make_file:
        lea     stems_path,%a0
        lea     stems_fpath,%a1
.Lm_copy:
        move.b  (%a0)+,(%a1)+
        bne.s   .Lm_copy
        subq.l  #1,%a1
        move.l  %d3,%d0
        addq.l  #1,%d0
        move.l  %d0,-(%sp)
        pea     fmt_file
        move.l  %a1,-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        rts

| ---- start: name, folder, one file per latched track ---------------------
| d0 = 0 with every file open, or -1 with stems_status set and none open.
stems_start:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        clr.l   stems_nopen
        clr.l   stems_wfail
        bsr.w   stems_make_name
        bsr.w   stems_make_folder
        tst.l   %d0
        bmi.w   .Ls_path
        movea.l FS_EXISTS_PTR,%a0   | same minute as an earlier take: refuse
        pea     stems_path
        jsr     (%a0)
        addq.l  #4,%sp
        tst.l   %d0
        bne.w   .Ls_exists
        movea.l FS_MKDIR_PTR,%a0    | an error is left to the opens
        pea     stems_path
        jsr     (%a0)
        addq.l  #4,%sp
        move.l  stems_mask,%d2
        moveq   #0,%d3              | track k
.Ls_trk:
        lsr.l   #1,%d2
        bcc.w   .Ls_next
        bsr.w   stems_make_file
        pea     MODE_W
        pea     stems_fpath
        RAWCALL RAW_OPEN_PTR
        addq.l  #8,%sp
        tst.l   %d0
        ble.w   .Ls_open
        move.l  stems_nopen,%d1     | slot j
        lea     stems_handle,%a0
        move.l  %d0,(%a0,%d1.l*4)
        lea     stems_fpos,%a0
        clr.l   (%a0,%d1.l*4)
        lea     stems_slen,%a0
        moveq   #HDR_SIZE,%d0
        move.l  %d0,(%a0,%d1.l*4)   | the stream starts with the placeholder header
        bsr.w   stems_sbuf
        lea     stems_hdr,%a0
        moveq   #HDR_SIZE/4,%d0
.Ls_hdr:
        move.l  (%a0)+,(%a2)+
        subq.l  #1,%d0
        bne.s   .Ls_hdr
        addq.l  #1,stems_nopen
.Ls_next:
        addq.l  #1,%d3
        tst.l   %d2
        bne.w   .Ls_trk
        moveq   #0,%d0
        bra.s   .Ls_out
.Ls_open:
        moveq   #ERR_OPEN,%d0
        move.l  %d0,stems_status
        bsr.w   stems_close_all
        moveq   #-1,%d0
        bra.s   .Ls_out
.Ls_path:
        moveq   #ERR_PATH,%d0
        move.l  %d0,stems_status
        moveq   #-1,%d0
        bra.s   .Ls_out
.Ls_exists:
        moveq   #ERR_EXISTS,%d0
        move.l  %d0,stems_status
        moveq   #-1,%d0
.Ls_out:
        movem.l (%sp),%d2-%d3/%a2
        lea     12(%sp),%sp
        rts

| ---- close every open file, as they are -----------------------------------
stems_close_all:
        move.l  %d2,-(%sp)
        moveq   #0,%d2
.Lx_trk:
        cmp.l   stems_nopen,%d2
        bcc.s   .Lx_done
        lea     stems_handle,%a0
        move.l  (%a0,%d2.l*4),-(%sp)
        RAWCALL RAW_CLOSE_PTR
        addq.l  #4,%sp
        addq.l  #1,%d2
        bra.s   .Lx_trk
.Lx_done:
        clr.l   stems_nopen
        move.l  (%sp)+,%d2
        rts

| ---- drain: frames from the ring into the stream buffers, then sectors -----
| d1 = CHUNK_FRAMES: whole chunks only (recording). d1 = 1: everything.
| d0 = 0, or -1 with ERR_WRITE set and stems_wfail = 1.
stems_drain:
        lea     -24(%sp),%sp
        movem.l %d2-%d5/%a2-%a3,(%sp)
        move.l  %d1,%d5             | the smallest batch worth taking
.Ld_more:
        move.l  stems_wr,%d2
        sub.l   stems_rd,%d2        | frames waiting
        cmp.l   %d5,%d2
        bcs.w   .Ld_done
        cmpi.l  #CHUNK_FRAMES,%d2
        bls.s   .Ld_batch
        move.l  #CHUNK_FRAMES,%d2
.Ld_batch:
        moveq   #0,%d3              | frame within the batch
.Ld_frame:
        movea.l stems_rd_off,%a3
        adda.l  #stems_ring,%a3
        moveq   #0,%d4              | slot j
.Ld_trk:
        move.l  %d4,%d1
        bsr.w   stems_sbuf          | a2 = stream buffer j
        lea     stems_slen,%a0
        move.l  (%a0,%d4.l*4),%d0
        adda.l  %d0,%a2
        addi.l  #TRACK_BYTES,%d0
        move.l  %d0,(%a0,%d4.l*4)
        moveq   #16,%d1
.Ld_s:                              | [L1 L0 R1 R0] -> [L0 L1 R0 R1]
        move.l  (%a3)+,%d0
        BYTEREV 0
        swap    %d0
        move.l  %d0,(%a2)+
        subq.l  #1,%d1
        bne.s   .Ld_s
        addq.l  #1,%d4
        cmp.l   stems_nt,%d4
        bcs.s   .Ld_trk
        move.l  stems_rd_off,%d0
        add.l   stems_fbytes,%d0
        cmp.l   stems_rlimit,%d0
        bcs.s   .Ld_nowrap
        moveq   #0,%d0
.Ld_nowrap:
        move.l  %d0,stems_rd_off
        addq.l  #1,%d3
        cmp.l   %d2,%d3
        bcs.s   .Ld_frame
        add.l   %d2,stems_rd        | the hook may reuse these frames now
        moveq   #0,%d4
.Ld_flush:
        move.l  %d4,%d1
        moveq   #0,%d0              | whole sectors only
        bsr.w   stems_flush
        tst.l   %d0
        bmi.s   .Ld_err
        addq.l  #1,%d4
        cmp.l   stems_nt,%d4
        bcs.s   .Ld_flush
        bra.w   .Ld_more
.Ld_done:
        moveq   #0,%d0
        bra.s   .Ld_out
.Ld_err:
        moveq   #-1,%d0
.Ld_out:
        movem.l (%sp),%d2-%d5/%a2-%a3
        lea     24(%sp),%sp
        rts

| ---- flush slot d1's whole sectors; with d0 != 0, pad the tail first ------
| The file's first sector is kept in the sector-0 copy. d0 = 0, or -1.
stems_flush:
        lea     -20(%sp),%sp
        movem.l %d2-%d4/%a2-%a3,(%sp)
        move.l  %d1,%d4             | slot j
        move.l  %d0,%d3             | pad?
        bsr.w   stems_sbuf          | a2 = stream buffer j
        lea     stems_slen,%a3
        move.l  (%a3,%d4.l*4),%d2   | bytes waiting
        tst.l   %d3
        beq.s   .Lf_whole
        move.l  %d2,%d0
        andi.l  #511,%d0
        beq.s   .Lf_whole
        neg.l   %d0
        addi.l  #512,%d0            | zeros to the sector's end
        lea     (%a2,%d2.l),%a0
        add.l   %d0,%d2
.Lf_zero:
        clr.b   (%a0)+
        subq.l  #1,%d0
        bne.s   .Lf_zero
.Lf_whole:
        move.l  %d2,%d3
        lsr.l   #8,%d3
        lsr.l   #1,%d3              | whole sectors
        beq.w   .Lf_ok
        move.l  %d3,-(%sp)
        move.l  %a2,-(%sp)
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        tst.l   %d0
        bmi.s   .Lf_err
        lea     stems_fpos,%a3
        tst.l   (%a3,%d4.l*4)
        bne.s   .Lf_moved
        move.l  %d4,%d1             | the file's first sector: keep a copy
        bsr.w   stems_sec0
        movea.l %a2,%a1
        move.l  #128,%d1
.Lf_c0:
        move.l  (%a1)+,(%a0)+
        subq.l  #1,%d1
        bne.s   .Lf_c0
.Lf_moved:
        move.l  %d3,%d1
        lsl.l   #8,%d1
        add.l   %d1,%d1             | bytes written
        add.l   %d1,(%a3,%d4.l*4)
        sub.l   %d1,%d2             | the carry: 0 to 511 bytes
        lea     (%a2,%d1.l),%a0
        movea.l %a2,%a1
        move.l  %d2,%d0
        beq.s   .Lf_set
.Lf_mv:
        move.b  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne.s   .Lf_mv
.Lf_set:
        lea     stems_slen,%a3
        move.l  %d2,(%a3,%d4.l*4)
.Lf_ok:
        moveq   #0,%d0
        bra.s   .Lf_out
.Lf_err:
        moveq   #ERR_WRITE,%d0
        move.l  %d0,stems_status
        moveq   #1,%d0
        move.l  %d0,stems_wfail
        moveq   #-1,%d0
.Lf_out:
        movem.l (%sp),%d2-%d4/%a2-%a3
        lea     20(%sp),%sp
        rts

| ---- finish: the rest, then per file the header, the length, close -------
stems_finish:
        lea     -16(%sp),%sp
        movem.l %d2-%d4/%a2,(%sp)
        tst.l   stems_wfail
        bne.s   .Lz_files
        moveq   #1,%d1
        bsr.w   stems_drain         | everything left
.Lz_files:
        moveq   #0,%d4
.Lz_trk:
        cmp.l   stems_nopen,%d4
        bcc.w   .Lz_done
        lea     stems_fpos,%a0
        move.l  (%a0,%d4.l*4),%d2   | on the card
        tst.l   stems_wfail
        bne.s   .Lz_len
        lea     stems_slen,%a0
        add.l   (%a0,%d4.l*4),%d2   | + the carry: the exact length
        move.l  %d4,%d1
        moveq   #1,%d0
        bsr.w   stems_flush         | the carry, padded
        tst.l   %d0
        bpl.s   .Lz_len
        lea     stems_fpos,%a0
        move.l  (%a0,%d4.l*4),%d2   | the carry failed: what is on the card
.Lz_len:
        move.l  %d2,%d3
        subi.l  #HDR_SIZE,%d3       | data bytes
        bpl.s   .Lz_pos
        moveq   #0,%d3
.Lz_pos:
        andi.l  #-4,%d3
        moveq   #HDR_SIZE,%d2
        add.l   %d3,%d2             | the length: 44 + data
        lea     stems_fpos,%a0
        tst.l   (%a0,%d4.l*4)
        beq.w   .Lz_close           | nothing on the card: no header to fix
        move.l  %d4,%d1
        bsr.w   stems_sec0
        movea.l %a0,%a2
        move.l  %d3,%d0
        BYTEREV 0
        move.l  %d0,40(%a2)         | data size, little-endian
        moveq   #36,%d0
        add.l   %d3,%d0
        BYTEREV 0
        move.l  %d0,4(%a2)          | RIFF size = 36 + data
        clr.l   -(%sp)
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_SEEK_PTR
        addq.l  #8,%sp
        tst.l   %d0
        bmi.s   .Lz_seekerr
        pea     1
        move.l  %a2,-(%sp)
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_WRITE_PTR
        lea     12(%sp),%sp
        tst.l   %d0
        bmi.s   .Lz_werr
.Lz_setlen:
        move.l  %d2,-(%sp)
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_SETLEN_PTR
        addq.l  #8,%sp
        tst.l   %d0
        bmi.s   .Lz_cerr
.Lz_close:
        lea     stems_handle,%a0
        move.l  (%a0,%d4.l*4),-(%sp)
        RAWCALL RAW_CLOSE_PTR
        addq.l  #4,%sp
        tst.l   %d0
        bpl.s   .Lz_next
        moveq   #ERR_CLOSE,%d0
        move.l  %d0,stems_status
.Lz_next:
        addq.l  #1,%d4
        bra.w   .Lz_trk
.Lz_seekerr:
        moveq   #ERR_SEEK,%d0
        move.l  %d0,stems_status
        bra.s   .Lz_setlen
.Lz_werr:
        moveq   #ERR_WRITE,%d0
        move.l  %d0,stems_status
        bra.s   .Lz_setlen
.Lz_cerr:
        moveq   #ERR_CLOSE,%d0
        move.l  %d0,stems_status
        bra.s   .Lz_close
.Lz_done:
        clr.l   stems_nopen
        clr.l   stems_wfail
        movem.l (%sp),%d2-%d4/%a2
        lea     16(%sp),%sp
        rts
```

Then append Task 1's `stems_probe_run` routine unchanged (it now uses the `RAWCALL` macro defined at the top; delete the macro definition that sat above it in Task 1).

- [ ] **Step 4: Assemble and read it back.** Sync `modules/stems/stems.s`, run `make bus REMIX=stems`. Then `m68k-elf-objdump -d out/platform/runtime/runtime.elf | less` and check four spots by eye: every `(%aN,%dN.l*4)` disassembles as `%aN@(0,%dN:l:4)`; `-4(%a0,%d1.l*4)` as `%a0@(-4,%d1:l:4)`; each `BYTEREV 0` as `.short 0x02c0`; no branch was relaxed into something unexpected. Fix any operand the assembler rejects by using the MIT form it prints.

- [ ] **Step 5: Run the verifier.** `python3 tools/verify/verify_stems.py stems > log; echo $?`. Expected: every check PASS, including `probe:`, `stream:`, `wrap:`, `cap:`, `overflow:`, `cardfail:`. If `cardfail` changes (the refused write now comes from the raw write, not the buffered flush), confirm the hang is still in the driver's DRQ poll at `0x40014cf4` and update only its label text.

- [ ] **Step 6: Gates.** `make check REMIX=stems > log; echo $?` = 0, and `REMIX=stems python3 tools/verify/verify_dram_boot.py` PASS.

- [ ] **Step 7: Commit.**

```bash
git add modules/stems/stems.s tools/verify/verify_stems.py
git commit -m "stems: stream the take to the card while it records -- raw file routines, a latched track mask, the ring in whole frames, the header fixed at the end"
```

---

### Task 3: Eight tracks under the port

**Files:**
- Modify: `tools/verify/stems_fixture.py` (a `build8()` for an 8-track fixture, written to `out/stems_fixture8.json` and `out/stems_fixture8_card.img`)
- Modify: `tools/verify/verify_stems.py` (`port()` takes a fixture path; new `eight()`)

**Interfaces:**
- Consumes: `stems_tracks` (poked to `0xFF`), `take(card)` returning `[(name, bytes)]` in track order, `wav_check` logic.
- Produces: `stems_fixture.build8()`; verifier `eight(s)`.

- [ ] **Step 1: Write the fixture.** In `tools/verify/stems_fixture.py`, add:

```python
SOUNDS8 = ("kick", "snare", "hat", "clap", "stab", "bass", "melody", "click")
FIXTURE8_JSON = ROOT / "out" / "stems_fixture8.json"
CARD8_OUT = ROOT / "out" / "stems_fixture8_card.img"
SCRATCH8 = ROOT / "out" / "task_s8" / "fixture_src"


def build8(project_dir=DEFAULT_PROJECT):
    """Every track FLEX on its own slot (T<n> plays slot n, sound SOUNDS8[n-1]),
    a trig on step 1 of every pattern, FX1 and FX2 SEND, banks 1 and 2. No
    NEIGHBOR machine anywhere, so each read-back slot is its own track."""
    import shutil
    project_dir = pathlib.Path(project_dir)
    if SCRATCH8.exists():
        shutil.rmtree(SCRATCH8)
    SCRATCH8.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(project_dir, SCRATCH8)
    for bank in FIXTURE_BANKS:
        for part in (1, 2, 3, 4):
            for t in range(1, 9):
                ot_project.set_machine_type(SCRATCH8, bank, part, t, FLEX_MTYPE, mirror=True, guard=False)
        for part in range(1, 9):
            for t in range(1, 9):
                ot_project.set_track_slot(SCRATCH8, bank, part, t, t, kind="flex")
        for pat in range(16):
            for t in range(8):
                ot_project.set_pattern_trig(SCRATCH8, bank, pat, t, 1, guard=False)
    for t in range(1, 9):
        ot_project.set_fx(SCRATCH8, "fx1", t, "SEND", guard=False)
        ot_project.set_fx(SCRATCH8, "fx2", t, "SEND", guard=False)
    for n, snd in reversed(list(enumerate(SOUNDS8, start=1))):
        _add_sample_slot(SCRATCH8 / "project.work", n, snd)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_audio.py"), *SOUNDS8],
                   check=True, cwd=str(ROOT))
    audio = [f"{ROOT / 'out' / 'test_audio' / (snd + '.wav')}:AUDIO/{snd}.wav" for snd in SOUNDS8]
    card_bytes, name = emu_rtos.stage_project(SCRATCH8, SET_NAME, PROJECT_NAME, audio=audio)
    CARD8_OUT.write_bytes(card_bytes)
    result = {"card": str(CARD8_OUT), "set": SET_NAME, "project": name, "staged": [s + ".wav" for s in SOUNDS8]}
    FIXTURE8_JSON.write_text(json.dumps(result, indent=2) + "\n")
    print(f"card:    {result['card']}")
    return result
```

and change the `__main__` block to call `build8()` when the first argument is `--eight`, `build()` otherwise.

- [ ] **Step 2: Write the failing test.** In `tools/verify/verify_stems.py`, give `port()` a `fixture=FIXTURE` parameter and replace `json.loads(FIXTURE.read_text())` in it with `json.loads(pathlib.Path(fixture).read_text())`. Then add:

```python
FIXTURE8 = pathlib.Path("out/stems_fixture8.json")


def take_files(card_path, fixture=FIXTURE):
    """Every .wav in the one new take folder, as [(name, bytes)] sorted by
    name (T1 first), or [] when there is not exactly one new folder."""
    import emu_card as ec
    img = pathlib.Path(card_path).read_bytes()
    fx = json.loads(pathlib.Path(fixture).read_text())
    audio = f"/{fx['set']}/AUDIO"
    names = [n for n in (ec.list_dir(img, audio) or []) if n not in fx.get("staged", [])]
    if len(names) != 1:
        return []
    folder = f"{audio}/{names[0]}"
    wavs = sorted(n for n in (ec.list_dir(img, folder) or []) if n.upper().endswith(".WAV"))
    return [(n, ec.read_file(img, f"{folder}/{n}")) for n in wavs]


def slot_frames(dump_path, k):
    """Track k's (0-based) 16-bit stereo frames from a --block-dump, like t1_frames."""
    import blockdump
    ram_for = (0x80003190, 0x80003590) if k < 4 else (0x80003390, 0x80003790)
    base = (k % 4) * 0x40
    out = []
    for d, frame, ch, core, ram, w in blockdump.read(dump_path):
        if ram in ram_for and d == READBACK_DIR:
            out.append((frame, [x - 65536 if x >= 32768 else x for x in w[base:base + 64:2]]))
    return [s for _, s in sorted(out)]


def eight(s):
    """stems_tracks = 0xFF after the action: eight files, each equal to its
    own read-back slot at one fixed lag, and no two alike."""
    if not FIXTURE8.exists():
        check("eight: the 8-track fixture exists (stems_fixture.py --eight)", False)
        return
    pokes = [(s["stems_tracks"] + 3, 0xff)]
    log, dump, card, words, _ = port(s, 400, stop_at=300, tag="eight", pokes=pokes, fixture=FIXTURE8)
    st, status, _, wr, rd, nfr = words
    check("eight: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    files = take_files(card, FIXTURE8)
    check("eight: eight files, T1 to T8", [n.upper() for n, _ in files] == [f"T{i}.WAV" for i in range(1, 9)],
          f"{[n for n, _ in files]}")
    datas = []
    for k, (name, data) in enumerate(files[:8]):
        got = [[int.from_bytes(data[44 + f * 64 + 2 * j:44 + f * 64 + 2 * j + 2], "little", signed=True)
                for j in range(32)] for f in range((len(data) - 44) // 64)]
        want = slot_frames(dump, k)
        lag = next((L for L in range(len(want) - len(got) + 1) if want[L:L + len(got)] == got), None)
        check(f"eight: {name} equals track {k + 1}'s read-back at one fixed lag", lag is not None and got,
              f"lag {lag}")
        datas.append(data[44:])
    check("eight: no two files alike", len(set(datas)) == len(datas), f"{len(set(datas))} distinct of {len(datas)}")
```

Add `eight(s)` to `main()` after `cap(s)`.

- [ ] **Step 3: Run it to see it fail.** Sync both files; run `python3 tools/verify/verify_stems.py stems`. Expected: `eight: the 8-track fixture exists` FAIL.

- [ ] **Step 4: Build the fixture and run again.** `python3 tools/verify/stems_fixture.py --eight`, then the verifier. Expected: every `eight:` check PASS. If "no two files alike" fails because some sounds are silent in their first frames, replace those sounds in `SOUNDS8` with ones that start loud, and say which in the commit message.

- [ ] **Step 5: Commit.**

```bash
git add tools/verify/stems_fixture.py tools/verify/verify_stems.py
git commit -m "verify_stems: eight tracks under the port -- a fixture with a sound per track, each file equal to its own slot"
```

---

### Task 4: The hook's cost, and the 20-second take

**Files:**
- Modify: `docs/firmware/STEM_REC.md` (section 12.2)

- [ ] **Step 1: Measure.** Read the current addresses: `m68k-elf-nm out/platform/runtime/runtime.elf | grep -E "stems_(frame_hook|layout|action|state|tracks)"`. Run section 10.0's tap command twice with `--coverage`, once as is and once adding `--poke <stems_tracks+3>=255` with the 8-track fixture's card. Sum the hit counts of every address from `stems_frame_hook` to `stems_layout` (the hook ends where `stems_layout` begins) and divide by the frames recorded (`stems_frames` from the mem dump). That is the hook's instructions per recording frame.

- [ ] **Step 2: The 20-second take.** `python3 tools/verify/verify_stems.py stems --long > log; echo $?` (about 20 minutes of wall time). Expected: every `limit` check PASS.

- [ ] **Step 3: Write section 12.2.** Append to `docs/firmware/STEM_REC.md`:

```markdown
### 12.2 The hook's cost, and a take past 15 s ✅

Instructions per recording frame, from `--coverage` over the hook
(`stems_frame_hook` to `stems_layout`), section 10.0's method:

| Tracks | Instructions per frame |
|---|---|
| 1 (T1) | <the measured number> |
| 8 | <the measured number> |

These are instruction counts, not cycles. The hook's time on the unit is
not measured.

A 20-second take (`verify_stems.py --long`): <frames> frames, past the old
cap of 41,344, and the file's data equals the ring byte for byte.
```

Fill each `<…>` with the measured value.

- [ ] **Step 4: Commit.**

```bash
git add docs/firmware/STEM_REC.md
git commit -m "STEM_REC 12.2: the hook's cost at 1 and 8 tracks, and a 20-second take"
```

---

### Task 5: Documents and the flash

**Files:**
- Modify: `docs/firmware/STEM_REC.md` (section 12.0, the design as built)
- Modify: `modules/stems/README.md`, `modules/stems/manifest.py` (docstring)
- Modify: `docs/remixer/FAILURE_MODES.md` (the STEM REC block)
- Modify: `docs/effects/FLASHPLAN.md` (Flash 13)
- Modify: `docs/firmware/CROSSCHECK.md` (one line under "What changed")

- [ ] **Step 1: STEM_REC 12.0.** Insert before `### 12.1`:

```markdown
### 12.0 The design as built

Spec: `docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md`.

- The take is written while it records. Each enabled track gets its own
  file, `<set>/AUDIO/YYMMDD-HHMM/T<n>.wav`, 16-bit stereo.
- `stems_tracks` is the track mask, default `0x01` (T1). The frame hook
  latches it when the take starts.
- The ring holds whole frames of `64 × tracks` bytes, and its offsets wrap
  at the last whole frame.
- The writer drains the ring in 512-frame chunks while recording, and the
  rest at the end.
- It writes through the raw file routines (12.1) from its own buffers. It
  never touches the shared staging buffer `0x4ecd3000`, so 7.5a's race no
  longer involves STEM REC.
- The processor reaches those buffers only through the uncached alias, so
  a DMA write reads what was written (11.8).
- At the end, the writer rewrites each file's sector 0 with the real
  header, sets the exact length, and closes.
- A take ends at STOP, at STEM REC, or at 60 minutes. If the card falls
  behind and the ring fills, the take stops at the last whole frame with
  status 1, and its files still play.
```

- [ ] **Step 2: README and manifest docstring.** Replace every statement that the take is written after it stops, that it is limited to 15 s, or that STEM REC uses the buffered file API, with the streaming behavior. Keep the timer do-not. Remove the staging-buffer do-not for STEM REC, and say why (it no longer uses that buffer).

- [ ] **Step 3: FAILURE_MODES.** In the STEM REC block: delete "No file after a power cut or a card pull during a take" and "The file appears some seconds after the stop", and add:

```markdown
### A take ends early with no error shown

**Symptom.** A take stops by itself before STEM REC or the sequencer
stopped it. Its files play but are shorter than the performance.

**Cause.** Predicted. The card fell behind and the 4 MiB ring filled, so
the take stopped at the last whole frame (status 1, overflow), or the take
reached the 60-minute cap (status 0). Streaming spec, section 1.

**First check.** The status word under the port, or the take's length: 60
minutes is the cap. A slow or nearly full card is the likely cause of an
overflow.

### After a power cut or a card pull, a take's files have a placeholder header

**Symptom.** A take's `Tn.wav` files exist but show zero length or won't
open in a DAW.

**Cause.** Known, by design. The audio is streamed while recording, and the
real header is written at the end. A take cut off before the end keeps its
audio on the card with the placeholder header (sizes 0).

**Fix.** Recover the audio as raw 16-bit stereo, 44.1 kHz, little-endian,
skipping the first 44 bytes.
```

In "A take with foreign bytes in it, or a bank that loads wrong after a take", add a first line: "**Retired for STEM REC's streaming build** (22 Sep 2026): STEM REC no longer uses the shared buffer. Kept for the tag 27 image and for stock's own saves."

- [ ] **Step 4: FLASHPLAN Flash 13.** Rewrite the Flash 13 header line and first paragraph for the streaming image: built from `crosscheck` at this plan's last commit, `make image REMIX=stems BUILD=<next free tag>` (Yves builds it; the hashes are his to record). Replace do-not 2 with: "STEM REC no longer uses the shared staging buffer (STEM_REC.md 12.0). Stock's own saves still share it with each other, as in stock." Replace test 1 with: "**Record at least 60 s** with Flex machines only, stopped with STEM REC. **Report:** the folder name and the unit's clock, `T1.wav`'s length (data bytes = frames × 64), whether it plays whole in a DAW, and any dropout heard live." Keep tests 2 to 4, the PIO patch note, the DMA note, and the CONTROL-row note.

- [ ] **Step 5: CROSSCHECK.** Under "⚠️ Stock saves by itself about 1 s after every STOP", add: "**Resolved for STEM REC** by the streaming build (spec `2026-09-22-stem-rec-streaming-design.md`): STEM REC writes through the raw file routines from its own buffers and never touches `0x4ecd3000`."

- [ ] **Step 6: Final gates.** In the worktree, after syncing every changed file: `make check REMIX=stems > log; echo $?` = 0; `python3 tools/verify/verify_stems.py stems` all PASS; `REMIX=stems python3 tools/verify/verify_dram_boot.py` PASS.

- [ ] **Step 7: Commit.**

```bash
git add docs/firmware/STEM_REC.md modules/stems/README.md modules/stems/manifest.py docs/remixer/FAILURE_MODES.md docs/effects/FLASHPLAN.md docs/firmware/CROSSCHECK.md
git commit -m "docs: STEM REC streams -- STEM_REC 12.0, README, FAILURE_MODES, Flash 13 restaged for the streaming image"
```
