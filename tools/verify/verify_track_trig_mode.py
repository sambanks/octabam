#!/usr/bin/env python3
"""TRACK TRIG MODE under the port: per-track CHROMATIC / SLOTS / SLICES,
saved with the project.

    python3 tools/verify/verify_track_trig_mode.py REMIX

Each boot loads a project whose project.work holds "#TRIG_MODES=12300000"
(T1 CHROMATIC, T2 SLOTS, T3 SLICES). A FUNC hold's first UP / DOWN opens
the trig-mode popup; the second steps it.

  load     the project loads: tm_mode reads 1 2 3 0 0 0 0 0.
  switch   (MKI) the load shows T1's CHROMATIC (tm_boot); FUNC + DOWN ->
           SLOTS, kept for T1; T2 -> its own SLOTS (no change), T3 -> SLICES;
           FUNC + DOWN -> QUICK MUTE, not kept; T1 -> still QUICK MUTE
           (global); FUNC + UP steps out of it to SLICES, which lands on
           T1's own SLOTS instead and writes nothing (28 Oct 2026, on the
           MKI: a step out of QUICK MUTE overwrote the track's mode); T2,
           T1 -> SLOTS, no change; FUNC + UP -> CHROMATIC, kept for T1 (the
           list's cursor was moved to SLOTS). The trig mode's writes are,
           in order, 1 2 3 4 3 2 1.
  save     (MKII, FUNC + PROJ) the load shows T1's CHROMATIC; T4 (unset)
           keeps it; FUNC + DOWN -> SLOTS, kept for T4; SAVE: the saved
           project.work has "#TRIG_MODES=12320000" right before [/SETTINGS].
  stock    that saved card on the stock OS (out/raw/section_3_MAIN_OS.bin):
           the parser ends at its success return 0x4008827a, never at the
           unknown-key error 0x40086d3a (-51). The comment keeps the project
           loading on stock.
  reload   the saved card on this image: tm_mode reads 1 2 3 2 0 0 0 0.
  power    a power cycle: the saved card, CS1 as the save left it, the
           firmware's own power-up load (no LOAD PROJECT post; it restores
           from CS1 and never parses project.work -- 27 Oct 2026 on the MKI
           the modes were gone after a power cycle while the table was
           DRAM). The current track T4's SLOTS shows at the load (tm_boot);
           T2 -> its own SLOTS (no change), T3 -> SLICES.

Cannot see: the trig LEDs and the mode label (DRAW_MODE is called; what it
draws is not decoded here), MIDI mode, the hardware.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "emu"))
import emu_card  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
OUT = ROOT / "out/track-trig-mode-verify"   # (subprocess args are a list: a space in ROOT is safe)
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
TMODE = 0x460D16F0
TM = 0x100F85E8                        # the table, battery RAM (CS1)
OK_RET, BAD_KEY = 0x4008827A, 0x40086D3A
YES, NO, FUNC, UP, DOWN, PROJ = 0x31, 0x32, 0x2D, 0x33, 0x20, 0x1C
T1, T2, T3, T4 = 0x10, 0x11, 0x12, 0x13
WORK = "#TRIG_MODES=12300000\n[STATES]\nBANK=0\n\n"


def tap(t, k):
    return [f"{t} key {k:#x} down", f"{t + 60} key {k:#x} up"]


def step(t, k):
    """FUNC held, two presses: the first opens the popup, the second steps."""
    return [f"{t} key {FUNC:#x} down"] + tap(t + 300, k) + tap(t + 900, k) + [f"{t + 1400} key {FUNC:#x} up"]


PRE = tap(1500, YES) + tap(3000, YES) + tap(5000, YES)          # the date dialog
SWITCH = (PRE + step(6000, DOWN) + tap(8200, T2) + tap(9200, T3) + step(10200, DOWN) + tap(12400, T1)
          + step(13400, UP) + tap(15600, T2) + tap(16600, T1) + step(17600, UP), 20000)
SAVE = ([f"500 key {NO:#x} down", f"560 key {NO:#x} up"] + tap(2000, T4) + step(3000, DOWN) + tap(5500, NO)
        + [f"6500 key {FUNC:#x} down", f"6560 key {PROJ:#x} down", f"6620 key {PROJ:#x} up", f"6680 key {FUNC:#x} up"]
        + tap(8000, YES), 40000)


def stage(work):
    project = work / "project"
    project.mkdir(parents=True)
    (project / "project.work").write_text(WORK)
    (project / "project.strd").write_text(WORK)
    card = work / "card.img"
    subprocess.run([str(ROOT / ".venv/bin/python3"), "tools/emu/ot_emu/stage_card.py", str(project), "OCTABAM", "TMODE",
                    "--tree", str(work / "tree"), "--out", str(card)], cwd=ROOT, check=True, capture_output=True)
    return card


def boot(work, name, image, card, script, quit_ms, tm, mkii=False, extra=()):
    (work / f"{name}.script").write_text("\n".join(script + [f"{quit_ms} quit"]) + "\n")
    args = [str(EMU), "--image", str(image), "--card", str(card), "--card-out", str(work / f"{name}.img"),
            "--set", "OCTABAM", "--project", "TMODE", "--load-ms", "90000", *(["--mkii"] if mkii else []),
            "--watch-mem", f"{TMODE:#x},4;{tm:#x},8", "--watch-pc", f"{OK_RET:#x},{BAD_KEY:#x},0x400866c4",
            "--live-script", str(work / f"{name}.script"), *map(str, extra)]
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=1800)
    log = r.stdout + r.stderr
    (work / f"{name}.log").write_text(log)
    return r.returncode, log


def table(log, tm):
    """tm_mode's 8 bytes after the boot's last write to each."""
    b = [0] * 8
    for a, val in re.findall(r"\] \[(0x[0-9a-f]+)\] <- (\S+) \(\d\)", log):
        a = int(a, 16)
        if tm <= a < tm + 8:
            b[a - tm] = int(val, 0)   # 4-byte clears land at tm and tm+4; only their first byte matters below
    return b


def modes(log):
    return [int(v, 0) for v in re.findall(rf"\] \[{TMODE:#x}\] <- (\S+) \(4\)", log)]


def main():
    remix = sys.argv[1]
    if "TRACK TRIG MODE" not in registry.remix(remix).modules:
        return 0
    if not EMU.is_file():
        print("  [SKIP] verify_track_trig_mode: no port (make emu-cf)")
        return 0
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    if "--no-build" not in sys.argv:           # --no-build: gate the image already in out/
        env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
        subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, check=True)
    image = OUT / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    tm = TM

    cards = {n: stage(OUT / n) for n in ("switch", "save")}
    with ThreadPoolExecutor(max_workers=2) as pool:
        sw = pool.submit(boot, OUT / "switch", "switch", image, cards["switch"], *SWITCH, tm)
        sv = pool.submit(boot, OUT / "save", "save", image, cards["save"], *SAVE, tm, True,
                         ("--mem-dump", f"0x10000000,0x100000={OUT / 'save' / 'cs1.bin'}"))
        (rc_sw, log_sw), (rc_sv, log_sv) = sw.result(), sv.result()
    saved = OUT / "save" / "save.img"
    with ThreadPoolExecutor(max_workers=3) as pool:
        st = pool.submit(boot, OUT / "save", "stock", STOCK, saved, [], 100, tm)
        rl = pool.submit(boot, OUT / "save", "reload", image, saved, [], 100, tm)
        pw = pool.submit(boot, OUT / "save", "power", image, saved, tap(1500, T2) + tap(2500, T3), 3500, tm, True,
                         ("--boot-load", "--cs1-in", OUT / "save" / "cs1.bin"))
        (rc_st, log_st), (rc_rl, log_rl), (rc_pw, log_pw) = st.result(), rl.result(), pw.result()

    fails = []

    def check(ok, what):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}")
        if not ok:
            fails.append(what)

    check(rc_sw == rc_sv == rc_st == rc_rl == rc_pw == 0, "every boot exits 0")
    parsed = [int(v, 0) for v in re.findall(r"<- (\S+) \(1\) at pc", log_sw)][:8]
    check(parsed == [1, 2, 3, 0, 0, 0, 0, 0], "load: tm_mode 1 2 3 0 0 0 0 0 from #TRIG_MODES=")
    got = modes(log_sw)
    check(got == [1, 2, 3, 4, 3, 2, 1], f"switch: trig mode writes 1 2 3 4 3 2 1 (got {' '.join(map(str, got))})")
    check(table(log_sw, tm)[:4] == [1, 2, 3, 0],
          f"switch: tm_mode 1 2 3 0 (QUICK MUTE not kept, its exit kept T1's SLOTS) (got {table(log_sw, tm)[:4]})")
    files = emu_card.extract_image(saved.read_bytes()) if saved.is_file() else {}
    text = files.get("OCTABAM/TMODE/project.work", b"").decode(errors="replace")
    check("#TRIG_MODES=12320000\r\n[/SETTINGS]" in text, "save: #TRIG_MODES=12320000 before [/SETTINGS]")
    check(f"at {OK_RET:#x}" in log_st and f"at {BAD_KEY:#x}" not in log_st,
          "stock: the saved project parses to success, no unknown-key error")
    check(table(log_rl, tm)[:8] == [1, 2, 3, 2, 0, 0, 0, 0], "reload: tm_mode 1 2 3 2 0 0 0 0")
    check("at 0x400866c4" not in log_pw, "power: the power-up load does not parse project.work (CS1 kept)")
    got = [m for i, m in enumerate(modes(log_pw)) if i == 0 or m != modes(log_pw)[i - 1]]   # the load writes once a bank read
    check(got == [2, 3], f"power: T4 SLOTS at the load, T2 SLOTS, T3 SLICES (got {' '.join(map(str, got))})")
    if fails:
        print(f"  verify_track_trig_mode: {len(fails)} FAIL")
        return 1
    print("  verify_track_trig_mode: ALL GOOD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
