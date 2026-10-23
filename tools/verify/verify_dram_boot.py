#!/usr/bin/env python3
"""Boot the image just built under the ColdFire port and check that every
DRAM payload octabam's loader carries actually lands.

For the current REMIX (the image at out/mainos_bus.bin):
  * the boot reaches the RTOS handoff, and the loader's entry ran exactly
    once while its `fatal` hang never did -- so every hash gate passed;
  * the octabam window (out/platform/runtime/runtime.bin, when the remix
    has DRAM units) reads back equal to the linked runtime -- except for
    bytes the runtime itself writes once it runs, which are counted and
    printed, not hidden. Known cases: midi-scenes' state words; PLOCKS P2's
    INITED sentinel, stamped with MAGIC ('PLK2') by plk_init the first time
    it runs before handoff; BRAIN's brain_ts/brain_ts_last per-task CPU
    table, written by brain_sched (the scheduler hook) on every task
    switch from very early in boot, so a BRAIN-carrying remix always shows
    some of these -- it is not a one-time stamp, and a boot that reaches
    handoff later or schedules differently changes the count a little;
    USB AUDIO IN's six config words and per-speed descriptor pointers
    (usb_trk..usb_hs_step in usbaudio's data, 26 B): the boot config code
    applies the setting defaults (MAIN/CUE/MIDI on, MASTER/INPUTS off), the
    interface numbers, the four cfg_sel pointers into the descriptor blobs
    it builds in a bank buffer, and the audio geometry (frame bytes, HS
    capability/step) before handoff.

SKIPs when the port is not built (`make emu-cf`) or the remix carries no
DRAM payload. What this cannot see: caches (the port has none), the
recorder, and anything after the handoff.
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import platform_build, registry  # noqa: E402
from boot_mutable import resolve_ranges, compare_runtime  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
remix = registry.remix(os.environ.get("REMIX"))
mods = registry.selected(remix)
dram = any(u.dram for m in mods for u in getattr(m, "linked", ()))
if not dram:
    print(f"  [ -- ] verify_dram_boot: {remix.name} carries no DRAM payload")
    sys.exit(0)
if not EMU.exists():
    print("  [SKIP] verify_dram_boot: the ColdFire port is not built (make emu-cf)")
    sys.exit(0)

# Build THIS remix's image first: `make verify` runs after the remix
# self-test, which builds every remix in turn and leaves the last one at
# out/mainos_bus.bin (and its loader at out/platform/). The first run of
# this check booted `warped` while looking for midi-scenes' loader and
# reported it never ran.
env = dict(os.environ, REMIX=remix.name, XBUS="1", SPEC="1")
env.setdefault("BUILD", "0")
r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                   capture_output=True, text=True, cwd=ROOT)
if r.returncode:
    sys.exit(f"verify_dram_boot: building {remix.name} failed:\n{(r.stdout + r.stderr)[-1500:]}")

nm = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/loader.elf")],
                    capture_output=True, text=True).stdout
syms = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
entry, fatal = syms["octabam_bootstrap"], syms["fatal"]

dumps, expects = [], []
if dram:
    import json
    layout = json.loads((ROOT / "out/platform" / platform_build.LAYOUT).read_text())
    raw = (ROOT / "out/platform/runtime/runtime.bin").read_bytes()
    dumps.append((layout["base"], len(raw), ROOT / "out/_dump_octabam.bin"))
    expects.append(("octabam reserve", raw))

args = [str(EMU), "--image", str(IMAGE), "--max", "80000000",
        "--watch-pc", f"0x{entry:x},0x{fatal:x}",
        "--mem-dump", ";".join(f"0x{a:x},{n}={p}" for a, n, p in dumps)]
r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
out = r.stdout
handoff = "HANDOFF" in out
hits = [l for l in out.splitlines() if l.strip().startswith("[") and " at 0x" in l]
entry_hits = sum(1 for l in hits if f"at 0x{entry:x}" in l)
fatal_hits = sum(1 for l in hits if f"at 0x{fatal:x}" in l)
ok = handoff and entry_hits == 1 and fatal_hits == 0
print(f"  [{'PASS' if ok else 'FAIL'}] verify_dram_boot: {remix.name} boots to the handoff; "
      f"loader ran {entry_hits}x, its fatal hang {fatal_hits}x")
# Modules own their mutable-state declarations; this gate only verifies
# their linked extent/initial contents and accounts for changes at handoff.
try:
    mutable_ranges = resolve_ranges(mods, layout, ROOT / "out/platform/runtime", raw)
except ValueError as error:
    sys.exit(f"[FAIL] verify_dram_boot: {error}")

for (a, n, p), (label, raw) in zip(dumps, expects):
    got = p.read_bytes() if p.exists() else b""
    diff = [i for i in range(min(len(got), len(raw))) if got[i] != raw[i]]
    # 14 Oct 2026: the official remixes (octabam-bus/-core/-inserts) carry
    # BRAIN and PLOCKS P2 through this gate for the first time and measured
    # 41-42 (brain_ts/brain_ts_last plus PLOCKS P2's INITED stamp, see the
    # module docstring above); 64 keeps headroom without going blind to a
    # new undeclared writer.
    fine, transient, remaining = compare_runtime(a, raw, got, mutable_ranges)
    ok &= fine
    changes = (f"{transient} declared mutable byte(s) and {remaining} other byte(s)"
               if mutable_ranges else f"{len(diff)} byte(s)")
    print(f"  [{'PASS' if fine else 'FAIL'}] verify_dram_boot: {label} at 0x{a:08x} == linked "
          f"runtime ({n:,} B) except {changes} the runtime wrote itself"
          + (f" at +{diff[0]:#x}.." if diff else ""))
sys.exit(0 if ok else 1)
