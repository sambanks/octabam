#!/usr/bin/env python3
"""REMOTE's event records under the ColdFire port: a project load, PLAY, STOP and a program change read back over
the vendor request 0xc0/0x5a through tools/hw/ot_events.py, the reader a unit is read with.

    python3 tools/verify/verify_remote.py <remix>

Boots out/mainos_bus.bin on a card with a project (OT_PROJECT or ~/.octabam_project; else a fresh one the
firmware makes, tools/hw/ot_fresh.py), enumerates over the scripted host and checks:

  block      the header's magic; a 256-byte request returns 255 bytes and a 64-byte one 63; an offset at the
             block's end STALLs; the head read over USB equals the cell at RMT_RING + 4
  load       the ring holds the load's record(s): LOADALL, LOADMASK or PRELOAD
  play       PLAY pressed: wait_for returns PLAYING 1; STOP: PLAYING 0. Each wait advances the port 10 ms a poll
             and reports the emulated ms from the key's press
  program    a program change with the sequencer stopped: wait_for returns PATTERN with the program's pattern
  screen     the screen count rises after a key that redraws
  order      record numbers read are consecutive and their seq fields are the numbers' low 16 bits
  peek       PEEK (0xc0/0x58) at RMT_RING returns the header; a peripheral register, flash and the uncached
             view STALL; a read stops at a window's end
  trace      the last 64 frame interrupts read back; every interrupted PC is in SDRAM; the count rises
  file       the card log (/LOG <date>.txt) holds a "RMT seq kind arg stamp" line for each record the load
             flushed, equal to the record read over USB

SKIPs when the remix has no REMOTE or no USB, or the port is not built.
What it cannot see: the unit's timing (the stamps are the port's timer), a host's USB stack, the frame
interrupt's added time on a unit, and a flush at a save (no save is driven here).
"""
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(ROOT / "tools/hw"))
sys.path.insert(0, str(ROOT / "tools/verify"))
import ot_events  # noqa: E402
import usb_host  # noqa: E402  (tools/harness)
import emu_card  # noqa: E402  (tools/emu)
from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
ELF = ROOT / "out/platform/runtime/runtime.elf"
OUT = ROOT / "out/rmt_gate"
PY = ROOT / ".venv/bin/python3"


def symbol(name):
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    for line in subprocess.run([nm, str(ELF)], capture_output=True, text=True).stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == name:
            return int(parts[0], 16)
    raise RuntimeError(f"{name} not in {ELF}")


def project():
    """-> (directory, name): the user's project, else a fresh one made under the port."""
    p = os.environ.get("OT_PROJECT", "")
    f = pathlib.Path.home() / ".octabam_project"
    if not p and f.exists():
        p = f.read_text().strip()
    if p and pathlib.Path(p).is_dir():
        return pathlib.Path(p)
    r = subprocess.run([str(PY if PY.exists() else sys.executable), str(ROOT / "tools/hw/ot_fresh.py"),
                        "--image", str(IMAGE), "--out", str(OUT / "fresh")], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_remote: ot_fresh failed:\n{(r.stdout + r.stderr)[-800:]}")
    return OUT / "fresh/image/NOPROJ"


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    if not EMU.is_file():
        print("  [SKIP] verify_remote: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_remote: no out/mainos_bus.bin (make bus)")
        return 1
    mods = registry.remix(remix).modules
    if "REMOTE" not in mods or "USB" not in mods:
        print("  [SKIP] verify_remote: the remix has no REMOTE or no USB")
        return 0
    from stems_panel import MenuPort

    OUT.mkdir(parents=True, exist_ok=True)
    src = project()
    card, tree = OUT / "card.img", OUT / "tree"
    if tree.exists():
        shutil.rmtree(tree)
    card.unlink(missing_ok=True)
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(src), "OCTABAM", "RMTT",
                        "--tree", str(tree), "--out", str(card), "--image-mb", "64"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_remote: stage_card failed:\n{(r.stdout + r.stderr)[-800:]}")
    sock = f"/tmp/ot-remote-{os.getpid()}.sock"
    fails = []

    def check(what, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + detail if detail else ''}")
        if not ok:
            fails.append(what)

    p = MenuPort(IMAGE, card, "OCTABAM", "RMTT", mkii=True, log_path=OUT / "port.txt",
                 extra=["--usb-host", sock, "--load-ms", "90000"])
    ms = [0]

    def run(n):
        p.run(n)
        ms[0] += n

    def serve(fn):
        """A bench call on a thread while the port runs."""
        out = {}

        def t():
            try:
                out["v"] = fn()
            except Exception as e:  # noqa: BLE001
                out["e"] = e
        th = threading.Thread(target=t)
        th.start()
        while th.is_alive():
            run(10)
            th.join(0.01)
        if "e" in out:
            raise out["e"]
        return out["v"]

    b = None
    try:
        p.settle()
        res = {}

        def bench():
            res["b"] = usb_host.Bench(sock, timeout=60.0)
            usb_host.enumerate_device(res["b"], hs=True)
        serve(bench)
        b = res["b"]

        def ctrl(off, n):
            return bytes(serve(lambda: b.ctrl_in(0xc0, 0x5a, off, 0, n)))

        hdr = ctrl(0, 32)
        check("the header's magic is RMT1", hdr[:4] == ot_events.MAGIC, hdr[:4].hex())
        lens = {n: len(ctrl(32, n)) for n in (256, 64, 100)}
        check("a reply is at most 255 bytes and never a multiple of 64", lens == {256: 255, 64: 63, 100: 100}, str(lens))
        try:
            ctrl(ot_events.BYTES, 4)
            check("an offset at the block's end STALLs", False, "a reply came back")
        except Exception as e:  # noqa: BLE001
            check("an offset at the block's end STALLs", True, type(e).__name__)

        ev = ot_events.Events(ctrl, from_start=True)
        head = ev.head()
        cell = p.long(symbol("RMT_RING") + 4)
        check("the head over USB is the cell at RMT_RING + 4", 0 <= cell - head <= 4, f"usb {head}, dram {cell}")
        recs = ev.poll()
        loads = [r for r in recs if r["name"] in ("LOADALL", "LOADMASK", "PRELOAD")]
        check("the ring holds the load's record(s)", bool(loads), str([(r["name"], r["arg"]) for r in recs]))

        tick = lambda: run(10)                                        # noqa: E731

        def timed(what, kind, arg, act):
            t0 = ms[0]
            act()
            try:
                r = ev.wait_for(kind, arg, timeout=60.0, tick=tick)
                recs.append(r)
                recs.extend(r["passed"])
                check(f"{what}: {kind} {arg} after {ms[0] - t0} emulated ms", True)
            except TimeoutError as e:
                check(f"{what}: {kind} {arg}", False, str(e))

        def press(name):
            p.key(name, True)
            run(40)
            p.key(name, False)

        timed("PLAY", "PLAYING", 1, lambda: press("play"))
        timed("STOP", "PLAYING", 0, lambda: press("stop"))
        timed("program change 1, stopped", "PATTERN", 1, lambda: p.proc.command("midi c0 01", "ok"))

        s0 = ev.header()[1]
        press("pg_fx1")
        try:
            s1 = ev.wait_screen(s0, timeout=30.0, tick=tick)
            check(f"the screen count rises after a page key: {s0} -> {s1}", True)
        except TimeoutError as e:
            check("the screen count rises after a page key", False, str(e))

        recs.extend(ev.poll())
        ns = sorted({r["n"] for r in recs})
        check(f"{len(ns)} records read, consecutive, none lost",
              ns == list(range(ns[0], ns[0] + len(ns))) and ev.lost == 0, f"lost {ev.lost}")

        def peek1(addr, n):
            return bytes(serve(lambda: b.ctrl_in(0xc0, 0x58, addr >> 16, addr & 0xffff, n)))

        ring = symbol("RMT_RING")
        check("PEEK at RMT_RING returns the header's magic and RMT_TRACE's address",
              ot_events.peek(peek1, ring, 4) == ot_events.MAGIC
              and struct.unpack(">I", ot_events.peek(peek1, ring + 16, 4))[0] == symbol("RMT_TRACE"))
        for addr, what in ((0xfc07c00c, "a peripheral register"), (0x00000400, "flash"), (0x48000000, "the uncached view")):
            try:
                peek1(addr, 4)
                check(f"PEEK of {what} ({addr:#x}) STALLs", False, "a reply came back")
            except Exception as e:  # noqa: BLE001
                check(f"PEEK of {what} ({addr:#x}) STALLs", True, type(e).__name__)
        check("PEEK stops at a window's end: 2 bytes back for 8 asked at 0x80007ffe", len(peek1(0x80007ffe, 8)) == 2)
        tr = ot_events.trace(ctrl, peek1, last=64)
        ok = len(tr) >= 48 and all(0x40000400 <= pc < 0x48000000 for _n, pc, _t in tr)
        gaps = [(tr[i + 1][2] - tr[i][2]) & 0xffffffff for i in range(len(tr) - 1) if tr[i + 1][0] == tr[i][0] + 1]
        check(f"the trace: {len(tr)} of the last 64 frame interrupts, every interrupted PC in SDRAM; entry gaps "
              f"{min(gaps, default=0)}..{max(gaps, default=0)} timer counts",
              ok and bool(gaps), f"pcs {sorted({hex(pc) for _n, pc, _t in tr})[:6]}")
        run(200)
        check("the trace's count rises", ot_events.trace(ctrl, peek1, last=1)[-1][0] > tr[-1][0])

        p.card_flush()
        files = emu_card.extract_image(card.read_bytes())
        lines = [ln.split("RMT ", 1)[1].split() for k, v in files.items() if "LOG" in k.upper()
                 for ln in v.decode("latin1").splitlines() if " RMT " in ln]
        logged = {int(x[0]): (int(x[1]), int(x[2]), int(x[3]) & 0xffffffff) for x in lines if len(x) == 4}
        by_n = {r["n"] & 0xffff: (r["kind"], r["arg"], r["stamp"]) for r in recs}
        want = {n: v for n, v in by_n.items() if n <= max((r["n"] for r in loads), default=-1)}
        check(f"the card log holds the {len(want)} record(s) up to the load's last, as read over USB",
              bool(want) and all(logged.get(n) == v for n, v in want.items()), f"log {logged}, usb {want}")
    except Exception as e:  # noqa: BLE001 -- a hang or a stall is the finding
        check(f"the run completed ({type(e).__name__}: {e})", False)
    finally:
        if b is not None:
            b.sock.close()
        p.__exit__()
    print(f"verify_remote: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
