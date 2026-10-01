#!/usr/bin/env python3
"""DSP RESET PROBE under the port: the instrument answers BOTH ways.

    python3 tools/verify/verify_dspreset.py dsp-reset

The probe asks whether the ColdFire can reset the DSP (RSTOUT, RCR bit 6).
The port cannot answer that -- it has no board, and a modelled pin proves
nothing about a real one. What the port CAN prove, and what this gate is
for, is that the probe would tell us either way. A measurement that can
only report one of its two outcomes is worth nothing (AGENTS.md: ask what
the instrument physically cannot see), so the same image is booted twice:

  plain               no model. Every core keeps running its payload, so
                      the control pass and both test passes must come back
                      EMPTY, the probe must not re-upload anything, and the
                      boot must go on to the RTOS handoff.
  --dsp-reset-on      the port models a reset line on that register bit
                      (dsp.h bootReset). The control pass must STILL be
                      empty -- it runs before the pulse -- and then both
                      cores must answer with their own magic, the probe
                      must re-pulse and re-run the stock upload, and the
                      boot must still reach the handoff with both cores
                      back in a finished boot.

And with OS SWITCH in the remix (`dsp-reset-pc`) the plain run must also
show the POSITIVE CONTROL: the probe parks core 0 with host command $12,
and the parked core -- a boot-ROM loader -- must answer the same seven
words. That step is what makes a "no answer" on the unit mean anything, so
it is gated here before it is trusted there.

Plus: the seven words the ColdFire sends are assembled from micro.asm on
every run and compared with the longs in probe.s, and disassembled back
(AGENTS.md: disassemble what you assemble).

The notes are read at the probe's own MIDI routine, the way verify_boottrace
reads BOOT TRACE's: --watch-pc on `dr_note` gives the note in d0 and the
velocity in d1 at every call.
"""
import os, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
ASM = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm"
DISASM = ROOT / "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"
MOD = ROOT / "modules/dsp-reset-probe"
CELL_MAGIC = 0x44525031
RCR_BIT = "0xfc0a0000:6"

# note, velocity. The probe's own table (probe.s): 40 in, 41 the control,
# 42 the pulse, 43/44 the cores, 45/46 the restore, 47 done, 48 the control
# answered, 49 an unexpected word.
#
# NONE is "no boot ROM answered", which has two honest shapes and the gate
# accepts either: 0, every word went and nothing came back, or 3, the port
# would not take a word. A RUNNING payload gives 3 here -- it leaves a word
# unread in its receive register, which holds TXDE low -- while a unit whose
# payload drains the register through its DMA would give 0. Neither is an
# answer; only 1 is.
NONE = (0, 3)
# No 45/46 in the plain run: nothing answered, so there is nothing to put
# back in a boot ROM and no upload to re-run (probe.s, "the restore").
PLAIN = [(40, 1), (41, NONE), (42, 1), (43, NONE), (44, NONE),
         (42, 2), (43, NONE), (44, NONE), (47, 0)]
# With OS SWITCH in the remix the probe MAKES a listening boot ROM: core 1
# takes the park command (50/1) and then answers the same seven words
# (51/1). That is the positive control, the half of the argument the
# modelled run cannot give on a unit -- it must hold under the port too, or
# the step is not doing what it says.
# ... and it runs FIRST, on core 1, so the parked loader gets a clean port;
# core 1 is then not probed again (no note 44).
PLAIN_PC = [(40, 1), (50, 1), (51, 1), (41, NONE), (42, 1), (43, NONE),
            (42, 2), (43, NONE), (47, 0x40)]
# bit 0 core 0 answered | bit 1 core 1 | pass 1 in bits 3..2 | bit 4 re-uploaded
RESET = [(40, 1), (41, NONE), (42, 1), (43, 1), (44, 1), (45, 1), (46, 1), (47, 0x17)]
# the modelled run with the park build: the positive control first, then the
# reset answers on core 0 alone (core 1 is the control's, and parked)
RESET_PC = [(40, 1), (50, 1), (51, 1), (41, NONE), (42, 1), (43, 1),
            (45, 1), (46, 1), (47, 0x55)]


def matches(seq, want):
    """The note stream against a table whose velocities may be a set."""
    if len(seq) != len(want):
        return False
    for (n, v), (wn, wv) in zip(seq, want):
        if n != wn or (v not in wv if isinstance(wv, tuple) else v != wv):
            return False
    return True


def nm(elf):
    out = subprocess.run(["m68k-elf-nm", str(elf)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def micro_words(work):
    """The words dsp_asm makes of micro.asm, round-tripped."""
    src, binf = work / "micro.asm", work / "micro.bin"
    src.write_bytes((MOD / "micro.asm").read_bytes())
    subprocess.run([str(ASM), "-in", str(src), "-org", "31000", "-out", str(binf)],
                   check=True, capture_output=True, text=True)
    b = binf.read_bytes()
    words = [b[i] | (b[i + 1] << 8) | (b[i + 2] << 16) for i in range(0, len(b), 3)]
    back = subprocess.run([str(DISASM), "-in", str(binf), "-pc", "31000", "-le"],
                          capture_output=True, text=True).stdout
    return words, back


def probe_longs():
    """The `.long`s under dr_micro in probe.s."""
    text = (MOD / "probe.s").read_text().split("dr_micro:", 1)[1]
    out = []
    for line in text.splitlines():
        line = line.split("|")[0].strip()
        if not line:
            continue
        if not line.startswith(".long"):
            break
        out += [int(v, 0) for v in line[5:].split(",")]
    return out


def notes(out, at):
    seq = []
    for m in re.finditer(r"^\s*\[\s*\d+\] at 0x([0-9a-f]+) d0=(0x[0-9a-f]+|0) d1=(0x[0-9a-f]+|0)",
                         out, re.M):
        if int(m.group(1), 16) == at:
            seq.append((int(m.group(2), 16) & 0xFF, int(m.group(3), 16) & 0x7F))
    return seq


def boot(image, at, cell, work, tag, extra=()):
    ver = work / "norver.bin"
    ver.write_bytes((ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()[0xDE648:0xDE64A])
    dump = work / f"cell_{tag}.bin"
    out = subprocess.run([str(EMU), "--image", str(image), "--mkii", "--dsp",
                          "--preload", f"0x3ffc={ver}", "--max", "200000000",
                          "--frame", "--frames", "20",
                          "--mem-dump", f"{cell:#x},32={dump}",
                          "--watch-pc", f"0x{at:x}", *extra],
                         capture_output=True, text=True, cwd=ROOT).stdout
    cell = dump.read_bytes() if dump.exists() else b""
    rec = [int.from_bytes(cell[i:i + 4], "big") for i in range(0, len(cell), 4)]
    return out, notes(out, at), rec


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    if "DSP RESET PROBE" not in registry.remix(remix).modules:
        print(f"  [SKIP] verify_dspreset: {remix} does not carry DSP RESET PROBE")
        return 0
    if not EMU.exists():
        print("  [SKIP] verify_dspreset: the ColdFire port is not built (make emu-cf)")
        return 0
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_dspreset: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    work = pathlib.Path(tempfile.mkdtemp(prefix="dspreset."))
    syms = nm(ROOT / "out/linked/dsp-reset-probe/dsp_reset_probe/u.elf")
    at, cell = syms["dr_note"], syms["dr_cell"]
    fails = []

    # 1. the seven words are micro.asm's, and they disassemble back to it
    want, back = micro_words(work)
    got = probe_longs()
    if got != want:
        fails.append(f"probe.s's dr_micro {[hex(w) for w in got]} is not micro.asm's "
                     f"{[hex(w) for w in want]}")
    for form in ("brclr", "M_HOTX", "$5a3c60"):
        if form not in back:
            fails.append(f"the round-trip disassembly has no {form}:\n{back}")
    # probe.s finds the magic's immediate BY VALUE to OR the core number in
    if want.count(0x5A3C60) != 1:
        fails.append(f"the magic is not unique in the table: {[hex(w) for w in want]}")

    # 2. plain: nothing answers, nothing is re-uploaded, the boot goes on
    image = ROOT / "out/mainos_bus.bin"
    park = "OS SWITCH" in registry.remix(remix).modules
    want = PLAIN_PC if park else PLAIN
    out, seq, rec = boot(image, at, cell, work, "plain")
    if not matches(seq, want):
        fails.append(f"plain: notes {seq} != {want}")
    if "HANDOFF" not in out:
        fails.append("plain: the boot did not reach the RTOS handoff")
    if not rec or rec[0] != CELL_MAGIC or rec[5] != (0x40 if park else 0):
        fails.append(f"plain: the cell reads {[hex(v) for v in rec]}")
    # core 1's magic: the probe ORs the core number into it
    if park and (len(rec) < 8 or rec[7] != 0x5A3C61):
        fails.append(f"plain: the parked core answered {[hex(v) for v in rec]}, not 0x5a3c61")

    # 3. modelled: both cores answer, the probe restores them, the boot goes on
    out, seq, rec = boot(image, at, cell, work, "reset", ("--dsp-reset-on", RCR_BIT))
    want = RESET_PC if park else RESET
    if "dsp-reset  : MODELLED" not in out:
        fails.append("--dsp-reset-on was not accepted by the port")
    if not matches(seq, want):
        fails.append(f"modelled: notes {seq} != {want}")
    if "HANDOFF" not in out:
        fails.append("modelled: the boot did not reach the RTOS handoff after the re-upload")
    if "core 0: boot ROM done" not in out or "core 1: boot ROM done" not in out:
        fails.append("modelled: a core did not come back from the re-upload")
    ok_cell = (rec and rec[0] == CELL_MAGIC and rec[3] == 0x5A3C60
               and rec[5] == (0x55 if park else 0x17)
               and (park or rec[4] == 0x5A3C61))
    if not ok_cell:
        fails.append(f"modelled: the cell reads {[hex(v) for v in rec]}")

    ok = not fails
    print(f"  [{'PASS' if ok else 'FAIL'}] verify_dspreset: the probe reports NO reset on the "
          f"plain port and both cores in their boot ROM when the port models one "
          f"({RCR_BIT}); its seven words are micro.asm's")
    for f in fails:
        print(f"         {f}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
