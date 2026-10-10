#!/usr/bin/env python3
"""MIDI SCENES oracle scenarios under the port: the same panel scripts on
each given image, MIDI OUT recorded with the frame of each byte, and the
MIDI track state dumped at the end of each scenario.

    python3 tools/verify/verify_scenes.py --image his=MAIN21.raw --image stock=out/raw/section_3_MAIN_OS.bin \
        [--project DIR] [--card CARD] [--out DIR] [--only b1,b7]

Phase 0 harness: records, compares nothing against a module. Each image
loads the project once; the scenarios fork from that load (`ot_emu
--scenario`). The fixture: bank 2 of OCTABAM89_setgate (its saved bank),
MIDI track 1 on channel 11 (Part byte `+0x4e2`, ch+1), MIDI track 2 off.

Scenarios (all start: NO for the date prompt, MIDI, T1, FX1 = CTRL1):

  b1      SCENE A held + knob D +40, SCENE B held + knob D +100 (CTRL1
          slot 3 = CC2), stopped.
  b7      b1, then the fader 255 / 128 / 1 / 255, stopped.
  b7play  b1, PLAY, then the fader 255 / 128 / 1 / 255.
  b3      b7, then SCENE A held + push knob D (row 0x27 bit 3), then the
          fader 1 / 255.
  b29copy b1, SCENE A held + REC (copy), SCENE B held + STOP (paste),
          then the fader 1 / 255.
  b29clear b1, SCENE A held + PLAY (clear), then the fader 1 / 255.
          (The scene-held key map: tables 0x400bae1c / 0x400bb18a, key 0x29
          REC -> copy 0x40062f60, 0x27 STOP -> paste 0x40062da0, 0x28 PLAY
          -> clear 0x40062e84.)

Per scenario: OUT/<image>/<tag>.midi (raw), .midi.frames (`frame hex..`,
frames since the script start, 16 samples each at 44.1 kHz), and the
dumps listed in DUMPS.
"""
import argparse, os, pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/scenesverify"

BANK0, BANK_STRIDE, PART_WINDOW, PART_STRIDE = 0x400e21e0, 0x9b340, 0x8ed80, 0x18b2
# Part window = bank base + 0x8ed80 + part * 0x18b2; bank file Part p at
# 0x8eed6 + p * 0x18bb, RAM offset + 9 (the chunk header).
FILE_PART, FILE_PSTRIDE, NPARTS_FILE = 0x8eed6, 0x18bb, 8
MIDI_SETUP, MIDI_SETUP_STRIDE = 0x4e2, 0x24      # Part offset; byte 0 = channel + 1, 0 = off
MIDI_PARAMS = 0x3e2                               # Part offset, 32 B per MIDI track: flat 0..29, CC enables 30/31
SCENE_B = 0x11                                    # Part offset: scene B's index (scene A at +0x10)
K = dict(no=0x32, midi=0x35, t1=0x10, t2=0x11, fx1=0x25, fx2=0x26, amp=0x23, play=0x28, stop=0x27,
         func=0x2d, scene_a=0x19, scene_b=0x1a, push_d=0x3b, rec=0x29)

DUMPS = {                                         # name: (address, length)
    "msc": (0x40a955e0, 0x2000),                  # his msc21_ram: MSC, clip, CKPT, TRIG_SNAP (his image only)
    "trk": (0x46c76dc0, 0x44 * 8),                # MIDI track records
    "lfoin": (0x46c78960, 0x100),                 # track*32 + flat
    "mask": (0x8000664e, 0x20),                   # active-lock mask, u32 per track
    "mode": (0x80000012, 4),                      # MIDI mode long
    "xf": (0x460d16c8, 4),
    "db": (0x46c82456, 4),
    "ui": (0x100b14cc, 4),                        # track, ?, ?, part
    "page": (0x460d1684, 4),
}


class Script:
    """A --live-script at emulated milliseconds."""

    def __init__(self):
        self.t, self.lines = 1500.0, []

    def send(self, x, gap=60):
        self.lines.append(f"{self.t:.0f} {x}"); self.t += gap

    def tap(self, k, gap=250):
        self.send(f"key {K[k]:#x} down", 40); self.send(f"key {K[k]:#x} up", gap)

    def turn(self, hold, enc, ticks):
        self.send(f"key {K[hold]:#x} down", 60)
        self.send(f"enc {enc} {ticks}", 200)
        self.send(f"key {K[hold]:#x} up", 300)

    def chord(self, hold, k):
        self.send(f"key {K[hold]:#x} down", 60); self.tap(k, 150); self.send(f"key {K[hold]:#x} up", 300)

    def pot(self, v, gap=500):
        self.send(f"pot {v}", gap)

    def text(self):
        return "\n".join(self.lines + [f"{self.t:.0f} quit"]) + "\n"


def start(s):
    s.tap("no", 400); s.tap("midi", 300); s.tap("t1", 300); s.tap("fx1", 400)


def b1(s):
    start(s); s.turn("scene_a", 3, 40); s.turn("scene_b", 3, 100)


def sweep(s, vals=(255, 128, 1, 255)):
    for v in vals:
        s.pot(v)


def b7(s):
    b1(s); sweep(s)


def b7play(s):
    b1(s); s.tap("play", 1000); sweep(s)


def b3(s):
    b7(s); s.chord("scene_a", "push_d"); sweep(s, (1, 255))


def b29copy(s):
    b1(s); s.chord("scene_a", "rec"); s.chord("scene_b", "stop"); sweep(s, (1, 255))


def b29clear(s):
    b1(s); s.chord("scene_a", "play"); sweep(s, (1, 255))


SCENARIOS = dict(b1=b1, b7=b7, b7play=b7play, b3=b3, b29copy=b29copy, b29clear=b29clear)


def fixture(src, dst):
    """Copy the project's .work files. In every Part of every bank: MIDI track 1
    on channel 11, its CC1..CC10 enabled (param block bytes 30/31 = 0x3c/0x3f),
    scene B = scene 9 (Part +0x11 = 8; scene A stays scene 1)."""
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for f in src.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, dst / f.name)
    for b in range(1, 17):
        p = dst / f"bank{b:02d}.work"
        d = bytearray(p.read_bytes())
        for part in range(NPARTS_FILE):
            o = FILE_PART + part * FILE_PSTRIDE + 9
            d[o + MIDI_SETUP] = 11
            d[o + MIDI_PARAMS + 30], d[o + MIDI_PARAMS + 31] = 0x3c, 0x3f
            d[o + SCENE_B] = 8
        d[-2:] = (sum(d[0x10:-2]) & 0xffff).to_bytes(2, "big")
        p.write_bytes(bytes(d))


def decode(raw, st=0):
    """MIDI bytes -> (messages, running status). The firmware's drainer uses running status."""
    out, i = [], 0
    while i < len(raw):
        if raw[i] & 0x80:
            st = raw[i]; i += 1
        if st >= 0xf8 or st == 0:
            out.append(f"{st:02x}"); continue
        n = 2 if st & 0xf0 in (0x80, 0x90, 0xa0, 0xb0, 0xe0) else 1 if st & 0xf0 in (0xc0, 0xd0) else 0
        out.append(" ".join(f"{b:02x}" for b in (st, *raw[i:i + n]))); i += n
    return out, st


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", action="append", required=True, help="NAME=PATH, repeatable")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--card", default="", help="a staged card (skips staging)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", default="4")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if not EMU.is_file():
        sys.exit("verify_scenes: no port binary (make emu-cf)")
    card = pathlib.Path(a.card) if a.card else out / "card.img"
    if not a.card:
        if not a.project:
            pf = pathlib.Path.home() / ".octabam_project"
            a.project = pf.read_text().strip() if pf.is_file() else ""
        if not a.project:
            sys.exit("verify_scenes: no project (--project, OT_PROJECT or ~/.octabam_project)")
        fixture(pathlib.Path(a.project).expanduser(), out / "project")
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(out / "project"), "OCTABAM",
                            "SCN", "--tree", str(out / "tree"), "--out", str(card)], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_scenes: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    proj = (out / "project" / "project.work") if not a.card else None
    bank = 2
    if proj and proj.is_file():
        import re
        m = re.search(rb"\[STATES\]\r?\nBANK=(\d+)", proj.read_bytes())
        bank = int(m.group(1)) if m else 0
    dumps = dict(DUMPS, parts=(BANK0 + bank * BANK_STRIDE + PART_WINDOW, 4 * PART_STRIDE))
    tags = [t for t in SCENARIOS if not a.only or t in a.only.split(",")]
    for spec in a.image:
        name, path = spec.split("=", 1)
        d = out / name; d.mkdir(exist_ok=True)
        scen = []
        for tag in tags:
            s = Script(); SCENARIOS[tag](s)
            sp = d / f"{tag}.script"; sp.write_text(s.text())
            dump = ";".join(f"{ad:#x},{ln:#x}={d / f'{tag}_{k}.bin'}" for k, (ad, ln) in dumps.items())
            scen += ["--scenario", f"{d / (tag + '.txt')} --live-script {sp} --midi-out {d / (tag + '.midi')} "
                                   f"--mem-dump {dump}"]
        cmd = [EMU, "--image", path, "--card", card, "--set", "OCTABAM", "--project", "SCN", "--load-ms", "90000",
               "--scenario-jobs", a.jobs] + scen
        with open(d / "port.txt", "w") as f:
            f.write(" ".join(map(str, cmd)) + "\n"); f.flush()
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        print(f"== {name} (ot_emu exit {r.returncode})")
        for tag in tags:
            fr = d / f"{tag}.midi.frames"
            print(f"  {tag}:")
            if not fr.is_file():
                print("    (no MIDI OUT record)"); continue
            st, rows = 0, {}
            for line in fr.read_text().split("\n"):
                if line.strip():
                    frame, *hx = line.split()
                    rows.setdefault(int(frame), []).extend(int(h, 16) for h in hx)
            for frame, raw in rows.items():
                msgs, st = decode(bytes(raw), st)
                print(f"    frame {frame:>6}: {' | '.join(msgs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
