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
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, "tools/scratch")   # blockdump.py lives here (t1_frames, below)
BASE = 0x40000400
IMAGE = pathlib.Path("out/mainos_bus.bin")
STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
RUNTIME_ELF = pathlib.Path("out/platform/runtime/runtime.elf")
LAYOUT_DIR = pathlib.Path("out/platform")      # platform_build.LAYOUT lives here, by name
CONTROL_DESC, CONTROL_ROWS, ROW_LEN, STOCK_N = 0x400cbd54, 0x400cc5a8, 24, 6
FRAME_SITE = 0x40004b12

# Task 11's interface (STEM_REC.md section 9.4): T1's slot in the read-back
# half, and the direction char blockdump.py's summary prints for that class.
READBACK_DIR = "<"
T1_OFFSET = 0x100

EMU = pathlib.Path("out/emu/ot_emu")
FIXTURE = pathlib.Path("out/stems_fixture.json")   # written by tools/verify/stems_fixture.py
KEY_STOP = 0x4000a1e0
STOP_GATE = 0x80000029     # the STOP handler returns early while this byte is 0 (STEM_REC.md 1.6)
PRE_ROLL = 40              # frames before the transport start; the dump includes them
ST_IDLE, ST_ARMED, ST_RECORDING, ST_FINISHING = 0, 1, 2, 3   # stems.s
STACK_SIZE, STACK_FILL = 0x2000, 0x5354454d                   # stems.s: DramRegion stems_stack, "STEM"
STACK_LIMIT = 6 * 1024     # above this, the plan raises the stack to 16 KB before a flash

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
    from remix import platform_build
    lay = json.loads((LAYOUT_DIR / platform_build.LAYOUT).read_text())
    ring, stack = s["stems_ring"], s["stems_stack"]
    check("ring is 4 MiB ending at the reserve ceiling", ring + 0x400000 == lay["ceiling"],
          f"0x{ring:08x} + 4 MiB vs ceiling 0x{lay['ceiling']:08x}")
    check("stack sits just below the ring", stack + 0x2000 <= ring, f"0x{stack:08x}")
    check("the runtime's stage ends below the stack", lay["stage_end"] <= stack,
          f"stage end 0x{lay['stage_end']:08x}")


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


def port(s, frames, stop_at=None, extra=(), tag="run", ring_bytes=0, calls=(), pokes=(),
         card_in=None, dump_blocks=True, stack=False):
    """One fixture run under the port: the module's action called before
    play (`--call-before-play`: the action arms, and the hook takes the
    ARMED-to-RECORDING edge on the first playing frame), STOP at `stop_at`
    (None = no STOP), any further `calls` as (frame, addr), any `pokes` as
    (addr, byte) applied after the load. A run that calls STOP also sets
    STOP_GATE to 1: the port starts the transport without the PLAY key, and
    on the fixture's project that leaves the STOP handler's gate shut, so
    the call would do nothing (Task 10). Dumps the six state words and, when
    `ring_bytes`, the start of the ring. Returns (log text, dump, card,
    state words, ring bytes). `card_in` replaces the fixture's card (Task 16:
    a second take on the first take's card). `dump_blocks=False` drops the
    block dump, which a run of tens of thousands of frames cannot afford.
    `stack=True` also dumps the writer task's 8 KB stack to <tag>.stack.

    `--call-before-play` beside `--pre-roll` needs the port fixed on 13 Sep
    2026 (`main.cpp` runs to main's spin before the call; STEM_REC.md 10.1).
    An older port refuses the call, prints the refusal and records nothing,
    so `tap()` checks the call's own report line before anything else."""
    fx = json.loads(FIXTURE.read_text())
    work = pathlib.Path("out/stems_runs"); work.mkdir(parents=True, exist_ok=True)
    dump, card = work / f"{tag}.dump", work / f"{tag}.img"
    mem, ring = work / f"{tag}.mem", work / f"{tag}.ring"
    dumps = f"0x{s['stems_state']:x},24={mem}"
    if ring_bytes:
        dumps += f";0x{s['stems_ring']:x},{ring_bytes}={ring}"
    if stack:
        dumps += f";0x{s['stems_stack']:x},{STACK_SIZE}={work / (tag + '.stack')}"
    at = [f"{f}:0x{a:x}:0" for f, a in calls]
    pk = list(pokes)
    if stop_at is not None:
        at.append(f"{stop_at}:0x{KEY_STOP:x}:0")
        pk.append((STOP_GATE, 1))
    args = [str(EMU), "--image", str(IMAGE), "--card", card_in or fx["card"], "--set", fx["set"],
            "--project", fx["project"], "--sequencer", "--internal-clock",
            "--frames", str(frames), "--load-ms", "20000", "--dsp", "--main-level", "64",
            "--pre-roll", str(PRE_ROLL), "--poke-trig", "2",
            *(["--block-dump", str(dump)] if dump_blocks else []),
            "--call-before-play", f"0x{s['stems_action']:x}:0",
            "--card-out", str(card), "--mem-dump", dumps, *extra]
    if at:
        args += ["--at", ",".join(at)]
    if pk:
        args += ["--poke", ";".join(f"0x{a:x}={b}" for a, b in pk)]
    r = subprocess.run(args, capture_output=True, text=True)
    (work / f"{tag}.log").write_text(r.stdout + r.stderr)   # the port's report, for the call timing
    m = mem.read_bytes() if mem.exists() else b"\0" * 24
    words = [int.from_bytes(m[i:i + 4], "big") for i in range(0, 24, 4)]
    return (r.stdout + r.stderr, dump, card, words,
            ring.read_bytes() if ring_bytes and ring.exists() else b"")


def tap(s):
    log, dump, _, words, raw = port(s, 400, stop_at=300, tag="tap", ring_bytes=64 * 400)
    st, status, _, wr, rd, nfr = words
    armed = [l for l in log.splitlines() if l.startswith("call") and "before play" in l]
    check("the action was called before play", any("-> returned" in l for l in armed),
          armed[0].strip() if armed else "no call line in the port's report")
    check("the hook recorded frames", nfr > 200, f"{nfr} frames, wr {wr}")
    # Every check below needs frames: with none, "equal at a fixed lag" and
    # "64 bytes per frame" are true of an empty ring, which is how the first
    # RED run of this task passed three of them.
    check("wr is 64 bytes per frame", nfr > 0 and wr == 64 * nfr, f"{wr} vs {64 * nfr}")
    check("the stop moved RECORDING on", nfr > 0 and st in (ST_IDLE, ST_FINISHING),
          f"state {st}, status {status}")
    # The hook stores big-endian. Once the take has stopped, the task swaps
    # each run to little-endian in place before it writes it, and stems_rd
    # counts the bytes it has swapped and written. So frames below rd are
    # little-endian and the rest big-endian.
    got = [[int.from_bytes(raw[f * 64 + 2 * k:f * 64 + 2 * k + 2],
                           "little" if f * 64 < rd else "big", signed=True)
            for k in range(32)] for f in range(nfr)]
    want = t1_frames(dump)
    lag = next((L for L in range(len(want) - nfr + 1) if want[L:L + nfr] == got), None)
    check("every ring frame equals T1's read-back at one fixed lag", nfr > 0 and lag is not None,
          f"lag {lag} frames (pre-roll {PRE_ROLL})" if lag is not None
          else f"no lag 0..{len(want) - nfr} matches")
    loud = any(any(x) for x in got)
    check("the signal is not silence", loud,
          "non-zero samples present" if loud else f"all {nfr} ring frames are zero")


def wav_check(card_path, nfr, dump, tag):
    """The take on the card: one new folder in the set's AUDIO folder, its
    T1.wav with the header STEM REC writes, and every sample equal to T1's
    read-back at one fixed lag."""
    import emu_card as ec
    img = pathlib.Path(card_path).read_bytes()
    fx = json.loads(FIXTURE.read_text())
    audio = f"/{fx['set']}/AUDIO"
    names = [n for n in (ec.list_dir(img, audio) or []) if n not in fx.get("staged", [])]
    check(f"{tag}: one new recording in {audio}", len(names) == 1, f"{names}")
    if not names:
        return
    path = f"{audio}/{names[0]}/T1.wav"
    data = ec.read_file(img, path)
    check(f"{tag}: {path} exists", data is not None)
    if data is None:
        return
    if len(data) < 44:
        check(f"{tag}: the file holds a header", False, f"{len(data)} bytes")
        return
    riff, size, wave_, fmt, flen, pcm, ch, rate, brate, align, bits, dtag, dlen = \
        struct.unpack_from("<4sI4s4sIHHIIHH4sI", data, 0)
    check(f"{tag}: header fields", (riff, wave_, fmt, flen, pcm, ch, rate, brate, align, bits, dtag) ==
          (b"RIFF", b"WAVE", b"fmt ", 16, 1, 2, 44100, 176400, 4, 16, b"data"))
    check(f"{tag}: data size = frames x 64", nfr > 0 and dlen == 64 * nfr, f"{dlen} vs {64 * nfr}")
    check(f"{tag}: RIFF size = 36 + data", size == 36 + dlen, f"{size}")
    check(f"{tag}: file length = 44 + data", len(data) == 44 + dlen, f"{len(data)}")
    if len(data) < 44 + 64 * nfr:
        check(f"{tag}: every sample equals T1's read-back at one fixed lag", False, "file too short")
        return
    got = [list(struct.unpack_from("<32h", data, 44 + 64 * f)) for f in range(nfr)]
    want = t1_frames(dump)
    lag = next((L for L in range(len(want) - nfr + 1) if want[L:L + nfr] == got), None)
    check(f"{tag}: every sample equals T1's read-back at one fixed lag", nfr > 0 and lag is not None,
          f"lag {lag} frames (pre-roll {PRE_ROLL})")


def full(s):
    """Armed before play, STOP at 400, and 300 frames for the task to write
    the take."""
    log, dump, card, words, _ = port(s, 700, stop_at=400, tag="full", stack=True)
    st, status, made, wr, rd, nfr = words
    raw = pathlib.Path("out/stems_runs/full.stack")
    if raw.exists():
        longs = [int.from_bytes(raw.read_bytes()[i:i + 4], "big") for i in range(0, STACK_SIZE, 4)]
        untouched = next((i for i, w in enumerate(longs) if w != STACK_FILL), len(longs))
        peak = STACK_SIZE - 4 * untouched
        check(f"full: the writer's stack peak is at most {STACK_LIMIT} bytes", 0 < peak <= STACK_LIMIT,
              f"{peak} of {STACK_SIZE} bytes used")
    check("full: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    check("full: the task drained everything", nfr > 0 and rd == wr, f"rd {rd}, wr {wr}")
    wav_check(card, nfr, dump, "full")
    return log, words


def rowstop(s):
    """Armed before play, stopped from the row at frame 200 while the
    sequencer plays on to the STOP at 400: the task writes the take while
    the sequencer is still running."""
    log, dump, card, words, _ = port(s, 700, stop_at=400, tag="rowstop",
                                     calls=((200, s["stems_action"]),))
    st, status, made, wr, rd, nfr = words
    check("rowstop: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    check("rowstop: the row stopped it near frame 200", 150 < nfr < 260, f"{nfr} frames")
    wav_check(card, nfr, dump, "rowstop")


ERR_OVERFLOW, ERR_EXISTS, ERR_WRITE = 1, 4, 5
RING_SIZE = 0x400000
DRIVER_DRQ_POLL = 0x40014cf4             # the stock write command's wait for DRQ (STEM_REC.md 11.4)
OVERFLOW_FRAMES = 4000                   # the task writes the whole 4 MiB ring after the guard


def watched(s, extra=(), span=8):
    """--watch-mem on the state words from stems_state on, `span` bytes:
    every write, in order, so a run can see a value the next arm clears.
    8 covers the state and the status; 24 adds the write index and the
    frame count, which the hook writes every frame."""
    return ("--watch-mem", f"0x{s['stems_state']:x},{span}", *extra)


def writes(s, log, span=8):
    """(sample, word, value) for every watched write: word 0 = state,
    1 = status, 3 = stems_wr, 5 = stems_frames."""
    out = []
    for l in log.splitlines():
        if "] <- " not in l or "[0x" not in l:
            continue
        try:
            sample = float(l.split("[", 1)[1].split("]", 1)[0])
            addr = int(l.split("[0x", 1)[1].split("]", 1)[0], 16)
            val = int(l.split("<- ", 1)[1].split()[0], 0)
        except ValueError:
            continue
        if s["stems_state"] <= addr < s["stems_state"] + span:
            out.append((sample, (addr - s["stems_state"]) // 4, val))
    return out


def take(card_path):
    """The one new take's T1.wav on a card, or None."""
    import emu_card as ec
    img = pathlib.Path(card_path).read_bytes()
    fx = json.loads(FIXTURE.read_text())
    audio = f"/{fx['set']}/AUDIO"
    names = [n for n in (ec.list_dir(img, audio) or []) if n not in fx.get("staged", [])]
    return ec.read_file(img, f"{audio}/{names[0]}/T1.wav") if len(names) == 1 else None


def exists(s):
    """A second take on the first take's card, in the same minute: refused,
    and the first take is untouched. Every port take is 000000-0000 (the
    port's clock reads 0, STEM_REC.md 11.2), so the minute is the same."""
    first = pathlib.Path("out/stems_runs/full.img")
    if not first.exists():
        print("  [SKIP] exists: needs the full run's card")
        return
    before = take(first)
    log, _, card, words, _ = port(s, 700, stop_at=400, tag="exists", card_in=str(first),
                                  dump_blocks=False)
    st, status, _, wr, rd, nfr = words
    check("exists: refused with ERR_EXISTS, state IDLE", st == ST_IDLE and status == ERR_EXISTS,
          f"state {st}, status {status}")
    after = take(card)
    check("exists: the first take is byte-identical", before is not None and after == before,
          f"{len(before) if before else None} bytes before, {len(after) if after else None} after")


def overflow(s):
    """The ring made to look nearly full: stems_rd poked so wr - rd is
    RING_SIZE - 6400 plus what the hook has written. The hook stops with
    ERR_OVERFLOW once 100 frames are in; the task then writes what it
    believes is there (the whole ring) and closes. A STOP, then the row,
    arms again: the task came back to IDLE."""
    rd = (-(RING_SIZE - 6400)) & 0xffffffff
    pokes = [(s["stems_rd"] + i, (rd >> (24 - 8 * i)) & 0xff) for i in range(4)]
    log, _, card, words, _ = port(s, OVERFLOW_FRAMES, stop_at=OVERFLOW_FRAMES - 400, tag="overflow",
                                  pokes=pokes, dump_blocks=False,
                                  calls=((OVERFLOW_FRAMES - 200, s["stems_action"]),),
                                  extra=watched(s, span=24))
    st, status, _, wr, rd_end, _ = words
    ws = writes(s, log, span=24)
    nfr = max((v for x, w, v in ws if w == 5), default=0)   # the re-arm clears the count
    statuses = [v for x, w, v in ws if w == 1]
    states = [v for x, w, v in ws if w == 0]
    check("overflow: the hook stopped with ERR_OVERFLOW", ERR_OVERFLOW in statuses,
          f"status writes {statuses}")
    check("overflow: 100 frames, then the guard", nfr == 100, f"{nfr} frames")
    fin = next((x for x, w, v in ws if w == 0 and v == ST_FINISHING), None)
    idle = next((x for x, w, v in ws if w == 0 and v == ST_IDLE and fin is not None and x > fin), None)
    if fin is not None and idle is not None:
        print(f"  [ -- ] overflow: the task wrote the whole ring in {(idle - fin) / 16:.0f} frames "
              f"({(idle - fin) / 44100:.2f} s of port time)")
    check("overflow: the task wrote and went IDLE, and the row armed again",
          states[-2:] == [ST_IDLE, ST_ARMED] and st == ST_ARMED, f"state writes {states}, state {st}")


def cardfail(s):
    """Every card write after the 20th is refused, as a card answers an
    aborted command: ERR and ABRT, no DRQ. The stock driver's write command
    waits for DRQ at 0x40014cf4 with no error check and no timeout, so the
    writer task hangs there, holding the file layer's lock (STEM_REC.md
    11.4). This run RECORDS that fact rather than expecting a recovery: a
    change here means the driver's answer, or the port's card model,
    changed."""
    work = pathlib.Path("out/stems_runs")
    cov = work / "cardfail.cov"
    log, _, card, words, _ = port(s, 700, stop_at=400, tag="cardfail", dump_blocks=False,
                                  extra=watched(s, ("--card-fail-after", "20", "--coverage", str(cov))))
    st, status, _, wr, rd, nfr = words
    polls = 0
    if cov.exists():
        polls = next((int(n) for a, n in (l.split() for l in cov.read_text().splitlines())
                      if int(a, 16) == DRIVER_DRQ_POLL), 0)
    sectors = next((l.split("(")[1].split()[0] for l in log.splitlines() if l.startswith("card out")), "?")
    check("cardfail: a refused write hangs the writer in the stock driver's DRQ poll (known)",
          st == ST_FINISHING and sectors == "20" and polls > 100000,
          f"state {st}, {sectors} sectors written, {polls} polls at 0x{DRIVER_DRQ_POLL:x}")


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
    if EMU.exists() and FIXTURE.exists():
        tap(s)
        full(s)
        rowstop(s)
        exists(s)
        overflow(s)
        cardfail(s)
    else:
        print("  [SKIP] port runs: build the port (make emu-cf) and the fixture "
              "(python3 tools/verify/stems_fixture.py)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
