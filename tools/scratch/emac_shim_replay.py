from unicorn import *; from unicorn.m68k_const import *
import sys, os; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path); import emu_bringup as eb
MACSR = b"\xa9\x3c\x00\x00\x00\x20"
uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN); uc.mem_map(0x1000, 0x2000); uc.mem_map(0, 0x1000)
class R: trap = None; emac_shims = 0
r = R()
def on_intr(u, intno, user):
    r.trap = (intno, None); u.emu_stop()
uc.hook_add(UC_HOOK_INTR, on_intr)
code = (MACSR + b"\x92\x84" + b"\xa4\x98\x59\x01" + b"\x94\x84" + b"\xa2\x18\x59\x02" + b"\xa1\xc2" + b"\xa3\xc3" + b"\x4e\x71")
uc.mem_write(0x1000, code)
ev = 0x3c9be80
uc.mem_write(0x2000, ev.to_bytes(4, "big") * 4)
uc.reg_write(UC_M68K_REG_D1, ev); uc.reg_write(UC_M68K_REG_D4, 0x3c84000); uc.reg_write(UC_M68K_REG_D5, 0xfff55556); uc.reg_write(UC_M68K_REG_A0, 0x2000)
end = 0x1000 + len(code); pc = 0x1000
for expect_trap_pc in (0x1008, 0x100e):
    r.trap = None
    uc.emu_start(pc, end)
    print("stopped at", hex(uc.reg_read(UC_M68K_REG_PC)), "trap", r.trap)
    r.trap = (4, expect_trap_pc)
    pc = eb._emac_load_shim(uc, r)
    print("  resume", hex(pc), "d1", hex(uc.reg_read(UC_M68K_REG_D1)), "d2", hex(uc.reg_read(UC_M68K_REG_D2)))
uc.emu_start(pc, end)
print("d2 (acc0) =", hex(uc.reg_read(UC_M68K_REG_D2) & 0xffffffff), "d3 (acc1) =", hex(uc.reg_read(UC_M68K_REG_D3) & 0xffffffff), "want 0x1f 0x1f")
