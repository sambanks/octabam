from unicorn import *; from unicorn.m68k_const import *
D = [UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7]
def run(op, ext, regs, macsr=0x20, presep=False):
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN); uc.mem_map(0x1000, 0x1000)
    code = b"\xa9\x3c" + macsr.to_bytes(4, "big") + (b"\x4e\x71" if presep else b"") + op.to_bytes(2, "big") + ext.to_bytes(2, "big") + b"\xa1\xc2" + b"\x4e\x71"
    uc.mem_write(0x1000, code)
    for i, v in regs.items(): uc.reg_write(D[i], v & 0xffffffff)
    uc.emu_start(0x1000, 0x1000 + len(code))
    return uc.reg_read(UC_M68K_REG_D2) & 0xffffffff
def enc(rx, ry, msac): return 0xA000 | (rx << 9) | ry, 0x0800 | (0x100 if msac else 0)
def hw(a, b, msac):
    p = (a * b) >> 31
    return (-p if msac else p) & 0xffffffff
cases = [("d0*d1 pos, mac", 0, 1, False, 0xc00, 0x200000), ("d0*d1 pos, msac", 0, 1, True, 0xc00, 0x200000),
         ("d1*d5 pos, mac", 5, 1, False, 48768, 699050), ("d1*d5 pos, msac", 5, 1, True, 48768, 699050),
         ("d1*d5 -384*-699050 mac", 5, 1, False, -384, -699050), ("d1*d5 -384*-699050 msac", 5, 1, True, -384, -699050),
         ("d0*d1 -384*-699050 mac", 1, 0, False, -384, -699050), ("d0*d1 -384*+699050 mac", 1, 0, False, -384, 699050),
         ("d0*d1 48768*-699050 mac", 1, 0, False, 48768, -699050)]
for name, rx, ry, msac, a, b in cases:
    op, ext = enc(rx, ry, msac)
    regs = {ry: a, rx: b}
    print(f"{name:28s} op={op:#06x} ext={ext:#06x}: emu={run(op, ext, regs):#x} emu(nop sep)={run(op, ext, regs, presep=True):#x} hw={hw(a, b, msac):#x}")
