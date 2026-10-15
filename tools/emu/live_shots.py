#!/usr/bin/env python3
"""Capture the remix's screens on the port: a scripted panel, PNG per shot.

    python3 tools/emu/live_shots.py octabam-core --script tools/site/shots/octabam-core.script

Builds the remix (BUILD=91), stages the gate project onto a scratch card
the way tools/emu/live.py does, boots `ot_emu --live <fifo> --lcd <file>`
and drives the panel through the FIFO. The boot's date prompt is cleared
with exactly one [NO]; the script then runs one directive per line:

    key 0xNN                 tap (down, hold, up)
    chord 0xNN 0xNN          press both, release second first (FUNC + key)
    hold 0xNN / release 0xNN hold and release a key (a page held for a shot)
    enc <n> <delta>          encoder turn (0-5 = A-F, 6 = LEVEL)
    wait <s>                 wall-clock sleep
    shot <module>/<screen>   dump docs/site/img/<module>/<screen>.png
    quit                     stop the script early

Blank lines and `#` comments are ignored. A `shot` settles 0.6 s first so
the screen has drawn; `key`/`chord`/`enc` settle 0.25 s after. The LCD
plane is written by the port every 30 ms while dirty, so shots are the
screen as the firmware left it. `--keep-card` keeps out/live/card.img.
"""
import argparse, os, pathlib, shutil, subprocess, sys, tempfile, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import ot_project as otp  # noqa: E402
import verify_set as vs  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/live"
IMG = ROOT / "docs/site/img"


def tap(fd, code):
    os.write(fd, f"key 0x{code:02x} down\n".encode()); time.sleep(0.07)
    os.write(fd, f"key 0x{code:02x} up\n".encode()); time.sleep(0.25)


def chord(fd, first, second):
    os.write(fd, f"key 0x{first:02x} down\n".encode()); time.sleep(0.05)
    os.write(fd, f"key 0x{second:02x} down\n".encode()); time.sleep(0.07)
    os.write(fd, f"key 0x{second:02x} up\n".encode()); time.sleep(0.05)
    os.write(fd, f"key 0x{first:02x} up\n".encode()); time.sleep(0.25)


def shot(lcd, module, screen, scale):
    time.sleep(0.6)
    target = IMG / module / f"{screen}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/lcd_view.py"), str(lcd),
                        "--png", str(target), "--scale", str(scale)], cwd=ROOT)
    if r.returncode:
        raise RuntimeError(f"shot {module}/{screen}: lcd_view exited {r.returncode}")
    print(f"shot       : {target.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("remix")
    ap.add_argument("--script", required=True, help="one directive per line")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--bank", type=int, default=int(os.environ.get("OT_BANK", "0") or 0))
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--keep-card", action="store_true")
    ap.add_argument("--dsp", action="store_true", help="run the DSP pair (PLAY can then make audio)")
    ap.add_argument("--audio-in", default="", help="ot_emu --audio-in: a WAV onto RX0, or 'tones'")
    ap.add_argument("--main-level", default="64",
                    help="ot_emu --main-level, posted after the load ('off' = never; the port only defaults it under --interactive, and unposted every voice is silent -- O9b)")
    a = ap.parse_args()

    if not a.project:
        p = pathlib.Path.home() / ".octabam_project"
        a.project = p.read_text().strip() if p.is_file() else ""
    if not a.project:
        sys.exit("live_shots: no project (OT_PROJECT=<dir>, --project, or ~/.octabam_project)")
    if not EMU.exists():
        sys.exit("live_shots: the port is not built -- make emu-cf")
    pdir = pathlib.Path(a.project).expanduser()

    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1", BUILD="91")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"live_shots: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "image.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)

    raw = (pdir / "project.work").read_bytes()
    import re
    m = re.search(rb"\r\nBANK=(\d+)\r\n", raw)
    bank = a.bank or (int(m.group(1)) + 1 if m else 1)
    pat_part, _ = otp.bank_info(pdir, bank)
    part = vs.part_of(pdir, bank, pat_part[0] + 1)
    card = OUT / "card.img"
    audio, mb = vs.stage(pdir, part, "OCTABAM", "RIG", OUT / "tree", 64, bank, card)
    print(f"live_shots: {a.remix} on {pdir.name} bank {bank}, card {mb} MB, {len(audio)} sample file(s)")

    work = pathlib.Path(tempfile.mkdtemp(prefix="emshot."))
    fifo, lcd, log = work / "panel", OUT / "lcd.bin", OUT / "port.txt"
    os.mkfifo(fifo)
    cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM",
           "--project", "RIG", "--load-ms", "90000", "--live", str(fifo), "--lcd", str(lcd), "--mkii"]
    if a.dsp:
        cmd.append("--dsp")
    if a.audio_in:
        cmd += ["--audio-in", a.audio_in]
    if a.main_level != "off":
        cmd += ["--main-level", a.main_level]
    with open(log, "w") as lf:
        port = subprocess.Popen(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
        keep = os.open(fifo, os.O_RDWR)              # holds the FIFO open for the port
        try:
            deadline = time.time() + 300   # --dsp boots run ~4x slower than real time
            while port.poll() is None and "live       : reading panel" not in log.read_text():
                if time.time() > deadline:
                    raise RuntimeError("the port never reached the live phase")
                time.sleep(0.2)
            if port.poll() is not None:
                raise RuntimeError(f"the port stopped during boot -- {log}")
            time.sleep(1.5)
            tap(keep, 0x32)                          # the one NO: clears SET DATE/TIME
            time.sleep(3.0)
            for line in pathlib.Path(a.script).read_text().splitlines():
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                w = line.split()
                if w[0] == "quit":
                    break
                if w[0] == "key" and len(w) == 2:
                    tap(keep, int(w[1], 0))
                elif w[0] == "chord" and len(w) == 3:
                    chord(keep, int(w[1], 0), int(w[2], 0))
                elif w[0] == "hold" and len(w) == 2:
                    os.write(keep, f"key 0x{int(w[1], 0):02x} down\n".encode()); time.sleep(0.15)
                elif w[0] == "release" and len(w) == 2:
                    os.write(keep, f"key 0x{int(w[1], 0):02x} up\n".encode()); time.sleep(0.25)
                elif w[0] == "enc" and len(w) == 3:
                    os.write(keep, f"enc {int(w[1])} {int(w[2])}\n".encode()); time.sleep(0.25)
                elif w[0] == "wait" and len(w) == 2:
                    time.sleep(float(w[1]))
                elif w[0] == "shot" and len(w) == 2:
                    module, _, screen = w[1].partition("/")
                    shot(lcd, module, screen, a.scale)
                else:
                    print(f"live_shots: unknown line {line!r}")
            if port.poll() is None:
                os.write(keep, b"quit\n")
                port.wait(timeout=20)
        finally:
            try:
                os.close(keep)
            except OSError:
                pass
            if port.poll() is None:
                port.send_signal(subprocess.signal.SIGTERM)
    print(f"live_shots: port log {log}")
    if not a.keep_card:
        card.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
