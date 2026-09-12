#!/usr/bin/env python3
"""Pressure-test a remix: every layout a user can select, priced and rendered.

    python3 tools/harness/pressure.py price  [--remix bamsep26]        # A1: the static envelope
    python3 tools/harness/pressure.py render [--remix bamsep26] [--top N] [--sample N] [--seconds S]
                                                                      # A2: the worst under the meter + memory police

PRICE enumerates, per core, every combination of FX1 x FX2 on the four
tracks the core serves -- FX1 from {none} + the remix's FX1 rows of ours,
FX2 from SEND, this core's server (at most one per core: the design rule),
any of ours that is on the FX2 chooser, and stock rows (0: stock code runs
on the ColdFire or inside stock's own share, which the counter does not
price) -- and sums the STATIC per-sample cost of each pick, each module at
its worst mode loop (`tools/build/cycle_count.py`: a floor, words in the
sample loop, no contention; ~270 LOW on the reverb, CHIP.md s2). The wall
is USABLE + the FILTER credit. Out comes the distribution: how many layouts
are over, the cheapest over and the dearest under, and the station count
that fits beside each server. `out/pressure/<remix>_layouts.tsv` has every
layout. The wall is a CLIFF and only the burn sweep measures it (CHIP.md
s2 "the burn knob"); this says which layouts to sweep.

RENDER takes the dearest N layouts per core (and a random sample of the
rest) and runs them through rig_render on the real image with every mode
and knob at its dearest setting, all stems live, `dsp_host -guard -dirty`
(a write outside the instance's window, garbage in every buffer) and the
meter. A local red -- a clobber, a HANG, a `!!` -- is a defect. A local
green says nothing about the cliff.
"""
import argparse, itertools, json, os, pathlib, random, re, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry             # noqa: E402
from remix.schema import BusRole       # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "out/pressure"
TRACKS_PER_CORE = 4


def price_modules(remix):
    """{key: (stem, cycles, server, on_fx1, on_fx2)} for the remix's DSP modules."""
    import cycle_count as cc
    mods = {}
    stock_fx1 = set()
    from remix import stock as _stock
    _all = registry.modules()
    stock_fx1 = {e.key for e in _stock.MODULES if e.menu.fx2_id in _stock.fx1_ids()}
    fx1_keys = set(remix.fx1) if remix.fx1 else set()
    for m in registry.selected(remix):
        if m.dsp is None:
            continue
        stem = pathlib.Path(m.dsp.asm).stem
        row = cc.measure(stem)
        server = m.dsp.bus_role is BusRole.SERVER
        on_fx1 = (m.key in fx1_keys) or (not fx1_keys and m.menu is not None
                                         and m.menu.replaces in stock_fx1)
        fx1_only = m.claims is not None and m.claims.fx1_only
        on_fx2 = not fx1_only and m.key != "SEND"      # SEND is the FX2 fallback itself
        mods[m.key] = dict(stem=stem, cycles=row["cycles"], inner=row["inner"],
                          server=server, on_fx1=on_fx1, on_fx2=on_fx2)
    return mods


def enumerate_layouts(mods, core_server):
    """Every (fx1, fx2) x 4 tracks for one core, as sorted tuples (order on a
    core does not change the sum), with the per-core cost."""
    fx1_opts = [None] + sorted(k for k, m in mods.items() if m["on_fx1"] and not m["server"])
    fx2_opts = ["SEND"] + sorted(k for k, m in mods.items() if m["on_fx2"] and not m["server"] and k != "SEND")
    if core_server:
        fx2_opts.append(core_server)
    slots = [(a, b) for a in fx1_opts for b in fx2_opts]
    cost = {k: m["cycles"] for k, m in mods.items()}
    cost[None] = 0
    seen = {}
    for combo in itertools.combinations_with_replacement(slots, TRACKS_PER_CORE):
        if sum(1 for _, b in combo if b == core_server) > 1:
            continue                                   # one server per core
        c = sum(cost[a] + cost[b] for a, b in combo)
        seen[combo] = c
    return seen


def price(a):
    import cycle_count as cc
    remix = registry.remix(a.remix)
    mods = price_modules(remix)
    servers = [k for k, m in mods.items() if m["server"]]
    # the FILTER credit, as cycle_count computes it
    _all = registry.modules()
    filter_listed = "FILTER" in set(remix.modules) | set(remix.fx1)
    filter_replaced = any(_all[k].menu is not None and _all[k].menu.replaces == "FILTER" for k in mods)
    credit = 0 if (filter_listed and not filter_replaced) else 4 * 192
    # ⚠️ TWO LINES, because the credit is arithmetic and the hang is measured:
    # tag 91 (4 Sep 2026) hung the sequencer with three stations beside the
    # reverb at a STATIC 3,106 -- under USABLE, let alone USABLE + credit --
    # so on core 0 the credited line is optimistic and the flat line is the
    # one to design against until the burn sweep says otherwise.
    wall = a.wall or cc.USABLE
    wall_credit = cc.USABLE + credit
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"remix {remix.name!r}: wall = {wall} cycles/sample per core (USABLE; tag 91 hung at a static 3,106); "
          f"credited line {wall_credit} (+{credit} FILTER credit) shown beside it")
    print(f"{'module':16} {'cycles':>7}  fx1 fx2 server  worst loop")
    for k, m in sorted(mods.items(), key=lambda kv: -kv[1]["cycles"]):
        print(f"{k:16} {m['cycles']:7d}  {'x' if m['on_fx1'] else '.':^3} {'x' if m['on_fx2'] else '.':^3} "
              f"{'x' if m['server'] else '.':^6}  {m['inner']}")
    rows = []
    summary = {}
    for core, label in ((0, "core 0 (T5-8)"), (1, "core 1 (T1-4)")):
        # which server lives on this core: payload A (core 0) hosts the reverb
        srv = next((k for k in servers if (k == "REVERB SERVER") == (core == 0)), None)
        lay = enumerate_layouts(mods, srv)
        over = {c: v for c, v in lay.items() if v > wall}
        under = {c: v for c, v in lay.items() if v <= wall}
        over_c = sum(1 for v in lay.values() if v > wall_credit)
        print(f"\n{label}: server {srv or 'none'}; {len(lay)} layouts, {len(over)} over the wall "
              f"({100 * len(over) / len(lay):.0f}%; {over_c} = {100 * over_c / len(lay):.0f}% over the credited line)")
        if over:
            cheapest_over = min(over.items(), key=lambda kv: kv[1])
            print(f"  cheapest OVER : {cheapest_over[1]:5d}  {fmt(cheapest_over[0])}")
        if under:
            dearest_under = max(under.items(), key=lambda kv: kv[1])
            print(f"  dearest UNDER : {dearest_under[1]:5d}  {fmt(dearest_under[0])}")
        worst = max(lay.items(), key=lambda kv: kv[1])
        print(f"  worst         : {worst[1]:5d}  {fmt(worst[0])}")
        # how many of the dearest station fit beside the server, FX1 only / both slots
        stations = sorted((k for k, m in mods.items() if not m["server"] and k != "SEND"),
                          key=lambda k: -mods[k]["cycles"])
        if stations and srv:
            base = mods[srv]["cycles"] + 3 * mods["SEND"]["cycles"] if "SEND" in mods else mods[srv]["cycles"]
            for st in stations:
                n = int((wall - base) // mods[st]["cycles"])
                print(f"  beside {srv}: {n} x {st} fit on the arithmetic ({mods[st]['cycles']} each, {base} base)")
        for combo, v in sorted(lay.items(), key=lambda kv: -kv[1]):
            rows.append((core, v, "OVER" if v > wall else ("over-credited" if v > wall_credit else "ok"), fmt(combo)))
        summary[label] = dict(server=srv, layouts=len(lay), over=len(over), over_credited=over_c, worst=worst[1],
                              worst_layout=fmt(worst[0]))
    tsv = OUT / f"{remix.name}_layouts.tsv"
    with open(tsv, "w") as f:
        f.write("core\tcycles\tverdict\tlayout\n")
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")
    (OUT / f"{remix.name}_price.json").write_text(json.dumps(dict(remix=remix.name, wall=wall, wall_credited=wall_credit, credit=credit,
                                                                   modules={k: m["cycles"] for k, m in mods.items()},
                                                                   cores=summary), indent=1))
    print(f"\n-> {tsv} ({len(rows)} rows)")


def fmt(combo):
    return " | ".join(f"{a or '-'}+{b}" for a, b in combo)


# ---- A2: render ------------------------------------------------------------
# Every mode and knob at its dearest setting. Modes are the pricer's "worst
# loop"; knobs that gate work (a send at 0 registers nothing, MIX 0 can
# short-circuit a stage) go to their maximum so nothing is skipped.
DEAR = {
    "CHARACTER": {"DRV": 127, "FOLD": 127, "CRSH": 127, "COMP": 127, "MIX": 127, "RING": 127, "WDTH": 127, "SRR": 3},
    "SPECTRUM": {"RES": 127, "DRV": 127, "MODE": 4, "ROUT": 3, "SRC": 2, "DPTH": 127},
    "MODULATION": {"MIX": 127, "FDBK": 127, "DPTH": 127, "MODE": 2, "STGS": 3},
    "DELAY SERVER": {"AUX": 100, "FDBK": 100, "MODE": 1, "MDEP": 127, "MRAT": 127, "MIX": 127, "FRZE": 0},
    "REVERB SERVER": {"AUX": 100, "MODE": 2, "SHMR": 127, "DIFF": 127, "GATE": 0, "MIX": 127, "MOD": 127},
    "SEND": {"AUX": 100},
}
LETTER_TRACKS = {0: (5, 6, 7, 8), 1: (1, 2, 3, 4)}


def render(a):
    remix = registry.remix(a.remix)
    tsv = OUT / f"{remix.name}_layouts.tsv"
    if not tsv.is_file():
        sys.exit(f"{tsv} missing -- run `pressure.py price --remix {remix.name}` first")
    rows = [l.rstrip("\n").split("\t") for l in open(tsv)][1:]
    by_core = {0: [], 1: []}
    for core, cyc, verdict, layout in rows:
        by_core[int(core)].append((int(cyc), verdict, layout))
    random.seed(a.seed)
    picks = []
    for core in (0, 1):
        lst = by_core[core]                       # already sorted dearest first
        picks += [(core, *r) for r in lst[:a.top]]
        picks += [(core, *r) for r in random.sample(lst[a.top:], min(a.sample, max(0, len(lst) - a.top)))]
    image = pathlib.Path(a.image)
    if not image.is_file():
        sys.exit(f"{image} missing -- `make bus REMIX={remix.name}` first")
    stems = pathlib.Path(a.stems)
    if not any(stems.glob("T*.wav")):
        sys.exit(f"no stems in {stems} -- `python3 scripts/make_test_audio.py` and copy/rename to T1..T8.wav, or --stems")
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for n, (core, cyc, verdict, layout) in enumerate(picks):
        tracks, sets = [], []
        for t, slot in zip(LETTER_TRACKS[core], layout.split(" | ")):
            fx1, fx2 = slot.split("+")
            tracks.append(f"T{t}={fx2}" if fx1 == "-" else f"T{t}={fx1}+{fx2}")
            for eff, fxn in ((fx1, 1), (fx2, 2)):
                for k, v in DEAR.get(eff, {}).items():
                    sets += ["--set", f"T{t}:FX{fxn}:{k}={v}"]
        # the other core carries the plain rig so the bus has both ends
        other = 1 - core
        for t in LETTER_TRACKS[other]:
            tracks.append(f"T{t}=SEND")
        outdir = OUT / f"render_{remix.name}_c{core}_{n:03d}"
        cmd = [sys.executable, str(ROOT / "tools/harness/rig_render.py"), "--image", str(image), "--remix", remix.name,
               "--tracks", ",".join(tracks), "--stems", str(stems), "--seconds", str(a.seconds), "--tail", "0.5",
               "--frames", "16", "--extra=-guard -dirty 0x5a", "-v", "--out", str(outdir)] + sets
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        text = r.stdout + r.stderr
        (outdir.parent / f"{outdir.name}.log").write_text(text)
        meter = {}
        for line in text.splitlines():
            if "meter:" in line:
                c = int(line.split("core")[1].split()[0]); mx = int(line.split("max")[1].split()[0])
                per = float(line.split("(")[1].split("/sample")[0])
                meter[c] = (mx, per)
        # What is a red: a HANG, a CLOBBER of a loaded module, or a STRAY
        # write from a NON-server instance. A server writes the bus scratch
        # and (the reverb) its relocated buffers outside its own window by
        # design, so its strays are expected and listed, not failed. A
        # clipped mix.wav is the fixture (every knob at its dearest), not the
        # DSP -- reported, not failed.
        flags, notes = [], []
        inst_kind = {}
        for l in text.splitlines():
            m_ = re.match(r"\s+T(\d) FX(\d) (\S+(?: \S+)?)\s+core", l)
            if m_:
                inst_kind[len(inst_kind)] = m_.group(3).strip()
            if "HANG" in l:
                flags.append(l.strip())
            elif "clipped samples" in l:
                notes.append(l.strip().split("!!")[1].split("(")[0].strip())
            m_ = re.search(r"instance (\d+): .* (\d+) stray write regions, (\d+) CLOBBERING", l)
            if m_:
                k, stray, clob = int(m_.group(1)), int(m_.group(2)), int(m_.group(3))
                who = inst_kind.get(k, "?")
                if clob:
                    flags.append(f"instance {k} ({who}) CLOBBERS a loaded module ({clob} regions)")
                elif stray and who not in ("REVERB SERVER", "DELAY SERVER"):
                    flags.append(f"instance {k} ({who}) writes {stray} stray regions outside its window")
                elif stray:
                    notes.append(f"{who} {stray} strays (bus scratch/relocated buffers: expected)")
        failed = r.returncode != 0 or bool(flags)
        report.append(dict(n=n, core=core, static=cyc, verdict=verdict, layout=layout, rc=r.returncode,
                           meter=meter, flags=flags[:8], notes=notes[:8]))
        m = meter.get(core, (0, 0.0))
        print(f"[{n:03d}] core {core} static {cyc:5d} {verdict:4}  meter {m[1]:7.1f}/sample  "
              f"{'RED ' + ('; '.join(flags[:2]) or f'rc {r.returncode}') if failed else 'memory clean'}"
              f"{'  (' + '; '.join(notes[:2]) + ')' if notes else ''}   {layout}")
    (OUT / f"{remix.name}_render.json").write_text(json.dumps(report, indent=1))
    bad = [r for r in report if r["rc"] != 0 or r["flags"]]
    over = [r for r in report if r["verdict"] != "ok"]
    print(f"\n{len(report)} layouts rendered, {len(bad)} with a local red (a clobber, a stray from an insert, a hang, a refused run);"
          f" {len(over)} of them price OVER the wall and rendered anyway -- the emulator has no cliff."
          f"\nMemory is what this pass can prove; cycles are the burn sweep's (CHIP.md s2).")
    return 1 if bad else 0


# ---- A3: the documented soft failures ---------------------------------------
# Layouts the enumeration excludes by rule or that a knob can reach, each of
# which some document calls a glitch, a hang or a squeal. Rendered under the
# same police; the verdict is the guard's plus the output's peak (a squeal
# reads as a rail-to-rail tail after the stems stop).
ODD = [
    ("two delay servers on core 1 (shared scratch: BUS.md Known limitations)",
     "T1=DELAY SERVER,T2=DELAY SERVER,T3=SEND,T4=SEND,T5=REVERB SERVER,T6=SEND", ["T3:AUX=100", "T4:AUX=100"]),
    ("two reverb servers on core 0",
     "T5=REVERB SERVER,T6=REVERB SERVER,T7=SEND,T1=DELAY SERVER,T2=SEND", ["T7:AUX=100", "T2:AUX=100"]),
    ("reverb on FX1 and FX2 of one track (PARAM_PAGES 5d)",
     "T5=REVERB SERVER+REVERB SERVER,T6=SEND,T1=DELAY SERVER,T2=SEND", ["T6:AUX=100", "T2:AUX=100"]),
    ("delay on FX1 and FX2 of one track",
     "T1=DELAY SERVER+DELAY SERVER,T2=SEND,T5=REVERB SERVER,T6=SEND", ["T2:AUX=100", "T6:AUX=100"]),
    ("Character BUS mode (the return) on T4, not T8",
     "T4=CHARACTER,T1=DELAY SERVER,T2=SEND,T5=REVERB SERVER,T8=CHARACTER", ["T4:SAT=3", "T4:RET=127", "T8:SAT=3", "T8:RET=127", "T2:AUX=100"]),
    ("reverb DIFF 127 (the 4 Sep squeal)",
     "T5=REVERB SERVER,T6=SEND,T1=DELAY SERVER,T2=SEND", ["T5:DIFF=127", "T5:TIME=127", "T5:MOD=127", "T6:AUX=127", "T2:AUX=127"]),
    ("delay FDBK 127, FRZE HOLD, GRAIN",
     "T1=DELAY SERVER,T2=SEND,T5=REVERB SERVER,T6=SEND", ["T1:FDBK=127", "T1:MODE=1", "T1:FRZE=1", "T1:MRAT=127", "T2:AUX=127"]),
    ("every station at every extreme on one track, both slots",
     "T5=SPECTRUM+CHARACTER,T6=SEND,T1=MODULATION+SPECTRUM,T2=SEND",
     ["T5:FX1:RES=127", "T5:FX1:DRV=127", "T5:FX1:MODE=4", "T5:FX1:ROUT=3", "T5:FX2:DRV=127", "T5:FX2:FOLD=127", "T5:FX2:CRSH=127",
      "T1:FX1:FDBK=127", "T1:FX1:MIX=127", "T1:FX1:MODE=3", "T1:FX2:RES=127", "T1:FX2:ROUT=2"]),
]


def oddities(a):
    remix = registry.remix(a.remix)
    image = pathlib.Path(a.image)
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for n, (what, tracks, sets) in enumerate(ODD):
        outdir = OUT / f"odd_{remix.name}_{n:02d}"
        cmd = [sys.executable, str(ROOT / "tools/harness/rig_render.py"), "--image", str(image), "--remix", remix.name,
               "--tracks", tracks, "--stems", a.stems, "--seconds", str(a.seconds), "--tail", "2.0",
               "--frames", "16", "--extra=-guard -dirty 0x5a", "-v", "--out", str(outdir)]
        for sv in sets:
            cmd += ["--set", sv]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        text = r.stdout + r.stderr
        (OUT / f"odd_{remix.name}_{n:02d}.log").write_text(text)
        flags = [l.strip() for l in text.splitlines() if "HANG" in l or "CLOBBERING a loaded module" in l and not l.strip().endswith("0 CLOBBERING a loaded module")]
        if r.returncode != 0:
            flags.append(f"rc {r.returncode}: {text.strip().splitlines()[-1] if text.strip() else ''}")
        # the tail: does anything ring on after the stems stop (a squeal, a runaway)?
        tail_db = {}
        try:
            import wave, math
            for t in range(1, 9):
                w = outdir / f"T{t}.wav"
                if not w.is_file():
                    continue
                with wave.open(str(w)) as f:
                    nfr = f.getnframes(); f.setpos(max(0, nfr - 22050)); raw = f.readframes(22050)
                vals = [int.from_bytes(raw[i:i + 3], "little", signed=True) / 8388608 for i in range(0, len(raw), 3)]
                rms_ = math.sqrt(sum(v * v for v in vals) / len(vals)) if vals else 0
                tail_db[t] = round(20 * math.log10(rms_), 1) if rms_ > 0 else -200
        except Exception as e:      # noqa: BLE001
            flags.append(f"tail read failed: {e}")
        peaks = {int(l.split("T")[1].split(".")[0]): float(l.split("peak")[1].split()[0])
                 for l in text.splitlines() if l.strip().startswith("T") and ".wav  peak" in l}
        loud = {t: d for t, d in tail_db.items() if d > -20}
        if loud:
            flags.append(f"tail still at {loud} dBFS 0.5 s after the stems stop (runaway/squeal?)")
        print(f"[odd {n:02d}] {'RED' if flags else 'ok '}  {what}\n          peak dBFS: "
              + " ".join(f"T{t}:{d}" for t, d in sorted(peaks.items()))
              + "\n          tail (last 0.5 s of a 2 s tail, dBFS): "
              + " ".join(f"T{t}:{d}" for t, d in sorted(tail_db.items())) + ("\n          " + "; ".join(flags) if flags else ""))
        report.append(dict(n=n, what=what, tracks=tracks, sets=sets, rc=r.returncode, flags=flags, tail_db=tail_db, peaks=peaks))
    (OUT / f"{remix.name}_oddities.json").write_text(json.dumps(report, indent=1))
    return 1 if any(r["flags"] for r in report) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("price"); p.add_argument("--remix", default=os.environ.get("REMIX", "bamsep26"))
    p.add_argument("--wall", type=int, help="cycles/sample per core to score against (default USABLE = 3120)")
    r = sub.add_parser("render")
    r.add_argument("--remix", default=os.environ.get("REMIX", "bamsep26"))
    r.add_argument("--image", default="out/mainos_bus.bin")
    r.add_argument("--top", type=int, default=6, help="dearest layouts per core")
    r.add_argument("--sample", type=int, default=4, help="random extra layouts per core")
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--seconds", type=float, default=2.0)
    r.add_argument("--stems", default="out/test_audio/rig")
    o = sub.add_parser("oddities")
    o.add_argument("--remix", default=os.environ.get("REMIX", "bamsep26"))
    o.add_argument("--image", default="out/mainos_bus.bin")
    o.add_argument("--seconds", type=float, default=2.0)
    o.add_argument("--stems", default="out/test_audio/rig")
    a = ap.parse_args()
    return {"price": price, "render": render, "oddities": oddities}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main() or 0)
