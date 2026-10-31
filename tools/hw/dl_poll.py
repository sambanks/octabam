#!/usr/bin/env python3
"""Poll LOAD METER and the demand loader's counters every few milliseconds, to a log, until the unit stops answering or the time is up.

    .venv/bin/python3 tools/hw/dl_poll.py SECONDS [LOGFILE]       (default LOGFILE out/dl_poll.log)

One line per poll: seconds since the start, then
    dsp_seq bad  c0_busy c0_period  c1_busy c1_period  c0_peak_busy c0_peak_period  c1_peak_busy c1_peak_period  tue roe
    loads_armed withdrawals_armed doorbells_sent effects_loaded_bits blocks_holding_code other_ping_calls chunks_sent
(`dsp_seq` is the count of good DSP meter records the ColdFire has taken: it stops when the DSP frame loop stops; the
last seven are DLPUMP's DL_DIAG words, as tools/hw/dl_state.py names them.) A line `ERR <exception>` is a request that failed. About 250 polls a second: one
poll sees about one DSP frame in ten, so a one-frame spike can be missed; the peak columns are the maximum since LOAD METER's
view was last opened (BRAIN > PERFORMANCE resets them).

Used on 28 Oct 2026 to catch the T4 freeze (docs/contributing/FAILURE_MODES.md, "DARK REV picked on T4's FX2 ...").
"""
import pathlib
import struct
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import load_meter as lm  # noqa: E402


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    path = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "out/dl_poll.log")
    path.parent.mkdir(parents=True, exist_ok=True)
    dev = lm.libusb_device()

    def ctrl(w, off, n):
        return bytes(dev.ctrl_transfer(0xC0, 0x57, w, off, n, timeout=500))

    t0, errs = time.time(), 0
    with open(path, "w", buffering=1) as log:
        while time.time() - t0 < seconds:
            try:
                d = lm.decode(lm.read_block(ctrl, 0, lm.STATS_BYTES), lm.read_block(ctrl, 1, lm.DSP_BYTES),
                              bytes(lm.OT_BYTES))["dsp"]
                w = struct.unpack(">16I", lm.read_block(ctrl, 3, 64))
                c0, c1 = d["core0"], d["core1"]
                row = (d["seq"], d["bad"], c0["busy"], c0["period"], c1["busy"], c1["period"], c0["peak_busy"],
                       c0["peak_period"], c1["peak_busy"], c1["peak_period"], d["tue"], d["roe"],
                       w[5], w[6], w[8], w[10], w[11], w[3], w[7])
                log.write(f"{time.time() - t0:8.3f} " + " ".join(str(x) for x in row) + "\n")
                errs = 0
            except Exception as e:  # a stopped frame loop still answers; a vanished unit does not
                errs += 1
                log.write(f"{time.time() - t0:8.3f} ERR {e}\n")
                if errs > 20:
                    break
                time.sleep(0.05)
        log.write("END\n")


if __name__ == "__main__":
    main()
