#!/usr/bin/env python3
"""PROBE (not a gate): what RTRG / RTIM do to the sound, measured from the port's audio.

Retrigs are made by the stock sample renderer inside one voice, so no firmware
state shows them. This renders T1 alone (one trig, a decaying noise burst as
its sample) with RTRG,RTIM locked on that trig, runs the sequencer with the DSP
for --frames frames, reads core 0's MAIN L/R from --audio-out and prints the
onsets it finds (ms from the first one).

    OT_PROJECT=<dir> python3 tools/verify/probe_usbmidi_retrig_audio.py 0,0 3,64 3,16
"""
import argparse, importlib.util, math, os, pathlib, random, re, shutil, struct, subprocess, sys, tempfile, wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import ot_project as otp  # noqa: E402
import ot_bank as ob  # noqa: E402

spec = importlib.util.spec_from_file_location("verify_set", ROOT / "tools/verify/verify_set.py")
vs = importlib.util.module_from_spec(spec); spec.loader.exec_module(vs)
EMU, IMAGE = ROOT / "out/emu/ot_emu", ROOT / "out/mainos_bus.bin"
(ROOT / "out").mkdir(exist_ok=True)
OUT = pathlib.Path(tempfile.mkdtemp(prefix="retrig_audio_", dir=ROOT / "out"))   # per process: TRAPS trap-tmp-race


def burst(path, secs=0.3):
    path.parent.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(b"".join(struct.pack("<h", int(20000 * math.exp(-i / 2500) * rnd.uniform(-1, 1)))
                               for i in range(int(44100 * secs))) + bytes(2 * 44100))


def onsets(samples, rate=44100):
    blk = rate // 1000
    env = [max(abs(x) for x in samples[i:i + blk]) for i in range(0, len(samples) - blk, blk)]
    peak = max(env) or 1
    out, low = [], True
    for i, e in enumerate(env):
        if low and e > 0.35 * peak:
            out.append(i); low = False
        elif e < 0.08 * peak:
            low = True
    return [o - out[0] for o in out] if out else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variants", nargs="+", help="RTRG,RTIM pairs")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--frames", type=int, default=5000)
    a = ap.parse_args()
    pdir0 = pathlib.Path(a.project).expanduser()
    bank = 1
    for v in a.variants:
        rtrg, rtim = (int(x) for x in v.split(","))
        d = OUT / f"v_{rtrg}_{rtim}"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        src = d / "src"
        shutil.copytree(pdir0, src)

        def mut(data):
            first = 4                           # step 5: a trig at step 1 can fall before the first frame
            for t in range(8):
                ob.set_mask(data, 0, t, (1 << first) if t == 0 else 0, 0)
            base = ob.trac(0, 0) + ob.LOCKS + first * ob.LOCK_LEN
            data[base + 4], data[base + 5] = rtrg, rtim
        otp._bank_write(src, bank, mut, guard=False)
        pat_part, _ = otp.bank_info(src, bank)
        pn = pat_part[0] + 1 if 1 <= pat_part[0] + 1 <= 4 else 1
        part = vs.part_of(src, bank, pn)
        for (kind, slot), rel in vs.sample_paths(src).items():
            if (kind == "FLEX" and slot - 1 in part["flex"]) or (kind == "STATIC" and slot - 1 in part["static"]):
                burst((src / rel).resolve())
        card = d / "card.img"
        audio, mb = vs.stage(src, part, "OCTABAM", "RIG", d / "tree", 64, bank, card)
        cmd = [str(EMU), "--image", str(IMAGE), "--card", str(card), "--set", "OCTABAM", "--project", "RIG",
               "--sequencer", "--internal-clock", "--frames", str(a.frames), "--load-ms", "90000",
               "--dsp", "--main-level", "64", "--audio-out", str(d / "audio")]
        with open(d / "port.log", "w") as log:
            subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
        txt = (d / "port.log").read_text()
        m = re.search(r"core0\.wav, .*?transport start at frame (\d+)", txt)
        wp = pathlib.Path(str(d / "audio") + "_core0.wav")
        if not m or not wp.is_file():
            print(f"RTRG {rtrg} RTIM {rtim}: no audio ({txt[-300:]!r})"); continue
        with wave.open(str(wp), "rb") as f:
            ch = f.getnchannels(); f.setpos(int(m.group(1)))
            raw = f.readframes(f.getnframes() - int(m.group(1)))
        s = [int.from_bytes(raw[i:i + 3], "little", signed=True) for i in range(2 * 3, len(raw), ch * 3)]
        o = onsets(s)
        print(f"RTRG {rtrg:3d} RTIM {rtim:3d}: {len(o)} onset(s) at ms {o[:16]}  (peak {max(map(abs, s)) if s else 0})")


if __name__ == "__main__":
    main()
