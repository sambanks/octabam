#!/usr/bin/env python3
"""The first-START stall assay, one trial per power-cycle of the unit.

  .venv/bin/python3 tools/hw/ot_stall.py run LABEL --trials 8 [--no-capture] [--settle 12] [--play 10]
  .venv/bin/python3 tools/hw/ot_stall.py show LABEL
  .venv/bin/python3 tools/hw/ot_stall.py log                # the frame log now (FRAMELOG images only)

A trial: wait for the unit on USB with the DSP count advancing, wait --settle seconds (the project loads),
read the counters, open the USB capture (unless --no-capture), wait 2 s, send START with a 120 BPM clock
beginning at START, poll LOAD METER for --play seconds, STOP, read the counters again. The result
(ok / STALLED / no answer) is spoken; the next trial starts when the unit has left USB and come back.
Each trial runs in its own process (CoreMIDI and CoreAudio hold a stale device list across a re-enumeration).
Results: out/session/stall/LABEL.jsonl, a line a trial.

The frame log is lm_ot on an image built with tools/hw/framelog.patch applied (`git apply`; a test edit to LOAD
METER and USB, never committed applied): the last 22 frame interrupts' entry stamp, duration and USB-shim share,
the last 16 transfer-chain ends, frozen 12 frames after each frame interrupt of 440 us or more. On any other image
the same block is OTOP's costs and the decode is meaningless; --framelog says which.
"""
import argparse
import json
import pathlib
import struct
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import dl_state  # noqa: E402
import load_meter as lm  # noqa: E402
import usb_counters  # noqa: E402

PORT = "Elektron Octatrack DPS-1"
OUT = pathlib.Path("out/session/stall")
UNIT = 64 / 132.0                       # a frame-log unit in us (64 counts of the 132 MHz timer)


def find_dev():
    import usb.core
    return usb.core.find(idVendor=0x1935, idProduct=0x0002, backend=lm.libusb_backend())


def say(text):
    subprocess.Popen(["say", text])


def frame_log(dev):
    """-> {count, frozen, frames: [(entry_us, duration_us, usb_us, chain_end_us or None)] oldest first}. entry_us is
    relative to the oldest frame; chain_end_us is the first state-7 stamp at or after the frame's entry, relative to
    that entry."""
    def ctrl(w, off, n):
        return bytes(dev.ctrl_transfer(0xc0, 0x57, w, off, n, timeout=1000))
    w = struct.unpack(">64I", lm.read_block(ctrl, 2, 256))
    nxt = w[2] if 20 <= w[2] <= 62 else 20
    order = list(range(nxt, 64, 2)) + list(range(20, nxt, 2))
    fr = [(w[i], w[i + 1]) for i in order if w[i]]
    ends = sorted(x for x in w[4:20] if x)
    out = []
    for k, (t, pk) in enumerate(fr):
        nt = fr[k + 1][0] if k + 1 < len(fr) else None
        ce = [e for e in ends if (e - t) & 0xffffffff < 132000 and (nt is None or (nt - e) & 0xffffffff < 0x80000000)]
        out.append((round(((t - fr[0][0]) & 0xffffffff) / 132.0, 1), round((pk >> 16) * UNIT, 1),
                    round((pk & 0x7fff) * UNIT, 1), round((ce[0] - t) / 132.0, 1) if ce else None, bool(pk & 0x8000)))
    return {"count": w[0], "frozen": bool(w[3] >> 31), "frames": out}


def fmt_log(fl):
    return " ".join(f"{t:.0f}/{d:.0f}/{u:.0f}/{'-' if c is None else round(c)}" + ("G" if g else "")
                    for t, d, u, c, g in fl["frames"])


def snapshot(dev, framelog):
    s = {}
    for key, fn in (("out", lambda: usb_counters.read(dev)), ("in", lambda: usb_counters.read(dev, host_in=True)),
                    ("dl", lambda: list(dl_state.read(dev)["words"])), ("meter", lambda: lm.read_fast(dev))):
        try:
            s[key] = fn()
        except Exception as e:          # a block the image does not serve STALLs
            s[key] = f"{type(e).__name__}: {e}"
    if framelog:
        try:
            s["framelog"] = frame_log(dev)
        except Exception as e:
            s["framelog"] = f"{type(e).__name__}: {e}"
    return s


def up(dev):
    try:
        a = lm.read_fast(dev)["dsp"]["seq"]; time.sleep(0.4)
        return lm.read_fast(dev)["dsp"]["seq"] != a
    except Exception:
        return False


def one(a):
    """One trial on a unit that is up. Prints one JSON line."""
    import ot_midi
    dev = find_dev()
    res = {"t": time.strftime("%H:%M:%S"), "capture": not a.no_capture}
    res["before"] = snapshot(dev, a.framelog)
    out = ot_midi.Out(PORT)
    cap = None
    if not a.no_capture:
        import sounddevice as sd
        di = [i for i, d in enumerate(sd.query_devices()) if "Octatrack" in d["name"] and d["max_input_channels"] > 0]
        if not di:
            res["result"] = "no capture device"
            print(json.dumps(res)); return
        nch = sd.query_devices(di[0])["max_input_channels"]
        cap = sd.InputStream(samplerate=44100, channels=nch, dtype="float32", device=di[0], callback=lambda *x: None)
        cap.start()
        res["channels"] = nch
        time.sleep(2.0)
        if not up(dev):                 # the capture alone, before any START
            res["result"] = "STALLED before START"
            res["after"] = snapshot(dev, a.framelog)
            print(json.dumps(res)); return
    stop = threading.Event()

    def clock():
        period = 60.0 / (120 * 24); t0 = time.time(); n = 0
        while not stop.is_set():
            out.send([0xF8]); n += 1
            d = t0 + n * period - time.time()
            if d > 0:
                time.sleep(d)
    out.send([0xFA])
    th = threading.Thread(target=clock); th.start()
    t0 = time.time(); last = None; still = 0; longest = []; verdict = "ok"
    while time.time() - t0 < a.play:
        time.sleep(0.25)
        try:
            r = lm.read_fast(dev)
        except Exception as e:
            res["no_answer_at_s"] = round(time.time() - t0, 2)
            back = None
            for k in range(6):          # does the unit answer again, and is the DSP running then?
                time.sleep(1.0)
                try:
                    d2 = find_dev()
                    if d2 is not None:
                        dev = d2
                        back = up(dev); break
                except Exception:
                    pass
            res["answered_again"] = back
            verdict = f"no answer ({type(e).__name__})" if back is None else \
                ("USB dropout, DSP running" if back else "USB dropout, DSP STALLED")
            break
        longest.append(round(r["cf"]["longest_us"]))
        if a.framelog and "mid" not in res and time.time() - t0 >= 2.0:
            try:
                res["mid"] = {"framelog": frame_log(dev)}
            except Exception as e:
                res["mid"] = {"framelog": f"{type(e).__name__}: {e}"}
        seq = r["dsp"]["seq"]
        still = still + 1 if seq == last else 0
        last = seq
        if still >= 3:                  # 0.75 s without a DSP record
            verdict = "STALLED"; res["stalled_at_s"] = round(time.time() - t0 - 0.75, 2); break
    out.send([0xFC]); stop.set(); th.join()
    res["result"] = verdict
    res["longest_us"] = longest
    if not verdict.startswith("no answer"):
        res["after"] = snapshot(dev, a.framelog)
    if cap is not None:
        try:
            cap.stop(); cap.close()
        except Exception:
            pass
    print(json.dumps(res))


def run(a):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{a.label}.jsonl"
    done = sum(1 for _ in open(path)) if path.exists() else 0
    need_cycle = a.cycle_first
    while done < a.trials:
        if need_cycle:
            print(f"[{done}/{a.trials}] power-cycle the unit", flush=True)
            while find_dev() is not None:
                time.sleep(0.5)
            print("  unit left USB", flush=True)
        while True:
            dev = find_dev()
            if dev is not None and up(dev):
                break
            time.sleep(1.0)
        print(f"  unit up, settling {a.settle:.0f} s", flush=True)
        time.sleep(a.settle)
        cmd = [sys.executable, __file__, "one", "--play", str(a.play)] + (["--no-capture"] if a.no_capture else []) \
            + (["--framelog"] if a.framelog else [])
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=a.play + 60)
        line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else json.dumps({"result": "runner failed", "err": p.stderr[-400:]})
        r = json.loads(line)
        r["trial"] = done + 1; r["label"] = a.label
        with open(path, "a") as f:
            f.write(json.dumps(r) + "\n")
        done += 1
        print(f"  trial {done}: {r['result']}  ({r.get('channels', 0)} ch)", flush=True)
        say(f"trial {done} {'ok' if r['result'] == 'ok' else 'stalled' if r['result'].startswith('STALLED') else 'failed'}. "
            + ("power cycle" if done < a.trials else "set finished"))
        need_cycle = True
    show(a)


def show(a):
    path = OUT / f"{a.label}.jsonl"
    rows = [json.loads(x) for x in open(path)]
    bad = [r for r in rows if r["result"] != "ok"]
    print(f"{a.label}: {len(rows)} trials, {len(bad)} not ok")
    for r in rows:
        b = r.get("before", {}); m = b.get("meter") if isinstance(b.get("meter"), dict) else None
        print(f"  {r['trial']:2d} {r['t']} {r['result']:10s} ch {r.get('channels', 0):2d} "
              f"bad-before {m['dsp']['bad'] if m else '?'} longest max {max(r.get('longest_us') or [0])} us"
              + (f" stalled at {r['stalled_at_s']} s" if "stalled_at_s" in r else ""))
        fl = (r.get("mid") or r.get("after") or {}).get("framelog")
        if isinstance(fl, dict) and "frames" in fl and (a.frames or r["result"] != "ok"):
            print("     frame log, oldest first (entry/duration/usb/chain-end us): " + fmt_log(fl))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "one", "show"):
        p = sub.add_parser(name)
        if name != "one":
            p.add_argument("label")
        p.add_argument("--trials", type=int, default=8)
        p.add_argument("--no-capture", action="store_true")
        p.add_argument("--framelog", action="store_true", help="the image carries the FRAMELOG edit")
        p.add_argument("--settle", type=float, default=12.0)
        p.add_argument("--play", type=float, default=10.0)
        p.add_argument("--cycle-first", action="store_true", help="wait for a power-cycle before the first trial")
        p.add_argument("--frames", action="store_true", help="show: print every trial's frame log")
    sub.add_parser("log")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a)
    elif a.cmd == "one":
        one(a)
    elif a.cmd == "show":
        show(a)
    else:
        fl = frame_log(find_dev())
        print(fl["count"], "frames;", "frozen;" if fl["frozen"] else "", fmt_log(fl))


if __name__ == "__main__":
    main()
