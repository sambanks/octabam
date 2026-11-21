#!/usr/bin/env python3
"""ot_fuzz.py run on an image without LOAD METER, with REMOTE's frame-interrupt trace as the health check.

    python3 tools/hw/ot_fuzz_remote.py run SEQ.json LABEL [--no-silence-check] ...

An image with REMOTE and no LOAD METER answers `0xc0/0x57` with a STALL, so ot_fuzz runs on the MIDI destination and the audio
alone and sees no DSP stall. The frame interrupt is driven by the DSP; REMOTE's RMT_TRACE counts them (modules/remote/README.md).
The check here is that count advancing about 2,756 a second, the rule LOAD METER's `healthy` applies to the DSP's own count.
"""
import sys
import time

import load_meter
import ot_card
import ot_events as ev


def _count(u):
    import struct
    base = struct.unpack(">I", ev.read_bytes(u.ctrl, 16, 4))[0]
    return struct.unpack(">I", ev.peek(u.peek1, base, 4))[0]


def healthy(dev, wait=0.4):
    u = ot_card.Unit()
    a = _count(u)
    time.sleep(wait)
    rate = (_count(u) - a) / wait
    if rate < 1500:
        return False, f"the frame interrupt count (REMOTE's trace) advances {rate:.0f} a second (about 2,756 when running)"
    return True, ""


def read_fast(dev):
    return {"dsp": {"bad": 0, "seq": 0}, "cf": {"longest_us": 0, "mean_us": 0.0, "share": 0.0}}


if __name__ == "__main__":
    load_meter.healthy = healthy
    load_meter.read_fast = read_fast
    import ot_fuzz
    sys.argv[0] = "ot_fuzz.py"
    sys.exit(ot_fuzz.main())
