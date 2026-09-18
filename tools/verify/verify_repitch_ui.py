#!/usr/bin/env python3
"""REPITCH on the panel: the firmware's own page drawers under the Python
emulator (tools/emu/emu_bringup.py), on the built image.

    .venv/bin/python3 tools/verify/verify_repitch_ui.py [REMIX] [--image FILE]

  setup   PLAYBACK SETUP (STATIC and FLEX) draws TSTR 0..4 as OFF AUTO NORM
          BEAT RPCH on the five-position select's icons -- stock's four-
          position select draws nothing for 4, which read as a blank value
  ptch    the PLAYBACK page draws PTCH's dial unless the track is on
          REPITCH (SETUP TSTR = REPITCH, or AUTO with the bound sample's
          own TIMESTRETCH = REPITCH); the other five dials always draw
  attr    the audio editor's ATTR page (0x4006e450) prints the sample's
          TIMESTRETCH 0/2/3/4 as OFF NORMAL BEAT REPITCH, ERROR past it
          (its value keys are run by repitch_probe)

What it cannot see: pixels (strings and bitmap calls are captured, not the
LCD).
SKIPs without the .venv (make emu-setup).
"""
import argparse, os, pathlib, shutil, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAYBACK_SETUP_OPEN = 0x400584D0
DIAL = 0x400BD15A                 # the knob's dial background bitmap
SELECT5_ICONS = [0x400BE28E, 0x400BE2A2, 0x400BE2B6, 0x400BE2CA, 0x400BE2DE]
SETUP_OFF = 0x8EF5A               # Part + track*30 + machine*6 + slot
LANES, VOICES = 0x80000510, 0x800049D8
FAKE_SETTINGS = 0x47E00000
TRACK = 2
PTCH_DIAL_XY = (64, 40)
ATTR_ROWS, ATTR_DRAW = 0x4006E91C, 0x4006E450


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default="repitch")
    ap.add_argument("--image", default="", help="a built image (default: build REMIX)")
    a = ap.parse_args()
    remix = a.remix
    try:
        import emu_bringup as emu
        from unicorn import UC_HOOK_CODE, UcError
        from unicorn.m68k_const import UC_M68K_REG_A7
    except ImportError:
        print("  [SKIP] verify_repitch_ui: no .venv (make emu-setup)")
        return 0
    if not emu.HAVE_UNICORN:
        print("  [SKIP] verify_repitch_ui: unicorn not installed (make emu-setup)")
        return 0
    image = pathlib.Path(a.image) if a.image else ROOT / "out/repitch_ui/image.bin"
    if not a.image:
        env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_repitch_ui: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        image.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)

    boot = emu.boot(str(image))
    uc = boot.uc
    emu._prime_menu(boot)
    bitmaps = []

    def bitmap_hook(u, address, size, user):
        sp = u.reg_read(UC_M68K_REG_A7)
        rd = lambda o: int.from_bytes(u.mem_read(sp + o, 4), "big")
        bitmaps.append((rd(4), rd(12), rd(16)))
    uc.hook_add(UC_HOOK_CODE, bitmap_hook, begin=0x400128A8, end=0x400128A8)

    emu._prime_part(boot)
    uc.mem_write(emu.CUR_TRACK_B, bytes([TRACK]))
    uc.mem_write(0x100B14CC, TRACK.to_bytes(4, "big"))
    uc.mem_write(emu.PAT_W, b"\0")
    uc.mem_write(emu.PAT_R, b"\0")
    uc.mem_write(FAKE_SETTINGS, bytes(0x448))
    uc.mem_write(FAKE_SETTINGS + 0x114, (2880).to_bytes(4, "big"))
    uc.mem_write(VOICES + 168 * TRACK + 8, FAKE_SETTINGS.to_bytes(4, "big"))

    def state(machine, tstr, tsmode):
        uc.mem_write(emu._part_addr(uc, emu.MACHINE_OFF, TRACK), bytes([machine]))
        uc.mem_write(emu._part_addr(uc, SETUP_OFF, TRACK, 6 * machine + 4, track_stride=30), bytes([tstr]))
        uc.mem_write(LANES + 48 * TRACK + 28, bytes([tstr]))
        uc.mem_write(FAKE_SETTINGS + 0x110, tsmode.to_bytes(4, "big"))

    def render(opener):
        bitmaps.clear()
        boot._draws.clear()
        try:
            opener()
        except UcError as e:
            return None, [], str(e)
        return list(boot._draws), list(bitmaps), None

    def setup_page():
        emu._call_page(uc, PLAYBACK_SETUP_OPEN, boot._draws)

    def playback_page():
        emu._call(uc, emu.PAGE_STAGE, (0,))
        boot._draws.clear()
        bitmaps.clear()
        emu._call(uc, emu.TRACK_DRAW)

    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += not ok
        print(f"  [{'ok' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    labels = ["OFF", "AUTO", "NORM", "BEAT", "RPCH"]
    for machine, name in ((0, "STATIC"), (1, "FLEX")):
        got = []
        for v in range(5):
            state(machine, v, 2)
            draws, bms, err = render(setup_page)
            cell = [t for x, y, t in (draws or []) if y == 3 and 70 <= x <= 90]
            icons = [b for b, _x, _y in bms if b in SELECT5_ICONS]
            got.append((cell, icons, err))
            try:                            # the opener toggles: close it again
                emu._call(uc, PLAYBACK_SETUP_OPEN)
            except UcError:
                pass
        ok = all(c == [labels[v]] and i == [SELECT5_ICONS[v]] and e is None for v, (c, i, e) in enumerate(got))
        check(f"setup: {name} TSTR 0..4 draw {' '.join(labels)} on the five-position icons", ok,
              "" if ok else str(got))

    for machine, name in ((0, "STATIC"), (1, "FLEX")):
        for tstr, tsmode, off in ((0, 4, False), (2, 4, False), (4, 2, True), (1, 2, False), (1, 4, True)):
            state(machine, tstr, tsmode)
            _draws, bms, err = render(playback_page)
            dials = sorted({(x, y) for b, x, y in bms if b == DIAL})
            ok = err is None and len(dials) == (5 if off else 6) and ((PTCH_DIAL_XY in dials) != off)
            check(f"ptch: {name} TSTR {tstr} sample TSMODE {tsmode}: PTCH dial "
                  f"{'hidden' if off else 'drawn'}, the other five drawn", ok,
                  "" if ok else f"dials {dials} {err or ''}")
    # The audio editor's ATTR page, FLEX slot 1, drawn on the SETUP window's
    # canvas: the editor's kind/slot globals, the slot record's "loaded"
    # gate, the page's own row-list setup, then its draw.
    # The SETUP renders above leave the window closed (its opener toggles).
    render(setup_page)
    handle = int.from_bytes(uc.mem_read(0x400BB7C8 + 8, 4), "big")
    if not handle:
        check("attr: the SETUP window reopened for a canvas", False)
        return 1
    attr_canvas = handle + 36
    settings = 0x100B14F0
    for addr, val in ((0x46C8D1A0, 1), (0x46C8D19C, 0), (0x46105408, 1), (0x46C922C4 + 8, 0)):
        uc.mem_write(addr, val.to_bytes(4, "big"))
    uc.mem_write(settings + 0x114, (2880).to_bytes(4, "big"))
    want = {0: "OFF", 2: "NORMAL", 3: "BEAT", 4: "REPITCH", 5: "ERROR"}
    got = {}
    for v in want:
        uc.mem_write(settings + 0x110, v.to_bytes(4, "big"))
        try:
            emu._call(uc, ATTR_ROWS)
            boot._draws.clear()
            emu._call(uc, ATTR_DRAW, (attr_canvas,))
        except UcError as e:
            got[v] = str(e)
            continue
        row = {y for x, y, t in boot._draws if t == "TIMESTRETCH"}
        got[v] = [t for x, y, t in boot._draws if y in row and x > 40]
    ok = all(got[v] == [want[v]] for v in want)
    check("attr: TIMESTRETCH 0/2/3/4/5 draws OFF NORMAL BEAT REPITCH ERROR", ok, "" if ok else str(got))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
