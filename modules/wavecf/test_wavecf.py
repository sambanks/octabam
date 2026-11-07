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


def E():
    """A model engine with its AMP open (the machine's opens with wcf_amp once a frame; these tests call the engine directly)."""
    e = R.Engine()
    e.amp_cur = e.amp_tgt = 1 << 30
    e.amp_on = 1
    return e


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
        for name, blocks in (("engine", R.with_amp(R.scenario())), ("note", R.with_amp(R.scenario_note())),
                             ("amp", R.scenario_amp())):
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
        e = E()
        e.cmd(3, R.q31(1 - np.exp(-1 / (0.004 * R.SR))), R.q31(1 - np.exp(-1 / (0.05 * R.SR))), 0)
        e.cmd(1, 0, R.inc_of(440.0), R.q31(0.2))
        x = np.array(e.render(R.SR), dtype=np.float64)[R.SR // 4:] / (1 << 27)
        spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        peak = np.argmax(spec) * R.SR / len(x)
        amp = np.max(np.abs(x))
        check(abs(peak - 440.0) < 2.0, f"a voice on frame 0 is a sine at 440 Hz (peak {peak:.1f} Hz)")
        want = 0.2 * tables.AMP
        check(abs(amp - want) < 0.003, f"its level is gain x table amplitude ({amp:.4f}, want {want:.4f})")
        e2 = E()
        e2.cmd(3, R.q31(1 - np.exp(-1 / (0.004 * R.SR))), R.q31(1 - np.exp(-1 / (0.05 * R.SR))), 0)
        e2.cmd(1, 0, R.inc_of(440.0), R.q31(0.2)); e2.cmd(0, 3 << 16, 0, 0)
        y = np.array(e2.render(R.SR), dtype=np.float64)[R.SR // 2:] / (1 << 27)
        check(abs(np.max(np.abs(y)) - want) < 0.004 and np.mean(np.abs(y)) > 0.8 * want, "frame 3 is the square: its level is the table amplitude")
        e3 = E()
        e3.cmd(3, R.q31(1 - np.exp(-1 / (0.004 * R.SR))), R.q31(1 - np.exp(-1 / (0.05 * R.SR))), 0)
        e3.cmd(1, 0, R.inc_of(440.0), R.q31(0.2)); e3.render(2000); e3.cmd(2, 0, 0, 0)
        z = np.array(e3.render(R.SR // 2), dtype=np.float64)
        check(z[-100:].max() == 0 and z[-100:].min() == 0, "a released voice ends in exact zero")
    # the AMP envelope (the DSP's laws, Tim Hastie's measurements): attack, hold, release, and no step at a START
    def amp_frame(e, atk, hold, rel, start=0):
        e.cmd(8, atk | hold << 8 | rel << 16 | start << 24, 0, 0)
        e.render(16)                                                    # the call that ramps to the new level

    e = R.Engine()
    amp_frame(e, 0, 127, 127, 1)
    frames = 1
    while e.amp_tgt < (1 << 30) and frames < 100:
        amp_frame(e, 0, 127, 127)
        frames += 1
    check(frames == 16, f"AMP ATK 0 reaches full in 16 frames ({frames}): the DSP's floor of 5.8 ms")
    e = R.Engine()
    amp_frame(e, 70, 127, 127, 1)
    f70 = 1
    while e.amp_tgt < (1 << 30) and f70 < 100000:
        amp_frame(e, 70, 127, 127)
        f70 += 1
    check(abs(f70 * 16 / R.SR - 3.85e-3 * 2 ** (70 / 8.53)) / (3.85e-3 * 2 ** (70 / 8.53)) < 0.1, f"AMP ATK 70 ramps in {f70 * 16 / R.SR:.2f} s (the DSP's law: {3.85e-3 * 2 ** (70 / 8.53):.2f} s)")
    e = E()
    e.fps = 345
    amp_frame(e, 0, 32, 60, 1)
    held = 1
    while e.amp_tgt >= (1 << 30) and held < 5000:
        amp_frame(e, 0, 32, 60)
        held += 1
    want = (R._AMP_HOLD[32] * 345 >> 7) + 1
    check(held == want, f"AMP HOLD 32 holds {held} frames at 345 a step (the table says {want}): about {held * 16 / R.SR * 1000:.0f} ms")
    for _ in range(4000):
        amp_frame(e, 0, 32, 60)
    check(e.amp_tgt == 0, "AMP REL 60 releases to silence after the hold")
    e = E()
    amp_frame(e, 0, 32, 127, 1)
    for _ in range(3000):
        amp_frame(e, 0, 32, 127)
    check(e.amp_tgt == (1 << 30), "AMP REL 127 (INF) holds the level after HOLD")
    # a START on a sounding track continues from its level: the output does not dip (the DSP's restart from 0 is hidden by its ATK 0 / HOLD INF)
    e = E()
    e.cmd(3, R.q31(1 - np.exp(-1 / (0.004 * R.SR))), R.q31(1 - np.exp(-1 / (0.05 * R.SR))), 0)
    e.cmd(4, 0, 0, 1)
    out = []
    for i in range(300):
        e.cmd(8, 0 | 127 << 8 | 127 << 16 | (1 << 24 if i in (100, 101, 160) else 0), 0, 0)
        out += e.render(16)
    y = np.array(out[2000:], dtype=np.float64) / (1 << 27)
    d2 = np.abs(y[2:] - 2 * y[1:-1] + y[:-2])
    check(d2.max() < 3.0 * float(np.max(np.abs(y))) * (2 * np.pi * 131.0 / R.SR) ** 2, "a START on a sounding track does not dip or step the output")
    # the closed AMP is silent, and costs nothing
    e = R.Engine()
    e.cmd(4, 0, 0, 1)
    check(not any(e.render(16)), "a closed AMP renders silence")

    # SPRD lifts the upper chord notes an octave; GLID sets the pitch glide's time
    e = E()
    e.cmd(5, 0, 32, 0)                                                  # SPRD 32: the 2nd note up an octave
    e.cmd(4, 0, 3, 3)                                                   # MAJ, 3 voices: C, E+12, G
    check([e.v[v]["inc_tgt"] for v in range(3)] == [R.inc_of_p(256 * k) for k in (0, 16, 7)], "SPRD 32: MAJ is C, E an octave up, G (open voicing)")
    e = E()
    e.cmd(5, 0, 127, 0)
    e.cmd(4, 0, 3, 4)
    check([e.v[v]["inc_tgt"] for v in range(4)] == [R.inc_of_p(256 * k) for k in (0, 16, 19, 24)], "SPRD 127: MAJ x4 is C, E, G, C all up an octave except the root")

    def glide_steps(glid):                                              # calls until a sounding voice is within 1 cent of its new pitch
        e = E()
        e.cmd(5, 0, 0, glid)
        e.cmd(4, 0, 0, 1)
        e.render(16)
        e.cmd(4, 12 * 256, 0, 1)
        tgt = e.v[0]["inc_tgt"]
        n = 0
        while abs(1200 * np.log2(e.v[0]["inc"] / tgt)) > 1.0 and n < 20000:
            e.render(16)
            n += 1
        return n

    g0, g64, g127 = glide_steps(0), glide_steps(64), glide_steps(127)
    check(g0 < g64 < g127 and g0 * 16 / R.SR < 0.04 and 0.2 < g127 * 16 / R.SR < 4.0,
          f"GLID 0 / 64 / 127 reaches the new pitch in {g0 * 16 / R.SR * 1000:.0f} / {g64 * 16 / R.SR * 1000:.0f} / {g127 * 16 / R.SR * 1000:.0f} ms")

    # SETUP: level, drive, octave and vibrato, on the model (the streams above hold it to the C builds)
    def tone(setup=None, p=0, secs=1, chrd=0, voic=1):
        e = E()
        e.cmd(3, R.q31(1 - np.exp(-1 / (0.004 * R.SR))), R.q31(1 - np.exp(-1 / (0.05 * R.SR))), 0)
        if setup:
            e.cmd(6, *setup, 0)
        e.cmd(4, p, chrd, voic)
        out = []
        for _ in range(R.SR * secs // 16):            # 16-sample calls, as the frame interrupt makes them (the LFO moves once a call)
            out += e.render(16)
        return np.array(out, dtype=np.float64)[R.SR // 4:] / (1 << 27)

    def pack(vibr=0, vrat=0, oct_=1, fine=64, comp=0, mode=0):
        return (vibr | vrat << 8 | oct_ << 16 | fine << 24, comp | mode << 8)

    base = tone(pack())

    def notes_poly(*ps, voic=4, mode=1):
        e = E()
        e.cmd(3, R.q31(1 - np.exp(-1 / (0.004 * R.SR))), R.q31(1 - np.exp(-1 / (0.05 * R.SR))), 0)
        e.cmd(6, *pack(mode=mode), 0)
        for p in ps:
            e.cmd(4, 256 * p, 3, voic)
        return e

    e = notes_poly(0, 4, 7, 12)
    check([bool(v["gate"]) for v in e.v] == [True] * 4 and sorted(v["inc_tgt"] for v in e.v) == sorted(R.inc_of_p(256 * k) for k in (0, 4, 7, 12)),
          "POLY: four trigs take four voices, each its own pitch, all still gated")
    e = notes_poly(0, 4, 7, 12, 16)
    check(e.v[0]["inc_tgt"] == R.inc_of_p(16 * 256) and e.v[1]["inc_tgt"] == R.inc_of_p(4 * 256), "POLY: the fifth trig takes voice 0 again (round-robin)")
    e = notes_poly(0, 4, 7, voic=2)
    check(e.v[0]["inc_tgt"] == R.inc_of_p(7 * 256) and e.v[1]["inc_tgt"] == R.inc_of_p(4 * 256) and not e.v[2]["gate"] and not e.v[3]["gate"],
          "POLY with VOIC 2: a pool of two voices, the others off")
    e = notes_poly(0, 4, voic=2, mode=0)
    check(e.v[0]["inc_tgt"] == R.inc_of_p(256 * 4) and e.v[1]["inc_tgt"] == R.inc_of_p(256 * 8) and not e.v[2]["gate"],
          "CHORD mode (CHRD 3, VOIC 2, the second trig at +4): the chord's first two notes on voices 0 and 1, the earlier note replaced")

    e = E()
    e.cmd(7, 0xAB5, 0, 0)                                               # C major
    e.cmd(4, 0, 4, 4)                                                   # CHRD MIN: C Eb G C
    got = [e.v[v]["inc_tgt"] for v in range(4)]
    want = [R.inc_of_p(256 * k) for k in (0, 2, 7, 12)]                # Eb -> D (the lower neighbour first)
    check(got == want, "a scale snaps the chord: C minor in C major is C D G C (ties go down)")
    e = E()
    e.cmd(7, 0xAB5, 0, 0)
    e.cmd(4, 0, 3, 4)
    check([e.v[v]["inc_tgt"] for v in range(4)] == [R.inc_of_p(256 * k) for k in (0, 4, 7, 12)], "a scale that holds the chord leaves it as it is")
    e = E()
    e.cmd(7, 0xAB5, 0, 0)
    e.cmd(4, 256 * 3 + 100, 0, 1)
    check(e.v[0]["inc_tgt"] == R.inc_of_p(256 * 2 + 100), "the snap moves whole semitones: the fraction stays")

    # a pitch change on a sounding voice glides: no spike in the second difference (a step in the increment was ~20x a clean sine's)
    e = E()
    e.cmd(3, R.q31(1 - np.exp(-1 / (0.004 * R.SR))), R.q31(1 - np.exp(-1 / (0.05 * R.SR))), 0)
    e.cmd(4, 0, 0, 1)
    pre = []
    for _ in range(R.SR // 2 // 16):
        pre += e.render(16)
    e.cmd(4, 7 * 256, 0, 1)                                              # C3 -> G3 on a sounding voice
    post = []
    for _ in range(R.SR // 4 // 16):
        post += e.render(16)
    y = np.array(pre[-2000:] + post, dtype=np.float64) / (1 << 27)
    A = float(np.max(np.abs(y)))
    d2 = np.abs(y[2:] - 2 * y[1:-1] + y[:-2])
    clean = A * (2 * np.pi * 196.0 / R.SR) ** 2
    check(d2.max() < 3.0 * clean, f"a pitch change glides: the largest second difference is {d2.max() / clean:.1f}x a clean sine's (a step was ~20x)")

    def peak_hz(x):
        sp = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        return float(np.argmax(sp) * R.SR / len(x))

    check(abs(peak_hz(tone(pack(oct_=2))) / peak_hz(base) - 2.0) < 0.01 and abs(peak_hz(tone(pack(oct_=0))) / peak_hz(base) - 0.5) < 0.01,
          "OCT 0 / 1 / 2 is an octave down / none / up")
    def inc_after(setup):                                                  # the note's phase step: no FFT resolution in the way
        e = E()
        e.cmd(6, *setup, 0)
        e.cmd(4, 0, 0, 1)
        return e.v[0]["inc_tgt"]

    cents = 1200 * np.log2(inc_after(pack(fine=127)) / inc_after(pack(fine=64)))
    check(abs(cents - 49.2) < 0.2 and abs(1200 * np.log2(inc_after(pack(fine=0)) / inc_after(pack(fine=64))) + 50.0) < 0.2,
          f"FINE 0 / 64 / 127 is -50 / 0 / +49 cents ({cents:.2f})")

    def h3(x):                                                            # the 3rd harmonic against the fundamental
        sp = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        f0 = int(np.argmax(sp))
        return float(sp[3 * f0 - 3:3 * f0 + 4].max() / sp[f0 - 3:f0 + 4].max())

    check(h3(base) < 0.002 and h3(tone(pack(comp=100))) > 0.02, f"COMP adds odd harmonics (3rd: {h3(base):.4f} -> {h3(tone(pack(comp=100))):.4f})")
    lv = [np.sqrt(np.mean(tone(pack(comp=c)) ** 2)) for c in (1, 60, 127)]
    check(max(lv) / min(lv) < 1.5, f"COMP's makeup holds the peak; the RMS stays within 1.5x as the wave squares ({max(lv) / min(lv):.2f})")

    def zc_std(x):                                                         # the spread of the period lengths, as a fraction
        z = np.nonzero((x[:-1] < 0) & (x[1:] >= 0))[0]
        d = np.diff(z).astype(np.float64)
        return float(d.std() / d.mean())

    check(zc_std(tone(pack(vibr=127, vrat=60), secs=3)) > 0.005 and zc_std(base) < 0.002,
          f"VIBR moves the pitch (period spread {zc_std(tone(pack(vibr=127, vrat=60), secs=3)):.4f}, off {zc_std(base):.5f})")

    # the note layer
    worst = 0.0
    for p in range(-48 * 256, 48 * 256 + 1, 13):
        hz = tables.BASE_HZ * 2.0 ** (p / 256.0 / 12.0)
        got = R.inc_of_p(p) / 4294967296.0 * R.SR
        worst = max(worst, abs(1200 * __import__("math").log2(got / hz)))
    check(worst < 0.5, f"wcf_inc is within {worst:.3f} cents of 2^(p/12) from C3 across -48..+48 semitones")
    check(abs(R.inc_of_p(0) - R.inc_of(tables.BASE_HZ)) <= 1 and R.inc_of_p(12 * 256) == 2 * R.inc_of_p(0), "TUNE 0 is C3 and +12 semitones doubles the increment")
    e = E()
    e.note(0, 3, 3)
    incs = [e.v[v]["inc_tgt"] for v in range(4)]
    want = [R.inc_of_p(256 * d) for d in tables.CHORDS[3][:3]]
    check(incs[:3] == want and e.v[3]["gate"] == 0 and all(e.v[v]["gate"] for v in range(3)), "CHRD 3 with VOIC 3 gates the first three chord notes and no fourth")
    print("FAIL" if FAILS else "ALL PASS")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
