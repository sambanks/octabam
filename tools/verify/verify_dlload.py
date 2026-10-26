#!/usr/bin/env python3
"""The demand loader under the port: DLPUMP loads and withdraws an effect as the tracks use it, DLCOPY publishes it.

    python3 tools/verify/verify_dlload.py [REMIX] [--project DIR]       (default test/dlspike)

Builds the remix (default test/dlspike: MODULATION on demand; octabam: four effects) and runs scenarios on the
staged project, each on its own boot, setting track effect ids by poking the live arrays
(0x80000ec4 FX1, 0x80000ecc FX2) and the Part bytes behind them. Effects are numbered as in
Remix.window_demand (k):

  used       T1.. use effects 0.. on FX1 from the start -> each bound, its entry and code in the window
                                                          word for word, seen from both cores
  withdrawn  the same, T1's FX1 back to FILTER at 2 s  -> effect 0 unbound after the 2 s grace, its span empty, the rest bound
  grace      effect 0 unused at 2 s and used again at 3 s -> still bound, loaded once
  reverb-takes  effect 0 unused at 2 s, a reverb on its block at 2.5 s -> unbound by 3.4 s, well inside the grace
  pick-reverb-unused  effect 0 loaded and unused: the FX2 chooser accepts a reverb on its block, no toast, effect withdrawn
  unused     no track uses any                          -> none bound
  plate-ok / spring-ok  effect 0 in use with PLATE or SPRING REV on its block's track -> loaded, no toast (neither reaches the code)
  race       effect 0 in use, a DARK REV on its block 60 ms later (inside the load debounce) -> never loaded, no block received
  toast text  each effect's toast strings (EVICT Tn FX2 1ST, EVICT <name> 1ST) name the track of its own block and the effect's chooser name (the generated table)
  two-b, two-a, two-ab-b, two-ab-a  effect 0 on two tracks of one core, and on one track of each core: the instances each have their own r7 (a pcwatch on the proc)
  runs-b<k> / runs-a<k>  T1 (core B) / T5 (core A) uses effect k -> its loaded proc is reached on that core (--dsp-pcwatch)
  reverb-late effect 0 in use and loaded, then at 2 s the FX2 of its block's track becomes DARK REV (a route the choosers do not guard) -> effect 0 moves to its second home
  blocked    effect 0 in use, and the FX2 of its first home's track is DARK REV -> effect 0 is loaded into its second home, no toast
  both-blocked  DARK REV on the FX2 of both homes' tracks -> not loaded, a toast at the next page key
  stuck      effect 0 loaded in its first home, DARK REV already on the second's track, then on the first's -> it stays, a toast
  pick / pick-blocked  T2's chooser (FX1, else FX2; NONE, DOWN to its row, YES) picks effect 0; with the block's track on DARK REV
             the chooser leaves T2's FX1 as it was

Cannot see: the hardware's host-write timing, other projects' use of X:0x2840..0x3fff.
"""
import argparse, json, os, pathlib, re, shutil, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/dlload"
STAGE = 0x2900
FX1_LIVE, FX2_LIVE = 0x80000EC4, 0x80000ECC
FX1_PART, FX2_PART = 0x402A75E0, 0x402A75E8      # Part 1's FX ids of track 1 (bank + 0x8ed80 / 0x8ed88)
FILTER, PLATE, SPRING, DARK = 0x01, 0x14, 0x15, 0x16      # DARK REV is the reverb whose buffer reaches the demand effect's code
KEYS = dict(no=0x32, fx1=0x25, fx2=0x26, down=0x20, yes=0x31, **{f"t{i + 1}": 0x10 + i for i in range(8)})
TOAST = 0x4005A2B8          # the firmware's message popup: every decision the loader makes on a chooser ends here
FAILS = []


def check(what, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {what}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(what)


def poke(live, part, track, value):
    return f"{live + track:#x}={value:#x};{part + track:#x}={value:#x}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default="test/dlspike")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--set-name", default="BRAINSET")
    ap.add_argument("--name", default="BRAINPRJ")
    ap.add_argument("--ms", type=int, default=7000)
    a = ap.parse_args()
    project = a.project
    if not project and pathlib.Path("~/.octabam_project").expanduser().is_file():
        project = pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
    if not project:
        print("  [SKIP] verify_dlload: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_dlload: no port binary (make emu-cf)"); return 0
    OUT.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env, capture_output=True,
                       text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_dlload: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "mainos.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    recs = list(json.loads((ROOT / "out/dsp/demand_records.json").read_text()).items())
    from remix import registry
    order = list(registry.remix(a.remix).window_demand)
    recs = [dict(next(r for key, r in recs if key == k), key=k) for k in order]
    rec = recs[0]
    mod_id = rec["id"]

    copy = OUT / "project"
    shutil.rmtree(copy, ignore_errors=True)
    copy.mkdir(parents=True)
    for f in pathlib.Path(project).expanduser().iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)

    every = ";".join(poke(FX1_LIVE, FX1_PART, t, r["id"]) for t, r in enumerate(recs))
    block_track = {0: 6, 1: 7, 2: 2, 3: 3}[(rec["addr"] - 0x30000) >> 14 & 3]       # modules/dlpump/manifest.py
    # the chooser that lists effect 0 (FX1 when it has a row there) and its row, from the image's id -> row tables
    img = image.read_bytes()
    row1, row2 = (int.from_bytes(img[addr + 4 * mod_id - 0x40000400:][:4], "big") for addr in (0x400D60D0, 0x400D6150))
    chooser, row = ("fx1", row1) if row1 else ("fx2", row2)
    if not row:
        sys.exit(f"verify_dlload: {rec['key']} (id 0x{mod_id:02x}) is on neither chooser")
    live, part, slot = (FX1_LIVE, FX1_PART, 0) if chooser == "fx1" else (FX2_LIVE, FX2_PART, 8)
    ALT = rec["homes"][1]["addr"]                                                   # its second home
    alt_track = {0: 6, 1: 7, 2: 2, 3: 3}[(ALT - 0x30000) >> 14 & 3]                 # the FX2 track whose slot shares that block
    both = poke(FX2_LIVE, FX2_PART, block_track, DARK) + ";" + poke(FX2_LIVE, FX2_PART, alt_track, DARK)
    every_first = poke(FX1_LIVE, FX1_PART, 0, mod_id)
    reverb_row = int.from_bytes(img[0x400D6150 + 4 * DARK - 0x40000400:][:4], "big")     # DARK REV's row on the FX2 chooser
    scenarios = {
        "used": (every, []),
        "withdrawn": (every, [(2000, poke(FX1_LIVE, FX1_PART, 0, FILTER))]),
        "unused": ("", []),
        "plate-ok": (poke(FX1_LIVE, FX1_PART, 0, mod_id) + ";" + poke(FX2_LIVE, FX2_PART, block_track, PLATE), []),      # reverbs the code is clear of
        "spring-ok": (poke(FX1_LIVE, FX1_PART, 0, mod_id) + ";" + poke(FX2_LIVE, FX2_PART, block_track, SPRING), []),
        "race": (poke(FX1_LIVE, FX1_PART, 0, mod_id), [(60, both)]),     # a reverb on every home 60 ms behind the effect
        "grace": (poke(FX1_LIVE, FX1_PART, 0, mod_id),            # unused at 2 s, used again at 3 s: inside the 2 s grace
                  [(2000, poke(FX1_LIVE, FX1_PART, 0, FILTER)), (3000, poke(FX1_LIVE, FX1_PART, 0, mod_id))]),
        "reverb-late": (poke(FX1_LIVE, FX1_PART, 0, mod_id), [(2000, poke(FX2_LIVE, FX2_PART, block_track, DARK))]),
        "blocked": (poke(FX1_LIVE, FX1_PART, 0, mod_id) + ";" + poke(FX2_LIVE, FX2_PART, block_track, DARK), []),      # its first home is under DARK REV
        "both-blocked": (poke(FX1_LIVE, FX1_PART, 0, mod_id) + ";" + both, []),                                         # every home is
        "stuck": (poke(FX1_LIVE, FX1_PART, 0, mod_id) + ";" + poke(FX2_LIVE, FX2_PART, alt_track, DARK),
                  [(2000, poke(FX2_LIVE, FX2_PART, block_track, DARK))]),                                              # loaded, then nowhere to move to
        "pick": (poke(live, part, 1, 0), []),
        "pick-blocked": (poke(live, part, 1, 0) + ";" + poke(FX2_LIVE, FX2_PART, block_track, DARK), []),
        "pick-both-blocked": (poke(live, part, 1, 0) + ";" + both, []),
        "pick-reverb": (every_first + ";" + poke(FX2_LIVE, FX2_PART, block_track, 0), []),
        "pick-reverb-stuck": (every_first + ";" + poke(FX2_LIVE, FX2_PART, block_track, 0) + ";" + poke(FX2_LIVE, FX2_PART, alt_track, DARK), []),
        "pick-reverb-unused": (every_first + ";" + poke(FX2_LIVE, FX2_PART, block_track, 0),
                               [(2000, poke(FX1_LIVE, FX1_PART, 0, FILTER))]),         # loaded, but no track uses it
        "reverb-takes": (poke(FX1_LIVE, FX1_PART, 0, mod_id),                           # unused at 2 s, a reverb arrives at 2.5 s
                         [(2000, poke(FX1_LIVE, FX1_PART, 0, FILTER)), (2500, poke(FX2_LIVE, FX2_PART, block_track, DARK))]),
    }
    watch = {}
    for k, r in enumerate(recs):                                   # every effect, on a track of each core
        scenarios[f"runs-b{k}"] = (poke(FX1_LIVE, FX1_PART, 0, r["id"]), [])      # T1 is on core B
        scenarios[f"runs-a{k}"] = (poke(FX1_LIVE, FX1_PART, 4, r["id"]), [])      # T5 is on core A
        watch[f"runs-b{k}"], watch[f"runs-a{k}"] = f"1:{r['proc']:x}", f"0:{r['proc']:x}"
    TWO = {"two-b": ((0, 1), 1, 2), "two-a": ((4, 5), 0, 2),             # tag: (tracks, watched core, instances it sees)
           "two-ab-b": ((0, 4), 1, 1), "two-ab-a": ((0, 4), 0, 1)}       # one track on each core, the same effect
    for tag, (tracks, core, _) in TWO.items():
        scenarios[tag] = (";".join(poke(FX1_LIVE, FX1_PART, t, rec["id"]) for t in tracks), [])
        watch[tag] = f"{core}:{rec['proc']:x}"
    procs = {}
    for tag, (first, later) in scenarios.items():
        card = OUT / f"{tag}.img"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                            "--tree", str(OUT / f"tree_{tag}"), "--out", str(card)], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_dlload: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        lines = [f"{ms} poke {p}" for ms, p in later]
        if tag.startswith("pick"):
            t = 1500 if not tag.startswith("pick-reverb") else 3500   # after the load has landed
            if tag.startswith("pick-reverb"):
                keys = ((f"t{block_track + 1}", 400), ("fx2", 160), ("fx2", 800)) + (("down", 500),) * reverb_row + (("yes", 1500),)
            else:
                keys = (("no", 400), ("t2", 400), (chooser, 160), (chooser, 800)) + (("down", 500),) * row + (("yes", 1500),)
            if tag.startswith("pick-reverb"):
                lines += [f"1500 key {KEYS['no']:#x} down", f"1540 key {KEYS['no']:#x} up"]
            for k, gap in keys:
                lines += [f"{t} key {KEYS[k]:#x} down", f"{t + 40} key {KEYS[k]:#x} up"]
                t += 40 + gap
        if tag in ("used", "blocked", "both-blocked", "stuck", "reverb-late", "plate-ok", "spring-ok"):               # a page key after the decision: where a deferred toast shows
            lines += [f"{a.ms - 800} key {KEYS['fx1']:#x} down", f"{a.ms - 760} key {KEYS['fx1']:#x} up"]
        # the script is read in order, so a quit that is earlier than the last key waits for it; after a pick that moves
        # an effect, the reload (the debounce, then three sends) needs a few seconds past the last key
        lines.append(f"{(t + 3000) if tag == 'pick-reverb' else (3400 if tag == 'reverb-takes' else a.ms)} quit")
        (OUT / f"{tag}.script").write_text("\n".join(lines) + "\n")
        dump = OUT / f"{tag}_ids.bin"
        peeks = ";".join(f"{c}:X:{STAGE:x},1;{c}:X:{0x33DA3 + 8 * k:x},8;{c}:P:{r['addr']:x},{len(r['words'])}"
                         for c in (0, 1) for k, r in enumerate(recs))
        cmd = [EMU, "--image", image, "--card", card, "--set", a.set_name, "--project", a.name, "--load-ms", "90000",
               "--mkii", "--dsp", "--frame", "--live-script", OUT / f"{tag}.script", "--dsp-peek", peeks,
               "--mem-dump", f"{FX1_LIVE:#x},16={dump}"]
        if first:
            cmd += ["--step", "-:poke:" + first]
        if tag in watch:
            cmd += ["--dsp-pcwatch", watch[tag]]
        if tag.startswith("pick") or tag in ("used", "blocked", "both-blocked", "stuck", "reverb-late", "plate-ok", "spring-ok"):
            cmd += ["--watch-pc", f"{TOAST:#x}"]
        fh = open(OUT / f"{tag}.txt", "w")
        procs[tag] = (subprocess.Popen(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT), fh)
    texts = {}
    for tag, (p, fh) in procs.items():
        rc = p.wait()
        fh.close()
        texts[tag] = (OUT / f"{tag}.txt").read_text(errors="replace")
        if rc or "ended on quit" not in texts[tag]:
            sys.exit(f"verify_dlload: the {tag} run did not finish -- {OUT / (tag + '.txt')}")

    def peek(tag, core, space, addr):
        m = re.search(rf"core {core} {space}:0x0*{addr:x}:([^\n]*)", texts[tag])
        return [int(t, 16) for t in m.group(1).split()] if m else []

    print("used:")
    for k, r in enumerate(recs):
        n = len(r["words"])
        for c in (1, 0):
            entry = peek("used", c, "X", 0x33DA3 + 8 * k)
            check(f"core {c}: {r['key']} is bound with its entries and span",
                  entry[:5] == [0xB0A5ED, r["init"], r["proc"], r["addr"], r["addr"] + n], f"{[hex(w) for w in entry]}")
            if c == 1:
                check(f"{r['key']}: the copier counted three blocks received, none refused, three published (DLPROBE's counters)",
                      entry[5:8] == [3, 0, 3], f"{entry[5:8]}")
            code = peek("used", c, "P", r["addr"])
            check(f"core {c}: {r['key']}'s code is in the window, every word", code == r["words"],
                  f"{len(code)} of {n} words read")
    check("the doorbell was consumed", peek("used", 1, "X", STAGE) == [0])
    print("withdrawn:")
    entry = peek("withdrawn", 1, "X", 0x33DA3)
    check(f"{recs[0]['key']} is unbound and its span empty", entry[:1] == [0] and entry[3:5] == [0, 0], f"{[hex(w) for w in entry]}")
    for k, r in enumerate(recs[1:], 1):
        check(f"{r['key']} stays bound", peek("withdrawn", 1, "X", 0x33DA3 + 8 * k)[:1] == [0xB0A5ED])
    print("grace:")
    entry = peek("grace", 1, "X", 0x33DA3)
    check(f"{recs[0]['key']} stays loaded through a short gap in use, and is not loaded a second time",
          entry[:1] == [0xB0A5ED] and entry[5:8] == [3, 0, 3], f"{[hex(w) for w in entry]}")
    print("unused:")
    for k, r in enumerate(recs):
        check(f"{r['key']} was never bound", peek("unused", 1, "X", 0x33DA3 + 8 * k)[:1] == [0])
    print("reverb-late:")
    entry = peek("reverb-late", 1, "X", 0x33DA3)
    check(f"{recs[0]['key']} moves to its second home when a stock reverb that reaches its code arrives on its block "
          f"(P:0x{ALT:05x}), loaded twice and intact", entry[0] == 0xB0A5ED and entry[3] == ALT and entry[5:8] == [6, 0, 6],
          f"{[hex(w) for w in entry]}")
    print("blocked:")
    entry = peek("blocked", 1, "X", 0x33DA3)
    check(f"{recs[0]['key']} is loaded into its second home when the first is under a reverb that reaches it",
          entry[0] == 0xB0A5ED and entry[3] == ALT and entry[5:8] == [3, 0, 3], f"{[hex(w) for w in entry]}")
    print("both-blocked:")
    check(f"{recs[0]['key']} is not loaded when every home is under such a reverb", peek("both-blocked", 1, "X", 0x33DA3)[:1] == [0])
    print("stuck:")
    entry = peek("stuck", 1, "X", 0x33DA3)
    check(f"{recs[0]['key']} stays in its first home when a reverb reaches it and the other home is taken",
          entry[0] == 0xB0A5ED and entry[3] == rec["addr"] and entry[5:8] == [3, 0, 3], f"{[hex(w) for w in entry]}")
    print("race:")
    entry = peek("race", 1, "X", 0x33DA3)
    check(f"{recs[0]['key']} is not loaded when reverbs arrive on every home 60 ms after it (a project load writes the ids over a stretch of frames)",
          entry[:1] == [0] and entry[5:6] == [0], f"{[hex(w) for w in entry]}")
    print("pick:")
    ids = {t: (OUT / f"{t}_ids.bin").read_bytes() for t in ("pick", "pick-blocked", "pick-both-blocked")}
    check(f"T2's {chooser.upper()} chooser picks {recs[0]['key']} when it can be loaded", ids["pick"][slot + 1] == mod_id, f"{chooser} of T2 = 0x{ids['pick'][slot + 1]:02x}")
    check("and picks it when only its first home is under a reverb that reaches it (it loads into the second)",
          ids["pick-blocked"][slot + 1] == mod_id, f"{chooser} of T2 = 0x{ids['pick-blocked'][slot + 1]:02x}")
    check("and leaves T2's effect as it was when every home is", ids["pick-both-blocked"][slot + 1] == 0,
          f"{chooser} of T2 = 0x{ids['pick-both-blocked'][slot + 1]:02x}")
    def toasts(tag):
        m = re.search(r"watch-pc[^\n]*?(\d+) hit", texts[tag])
        return int(m.group(1)) if m else -1

    check("a refused pick shows a toast, an allowed one does not",
          toasts("pick-both-blocked") >= 1 and toasts("pick") == 0 and toasts("pick-blocked") == 0,
          f"toast calls: pick {toasts('pick')}, pick-blocked {toasts('pick-blocked')}, pick-both-blocked {toasts('pick-both-blocked')}")
    check("an effect with no home free says so at the next page key, and one that loads in its second home does not",
          toasts("both-blocked") >= 1 and toasts("blocked") == 0, f"toast calls: both-blocked {toasts('both-blocked')}, blocked {toasts('blocked')}")
    check("a reverb that reaches a loaded effect that cannot move (and runs dry) says so at the next page key; a move shows none",
          toasts("stuck") >= 1 and toasts("reverb-late") == 0, f"toast calls: stuck {toasts('stuck')}, reverb-late {toasts('reverb-late')}")
    check("no toast when nothing collides", toasts("used") == 0, f"toast calls: {toasts('used')}")
    print("clear reverbs:")
    for tag, rname in (("plate-ok", "PLATE REV"), ("spring-ok", "SPRING REV")):
        entry = peek(tag, 1, "X", 0x33DA3)
        check(f"{recs[0]['key']} loads with {rname} on its block's FX2 (the reverb's buffer ends below the code), and no toast is shown",
              entry[:1] == [0xB0A5ED] and toasts(tag) == 0, f"{[hex(w) for w in entry[:8]]}, toast calls {toasts(tag)}")
    print("pick-reverb:")
    rv = (OUT / "pick-reverb_ids.bin").read_bytes()
    check(f"a stock reverb chosen on the FX2 slot of {recs[0]['key']}'s block is accepted while the effect has another home to move to",
          rv[8 + block_track] == DARK and toasts("pick-reverb") == 0,
          f"FX2 of track {block_track + 1} = 0x{rv[8 + block_track]:02x}, toast calls {toasts('pick-reverb')}")
    entry = peek("pick-reverb", 1, "X", 0x33DA3)
    check(f"and the effect moves: it is bound in its second home", entry[0] == 0xB0A5ED and entry[3] == ALT, f"{[hex(w) for w in entry]}")
    print("pick-reverb-stuck:")
    rv = (OUT / "pick-reverb-stuck_ids.bin").read_bytes()
    check(f"a stock reverb chosen there is refused when the other home is taken",
          rv[8 + block_track] == 0, f"FX2 of track {block_track + 1} = 0x{rv[8 + block_track]:02x}")
    check("and the refusal shows a toast", toasts("pick-reverb-stuck") >= 1, f"toast calls: {toasts('pick-reverb-stuck')}")
    print("pick-reverb-unused:")
    rv = (OUT / "pick-reverb-unused_ids.bin").read_bytes()
    check("a reverb chosen on the block of a loaded effect that no track uses is accepted, without a toast",
          rv[8 + block_track] == DARK and toasts("pick-reverb-unused") == 0,
          f"FX2 of track {block_track + 1} = 0x{rv[8 + block_track]:02x}, toast calls {toasts('pick-reverb-unused')}")
    check(f"and {recs[0]['key']} is withdrawn for it",
          peek("pick-reverb-unused", 1, "X", 0x33DA3)[:1] == [0])
    print("reverb-takes:")
    entry = peek("reverb-takes", 1, "X", 0x33DA3)
    check(f"a reverb arriving on an unused loaded effect's block takes it at once: {recs[0]['key']} is unbound 0.9 s later, inside the grace",
          entry[:1] == [0], f"{[hex(w) for w in entry]}")
    print("runs:")
    for k, r in enumerate(recs):
        for tag, core in ((f"runs-b{k}", 1), (f"runs-a{k}", 0)):
            m = re.search(r"dsp pcwatch:[^\n]*\n((?: +\d+ [^\n]*\n)*)", texts[tag])
            arrivals = len(m.group(1).splitlines()) if m else None
            check(f"core {core}: {r['key']}'s loaded proc is reached on a track of that core", bool(arrivals),
                  f"arrivals at P:0x{r['proc']:x}: {arrivals}")
    print("instances:")
    for tag, (tracks, core, want) in TWO.items():
        m = re.search(r"dsp pcwatch:[^\n]*\n((?: +\d+ [^\n]*\n)*)", texts[tag])
        rows = [ln.split() for ln in m.group(1).splitlines()] if m else []
        bases = sorted({int(f[16], 16) for f in rows if len(f) > 16})
        check(f"{rec['key']} on tracks {[t + 1 for t in tracks]}: core {core} runs {want} instance(s), each with its own r7",
              len(bases) == want, f"{len(rows)} arrivals, r7 = {[hex(b) for b in bases]}")
    print("toast text:")
    inc = max((ROOT / "out/platform/runtime").glob("*_dlpump.inc/remix.inc"), key=lambda f: f.stat().st_mtime)
    text = inc.read_text()
    rows = [list(map(str.strip, m.split(","))) for m in re.findall(r"\.long\s+(0x[0-9a-f]+,\s*\d+,\s*dl_hm\d+[^\n]*)", text)]
    for k, key in enumerate(order):
        track = int(rows[k][1]) + 1
        name = registry.modules()[key].menu.fullname.decode().upper()[:10]
        need = re.search(rf'dl_need{k}: \.asciz "([^"]*)"', text).group(1)
        hold = re.search(rf'dl_hold{k}: \.asciz "([^"]*)"', text).group(1)
        check(f"{key}: its toasts name its block's track T{track}",
              need == f"EVICT T{track} FX2 1ST" and hold == f"EVICT {name} 1ST", f"{need!r}, {hold!r}")
    print("PASS" if not FAILS else "FAIL")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
