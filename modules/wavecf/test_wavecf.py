#!/usr/bin/env python3
"""WAVE's engine (modules/wavecf/engine.c): the Python model, the host build and the ColdFire build
under Unicorn agree sample for sample on one command stream, and the sound is what it should be.

    python3 modules/wavecf/test_wavecf.py

Needs m68k-elf-gcc / -objcopy / -nm / -objdump, a host cc and .venv/lib/unicorn-emac (make setup)."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import ref_wavecf as R  # noqa: E402
import tables  # noqa: E402

FAILS = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def be32(path):
    d = pathlib.Path(path).read_bytes()
    return [int.from_bytes(d[i:i + 4], "big", signed=True) for i in range(0, len(d), 4)]


def main():
    check(tables.text() == (HERE / "tables.s").read_text() and tables.text_c() == (HERE / "wcf_data.c").read_text(),
          "tables.s and wcf_data.c are what tables.py makes")
    with tempfile.TemporaryDirectory(prefix="wavecf-") as td:
        td = pathlib.Path(td)
        SRC = [str(HERE / f) for f in ("engine.c", "wcf.c", "wcf_data.c")]
        tb = b"".join((s & 0xffff).to_bytes(2, "big") for f in tables.frames() for s in f)
        (td / "table.bin").write_bytes(tb)
        cc = shutil.which("cc") or "cc"
        subprocess.run([cc, "-O2", "-I", str(HERE), "-o", str(td / "drive"), str(HERE / "harness/drive.c"), *SRC], check=True)
        (td / "link.ld").write_text("SECTIONS { . = 0x10000; .text : { *(.text*) *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } }\n")
        objs = []
        for src in SRC:
            o = td / (pathlib.Path(src).stem + ".o")
            subprocess.run(["m68k-elf-gcc", "-mcpu=54455", "-O2", "-fomit-frame-pointer", "-ffreestanding", "-fno-builtin", "-nostdlib",
                            "-I", str(HERE), "-c", src, "-o", str(o)], check=True)
            objs.append(str(o))
        subprocess.run(["m68k-elf-gcc", "-mcpu=54455", "-nostdlib", "-T", str(td / "link.ld"), *objs, "-o", str(td / "engine.elf")], check=True)
        subprocess.run(["m68k-elf-objcopy", "-O", "binary", str(td / "engine.elf"), str(td / "engine.bin")], check=True)
        py = ROOT / ".venv/bin/python"
        for name, blocks in (("engine", R.scenario()), ("note", R.scenario_note())):
            R.write_stream(td / "cmds.bin", blocks)
            model = R.run(blocks)
            subprocess.run([str(td / "drive"), str(td / "cmds.bin"), str(td / "table.bin"), str(td / "host.i32")], check=True)
            check(be32(td / "host.i32") == model, f"{name} stream: host build == Python model ({len(model)} samples)")
            r = subprocess.run([str(py), "-I", str(HERE / "harness/run_cf.py"), str(td / "engine.elf"), str(td / "engine.bin"),
                                str(td / "table.bin"), str(td / "cmds.bin"), str(td / "cf.i32")], capture_output=True, text=True)
            print("   " + (r.stdout.strip() or r.stderr.strip()[-300:]))
            cf = be32(td / "cf.i32") if (td / "cf.i32").exists() else []
            check(cf == model, f"{name} stream: ColdFire build under Unicorn == Python model")

        # the sound: one voice on the sine frame at 440 Hz is a 440 Hz sine, at the gain it was given
        import numpy as np
        e = R.Engine()
        e.cmd(3, R.q31(1 - np.exp(-1 / (0.004 * R.SR))), R.q31(1 - np.exp(-1 / (0.05 * R.SR))), 0)
        e.cmd(1, 0, R.inc_of(440.0), R.q31(0.2))
        x = np.array(e.render(R.SR), dtype=np.float64)[R.SR // 4:] / (1 << 27)
        spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        peak = np.argmax(spec) * R.SR / len(x)
        amp = np.max(np.abs(x))
        check(abs(peak - 440.0) < 2.0, f"a voice on frame 0 is a sine at 440 Hz (peak {peak:.1f} Hz)")
        want = 0.2 * tables.AMP
        check(abs(amp - want) < 0.003, f"its level is gain x table amplitude ({amp:.4f}, want {want:.4f})")
        e2 = R.Engine()
        e2.cmd(3, R.q31(1 - np.exp(-1 / (0.004 * R.SR))), R.q31(1 - np.exp(-1 / (0.05 * R.SR))), 0)
        e2.cmd(1, 0, R.inc_of(440.0), R.q31(0.2)); e2.cmd(0, 3 << 16, 0, 0)
        y = np.array(e2.render(R.SR), dtype=np.float64)[R.SR // 2:] / (1 << 27)
        check(abs(np.max(np.abs(y)) - want) < 0.004 and np.mean(np.abs(y)) > 0.8 * want, "frame 3 is the square: its level is the table amplitude")
        e3 = R.Engine()
        e3.cmd(3, R.q31(1 - np.exp(-1 / (0.004 * R.SR))), R.q31(1 - np.exp(-1 / (0.05 * R.SR))), 0)
        e3.cmd(1, 0, R.inc_of(440.0), R.q31(0.2)); e3.render(2000); e3.cmd(2, 0, 0, 0)
        z = np.array(e3.render(R.SR // 2), dtype=np.float64)
        check(z[-100:].max() == 0 and z[-100:].min() == 0, "a released voice ends in exact zero")
    # the note layer
    worst = 0.0
    for p in range(-48 * 256, 48 * 256 + 1, 13):
        hz = tables.BASE_HZ * 2.0 ** (p / 256.0 / 12.0)
        got = R.inc_of_p(p) / 4294967296.0 * R.SR
        worst = max(worst, abs(1200 * __import__("math").log2(got / hz)))
    check(worst < 0.5, f"wcf_inc is within {worst:.3f} cents of 2^(p/12) from C3 across -48..+48 semitones")
    check(abs(R.inc_of_p(0) - R.inc_of(tables.BASE_HZ)) <= 1 and R.inc_of_p(12 * 256) == 2 * R.inc_of_p(0), "TUNE 0 is C3 and +12 semitones doubles the increment")
    e = R.Engine()
    e.note(0, 3, 3)
    incs = [e.v[v]["inc"] for v in range(4)]
    want = [R.inc_of_p(256 * d) for d in tables.CHORDS[3][:3]]
    check(incs[:3] == want and e.v[3]["gate"] == 0 and all(e.v[v]["gate"] for v in range(3)), "CHRD 3 with VOIC 3 gates the first three chord notes and no fourth")
    print("FAIL" if FAILS else "ALL PASS")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
