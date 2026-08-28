#!/usr/bin/env python3
"""Gain-match a whole project bank by bank, driven over MIDI.

Built 24 Aug 2026 for the 8-song level cleanup. Rig: OT on Midihub port "A",
Rytm on its own USB port (clock master; PC chained to the OT). Capture is
tools/rec.swift compiled on demand -> out/hw/gain/rec (the ffmpeg/avfoundation
path drops samples in chunks -- do not go back to it; measured 24 Aug).

    python3 tools/gain_pass.py pc N                  # pattern N (0-127); bank A=0-15, B=16-31...
    python3 tools/gain_pass.py mix NAME [--secs 16]  # full-mix capture + report
    python3 tools/gain_pass.py solo-map NAME [--machine ot|rytm] [--secs 8]
                                                     # solo each track in turn, capture, report
    python3 tools/gain_pass.py set ot 3 --level 100 --vol 64
    python3 tools/gain_pass.py set rytm 2 --level 90
    python3 tools/gain_pass.py analyse FILE.wav
    python3 tools/gain_pass.py start | stop          # Rytm transport

CC map (manual-confirmed, docs/MIDI.md "Remote CC reference"):
  OT   per-track ch 1-8 : level CC46, AMP VOL CC25, mute CC49, solo CC50
  Rytm per-track ch 1-12: LEVEL CC95, amp volume CC7, mute CC94, solo CC93
Program change goes to the Rytm (chained to the OT). Solo'd captures aim for
about -18 dBFS RMS; the full mix should peak under -6 dBFS with no clip runs.
"""
import argparse, array, math, os, pathlib, subprocess, sys, time, wave

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "out/hw/gain"
REC = OUT / "rec"
OT_PORT, AR_PORT = "A", "Elektron Analog Rytm MKII"
M = {
    "ot":   dict(port=OT_PORT, level=46, vol=25, mute=49, solo=50, tracks=8),
    "rytm": dict(port=AR_PORT, level=95, vol=7,  mute=94, solo=93, tracks=12),
}

def send(port, *args, tries=3):
    for i in range(tries):
        r = subprocess.run(["python3", str(REPO / "tools/ot_midi.py"), "-p", port]
                           + [str(a) for a in args], capture_output=True)
        if r.returncode == 0:
            return
        time.sleep(0.2)
    sys.exit(f"MIDI send failed: {port} {args}: {r.stderr.decode().strip()}")

def ensure_rec():
    src = REPO / "tools/rec.swift"
    OUT.mkdir(parents=True, exist_ok=True)
    if not REC.exists() or REC.stat().st_mtime < src.stat().st_mtime:
        subprocess.run(["swiftc", "-O", str(src), "-o", str(REC)], check=True)

def record(name, secs):
    ensure_rec()
    path = OUT / f"{name}.wav"
    r = subprocess.run([str(REC), str(secs), str(path)], capture_output=True, text=True, check=True)
    return path

# --- analysis (pure python, no numpy on this machine) -----------------------

def biquad(kind, fc, sr, q=0.7071):
    w = 2 * math.pi * fc / sr
    alpha = math.sin(w) / (2 * q); c = math.cos(w)
    if kind == "lp":
        b0, b1, b2 = (1 - c) / 2, 1 - c, (1 - c) / 2
    else:
        b0, b1, b2 = (1 + c) / 2, -(1 + c), (1 + c) / 2
    a0, a1, a2 = 1 + alpha, -2 * c, 1 - alpha
    return (b0/a0, b1/a0, b2/a0, a1/a0, a2/a0)

def run_biquad(x, co):
    b0, b1, b2, a1, a2 = co
    y = [0.0] * len(x); x1 = x2 = y1 = y2 = 0.0
    for i, v in enumerate(x):
        o = b0*v + b1*x1 + b2*x2 - a1*y1 - a2*y2
        x2, x1, y2, y1 = x1, v, y1, o
        y[i] = o
    return y

def rms_db(x):
    return 20*math.log10(math.sqrt(sum(v*v for v in x)/max(len(x),1)) + 1e-9)

def analyse(path, label=""):
    w = wave.open(str(path)); n = w.getnchannels(); sr = w.getframerate()
    a = array.array('i'); a.frombytes(w.readframes(w.getnframes()))
    full = 2**31
    ch1 = [a[i*n]/full for i in range(len(a)//n)]
    ch2 = [a[i*n+1]/full for i in range(len(a)//n)] if n > 1 else ch1
    mono = [(l+r)/2 for l, r in zip(ch1, ch2)]
    pk = max(max(abs(v) for v in ch1), max(abs(v) for v in ch2))
    # clip runs on either channel
    runs = pinned = cur = 0
    for l, r in zip(ch1, ch2):
        if abs(l) >= 0.985 or abs(r) >= 0.985:
            cur += 1; pinned += 1
        else:
            if cur >= 2: runs += 1
            cur = 0
    if cur >= 2: runs += 1
    bands = {}
    lo = run_biquad(mono, biquad("lp", 120, sr))
    hi = run_biquad(mono, biquad("hp", 2500, sr))
    mid_lo = run_biquad(run_biquad(mono, biquad("hp", 120, sr)), biquad("lp", 600, sr))
    mid_hi = run_biquad(run_biquad(mono, biquad("hp", 600, sr)), biquad("lp", 2500, sr))
    bands = {"<120": rms_db(lo), "120-600": rms_db(mid_lo),
             "600-2.5k": rms_db(mid_hi), ">2.5k": rms_db(hi)}
    res = dict(label=label, rms=rms_db(mono), peak=20*math.log10(pk + 1e-9),
               runs=runs, pinned=pinned, bands=bands,
               bal=rms_db(ch1) - rms_db(ch2))
    bstr = "  ".join(f"{k} {v:6.1f}" for k, v in bands.items())
    print(f"{label:12s} rms {res['rms']:6.1f}  peak {res['peak']:6.1f} dBFS"
          f"  L-R {res['bal']:+4.1f}  clip-runs {runs}\n{'':12s} {bstr}")
    return res

# --- actions ----------------------------------------------------------------

def do_solo_map(name, machine, secs):
    """Each track: solo -> restart transport (so every capture starts at bar 1
    and covers the same musical material -- free-running windows land on
    different song sections and gave 20 dB run-to-run drift) -> record -> stop."""
    m = M[machine]
    results = []
    try:
        for trk in range(1, m["tracks"] + 1):
            send(m["port"], "cc", trk, m["solo"], 127)
            time.sleep(0.2)
            send(AR_PORT, "start")
            time.sleep(0.3)
            path = record(f"{name}_{machine}_t{trk}", secs)
            send(AR_PORT, "stop")
            send(m["port"], "cc", trk, m["solo"], 0)
            results.append(analyse(path, f"{machine} T{trk}"))
    finally:
        for trk in range(1, m["tracks"] + 1):
            send(m["port"], "cc", trk, m["solo"], 0)
        send(AR_PORT, "stop")
    quiet = [r["label"] for r in results if r["rms"] < -45]
    if quiet:
        print(f"\nno content (rms < -45): {', '.join(quiet)}")
    return results

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pc"); p.add_argument("n", type=int); p.add_argument("--ch", type=int, default=1)
    p = sub.add_parser("mix"); p.add_argument("name"); p.add_argument("--secs", type=float, default=16)
    p = sub.add_parser("solo-map"); p.add_argument("name")
    p.add_argument("--machine", choices=["ot", "rytm"], default="ot")
    p.add_argument("--secs", type=float, default=8)
    p = sub.add_parser("set"); p.add_argument("machine", choices=["ot", "rytm"])
    p.add_argument("track", type=int)
    p.add_argument("--level", type=int); p.add_argument("--vol", type=int)
    p = sub.add_parser("analyse"); p.add_argument("file")
    sub.add_parser("start"); sub.add_parser("stop")
    a = ap.parse_args()

    if a.cmd == "pc":
        # both machines take PC directly (OT PROG CH RECEIVE is on; the Rytm
        # does NOT reliably forward per-pattern changes to the OT -- measured
        # 24 Aug: bank jumps forwarded, within-bank pattern steps not)
        status = 0xC0 | (a.ch - 1)
        send(AR_PORT, "raw", f"{status:02X}", f"{a.n:02X}")
        send(OT_PORT, "raw", f"{status:02X}", f"{a.n:02X}")
    elif a.cmd == "mix":
        send(AR_PORT, "start"); time.sleep(1.0)
        try: path = record(a.name, a.secs)
        finally: send(AR_PORT, "stop")
        analyse(path, a.name)
    elif a.cmd == "solo-map":
        do_solo_map(a.name, a.machine, a.secs)
    elif a.cmd == "set":
        m = M[a.machine]
        if a.level is not None: send(m["port"], "cc", a.track, m["level"], a.level)
        if a.vol is not None: send(m["port"], "cc", a.track, m["vol"], a.vol)
    elif a.cmd == "analyse":
        analyse(a.file, pathlib.Path(a.file).stem)
    elif a.cmd in ("start", "stop"):
        send(AR_PORT, a.cmd)

if __name__ == "__main__":
    main()
