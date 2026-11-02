#!/usr/bin/env python3
"""A project of ColdFire-cost layouts, stepped and measured like ot_matrix's.

    python3 tools/hw/ot_cfmatrix.py plan
    python3 tools/hw/ot_cfmatrix.py proj SRC DEST [REMIX=octabam]    # SRC: a fresh unit-created project (ot_matrix --clean)
    python3 tools/hw/ot_cfmatrix.py run DEST LABEL [--only 0-21]    # LOAD METER per layout, over USB MIDI; no audio capture
    python3 tools/hw/ot_matrix.py run DEST LABEL                     # the same layouts with the audio detectors (needs the USB audio device)

Each layout is one pattern of bank A-H playing its own part, selected by program change as in ot_matrix.
The axes are ColdFire work that scales with something the project holds:

  OCTA-303 voices   n tracks on a FLEX slot whose sample is named TB303 (saw) or TB303D (saw + pedal),
                    a trig on every step; the other tracks play HITS on step 1 only
  trig density      all eight tracks on HITS, a trig on step 1 / on every step / on every step with a PTCH lock
  VARISPEED         TSTR = VARI (4) on n tracks, HITS on every step
  stations on FX1   the 303 layouts with a station on FX1 of every track

Not here: SCALE QUANTIZER, which acts on key and knob events and not on a stored pattern; the crossfader and
scene locks; an armed recorder. USB audio on or off is the image's setting (BRAIN), not the project's: run the
project once for each.
"""
import argparse
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ot_matrix as om  # noqa: E402
import ot_project as P  # noqa: E402

SLOT_HITS, SLOT_303, SLOT_303D = 1, 2, 3
STEPS = 64
SETUP_TSTR = 0x1e3 + 6 + 4          # Part-relative: track t's PLAYBACK SETUP is 0x1e3 + 6 + 30 * t; LOOP SLIC LEN RATE TSTR
VARI = 4                            # TSTR's fifth position (measured: a unit-set T1 went 0 -> 4 at this byte, 2 Nov 2026)
SIG_AT = 0x45                       # Part-relative: track t's 'T', 'B', 1 at SIG_AT + 30 * t (octa303.s o3_sig: Part' + 0x3c + 30 * t)
PLAYBACK_AT = 0x39                  # PLAYBACK page 1 bytes, 30 * t; a signed 303's defaults are 64 64 64 64 64 0
SETUP_AT = 0x1e9                    # SETUP bytes, 30 * t; a signed 303's defaults are WAVE GATE FINE SLID DRIV ACCV = 0 0 64 0 0 64
LOCK_FLAT = 0                       # PTCH, PLAYBACK page 1 slot A (STEP_LOCKS.md: track + 0x59 + step * 32 + flat)


class Lay:
    def __init__(self, name, n303=0, carrier=SLOT_303, density="sparse", locks=False, fx1=None, vari=(),
                 signed=False, steps303=None, stepsrest=None):
        self.name, self.n303, self.carrier = name, n303, carrier
        self.vari = tuple(vari)             # 0-based tracks with TSTR = VARI
        self.signed = signed                # the first n303 tracks are OCTA-303 machines (signature), not a TB303 sample name
        self.steps303 = steps303            # None: as density; else the 1-based steps the 303 tracks trig on
        self.stepsrest = stepsrest          # None: as density; else the steps the other tracks trig on (empty list: none)
        self.density, self.locks, self.fx1 = density, locks, fx1


def layouts():
    out = [Lay("BASE: HITS on step 1, all tracks")]
    for n in (1, 2, 3, 4, 6, 8):
        out.append(Lay(f"{n} x OCTA-303 saw, every step", n303=n))
    out.append(Lay("4 x OCTA-303 TB303D, every step", n303=4, carrier=SLOT_303D))
    out.append(Lay("8 x OCTA-303 TB303D, every step", n303=8, carrier=SLOT_303D))
    out.append(Lay("HITS every step, all tracks", density="dense"))
    out.append(Lay("HITS every step + PTCH lock every step", density="dense", locks=True))
    for st in ("SPECTRUM", "CHARACTER", "MODULATION"):
        out.append(Lay(f"4 x OCTA-303 saw + {st} FX1", n303=4, fx1=st))
    out.append(Lay(f"8 x OCTA-303 saw + SPECTRUM FX1", n303=8, fx1="SPECTRUM"))
    out.append(Lay("4 x OCTA-303 saw, every step + PTCH lock every step", n303=4, locks=True))
    out.append(Lay("8 x OCTA-303 saw, every step + PTCH lock every step", n303=8, locks=True))
    out.append(Lay("1 x VARI (T5), HITS every step", density="dense", vari=(4,)))
    out.append(Lay("4 x VARI (T5-8), HITS every step", density="dense", vari=(4, 5, 6, 7)))
    out.append(Lay("8 x VARI, HITS every step", density="dense", vari=range(8)))
    out.append(Lay("8 x VARI, HITS every step + PTCH lock every step", density="dense", locks=True, vari=range(8)))
    out.append(Lay("4 x OCTA-303 (T1-4) + 4 x VARI (T5-8)", n303=4, density="dense", vari=(4, 5, 6, 7)))
    return out


def layouts_diag():
    """Signed OCTA-303 machines only: the idle cost per machine, and the step-1 / simultaneous-start cases."""
    every = list(range(1, STEPS + 1))
    out = [Lay("nothing plays: no trigs on any track", stepsrest=[], steps303=[])]
    for n in (1, 2, 3, 4, 5, 6):
        out.append(Lay(f"{n} x OCTA-303, no trigs (idle cost)", n303=n, signed=True, steps303=[], stepsrest=[]))
    out.append(Lay("4 x OCTA-303, every step but 1; T5-8 empty", n303=4, signed=True, steps303=every[1:], stepsrest=[]))
    out.append(Lay("4 x OCTA-303, every step incl. 1; T5-8 empty", n303=4, signed=True, steps303=every, stepsrest=[]))
    out.append(Lay("4 x OCTA-303, every step incl. 1; T5-8 HITS on step 1", n303=4, signed=True, steps303=every, stepsrest=[1]))
    out.append(Lay("2 x OCTA-303, every step incl. 1; rest empty", n303=2, signed=True, steps303=every, stepsrest=[]))
    out.append(Lay("4 x OCTA-303, every 4th step from 1; rest empty", n303=4, signed=True, steps303=every[::4], stepsrest=[]))
    out.append(Lay("4 x OCTA-303, every 4th step from 2; rest empty", n303=4, signed=True, steps303=every[1::4], stepsrest=[]))
    out.append(Lay("4 x HITS on step 1 only (T5-8); no 303", stepsrest=[1], steps303=[]))
    out.append(Lay("6 x OCTA-303, every step incl. 1; rest empty", n303=6, signed=True, steps303=every, stepsrest=[]))
    return out


def chunk_of(lays, remix_name):
    import ot_ladder as L
    from remix import registry
    mods = registry.modules()
    out = []
    for lay in lays:
        spec = None
        if lay.fx1:
            m = mods[lay.fx1]
            spec = (lay.fx1, dict(getattr(m, "dear", None) or {}))
        lo = {t: (spec, None) for t in range(1, 9)}
        out.append((lay.name, "cf", lo))
    return out


def write_samples(dest):
    """HITS stays slot 1; TB303 and TB303D are the same audio under the carrier names (the 303 voice replaces it)."""
    import ot_stimuli as S
    q, _ = S.render("hits")
    names = ["hits", "TB303", "TB303D"]
    frames = {n: len(q) for n in names}
    for n in names:
        S.write_wav(dest / f"{n}.wav", q)
    om._stim_text(dest, names, frames)
    om._stim_markers(dest, names, frames)


def stamp_layout(data, i, lay):
    """One bank file: layout i's pattern (its trigs and locks) and its part (machines and slots), live and saved copy."""
    bank, j = divmod(i, 4)
    assigned = {}
    for t in range(8):
        is303 = t < lay.n303
        # a signed machine needs no carrier sample (SETUP's WAVE is the carrier), and a TB303* name would make it a
        # second way into the voice that the signature does not control
        assigned[t] = (SLOT_HITS if lay.signed else lay.carrier) if is303 else SLOT_HITS
    for p in (j, j + 4):
        off = P.PART_BASE + p * P.PART_STRIDE
        om.stim_part(data, off, [(t, s) for t, s in assigned.items()])
        for t in lay.vari:
            data[off + SETUP_TSTR + 30 * t] = VARI
        if lay.signed:
            for t in range(lay.n303):
                data[off + SIG_AT + 30 * t:off + SIG_AT + 30 * t + 3] = bytes([0x54, 0x42, 0x01])
                data[off + PLAYBACK_AT + 30 * t:off + PLAYBACK_AT + 30 * t + 6] = bytes([64, 64, 64, 64, 64, 0])
                data[off + SETUP_AT + 30 * t:off + SETUP_AT + 30 * t + 6] = bytes([0, 0, 64, 0, 0, 64])
    om.stim_pattern(data, j, [(t, s) for t, s in assigned.items()])
    for t in range(8):
        trac = P.trac_off(j, t)
        every = lay.density == "dense" or t < lay.n303 or t in lay.vari
        steps = lay.steps303 if t < lay.n303 else lay.stepsrest
        if steps is not None:
            data[trac:trac + 8] = bytes(8)
            for st in steps:                                     # step 1 is the mask's last byte, bit 0
                data[trac + 7 - (st - 1) // 8] |= 1 << ((st - 1) % 8)
            every = bool(steps) and len(steps) == STEPS
        elif every:
            data[trac:trac + 8] = bytes([0xff]) * 8              # the trig mask: all 64 steps
        if lay.locks and every:
            for k in range(STEPS):
                data[trac + 0x59 + k * 32 + LOCK_FLAT] = 64 + 5 * (k % 12)


def pick(a):
    return layouts_diag() if getattr(a, "set", "cost") == "diag" else layouts()


def cmd_plan(a):
    for i, lay in enumerate(pick(a)):
        print(f"  {i:3d}  {lay.name}")


def cmd_proj(a):
    lays = pick(a)
    if a.only_layout is not None:           # every slot holds this layout: the port plays A01 whatever the program change
        lays = [lays[a.only_layout]] * om.PER_PROJECT
    assert len(lays) <= om.PER_PROJECT, len(lays)
    dest = pathlib.Path(a.dest).expanduser()
    om.make_project(a.src, dest, a.remix, chunk_of(lays, a.remix), stimuli=["hits"], clean=True)
    write_samples(dest)
    for i, lay in enumerate(lays):
        bank, _pat, _prog = om._program(i)

        def mut(data, i=i, lay=lay):
            stamp_layout(data, i, lay)

        P._bank_write(dest, bank, mut, guard=False)
    P.write_stored(dest)
    print(f"{dest}: {len(lays)} layouts (slot 0 first); the rest repeat BASE")


SETTLE_S, MEASURE_S = 4.0, 6.0      # after MIDI START: the voices and loads settle, then the readings (--settle, --measure)


def cmd_run(a):
    """Each layout: stop, program change, START, SETTLE_S, then MEASURE_S of LOAD METER readings. -> cf_report.json."""
    import json
    import threading
    import time
    import numpy as np
    import load_meter
    import ot_ladder as L
    plan = json.loads((pathlib.Path(a.project) / "OCTABAM_MATRIX.json").read_text())
    entries = plan["layouts"]
    only = om.parse_only(a.only, len(entries)) if a.only else range(len(entries))
    out_dir = pathlib.Path("out/hw/matrix") / a.label
    out_dir.mkdir(parents=True, exist_ok=True)
    usb = load_meter.libusb_device()
    clock = L.Clock(plan.get("bpm") or 120.0, a.midi)
    pc_ch = plan.get("pc_channel") or 1
    rows, stop = [], threading.Event()

    def poll():
        while not stop.is_set():
            try:
                r = load_meter.read_fast(usb)
                r["t"] = time.time()
                rows.append(r)
            except Exception:  # noqa: BLE001
                time.sleep(0.05)

    threading.Thread(target=poll, daemon=True).start()
    results = []
    print(f"{'layout':52s} {'CF mean':>8s} {'CF max':>7s} {'longest':>8s} {'DSP0 mean/max':>14s} {'DSP1 mean/max':>14s} {'bad':>4s}")
    try:
        for i in only:
            e = entries[i]
            ok, why = load_meter.healthy(usb)
            if not ok:
                print(f"The unit is not running normally: {why}. Stopping; power-cycle it.")
                results.append({"slot": i, "name": e["name"], "flags": ["UNHEALTHY"], "why": why})
                break
            clock.stop(); time.sleep(0.5)
            clock.pc(pc_ch, e["program"]); time.sleep(1.0)
            t0 = time.time()
            clock.start()
            time.sleep(a.settle + a.measure)
            clock.stop()
            rr = [r for r in rows if t0 + a.settle <= r["t"] <= t0 + a.settle + a.measure]
            if len(rr) < 20:
                results.append({"slot": i, "name": e["name"], "flags": ["NO READINGS"]})
                print(f"{i:2d} {e['name'][:48]:48s} no readings"); break
            sh = np.array([r["cf"]["share"] or 0.0 for r in rr])
            lo = np.array([r["cf"]["longest_us"] for r in rr])
            c0 = np.array([load_meter.ratio(r["dsp"]["core0"]) or 0.0 for r in rr])
            c1 = np.array([load_meter.ratio(r["dsp"]["core1"]) or 0.0 for r in rr])
            bad = int(rr[-1]["dsp"]["bad"] - rr[0]["dsp"]["bad"])
            row = {"slot": i, "name": e["name"], "readings": len(rr), "cf_share_mean": float(sh.mean()), "cf_share_max": float(sh.max()),
                   "cf_longest_us_max": float(lo.max()), "dsp0_mean": float(c0.mean()), "dsp0_max": float(c0.max()),
                   "dsp1_mean": float(c1.mean()), "dsp1_max": float(c1.max()), "bad": bad, "flags": []}
            if row["cf_longest_us_max"] > 362.8:
                row["flags"].append("CF_OVERRUN")
            if bad > 0:
                row["flags"].append("BAD")
            if a.series:                      # every reading: seconds after START, share, mean run, longest run, DSP counter
                row["series"] = [[round(r["t"] - t0, 2), round(r["cf"]["share"] or 0.0, 4), round(r["cf"]["mean_us"], 1),
                                  round(r["cf"]["longest_us"], 1), r["dsp"]["seq"]] for r in rr]
            results.append(row)
            print(f"{i:2d} {e['name'][:48]:48s} {100 * row['cf_share_mean']:7.1f}% {100 * row['cf_share_max']:6.1f}% {row['cf_longest_us_max']:7.0f}u "
                  f"{100 * row['dsp0_mean']:5.1f}/{100 * row['dsp0_max']:5.1f}% {100 * row['dsp1_mean']:5.1f}/{100 * row['dsp1_max']:5.1f}% {bad:4d} "
                  + " ".join(row["flags"]), flush=True)
    finally:
        stop.set(); clock.stop(); clock.close()
        (out_dir / "cf_report.json").write_text(json.dumps({"project": str(a.project), "results": results}, indent=1))
    print(f"{len(results)} layouts; {out_dir / 'cf_report.json'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--set", default="cost", choices=("cost", "diag"))
    p = sub.add_parser("proj")
    p.add_argument("src")
    p.add_argument("dest")
    p.add_argument("remix", nargs="?", default="octabam")
    p.add_argument("--only-layout", type=int, default=None, help="fill all 32 slots with this layout (for the port)")
    p.add_argument("--set", default="cost", choices=("cost", "diag"))
    r = sub.add_parser("run")
    r.add_argument("project")
    r.add_argument("label")
    r.add_argument("--only", default="")
    r.add_argument("--midi", default="Elektron Octatrack DPS-1")
    r.add_argument("--settle", type=float, default=SETTLE_S, help="seconds after START before the readings")
    r.add_argument("--measure", type=float, default=MEASURE_S, help="seconds of readings")
    r.add_argument("--series", action="store_true", help="keep every reading in cf_report.json")
    a = ap.parse_args()
    {"plan": cmd_plan, "proj": cmd_proj, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    main()
