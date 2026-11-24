#!/usr/bin/env python3
"""TEMPO BUS under the port: the TEMPO key opens the bus screen, the knobs
edit the hosts, the window closes clean.

    python3 tools/verify/verify_tempo_bus.py octabam-bus     # after verify_set
    OT_PROJECT=<dir> make check REMIX=octabam-bus            # the same, from make verify

Boots the image and card verify_set staged (out/setverify/image.bin,
card.img), drives the panel through `ot_emu --live-script` (key and encoder
events on the panel link at emulated times, no wall-clock sleeps), dumps RAM at the end and checks:

  window   TEMPO opens a 118 x 64 window (the menu window's size)
  delay    rows MODE TIME WET TONE FDBK PING SIZE SCTR DENS PTCH, a mode's
           --- slots left out. Row 0 MODE: A to 0 then +2 (REVERSE; with
           MODE DEFAULTS its view: TIME, page-2 slot 11 = 20); row 2 WET,
           A to 0 then +9 -> page-1 flat 29 = 9; row 4 FDBK, B to 0 then +5
           -> flat 26 = 5; row 5 is SLEN with PING left out, B to 0 then +1
           -> page-2 slot 3 = 1, PING (flat 28) stays 0
  reverb   rows MODE TIME WET TONE SIZE DLY SHMR SHFT DIFF GATE. RIGHT: its
           own cursor, row 0; UP held there; row 4 SIZE, B to 0 then +7 ->
           flat 26 = 7; row 5 DLY, A to 0 then +11 -> page-2 slot 10 = 11;
           row 1 TIME, A to 0 then +5 -> page-2 slot 11 = 5
  copy     FUNC+REC, FUNC+STOP and a second FUNC+STOP, one boot each
           (copypaste(): the values, MODE first, the undo)
  tempo    LEVEL to the 30.0 floor and +5, then FUNC + LEVEL +3 -> 35.3 BPM
           (project tempo 0x80000020 = BPM x 24; skipped while the pattern
           tempo is on)
  close    after TEMPO again the window handle is 0 and no input layer in
           the list lies inside the module's code
  run      the port ends on `quit`, not on a fault
  scenes   a second boot (scenes()): with scene A pressed over the open
           window, WET -27 is scene A's lock on the host's flat 29 and no
           other flat of the track is locked; a push with no turn removes
           FDBK's lock; TIME -9 is a SCENES P2 cell; with scene B held before
           the window opens, WET -9 is scene B's lock. The morph itself is
           stock's and not run here (the panel script runs with the
           transport stopped)

Writes out/tempobus/screen.png (the window before it closes is not kept;
the last frame drawn is rendered from the second, reopened window).
SKIPs without the port, without verify_set's staged card, or when the
remix does not carry TEMPO BUS. What it cannot see: the LCD composition
(the window planes are rendered from RAM), the MKII keymap (the port
boots the MKI one; TEMPO, LEFT and RIGHT are the same codes in both).
"""
import os, pathlib, re, struct, subprocess, sys, tempfile, time, zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
SET = ROOT / "out/setverify"
GAP, DOWN = 50.0, 20.0         # emulated ms between panel lines; key down -> up
OUT = ROOT / "out/tempobus"
WINH, LAYERS = 0x460d16a0, 0x460d165c
TABLE, STRIDE, PLANES = 0x46c7d34c, 56, 0x460d1f7b
LIVEB = 0x80000810
DUMP_BASE, DUMP_LEN = 0x460d0000, 0xbb0000
ROM_BASE, ROM_LEN = 0x400b0000, 0x28000        # the stock layers and ours live here
KEY_TEMPO, KEY_NO, KEY_RIGHT, KEY_UP, KEY_DOWN, KEY_FUNC = 0x18, 0x32, 0x21, 0x33, 0x20, 0x2d
KEY_LEFT, KEY_STOP, KEY_REC = 0x34, 0x27, 0x29
TEMPO = 0x80000020
LIVE_IDS = 0x80000ec4          # the live FX1/FX2 id arrays (verify_set.LIVE_IDS)


def png(path, w, h, px, scale=4):
    rows = []
    for y in range(h * scale):
        row = bytearray([0])
        for x in range(w * scale):
            row += b"\xe8\xf0\x60" if px[y // scale][x // scale] else b"\x1c\x24\x10"
        rows.append(bytes(row))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def scenes(image, card, setname, name, work, dly, p2, check):
    """A second boot: the window's knobs with a scene held (sambanks/octabam#1221).

    Stock's scene press pushes the scene's input layer over the window's, and
    that layer took every encoder: a turn wrote a lock on the hidden page's
    knob (T1 flat 0) and the window's row was untouched. Checks, on the delay
    host's (T`dly`+1) Part and its scene blocks:
      A  TEMPO open, SCENE A pressed: WET -27 locks scene A's flat 29, FDBK
         -9 then a push with no turn leaves no lock on flat 26; TIME -9 is a
         SCENES P2 cell (without SCENES P2: the Part's TIME); no other T1 lock
      B  TEMPO closed, SCENE B held, TEMPO opened: WET -9 locks scene B's flat 29
    Each lock is checked against the Part's value at the end, so a turn the
    Part took instead fails it. Returns the failures."""
    BLOB, BANK_STRIDE, DBPTR = 0x400e21e0, 0x9b340, 0x46c82456
    SC_A, SC_B, PUSH_A = 0x19, 0x1a, 0x38
    lines, now = [], [1500.0]

    def send(line, pause=GAP):
        lines.append(f"{now[0]:.0f} {line}")
        now[0] += pause

    def key(code, pause=3 * GAP):
        send(f"key {code:#x} down", DOWN)
        send(f"key {code:#x} up", pause)

    key(KEY_NO, 5 * GAP)
    key(KEY_TEMPO, 5 * GAP)                         # rows: MODE TIME WET TONE FDBK ...
    key(KEY_DOWN); key(KEY_DOWN)                    # row 2: WET
    send(f"key {SC_A:#x} down", 6 * GAP)            # after the window: its layer goes over ours
    for _ in range(3):
        send("enc 0 -9", 6 * GAP)                   # WET -27: scene A's lock
    key(KEY_DOWN); key(KEY_DOWN)                    # row 4: FDBK
    send("enc 0 -9", 6 * GAP)                       # a lock ...
    key(PUSH_A, 6 * GAP)                            # ... and a push with no turn clears it
    for _ in range(3):
        key(KEY_UP)                                 # row 1: TIME (page 2)
    send("enc 0 -9", 6 * GAP)
    send(f"key {SC_A:#x} up", 6 * GAP)
    key(KEY_TEMPO, 5 * GAP)                         # close
    send(f"key {SC_B:#x} down", 6 * GAP)            # B held first, then the window
    key(KEY_TEMPO, 5 * GAP)
    key(KEY_DOWN)                                   # row 2: WET
    send("enc 0 -9", 6 * GAP)
    send("quit")
    script = work / "scenes.txt"
    script.write_text("\n".join(lines) + "\n")
    run_card = work / "card_scenes.img"
    run_card.write_bytes(card.read_bytes())
    ui, dbs = work / "s_ui.bin", [work / f"s_db{b}.bin" for b in range(16)]
    log = OUT / "port_scenes.txt"
    cmd = [str(EMU), "--image", str(image), "--card", str(run_card), "--set", setname,
           "--project", name, "--load-ms", "90000", "--live-script", str(script),
           "--mem-dump", f"{DBPTR:#x},4={ui};"
                         + ";".join(f"{BLOB + b * BANK_STRIDE + 0x8ed80:#x},0x6300={f}" for b, f in enumerate(dbs))]
    with open(log, "w") as lf:
        lf.write(" ".join(cmd) + "\n"); lf.flush()
        subprocess.run(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, timeout=900)
    fails = [0]

    def chk(label, ok, detail=""):
        fails[0] += 0 if ok else 1
        check(label, ok, detail)

    chk("scenes: the port ended on quit", "ended on quit" in log.read_text())
    if not ui.is_file():
        return fails[0]
    db = struct.unpack(">I", ui.read_bytes())[0]
    part = dbs[(db - BLOB) // BANK_STRIDE].read_bytes()       # part 0's window, from +0x8ed80
    P = lambda off: part[off - 0x8ed80]
    sa, sb = P(0x8ed90), P(0x8ed91)
    lock = lambda sc, flat: P(0x8f3e2 + 0x100 * sc + 0x20 * dly + flat)
    cells = lambda sc: [(P(0x8f400 + 0x100 * sc + 0x20 * c), P(0x8f401 + 0x100 * sc + 0x20 * c))
                        for c in range(8) if not P(0x8f400 + 0x100 * sc + 0x20 * c) & 0x80]
    wet, time_ = P(0x8ee9a + 24 * dly + 18 + 5), P(0x8f084 + 30 * dly + 5)
    t = f"T{dly + 1}"
    chk(f"scenes: A held after TEMPO: WET -27 locks scene {sa}'s flat 29 = {max(wet - 27, 0)}, the Part keeps {wet}",
        lock(sa, 29) == max(wet - 27, 0), f"lock {lock(sa, 29)}")
    chk(f"scenes: FDBK's lock (flat 26) removed by the push", lock(sa, 26) == 0xff, f"{lock(sa, 26)}")
    if p2:
        chk(f"scenes: TIME -9 is scene {sa}'s cell ({dly << 4 | 5:#04x}, {max(time_ - 9, 0)}), the Part keeps {time_}",
            cells(sa) == [(dly << 4 | 5, max(time_ - 9, 0))], f"cells {cells(sa)}")
    others = {f: lock(sa, f) for f in range(30) if f != 29 and lock(sa, f) != 0xff}
    chk(f"scenes: no other {t} lock in scene {sa} (the hidden page's knob A is flat 0)", not others, f"{others}")
    chk(f"scenes: B held before TEMPO: WET -9 locks scene {sb}'s flat 29 = {max(wet - 9, 0)}",
        lock(sb, 29) == max(wet - 9, 0), f"lock {lock(sb, 29)}")
    return fails[0]


def copypaste(image, card, setname, name, work, dly, vrb, undo, check):
    """A boot a case: FUNC+REC copies the window's values, FUNC+STOP pastes them,
    a second FUNC+STOP undoes the paste (`undo`).

    Copied: delay MODE REVERSE (page-2 slot 0 = 2), TIME 50 (slot 5, after the
    mode's view put 20 there), SLEN 1 (slot 3); reverb TIME 5, SIZE 7. Then
    delay MODE back to CLEAN and TIME 99, reverb TIME 30 and SIZE 40. The
    paste puts the copy back; MODE goes first, so MODE DEFAULTS' re-default
    does not leave TIME at the view's 20. With `undo` the second paste
    puts the 99 / 30 / 40 back. Returns the failures."""
    lines, now = [], [1500.0]

    def send(line, pause=GAP):
        lines.append(f"{now[0]:.0f} {line}")
        now[0] += pause

    def key(code, pause=3 * GAP):
        send(f"key {code:#x} down", DOWN)
        send(f"key {code:#x} up", pause)

    def knob(n, v):
        send(f"enc {n} -64"); send(f"enc {n} -64"); send(f"enc {n} {v}", 3 * GAP)

    def func(code):
        send(f"key {KEY_FUNC:#x} down", GAP)
        key(code, GAP)
        send(f"key {KEY_FUNC:#x} up", 3 * GAP)

    key(KEY_NO, 5 * GAP)
    key(KEY_TEMPO, 5 * GAP)
    send("enc 0 -5"); send("enc 0 2", 3 * GAP)       # row 0 MODE: REVERSE
    key(KEY_DOWN); knob(0, 50)                       # row 1 TIME
    for _ in range(4):
        key(KEY_DOWN)                                # row 5: SLEN
    knob(1, 1)
    key(KEY_RIGHT)
    for _ in range(4):
        key(KEY_DOWN)                                # reverb row 4: SIZE
    knob(1, 7)
    for _ in range(3):
        key(KEY_UP)                                  # row 1: TIME
    knob(0, 5)
    func(KEY_REC)
    key(KEY_LEFT)
    for _ in range(5):
        key(KEY_UP)                                  # delay row 0: MODE
    send("enc 0 -5", 3 * GAP)                        # CLEAN
    key(KEY_DOWN); knob(0, 99)                       # row 1: TIME
    key(KEY_RIGHT)                                   # reverb row 1: TIME
    knob(0, 30)
    for _ in range(3):
        key(KEY_DOWN)
    knob(1, 40)                                      # row 4: SIZE
    func(KEY_STOP)
    if undo:
        func(KEY_STOP)
    send("quit")
    script = work / f"copypaste{int(undo)}.txt"
    script.write_text("\n".join(lines) + "\n")
    run_card = work / f"card_copypaste{int(undo)}.img"
    run_card.write_bytes(card.read_bytes())
    lanes = work / f"lanes_copypaste{int(undo)}.bin"
    log = OUT / f"port_copypaste{int(undo)}.txt"
    cmd = [str(EMU), "--image", str(image), "--card", str(run_card), "--set", setname,
           "--project", name, "--load-ms", "90000", "--live-script", str(script),
           "--mem-dump", f"{LIVEB:#x},0x240={lanes}"]
    with open(log, "w") as lf:
        lf.write(" ".join(cmd) + "\n"); lf.flush()
        subprocess.run(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, timeout=900)
    fails = [0]

    def chk(label, ok, detail=""):
        fails[0] += 0 if ok else 1
        check(label, ok, detail)

    what = "undo" if undo else "paste"
    chk(f"copy/{what}: the port ended on quit", "ended on quit" in log.read_text())
    if not lanes.is_file():
        return fails[0]
    lane = lanes.read_bytes()
    L = lambda t, o: lane[t * 72 + o]
    got = {"mode": L(dly, 0x38), "time": L(dly, 0x3d), "vtime": L(vrb, 0x3d), "vsize": L(vrb, 26)}
    if undo:
        want = {"mode": 0, "time": 99, "vtime": 30, "vsize": 40}
    else:
        want = {"mode": 2, "time": 50, "vtime": 5, "vsize": 7}
        got["slen"], want["slen"] = L(dly, 0x3b), 1
    chk(f"copy/{what}: delay MODE, TIME, SLEN and reverb TIME, SIZE read back", got == want,
        f"got {got}, want {want}")
    return fails[0]


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    mods = registry.remix(remix).modules
    if "TEMPO BUS" not in mods:
        print(f"  [SKIP] verify_tempo_bus: {remix} does not carry TEMPO BUS")
        return 0
    if not EMU.exists():
        print("  [SKIP] verify_tempo_bus: the ColdFire port is not built (make emu-cf)")
        return 0
    image, card = SET / "image.bin", SET / "card.img"
    if not (image.is_file() and card.is_file()):
        print("  [SKIP] verify_tempo_bus: no staged card (run verify_set with OT_PROJECT first)")
        return 0
    first = (SET / "port.txt").read_text().split("\n", 1)[0]
    setname = re.search(r"--set (\S+)", first).group(1)
    name = re.search(r"--project (\S+)", first).group(1)
    OUT.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix="tempobus."))
    run_card = work / "card.img"
    run_card.write_bytes(card.read_bytes())
    script = work / "panel.txt"
    dump, lanes, rom, log = work / "ram.bin", work / "lanes.bin", work / "rom.bin", OUT / "port.txt"
    tmp = work / "tempo.bin"
    ids = work / "ids.bin"
    # The panel script at EMULATED times (ot_emu --live-script): the same key
    # sequence the unit's user presses, with no wall-clock sleeps, so a
    # loaded machine runs it exactly as a quiet one. Gaps in emulated ms.
    lines, now = [], [1500.0]            # the first key after the boot settles

    def send(line, pause=GAP):
        lines.append(f"{now[0]:.0f} {line}")
        now[0] += pause

    def key(code, pause=3 * GAP):
        send(f"key {code:#x} down", DOWN)
        send(f"key {code:#x} up", pause)

    key(KEY_NO, 5 * GAP)                              # the boot's date prompt
    key(KEY_TEMPO, 5 * GAP)
    # rows (26 Sep 2026): MODE TIME WET TONE in both boxes, then each
    # engine's own (delay FDBK PING SIZE SCTR DENS PTCH, reverb SIZE DLY
    # SHMR SHFT DIFF GATE); DEL and REV are the host pages', and a mode's
    # --- slots are left out
    send("enc 0 -5"); send("enc 0 2", 3 * GAP)        # row 0 MODE: A to REVERSE (its view)
    key(KEY_DOWN); key(KEY_DOWN)                      # row 2: WET
    send("enc 0 -64"); send("enc 0 -64"); send("enc 0 9", 3 * GAP)
    key(KEY_DOWN); key(KEY_DOWN)                      # row 4: FDBK
    send("enc 1 -64"); send("enc 1 -64"); send("enc 1 5")
    key(KEY_DOWN)                                     # row 5: SLEN, REVERSE's --- PING left out
    send("enc 1 -64"); send("enc 1 -64"); send("enc 1 1", 3 * GAP)
    key(KEY_RIGHT)                                    # reverb: its own cursor, row 0 (MODE)
    key(KEY_UP)                                       # UP at row 0: held there
    for _ in range(4):
        key(KEY_DOWN)                                 # row 4: SIZE
    send("enc 1 -64"); send("enc 1 -64"); send("enc 1 7", 3 * GAP)
    key(KEY_DOWN)                                     # row 5: DLY
    send("enc 0 -64"); send("enc 0 -64"); send("enc 0 11", 3 * GAP)
    for _ in range(4):
        key(KEY_UP)                                   # row 1: TIME
    send("enc 0 -64"); send("enc 0 -64"); send("enc 0 5", 3 * GAP)
    send("enc 6 -128"); send("enc 6 -128")            # LEVEL: to the 30.0 floor
    send("enc 6 5", 2 * GAP)                          # LEVEL: +5 BPM
    send(f"key {KEY_FUNC:#x} down", GAP)
    send("enc 6 3", 2 * GAP)                          # FUNC + LEVEL: +0.3 BPM
    send(f"key {KEY_FUNC:#x} up", 3 * GAP)
    key(KEY_TEMPO, 5 * GAP)                           # close
    send("quit")
    script.write_text("\n".join(lines) + "\n")
    cmd = [str(EMU), "--image", str(image), "--card", str(run_card), "--set", setname,
           "--project", name, "--load-ms", "90000", "--live-script", str(script),
           "--mem-dump", f"{DUMP_BASE:#x},{DUMP_LEN:#x}={dump};{LIVEB:#x},0x240={lanes};{TEMPO:#x},8={tmp};"
                         f"{ROM_BASE:#x},{ROM_LEN:#x}={rom};{LIVE_IDS:#x},16={ids}"]
    with open(log, "w") as lf:
        lf.write(" ".join(cmd) + "\n"); lf.flush()
        subprocess.run(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, timeout=900)
    text = log.read_text()

    fails = 0
    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'ok' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    check("run: the port ended on quit", "ended on quit" in text,
          re.search(r"live script: .*ended .*", text).group(0) if "ended" in text else "no end line")
    ram, lane, romb = dump.read_bytes(), lanes.read_bytes(), rom.read_bytes()

    def rd(a, n):
        if ROM_BASE <= a < ROM_BASE + ROM_LEN:
            return romb[a - ROM_BASE:a - ROM_BASE + n]
        return ram[a - DUMP_BASE:a - DUMP_BASE + n]
    u32 = lambda a: struct.unpack(">I", rd(a, 4))[0]

    # the host tracks: the part's live FX2 ids, from this run (the card
    # verify_set staged; it need not have run: `verify_set --stage-only`)
    idb = ids.read_bytes()
    fx2 = list(idb[8:16])
    dly = next((t for t, v in enumerate(fx2) if v == registry.by_key("DELAY SERVER").menu.fx2_id), None)
    vrb = next((t for t, v in enumerate(fx2) if v == registry.by_key("REVERB SERVER").menu.fx2_id), None)
    L = lambda t, o: lane[t * 72 + o]

    # the screen as it stood at the last draw: the plane is kept after the close
    for i in range(5):
        e = TABLE + i * STRIDE
        w, h = struct.unpack(">ii", rd(e + 36, 8))
        if (w, h) == (118, 64):
            col = 8
            px = [[0] * w for _ in range(h)]
            for x in range(w):
                bits = int.from_bytes(rd(PLANES + i * 0x400 + x * col, col), "big")
                for y in range(h):
                    px[h - 1 - y][x] = (bits >> (63 - y)) & 1
            png(OUT / "screen.png", w, h, px)
    check("window: TEMPO opened a 118 x 64 window", (OUT / "screen.png").is_file(),
          str(OUT / "screen.png"))
    if dly is None or vrb is None:
        check("hosts: the staged part hosts BusDelay and BusVerb", False, f"FX2 ids {fx2}")
    else:
        check(f"delay: FDBK (T{dly + 1} page-1 flat 26) = 5", L(dly, 26) == 5, f"{L(dly, 26)}")
        check(f"delay: MODE (T{dly + 1} page-2 slot 0) = 2, REVERSE", L(dly, 0x38) == 2, f"{L(dly, 0x38)}")
        check(f"delay: row 2 set WET (page-1 flat 29) = 9", L(dly, 29) == 9, f"{L(dly, 29)}")
        check(f"delay: REVERSE's --- PING left out, row 5 set SLEN (page-2 slot 3) = 1, PING stays 0",
              L(dly, 0x3b) == 1 and L(dly, 28) == 0, f"SLEN {L(dly, 0x3b)}, PING {L(dly, 28)}")
        if "MODE DEFAULTS" in mods:
            check(f"delay: REVERSE's view landed (TIME, page-2 slot 11 = 20)", L(dly, 0x3d) == 20, f"{L(dly, 0x3d)}")
        check(f"reverb: TIME (T{vrb + 1} page-2 slot 11) = 5, row 1", L(vrb, 0x3d) == 5, f"{L(vrb, 0x3d)}")
        check(f"reverb: DLY (T{vrb + 1} page-2 slot 10) = 11, row 5", L(vrb, 0x3c) == 11, f"{L(vrb, 0x3c)}")
        check(f"reverb: SIZE (T{vrb + 1} page-1 flat 26) = 7, row 4", L(vrb, 26) == 7, f"{L(vrb, 26)}")
    traw, ptn = struct.unpack(">I", tmp.read_bytes()[:4])[0], tmp.read_bytes()[4]
    if ptn:
        print("  [SKIP] tempo: the pattern tempo is on")
    else:
        check("tempo: LEVEL floor +5, FUNC + LEVEL +3 -> 35.3 BPM",
              traw // 24 == 35 and traw % 24 != 0, f"raw {traw} = {traw / 24:.2f} BPM")
    check("close: the TEMPO window handle is 0", u32(WINH) == 0, f"{u32(WINH):#x}")
    node, inside, walked = u32(LAYERS), [], 0
    while node and walked < 32:
        if 0x400d64e0 <= node < 0x400d6b00:          # the tempobus unit
            inside.append(node)
        node = u32(node) if (DUMP_BASE <= node < DUMP_BASE + DUMP_LEN
                             or ROM_BASE <= node < ROM_BASE + ROM_LEN) else 0
        walked += 1
    check("close: no input layer from the module is left registered", not inside,
          ", ".join(f"{n:#x}" for n in inside))
    if dly is not None:
        fails += scenes(image, card, setname, name, work, dly, "SCENES P2" in mods, check)
    if dly is not None and vrb is not None:
        for undo in (False, True):
            fails += copypaste(image, card, setname, name, work, dly, vrb, undo, check)
    print(f"verify_tempo_bus: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
