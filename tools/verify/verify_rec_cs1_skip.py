#!/usr/bin/env python3
"""verify_rec_cs1_skip -- REC CS1 SKIP's routine leaves memory as stock's does.

The recorder's control-record update (stock 0x4000432c) runs about 1.5 times a
recording track a frame and writes six fields of the track's record in CS1
(0x100d38f0 + 1096 x id), almost always with the values already there. CS1
costs about 0.5 us an access on a MKII. REC CS1 SKIP's rcs_update replaces the
routine and skips those writes (skip.s has the argument).

This gate runs stock's routine (from the user's own OS image) and rcs_update
(linked here from skip.s) side by side under unicorn (ColdFire V4e), each on
its own copy of memory, through the same long run of calls, and compares:

  - the 44-byte records at 0x46c938c4 and every byte of the CS1 page, after
    every call;
  - [r+300] and [r+308] always (the skip compares the value it read);
  - [r+276], [r+280], [r+296].b and [r+304] always, except for at most four
    calls of that track after another writer changed one of them (the
    copy in DRAM is checked one field a call; skip.s): then within four;
  - d2-d7, a2-a6 and the stack pointer as the caller left them.

The calls cover ids 0..9 (8 and 9 have no copy and write as stock), lengths
0, under 64, large and negative, the flag set and clear, the two tempo words
changing, and other writers storing into every one of the six fields. It also
counts CS1 reads and writes per call in steady play, stock against the module.
"""
import pathlib
import random
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
try:
    from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn import m68k_const as R
except ImportError:
    print("  [SKIP] verify_rec_cs1_skip: no unicorn (the .venv: make emu-setup)")
    sys.exit(0)

from remix import platform_build, registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
OS = ROOT / "out/raw/section_3_MAIN_OS.bin"
LOAD = 0x40000400               # the section's first byte (emu_bringup: the image's 0x400-byte header precedes it)
STOCK = 0x4000432c
UNIT_AT = 0x40400000            # rcs_update linked here, away from the OS image
STACK = 0x40500000
STOP = 0x40600000               # the return address: emulation stops here
CS1 = 0x100d0000                # the page holding the records of ids 0..9
REC0, REC_SIZE = 0x100d38f0, 1096
TABLE = 0x46c90000              # the page holding 0x46c938c4 + 44 x id
GLOBALS = 0x80001000            # 0x8000181c and 0x80001820, the routine's two other inputs
MIRRORED = (276, 280, 296, 304)  # checked against the copy, one a call
READ_FIELDS = (300, 308)        # compared with the value read
SAVED = ([getattr(R, f"UC_M68K_REG_D{i}") for i in range(2, 8)]
         + [getattr(R, f"UC_M68K_REG_A{i}") for i in range(2, 7)])


def link_unit():
    """skip.s linked alone at UNIT_AT -> (bytes, rcs_update's address)."""
    m = registry.by_key("REC CS1 SKIP")
    with tempfile.TemporaryDirectory() as d:
        raw, syms, _, _ = platform_build.link_runtime([(m.key, m.linked[0])], pathlib.Path(d), {}, UNIT_AT)
    return raw, syms["rcs_update"], m


class Machine:
    def __init__(self, os_bytes, unit):
        uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(R.UC_CPU_M68K_CFV4E)
        uc.mem_map(0x40000000, (0x400 + len(os_bytes) + 0xFFFF) & ~0xFFFF)
        uc.mem_write(LOAD, os_bytes)
        for base in (UNIT_AT, STACK, STOP, CS1, TABLE, GLOBALS):
            uc.mem_map(base, 0x10000)
        uc.mem_write(UNIT_AT, unit)
        uc.mem_write(STOP, b"\x4e\x71")
        self.uc = uc
        self.reads = self.writes = 0
        uc.hook_add(UC_HOOK_MEM_READ, self._read, begin=CS1, end=CS1 + 0xFFFF)
        uc.hook_add(UC_HOOK_MEM_WRITE, self._write, begin=CS1, end=CS1 + 0xFFFF)

    def _read(self, *a):
        self.reads += 1

    def _write(self, *a):
        self.writes += 1

    def call(self, at, rid, length, flag, regs):
        uc = self.uc
        sp = STACK + 0x8000
        args = [STOP, rid & 0xFFFFFFFF, length & 0xFFFFFFFF, flag]
        uc.mem_write(sp, b"".join(v.to_bytes(4, "big") for v in args))
        for r, v in zip(SAVED, regs):
            uc.reg_write(r, v)
        uc.reg_write(R.UC_M68K_REG_SR, 0x2000)               # supervisor, as in the frame interrupt (before a7:
        uc.reg_write(R.UC_M68K_REG_A7, sp)                   # the SR write selects the stack pointer a7 names)
        self.reads = self.writes = 0
        uc.emu_start(at, STOP, count=10_000)
        if uc.reg_read(R.UC_M68K_REG_PC) != STOP:
            sys.exit(f"  [FAIL] verify_rec_cs1_skip: the routine at {at:#x} did not return")
        return [uc.reg_read(r) for r in SAVED], uc.reg_read(R.UC_M68K_REG_A7) - 4   # sp after the rts

    def poke(self, addr, value, size):
        self.uc.mem_write(addr, (value & ((1 << (8 * size)) - 1)).to_bytes(size, "big"))

    def page(self, base):
        return bytes(self.uc.mem_read(base, 0x10000))


def fail(msg):
    sys.exit(f"  [FAIL] verify_rec_cs1_skip: {msg}")


def main():
    if not OS.exists():
        fail(f"{OS.relative_to(ROOT)} is missing (make os && make recon)")
    os_bytes = OS.read_bytes()
    unit, entry, m = link_unit()
    want = m.detours[0].expect
    if os_bytes[STOCK - LOAD:STOCK - LOAD + len(want)] != want:
        fail("the OS image does not hold the routine the detour expects at 0x4000432c")
    stock, mod = Machine(os_bytes, unit), Machine(os_bytes, unit)
    rng = random.Random(0xc51)
    grace = [0] * 10
    lengths = [0] * 10
    n = steady = 0
    io = {"stock": [0, 0], "module": [0, 0]}
    for both in (stock, mod):
        both.poke(0x8000181c, 0x1234, 4)
        both.poke(0x80001820, 0x56, 4)
    for i in range(40_000):
        quiet = i >= 38_000                                  # the last calls: no other writer, to show it converges
        if rng.random() < 0.01:
            v, at = rng.getrandbits(32), rng.choice((0x8000181c, 0x80001820))
            for both in (stock, mod):
                both.poke(at, v, 4)
        if not quiet and rng.random() < 0.03:                # another writer stores into a record
            rid = rng.randrange(10)
            off = rng.choice(MIRRORED + READ_FIELDS)
            size = 1 if off == 296 else 4
            v = rng.getrandbits(8 * size)
            for both in (stock, mod):
                both.poke(REC0 + REC_SIZE * rid + off, v, size)
            if off in MIRRORED and rid < 8:
                grace[rid] = 4
        rid = rng.choice((0, 1, 2, 3, 4, 5, 6, 7, 0, 1, 2, 8, 9))
        roll = rng.random()
        if roll < 0.02:
            lengths[rid] = 0
        elif roll < 0.04:
            lengths[rid] = rng.randrange(1, 64)
        elif roll < 0.05:
            lengths[rid] = -rng.randrange(1, 1 << 20)
        elif roll < 0.15:
            lengths[rid] = rng.randrange(64, 1 << 22)
        elif roll < 0.40:
            lengths[rid] += rng.randrange(1, 64)             # the recording grows
        flag = 1 if rng.random() < 0.05 else 0
        regs = [rng.getrandbits(32) for _ in SAVED]
        got_s, sp_s = stock.call(STOCK, rid, lengths[rid], flag, regs)
        got_m, sp_m = mod.call(entry, rid, lengths[rid], flag, regs)
        n += 1
        if got_m != regs or sp_m != sp_s:
            fail(f"call {n}: a callee-saved register or the stack pointer changed (id {rid})")
        if stock.page(TABLE) != mod.page(TABLE):
            fail(f"call {n}: the 44-byte records at 0x46c938c4 differ (id {rid}, len {lengths[rid]})")
        if not flag and lengths[rid] and grace[rid]:
            grace[rid] -= 1
        a, b = stock.page(CS1), mod.page(CS1)
        if a != b:
            for j in range(0x10000):
                if a[j] != b[j]:
                    addr = CS1 + j
                    who, off = divmod(addr - REC0, REC_SIZE)
                    in_field = 0 <= who < 10 and any(f <= off < f + (1 if f == 296 else 4) for f in MIRRORED)
                    if not (in_field and grace[who]):
                        fail(f"call {n}: CS1 {addr:#x} (id {who}, +{off}) differs from stock's "
                             f"({b[j]:#04x}, stock {a[j]:#04x})")
        if not flag and lengths[rid] > 0 and i > 1_000 and not any(grace):
            steady += 1
            io["stock"][0] += stock.reads
            io["stock"][1] += stock.writes
            io["module"][0] += mod.reads
            io["module"][1] += mod.writes
    if stock.page(CS1) != mod.page(CS1):
        fail("CS1 differs from stock's at the end, after 2,000 calls with no other writer")
    print(f"  PASS  rcs_update leaves the records and CS1 as stock's routine does, over {n} calls "
          f"(other writers within four calls of a track; at the end, every byte)")
    for k, (r, w) in io.items():
        print(f"        {k:7}: {r / steady:.2f} CS1 reads, {w / steady:.2f} CS1 writes a call ({steady} calls in steady play)")


if __name__ == "__main__":
    main()
