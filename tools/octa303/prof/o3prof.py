#!/usr/bin/env python3
"""OCTA303's stopwatch on the unit, read over USB (ACIDV91, 11 Nov 2026).

    python3 tools/octa303/prof/o3prof.py                 # a line a second, until ctrl-C
    python3 tools/octa303/prof/o3prof.py --for 30        # 30 s, then a summary
    python3 tools/octa303/prof/o3prof.py --log run.jsonl # every reading also to a file

What the image measures (modules/octa303/octa303.s, O3_PROF; read through the USB module's vendor
request 0xc0/0x57, block 4): for each track that ran OCTA303's sample loop, on DMA timer 3 (132 MHz,
the timer LOAD METER uses):
  CALL  the whole render call of the frame's last call: entry to exit, the stock renderer's call included;
  PRE   the call's entry to the sample loop (dEVILish's knobs, GATE 303, the stock renderer);
  LOOP  the sample loop, with the 16-sample control step inside it;
  MAX   the longest CALL since power-up (the image never resets it).
Shown in microseconds per frame (a frame is 362.8 us) and as a share of the ColdFire's time.  Beside it,
LOAD METER's own figures: the frame interrupt's share (CFIRE) and each DSP core's busy share.

A frame where a note starts mid-frame has two calls ([0, n) and [n, 16)); both are counted, so the per-frame
figures divide by the samples rendered / 16, not by the calls.  What it cannot see: the time between the calls.
The timer reads themselves cost a few cycles each (3 reads a call).  The unit copies the block a byte at a time
while the frame interrupt may add to it, so now and then one reading is torn: a second whose figures are out of
range is skipped and counted.
Needs pyusb and a libusb (tools/hw/load_meter.py's note: `pip install pyusb libusb-package`).
Written by Claude (Anthropic).
"""
import argparse, json, pathlib, struct, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/hw"))
CF_HZ, FRAME_US = 132e6, 1e6 * 16 / 44100


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--for", dest="secs", type=float, default=0, help="stop after this many seconds and summarise")
    ap.add_argument("--every", type=float, default=1.0)
    ap.add_argument("--log", default="", help="append every reading here (one JSON line each)")
    a = ap.parse_args()
    try:
        import load_meter as lm
        dev = lm.libusb_device()
    except ImportError as e:
        sys.exit(f"o3prof: {e}\n  install once:  python3 -m pip install pyusb libusb-package")

    def ctrl(w, off, n):
        return bytes(dev.ctrl_transfer(0xc0, 0x57, w, off, n, timeout=1000))

    def reading():
        try:
            prof = lm.read_block(ctrl, 4, 256)
        except Exception as e:
            sys.exit(f"o3prof: block 4 not answered ({e}): this image has no OCTA303 stopwatch (ACIDV91 has it)")
        base = lm.decode(lm.read_block(ctrl, 0, lm.STATS_BYTES), lm.read_block(ctrl, 1, lm.DSP_BYTES), bytes(lm.OT_BYTES))
        rows = [struct.unpack(">8I", prof[32 * t:32 * t + 32]) for t in range(8)]
        return time.time(), base, rows

    log = open(a.log, "a") if a.log else None
    prev = reading()
    t0 = prev[0]
    tot = {}
    torn = 0
    print("o3prof: a line a second; ctrl-C to stop" + (f", logging to {a.log}" if log else ""))
    try:
        while True:
            time.sleep(a.every)
            cur = reading()
            dt = cur[0] - prev[0]
            cf, dsp = cur[1]["cf"], cur[1]["dsp"]
            parts = [f"CFIRE {100 * (cf['share'] or 0):5.1f}%",
                     f"DSP0 {100 * (lm.ratio(dsp['core0']) or 0):4.1f}%", f"DSP1 {100 * (lm.ratio(dsp['core1']) or 0):4.1f}%"]
            rec = {"t": round(cur[0] - t0, 2), "cfire": cf["share"], "dsp0": lm.ratio(dsp["core0"]),
                   "dsp1": lm.ratio(dsp["core1"]), "tracks": {}}
            for t in range(8):
                p, c = prev[2][t], cur[2][t]
                calls = (c[0] - p[0]) & 0xFFFFFFFF
                if not calls:
                    continue
                d = [((c[i] - p[i]) & 0xFFFFFFFF) / CF_HZ * 1e6 for i in (1, 3, 4)]
                n = ((c[6] - p[6]) & 0xFFFFFFFF) / 16.0          # frames' worth of samples
                if d[0] > dt * 1e6 * 1.05 or not n:
                    torn += 1                                     # a torn reading (see the docstring)
                    continue
                call, pre, loop = (x / n for x in d)
                mx = c[2] / CF_HZ * 1e6
                share = d[0] / (dt * 1e6)
                parts.append(f"T{t + 1} {call:5.1f}us ({100 * share:4.1f}%) pre {pre:4.1f} loop {loop:5.1f} max {mx:5.1f}")
                rec["tracks"][t + 1] = {"calls": calls, "frames": n, "call_us": call, "pre_us": pre, "loop_us": loop, "share": share, "max_us": mx}
                s = tot.setdefault(t + 1, [0, 0.0, 0.0, 0.0, 0.0])
                s[0] += n; s[1] += d[0]; s[2] += d[1]; s[3] += d[2]; s[4] += dt
            print(" | ".join(parts), flush=True)
            if log:
                log.write(json.dumps(rec) + "\n"); log.flush()
            prev = cur
            if a.secs and cur[0] - t0 >= a.secs:
                break
    except KeyboardInterrupt:
        pass
    print("\nsummary (per frame, mean over the run):")
    for t, (n, call, pre, loop, secs) in sorted(tot.items()):
        print(f"  T{t}: {call / n:5.1f} us a frame = {100 * call / n / FRAME_US:4.1f}% of a frame "
              f"(pre {pre / n:4.1f}, loop {loop / n:5.1f}); {n:.0f} frames in {secs:.0f} s")
    print("  (the rows' maxima are since power-up: the image never resets them)" + (f"; {torn} torn readings skipped" if torn else ""))


if __name__ == "__main__":
    main()
