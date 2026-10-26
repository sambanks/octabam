#!/usr/bin/env python3
"""Read the demand loader's ColdFire counters from a unit over USB (the vendor request 0xc0/0x57, block 3, which the
USB module answers from DLPUMP's `DL_DIAG`; modules/dlpump/pump.s).

  tools/hw/dl_state.py                 # one reading
  tools/hw/dl_state.py --watch 1       # a reading a second

Needs pyusb and a libusb (see load_meter.py). The image must carry USB and DLPUMP; on any other image the request STALLs.
The words are the pump's own counts since power-up; none of it has been compared with an independent measurement.
"""
import argparse
import struct
import sys
import time

import load_meter as lm

NAMES = ("pump calls (frame interrupts)", "calls with ping 0", "calls with ping 1", "calls with another ping",
         "idle passes on a delivering frame", "loads armed", "withdrawals armed", "chunks sent",
         "doorbells sent", "repeats armed", "effects loaded (bits)", "blocks holding code (bits)", "(spare)")


def read(dev):
    def ctrl(w, off, n):
        return bytes(dev.ctrl_transfer(0xC0, 0x57, w, off, n, timeout=1000))
    raw = lm.read_block(ctrl, 3, 64)
    w = struct.unpack(">16I", raw)
    return {"words": w, "live": raw[48:64]}


def show(r):
    w = r["words"]
    for name, v in zip(NAMES, w):
        if not name.startswith("(spare)"):
            print(f"  {name:36s} {v}" + (f"  (0b{v:04b})" if name.startswith("effects") else ""))
    live = r["live"]
    print(f"  live FX1 ids T1..T8                  {' '.join(f'{b:02x}' for b in live[:8])}")
    print(f"  live FX2 ids T1..T8                  {' '.join(f'{b:02x}' for b in live[8:16])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--watch", type=float, default=0, help="a reading every N seconds")
    a = ap.parse_args()
    dev = lm.libusb_device()
    while True:
        try:
            show(read(dev))
        except Exception as e:  # a STALL is the request refused: the image has no DLPUMP, or no USB module
            sys.exit(f"dl_state: {e}")
        if not a.watch:
            return
        print()
        time.sleep(a.watch)


if __name__ == "__main__":
    main()
