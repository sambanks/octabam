import sys; sys.path.insert(0, "tools")
import emu_bringup as emu
from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.m68k_const import UC_M68K_REG_PC, UC_M68K_REG_A7, UC_M68K_REG_D0
EDIT = 0x4003a474; KNOB_ARR, SEL_ARR = 0x8ef5a, 0x8f04a; TRACK = 4; STUB = 0x4003249c
r = emu.boot("out/mainos_bus.bin"); uc = r.uc; assert r.clean
for base in (0x100a0000, 0x100f0000): uc.mem_map(base, 0x10000)
stores = []
uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc,a,addr,sz,v,u: stores.append((addr, sz, v)))
def on_code(uc, addr, size, u):
    if addr == STUB:
        sp = uc.reg_read(UC_M68K_REG_A7); ret = int.from_bytes(uc.mem_read(sp, 4), "big")
        uc.reg_write(UC_M68K_REG_A7, sp + 4); uc.reg_write(UC_M68K_REG_D0, 0); uc.reg_write(UC_M68K_REG_PC, ret)
uc.hook_add(UC_HOOK_CODE, on_code, begin=STUB, end=STUB+2)
def call(addr, args, budget=3_000_000):
    sp = emu.CALL_SP - 4*len(args); uc.reg_write(UC_M68K_REG_A7, sp)
    uc.mem_write(sp, emu.CALL_RET.to_bytes(4, "big"))
    for i,a in enumerate(args): uc.mem_write(sp+4+4*i, (a & 0xffffffff).to_bytes(4, "big"))
    uc.emu_start(addr, emu.CALL_RET, count=budget)
    return uc.reg_read(UC_M68K_REG_PC) == emu.CALL_RET
def part_stores(): return sorted((a - emu.FAKE_PART, v) for a, sz, v in stores if emu.FAKE_PART <= a < emu.FAKE_PART + 0x100000 and KNOB_ARR <= a - emu.FAKE_PART < SEL_ARR + 240)
emu.assign_fx2(r, track=TRACK, effect_id=7)
CANDS = (0x460c80f0, 0x460d5c30, 0x460e762c, 0x46c7de5e)
saved = {c: bytes(uc.mem_read(c, 4)) for c in CANDS}
print("candidate values:", {hex(c): int.from_bytes(v, "big") for c, v in saved.items()})
page_global = None
for c in CANDS:
    for cc in CANDS: uc.mem_write(cc, saved[cc])
    uc.mem_write(c, (4).to_bytes(4, "big")); stores.clear()
    ok = call(EDIT, (2, 3))
    ps = part_stores()
    print(f"set {hex(c)}=4 -> returned={ok} knob-array stores {[(hex(o), v) for o, v in ps]}")
    if any(o == KNOB_ARR + TRACK*30 + 4*6 + 2 for o, v in ps): page_global = c
for cc in CANDS: uc.mem_write(cc, saved[cc])
print("PAGE GLOBAL:", hex(page_global) if page_global else None)
if page_global:
    for eid, label in ((7, "BusVerb"), (6, "BusDelay")):
        emu.assign_fx2(r, track=TRACK, effect_id=eid); uc.mem_write(page_global, (4).to_bytes(4, "big"))
        print(f"=== {label}: seed 5, delta +3 ===")
        for slot in range(6):
            k = emu.FAKE_PART + KNOB_ARR + TRACK*30 + 4*6 + slot
            uc.mem_write(k, bytes([5])); stores.clear()
            ok = call(EDIT, (slot, 3))
            live = [(hex(a), v) for a, sz, v in stores if 0x80000800 <= a < 0x80001000]
            print(f"slot {6+slot}: returned={ok} knob 5->{uc.mem_read(k,1)[0]}  part stores {[(hex(o), v) for o, v in part_stores()]}  live {live}")
