#!/usr/bin/env python3
"""When does the DSP frame count stop? Program-change / START / STOP cycles with the count polled at 20 Hz.

    python3 tools/hw/ot_dspwatch.py [--cycles 10] [--programs 0,1] [--play 12] [--tail 3] [--poll-hz 20] [--out FILE]

Each cycle is `ot_matrix.py run`'s transport sequence: STOP, 0.3 s, program change, 0.8 s, START with a host clock,
--play seconds, STOP, --tail seconds. The DSP's record count (`dsp.seq`) advances about 2,800 a second whenever the
frame loop runs, playing or not; three polls without an advance is a stall. On a stall the tool stops and prints the
last events with their times against the stall. The load_meter reads are the only traffic besides MIDI.
"""
import argparse
import json
import pathlib
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import load_meter as lm  # noqa: E402
import ot_fuzz  # noqa: E402
import ot_midi  # noqa: E402

PORT = "Elektron Octatrack DPS-1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=10)
    ap.add_argument("--programs", default="0,1")
    ap.add_argument("--play", type=float, default=12.0)
    ap.add_argument("--tail", type=float, default=3.0)
    ap.add_argument("--poll-hz", type=float, default=20.0)
    ap.add_argument("--pc-channel", type=int, default=1)
    ap.add_argument("--audio", action="store_true", help="hold the unit's USB audio capture open, as ot_matrix.py run does")
    ap.add_argument("--continuous-clock", action="store_true", help="one clock thread for the whole run, as ot_matrix.py run has")
    ap.add_argument("--no-pc", action="store_true", help="send no program change: STOP and START only")
    ap.add_argument("--out", default="out/hw/suite/dspwatch.json")
    a = ap.parse_args()
    programs = [int(x) for x in a.programs.split(",")]
    dev = lm.libusb_device()
    ok, why = lm.healthy(dev)
    if not ok:
        sys.exit(f"the unit is not running normally: {why}. Power-cycle it.")
    out = ot_midi.Out(PORT)
    t0 = time.monotonic()
    events, polls, stall = [], [], {}
    stop_evt = threading.Event()

    def poller():
        last, same, period = None, 0, 1.0 / a.poll_hz
        nxt = time.monotonic()
        while not stop_evt.is_set():
            try:
                s = lm.read_fast(dev)["dsp"]["seq"]
            except Exception as e:                      # noqa: BLE001
                stall.update(t=time.monotonic() - t0, why=f"read failed: {e}")
                stop_evt.set()
                return
            t = time.monotonic() - t0
            polls.append((round(t, 3), s))
            same = same + 1 if s == last else 0
            last = s
            if same >= 3:
                stall.update(t=round(t - 3 * period, 3), why="DSP record count did not advance for 3 polls", seq=s)
                stop_evt.set()
                return
            nxt += period
            time.sleep(max(0.0, nxt - time.monotonic()))

    stream = None
    if a.audio:
        import sounddevice as sd
        import usb_transport_probe as U
        adev, nch = U.find_input("Octatrack")
        stream = sd.InputStream(device=adev, channels=nch, samplerate=44100, dtype="float32", callback=lambda *x: None)
        stream.start()
        events.append((round(time.monotonic() - t0, 3), f"audio capture open, {nch} channels"))
    th = threading.Thread(target=poller, daemon=True)
    th.start()

    def ev(name):
        events.append((round(time.monotonic() - t0, 3), name))

    clock = None
    cont = None
    if a.continuous_clock:
        cont = ot_fuzz.ClockGen(out, 120.0)
        cont.start()
        ev("continuous clock started")
    try:
        for c in range(a.cycles):
            pr = programs[c % len(programs)]
            if clock:
                clock.stop_evt.set(); clock = None
            out.send([0xFC]); ev(f"c{c} STOP"); time.sleep(0.3)
            if not a.no_pc:
                out.send([0xC0 | (a.pc_channel - 1), pr]); ev(f"c{c} PC {pr}")
            time.sleep(0.8)
            if cont is None:
                clock = ot_fuzz.ClockGen(out, 120.0)
            out.send([0xFA]); ev(f"c{c} START")
            if clock:
                clock.start()
            t = time.monotonic()
            while time.monotonic() - t < a.play and not stop_evt.is_set():
                time.sleep(0.05)
            if stop_evt.is_set():
                break
            if clock:
                clock.stop_evt.set(); clock = None
            out.send([0xFC]); ev(f"c{c} STOP (end of play)")
            t = time.monotonic()
            while time.monotonic() - t < a.tail and not stop_evt.is_set():
                time.sleep(0.05)
            if stop_evt.is_set():
                break
    finally:
        if clock:
            clock.stop_evt.set()
        if cont:
            cont.stop_evt.set()
        stop_evt.set()
        th.join(timeout=2)
        if stream:
            stream.stop(); stream.close()
    p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"events": events, "polls": polls, "stall": stall}))
    if stall:
        print(f"STALL at {stall['t']:.3f} s: {stall['why']}")
        for t, n in events[-5:]:
            print(f"  {t:8.3f}  {n}   ({stall['t'] - t:+.3f} s to the stall)")
        return 1
    rate = (polls[-1][1] - polls[0][1]) / (polls[-1][0] - polls[0][0])
    print(f"no stall in {a.cycles} cycles, {len(polls)} polls, {rate:.0f} records a second")
    return 0


if __name__ == "__main__":
    sys.exit(main())
