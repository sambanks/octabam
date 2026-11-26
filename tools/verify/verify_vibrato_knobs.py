#!/usr/bin/env python3
"""VIBRATO's FUNC-stop knob handlers (modules/vibrato/func_stops.s) under Unicorn.

The unit is assembled on its own (m68k-elf-as, -mcpu=5407, as build_bus
does) and every entry is called as the stock knob path calls a P+0x12a
handler: f(slot, detents, value) -> d0. No firmware image: the globals the
handler reads (FUNCTION, PERSONALIZE's FUNCTION + ENCODER, the key
records) are planted in mapped RAM. verify_lofi2_knobs.py is the same gate
for LOFI2's unit. Checked:

1. FUNC held: every entry walks its table up from the bottom and down from
   the top, one stop a detent; a multi-detent turn equals single steps; a
   value between stops lands on the nearest stop in the turn's direction;
   past the end the value stays.
2. FUNC not held: one unit a detent; x7 with the entry's own encoder
   pushed, not another's; PERSONALIZE's FUNCTION + ENCODER makes FUNC
   plain.
3. d2-d4 and the stack survive.

Raw values only: the stock caller clamps what the handler returns.

    python3 tools/verify/verify_vibrato_knobs.py
"""
from __future__ import annotations

import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_MEM_UNMAPPED
from unicorn.m68k_const import (
    UC_CPU_M68K_CFV4E,
    UC_M68K_REG_A7,
    UC_M68K_REG_D0,
    UC_M68K_REG_D2,
    UC_M68K_REG_D3,
    UC_M68K_REG_D4,
    UC_M68K_REG_PC,
    UC_M68K_REG_SR,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "modules/vibrato/func_stops.s"

CODE = 0x40200000          # where the unit is loaded (position-independent)
STOP = 0x40300000          # return address; emulation ends here
STACK = 0x46e00000
FUNC_HELD = 0x46c7dd26
FUNC_ENC_OFF = 0x800000a0
KEY_HELD = 0x46c7d8de + 0x10
PUSH_CODE = 0x38
CUR_TRACK = 0x80000000
CUR_PAGE = 0x460d1684
LIVE_LANE = 0x80000810

# The tables the README promises (raw values): entry -> (slot = encoder, stops).
Q5 = [0, 32, 64, 96, 127]
SEVENTHS = [0, 21, 43, 64, 85, 107, 127]
TABLES = {
    "vb_knob_spd": (0, SEVENTHS),                        # octaves, 0.25 .. 8 Hz, 15.5
    "vb_knob_dep": (1, [0, 14, 28, 40, 64, 90, 110, 127]),  # 0 1.2 4.9 9.9 25.4 50.2 75 100 cents
    "vb_knob_slew": (2, Q5),
    "vb_knob_wid": (3, SEVENTHS),                        # every 30 degrees
    "vb_knob_mix": (5, Q5),
}

FAILS = 0


def die(msg):
    print(f"  [FAIL] verify_vibrato_knobs: {msg}", file=sys.stderr)
    sys.exit(1)


def check(label, ok, detail=""):
    global FAILS
    if not ok:
        FAILS += 1
        print(f"  [FAIL] {label}" + (f" ({detail})" if detail else ""), file=sys.stderr)
    else:
        print(f"  [PASS] {label}" + (f" -- {detail}" if detail else ""))


def tool(name):
    for prefix in ("m68k-elf-", "m68k-linux-gnu-"):
        path = shutil.which(prefix + name)
        if path:
            return path
    die(f"no m68k {name} on PATH (make setup)")


def assemble():
    with tempfile.TemporaryDirectory() as tmp:
        obj = pathlib.Path(tmp) / "func_stops.o"
        binf = pathlib.Path(tmp) / "func_stops.bin"
        subprocess.run([tool("as"), "-mcpu=5407", "-o", str(obj), str(SRC)], check=True)
        subprocess.run([tool("objcopy"), "-O", "binary", "-j", ".text", str(obj), str(binf)], check=True)
        syms = {}
        for line in subprocess.check_output([tool("nm"), str(obj)], text=True).splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[1] in "Tt":
                syms[parts[2]] = int(parts[0], 16)
        return binf.read_bytes(), syms


class Machine:
    def __init__(self, code, syms):
        self.syms = syms
        uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        uc.mem_map(CODE, 0x10000)
        uc.mem_write(CODE, code)
        uc.mem_map(STOP, 0x1000)
        uc.mem_map(STACK - 0x10000, 0x20000)
        for base in (FUNC_HELD & ~0xfff, KEY_HELD & ~0xfff, CUR_PAGE & ~0xfff, 0x80000000):
            try:
                uc.mem_map(base, 0x2000)
            except Exception:
                pass

        def on_unmap(_uc, _access, address, _size, _value, _data):
            die(f"unmapped access at {address:#x} (pc {_uc.reg_read(UC_M68K_REG_PC):#x})")

        uc.hook_add(UC_HOOK_MEM_UNMAPPED, on_unmap)
        self.uc = uc
        self.state(func=False)

    def state(self, func=False, enc_off=False, pushed=None, track=0, page=4, lane=None):
        uc = self.uc
        uc.mem_write(FUNC_HELD, struct.pack(">I", 1 if func else 0))
        uc.mem_write(FUNC_ENC_OFF, struct.pack(">I", 1 if enc_off else 0))
        for enc in range(6):
            uc.mem_write(KEY_HELD + (PUSH_CODE + enc) * 0x18,
                         struct.pack(">I", 1 if pushed == enc else 0))
        uc.mem_write(CUR_TRACK, bytes([track]))
        uc.mem_write(CUR_PAGE, struct.pack(">I", page))
        uc.mem_write(LIVE_LANE, bytes(72 * 8))
        for (t, off), raw in (lane or {}).items():
            uc.mem_write(LIVE_LANE + 72 * t + off, bytes(raw))

    def call(self, entry, slot, detents, value):
        uc = self.uc
        sp = STACK - 0x100
        uc.mem_write(sp, struct.pack(">Iiii", STOP, slot, detents, value))
        uc.reg_write(UC_M68K_REG_SR, 0x2000)   # supervisor first: SR selects the stack pointer
        uc.reg_write(UC_M68K_REG_A7, sp)
        for reg, val in ((UC_M68K_REG_D2, 0x22222222), (UC_M68K_REG_D3, 0x33333333),
                         (UC_M68K_REG_D4, 0x44444444)):
            uc.reg_write(reg, val)
        uc.emu_start(CODE + self.syms[entry], STOP, count=20000)
        if uc.reg_read(UC_M68K_REG_PC) != STOP:
            die(f"{entry} did not return")
        saved = (uc.reg_read(UC_M68K_REG_D2), uc.reg_read(UC_M68K_REG_D3), uc.reg_read(UC_M68K_REG_D4))
        if saved != (0x22222222, 0x33333333, 0x44444444) or uc.reg_read(UC_M68K_REG_A7) != sp + 4:
            die(f"{entry} clobbered d2-d4 or the stack")
        return struct.unpack(">i", struct.pack(">I", uc.reg_read(UC_M68K_REG_D0)))[0]


def walk(m, entry, slot, table):
    """FUNC held: up from 0 and down from 127, one detent at a time."""
    up, v = [0], 0
    for _ in range(len(table) + 1):
        v = m.call(entry, slot, 1, v)
        up.append(v)
    down, v = [127], 127
    for _ in range(len(table) + 1):
        v = m.call(entry, slot, -1, v)
        down.append(v)
    want_up = table + [127, 127]
    want_down = table[::-1] + [0, 0]
    return up == want_up, down == want_down, up, down


def nearest_dir(table, v, d):
    above = [s for s in table if s > v]
    below = [s for s in table if s < v]
    if d > 0:
        return above[0] if above else v
    return below[-1] if below else v


def main():
    if not SRC.exists():
        die(f"{SRC} missing")
    code, syms = assemble()
    m = Machine(code, syms)

    # 1. FUNC held: each table, both directions, between-stop values, multi-detent turns.
    m.state(func=True)
    for entry, (slot, table) in TABLES.items():
        ok_up, ok_dn, up, dn = walk(m, entry, slot, table)
        check(f"{entry}: FUNC walks {table} up and down", ok_up and ok_dn,
              "" if ok_up and ok_dn else f"up {up} down {dn}")
        bad = [(v, d) for v in range(128) for d in (1, -1)
               if m.call(entry, slot, d, v) != nearest_dir(table, v, d)]
        check(f"{entry}: every value moves to the next stop in the turn's direction", not bad,
              f"{len(bad)} wrong, first {bad[:3]}" if bad else "")
        bad = []
        for v in (0, 50, 127):
            for d in (2, 3, -2, -3):
                single = v
                for _ in range(abs(d)):
                    single = nearest_dir(table, single, d)
                got = m.call(entry, slot, d, v)
                if got != single:
                    bad.append((v, d, got, single))
        check(f"{entry}: a {{2,3}}-detent turn equals single steps", not bad, str(bad[:2]) if bad else "")
        check(f"{entry}: zero detents leave the value", m.call(entry, slot, 0, 50) == 50)

    # 2. FUNC not held: one unit a detent, x7 on the entry's own push only; PERSONALIZE off.
    for entry, (slot, table) in TABLES.items():
        enc = slot
        m.state(func=False)
        plain = [m.call(entry, slot, d, 60) for d in (1, -1, 3)]
        m.state(func=False, pushed=enc)
        pushed = [m.call(entry, slot, d, 60) for d in (1, -1, 2)]
        m.state(func=False, pushed=(enc + 1) % 6)
        other = m.call(entry, slot, 1, 60)
        m.state(func=True, enc_off=True)
        off = m.call(entry, slot, 1, 60)
        check(f"{entry}: plain +1/-1/+3 -> {plain}; own push x7 -> {pushed}; another push and "
              f"PERSONALIZE-off FUNC plain",
              plain == [61, 59, 63] and pushed == [67, 53, 74] and other == 61 and off == 61,
              f"other push {other}, FUNC with FUNCTION+ENCODER off {off}")

    if FAILS:
        die(f"{FAILS} check(s) failed")
    print("verify_vibrato_knobs: OK")


if __name__ == "__main__":
    main()
