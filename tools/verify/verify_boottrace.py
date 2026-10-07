#!/usr/bin/env python3
"""BOOT TRACE under the port: a normal MKII boot sends notes 1..6 in order.

    python3 tools/verify/verify_boottrace.py os-switch-trace

Boots the remix (NOR's bootstrap version preloaded, so the entry takes the
hardware's path) and watches the trace routine's entry: the note it is
called with, in order, must be 2..6 then the frame interrupt's 7 and 8
(the port takes frames with --frame; 6 and the first frame race), and OS SWITCH's inline note 1 (when
it is in the image) must run first. The port arms its UART write watch only
after the boot, so the notes are read from the calls, not the wire; notes
4..6 were also seen on UART0's transmit register (29 Sep 2026).
"""
import os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"


def nm(elf):
    out = subprocess.run(["m68k-elf-nm", str(elf)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    mods = registry.remix(remix).modules
    # DSP RESET PROBE wedges the DSP by design: its control pass sends the
    # boot ROM's protocol into a running payload, whose frame protocol never
    # gets back in step, and the boot does not finish (measured on an MKII,
    # 29 Sep 2026, docs/contributing/FAILURE_MODES.md). A gate that asserts a
    # normal boot cannot be run on that image.
    if "DSP RESET PROBE" in mods:
        print(f"  [SKIP] verify_boottrace: {remix} carries DSP RESET PROBE, which stops the "
              f"boot on purpose")
        return 0
    if "BOOT TRACE" not in mods:
        print(f"  [SKIP] verify_boottrace: {remix} does not carry BOOT TRACE")
        return 0
    if not EMU.exists():
        print("  [SKIP] verify_boottrace: the ColdFire port is not built (make emu-cf)")
        return 0
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_boottrace: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    trace = nm(ROOT / "out/linked/boot-trace/boot_trace/u.elf")["tracev"]
    watch = [trace]
    chain = None
    if "OS SWITCH" in mods:
        chain = nm(ROOT / "out/platform/loader.elf")["txmidi"]
        watch.append(chain)
    work = pathlib.Path(tempfile.mkdtemp(prefix="boottrace."))
    ver = work / "norver.bin"
    stock = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()
    ver.write_bytes(stock[0xDE648:0xDE64A])
    out = subprocess.run([str(EMU), "--image", str(ROOT / "out/mainos_bus.bin"), "--mkii", "--dsp",
                          "--preload", f"0x3ffc={ver}", "--max", "150000000", "--frame", "--frames", "20",
                          "--watch-pc", ",".join(f"0x{a:x}" for a in watch)],
                         capture_output=True, text=True, cwd=ROOT).stdout
    seq, chain_bytes = [], 0
    for m in re.finditer(r"^\s*\[\s*\d+\] at 0x([0-9a-f]+) d0=(0x[0-9a-f]+|0) d1=(0x[0-9a-f]+|0)", out, re.M):
        a, d0, d1 = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)
        if a == trace:
            seq.append((d0 & 0xFF, d1 & 0x7F))
        elif a == chain:
            chain_bytes += 1
    notes = [n for n, _ in seq]
    want = [9, 2, 3, 4, 5, 6, 7, 8]
    ups = [(n, v) for n, v in seq if n in (14, 15)]
    echoes = [(n, v) for n, v in seq if n in (17, 18, 19)]
    notes = [n for n in notes if n not in (14, 15, 16, 17, 18, 19)]
    ok = (sorted(notes) == sorted(want) and notes[:5] == want[:5] and "HANDOFF" in out
          and ups == [(14, 0), (15, 0), (14, 1), (15, 1)]
          and [v for n, v in echoes if n == 18] == [3, 3] and not [1 for n, v in echoes if n == 19]
          and dict(seq).get(9) == 22 and 10 not in notes and 11 not in notes
          and chain_bytes == (6 if chain else 0))
    print(f"  [{'PASS' if ok else 'FAIL'}] verify_boottrace: a normal MKII boot sends notes "
          f"{'1, 12 (the chainloader), ' if chain else ''}{want}, clock 22, never 10/11, "
          f"uploads 14/15 on core 0 then core 1, final echoes 18 = 3, 3  "
          f"(saw {seq}, {chain_bytes} chainloader byte(s))")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
