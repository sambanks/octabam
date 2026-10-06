#!/usr/bin/env python3
"""Read USB AUDIO's counters from a unit over USB (the vendor request
0xc0/0x55 the module answers on EP0; modules/usb-audio-out/usbaudio.s).

  tools/hw/usb_counters.py            # once
  tools/hw/usb_counters.py --watch 1  # every second, deltas beside the values

Needs libusb and pyusb. On this Mac Homebrew is the Intel build under
/usr/local and the .venv python is arm64, so the x86_64 python takes the
package: `brew install libusb`, then
`/usr/local/bin/python3 -m pip install --user --break-system-packages pyusb`
and run this with `/usr/local/bin/python3` (25 Sep 2026).
A device-recipient control request needs no interface claim, so the
audio and MIDI drivers macOS attaches stay attached. The unit must be
running an image with a USB AUDIO OUT module; on any other image the request STALLs
(reported here, not an error).

Meaning (from usbaudio.s): produced/consumed are frame counts (the ring is
1,024 frames; fill = produced - consumed); underruns = polls the device
could not fill; overruns = the host stopped draining and the producer
lapped the ring; bankdup = blocks where the read-back ping-pong bank did
NOT alternate (the producer read a bank twice, or skipped one) -- the count
that decides whether the clicks are the producer's; minfill/maxfill = the
ring's low and high water at packet builds since the host's first poll of
this open; anchor = the frames the consumer skipped at that first poll (the
producer's output between SET_INTERFACE and the host starting to poll).

--in reads USB AUDIO IN's counters (0xc0/0x56; modules/usb-audio-in/
usbaudio_in.s) instead: produced/consumed = frames into and out of its
ring; pkts = OUT packets retired; lastn = frames in the last one; lastfill
= the ring's fill at the last DSP frame; underruns = blocks the ring could
not supply; overruns = ring laps; reprimes = EP3 OUT self-heal primes;
bad = err + partial: err = completions with a dTD error bit (halted, data
buffer, transaction), partial = lengths that were not whole frames;
frames/seconds = the two state-7 visits (equal while running);
minfill/maxfill = the ring's low and high water while consuming since the
stream came up (the cushion IN_TARGET has to cover).
"""
import argparse
import struct
import sys
import time

# usbaudio_in.s in_counters (NCOUNT 15), the same order usb_probe.py reads
IN_NAMES = ("produced", "consumed", "pkts", "lastn", "lastfill", "underruns", "overruns",
            "reprimes", "bad", "frames", "seconds", "minfill", "maxfill", "err", "partial")
NAMES = ("consumed", "acc", "overruns", "underruns", "lastn", "lastfill", "lastbank",
         "bankdup", "lastsamp", "srcjump", "reprimes", "minfill", "maxfill", "anchor", "produced")


def read(dev, host_in=False):
    req, names = (0x56, IN_NAMES) if host_in else (0x55, NAMES)
    n = 4 * len(names)
    raw = bytes(dev.ctrl_transfer(0xc0, req, 0, 0, n, timeout=1000))
    if len(raw) != n:
        raise RuntimeError(f"{len(raw)} bytes back, expected {n}")
    return dict(zip(names, struct.unpack(f">{len(names)}I" if host_in else f">{len(names)}i", raw)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--watch", type=float, default=0, help="seconds between reads; 0 = once")
    ap.add_argument("--in", dest="host_in", action="store_true",
                    help="USB AUDIO IN's counters (vendor request 0x56) instead of USB AUDIO's")
    a = ap.parse_args()
    try:
        import usb.core
    except ImportError:
        sys.exit("pyusb is not installed: brew install libusb && .venv/bin/pip install pyusb")
    # pyusb's default search misses a Homebrew libusb on this Mac (Intel
    # brew under /usr/local, 25 Sep 2026); name the library outright.
    import glob
    import usb.backend.libusb1
    libs = (glob.glob("/usr/local/opt/libusb/lib/libusb-1.0.dylib") + glob.glob("/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib")
            + glob.glob("/usr/local/lib/libusb-1.0*.dylib") + glob.glob("/usr/local/Cellar/libusb/*/lib/libusb-1.0*.dylib")
            + glob.glob("/opt/homebrew/lib/libusb-1.0*.dylib") + glob.glob("/opt/homebrew/Cellar/libusb/*/lib/libusb-1.0*.dylib"))
    backend = usb.backend.libusb1.get_backend(find_library=lambda _: libs[0]) if libs else None
    dev = usb.core.find(idVendor=0x1935, idProduct=0x0002, backend=backend)
    if dev is None:
        sys.exit("no Octatrack on USB (1935:0002)")
    try:
        last = read(dev, a.host_in)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"the request failed: {e} (a STALL means the image carries no USB AUDIO{' IN' if a.host_in else ''})")
    print(" ".join(f"{k}={v}" for k, v in last.items()), flush=True)
    while a.watch > 0:
        time.sleep(a.watch)
        now = read(dev, a.host_in)
        print(" ".join(f"{k}={now[k]}{'(+%d)' % (now[k] - last[k]) if now[k] != last[k] else ''}" for k in now), flush=True)
        last = now


if __name__ == "__main__":
    main()
