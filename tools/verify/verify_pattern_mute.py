#!/usr/bin/env python3
"""PATTERN MUTE under the port: two mute layers, the word stock reads is their OR.

    python3 tools/verify/verify_pattern_mute.py REMIX [--project DIR]

One load of the project (OCTABAM89_setgate: TRACK_MUTE_MASK=127, MIDI_TRACK_MUTE_MASK=255, pattern A01
current), then one forked scenario per gesture, each ending in a dump of the mute words, their SRAM
mirrors, the unit's layer state and the current bank's pattern records (RAM and CS1):

  global      FUNC+T1                      GLOBAL layer: word, layer and mirror agree
  layer       FUNC tapped twice            the layer flag flips (two presses inside 300 ms on DTCN3)
  pattern     double FUNC, FUNC+T8         PATTERN layer: word = GLOBAL | PATTERN, mirror keeps GLOBAL,
                                           the pattern's track 8 record and its CS1 copy hold bit 0,
                                           the bank is marked edited
  away        pattern, then PATTERN+trig 2 the other pattern has no PATTERN mutes: word back to GLOBAL
  back        away, then PATTERN+trig 1    A01's PATTERN layer returns
  midi        MIDI, FUNC+T1, double FUNC,  GLOBAL then PATTERN on the MIDI word; bit 1 of track 1's record
              FUNC+T1
  save        pattern, then SAVE PROJECT   bank03.work carries the PATTERN bit, project.work's
                                           TRACK_MUTE_MASK stays the GLOBAL byte

SKIPs without the port or a project.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/patternmute_verify"
IMAGE = ROOT / "out/mainos_bus.bin"
ELF = ROOT / "out/platform/runtime/runtime.elf"

BANK0, BANK_STRIDE = 0x400E21E0, 0x9B340
PAT_STRIDE, REC_OFF, REC_STRIDE = 0x8ED8, 31, 2330
CS1_PAT, EDIT_FLAG = 0x1001614E, 0x100F8598
FUNC, T1, T8, NO, MIDI, PATTERN, TRIG1, TRIG2 = 0x2D, 0x10, 0x17, 0x32, 0x35, 0x2E, 0x00, 0x01
PROJ, RIGHT, DOWN, YES = 0x1C, 0x21, 0x20, 0x31

WORDS = ((0x80000008, 4), (0x8000000C, 4), (0x100B14D4, 4), (0x100B14D8, 4), (EDIT_FLAG, 4))
SYMS = ("pm_gl_a", "pm_gl_m", "pm_pa", "pm_pm", "pm_ef_a", "pm_ef_m")
LAYER_B = 0x100B14DD                            # battery SRAM: bit 0 = PATTERN layer
LED_CD, LED_BM, CUR_TRACK = 0x460BA9CC, 0x460BA9AE, 0x80000000


class Script:
    def __init__(self):
        self.t, self.lines = 1500.0, []

    def send(self, x, gap=60):
        self.lines.append(f"{self.t:.0f} {x}")
        self.t += gap

    def dn(self, k, gap=60):
        self.send(f"key {k:#x} down", gap)

    def up(self, k, gap=300):
        self.send(f"key {k:#x} up", gap)

    def tap(self, k, gap=300):
        self.dn(k, 40)
        self.up(k, gap)

    def text(self):
        return "\n".join(self.lines + [f"{self.t + 1500:.0f} quit"]) + "\n"


def start(s):
    s.tap(NO, 500)


def func_t(s, t):
    s.dn(FUNC, 120)
    s.tap(t, 200)
    s.up(FUNC, 400)


def double_func(s):
    """FUNC tapped, then pressed again inside the stock window (14 UI ticks); the second press stays down."""
    s.dn(FUNC, 50)
    s.up(FUNC, 80)
    s.dn(FUNC, 120)


def pattern_key(s, trig):
    s.dn(PATTERN, 120)
    s.tap(trig, 200)
    s.up(PATTERN, 500)


def sc_global(s):
    start(s); func_t(s, T1)


def sc_layer(s):
    start(s)
    s.dn(FUNC, 50); s.up(FUNC, 80); s.dn(FUNC, 50); s.up(FUNC, 500)


def sc_pattern(s):
    start(s); double_func(s); s.tap(T8, 200); s.up(FUNC, 600)


def sc_away(s):
    sc_pattern(s); pattern_key(s, TRIG2)


def sc_back(s):
    sc_away(s); pattern_key(s, TRIG1)


def sc_midi(s):
    start(s); s.tap(MIDI, 600); func_t(s, T1)
    double_func(s); s.tap(T1, 200); s.up(FUNC, 600)


def sc_save(s):
    sc_pattern(s)
    s.tap(PROJ, 1000); s.tap(RIGHT, 700); s.tap(DOWN, 500); s.tap(YES, 1100); s.tap(YES, 30000)


SCENARIOS = {"global": sc_global, "layer": sc_layer, "pattern": sc_pattern, "away": sc_away,
             "back": sc_back, "midi": sc_midi, "save": sc_save}


def build(remix):
    """The image and the linked symbols of this remix, as verify_scenes builds them."""
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_pattern_mute: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    shutil.copy2(IMAGE, OUT / "image.bin")


def symbols():
    nm = subprocess.run(["m68k-elf-nm", str(ELF)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}


def record_dump(base):
    """Track records' mute byte for pattern 0 and 1: from byte 31 of the pattern record to the last track."""
    return (base + REC_OFF, 7 * REC_STRIDE + 1), (base + PAT_STRIDE + REC_OFF, 7 * REC_STRIDE + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    a = ap.parse_args()
    if not a.remix:
        sys.exit("verify_pattern_mute: a REMIX")
    if "PATTERN MUTE" not in registry.remix(a.remix).modules:
        print(f"  [ -- ] verify_pattern_mute: {a.remix} carries no PATTERN MUTE")
        return 0
    if not EMU.is_file():
        print("  [SKIP] verify_pattern_mute: no port binary (make emu-cf)")
        return 0
    if not a.project:
        pf = pathlib.Path.home() / ".octabam_project"
        a.project = pf.read_text().strip() if pf.is_file() else ""
    if not a.project:
        print("  [SKIP] verify_pattern_mute: no project (--project, OT_PROJECT or ~/.octabam_project)")
        return 0
    sys.path.insert(0, str(ROOT / "tools/emu"))
    import emu_card

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    build(a.remix)
    proj = OUT / "project"
    shutil.copytree(pathlib.Path(a.project).expanduser(), proj)
    pw = (proj / "project.work").read_bytes()
    m = re.search(rb"\[STATES\]\r?\nBANK=(\d+)", pw)
    bank = int(m.group(1)) if m else 0
    base = BANK0 + bank * BANK_STRIDE
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "SCN",
                        "--tree", str(OUT / "tree"), "--out", str(OUT / "card.img")],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_pattern_mute: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    sym = symbols()
    ram0, ram1 = record_dump(base)
    cs0, cs1 = record_dump(CS1_PAT)
    scen = []
    for tag, fn in SCENARIOS.items():
        s = Script(); fn(s)
        (OUT / f"{tag}.script").write_text(s.text())
        dumps = {f"w{i}": w for i, w in enumerate(WORDS)}
        dumps.update({n: (sym[n], 4) for n in SYMS})
        dumps.update({"layer": (LAYER_B, 1), "trk": (CUR_TRACK, 1), "ledcd": (LED_CD, 4 * 80), "ledbm": (LED_BM, 17)})
        if tag == "save":
            dumps["sram"] = (0x10000000, 0x100000)
        dumps.update({"ram0": ram0, "ram1": ram1, "cs0": cs0, "cs1": cs1})
        dump = ";".join(f"{ad:#x},{ln:#x}={OUT / f'{tag}_{k}.bin'}" for k, (ad, ln) in dumps.items())
        extra = f" --card-out {OUT / (tag + '.img')}" if tag == "save" else ""
        scen += ["--scenario", f"{OUT / (tag + '.txt')} --live-script {OUT / (tag + '.script')}{extra} --mem-dump {dump}"]
    cmd = [str(EMU), "--image", str(OUT / "image.bin"), "--card", str(OUT / "card.img"), "--set", "OCTABAM", "--project", "SCN",
           "--load-ms", "90000", "--mkii", "--scenario-jobs", "4"] + scen
    with open(OUT / "port.txt", "w") as f:
        rc = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    check(f"the port ran every scenario (exit {rc})", rc == 0)

    def u32(tag, k):
        p = OUT / f"{tag}_{k}.bin"
        return struct.unpack(">I", p.read_bytes()[:4])[0] if p.is_file() else None

    def u8(tag, k, off):
        p = OUT / f"{tag}_{k}.bin"
        return p.read_bytes()[off] if p.is_file() and len(p.read_bytes()) > off else None

    def state(tag):
        return dict(wa=u32(tag, "w0"), wm=u32(tag, "w1"), ma=u32(tag, "w2"), mm=u32(tag, "w3"), edit=u32(tag, "w4"),
                    **{n: u32(tag, n) for n in SYMS}, pm_layer=u8(tag, "layer", 0))

    def led(tag):
        """(countdown, bitmap bit) of the odd bit of the current track's key."""
        t = u8(tag, "trk", 0)
        if t is None:
            return None, None
        i = 8 * (5 + (t >> 2)) + 2 * (t & 3) + 1
        cd = (OUT / f"{tag}_ledcd.bin").read_bytes()[4 * i:4 * i + 4]
        bm = u8(tag, "ledbm", i >> 3)
        return struct.unpack(">I", cd)[0], (bm >> (i & 7)) & 1 if bm is not None else None

    G0, M0 = 0x7F00, 0xFF00                     # the fixture's TRACK_MUTE_MASK=127, MIDI_TRACK_MUTE_MASK=255
    s = state("global")
    check(f"global: FUNC+T1 -> word {s['wa']:#x}, GLOBAL {s['pm_gl_a']:#x}, mirror {s['ma']:#x}, layer {s['pm_layer']!r}"
          if s["wa"] is not None else "global: no dump",
          s["wa"] == 0x7E00 and s["pm_gl_a"] == 0x7E00 and s["ma"] == 0x7E00 and s["pm_pa"] == 0 and s["pm_layer"] == 0)
    cd, bit = led("global")
    check(f"global: the current track key's second colour is not held (countdown {cd}, bit {bit})", cd == 0)

    s = state("layer")
    check(f"layer: two FUNC presses flip the layer: {s['pm_layer']!r}" if s["pm_layer"] is not None else "layer: no dump",
          s["pm_layer"] == 1 and s["wa"] == G0)

    s = state("pattern")
    p0 = u8("pattern", "ram0", 7 * REC_STRIDE)
    c0 = u8("pattern", "cs0", 7 * REC_STRIDE)
    check(f"pattern: FUNC+T8 in the PATTERN layer -> word {s['wa']:#x} = GLOBAL {s['pm_gl_a']:#x} | PATTERN {s['pm_pa']:#x}"
          if s["wa"] is not None else "pattern: no dump",
          s["wa"] == 0xFF00 and s["pm_gl_a"] == G0 and s["pm_pa"] == 0x8000 and s["pm_layer"] == 1)
    cd, bit = led("pattern")
    check(f"pattern: the current track key's second colour is held lit (countdown {cd}, bitmap bit {bit})", bool(cd) and bit == 1)
    check(f"pattern: the mirror keeps the GLOBAL layer: {s['ma']:#x}" if s["ma"] is not None else "pattern: no mirror",
          s["ma"] == G0)
    check(f"pattern: A01 track 8 record RAM {p0!r}, CS1 {c0!r}; bank edited flag {s['edit']!r}",
          p0 is not None and p0 & 3 == 1 and c0 == p0 and s["edit"] == 1)

    s = state("away")
    check(f"away: pattern 2 has no PATTERN mutes: word {s['wa']:#x}, PATTERN {s['pm_pa']:#x}" if s["wa"] is not None else "away: no dump",
          s["wa"] == G0 and s["pm_pa"] == 0)
    s = state("back")
    check(f"back: A01's PATTERN layer returns: word {s['wa']:#x}, PATTERN {s['pm_pa']:#x}" if s["wa"] is not None else "back: no dump",
          s["wa"] == 0xFF00 and s["pm_pa"] == 0x8000)

    s = state("midi")
    r0 = u8("midi", "ram0", 0)
    check(f"midi: GLOBAL then PATTERN on the MIDI word: word {s['wm']:#x}, GLOBAL {s['pm_gl_m']:#x}, PATTERN {s['pm_pm']:#x}, "
          f"mirror {s['mm']:#x}, track 1 record {r0!r}" if s["wm"] is not None else "midi: no dump",
          s["wm"] == M0 and s["pm_gl_m"] == 0xFE00 and s["pm_pm"] == 0x0100 and s["mm"] == 0xFE00 and r0 is not None and r0 & 2 == 2)

    img = OUT / "save.img"
    if img.is_file():
        files = emu_card.extract_image(img.read_bytes())
        bk = files.get(f"OCTABAM/SCN/bank{bank + 1:02d}.work")
        pwk = files.get("OCTABAM/SCN/project.work")
        rec = None
        if bk:
            rec = bk[0x16 + 8 + 7 * 0x922 + 40]    # pattern A01, audio track 8, file offset 40
        mask = re.search(rb"TRACK_MUTE_MASK=(\d+)", pwk or b"")
        check(f"save: bank file A01 track 8 record byte {rec!r}, project.work TRACK_MUTE_MASK {mask.group(1).decode() if mask else None}",
              rec is not None and rec & 1 == 1 and mask is not None and int(mask.group(1)) == G0 >> 8)
    else:
        check("save: no card image written", False)
    cs1 = OUT / "save_sram.bin"
    if img.is_file() and cs1.is_file():
        d = OUT / "reboot"
        d.mkdir()
        (d / "q.script").write_text("2500 quit\n")
        dumps = {f"w{i}": w for i, w in enumerate(WORDS)}
        dumps.update({n: (sym[n], 4) for n in SYMS})
        dumps.update({"layer": (LAYER_B, 1), "trk": (CUR_TRACK, 1), "ledcd": (LED_CD, 4 * 80), "ledbm": (LED_BM, 17)})
        dump = ";".join(f"{ad:#x},{ln:#x}={OUT / f'reboot_{k}.bin'}" for k, (ad, ln) in dumps.items())
        cmd = [str(EMU), "--image", str(OUT / "image.bin"), "--card", str(img), "--set", "OCTABAM", "--project", "SCN",
               "--load-ms", "90000", "--mkii", "--cs1-in", str(cs1),
               "--live-script", str(d / "q.script"), "--mem-dump", dump]
        with open(d / "port.txt", "w") as f:
            rc2 = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
        s = state("reboot")
        cd, bit = led("reboot")
        check(f"reboot: power cycle on the saved card and SRAM: layer {s['pm_layer']!r}, word {s['wa']!r}, "
              f"GLOBAL {s['pm_gl_a']!r}, PATTERN {s['pm_pa']!r}, mirror {s['ma']!r}, key countdown {cd}",
              rc2 == 0 and s["pm_layer"] == 1 and s["wa"] == 0xFF00 and s["pm_gl_a"] == G0 and s["pm_pa"] == 0x8000
              and s["ma"] == G0 and bool(cd))
    else:
        check("reboot: no saved card or SRAM image", False)
    print(f"verify_pattern_mute: {fails} failure(s) -- {OUT}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
