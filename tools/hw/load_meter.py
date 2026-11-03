#!/usr/bin/env python3
"""Read LOAD METER's figures from a unit over USB (the vendor request
0xc0/0x57 the USB module answers on EP0; modules/usb/usbaudio.s).

  tools/hw/load_meter.py                       # one reading
  tools/hw/load_meter.py --watch 1             # a reading a second
  tools/hw/load_meter.py --for 20 --json out.json   # 20 s of polling, summarised

Needs pyusb and a libusb: `pip install pyusb libusb-package` (the bundled library loads in an arm64
python), or a Homebrew libusb of the same architecture as the python. The
image must carry LOAD METER and USB; on any other image the request STALLs
(reported, not an error). wValue low names the block: 0 lm_stats, 1 lm_dsp,
2 lm_ot (modules/load-meter/meter.s), all big-endian longs; wIndex low is the byte
offset to read from, and a reply is never a multiple of 64 bytes long (a block can
come in two pieces; `read_block`).

Units. lm_stats is on DMA timer 3 (132 MHz): `window` counts a 0.5 s window,
`sum` the frame interrupt's time in it, `count` its runs, `longest` the
longest run. lm_dsp and lm_ot are on the DSP's timer 0 (CLK/2): a frame is
36,256 counts nominal. lm_dsp is the last good frame's {busy, period} per
core and the peak since lm_dsp_reset (set by BRAIN's view opening; a host
cannot clear it, so a peak is the highest since the view was last opened or
the unit booted). lm_ot is per effect slot {last, sum, count, max}: slots
0-7 are payload A's (tracks 5-8: FX1, FX2 of each position), 8-15 payload
B's (tracks 1-4); the slot is sampled about every 6 ms, so a run's mean is
the delta of `sum` over the delta of `count`.

Everything printed is a reading of the unit's timers. None of it has been
compared with an independent measurement on a unit.
"""
import argparse
import glob
import json
import struct
import sys
import time

CF_HZ = 132e6            # DMA timer 3
FRAME_COUNTS = 36256     # timer 0, one 44.1 kHz / 16 frame, nominal
STATS_BYTES, DSP_BYTES, OT_BYTES = 20, 48, 256
FRAME_US = 362.8


def decode(stats, dsp, ot):
    """The three blocks (bytes) -> a dict of numbers."""
    seq, window, sum_, count, longest = struct.unpack(">5I", stats)
    d = struct.unpack(">12I", dsp)
    slots = [dict(zip(("last", "sum", "count", "max"), struct.unpack(">4I", ot[16 * i:16 * i + 16])))
             for i in range(16)]
    return {
        "cf": {"seq": seq, "window": window, "sum": sum_, "count": count, "longest": longest,
               "share": sum_ / window if window else None,
               "mean_us": 1e6 * sum_ / count / CF_HZ if count else None,
               "longest_us": 1e6 * longest / CF_HZ,
               "irq_per_s": count * CF_HZ / window if window else None},
        "dsp": {"seq": d[0], "bad": d[1],
                "core0": {"busy": d[2], "period": d[3], "peak_busy": d[6], "peak_period": d[7]},
                "core1": {"busy": d[4], "period": d[5], "peak_busy": d[8], "peak_period": d[9]},
                "tue": d[10], "roe": d[11]},
        "slots": slots,
    }


def ratio(core, key="busy", pkey="period"):
    return core[key] / core[pkey] if core[pkey] else None


def slot_name(i):
    core, k = ("A", i) if i < 8 else ("B", i - 8)
    return f"{core}{k // 2 + 1}.{'FX1' if k % 2 == 0 else 'FX2'}"


def libusb_backend():
    """pyusb's libusb 1.x backend: libusb-package's bundled library when installed (arm64 and x86_64 wheels),
    else a Homebrew libusb by path. On a Mac with the Intel Homebrew under /usr/local an arm64 python cannot
    load that one (docstring of usb_counters.py)."""
    import usb.backend.libusb1
    try:
        import libusb_package
        be = libusb_package.get_libusb1_backend()
        if be is not None:
            return be
    except ImportError:
        pass
    libs = (glob.glob("/usr/local/opt/libusb/lib/libusb-1.0.dylib") + glob.glob("/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib")
            + glob.glob("/usr/local/lib/libusb-1.0*.dylib") + glob.glob("/usr/local/Cellar/libusb/*/lib/libusb-1.0*.dylib")
            + glob.glob("/opt/homebrew/lib/libusb-1.0*.dylib") + glob.glob("/opt/homebrew/Cellar/libusb/*/lib/libusb-1.0*.dylib"))
    return usb.backend.libusb1.get_backend(find_library=lambda _: libs[0]) if libs else None


def libusb_device():
    import usb.core
    dev = usb.core.find(idVendor=0x1935, idProduct=0x0002, backend=libusb_backend())
    if dev is None:
        sys.exit("no Octatrack on USB (1935:0002), or no libusb backend (pip install libusb-package)")
    return dev


def read_block(ctrl, w, size):
    """Block `w` of `size` bytes through ctrl(w, offset, wLength) -> bytes. The unit never sends a reply whose
    length is a multiple of 64 (the next control request would return 0 bytes), so a block can come in
    pieces; wIndex is the byte offset to resume from."""
    out = b""
    while len(out) < size:
        raw = ctrl(w, len(out), size - len(out))
        if not raw:
            raise RuntimeError(f"block {w}: 0 bytes back at offset {len(out)}")
        out += raw
    return out[:size]


def read(dev):
    """One reading: lm_stats, lm_dsp and lm_ot over vendor request 0xc0/0x57."""
    def ctrl(w, off, n):
        return bytes(dev.ctrl_transfer(0xc0, 0x57, w, off, n, timeout=1000))
    return decode(read_block(ctrl, 0, STATS_BYTES), read_block(ctrl, 1, DSP_BYTES), read_block(ctrl, 2, OT_BYTES))


def read_fast(dev):
    """lm_stats and lm_dsp only (two requests, no per-slot costs): for polling several times a second."""
    def ctrl(w, off, n):
        return bytes(dev.ctrl_transfer(0xc0, 0x57, w, off, n, timeout=1000))
    d = decode(read_block(ctrl, 0, STATS_BYTES), read_block(ctrl, 1, DSP_BYTES), bytes(OT_BYTES))
    d.pop("slots")
    return d


def healthy(dev, wait=0.4):
    """-> (ok, why): the DSP's record count advances about 2,800 a second and the frame interrupt keeps its rate.
    A unit left stuck by an overload, or found frozen with the count at 0x7FFFFF (24 Oct 2026), fails this and needs a
    power-cycle."""
    a = read_fast(dev)
    time.sleep(wait)
    return judge(a, read_fast(dev), wait)


def judge(a, b, dt):
    """healthy()'s rules on two read_fast() readings taken dt seconds apart -> (ok, why)."""
    adv = (b["dsp"]["seq"] - a["dsp"]["seq"]) / dt
    irq = b["cf"]["irq_per_s"] or 0.0
    if adv < 1500:
        return False, f"the DSP's frame count advances {adv:.0f} a second (about 2,800 when running)"
    if irq < 0.9 * 2756:
        return False, f"the frame interrupt runs {irq:.0f} a second (nominal 2,756)"
    return True, ""


def line(r):
    cf, dsp = r["cf"], r["dsp"]
    c0, c1 = ratio(dsp["core0"]), ratio(dsp["core1"])
    return (f"CF {100 * cf['share']:5.1f}% mean {cf['mean_us']:6.1f} us longest {cf['longest_us']:6.1f} us "
            f"{cf['irq_per_s']:6.0f}/s | DSP0 {100 * c0:5.1f}% DSP1 {100 * c1:5.1f}% "
            f"(peaks {100 * ratio(dsp['core0'], 'peak_busy', 'peak_period'):5.1f}% "
            f"{100 * ratio(dsp['core1'], 'peak_busy', 'peak_period'):5.1f}%) bad {dsp['bad']}")


def summarise(readings):
    """Fresh windows only (a new lm_stats seq): the ColdFire share's mean and worst, the
    DSP ratios' mean and worst, and each slot's mean over the whole run."""
    fresh, last = [], None
    for r in readings:
        if r["cf"]["seq"] != last:
            fresh.append(r)
            last = r["cf"]["seq"]
    out = {"readings": len(readings), "windows": len(fresh)}
    if not fresh:
        return out
    shares = [r["cf"]["share"] for r in fresh]
    out["cf_share_mean"], out["cf_share_max"] = sum(shares) / len(shares), max(shares)
    out["cf_longest_us"] = max(r["cf"]["longest_us"] for r in fresh)
    for k in ("core0", "core1"):
        v = [ratio(r["dsp"][k]) for r in readings if r["dsp"][k]["period"]]
        out[f"dsp_{k}_mean"], out[f"dsp_{k}_max"] = sum(v) / len(v), max(v)
        out[f"dsp_{k}_peak"] = max(ratio(r["dsp"][k], "peak_busy", "peak_period") for r in readings)
    a, b = readings[0]["slots"], readings[-1]["slots"]
    out["slots"] = {slot_name(i): {"mean_counts": (b[i]["sum"] - a[i]["sum"]) / (b[i]["count"] - a[i]["count"]),
                                   "max_counts": b[i]["max"], "samples": b[i]["count"] - a[i]["count"]}
                    for i in range(16) if b[i]["count"] > a[i]["count"]}
    out["irq_per_s_median"] = sorted(r["cf"]["irq_per_s"] for r in fresh if r["cf"]["irq_per_s"])[len(fresh) // 2]
    out["bad_records"] = readings[-1]["dsp"]["bad"] - readings[0]["dsp"]["bad"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--watch", type=float, default=0, help="seconds between readings, until interrupted")
    ap.add_argument("--for", dest="secs", type=float, default=0, help="poll for this many seconds, then summarise")
    ap.add_argument("--interval", type=float, default=0.25, help="seconds between polls with --for")
    ap.add_argument("--json", help="with --for: write the summary here")
    ap.add_argument("--jsonl", action="store_true", help="one JSON reading per line with its time, until killed "
                    "(tools/hw/ot_matrix.py reads this through the x86_64 python)")
    a = ap.parse_args()
    try:
        import usb.core  # noqa: F401
    except ImportError:
        sys.exit("pyusb is not installed: brew install libusb && pip install pyusb")
    dev = libusb_device()
    try:
        r = read(dev)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"the request failed: {e} (a STALL means the image carries no LOAD METER or no USB)")
    if a.jsonl:
        while True:
            print(json.dumps({"t": time.time(), **read(dev)}), flush=True)
            time.sleep(a.interval)
    if a.secs:
        readings, t0 = [r], time.monotonic()
        while time.monotonic() - t0 < a.secs:
            time.sleep(a.interval)
            readings.append(read(dev))
        s = summarise(readings)
        print(f"{s['readings']} readings, {s['windows']} published windows")
        if s["windows"]:
            print(f"CF share mean {100 * s['cf_share_mean']:.1f}% max {100 * s['cf_share_max']:.1f}% "
                  f"longest run {s['cf_longest_us']:.1f} us ({100 * s['cf_longest_us'] / FRAME_US:.0f}% of a frame)")
            for k in ("core0", "core1"):
                print(f"DSP {k[-1]} busy/period mean {100 * s[f'dsp_{k}_mean']:.1f}% max {100 * s[f'dsp_{k}_max']:.1f}% "
                      f"peak since reset {100 * s[f'dsp_{k}_peak']:.1f}%")
            for n, v in s["slots"].items():
                print(f"  {n:7s} mean {v['mean_counts']:8.0f} counts ({100 * v['mean_counts'] / FRAME_COUNTS:5.2f}% of a frame) "
                      f"max {v['max_counts']:6d}  n={v['samples']}")
            print(f"bad records in the run: {s['bad_records']}")
        if a.json:
            with open(a.json, "w") as f:
                json.dump(s, f, indent=1)
        return
    print(line(r))
    while a.watch > 0:
        time.sleep(a.watch)
        print(line(read(dev)), flush=True)


if __name__ == "__main__":
    main()
