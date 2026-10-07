#!/usr/bin/env python3
"""STEM REC -- the row, the tap and the file, checked without hardware.

    python3 tools/verify/verify_stems.py [remix] [--long] [--fat32] [--static] [--only=NAME,...] [--alone]

Static, from the built image: MAIN MENU has five categories, the four
stock ones byte for byte and STEMS fifth, with its icon and its list;
CONTROL is stock; the STEMS list ships filled in, its eighteen rows with
their actions, headings and labels as at boot; the frame site jumps to the
hook; the ring and the stack sit at the top of the platform reserve, above
the runtime's stage. `--static` stops there; `--only=NAME,...` runs only
the named port runs (their names are main()'s table). Then, when the
port is built, the fixtures are built from the project template
(tools/verify/stems_fixture.py; STEMS_TEMPLATE=<dir>, default
out/projects/Ultimate FX 1.5.3) and the port runs of the proof of concept,
of the streaming plan and of the eight-track plan follow: the mask takes
on the THRU fixture (1, 2, 4 and 8 tracks, and 0xA5). `--long` adds a
20-second take (about 7 minutes under the port, 5 Oct 2026), the masks of
3, 5, 6 and 7 tracks and T8 alone, the mask latched at the start, an
eight-track wrap, an eight-track overflow, eight tracks on a card at half
the speed they need, and everything at 24 bits outrunning the port's card;
it stays out of `make check`. `--fat32` runs the take checks again on a FAT32 card
(`stems_fixture.py --fat32`), after checking the firmware mounted it; it
stays out of `make check` too.

Each check's first run on a fixture shares one boot with the others'
(the port's --scenario: one LOAD PROJECT, a child forked per run), unless
it sets a boot option (PRE_BOOT: a block dump, an audio capture, a write
watch, dirty DSP RAM, a card latency). `--alone` boots every run on its
own, as before; same_as_alone checks the two give the same takes.
"""
import json
import os
import pathlib
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
BASE = 0x40000400
IMAGE = pathlib.Path("out/mainos_bus.bin")
STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
RUNTIME_ELF = pathlib.Path("out/platform/runtime/runtime.elf")
LAYOUT_DIR = pathlib.Path("out/platform")      # platform_build.LAYOUT lives here, by name
CONTROL_DESC, CONTROL_ROWS, ROW_LEN, STOCK_N = 0x400cbd54, 0x400cc5a8, 24, 6
ROOT_DESC, ROOT_ROWS, ROOT_N = 0x400cbd8c, 0x400cc698, 4      # MAIN MENU's root (MAINMENU.md 2)
MENU_ROWS, ROW_TRK0, ROW_PEAK, MENU_VISIBLE = 18, 2, 17, 7     # stems.s: the STEMS list
FRAME_SITE = 0x40004b12
ATA_FIRST_SITE = 0x40014cfe  # the stock PIO write's first sector (STEM_REC.md 11.7)

# Task 11's interface (STEM_REC.md section 9.4): T1's slot in the read-back
# half, and the direction char blockdump.py's summary prints for that class.
# Track k is at k * 0x80 (stock NEIGHBOR 0x400046dc); 0x100 was T3, which the
# old fixture's NEIGHBOR chain filled with a copy of T1 (STEM_REC.md 9.2).
READBACK_DIR = "<"
T1_OFFSET = 0x00

EMU = pathlib.Path("out/emu/ot_emu")
FIXTURE = pathlib.Path("out/stems_fixture.json")   # written by tools/verify/stems_fixture.py
# The fixtures' project: EZBot's "Ultimate FX 1.5.3" template, a local
# project that never enters the repository. A fresh tree has none (the
# shards of `make check-remix-gates` wipe out/), so STEMS_TEMPLATE names it.
TEMPLATE = pathlib.Path(os.environ.get("STEMS_TEMPLATE") or "out/projects/Ultimate FX 1.5.3")
KEY_STOP = 0x4000a1e0
STOP_GATE = 0x80000029     # the STOP handler returns early while this byte is 0 (STEM_REC.md 1.6)
PRE_ROLL = 40              # frames before the transport start; the dump includes them
TRACK_HALF, TRACK_DELAY = 1, 1             # the samples core 0 mixes (STEM_REC.md 18.5)
# A take's first frame is one frame after the edge (the frame that latches
# records nothing), and its samples are the half and the frame core 0 mixes.
# TRACK_DELAY is the signal's delay: since the perf round (design 1.1) the
# hook stages the tracks a frame early rather than copying them a frame
# late, so stems.s has no TRACK_DELAY and the files are the same.
STEM_LAG = PRE_ROLL + 1 - TRACK_DELAY - TRACK_HALF
ST_IDLE, ST_ARMED, ST_RECORDING, ST_FINISHING = 0, 1, 2, 3   # stems.s
STACK_SIZE, STACK_FILL = 0x2000, 0x5354454d                   # stems.s: DramRegion stems_stack, "STEM"
STACK_LIMIT = 6 * 1024     # above this, the plan raises the stack to 16 KB before a flash
RING_SIZE = 0x800000               # stems.s: the ring, 8 MiB (piece 5)
RING_SIZE_T1 = RING_SIZE           # T1 only: 131,072 frames of 64 bytes
RING_FRAMES_T1 = RING_SIZE_T1 // 64
FILE_NAMES = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "MAIN", "CUE", "AB", "CD", "A", "B", "C", "D"]
LAYOUT_CASES = [  # (sources, format, files, ring frame bytes)
    (0x001, 0b110, ["T1"], 64),
    (0x0ff, 0b110, [f"T{k}" for k in range(1, 9)], 512),
    (0x0a5, 0b110, ["T1", "T3", "T6", "T8"], 256),
    (0x701, 0b110, ["T1", "MAIN", "CUE", "AB"], 256),
    (0x401, 0b100, ["T1", "A", "B"], 128),
    (0xfff, 0b000, [f"T{k}" for k in range(1, 9)] + ["MAIN", "CUE", "A", "B", "C", "D"], 768),
    (0x001, 0b111, ["T1"], 96),
    (0xfff, 0b001, [f"T{k}" for k in range(1, 9)] + ["MAIN", "CUE", "A", "B", "C", "D"], 1152),
]
CUE_T1 = 0x80000c51                # T1's cue level byte (docs/firmware/MIDI.md: CC 47)
CUE_ON = 0x80000009                # bits 16-23 of 0x80000008: a track's CUE (MIDI.md: CC 51); bit 0 = T1
# Both are stepped after the transport start, which re-applies the saved
# part: T1 cued, at cue level 127 (its cue word 0x7ef8; cued alone 0x6c00;
# the level byte alone moves nothing; measured 3 Oct 2026).
CUE_STEPS = [f"1:poke:0x{CUE_ON:x}=1", f"1:poke:0x{CUE_T1:x}=127"]
# The source takes stop at 180; four files need more than 120 frames from
# FINISHING to IDLE under the port's card latency (3 Oct 2026: a 300-frame
# run ended FINISHING with every file still 0 bytes), so 420 follow.
SRC_FRAMES = 600
# Fourteen files at 16 bits: the writer falls behind under the port's card
# latency (frame 1,024 of 1,731 written at the stop) and needs 1,516 frames
# from FINISHING to IDLE (3 Oct 2026, watch log), so 1,900 follow the stop.
A14_FRAMES = 3600                  # THRU_STOP (1,700) + 1,900
A14W_FRAMES = 5000                 # 24 bits: 1.5 times the data, so 3,300 follow the stop
MAX_FRAMES = 9922500               # 60 minutes
CHUNK_FRAMES = 512

fails = 0


def check(label, ok, detail=""):
    global fails
    if RECORDING is not None:
        return                     # prefetch() is collecting runs: a check's lines don't count
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def syms():
    out = subprocess.run(["m68k-elf-nm", str(RUNTIME_ELF)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def rd32(img, a):
    return int.from_bytes(img[a - BASE:a - BASE + 4], "big")


def static(img, stock, s):
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
    want = b"\x4e\xb9" + s["stems_frame_hook"].to_bytes(4, "big") + b"\x4e\x71"
    got = img[FRAME_SITE - BASE:FRAME_SITE - BASE + 8]
    check("0x40004b12 is jsr stems_frame_hook; nop", got == want, got.hex())
    want = bytes.fromhex("4ef9") + s["stems_ata_first"].to_bytes(4, "big")
    got = img[ATA_FIRST_SITE - BASE:ATA_FIRST_SITE - BASE + 6]
    check("0x40014cfe is jmp stems_ata_first", got == want, got.hex())


def regions(s):
    from remix import platform_build
    lay = json.loads((LAYOUT_DIR / platform_build.LAYOUT).read_text())
    ring, stack, buf = s["stems_ring"], s["stems_stack"], s["stems_buf"]
    check(f"ring is {RING_SIZE >> 20} MiB ending at the reserve ceiling", ring + RING_SIZE == lay["ceiling"],
          f"0x{ring:08x} + {RING_SIZE >> 20} MiB vs ceiling 0x{lay['ceiling']:08x}")
    check("stack sits just below the ring", stack + 0x2000 <= ring, f"0x{stack:08x}")
    check("sector buffers sit below the stack, 512-aligned", buf + 270336 <= stack and buf % 512 == 0,
          f"0x{buf:08x}")
    check("the runtime's stage ends below the sector buffers", lay["stage_end"] <= buf,
          f"stage end 0x{lay['stage_end']:08x}")


def runtime_at(s, addr, n):
    """n bytes of the linked runtime as built (out/platform/runtime.raw), by address."""
    from remix import platform_build
    lay = json.loads((LAYOUT_DIR / platform_build.LAYOUT).read_text())
    raw = (LAYOUT_DIR / "runtime.raw").read_bytes()
    return raw[addr - lay["base"]:addr - lay["base"] + n]


def runtime_long(s, name):
    """A long of the linked runtime as built, by symbol."""
    return int.from_bytes(runtime_at(s, s[name], 4), "big")


def menu_static(s):
    """The STEMS list as it ships: filled in (the boot's set-up covers only
    the stock lists), eighteen rows, REC's, the sources' and the switches'
    actions, two
    headings never next to each other (the engine skips one row with
    action 0, not two in a row, and never moves onto a last one:
    STEM_REC.md 16.1), every label as at boot, the record-dot icon."""
    lng = lambda a: int.from_bytes(runtime_at(s, a, 4), "big")  # noqa: E731
    txt = lambda a: runtime_at(s, a, 32).split(b"\0")[0].decode("latin1")  # noqa: E731
    lst = [lng(s["stems_list"] + 4 * k) for k in range(7)]
    check("the STEMS list ships filled in: 18 rows, 7 visible, its rows",
          lst == [MENU_ROWS, 0, 0, 0, MENU_VISIBLE, MENU_ROWS, s["stems_rows"]], f"{[hex(x) for x in lst]}")
    rows = [[lng(s["stems_rows"] + ROW_LEN * r + 4 * k) for k in range(6)] for r in range(MENU_ROWS)]
    check("REC runs stems_action; T1-T8 and MAIN to CD stems_source_action; the three switches "
          "stems_switch_action; the status and PEAK are headings",
          [r[2] for r in rows] == [s["stems_action"], 0] + [s["stems_source_action"]] * 12
          + [s["stems_switch_action"]] * 3 + [0], f"{[hex(r[2]) for r in rows]}")
    check("no row has a window, a getter, a child or a page id",
          all(r[1] == r[3] == r[4] == r[5] == 0 for r in rows))
    texts = [txt(r[0]) for r in rows]
    check("the rows ship with the boot defaults",
          texts == ["REC", "READY"] + [f"T{k} [X]" for k in range(1, 9)]
          + ["MAIN [ ]", "CUE [ ]", "AB [ ]", "CD [ ]", "AB STEREO [X]", "CD STEREO [X]", "24 BIT [ ]", "PEAK 0%"],
          f"{texts}")
    check("the category is labelled STEMS", txt(s["stems_cat_label"]) == "STEMS")
    icon = [lng(s["stems_icon"] + 4 * k) for k in range(5)]
    p0 = [lng(s["stems_icon_p0"] + 4 * k) for k in range(19)]
    p1 = [lng(s["stems_icon_p1"] + 4 * k) for k in range(19)]
    # Which bit of a column is the top row isn't settled (MAINMENU.md 1), so
    # the dot must read the same either way up, and left to right.
    rev7 = lambda b: int(f"{b:07b}"[::-1], 2)  # noqa: E731
    check("the icon is 19 x 9 with two planes, a dot symmetric both ways, the stock mask",
          icon == [0x13, 9, 1, s["stems_icon_p0"], s["stems_icon_p1"]] and p0 == p0[::-1]
          and all(c & 0x80ffffff == 0 and rev7(c >> 24) == c >> 24 for c in p0) and any(p0)
          and p1 == [0xff800000] * 19, f"{[hex(c >> 24) for c in p0]}")


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


def t1_frames(dump_path, g=None):
    """T1's stereo frames from a --block-dump, in frame order (slot_frames)."""
    return slot_frames(dump_path, T1_OFFSET // 0x80, g)


def post16(g, x24):
    """A 16-bit stem sample: the top 16 bits of the track's 24-bit share of
    MAIN (STEM_REC.md 18.2), limited as core 0 limits MAIN."""
    return max(-0x8000, min(0x7fff, (g * x24) >> 29))


def main_capture(prefix):
    """MAIN from `--audio-out PREFIX`: TX0 ring words 2 and 3 of core 0's
    24-bit WAV, as L R L R ..."""
    import wave
    with wave.open(f"{prefix}_core0.wav") as w:
        n, c = w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
    return [int.from_bytes(raw[(i * c + ch) * 3:(i * c + ch) * 3 + 3], "little", signed=True)
            for i in range(n) for ch in (2, 3)]


def take16(data):
    return list(struct.unpack_from(f"<{(len(data) - 44) // 2}h", data, 44))


def core1_slot_peaks(dump_path):
    """The largest |sample| in each of core 1's four 0x80-byte slots (tracks
    1 to 4), over every read-back in a --block-dump."""
    import blockdump
    peaks = [0, 0, 0, 0]
    for d, frame, ch, core, ram, w in blockdump.read(dump_path):
        if ram in (0x80003190, 0x80003590) and d == READBACK_DIR:
            for k in range(4):
                for x in w[64 * k:64 * k + 64:2]:
                    peaks[k] = max(peaks[k], abs(x - 65536 if x >= 32768 else x))
    return peaks


def dsp_state(log):
    """Core 0's MAIN ramp state at the run's end, from --dsp-peek
    "0:X:0x3dd,50": per track slot [split, increment, gain] (words 0, 2, 4
    of each five; STEM_REC.md 18.3)."""
    m = re.search(r"core 0 X:0x003dd:((?: [0-9a-f]{6})+)", log)
    if not m:
        return []
    w = [int(x, 16) for x in m.group(1).split()]
    sx = lambda v: v - 0x1000000 if v & 0x800000 else v  # noqa: E731
    return [[sx(w[5 * k]), sx(w[5 * k + 2]), sx(w[5 * k + 4])] for k in range(8)]


def gain_of(log, k):
    """Track k's settled MAIN gain at the run's end (a run that holds its levels)."""
    st = dsp_state(log)
    return st[k][2] if st else None


def level_steps(pairs, addr=0x80000c50):
    """(steps, midi_lines) that move a level at the given frames: pokes of the
    level byte, or CC 46 on channel 1 when the poke doesn't move the page
    (lv_mover.txt, STEM_REC.md 18.1)."""
    mover = MOVER.read_text().split() if MOVER.exists() else ["poke", hex(addr)]
    if mover[0] == "poke":
        return [f"{f}:poke:0x{addr:x}={v}" for f, v in pairs], ()
    return [], tuple(f"{f} B0 2E {v:02X}" for f, v in pairs)


def gains(s):
    """Gate 1: the hook's mirror of core 0's MAIN ramp equals the DSP's own
    at the run's end, on the one-THRU fixture with T1's LEVEL stepped four
    times and the MAIN level once; from a clean boot and from dirty DSP RAM.
    The run may end inside core 0's frame, so each slot matches the hook's
    last mirrored frame or the one before. The crossfader and the scenes
    reach core 0 only through the same level words (STEM_REC.md 18.1); the
    fixture's scenes move none of them, so the LEVEL steps stand in."""
    steps, midi = level_steps(LEVEL_STEPS)
    steps.append(f"140:poke:0x{MAIN_LEVEL_SRC:x}=100")
    for tag, extra in (("gains", ()), ("gainsdirty", ("--dsp-dirty", "7"))):
        log, *_ = port(s, 260, tag=tag, calls_before=(), fixture=FIXTURE_THRU1, mask=None,
                       dump_blocks=False, extra=extra, steps=steps, midi_lines=midi,
                       mems=((s["stems_gstate"], 192, "gs"), (s["stems_gsel"], 4, "gsel"),
                             (s["stems_lvskip"], 4, "skip")))
        dsp = dsp_state(log)

        def longs(name):
            p = run_path(tag, name)
            raw = p.read_bytes() if p.exists() else b""
            return [int.from_bytes(raw[i:i + 4], "big", signed=True) for i in range(0, len(raw), 4)]
        both, sel = longs("gs"), (longs("gsel") or [0])[0] // 96     # two states, used in turn
        now, prev = (both[24:], both[:24]) if sel else (both[:24], both[24:])
        mine = [now[3 * k:3 * k + 3] for k in range(8)]
        before = [prev[3 * k:3 * k + 3] for k in range(8)]
        check(f"{tag}: core 0's state was read", len(dsp) == 8, f"{len(dsp)} slots")
        check(f"{tag}: the mirror equals core 0's MAIN ramp in every track slot",
              len(dsp) == 8 and all(d in (m, b) for d, m, b in zip(dsp, mine, before)),
              f"core 0 T1 {dsp[0] if dsp else None}, mirror {mine[0] if mine else None}, "
              f"the frame before {before[0] if before else None}")
        check(f"{tag}: T1's gain moved off its start", len(dsp) == 8 and dsp[0][2] not in (0, 0x1f7fe0),
              f"{dsp[0] if dsp else None}")
        check(f"{tag}: the sent page index never jumped", longs("skip") == [0], f"{longs('skip')}")


def layout(s):
    """The file table the hook latches at the start edge, for each case: the
    files in order, the ring frame, and the ring's capacity, RING_SIZE //
    frame bytes, with its wrap point."""
    for src, fmt, names, fb in LAYOUT_CASES:
        tag = f"layout{src:03x}{fmt}"
        log, _, _, _, _ = port(s, 120, stop_at=80, tag=tag, mask=None, dump_blocks=False,
                               pokes_before=[(s["stems_tracks"] + 2, src >> 8), (s["stems_tracks"] + 3, src & 0xff),
                                             (s["stems_fmt"] + 3, fmt)],
                               mems=((s["stems_nf"], 4 + 4 * 14, "ftab"), (s["stems_fbytes"], 12, "geom")))
        raw = run_path(tag, "ftab").read_bytes()
        nf = int.from_bytes(raw[:4], "big")
        ftab = [int.from_bytes(raw[4 + 4 * i:8 + 4 * i], "big") for i in range(nf)]
        kinds = [FILE_NAMES[d >> 24] for d in ftab]
        geom = run_path(tag, "geom").read_bytes()
        fbytes, rframes, rlimit = (int.from_bytes(geom[i:i + 4], "big") for i in (0, 4, 8))
        check(f"{tag}: the files", kinds == names, f"{kinds}")
        check(f"{tag}: the ring frame", fbytes == fb == sum(d & 0xffff for d in ftab), f"{fbytes}")
        check(f"{tag}: the capacity", rframes == RING_SIZE // fb and rlimit == rframes * fb,
              f"{rframes} frames, wrap at {rlimit}")


def wav24(data):
    n = (len(data) - 44) // 3
    return [int.from_bytes(data[44 + 3 * i:47 + 3 * i], "little", signed=True) for i in range(n)]


def w24(s):
    """Gate 5: a 24-bit take on the one-THRU fixture with T1's LEVEL stepped:
    T1.wav is 24-bit stereo and equals MAIN's 24 bits at every sample."""
    steps, midi = level_steps(LEVEL_STEPS)
    aud = run_path("w24", "aud")
    log, dump, card, words, _ = port(s, 300, stop_at=180, tag="w24", fixture=FIXTURE_THRU1,
                                     pokes_before=[(s["stems_fmt"] + 3, 0b111)], steps=steps, midi_lines=midi,
                                     extra=("--audio-out", str(aud)))
    st, status, _, wr, rd, nfr = words
    f = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU1)}
    d = f.get("T1.WAV")
    check("w24: T1.wav is 24-bit stereo, its length its frames",
          d is not None and len(d) >= 44 and wav_fmt(d) == (2, 264600, 6, 24, 96 * nfr),
          f"{wav_fmt(d) if d and len(d) >= 44 else None}, {nfr} frames")
    if d and len(d) >= 44:
        off = find_at(wav24(d), capture(aud, (2, 3)))
        check("w24: every sample of T1.wav equals MAIN's 24 bits", off is not None, f"offset {off}")


def w16v24(s):
    """The same deterministic run at 16 bits: every sample is the 24-bit
    take's top 16 bits."""
    steps, midi = level_steps(LEVEL_STEPS)
    log, dump, card, words, _ = port(s, 300, stop_at=180, tag="w16", fixture=FIXTURE_THRU1,
                                     steps=steps, midi_lines=midi)
    a = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU1)}.get("T1.WAV")
    b = {n.upper(): d for n, d in take_files(run_path("w24", "img"), FIXTURE_THRU1)}.get("T1.WAV")
    check("w16v24: the 16-bit take is the 24-bit take's top 16 bits, every sample",
          a is not None and b is not None and len(a) > 44 and wav16(a) == [v >> 8 for v in wav24(b)])


def all14w(s):
    """Review Focus 4 at 24 bits, and gate 2 at full precision: fourteen
    24-bit files; off MAIN's rails MAIN minus the sum of the eight stems is 0
    to 7 at every sample (each stem's floor against the mix's one floor), on
    them the sum lies beyond the rail."""
    log, dump, card, words, _ = port(s, A14W_FRAMES, stop_at=THRU_STOP, tag="all14w", fixture=FIXTURE_THRU,
                                     mask=None, pokes_before=[(s["stems_tracks"] + 2, 0x0f),
                                                              (s["stems_tracks"] + 3, 0xff),
                                                              (s["stems_fmt"] + 3, 0b001)])
    st, status, _, wr, rd, nfr = words
    f = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU)}
    check("all14w: fourteen files, IDLE, no error", len(f) == 14 and st == ST_IDLE and status == 0,
          f"{sorted(f)}, state {st}, status {status}")
    for n, d in f.items():
        ch = 1 if n in ("A.WAV", "B.WAV", "C.WAV", "D.WAV") else 2
        check(f"all14w: {n}'s header and length", len(d) >= 44 and wav_fmt(d) == (ch, 132300 * ch, 3 * ch, 24, 48 * ch * nfr)
              and len(d) == 44 + 48 * ch * nfr, f"{wav_fmt(d) if len(d) >= 44 else None}, {len(d)} bytes")
    if len(f) == 14 and all(len(d) > 44 for d in f.values()):
        stems = [wav24(f[f"T{k}.WAV"]) for k in range(1, 9)]
        main = wav24(f["MAIN.WAV"])
        sums = [sum(t[i] for t in stems) for i in range(len(main))]
        off = [m - x for m, x in zip(main, sums) if m not in (0x7fffff, -0x800000)]
        rail = [(m, x) for m, x in zip(main, sums) if m in (0x7fffff, -0x800000)]
        check("all14w: off MAIN's rails, MAIN minus the eight stems is 0 to 7",
              off and min(off) >= 0 and max(off) <= 7, f"{min(off) if off else None}..{max(off) if off else None}")
        check("all14w: on MAIN's rails, the stems' sum lies beyond the rail",
              all((m > 0 and x >= m - 7) or (m < 0 and x <= m + 7) for m, x in rail), f"{len(rail)} rail samples")


# overflow24's run, on the port's own card: everything at 24 bits needs
# 1,152 bytes a frame, more than the card writes, so the ring (7,281 frames)
# fills by itself; then the task writes it out and goes IDLE. Measured
# (v5-p5-fix1.log): RING FULL 12,402 frames into the take (the writer took
# 5,120 frames meanwhile, ~475 bytes a frame), IDLE 13,085 frames later
# (~640 bytes a frame), 25,487 in all.
OVERFLOW24_FRAMES = 30000


def overflow24(s):
    """Everything on at 24 bits on the port's card, too slow for it: the ring
    fills, the take stops with RING FULL, the task writes the ring out and
    goes IDLE, and every file holds the take's frames under a header that
    says so."""
    log, dump, card, words, _ = port(s, OVERFLOW24_FRAMES, tag="overflow24", fixture=FIXTURE_THRU, mask=None,
                                     dump_blocks=False,
                                     pokes_before=[(s["stems_tracks"] + 2, 0x0f), (s["stems_tracks"] + 3, 0xff),
                                                   (s["stems_fmt"] + 3, 0b111)],
                                     extra=watched(s))
    st, status, _, wr, rd, nfr = words
    ws = writes(s, log)
    marks = [(int(x) // 16, w, v) for x, w, v in ws]
    check("overflow24: RING FULL, then IDLE", status == ERR_OVERFLOW and st == ST_IDLE,
          f"status {status}, state {st}, {nfr} frames; (frame, word, value) {marks}")
    f = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU)}
    check("overflow24: twelve files, each the take's frames under a header that says so",
          len(f) == 12 and all(len(d) >= 44 and wav_fmt(d)[4] == len(d) - 44 == nfr * wav_fmt(d)[2] * 16
                               for d in f.values()),
          f"{len(f)} files, {sorted({len(d) for d in f.values()})} bytes, {nfr} frames")


def capture(prefix, chans):
    """TX0 ring words `chans` of core 0's 24-bit --audio-out WAV, interleaved."""
    import wave
    with wave.open(f"{prefix}_core0.wav") as w:
        n, c = w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
    return [int.from_bytes(raw[(i * c + ch) * 3:(i * c + ch) * 3 + 3], "little", signed=True)
            for i in range(n) for ch in chans]


def wav_fmt(data):
    """(channels, bytes a second, block align, bits, data bytes) of a WAV header."""
    ch, rate, brate, align, bits = struct.unpack_from("<HIIHH", data, 22)
    return ch, brate, align, bits, struct.unpack_from("<I", data, 40)[0]


def wav16(data):
    return list(struct.unpack_from(f"<{(len(data) - 44) // 2}h", data, 44))


def find_at(got, ref, width=64):
    """The offset of `got` inside `ref`, found from got's first sound and then
    required at every sample; None when either fails."""
    loud = next((i for i, v in enumerate(got) if v), None)
    if loud is None:
        return None
    key = got[loud:loud + width]
    pos = next((i for i in range(len(ref) - width) if ref[i:i + width] == key), None)
    if pos is None or pos < loud or ref[pos - loud:pos - loud + len(got)] != got:
        return None
    return pos - loud


def sources(s):
    """Gate 4: on the one-THRU fixture with T1 sent to CUE, a take of T1,
    MAIN, CUE and AB: four files in that order; MAIN.wav equals T1.wav sample
    for sample (only T1 reaches MAIN), and both are aligned in time by
    construction; CUE.wav is the cue bus (TX0 words 0 and 1) at one offset;
    AB.wav carries inputs A and B (the input WAV's channels 2 and 3), each a
    fixed gain of its own input at one lag."""
    aud = run_path("sources", "aud")
    log, dump, card, words, _ = port(s, SRC_FRAMES, stop_at=180, tag="sources", fixture=FIXTURE_THRU1, mask=None,
                                     pokes_before=[(s["stems_tracks"] + 2, 0x07), (s["stems_tracks"] + 3, 0x01)],
                                     steps=CUE_STEPS, extra=("--audio-out", str(aud)))
    st, status = words[0], words[1]
    check("sources: the take finished (IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    files = take_files(card, FIXTURE_THRU1)
    names = [n.upper() for n, _ in files]
    check("sources: T1, MAIN, CUE and AB, nothing else", sorted(names) == ["AB.WAV", "CUE.WAV", "MAIN.WAV", "T1.WAV"],
          f"{names}")
    f = {n.upper(): d for n, d in files}
    if len(f) != 4 or any(len(d) < 44 for d in f.values()):
        return
    check("sources: every header is 16-bit stereo",
          all(wav_fmt(d)[:4] == (2, 176400, 4, 16) for d in f.values()), f"{[wav_fmt(d)[:4] for d in f.values()]}")
    check("sources: MAIN.wav equals T1.wav, every sample (only T1 reaches MAIN)",
          wav16(f["MAIN.WAV"]) == wav16(f["T1.WAV"]) and any(wav16(f["T1.WAV"])))
    cue = [v >> 8 for v in capture(aud, (0, 1))]
    off = find_at(wav16(f["CUE.WAV"]), cue)
    check("sources: CUE.wav equals the cue bus at one offset, and holds sound",
          off is not None and any(wav16(f["CUE.WAV"])), f"offset {off}")
    ab = wav16(f["AB.WAV"])
    import wave
    with wave.open(json.loads(FIXTURE_THRU1.read_text())["audio_in"]) as w:
        raw = w.readframes(w.getnframes())
    ins = list(struct.unpack(f"<{len(raw) // 2}h", raw))
    offs = []
    for side, ch in (("A", 2), ("B", 3)):
        got = ab[0 if side == "A" else 1::2]
        off = find_at(got, ins[ch::4])      # the ring holds the input's samples exactly (STEM_REC.md 18.7)
        offs.append(off)
        check(f"sources: AB.wav's {'left' if side == 'A' else 'right'} channel is input {side}, every sample",
              off is not None, f"offset {off}")
    check("sources: A and B at the same offset", None not in offs and offs[0] == offs[1], f"{offs}")


def mono(s):
    """AB STEREO off: A.wav and B.wav, mono, equal to the stereo take's left
    and right channels of the same deterministic run."""
    log, dump, card, words, _ = port(s, SRC_FRAMES, stop_at=180, tag="mono", fixture=FIXTURE_THRU1, mask=None,
                                     pokes_before=[(s["stems_tracks"] + 2, 0x04), (s["stems_tracks"] + 3, 0x01),
                                                   (s["stems_fmt"] + 3, 0b100)])
    check("mono: the take finished (IDLE, no error)", words[0] == ST_IDLE and words[1] == 0,
          f"state {words[0]}, status {words[1]}")
    f = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU1)}
    check("mono: T1, A and B", sorted(f) == ["A.WAV", "B.WAV", "T1.WAV"], f"{sorted(f)}")
    sf = {n.upper(): d for n, d in take_files(run_path("sources", "img"), FIXTURE_THRU1)}
    if len(f) != 3 or "AB.WAV" not in sf or any(len(d) < 44 for d in list(f.values()) + [sf["AB.WAV"]]):
        return
    ab = wav16(sf["AB.WAV"])
    check("mono: A.wav and B.wav are one channel, 16 bits",
          wav_fmt(f["A.WAV"])[:4] == wav_fmt(f["B.WAV"])[:4] == (1, 88200, 2, 16))
    check("mono: A.wav is AB.wav's left, B.wav its right, every sample",
          wav16(f["A.WAV"]) == ab[0::2] and wav16(f["B.WAV"]) == ab[1::2])


def all14(s):
    """Review Focus 4: every source on, both pairs mono, on the eight-track
    THRU fixture: 14 files in order, each header its own, each length its
    frames; and the eight stems sum to MAIN within one step per track."""
    log, dump, card, words, _ = port(s, A14_FRAMES, stop_at=THRU_STOP, tag="all14", fixture=FIXTURE_THRU,
                                     mask=None, pokes_before=[(s["stems_tracks"] + 2, 0x0f),
                                                              (s["stems_tracks"] + 3, 0xff),
                                                              (s["stems_fmt"] + 3, 0b000)])
    st, status, _, wr, rd, nfr = words
    f = {n.upper(): d for n, d in take_files(card, FIXTURE_THRU)}
    want = [f"T{k}.WAV" for k in range(1, 9)] + ["MAIN.WAV", "CUE.WAV", "A.WAV", "B.WAV", "C.WAV", "D.WAV"]
    check("all14: fourteen files", sorted(f) == sorted(want), f"{sorted(f)}")
    check("all14: IDLE, no error", st == ST_IDLE and status == 0, f"state {st}, status {status}")
    for n, d in f.items():
        ch = 1 if n in ("A.WAV", "B.WAV", "C.WAV", "D.WAV") else 2
        check(f"all14: {n}'s header and length", wav_fmt(d) == (ch, 88200 * ch, 2 * ch, 16, 32 * ch * nfr)
              and len(d) == 44 + 32 * ch * nfr, f"{wav_fmt(d)}, {len(d)} bytes, {nfr} frames")
    if len(f) == 14:
        stems = [wav16(f[f"T{k}.WAV"]) for k in range(1, 9)]
        main = wav16(f["MAIN.WAV"])
        sums = [sum(t[i] for t in stems) for i in range(len(main))]
        # Eight floors against the mix's one: MAIN minus the sum is 0 to 7.
        # Eight THRU tracks of noise clip MAIN; on its rails the sum lies
        # beyond the rail instead (measured 3 Oct 2026: 600 rail samples).
        off = [m - x for m, x in zip(main, sums) if m not in (32767, -32768)]
        rail = [(m, x) for m, x in zip(main, sums) if m in (32767, -32768)]
        check("all14: off MAIN's rails, MAIN minus the eight stems is 0 to 7 at 16 bits",
              off and min(off) >= 0 and max(off) <= 7, f"{min(off) if off else None}..{max(off) if off else None}")
        check("all14: on MAIN's rails, the stems' sum lies beyond the rail",
              all((m > 0 and x >= m - 7) or (m < 0 and x <= m + 7) for m, x in rail), f"{len(rail)} rail samples")


def against_main(tag, card, fixture, aud):
    """T1.wav of the take against the captured MAIN's top 16 bits: found once,
    then equal at every sample. Returns (T1 samples, MAIN segment) or None."""
    files = dict(take_files(card, fixture))
    data = files.get("T1.wav") or files.get("T1.WAV")
    check(f"{tag}: T1.wav exists", data is not None, f"{sorted(files)}")
    if not data:
        return None
    got = take16(data)
    main = [m >> 8 for m in main_capture(aud)]
    loud = next((i for i, v in enumerate(got) if v), None)
    check(f"{tag}: the take holds sound", loud is not None)
    if loud is None:
        return None
    key = got[loud:loud + 64]
    pos = next((i for i in range(len(main) - 64) if main[i:i + 64] == key), None)
    check(f"{tag}: T1.wav's first sound is found in MAIN", pos is not None)
    if pos is None:
        return None
    seg = main[pos - loud:pos - loud + len(got)] if pos >= loud else []
    bad = next((i for i, (a, b) in enumerate(zip(got, seg)) if a != b), None)
    check(f"{tag}: every sample of T1.wav equals MAIN", bad is None and len(seg) == len(got),
          f"{len(got)} samples" if bad is None else f"first difference at sample {bad}: {got[bad]} vs {seg[bad]}")
    return got, seg


def postfader(s):
    """Gates 2-3, one track: on the one-THRU fixture (T1 alone sounds) a take
    armed before play with T1's LEVEL stepped during it. MAIN is T1's share
    alone, so T1.wav equals MAIN's top 16 bits at every sample -- through
    every step, the cut ramp included."""
    steps, midi = level_steps(LEVEL_STEPS)
    aud = run_path("postfader", "aud")
    log, dump, card, words, _ = port(s, 300, stop_at=180, tag="postfader", fixture=FIXTURE_THRU1,
                                     steps=steps, midi_lines=midi, extra=("--audio-out", str(aud)))
    against_main("postfader", card, FIXTURE_THRU1, aud)


def postmove(s):
    """Review Focus 1: the take starts while playing (REC at frame 58), two
    frames before the first LEVEL step: equal to MAIN from its first frame."""
    steps, midi = level_steps(LEVEL_STEPS)
    aud = run_path("postmove", "aud")
    log, dump, card, words, _ = port(s, 300, stop_at=180, tag="postmove", fixture=FIXTURE_THRU1,
                                     calls_before=(), calls=((58, s["stems_action"]),),
                                     steps=steps, midi_lines=midi, extra=("--audio-out", str(aud)))
    against_main("postmove", card, FIXTURE_THRU1, aud)


def clip(s):
    """Review Focus 2: T1 at LEVEL 127, the MAIN level at 127, a full-scale
    input, AMP VOL 127: the take equals MAIN at every sample at the top of
    the range. One THRU track can't clip MAIN under the port (it peaks at
    0.984 of full scale, STEM_REC.md 18.7), so the rails themselves are
    proven in Unicorn (verify_stems_units track16_rails, against MAIN's own
    formula)."""
    aud = run_path("clip", "aud")
    log, dump, card, words, _ = port(s, 300, stop_at=180, tag="clip", fixture=FIXTURE_THRU1_HOT,
                                     pokes_before=[(MAIN_LEVEL_SRC, 127)], extra=("--audio-out", str(aud)))
    res = against_main("clip", card, FIXTURE_THRU1_HOT, aud)
    if res:
        got, seg = res
        peak = max(abs(v) for v in got)
        check("clip: the take reaches the top of the range", peak >= 0.95 * 32767,
              f"peak {peak} of 32767")


def master(s):
    """Review Focus 5: MASTER TRACK on (STEM_REC.md 18.8): the take is whole --
    T1.wav as long as the frames recorded, and the task ends IDLE with no error."""
    log, dump, card, words, _ = port(s, 300, stop_at=180, tag="master", fixture=FIXTURE_THRU1_MASTER)
    st, status, _, wr, rd, nfr = words
    files = dict(take_files(card, FIXTURE_THRU1_MASTER))
    data = files.get("T1.wav") or files.get("T1.WAV")
    check("master: IDLE, no error, T1.wav holds every frame",
          st == ST_IDLE and status == 0 and data is not None and len(data) == 44 + 64 * nfr,
          f"state {st}, status {status}, {len(data) if data else None} bytes for {nfr} frames")


PRE_BOOT = ("--dsp-dirty", "--ata-latency", "--block-dump", "--audio-out", "--watch-mem")
# Options a scenario can't set: the port applies them at the boot, before
# the fork (main.cpp: --dsp-dirty and --ata-latency set the machine up,
# --watch-mem installs its watch, --audio-out switches the capture on, and
# --block-dump opens one stream a child with another path closes). A run
# with one boots alone.
PREFETCH = {}                                 # tag -> what port() returns, filled by prefetch()
RECORDING = None                              # a list while prefetch() collects the runs checks will make


class _Recorded(Exception):
    pass


def _port_parts(s, frames, stop_at=None, extra=(), tag="run", ring_bytes=0, calls=(), pokes=(),
                card_in=None, dump_blocks=True, stack=False, mems=(), calls_before=None, fixture=None,
                pokes_before=(), mask=0x01, load_ms=20000, steps=(), midi_lines=()):
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
    `pokes_before` land after the action and before the transport start, so
    they are in force from the take's first frame; `pokes` land after the
    transport start, some 26 frames into play (main.cpp).

    `--call-before-play` beside `--pre-roll` needs the port fixed on 13 Sep
    2026 (`main.cpp` runs to main's spin before the call; STEM_REC.md 10.1).
    An older port refuses the call, prints the refusal and records nothing,
    so `tap()` checks the call's own report line before anything else.

    A fixture with `audio_in`/`midi` feeds the port's inputs and MIDI IN.
    `mask` is the track mask poked before play, ahead of `pokes_before`
    (default T1: every check written for one track keeps its meaning with
    the build's all-eight default); None pokes nothing. `load_ms` is the
    port's budget for LOAD PROJECT, in emulated ms: the load ends as soon
    as the engine is idle, so a larger budget costs nothing when the load
    is quicker, and a slow emulated card needs one (stems_sweep.py).

    `steps` are upstream's `--step FRAME:call|poke|dump:SPEC` scripts,
    frames counted from the transport start like `calls`. `midi_lines`
    (`<frame> <hex bytes>`) go to the port's MIDI IN, and every run peeks
    core 0's MAIN ramp state at its end (dsp_state).
    `calls_before=()` arms nothing (None: the action, the default)."""
    tag = f"{tag}{SUFFIX}"
    before = (s["stems_action"],) if calls_before is None else tuple(calls_before)
    fx = json.loads(pathlib.Path(fixture or FIXTURE).read_text())
    pokes_before = ([(s["stems_tracks"] + 3, mask)] if mask is not None else []) + list(pokes_before)
    work = pathlib.Path("out/stems_runs"); work.mkdir(parents=True, exist_ok=True)
    paths = {"log": work / f"{tag}.log", "dump": work / f"{tag}.dump", "card": work / f"{tag}.img",
             "mem": work / f"{tag}.mem", "ring": work / f"{tag}.ring", "ring_bytes": ring_bytes}
    dumps = f"0x{s['stems_state']:x},24={paths['mem']}"
    if ring_bytes:
        dumps += f";0x{s['stems_ring']:x},{ring_bytes}={paths['ring']}"
    if stack:
        dumps += f";0x{s['stems_stack']:x},{STACK_SIZE}={work / (tag + '.stack')}"
    for addr, length, name in mems:
        dumps += f";0x{addr:x},{length}={work / (tag + '.' + name)}"
    at = [f"{f}:0x{a:x}:0" for f, a in calls]
    pk = list(pokes)
    if stop_at is not None:
        at.append(f"{stop_at}:0x{KEY_STOP:x}:0")
        pk.append((STOP_GATE, 1))
    pre = [str(EMU), "--image", str(IMAGE), "--card", card_in or fx["card"], "--set", fx["set"],
           "--project", fx["project"], "--load-ms", str(load_ms), "--dsp"]
    if fx.get("audio_in"):
        pre += ["--audio-in", fx["audio_in"]]
    post = ["--sequencer", "--internal-clock", "--frames", str(frames), "--main-level", "64",
            "--pre-roll", str(PRE_ROLL), "--poke-trig", "2",
            *(["--block-dump", str(paths["dump"])] if dump_blocks else []),
            *(["--call-before-play", ",".join(f"0x{a:x}:0" for a in before)] if before else []),
            "--card-out", str(paths["card"]), "--mem-dump", dumps, *extra]
    if fx.get("midi"):
        post += ["--midi", fx["midi"]]
    if at:
        post += ["--at", ",".join(at)]
    if pk:
        post += ["--poke", ";".join(f"0x{a:x}={b}" for a, b in pk)]
    if pokes_before:
        post += ["--poke-before-play", ";".join(f"0x{a:x}={b}" for a, b in pokes_before)]
    for st in steps:
        post += ["--step", st]
    if "--dsp-peek" not in extra:
        post += ["--dsp-peek", "0:X:0x3dd,50"]          # the gains the stems used (dsp_state)
    if midi_lines:
        mid = work / f"{tag}.midi.txt"
        mid.write_text("".join(line + "\n" for line in midi_lines))
        post += ["--midi", str(mid)]
    return pre, post, paths


def _port_result(paths, log):
    paths["log"].write_text(log)                    # the port's report, for the call timing
    m = paths["mem"].read_bytes() if paths["mem"].exists() else b"\0" * 24
    words = [int.from_bytes(m[i:i + 4], "big") for i in range(0, 24, 4)]
    ring = paths["ring"].read_bytes() if paths["ring_bytes"] and paths["ring"].exists() else b""
    return log, paths["dump"], paths["card"], words, ring


def port(s, frames, **kw):
    """One fixture run under the port, its arguments as _port_parts takes
    them. Returns (log, dump, card, state words, ring bytes). A result
    prefetch() already made is returned as it is."""
    if RECORDING is not None:
        RECORDING.append({"frames": frames, **kw})
        raise _Recorded
    tag = f"{kw.get('tag', 'run')}{SUFFIX}"
    if tag in PREFETCH:
        return PREFETCH.pop(tag)
    pre, post, paths = _port_parts(s, frames, **kw)
    r = subprocess.run(pre + post, capture_output=True, text=True)
    return _port_result(paths, r.stdout + r.stderr)


def port_group(s, runs, jobs=1):
    """Several runs on one fixture as scenarios of one boot (the port's
    --scenario: one load, a child forked per run). `runs` are port()'s
    keyword arguments, `frames` among them; the result is what port()
    returns for each, in order. Runs that don't share one boot, or that set
    a boot option (PRE_BOOT), each boot alone instead."""
    parts = [_port_parts(s, **r) for r in runs]
    pre = parts[0][0]
    if any(p[0] != pre for p in parts) or any(o in p[1] for p in parts for o in PRE_BOOT):
        return [port(s, **r) for r in runs]
    assert not any(" " in a for _, post, _ in parts for a in post), "a scenario's arguments split on spaces"
    args = list(pre)
    for _, post, paths in parts:
        args += ["--scenario", " ".join([str(paths["log"])] + post)]
    args += ["--scenario-jobs", str(jobs)]
    r = subprocess.run(args, capture_output=True, text=True)
    pathlib.Path("out/stems_runs/group.log").write_text(r.stdout + r.stderr)
    return [_port_result(paths, paths["log"].read_text() if paths["log"].exists() else "")
            for _, _, paths in parts]


def prefetch(s, checks, jobs=1):
    """Each check's first run, collected without running anything (port()
    records its arguments and stops the check), then run as one boot per
    fixture; each check then finds its first result waiting. A check that
    can't be collected, a run with a boot option, a fixture with one run,
    and every later run of a check boot on their own as before."""
    global RECORDING
    import contextlib
    import io
    RECORDING = []
    for c in checks:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                c(s)
        except Exception:
            pass
    runs, RECORDING = RECORDING, None
    groups = {}
    for r in runs:
        pre, post, _ = _port_parts(s, **r)
        if not any(o in post for o in PRE_BOOT):
            groups.setdefault(tuple(pre), []).append(r)
    for g in groups.values():
        if len(g) > 1:
            for r, res in zip(g, port_group(s, g, jobs)):
                PREFETCH[f"{r.get('tag', 'run')}{SUFFIX}"] = res


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
    want = t1_frames(dump, gain_of(log, 0))
    lag = next((L for L in range(len(want) - nfr + 1) if want[L:L + nfr] == got), None)
    check("every ring frame equals T1's read-back at one fixed lag", nfr > 0 and lag is not None,
          f"lag {lag} frames (pre-roll {PRE_ROLL})" if lag is not None
          else f"no lag 0..{len(want) - nfr} matches")
    loud = any(any(x) for x in got)
    check("the signal is not silence", loud,
          "non-zero samples present" if loud else f"all {nfr} ring frames are zero")


def card_files(card_path):
    """Every file on a card image, {path: bytes}, paths as the card spells
    them, without a leading slash ('STEMS/AUDIO/000000-0000/T1.wav'). A
    folder with no file in it does not appear: emu_card.extract_image lists
    files (verify_card_reader.py pins that)."""
    import emu_card as ec
    return ec.extract_image(pathlib.Path(card_path).read_bytes())


def first_clusters(card_path):
    """Every file's first cluster on a card image, {path: cluster}."""
    import emu_card as ec
    clusters = {}
    ec.extract_image(pathlib.Path(card_path).read_bytes(), clusters=clusters)
    return clusters


def take_clusters(card_path):
    """The first cluster of each take's T1.wav under <set>/AUDIO, {path: cluster}."""
    fx = json.loads(FIXTURE.read_text())
    audio = f"{fx['set']}/AUDIO/".lower()
    return {p: c for p, c in first_clusters(card_path).items()
            if p.lower().startswith(audio) and p.lower().endswith("/t1.wav")}


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


def wav_check(card_path, nfr, dump, tag, lag_want=STEM_LAG, g=None):
    """The take on the card: one new folder in the set's AUDIO folder, its
    T1.wav with the header STEM REC writes, and every sample equal to T1's
    read-back after the fader (g, the run's settled gain) at the lag a take
    armed before play starts at (STEM_LAG).
    The file must also hold sound: under the port the fixture's kick sounds
    for four frames, and a silent file equals the read-back at almost any
    lag, which is how a wrap test once passed on a file of zeros."""
    files = card_files(card_path)
    fx = json.loads(FIXTURE.read_text())
    audio = f"/{fx['set']}/AUDIO"
    names = new_entries(files)
    check(f"{tag}: one new recording in {audio}", len(names) == 1, f"{names}")
    if not names:
        return
    path = f"{audio}/{names[0]}/T1.wav"
    data = card_get(files, path)
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
    want = t1_frames(dump, g)
    same = nfr > 0 and want[lag_want:lag_want + nfr] == got
    check(f"{tag}: every sample equals T1's read-back at lag {lag_want}", same,
          "" if same else f"matching lags {[L for L in range(len(want) - nfr + 1) if want[L:L + nfr] == got][:5]}")
    peak = max((abs(x) for f in got for x in f), default=0)
    check(f"{tag}: the file holds sound", peak > 0, f"peak {peak}")


def full(s):
    """Armed before play, STOP at 400, and 300 frames for the task to write
    the take."""
    log, dump, card, words, _ = port(s, 700, stop_at=400, tag="full", stack=True)
    st, status, made, wr, rd, nfr = words
    raw = run_path("full", "stack")
    if raw.exists():
        longs = [int.from_bytes(raw.read_bytes()[i:i + 4], "big") for i in range(0, STACK_SIZE, 4)]
        untouched = next((i for i, w in enumerate(longs) if w != STACK_FILL), len(longs))
        peak = STACK_SIZE - 4 * untouched
        check(f"full: the writer's stack peak is at most {STACK_LIMIT} bytes", 0 < peak <= STACK_LIMIT,
              f"{peak} of {STACK_SIZE} bytes used")
    check("full: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    check("full: the task drained every frame", rd == wr == nfr, f"rd {rd}, wr {wr}, frames {nfr}")
    wav_check(card, nfr, dump, "full", g=gain_of(log, 0))
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
    check("rowstop: the task drained every frame", rd == wr == nfr, f"rd {rd}, wr {wr}, frames {nfr}")
    check("rowstop: the row stopped it near frame 200", 150 < nfr < 260, f"{nfr} frames")
    wav_check(card, nfr, dump, "rowstop", g=gain_of(log, 0))


def stream(s):
    """A take long enough to cross three chunks: the task must write while
    the take runs. The write watch logs the state words; a write to rd
    (word 4) before the first FINISHING is a write during the take."""
    mems = ((s["stems_peak"], 4, "peak"),) if "stems_peak" in s else ()
    log, dump, card, words, _ = port(s, 1900, stop_at=1700, tag="stream", extra=watched(s, span=24), mems=mems)
    st, status, _, wr, rd, nfr = words
    ws = writes(s, log, span=24)
    fin = next((x for x, w, v in ws if w == 0 and v == ST_FINISHING), None)
    mid = [x for x, w, v in ws if w == 4 and fin is not None and x < fin]
    check("stream: the task wrote during the take", len(mid) >= 2, f"{len(mid)} rd writes before FINISHING")
    check("stream: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    check("stream: the task drained every frame", nfr > 3 * CHUNK_FRAMES and rd == wr,
          f"rd {rd}, wr {wr}, frames {nfr}")
    wav_check(card, nfr, dump, "stream", g=gain_of(log, 0))
    if "stems_peak" in s:
        raw = run_path("stream", "peak")
        peak = int.from_bytes(raw.read_bytes(), "big") if raw.exists() else None
        check("stream: stems_peak is the largest fill the hook saw", peak == rebuilt_peak(ws),
              f"stems_peak {peak}, rebuilt {rebuilt_peak(ws)}")


def wrap(s):
    """The ring's offsets set to three frames before its end (T1: frames
    are 64 bytes) after the action and before play, so they are in force
    from the take's first frame: frames 0 to 2 go at the ring's end, and
    frame 3 on from its start, just before the kick's four loud frames (4
    to 7). The hook and the task both wrap, the offsets end at the right
    place, and the file must equal the read-back at the pre-roll lag."""
    off = RING_SIZE_T1 - 3 * 64
    pokes = [(s[w] + i, (off >> (24 - 8 * i)) & 0xff)
             for w in ("stems_wr_off", "stems_rd_off") for i in range(4)]
    log, dump, card, words, _ = port(s, 400, stop_at=300, tag="wrap", pokes_before=pokes,
                                     mems=((s["stems_wr_off"], 8, "offs"),))
    st, status, _, wr, rd, nfr = words
    check("wrap: the task finished (state IDLE, no error)", st == ST_IDLE and status == 0,
          f"state {st}, status {status}")
    raw = run_path("wrap", "offs")
    offs = raw.read_bytes() if raw.exists() else b"\0" * 8
    wr_off, rd_off = int.from_bytes(offs[:4], "big"), int.from_bytes(offs[4:], "big")
    want = (off + 64 * nfr) % RING_SIZE_T1
    check("wrap: both offsets wrapped and end where the take does", nfr > 3 and wr_off == rd_off == want,
          f"wr_off {wr_off}, rd_off {rd_off}, want {want} ({nfr} frames)")
    wav_check(card, nfr, dump, "wrap", g=gain_of(log, 0))


def cap(s):
    """The 60-minute cap: wr and rd poked to 50 frames short of it after
    the action. The hook must end the take by itself, with no error."""
    v = MAX_FRAMES - 50
    pokes = [(s[w] + i, (v >> (24 - 8 * i)) & 0xff) for w in ("stems_wr", "stems_rd") for i in range(4)]
    log, _, card, words, _ = port(s, 300, tag="cap", pokes=pokes, dump_blocks=False, extra=watched(s),
                                  mems=ui_mems(s, "end"))
    st, status, _, wr, rd, nfr = words
    check("cap: the hook ended the take at the cap", wr == MAX_FRAMES and st == ST_IDLE and status == 0,
          f"wr {wr}, state {st}, status {status}")
    data = take(card) or b""
    check("cap: the file holds the 50 frames", len(data) == 44 + 50 * 64, f"{len(data)} bytes")
    t, _ = ui_read(s, "cap", "end")
    check("cap: the status reads DONE 60:00", t is not None and t[:2] == ["REC", "DONE 60:00"],
          f"{t[:2] if t else None}")


def cut(s):
    """A take cut off mid-way, as a power cut or a card pull would: 1,500
    frames and no STOP, so the run ends while RECORDING, after the writer
    has streamed two chunks. What a computer would find on the card: the
    directory entry's length, and whether the take's data can be read."""
    log, _, card, words, _ = port(s, 1500, tag="cut", dump_blocks=False)
    st, status, _, wr, rd, nfr = words
    files = card_files(card)
    fx = json.loads(FIXTURE.read_text())
    names = new_entries(files)
    data = card_get(files, f"{fx['set']}/AUDIO/{names[0]}/T1.wav") if len(names) == 1 else None
    # Records a fact rather than a wish (26 Sep 2026): the file's length is
    # set only at the end, so a cut-off take is a 0-byte file even though
    # the writer had streamed most of it. A change here means the writer
    # started setting the length during the take.
    check("cut: a take cut off mid-way is a 0-byte T1.wav, its streamed audio unreachable (known)",
          st == ST_RECORDING and rd >= 2 * CHUNK_FRAMES and data is not None and len(data) == 0,
          f"state {st}, {nfr} frames recorded, {rd} streamed, T1.wav {None if data is None else len(data)} bytes")


LABEL_STOP, LABEL_FRAMES = 3000, 3400


def labels(s):
    """The labels one take shows, read from memory at frames 100 and 2,900
    and at the end. While it records: STOP, and REC mm:ss with the take's
    whole seconds or one less (the writer task rewrites the line at most a
    pass late), rising from 00:00 to 00:01. After it: REC, DONE mm:ss with
    the take's length, and PEAK n% from the recorder's own peak (one track:
    a 131,072-frame ring). The menu isn't open: the rows are memory, and the
    screen draws them at the next key (STEM_REC.md 16.1)."""
    tag = "labels"
    port(s, LABEL_FRAMES, stop_at=LABEL_STOP, tag=tag, dump_blocks=False,
         steps=[ui_step(s, 100, tag, "a"), ui_step(s, 2900, tag, "b")], mems=ui_mems(s, "end"))
    secs = []
    for when in ("a", "b"):
        t, w = ui_read(s, tag, when)
        if t is None:
            check(f"labels: the frame dump '{when}' exists", False)
            return
        now = w[5] * 16 // 44100
        allowed = {f"REC {mmss(w[5])}", f"REC {(now - 1) // 60:02d}:{(now - 1) % 60:02d}"}
        check(f"labels ({when}): STOP, and REC with the take's seconds", t[0] == "STOP" and t[1] in allowed,
              f"{[t[0], t[1], t[ROW_PEAK]]}, {w[5]} frames")
        secs.append(int(t[1][-2:]) if t[1].startswith("REC ") else -1)
    check("labels: the seconds rise while it records", secs[0] == 0 and secs[1] >= 1, f"{secs}")
    t, w = ui_read(s, tag, "end")
    pct = w[6] * 100 // (RING_SIZE_T1 // 64) if w else None
    shown = [t[0], t[1], t[ROW_PEAK]] if t else None
    check("labels (end): REC, DONE with the take's length, PEAK from its peak",
          t is not None and w[0] == ST_IDLE and shown == ["REC", f"DONE {mmss(w[5])}", f"PEAK {pct}%"],
          f"{shown}, {w[5] if w else None} frames, peak {w[6] if w else None}")


def labelsbehind(s):
    """The labels while the writer is behind the hook: every source on the
    eight-track THRU fixture, 768 bytes a frame, more than the port's card
    writes (about 454 bytes a frame, 3 Oct 2026). REC mm:ss must still rise
    while it records, read from memory at frames 100 and 6,000: the task
    refreshes the labels between the chunks it writes, not only between
    passes (verify_stems_menu found them frozen at REC 00:00). A chunk of
    twelve files takes some 860 frames to write here, so the label may lag
    by that much: 6,000 frames (2.2 s) leaves room for it."""
    tag = "labelsbehind"
    port(s, 6100, stop_at=6050, tag=tag, fixture=FIXTURE_THRU, mask=None, dump_blocks=False,
         pokes_before=[(s["stems_tracks"] + 2, 0x0f), (s["stems_tracks"] + 3, 0xff)],
         steps=[ui_step(s, 100, tag, "a"), ui_step(s, 6000, tag, "b")])
    secs, behind = [], None
    for when in ("a", "b"):
        t, w = ui_read(s, tag, when)
        if t is None:
            check(f"labelsbehind: the frame dump '{when}' exists", False)
            return
        secs.append(int(t[1][-2:]) if t[1].startswith("REC ") else -1)
        behind = w[3] - w[4]
    check("labelsbehind: the writer is more than a chunk behind at frame 6,000", behind > CHUNK_FRAMES,
          f"{behind} frames waiting")
    check("labelsbehind: the seconds rise while the writer is behind", secs[0] == 0 and secs[1] >= 1, f"{secs}")


def same_as_alone(s):
    """Task 10b: a scenario of one boot gives what a boot of its own gives:
    three runs on the one-THRU fixture (armed before play, 24 bits, a take
    started while playing), each alone and then together; the state words
    and every file of each take, byte for byte. No block dump: it is one
    stream opened at boot, so a run that wants one boots alone."""
    runs = [dict(frames=260, stop_at=180, tag="sa1", fixture=FIXTURE_THRU1, dump_blocks=False),
            dict(frames=260, stop_at=180, tag="sa2", fixture=FIXTURE_THRU1, dump_blocks=False,
                 pokes_before=[(s["stems_fmt"] + 3, 0b111)]),
            dict(frames=260, stop_at=180, tag="sa3", fixture=FIXTURE_THRU1, dump_blocks=False,
                 calls_before=(), calls=((58, s["stems_action"]),))]
    alone = [port(s, **r) for r in runs]
    together = port_group(s, [{**r, "tag": r["tag"] + "g"} for r in runs])
    for r, a, g in zip(runs, alone, together):
        fa, fg = take_files(a[2], FIXTURE_THRU1), take_files(g[2], FIXTURE_THRU1)
        check(f"same_as_alone {r['tag']}: the state words and every file equal its own boot's",
              a[3] == g[3] and fa == fg and len(fa) > 0, f"{a[3]} vs {g[3]}, {len(fa)} and {len(fg)} files")


HOOK_SIDE = ("stems_frame_hook", "stems_mirror", "stems_emac_in", "stems_emac_out", "stems_half",
             "stems_track16", "stems_track24", "stems_bus_src",
             "stems_bus16", "stems_bus24", "stems_stage", "stems_bus_frame", "stems_layout",
             "stems_trace_frame")
HOOK_CEILING = 7415   # the measured worst case, everything at 24 bits; 5,000 until Yves's
                      # decision of 4 Oct 2026 to test the cost on the unit (spec 4.6)


def hook_cost(s, cov):
    """Instructions the hook runs a frame, from a --coverage file (one
    `hexaddr count` line per instruction from the transport start): the
    counts inside the hook's routines (each from its symbol to the next
    symbol), over the times its first instruction ran (STEM_REC.md 10.0).
    Returns (per frame, frames, {routine: per frame})."""
    starts = sorted(set(s.values()))
    spans = []
    for name in HOOK_SIDE:
        a = s[name]
        nxt = next((x for x in starts if x > a), a + 0x1000)
        spans.append((name, a, nxt))
    total, frames, split = 0, 0, {}
    for line in pathlib.Path(cov).read_text().splitlines():
        f = line.split()
        if len(f) != 2:
            continue
        a, n = int(f[0], 16), int(f[1])
        if a == s["stems_frame_hook"]:
            frames = n
        for name, lo, hi in spans:
            if lo <= a < hi:
                total += n
                split[name] = split.get(name, 0) + n
                break
    per = {k: v // frames for k, v in split.items()} if frames else {}
    return (total // frames if frames else None), frames, per


def cost(s):
    """Gate 7: everything on at 24 bits, the eight-track THRU fixture, a take
    armed before play: at most HOOK_CEILING instructions a frame; and the
    cost with the recorder idle (the mirror alone), recorded. The detail
    splits the count by routine."""
    for tag, before, src, fmt in (("costrec", None, 0xfff, 0b001), ("costidle", (), 0x0ff, 0b110)):
        cov = run_path(tag, "cov")
        log, *_ = port(s, 400, tag=tag, fixture=FIXTURE_THRU, mask=None, dump_blocks=False, calls_before=before,
                       pokes_before=[(s["stems_tracks"] + 2, src >> 8), (s["stems_tracks"] + 3, src & 0xff),
                                     (s["stems_fmt"] + 3, fmt)],
                       extra=("--coverage", str(cov)))
        per, frames, split = hook_cost(s, cov) if cov.exists() else (None, 0, {})
        top = ", ".join(f"{k} {v}" for k, v in sorted(split.items(), key=lambda kv: -kv[1]) if v)
        if tag == "costrec":
            check(f"cost: at most {HOOK_CEILING} hook instructions a frame, everything on at 24 bits",
                  per is not None and per <= HOOK_CEILING, f"{per} a frame over {frames} frames ({top})")
        else:
            check("cost: the hook with the recorder idle (the mirror) is measured", per is not None,
                  f"{per} a frame over {frames} frames ({top})")


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


FIXTURE8 = pathlib.Path("out/stems_fixture8.json")   # tools/verify/stems_fixture.py --eight
FIXTURE32 = pathlib.Path("out/stems_fixture32.json")   # tools/verify/stems_fixture.py --fat32
FIXTURE_THRU = pathlib.Path("out/stems_fixture_thru.json")   # stems_fixture.py --thru
FIXTURE_THRU1 = pathlib.Path("out/stems_fixture_thru1.json")   # stems_fixture.py --thru1
FIXTURE_THRU1_HOT = pathlib.Path("out/stems_fixture_thru1hot.json")         # --thru1hot: a full-scale input
FIXTURE_THRU1_MASTER = pathlib.Path("out/stems_fixture_thru1master.json")   # --thru1master: MASTER TRACK on
GQ_N = 4                                   # stems.s: frames of per-sample gains kept
MOVER = pathlib.Path("out/stems_runs/lv_mover.txt")     # STEM_REC.md 18.1: "poke 0x80000c50"
MAIN_LEVEL_SRC = 0x80000035                # STEM_REC.md 18.1: the byte the page builder reads for MAIN
LEVEL_STEPS = ((60, 64), (61, 100), (90, 20), (120, 127))   # two steps a frame apart cut a ramp
GTAB_OFF, GTAB_LEN = 0xe9d8a, 258 * 3      # STEM_REC.md 18.4: X:0x6c00's words in the stock slice
FIXTURE_MODES = [("", FIXTURE), ("--eight", FIXTURE8), ("--fat32", FIXTURE32),
                 ("--thru1", FIXTURE_THRU1), ("--thru1hot", FIXTURE_THRU1_HOT),
                 ("--thru1master", FIXTURE_THRU1_MASTER),
                 ("--thru", FIXTURE_THRU)]   # the --thru1 builds pass through the THRU card: before --thru
CARD_READY = 0x460d1cb8     # emu_card.FW_CARD_READY: := 1 after the firmware's card init and mount
SUFFIX = ""                 # appended to every run's tag: "32" while the FAT32 checks run


def run_path(tag, ext):
    """A file a run wrote: out/stems_runs/<tag><SUFFIX>.<ext>."""
    return pathlib.Path("out/stems_runs") / f"{tag}{SUFFIX}.{ext}"


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


def take_files(card_path, fixture=FIXTURE):
    """Every .wav in the one new take folder, as [(name, bytes)] sorted by
    name (T1 first), or [] when there is not exactly one new folder."""
    files = card_files(card_path)
    fx = json.loads(pathlib.Path(fixture).read_text())
    names = new_entries(files, fixture)
    if len(names) != 1:
        return []
    folder = f"{fx['set']}/AUDIO/{names[0]}/".lower()
    return sorted((p[len(folder):], d) for p, d in files.items()
                  if p.lower().startswith(folder) and "/" not in p[len(folder):]
                  and p.upper().endswith(".WAV"))


def slot_frames(dump_path, k, g=None):
    """Track k's (0-based) stereo frames from a --block-dump, in frame order,
    32 samples each, L R L R ... g=None: each sample's top 16 bits as the DSP
    sent the read-back (the tap before piece 5; STEM_REC.md 9.2). A gain: the
    16-bit stem after the fader, post16, of the words the ColdFire sends
    core 0 (the '>' transfer of the read-back, every track in one block):
    the words core 0 mixes, which differ from the DSP's own in the last bit
    of positive samples (STEM_REC.md 18.5). A sample is two words, its top
    16 bits, then its low 8 bits shifted up."""
    import blockdump
    if g is None:
        ram_for, base = ((0x80003190, 0x80003590) if k < 4 else (0x80003390, 0x80003790)), (k % 4) * 0x40
    else:
        ram_for, base = (0x80003190, 0x80003590), k * 0x40
    out = []
    for d, frame, ch, core, ram, w in blockdump.read(dump_path):
        if ram not in ram_for:
            continue
        if g is None and d == READBACK_DIR:
            out.append((frame, [x - 65536 if x >= 32768 else x for x in w[base:base + 64:2]]))
        elif g is not None and d == ">" and core == 0:
            fr = []
            for i in range(32):
                v = (w[base + 2 * i] << 8) | (w[base + 2 * i + 1] >> 8)
                fr.append(post16(g, v - 0x1000000 if v & 0x800000 else v))
            out.append((frame, fr))
    return [s for _, s in sorted(out)]


# Frames the eight-track run lasts: STOP at 300, then time for the writer to
# close eight files. Upstream's port gives each card sector 8 samples of
# latency (30b530a, 27 Sep 2026); the writer then needs 255 frames from
# FINISHING to IDLE (measured the same day). It was 400 while the emulated
# card answered at once.
EIGHT_FRAMES = 700


def eight(s):
    """stems_tracks = 0xFF before the arm: eight files, each equal to its
    own read-back slot at one fixed lag, and no two alike. The hook latches
    the mask on the first playing frame, so the poke must land before play;
    the fixture's sounds play only their first four frames under the port
    (frames 44-47), so a take that starts later holds silence, which
    matches any slot at any lag. Each file must also be loud."""
    if not FIXTURE8.exists():
        check("eight: the 8-track fixture exists (stems_fixture.py --eight)", False)
        return
    log, dump, card, words, _ = port(s, EIGHT_FRAMES, stop_at=300, tag="eight", fixture=FIXTURE8,
                                     mask=0xFF)
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
        want = slot_frames(dump, k, gain_of(log, k))
        lag = next((L for L in range(len(want) - len(got) + 1) if want[L:L + len(got)] == got), None)
        peak = max((abs(x) for f in got for x in f), default=0)
        check(f"eight: {name} equals track {k + 1}'s read-back at one fixed lag, and is not silence",
              lag is not None and peak > 0, f"lag {lag}, {len(got)} frames, peak {peak}")
        datas.append(data[44:])
    check("eight: no two files alike", len(set(datas)) == len(datas), f"{len(set(datas))} distinct of {len(datas)}")


ERR_OVERFLOW, ERR_EXISTS, ERR_WRITE = 1, 4, 5
DRIVER_DRQ_POLL = 0x40014cf4             # the stock write command's wait for DRQ (STEM_REC.md 11.4)
# The overflow run: STOP at OVERFLOW_STOP, the row at OVERFLOW_FRAMES - 200,
# the end at OVERFLOW_FRAMES. The task writes the whole ring after the
# guard; under upstream's card latency (8 samples a sector, 30b530a) the
# 4 MiB ring took 5,167 frames from FINISHING to IDLE (measured 27 Sep
# 2026), so the row must come later than the 3,800 it did while the card
# answered at once. The 8 MiB ring (piece 5) takes twice the frames.
OVERFLOW_STOP = 7200
OVERFLOW_FRAMES = 14400


def watched(s, extra=(), span=8):
    """--watch-mem on the state words from stems_state on, `span` bytes:
    every write, in order, so a run can see a value the next arm clears.
    8 covers the state and the status; 24 adds the write index and the
    frame count, which the hook writes every frame."""
    return ("--watch-mem", f"0x{s['stems_state']:x},{span}", *extra)


def writes(s, log, span=8):
    """(sample, word, value) for every watched write: word 0 = state,
    1 = status, 3 = stems_wr, 4 = stems_rd, 5 = stems_frames, and 6 =
    stems_peak once the span is 28."""
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


def take(card_path):
    """The one new take's T1.wav on a card, or None."""
    files = card_files(card_path)
    fx = json.loads(FIXTURE.read_text())
    names = new_entries(files)
    return card_get(files, f"{fx['set']}/AUDIO/{names[0]}/T1.wav") if len(names) == 1 else None


LIMIT_FRAMES = 55300                     # the --long take: about 20 s, past the old cap of 41,344


def limit(s):
    """A 20-second take, stopped by STOP: past the old 15-second cap. T1's
    ring (131,072 frames) does not wrap in 20 s, so the file's data must equal
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


def exists(s):
    """A second take on the first take's card, in the same minute: refused,
    and the first take is untouched. Every port take is 000000-0000 (the
    port's clock reads 0, STEM_REC.md 11.2), so the minute is the same."""
    first = run_path("full", "img")
    if not first.exists():
        print("  [SKIP] exists: needs the full run's card")
        return
    before = take(first)
    log, _, card, words, _ = port(s, 700, stop_at=400, tag="exists", card_in=str(first),
                                  dump_blocks=False, mems=ui_mems(s, "end"))
    st, status, _, wr, rd, nfr = words
    check("exists: refused with ERR_EXISTS, state IDLE", st == ST_IDLE and status == ERR_EXISTS,
          f"state {st}, status {status}")
    after = take(card)
    check("exists: the first take is byte-identical", before is not None and after == before,
          f"{len(before) if before else None} bytes before, {len(after) if after else None} after")
    t, _ = ui_read(s, "exists", "end")
    check("exists: the status names the refusal", t is not None and t[:2] == ["REC", "SAME MINUTE"],
          f"{t[:2] if t else None}")


def overflow(s):
    """The writer held (stems_hold, a test seam) and the ring made to look
    nearly full after the action: rd poked 100 frames short of the ring's
    capacity behind wr (131,072 frames of 64 bytes at T1), and rd_off 100
    frames past wr_off. The hook stops with ERR_OVERFLOW once 100 frames
    are in. FINISHING ignores the hold, so the task writes the whole ring
    and closes a playable file. A STOP, then the row, arms again: the task
    came back to IDLE."""
    used = RING_FRAMES_T1 - 100
    rd = (-used) & 0xffffffff
    rd_off = 100 * 64
    pokes = [(s["stems_hold"] + 3, 1)]
    pokes += [(s["stems_rd"] + i, (rd >> (24 - 8 * i)) & 0xff) for i in range(4)]
    pokes += [(s["stems_rd_off"] + i, (rd_off >> (24 - 8 * i)) & 0xff) for i in range(4)]
    # REC pressed at frame 1000, inside the task's long FINISHING (the guard
    # trips near frame 75; IDLE came about frame 5,300 with the 4 MiB ring,
    # twice that with 8 MiB): it must change
    # nothing. The menu's words are dumped just before the re-arm and at the end.
    log, _, card, words, _ = port(s, OVERFLOW_FRAMES, stop_at=OVERFLOW_STOP, tag="overflow",
                                  pokes=pokes, dump_blocks=False,
                                  calls=((1000, s["stems_action"]), (OVERFLOW_FRAMES - 200, s["stems_action"])),
                                  extra=watched(s, span=24),
                                  steps=[ui_step(s, OVERFLOW_FRAMES - 210, "overflow", "pre")],
                                  mems=ui_mems(s, "end") + ((s["stems_peak"], 4, "peak"),))
    st, status, _, wr, rd_end, _ = words
    ws = writes(s, log, span=24)
    statuses = [v for x, w, v in ws if w == 1]
    states = [v for x, w, v in ws if w == 0]
    wrs = [v for x, w, v in ws if w == 3]
    check("overflow: the hook stopped with ERR_OVERFLOW", ERR_OVERFLOW in statuses,
          f"status writes {statuses}")
    check("overflow: 100 frames, then the guard", 100 in wrs and 101 not in wrs, f"wr reached {max(wrs, default=0)}")
    data = take(card) or b""
    ok = len(data) >= 44 and int.from_bytes(data[40:44], "little") == len(data) - 44 == RING_SIZE_T1
    check("overflow: the file holds the whole ring and its header agrees", ok,
          f"{len(data)} bytes")
    check("overflow: the task wrote and went IDLE, and the row armed again",
          states[-2:] == [ST_IDLE, ST_ARMED] and st == ST_ARMED, f"state writes {states}, state {st}")
    if "stems_peak" in s:
        raw = run_path("overflow", "peak")
        peak = int.from_bytes(raw.read_bytes(), "big") if raw.exists() else None
        check("overflow: the re-arm reset stems_peak to 0", peak == 0, f"stems_peak {peak}")
    check("overflow: REC while it saved changed nothing",
          states == [ST_ARMED, ST_RECORDING, ST_FINISHING, ST_IDLE, ST_ARMED], f"state writes {states}")
    t, _ = ui_read(s, "overflow", "pre")
    check("overflow: the status names the full ring", t is not None and t[:2] == ["REC", "RING FULL"],
          f"{t[:2] if t else None}")
    t, _ = ui_read(s, "overflow", "end")
    shown = [t[0], t[1], t[ROW_PEAK]] if t else None
    check("overflow: the re-arm shows CANCEL, ARMED and PEAK 0%",
          shown == ["CANCEL", "ARMED", "PEAK 0%"], f"{shown}")


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
    sectors = card_out_sectors(log)
    # The port refuses a command that STARTS at or past the 20th sector; a
    # raw write of several sectors that starts below it completes.
    check("cardfail: a refused raw write hangs the writer in the stock driver's DRQ poll (known)",
          st == ST_FINISHING and sectors is not None and sectors >= 20 and polls > 100000,
          f"state {st}, {sectors if sectors is not None else 'no card-out line in upstream form:'} "
          f"sectors written, {polls} polls at 0x{DRIVER_DRQ_POLL:x}")


def probe(s):
    """The five raw file routines, measured (STEM_REC.md 12.1). The action
    is called twice before play (arm, then cancel), so the writer task
    exists and is IDLE; stems_probe = 1 makes it run the probe once. The
    probe writes <set>/PROBE.BIN: sectors 0xAA 0xAA 0xAA with one raw
    write, then 0xBB with a second (does the position advance?), then a
    seek to 0 and 0xCC over sector 0, then length 1000, then close."""
    res = s["stems_probe_res"]
    pokes = [(s["stems_probe"] + 3, 1)]
    log, _, card, _, _ = port(s, 300, tag="probe", pokes=pokes, dump_blocks=False,
                              mems=((res, 28, "res"),),
                              calls_before=(s["stems_action"], s["stems_action"]))
    raw = run_path("probe", "res").read_bytes() if \
        run_path("probe", "res").exists() else b"\0" * 28
    r = [int.from_bytes(raw[i:i + 4], "big", signed=True) for i in range(0, 28, 4)]
    check("probe: raw open returned a handle", 1 <= r[0] <= 511, f"d0 {r[0]}")
    check("probe: raw write of 3 sectors", r[1] >= 0, f"d0 {r[1]}")
    check("probe: raw write of 1 more sector", r[2] >= 0, f"d0 {r[2]}")
    check("probe: raw seek to 0", r[3] >= 0, f"d0 {r[3]}")
    check("probe: raw write over sector 0", r[4] >= 0, f"d0 {r[4]}")
    check("probe: set length 1000", r[5] >= 0, f"d0 {r[5]}")
    check("probe: raw close", r[6] >= 0, f"d0 {r[6]}")
    fx = json.loads(FIXTURE.read_text())
    data = card_get(card_files(card), f"{fx['set']}/PROBE.BIN")
    check("probe: the file is exactly 1000 bytes (set length, shorter than written)",
          data is not None and len(data) == 1000, f"{None if data is None else len(data)} bytes")
    if data is not None and len(data) == 1000:
        check("probe: sector 0 is the rewrite (seek + write)", data[:512] == b"\xcc" * 512,
              f"first bytes {data[:4].hex()}")
        check("probe: sector 1 survived the rewrite, and the position advanced",
              data[512:1000] == b"\xaa" * 488, f"bytes 512.. {data[512:516].hex()}")


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
    # The flag is a 32-bit word (big-endian), 1 once mounted: its first
    # byte is 0 either way (27 Sep 2026, both cards read 00000001).
    word = {t: int.from_bytes(b[:4], "big") if len(b) >= 4 else None for t, b in ready.items()}
    check("fat32: control -- the FAT16 card reads as mounted", word["mount16"] == 1,
          ready["mount16"].hex())
    mounted = word["mount32"] == 1
    check("fat32: the firmware mounted the FAT32 card", mounted, ready["mount32"].hex())
    if not (mounted and word["mount16"] == 1):
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
        # The unit's 64 GB card allocates above cluster 65,535, where FAT32
        # needs a cluster number's high word; the fixture's filler puts the
        # take there (stems_fixture.py --fat32).
        takes = take_clusters(run_path("full", "img"))
        check("fat32: the take starts above cluster 65,535 (FAT32's high word in use)",
              bool(takes) and min(takes.values()) > 0xFFFF, f"{takes}")
    finally:
        FIXTURE, SUFFIX = saved, ""


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


# A mask take: at least three chunks (512 frames each) while recording,
# then the time the writer needs at the port's card speed (8 samples a
# sector: STEM_REC.md 13.3). Measured 28 Sep 2026 from the watch logs,
# FINISHING to IDLE: 24 frames at one track, 55 at two, 111 at four, 120
# for 0xA5, 410 at eight -- the 1,300 frames after the stop leave three
# times the eight-track drain.
THRU_STOP = 1700
THRU_FRAMES = 3000


def mask_take(s, mask, tag, stop_at=THRU_STOP, frames=THRU_FRAMES, pokes=(), extra=(), load_ms=20000):
    """One take on the THRU fixture with `mask`: a file per enabled track,
    each equal to its own track's read-back at one fixed offset, sound in
    every frame from its first, no two alike, the writer writing during the
    take, IDLE with no error, and stems_peak exact against the watch log.
    `extra` and `load_ms` go to the port (a slower card: slow8). Returns
    the take's length in frames, or None without the fixture."""
    if not FIXTURE_THRU.exists():
        check(f"{tag}: the THRU fixture exists (stems_fixture.py --thru)", False)
        return
    log, dump, card, words, _ = port(s, frames, stop_at=stop_at, tag=tag, fixture=FIXTURE_THRU,
                                     mask=mask, pokes=pokes, extra=watched(s, span=28, extra=extra),
                                     mems=((s["stems_peak"], 4, "peak"),), load_ms=load_ms)
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
        ref = slot_frames(dump, k, gain_of(log, k))
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
    return nfr


def latch(s):
    """The mask poked to 0xFF while a T1 take records (a --poke lands about
    25 frames into play): the take keeps the mask it latched at its start."""
    pokes = [(s["stems_tracks"] + 3, 0xFF)]
    mask_take(s, 0x01, "latch", pokes=pokes)


RING_FRAMES_8 = RING_SIZE // 512     # 16,384


def wrap8(s):
    """An eight-track take past the ring's 16,384 frames: the ring wraps, and
    every file still equals its track."""
    nfr = mask_take(s, 0xFF, "wrap8", stop_at=17000, frames=18500)
    check("wrap8: the take outran the ring, so the ring wrapped", nfr is not None and nfr > RING_FRAMES_8,
          f"{nfr} frames, the ring {RING_FRAMES_8}")


# overflow8's run: the 4 MiB ring was written out by frame 9,000; the 8 MiB
# ring takes twice the frames, as OVERFLOW_FRAMES did for T1.
OVERFLOW8_FRAMES = 18400


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
    log, _, card, words, _ = port(s, OVERFLOW8_FRAMES, stop_at=OVERFLOW_STOP, tag="overflow8", mask=0xFF,
                                  fixture=FIXTURE_THRU, pokes=pokes, dump_blocks=False,
                                  calls=((OVERFLOW8_FRAMES - 200, s["stems_action"]),),
                                  extra=watched(s, span=28))
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


# A card slower than eight tracks need: 22.58 MB/s / 32 = 0.71 MB/s against
# 1.41 (STEM_REC.md 15.4). A 5-second take filled the 4 MiB ring to about
# 92% without overflowing (the sweep, 28 Sep 2026), and the writer needed
# about 5.6 s more to drain its ~7,500 frames of 512 bytes. The 8 MiB ring
# (piece 5) peaked at 7,573 of 16,384 frames after the same 5 s
# (v5-p5-big-long.log), so the take and the drain double. Latency 32 is
# the quickest way to the fill: the card's rate equals the fill's.
SLOW_LATENCY = 32
SLOW_STOP = 27562                  # 10 s of frames
SLOW_FRAMES = SLOW_STOP + 34000


def slow8(s):
    """Eight tracks on a card at half the speed they need: the ring fills to
    near its capacity without overflowing, and the take still ends IDLE with
    no error, every file equal to its track (the plan's Review Focus 5)."""
    mask_take(s, 0xFF, "slow8", stop_at=SLOW_STOP, frames=SLOW_FRAMES,
              extra=("--ata-latency", str(SLOW_LATENCY)), load_ms=20000 * SLOW_LATENCY // 8)
    raw = run_path("slow8", "peak")
    peak = int.from_bytes(raw.read_bytes(), "big") if raw.exists() else 0
    check("slow8: the ring came within a fifth of its capacity and did not overflow",
          RING_FRAMES_8 * 4 // 5 <= peak < RING_FRAMES_8, f"stems_peak {peak} of {RING_FRAMES_8}")


def fixtures():
    """The fixture cards, built from TEMPLATE: rebuilt when the builder, the
    card writer, the project editor or the template change (a hash of all
    of them in out/stems_fixtures.key), reused otherwise -- a stale card is
    never read, and a quick run doesn't pay a minute to rebuild them. False,
    with nothing checked, when there is no template; a build that fails is
    a failed check."""
    if not TEMPLATE.is_dir():
        return False
    import hashlib
    import emu_card
    import ot_project
    h = hashlib.sha256()
    for p in [pathlib.Path("tools/verify/stems_fixture.py"), pathlib.Path(emu_card.__file__),
              pathlib.Path(ot_project.__file__)] + sorted(q for q in TEMPLATE.rglob("*") if q.is_file()):
        h.update(str(p).encode())
        h.update(p.read_bytes())
    key = pathlib.Path("out/stems_fixtures.key")
    if key.exists() and key.read_text() == h.hexdigest() and all(j.exists() for _, j in FIXTURE_MODES):
        check("the fixtures are current: their inputs are unchanged", True, h.hexdigest()[:12])
        return True
    for mode, _ in FIXTURE_MODES:
        r = subprocess.run([sys.executable, "tools/verify/stems_fixture.py", *([mode] if mode else []),
                            str(TEMPLATE)], capture_output=True, text=True)
        if r.returncode:
            tail = (r.stdout + r.stderr).strip().splitlines()
            check(f"the fixture builds from the template (stems_fixture.py{' ' + mode if mode else ''})",
                  False, tail[-1] if tail else f"exit {r.returncode}")
            return False
    key.write_text(h.hexdigest())
    check("the fixtures build from the template", True, str(TEMPLATE))
    return True


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
    img, stock, s = IMAGE.read_bytes(), STOCK.read_bytes(), syms()
    static(img, stock, s)
    menu_static(s)
    regions(s)
    check("the card-out parse reads upstream's line and refuses crosscheck's",
          card_out_sectors(CARD_OUT_UPSTREAM) == 23 and card_out_sectors(CARD_OUT_CROSSCHECK) is None)
    check("the build records all eight tracks by default", runtime_long(s, "stems_tracks") == 0xFF,
          f"0x{runtime_long(s, 'stems_tracks'):02x}")
    check("stems_peak is in the runtime, 0 at boot", "stems_peak" in s and runtime_long(s, "stems_peak") == 0)
    check("stems_gtab is the stock slice's gain table, word for word (STEM_REC.md 18.4)",
          "stems_gtab" in s and runtime_at(s, s["stems_gtab"], GTAB_LEN) == stock[GTAB_OFF:GTAB_OFF + GTAB_LEN])
    check("the menu's words are in the runtime: stems_took 0, the buffers",
          "stems_took" in s and runtime_long(s, "stems_took") == 0 and "stems_ui_bufs" in s)
    if "--static" in sys.argv:
        return 1 if fails else 0
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    runs = [("probe", probe), ("thru", thru), ("tap", tap), ("full", full), ("gains", gains),
            ("postfader", postfader), ("postmove", postmove), ("clip", clip), ("master", master),
            ("layout", layout), ("sources", sources), ("mono", mono), ("all14", all14),
            ("w24", w24), ("w16v24", w16v24), ("all14w", all14w),
            ("rowstop", rowstop),
            ("stream", stream), ("wrap", wrap), ("cap", cap), ("eight", eight)]
    runs += [(f"mask{m:02x}", lambda s, m=m: mask_take(s, m, f"mask{m:02x}"))
             for m in (0x01, 0x03, 0x0F, 0xFF, 0xA5)]
    runs += [("cost", cost), ("same_as_alone", same_as_alone), ("cut", cut), ("labels", labels), ("labelsbehind", labelsbehind), ("nocard", nocard), ("exists", exists),
             ("overflow", overflow), ("cardfail", cardfail)]
    if "--long" in sys.argv:
        runs += [("limit", limit)]
        runs += [(f"mask{m:02x}", lambda s, m=m: mask_take(s, m, f"mask{m:02x}"))
                 for m in (0x07, 0x1F, 0x3F, 0x7F, 0x80)]
        runs += [("latch", latch), ("wrap8", wrap8), ("overflow8", overflow8), ("slow8", slow8),
                 ("overflow24", overflow24)]
    if "--fat32" in sys.argv:
        runs += [("fat32", fat32)]
    if not EMU.exists():
        print("  [SKIP] port runs: build the port (make emu-cf)")
    elif not TEMPLATE.is_dir():
        print(f"  [SKIP] port runs: no project template at {TEMPLATE} "
              "(STEMS_TEMPLATE=<dir>, a local copy of EZBot's Ultimate FX 1.5.3)")
    elif fixtures():
        chosen = [fn for run_name, fn in runs if (only is None or run_name in only)
                  and run_name != "same_as_alone"]
        if "--alone" not in sys.argv:
            prefetch(s, chosen)           # one boot per fixture for each check's first run (Task 10b)
        for run_name, fn in runs:
            if only is None or run_name in only:
                fn(s)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
