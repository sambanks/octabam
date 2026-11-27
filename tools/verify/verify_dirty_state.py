#!/usr/bin/env python3
"""A module started from a GARBAGE instance block must be silent on silence.

The unit's X RAM holds whatever the effect before ours left in the block;
the port and dsp_host boot zeroed RAM, so a persistent slot that init does
not clear is a defect no local render can see. Found on the
master: Spectrum's filter B keeps its two HP poles at cHP = 0 FROZEN, so a
stale h2 was subtracted from every sample forever -- a DC offset of up to
full scale on a station's output, invisible in an AC-coupled capture, that
the master compressor's makeup clipped on one channel ("R collapses above
COMP 40"; docs/contributing/FAILURE_MODES.md).

    python3 tools/verify/verify_dirty_state.py [remix] [--image out/mainos_bus.bin]

For every DSP module of the remix with an entry in the dispatch tables:
render it under dsp_host with the instance block X:(r7+$00..$ff) pre-filled
with each of four garbage words, on silence, at its defaults and with every
knob nudged off its default (the live paths), 100 blocks of 15 frames; the
last 300 output samples must sit below -100 dBFS. A module whose render from a
ZEROED block is itself not silent at those knobs (CF METER prints its page-2
words) makes its output from the knobs: each garbage render must then equal
the zeroed one sample for sample. A server's lines live in
Y and are not filled here (they carry their own tagged counters; dsp_host's
-dirty covers Y).
"""
import os
import argparse, pathlib, struct, subprocess, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe
from remix import registry
from remix.schema import render_slot

ROOT = pathlib.Path(__file__).resolve().parents[2]
HOST = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host"
# A remix with a hook at the per-track source seam (OCTA303 SEAM, A P:0x39c / B P:0x1a2) has a jsr where dsp_host
# looks for the frame setup's last word (`move a,x:>$20e`), so it cannot find it: stop the setup just before the
# seam, as tools/harness/verify_analog_bd_reverbs.py does (this gate calls the effects directly).  Set in main().
SEAM_CTX = []
FRAMES, BLOCKS, TAIL = 15, 100, 300
FLOOR_DB = -100.0
FILLS = (0x7fffff, 0x800000, 0x400000, 0x5a5a5a)
# The state block each module renders at: schema.render_slot -- track 1 FX2 (dsp_host -r7 2, 0x6200)
# by default; SEND's FX1 slots (0x6100, 0x6400, 0x6700, 0x6a00) return before touching state; a
# module that runs at some positions only names one it runs at (Harness.render_r7; VOCODER 0x6500).
R7 = 2


def mem_with_fill(base: pathlib.Path, fill: int, out: pathlib.Path, r7: int = R7) -> pathlib.Path:
    blob = base.read_bytes(); body, term = blob[:-9], blob[-9:]
    assert term[0] == 0xff, "not a .mem dump"
    run = struct.pack("<BII", 1, 0x6000 + 0x100 * r7, 0x100) + struct.pack("<I", fill) * 0x100
    out.write_bytes(body + run + term); return out


def render(mem: pathlib.Path, init: int, proc: int, params, tmp: pathlib.Path, slot=(R7, 1)):
    n = FRAMES * BLOCKS
    src = tmp / "in.raw"; src.write_bytes(b"\0" * (8 * n)); out = tmp / "out.raw"
    cmd = [str(HOST), "-mem", str(mem), "-init", f"{init:x}", "-proc", f"{proc:x}", "-inst", "1", "-r7", str(slot[0]),
           "-alloc", str(slot[1]), "-inmask", "1", "-stereo", "-frames", str(FRAMES), "-blocks", str(BLOCKS),
           "-in", str(src), "-out", str(out), "-params", ",".join(str(x) for x in params)]
    cmd += SEAM_CTX
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        return None, (r.stdout + r.stderr)[-400:]
    d = out.read_bytes(); w = struct.unpack(f"<{len(d)//4}i", d)
    return (list(w[0::2])[:n], list(w[1::2])[:n]), ""


def db(x): return 20 * __import__("math").log10(max(abs(x), 1) / 8388607)


def knob_sets(mod):
    defaults = [(p.default or 0) for p in mod.params]
    yield "defaults", defaults
    nudged = []
    for p, d in zip(mod.params, defaults):
        count = getattr(p, "count", None) or 128
        nudged.append(d + 1 if d + 1 < count else d - 1)
    yield "every knob nudged", nudged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--image", default=None,
                    help="an image to read as it is; without it the remix is built first")
    a = ap.parse_args()
    remix = registry.remix(a.remix); mods = registry.bound(remix)     # the remix's own ids
    if a.image is None:
        # out/mainos_bus.bin is whatever built last (the selftest and
        # verify_character leave their own); build this remix's.
        env = dict(os.environ, REMIX=remix.name, XBUS="1", SPEC="1")
        env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_dirty_state: building {remix.name} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        a.image = str(ROOT / "out/mainos_bus.bin")
    seam = any(hasattr(h.site, "get") and h.site.get("A") == 0x39C for m in mods.values()
               for h in (getattr(getattr(m, "dsp", None), "hooks", None) or ()))
    if seam:
        SEAM_CTX[:] = ["-ctx", "372,39b,53e", "-ctxB", "17a,1a1,333"]
        print("the source seam carries a hook: dsp_host's frame setup stops before it (-ctx 372,39b,53e / -ctxB 17a,1a1,333)")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="dirtystate_"))
    mems = {pl: send_probe.dump_mem(a.image, tmp / f"payload_{pl}.mem", pl) for pl in "AB"}
    send_id = registry.by_name("send").menu.fx2_id
    send_ep = {pl: send_probe.entry_points(mems[pl], send_id) for pl in "AB"}
    fails = 0; checked = 0
    for key in remix.modules:
        mod = mods.get(key)
        dsp = getattr(mod, "dsp", None)
        if not dsp or not getattr(dsp, "asm", None) or not getattr(mod, "menu", None):
            continue
        fxid = mod.menu.fx2_id
        # the payload the module is placed on: A unless its id aliases SEND there
        pl = "A"
        ep = send_probe.entry_points(mems[pl], fxid)
        if ep == send_ep[pl] and fxid != send_id:
            pl = "B"; ep = send_probe.entry_points(mems[pl], fxid)
            if ep == send_ep[pl]:
                fails += 1
                print(f"[FAIL] {mod.name:14s} not placed on either payload"); continue
        init, proc = ep
        slot = render_slot(mod)
        for label, params in knob_sets(mod):
            worst = None
            ref, err = render(mem_with_fill(mems[pl], 0, tmp / f"{key}_zero.mem", slot[0]), init, proc, params, tmp, slot)
            if ref is not None and db(max(max(abs(x) for x in ref[0][-TAIL:]), max(abs(x) for x in ref[1][-TAIL:]))) > FLOOR_DB:
                bad = 0
                for fill in FILLS:
                    res, err = render(mem_with_fill(mems[pl], fill, tmp / f"{key}_{fill:06x}.mem", slot[0]), init, proc, params, tmp, slot)
                    checked += 1
                    if res != ref:
                        fails += 1; bad += 1
                        print(f"FAIL {mod.name:14s} {label:20s} fill {fill:06x}: output differs from the zeroed block's "
                              f"-- a slot init does not clear is feeding the output")
                if not bad:
                    print(f"OK   {mod.name:14s} {label:20s} payload {pl}: not silent from a zeroed block (output from the knobs); "
                          f"all {len(FILLS)} garbage fills equal it")
                continue
            for fill in FILLS:
                mem = mem_with_fill(mems[pl], fill, tmp / f"{key}_{fill:06x}.mem", slot[0])
                res, err = render(mem, init, proc, params, tmp, slot)
                checked += 1
                if res is None:
                    fails += 1; print(f"FAIL {mod.name:14s} {label:20s} fill {fill:06x}: dsp_host failed: {err.strip()[-160:]}"); continue
                L, R = res
                tail = max(max(abs(x) for x in L[-TAIL:]), max(abs(x) for x in R[-TAIL:]))
                peak = max(max(abs(x) for x in L), max(abs(x) for x in R))
                if worst is None or tail > worst[0]:
                    worst = (tail, peak, fill)
                if db(tail) > FLOOR_DB:
                    fails += 1
                    print(f"FAIL {mod.name:14s} {label:20s} fill {fill:06x}: tail {db(tail):6.1f} dBFS (peak {db(peak):6.1f}) -- "
                          f"a slot init does not clear is feeding the output")
            if worst is not None and db(worst[0]) <= FLOOR_DB:
                print(f"OK   {mod.name:14s} {label:20s} payload {pl}: tail {db(worst[0]):7.1f} dBFS, transient peak {db(worst[1]):7.1f} dBFS (worst fill {worst[2]:06x})")
    print(f"\nverify_dirtystate: {checked} renders, {fails} failed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
