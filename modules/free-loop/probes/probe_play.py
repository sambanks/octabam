#!/usr/bin/env python3
"""FREE LOOP phase 2, unknowns 1 and 3: start / stop a MAX take with the sequencer stopped,
and find where the take's length lands.

    probe_stop.py ROOT OUT

A fresh project (the image's own), T1 FLEX on R1, T1's recorder INAB AB, RLEN MAX, TRIG ONE2.
TRACK 1 + REC AB at 2000 ms (start), again at 4000 ms (ONE2: stop). Dumps the 0x8000xxxx RAM
window and the recorder control region at quit; a scan lists every long in 80000..96000.
"""
import pathlib, re, shutil, struct, subprocess, sys

ROOT = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tools/hw"))
import ot_project as op  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
REC_AB, TR1 = 0x2B, 0x10
MAILBOX, LIMIT = 0x46C7E9FA, 0x46C7FE24
FLEX, MAX, ONE2, AB = 1, 64, 1, 1


def press(ms):
    return [f"{ms} key {TR1:#x} down", f"{ms + 40} key {REC_AB:#x} down",
            f"{ms + 100} key {REC_AB:#x} up", f"{ms + 140} key {TR1:#x} up"]


def edit(data):
    for p in range(op.NPARTS_ALL):
        part = op.PART_BASE + p * op.PART_STRIDE
        data[part + op.MTYPE_OFF + 0] = FLEX
        data[part + 0x2d3 + 0 * 5 + op.SLOT_KIND["flex"]] = 0x80          # R1
        rec = part + op.REC_SETUP_OFF
        data[rec + op.REC_FIELDS.index("INAB")] = AB
        data[rec + op.REC_FIELDS.index("RLEN")] = MAX
        data[rec + op.REC_FIELDS.index("TRIG")] = ONE2
    data[op.trac_off(0, 0) + 0x00 + 7] |= 1                              # A1: a trig on step 1 of T1


fresh = OUT / "fresh"
if not (fresh / "image/NOPROJ/project.work").is_file():
    r = subprocess.run([str(PY), str(ROOT / "tools/hw/ot_fresh.py"), "--image", str(ROOT / "out/mainos_bus.bin"),
                        "--out", str(fresh)], cwd=ROOT, capture_output=True, text=True)
    assert not r.returncode, r.stdout + r.stderr
proj = OUT / "proj"
shutil.rmtree(proj, ignore_errors=True)
shutil.copytree(fresh / "image/NOPROJ", proj)
op._bank_write(proj, 1, edit, guard=False)
card = OUT / "card.img"
r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "FREE",
                    "--tree", str(OUT / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
assert not r.returncode, r.stdout + r.stderr


def run(tag, script_lines, quit_ms):
    script = OUT / f"{tag}.script"
    script.write_text("\n".join(script_lines + [f"{quit_ms} quit"]) + "\n")
    dumps = {"ram": (0x80000000, 0x8000), "ctl": (0x46C7E000, 0x16000), "rec": (0x46C922C4, 44 * 136), "slot": (0x100D38F0, 0x448)}
    args = [str(EMU), "--image", str(ROOT / "out/mainos_bus.bin"), "--card", str(card),
            "--set", "OCTABAM", "--project", "FREE", "--load-ms", "90000", "--mkii", "--dsp",
            "--watch-mem", f"{MAILBOX:#x},32;{LIMIT:#x},32;0x80004a3c,4;0x80004a00,8;0x46c802c8,4;0x100d38f0,0x448",
            "--mem-dump", ";".join(f"{a:#x},{n}={OUT / f'{tag}_{k}.bin'}" for k, (a, n) in dumps.items()),
            "--live-script", str(script), "--audio-in", "tones"]
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=900)
    (OUT / f"{tag}.txt").write_text(r.stdout + r.stderr)
    print(f"== {tag}: exit {r.returncode}")
    for line in (r.stdout + r.stderr).splitlines():
        if re.search(r"\[0x(46c7e9fa|46c7fe24|80004a3c|80004a0[0-7]|46c802c8|100d3[89a-f]|100d4[0-3])\] <- ", line):
            print(line)
    return {k: (a, (OUT / f"{tag}_{k}.bin").read_bytes()) for k, (a, _) in dumps.items()}


def scan(d, lo, hi):
    hits = {}
    for k, (base, data) in d.items():
        for o in range(0, len(data) - 3, 2):
            v = struct.unpack(">I", data[o:o + 4])[0]
            if lo <= v <= hi:
                hits[base + o] = v
    return hits


PLAY = 0x28
play = run("play", press(2000) + press(4000) + [f"5000 key {PLAY:#x} down", f"5060 key {PLAY:#x} up"], 9000)
for a in sorted(scan(play, 40000, 200000)):
    v = scan(play, 40000, 200000)[a]
    if 87000 < v < 90000: print(f"  {a:#010x} = {v}")
