#!/usr/bin/env python3
"""DRUMMER phase 2, unknown 2: what the step builder 0x4009d1e8 leaves for T1, step by step.

    .venv/bin/python3 modules/drummer/probe_steps.py --sample DIR/NAME.wav --project <empty project>

Same project as probe_slices.py (the user's sample, its slices, T1 FLEX SLIC on), with pattern A01 T1:

  step 1  trig                      step 5  trig, micro-timing -12
  step 2  nothing                   step 6  nothing
  step 3  trigless trig (mask 2)    step 7  trig, micro-timing +23
  step 4  trig, micro-timing +12    step 8  trig, condition 50 % (raw 4 ❓)

and every write to T1's words 0x46c7a810, 0x46c7a830, 0x46c7a14c, 0x46c77bfa and to its voice's
slice byte (a voice start) is logged with the emulated time, so each step's values and the instant
the voice starts can be read side by side.
"""
import argparse, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import probe_slices as ps  # noqa: E402

WATCH = {0x46c7a810: "a810", 0x46c7a830: "a830(µt)", 0x46c7a14c: "a14c", 0x46c77bfa: "7bfa", 0x800049f8: "VOICE", 0x800064d0: "STEP", 0x80000825: "LANE VOL", 0x80000a6e: "DSP VOL", 0x80001567: "PEND VOL", 0x80001538: "RESTMASK"}


def mut_pattern(data):
    off = ps.otp.trac_off(0, 0)
    data[off:off + 64] = bytes(64)
    data[off + 0x59:off + 0x59 + 64 * 32] = bytes([0xff]) * (64 * 32)
    def trig(step, which=0):
        data[off + 8 * which + 7 - step // 8] |= 1 << (step % 8)
    def word(step, value):
        # the FILE holds the word one byte before RAM's +0x89a (PARAM_PAGES.md 5g)
        data[off + 0x899 + 2 * step:off + 0x89b + 2 * step] = value.to_bytes(2, "big")
    import os
    if os.environ.get("DR_SPARSE"):
        # one trig every 4 steps: 0, +12, -12, +23 micro-timing; nothing between
        for st, mt in ((0, 0), (4, 12), (8, -12), (12, 23)):
            trig(st)
            word(st, (mt & 0x3f) << 7)
        return
    for s in (0, 3, 4, 6, 7):
        trig(s)
    trig(2, which=2)
    word(3, (12 & 0x3f) << 7)
    word(4, (-12 & 0x3f) << 7)
    word(6, (23 & 0x3f) << 7)
    word(7, 4)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--image", default=str(ps.ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--tempo", type=int, default=120)
    ap.add_argument("--frames", type=int, default=3000)
    a = ap.parse_args()
    out = ps.ROOT / "out/drummer/steps"
    out.mkdir(parents=True, exist_ok=True)
    wav = pathlib.Path(a.sample).expanduser().resolve()
    slices, count = ps.read_ot(wav.with_suffix(".ot"))
    import wave
    with wave.open(str(wav)) as w:
        frames = w.getnframes()
    proj = out / "project"
    ps.build_project(pathlib.Path(a.project), proj, frames, slices, count, a.tempo)
    ps.otp._bank_write(proj, 1, mut_pattern, guard=False)
    card = out / "card.img"
    r = subprocess.run([str(ps.PY), str(ps.ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "RIG",
                        "--tree", str(out / "tree"), "--out", str(card), "--audio", f"{wav}:{ps.SAMPLE_REL}"],
                       cwd=ps.ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"stage_card failed:\n{(r.stdout + r.stderr)[-1500:]}")
    watch = ";".join(f"{k:#x},1" if k in (0x800049f8, 0x800064d0, 0x80000825, 0x80001567) else f"{k:#x},2" if k == 0x80000a6e else f"{k:#x},4" for k in WATCH)
    cmd = [str(ps.EMU), "--image", a.image, "--card", str(card), "--set", "OCTABAM", "--project", "RIG",
           "--sequencer", "--internal-clock", "--frames", str(a.frames), "--load-ms", "90000",
           "--main-level", "64", "--watch-mem", watch,
           "--mem-dump", f"0x400e21e0,0x91a={out / 'trac_ram.bin'}"]
    log = out / "port.txt"
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ps.ROOT, stdout=f, stderr=subprocess.STDOUT)
    text = log.read_text()
    print(f"port exit {r.returncode}; log {log}")
    m0 = re.search(r"transport start at frame (\d+)", text)
    for m in re.finditer(r"\[\s*([\d.]+)\] \[(0x[0-9a-f]+)\] <- (0x[0-9a-f]+|0) \((\d)\) at pc (0x[0-9a-f]+)", text):
        t, addr, val, n, pc = float(m.group(1)), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4)), m.group(5)
        name = WATCH.get(addr)
        if name is None:
            continue
        if n == 4 and val & 0x80000000:
            val -= 1 << 32
        print(f"  {t:12.1f}  {name:9s} = {val:9d}   pc {pc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
