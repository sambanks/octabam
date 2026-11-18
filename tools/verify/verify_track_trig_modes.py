#!/usr/bin/env python3
"""TRACK TRIG MODES under the port (MKI): each track keeps its trig mode.

Each run boots the remix's image on a fresh project, dismisses the date
prompt and plays a panel script; at the end the trig mode (0x460d16f0) and
the module's sixteen bytes (T1-T8, M1-M8) are dumped and compared.

- sel:    T1 CHROMATIC (FUNC + DOWN), then T2: T2 is TRACKS (0).
- back:   ... T2 SLICES, then T1: CHROMATIC again (1); T1 = 1, T2 = 3 stored.
- again:  ... then T2: SLICES (3).
- midi:   T1 CHROMATIC, [MIDI]: M1 is TRACKS (0).
- mside:  ... M1 CHROMATIC, M2: TRACKS; [MIDI] back: T1 CHROMATIC (1).
- qmute:  T1 CHROMATIC, then QUICK MUTE (4), then T2: TRACKS (every mode
          is per track); T1 = QUICK MUTE stored.
- qback:  ... then T1 again: QUICK MUTE.
- dctl:   T3 DELAY CTRL (5), T1 SLOTS (2), back to T3: DELAY CTRL.
- mqm:    [MIDI], M1 QUICK MUTE (MIDI list row 2 without CHORDS, 3 with),
          M2, back to M1: QUICK MUTE.
- same:   T1 CHROMATIC, T1 pressed again: CHROMATIC.

The list's first FUNC + DOWN opens it at the current mode (measured: it
does not move); each further DOWN moves one row. The audio list is 0-5,
MIDI 0, 1, 4 (0, 1, 2, 4 with CHORDS).

Usage: verify_track_trig_modes.py [remix] [--no-build]  (default track-trig-modes;
--no-build: test out/mainos_bus.bin as built, `make bus REMIX=...` first)
"""
import os
import pathlib
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/verify"))
sys.path.insert(0, str(ROOT / "tools/emu"))
from remix import registry  # noqa: E402
import emu_card  # noqa: E402
import page_port as vt  # noqa: E402

FUNC, DOWN, UP, MIDI = 0x2d, 0x20, 0x33, 0x35
TRIG_MODE = 0x460d16f0
STEP = 300


class Script:
    def __init__(self):
        self.t, self.lines = 2400, []

    def tap(self, code):
        self.lines += vt.tap(self.t, code)
        self.t += STEP
        return self

    def mode(self, rows, key=DOWN):
        """FUNC held, DOWN (or UP) once to open the list, `rows` more taps, FUNC released."""
        self.lines.append((self.t, f"key {FUNC:#x} down"))
        self.t += 150
        for _ in range(rows + 1):
            self.tap(key)
        self.lines.append((self.t, f"key {FUNC:#x} up"))
        self.t += STEP
        return self

    def track(self, n):
        return self.tap(0x10 + n - 1)


def runs(chords):
    r = {}
    r["sel"] = (Script().mode(1).track(2), 0, {0: 1})
    r["back"] = (Script().mode(1).track(2).mode(3).track(1), 1, {0: 1, 1: 3})
    r["again"] = (Script().mode(1).track(2).mode(3).track(1).track(2), 3, {0: 1, 1: 3})
    r["midi"] = (Script().mode(1).tap(MIDI), 0, {0: 1})
    r["mside"] = (Script().mode(1).tap(MIDI).mode(1).track(2).tap(MIDI), 1, {0: 1, 8: 1})
    r["qmute"] = (Script().mode(1).mode(3).track(2), 0, {0: 4})
    r["qback"] = (Script().mode(1).mode(3).track(2).track(1), 4, {0: 4})
    r["dctl"] = (Script().track(3).mode(5).track(1).mode(2).track(3), 5, {2: 5, 0: 2})
    rows = 3 if chords else 2
    r["mqm"] = (Script().tap(MIDI).mode(rows).track(2).track(1), 4, {8: 4})
    r["same"] = (Script().mode(1).track(1), 1, {0: 1})
    return r


def run(out, image, mem, name, script):
    path = out / f"{name}.script"
    vt.page_script(path, sorted(script.lines), midi=False)
    dumps = f"{TRIG_MODE:#x},4={out}/{name}.mode;{mem:#x},16={out}/{name}.mem"
    cmd = [str(ROOT / "out/emu/ot_emu"), "--image", str(image), "--card", str(out / "card.img"),
           "--set", "OCTABAM", "--project", "TTM", "--load-ms", "90000",
           "--live-script", str(path), "--mem-dump", dumps]
    with (out / f"{name}.log").open("w") as f:
        return subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    remix = args[0] if args else "track-trig-modes"
    if "TRACK TRIG MODES" not in registry.remix(remix).modules:
        return 0
    out = ROOT / "out/ttm"
    fresh = out / "fresh"
    keep = fresh.exists() and "--no-build" in sys.argv     # ot_fresh's own cache, per image
    for p in out.iterdir() if out.exists() else ():
        if p != fresh or not keep:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    out.mkdir(parents=True, exist_ok=True)
    if "--no-build" not in sys.argv:
        env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
        subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, check=True)
    image = out / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    nm = subprocess.check_output(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")], text=True)
    mem = next(int(l.split()[0], 16) for l in nm.splitlines() if l.endswith(" ttm_mem"))
    card, _ = emu_card.stage_project(vt.fresh(out, image), "OCTABAM", "TTM", tree=out / "tree")
    (out / "card.img").write_bytes(card)

    cases = runs("CHORDS FACTORY" in registry.remix(remix).modules)
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        rcs = dict(zip(cases, pool.map(lambda kv: run(out, image, mem, kv[0], kv[1][0]), cases.items())))
    fails = 0
    for name, (_s, want_mode, want_mem) in cases.items():
        bad = []
        if rcs[name] != 0 or "ended on quit" not in (out / f"{name}.log").read_text():
            bad.append(f"the run exited {rcs[name]} or the script did not end")
        else:
            mode = int.from_bytes((out / f"{name}.mode").read_bytes(), "big")
            slots = list((out / f"{name}.mem").read_bytes())
            want = [want_mem.get(i, 0) for i in range(16)]
            if mode != want_mode:
                bad.append(f"trig mode {mode}, want {want_mode}")
            if slots != want:
                bad.append(f"slots {slots}, want {want}")
        print(f"{'ok  ' if not bad else 'FAIL'} {name}" + ("" if not bad else ": " + "; ".join(bad)))
        fails += bool(bad)
        if not bad:
            for p in out.glob(f"{name}.*"):
                p.unlink()
    print(f"verify_track_trig_modes: {len(cases) - fails}/{len(cases)} pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
