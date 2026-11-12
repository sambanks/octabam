#!/usr/bin/env python3
"""FRAME GUARD's arithmetic under Unicorn (modules/frame-guard/guard.s).

guard.s is assembled both ways (alone: it replays the prologue and jumps to the handler's body; bridged by HOOKS:
it returns) and fg_in is entered at a list of entry times against a model of DMA timer 3 that advances with the
instructions run. Checked per entry: whether it waited, how late the entry was when fg_in left, fg_waits, and for
the alone build the prologue's frame and the jump to 0x4000aad8.

This proves the decision and the wait's length. It does not model the DSP: that an entry 190 us late makes the DSP
skip a frame, and that the window 110-190 us holds the stall, are measurements on a unit (guard.s's header).
"""
import pathlib
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
try:
    from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_READ
    from unicorn.m68k_const import UC_CPU_M68K_CFV4E, UC_M68K_REG_A7, UC_M68K_REG_PC, UC_M68K_REG_SR
except ImportError:
    print("  [SKIP] verify_frame_guard: no unicorn (the .venv: make emu-setup)")
    sys.exit(0)

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "modules/frame-guard/guard.s"
AT = 0x40300000                 # the unit, linked here
BODY = 0x4000AAD8
STOP = 0x40310000               # the bridged build's return address
STACK = 0x40320000
DTCN3 = 0xFC07C00C
US = 132                        # timer counts a microsecond
TICK = 12                       # counts an instruction in the model (0.09 us)
FRAME = 362.8
LLO, LHI = 110, 190

# (interval before this entry in us, waits?) from a quiet start; lateness accumulates as guard.s computes it
CASES = (
    ("on the grid", [(FRAME, False)] * 6),
    ("105 us late: below the window", [(FRAME, False), (FRAME + 105, False), (FRAME - 105, False)]),
    ("111 us late: waits", [(FRAME, False), (FRAME + 111, True)]),
    ("149 us late (a logged stall's entry): waits", [(FRAME, False), (FRAME + 149, True)]),
    ("155 us late (the other): waits", [(FRAME, False), (FRAME + 155, True)]),
    ("189 us late: waits", [(FRAME, False), (FRAME + 189, True)]),
    ("195 us late: past the window", [(FRAME, False), (FRAME + 195, False)]),
    ("after a guarded entry the skipped frame's successor is on the grid",
     [(FRAME, False), (FRAME + 149, True), (2 * FRAME - 149, False), (FRAME, False)]),
    ("two late entries in a row: lateness carries", [(FRAME, False), (FRAME + 60, False), (FRAME + 60, True)]),
    ("a gap of five frames is on time", [(FRAME, False), (5 * FRAME + 150, False), (FRAME, False)]),
)


def assemble(bridged, d):
    d = pathlib.Path(d)
    (d / "remix.inc").write_text(f"        .equ HK_FRAME_ENTRY, {1 if bridged else 0}\n")
    o, e, b = d / "g.o", d / "g.elf", d / "g.bin"
    subprocess.run(["m68k-elf-as", "-mcpu=5475", f"-I{d}", "-o", str(o), str(SRC)], check=True)
    subprocess.run(["m68k-elf-ld", "-Ttext", hex(AT), "-Tdata", hex(AT + 0x800), "-e", "fg_in", "-o", str(e), str(o)],
                   check=True, capture_output=True)
    subprocess.run(["m68k-elf-objcopy", "-O", "binary", str(e), str(b)], check=True)
    nm = subprocess.check_output(["m68k-elf-nm", str(e)], text=True)
    syms = {ln.split()[2]: int(ln.split()[0], 16) for ln in nm.splitlines() if len(ln.split()) == 3}
    return b.read_bytes(), syms


class Run:
    def __init__(self, bridged, built):
        code, self.syms = built
        self.bridged = bridged
        uc = self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        uc.mem_map(AT, 0x30000)
        uc.mem_write(AT, code)
        uc.mem_map(BODY & ~0xFFF, 0x1000)
        uc.mem_map(DTCN3 & ~0xFFF, 0x1000)
        self.clock = 1 << 20
        uc.hook_add(UC_HOOK_CODE, self._tick)
        uc.hook_add(UC_HOOK_MEM_READ, self._timer, begin=DTCN3, end=DTCN3 + 3)

    def _tick(self, _uc, _addr, _size, _data):
        self.clock = (self.clock + TICK) & 0xFFFFFFFF

    def _timer(self, uc, _access, addr, _size, _value, _data):
        uc.mem_write(DTCN3, struct.pack(">I", self.clock))

    def word(self, name):
        return struct.unpack(">I", self.uc.mem_read(self.syms[name], 4))[0]

    def enter(self, at):
        """fg_in entered with the timer at `at` counts -> (the timer when it left, sp moved by)."""
        uc = self.uc
        self.clock = at & 0xFFFFFFFF
        uc.reg_write(UC_M68K_REG_SR, 0x2500)
        uc.reg_write(UC_M68K_REG_A7, STACK)
        if self.bridged:
            uc.mem_write(STACK, struct.pack(">I", STOP))
        uc.emu_start(self.syms["fg_in"], BODY if not self.bridged else STOP, count=2_000_000)
        pc = uc.reg_read(UC_M68K_REG_PC)
        want = STOP if self.bridged else BODY
        if pc != want:
            raise AssertionError(f"left at {pc:#x}, expected {want:#x}")
        return self.clock, STACK - uc.reg_read(UC_M68K_REG_A7)


def check(bridged):
    bad = 0
    with tempfile.TemporaryDirectory() as d:
        built = assemble(bridged, d)
    for name, seq in CASES:
        r = Run(bridged, built)
        t = 5_000_000
        late = 0.0
        first = True
        for interval, waits in seq:
            t += round(interval * US)
            if first or interval > 4 * FRAME:
                late = 0.0
            else:
                late = max(0.0, late + interval - 363.33)
                late -= 363.33 * int(late // 363.33)
            first = False
            n0 = r.word("fg_waits")
            left, moved = r.enter(t)
            waited = r.word("fg_waits") - n0
            spent = (left - t) / US
            ok = waited == (1 if waits else 0)
            if waits:
                ok = ok and LHI - 0.5 <= late + spent <= LHI + 1.5      # left when the entry was LHI late
            else:
                ok = ok and spent < 5                                    # straight through
            ok = ok and moved == (-4 if bridged else 252)               # rts popped / the prologue's frame
            if not ok:
                bad += 1
                print(f"  [FAIL] {'bridged' if bridged else 'alone'}: {name}: entry {late:.1f} us late, "
                      f"waited {waited}, spent {spent:.1f} us, sp moved {moved}")
    print(f"  [{'FAIL' if bad else ' OK '}] FRAME GUARD {'bridged by HOOKS' if bridged else 'alone'}: "
          f"{len(CASES)} entry sequences, window {LLO}-{LHI} us")
    return bad


def main():
    import shutil
    if not all(shutil.which(t) for t in ("m68k-elf-as", "m68k-elf-ld", "m68k-elf-objcopy", "m68k-elf-nm")):
        print("  [SKIP] verify_frame_guard: no m68k-elf toolchain")
        return 0
    return 1 if check(False) + check(True) else 0


if __name__ == "__main__":
    sys.exit(main())
