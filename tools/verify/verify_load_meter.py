#!/usr/bin/env python3
"""LOAD METER under the ColdFire port, with both DSP cores running.

    python3 tools/verify/verify_load_meter.py [remix] [--project DIR]

The remix (default `octabam-bus`) carries BRAIN and LOAD METER. Each run loads the
project, opens BRAIN > PERFORMANCE (or leaves it closed) and dumps LOAD METER's
lm_dsp and lm_ot (modules/load-meter/meter.s) and the screen's figures.

  publish     with the screen open: records arrive every frame (seq close to
              the frames run), periods in range, the DSP bars carry numbers,
              the refresh count rises
  otop        every effect slot (two cores x four tracks x FX1 and FX2) has
              samples, each mean cost is within its core's frame, the slots'
              means sum to no more than the core's mean busy time, and the
              heaviest slot of each core is the host engine on its track
              (core 0: T5's FX2, BusVerb; core 1: T1's FX2, BusDelay); in a
              remix without the bus the fixture puts id 0x16 (DARK REV, VERB
              HALL) on those two slots
  scrub       a write watch on MAIN's long 0 low byte (0x80005e63): the
              scrub (lm_scrub) zeroes it every frame the DSP wrote it
  every       lm_scrub runs once per frame interrupt (its pass count equals
              lm_out's), so it precedes every reader of MAIN in the interrupt
              (the stock recorder at 0x4000d340, USB's audio producer at 0x4000d9a0)
  usb         USB's audio-out ring (aud_ring, the producer forced on) is
              byte-identical between this build, an LM_NOPUB build (core 0
              publishes nothing) and an LM_NOOT build (OTOP's four hooks
              replay their displaced instruction and return): no published
              byte reaches a reader and the stamps change no sample
  closed      the screen closed: BRAIN's screen draw never runs and the
              host port carries the same blocks and words as with it open
  range       a DSP write watch on X:$37F28 (in the claimed $37F10-$37F2F,
              a word the meter never writes) on each core: only payload B's
              boot zero loop writes it
  calibrate   builds with LM_BURN = 0, 1000 and 3000 (a 1-cycle nop DO
              loop at each core's frame end): each core's mean busy over
              the run rises by the injected cycles in timer-0 counts (CLK/2,
              so N/2), within TOL; the error is printed

What it cannot see: the timer's rate and the burn's cost on the chip (the
port's cycle table; its timer moves in 1,024-count steps, so only means over
many samples are compared), DMA timing, hardware jitter. Every % and count is
a hardware-round item.
"""
import argparse, os, pathlib, re, shutil, struct, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
ELF = ROOT / "out/platform/runtime/runtime.elf"
OUT = ROOT / "out/loadmeter"
MAIN_LO = 0x80005e63
TOL = 0.05                       # measured errors 12 Oct 2026: +1.6%, +0.3%, -0.1%, +0.2%
BURNS = (0, 1000, 3000)
FAILS = []


def check(what, ok):
    print(f"  [{'ok' if ok else 'FAIL'}] {what}")
    if not ok:
        FAILS.append(what)


def symbol(name):
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    for line in subprocess.run([nm, str(ELF)], capture_output=True, text=True).stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == name:
            return int(parts[0], 16)
    sys.exit(f"verify_load_meter: {name} not in {ELF}")


def build(remix, burn, tag, nopub=False, noot=False, frame0=0):
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    env.pop("LM_BURN", None)
    env.pop("LM_NOPUB", None)
    env.pop("LM_NOOT", None)
    env.pop("LM_FRAME0", None)
    if frame0:
        env["LM_FRAME0"] = str(frame0)
    if noot:
        env["LM_NOOT"] = "1"
    if burn:
        env["LM_BURN"] = str(burn)
    if nopub:
        env["LM_NOPUB"] = "1"
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_load_meter: building {remix} (LM_BURN={burn}) failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / f"mainos_{tag}.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    return image, symbol("LM_DSP")


def syms():
    return dict(ot=symbol("LM_OT"), now=symbol("load_now"), ticks=symbol("load_ticks"), draw=symbol("brain_scr_draw"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default="octabam-bus")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--set-name", default="BRAINSET")
    ap.add_argument("--name", default="BRAINPRJ")
    ap.add_argument("--wrap-only", action="store_true", help="only the frame-count wrap check")
    ap.add_argument("--frames-ms", type=int, default=4000, help="emulated ms the view stays open")
    a = ap.parse_args()
    project = a.project
    if not project and pathlib.Path("~/.octabam_project").expanduser().is_file():
        project = pathlib.Path("~/.octabam_project").expanduser().read_text().strip()
    if not project:
        print("  [SKIP] verify_load_meter: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_load_meter: no port binary (make emu-cf)"); return 0
    remix = registry.remix(a.remix)
    if "LOAD METER" not in remix.modules or "BRAIN" not in remix.modules:
        print(f"  [ -- ] verify_load_meter: {a.remix} carries no LOAD METER and BRAIN"); return 0
    OUT.mkdir(parents=True, exist_ok=True)
    copy = OUT / "project"
    shutil.rmtree(copy, ignore_errors=True)
    copy.mkdir(parents=True)
    for f in pathlib.Path(project).expanduser().iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)
    # The otop and wrap checks name the heaviest slot of each core: T5's FX2 (core 0) and T1's FX2 (core 1), the
    # bus's host engines in a project RIG HOSTS wires. A remix without the bus gets the same two slots made the
    # heaviest in the copy: its id 0x16 (DARK REV in octabam, VERB HALL in octabam-verbs) on T1's and T5's FX2,
    # every other FX2 slot the generated project's DELAY. Until 15 Nov 2026 the gate ran with a project only on
    # octabam-bus's checks (sambanks/octabam#1051) and on octabam-verbs it found slots 7 and 12 heaviest.
    if "RIG HOSTS" not in remix.modules:
        sys.path.insert(0, str(ROOT / "tools/hw"))
        import ot_project as otp
        heavy = next((k for k, m in registry.bound(remix).items()          # the remix's own row, by key: a bare id
                      if k in remix.modules and getattr(m, "menu", None) is not None and m.menu.fx2_id == 0x16), None)
        if heavy is None:
            sys.exit(f"verify_load_meter: {a.remix} has no row on id 0x16 for the heaviest-slot fixture")
        for track in (1, 5):
            otp.set_fx(copy, "fx2", track, heavy, guard=False)

    into = [(0x1c, 500)] + [(0x20, 500)] * 4 + [(0x21, 500)]                 # PROJ, BRAIN's pane
    open_load = [(0x32, 500)] + into + [(0x20, 500)] * 3 + [(0x31, 500)]      # BRAIN > PERFORMANCE (the fourth row)

    def run(tag, image, lmd, keys, wait, extra=()):
        card = OUT / f"{tag}.img"
        r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                            "--tree", str(OUT / f"tree_{tag}"), "--out", str(card)], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_load_meter: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
        t, lines = 1500, []
        for code, gap in keys:
            lines += [f"{t} key {code:#x} down", f"{t + 30} key {code:#x} up"]
            t += gap
        lines.append(f"{t + wait} quit")
        (OUT / f"{tag}.script").write_text("\n".join(lines) + "\n")
        d_lmd, d_ot, d_now, d_ticks = (OUT / f"{tag}_lmd.bin", OUT / f"{tag}_ot.bin", OUT / f"{tag}_now.bin",
                                       OUT / f"{tag}_ticks.bin")
        sy = syms()
        cmd = [EMU, "--image", image, "--card", card, "--set", a.set_name, "--project", a.name,
               "--load-ms", "90000", "--mkii", "--dsp", "--frame", "--live-script", OUT / f"{tag}.script",
               "--mem-dump", f"{lmd:#x},72={d_lmd};{sy['ot']:#x},256={d_ot};{sy['now']:#x},12={d_now};{sy['ticks']:#x},4={d_ticks}",
               *extra]
        log = OUT / f"{tag}.txt"
        with open(log, "w") as fh:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        text = log.read_text()
        if r.returncode or "ended on quit" not in text:
            sys.exit(f"verify_load_meter: the {tag} run did not finish -- {log}")
        v = struct.unpack(">18I", d_lmd.read_bytes())
        ot = struct.unpack(">64I", d_ot.read_bytes())
        now = struct.unpack(">3i", d_now.read_bytes())
        ticks = struct.unpack(">I", d_ticks.read_bytes())[0]
        return v, (ot, now, ticks), text

    def host_totals(text, irqs):
        """Host commands per frame interrupt: writes to the HI08 command
        register (a --watch-mem on 0x20000004; the port prints no host-port
        summary under --live-script)."""
        n = sum(1 for ln in text.splitlines() if "[0x20000004]" in ln)
        return (round(n / irqs, 4),) if irqs and n else ()

    def wrap_check():
        # ---- wrap: core 0's frame count passes 2^23 and the slot index and costs stay right ----------------
        # With bit 23 of the count set, the next load sign-extends A2, `and #>$f` leaves it and `move a,n1` limits
        # the slot index to $800000: the cost read goes to a wild address. The port reads zero there and goes on;
        # the unit stopped its frame interrupt 50.7 minutes after power-up. The port shows it as costs of zero.
        image_w, lmd_w = build(a.remix, 0, "w0", frame0=(1 << 23) - 1000)
        v_w, (ot_w, _n, _t), _text = run("wrap", image_w, lmd_w, open_load, a.frames_ms)
        cnt = [ot_w[4 * i + 2] for i in range(16)]
        mean_w = [ot_w[4 * i + 1] / cnt[i] if cnt[i] else 0 for i in range(16)]
        top_w = (max(range(8), key=lambda i: mean_w[i]), max(range(8, 16), key=lambda i: mean_w[i]))
        check(f"wrap: {v_w[0]} good records from a frame count of 2^23 - 1000; every slot sampled "
              f"(fewest {min(cnt)}, most {max(cnt)}) and the costs read: heaviest slots {top_w}, "
              f"core 0 sum {sum(mean_w[:8]):.0f} counts",
              v_w[0] > 3000 and min(cnt) >= 100 and max(cnt) - min(cnt) <= 2 * (v_w[0] // 16 + 2)
              and top_w == (1, 9) and sum(mean_w[:8]) > 1000)

    if a.wrap_only:
        wrap_check()
        print(f"verify_load_meter: {'ok' if not FAILS else 'FAILED'} (wrap only)")
        return 1 if FAILS else 0

    # ---- publish, scrub ------------------------------------------------------
    image, lmd = build(a.remix, 0, "b0")
    v, (ot, now, ticks), text = run("open", image, lmd, open_load, a.frames_ms,
                                    ("--watch-mem", f"{MAIN_LO:#x},1;0x20000004,2"))
    seq, bad = v[0], v[1]
    b0, p0, b1, p1 = v[2], v[3], v[4], v[5]
    check(f"publish: good records {seq}, bad {bad}; core 0 busy/period {b0}/{p0}, core 1 {b1}/{p1}",
          seq > 1000 and bad <= seq // 100 + 2 and 20000 <= p0 <= 60000 and 20000 <= p1 <= 60000
          and 0 < b0 <= p0 and 0 < b1 <= p1)
    check(f"screen: both DSP bars carry numbers ({now[1]}, {now[2]}) and the refresh count rises ({ticks})",
          now[1] >= 0 and now[2] >= 0 and ticks >= 2)
    slots = [dict(last=ot[4 * i], sum=ot[4 * i + 1], count=ot[4 * i + 2], max=ot[4 * i + 3]) for i in range(16)]
    mean = [x["sum"] / x["count"] if x["count"] else 0 for x in slots]
    sample = min(x["count"] for x in slots)
    mb = (v[15] / max(v[17], 1), v[16] / max(v[17], 1))
    check(f"otop: every slot has samples (fewest {sample}) and each mean cost is inside its frame",
          sample >= 100 and all(0 <= mean[i] <= (p0 if i < 8 else p1) for i in range(16)))
    sums = (sum(mean[:8]), sum(mean[8:]))
    check(f"otop: the slots' mean costs ({sums[0]:.0f}, {sums[1]:.0f} counts) sum to no more than each core's mean "
          f"busy ({mb[0]:.0f}, {mb[1]:.0f}) plus the timer's 1,024-count step and are not zero",
          sums[0] <= mb[0] + 1024 and sums[1] <= mb[1] + 1024 and sums[0] > 0 and sums[1] > 0)
    top0, top1 = max(range(8), key=lambda i: mean[i]), max(range(8, 16), key=lambda i: mean[i])
    check(f"otop: the heaviest slot of core 0 is T5's FX2 (slot 1, BusVerb) and of core 1 T1's FX2 (slot 9, "
          f"BusDelay)  {top0}, {top1}", (top0, top1) == (1, 9))
    clears = sum(1 for ln in text.splitlines() if f"[{MAIN_LO:#x}]" in ln and "<- 0 " in ln)
    sets = sum(1 for ln in text.splitlines() if f"[{MAIN_LO:#x}]" in ln and "<- 0 " not in ln)
    check(f"scrub: MAIN's long 0 low byte zeroed after landing ({clears} clears, {sets} other writes)",
          clears > 1000)
    check(f"every: lm_scrub's passes {v[13]} against frame interrupts {v[14]}", v[14] > 1000 and abs(v[13] - v[14]) <= 1)
    open_host = host_totals(text, v[14])
    wrap_check()


    # ---- closed: no draws, the same host traffic --------------------------------
    v, _x, text = run("closed", image, lmd, [(0x32, 500)] + into + [(0x20, 500)],
                      a.frames_ms + 500, ("--watch-pc", f"{syms()['draw']:#x}", "--dsp-watch", "0:X:37f28",
                                                   "--watch-mem", "0x20000004,2"))
    range_logs = [text]
    draws = next((int(ln.split(":")[1].split()[0]) for ln in text.splitlines()
                  if ln.startswith("watch-pc") and "hit(s)" in ln), -1)
    check(f"closed: BRAIN's screen draw never runs ({draws} hits) and the DSPs still publish (seq {v[0]})",
          draws == 0 and v[0] > 1000)
    closed_host = host_totals(text, v[14])
    check(f"closed: host commands per frame interrupt match the open run  open {open_host}, closed {closed_host}",
          bool(open_host) and len(open_host) == len(closed_host)
          and all(abs(x - y) <= 0.01 * max(x, 1) for x, y in zip(open_host, closed_host)))

    # ---- calibration: an injected burn raises busy by N/2 counts ----------------
    # A DO loop of N one-cycle nops costs N core cycles plus the DO's own
    # setup (a constant, gone in the difference between burns); timer 0 counts
    # CLK/2, so N cycles are N/2 counts. The port's timer moves in 1,024-count
    # steps (dsp56kEmu timers.cpp: m_timerupdateInterval = 2,048 instructions),
    # so the figure compared is each core's mean busy over the run (lm_dsum),
    # which the frame length (not a multiple of 2,048) dithers.
    busy = {}
    for n in BURNS:
        img_n, lmd_n = (image, lmd) if n == 0 else build(a.remix, n, f"b{n}")
        extra = ("--dsp-watch", "1:X:37f28") if n == BURNS[1] else ()
        v, _x, text_n = run(f"burn{n}", img_n, lmd_n, open_load, a.frames_ms, extra)
        if extra:
            range_logs.append(text_n)
        busy[n] = (v[15] / max(v[17], 1), v[16] / max(v[17], 1))
    for core in (0, 1):
        for n in BURNS[1:]:
            rise = busy[n][core] - busy[0][core]
            want = n / 2
            check(f"calibrate: core {core} mean busy rises by {rise:.0f} counts for a {n}-cycle burn (expected {want:.0f}; "
                  f"error {100 * (rise - want) / want:+.1f}%, within {TOL:.0%})", abs(rise - want) <= TOL * want)

    # ---- range: nothing stock writes the claimed words but B's boot zero --------
    for core, log in enumerate(range_logs):
        writers = []
        on = False
        for ln in log.splitlines():
            if ln.startswith("dsp watch"):
                on = True
                continue
            if on:
                if not ln.startswith(" "):
                    break
                writers.append(ln.strip())
        stray = [w for w in writers if "pc 0x0004" not in w.lower() and "pc=0x4" not in w.lower()
                 and not any(f"{x:x}" in w.lower() for x in (0x49, 0x4a))]
        check(f"range: core {core}'s writers of X:$37F28: {len(writers)}, none but payload B's boot zero loop "
              f"(P:$49/$4a)  {stray[:3]}", not stray)

    # ---- usb: no published byte reaches USB's audio-out ring --------------------
    sym = {}
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    rings = []
    for tag, nopub, noot in (("usb_on", False, False), ("usb_off", True, False), ("usb_noot", False, True)):
        img_u, _l = (image, lmd) if not (nopub or noot) else build(a.remix, 0, tag, nopub=nopub, noot=noot)
        for line in subprocess.run([nm, str(ELF)], capture_output=True, text=True).stdout.splitlines():
            parts = line.split()
            if len(parts) == 3:
                sym[parts[2]] = int(parts[0], 16)
        if "aud_ring" not in sym:
            check("usb: the remix carries USB's audio out (aud_ring)", False)
            break
        card = OUT / f"{tag}.img"
        subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / f"tree_{tag}"), "--out", str(card)], cwd=ROOT, check=True,
                       capture_output=True)
        ring = OUT / f"{tag}_ring.bin"
        log = OUT / f"{tag}.txt"
        with open(log, "w") as fh:
            r = subprocess.run(list(map(str, [EMU, "--image", img_u, "--card", card, "--set", a.set_name,
                                              "--project", a.name, "--sequencer", "--internal-clock",
                                              "--frames", "3000", "--load-ms", "90000", "--dsp",
                                              "--poke", f"{sym['aud_force']:#x}=1",
                                              "--mem-dump", f"{sym['aud_sum']:#x},8192={ring}"])),
                               cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if r.returncode:
            sys.exit(f"verify_load_meter: the {tag} run failed -- {log}")
        rings.append(ring.read_bytes())
    if len(rings) == 3:
        diff = sum(1 for x, y in zip(rings[0], rings[1]) if x != y)
        lows = sum(1 for i in range(3, len(rings[0]), 4) if rings[0][i])
        check(f"usb: USB's audio-out ring byte-identical with the publish on and off ({diff} bytes differ; "
              f"{lows} nonzero low bytes with it on)", diff == 0 and lows == 0)
        diff = sum(1 for x, y in zip(rings[0], rings[2]) if x != y)
        check(f"usb: the ring is byte-identical with OTOP's stamps on and off ({diff} bytes differ)", diff == 0)
    if FAILS:
        print(f"verify_load_meter: FAILED ({len(FAILS)} failure(s)) -- {OUT}")
        return 1
    print(f"verify_load_meter: ok (0 failure(s)) -- {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
