#!/usr/bin/env python3
"""Tier-0 ColdFire bring-up harness (PLAN.md §5, the workbench).

Boots the real MAIN OS image on Unicorn's ColdFire V4e core, modelling only
as much of the hardware as the boot path actually touches. It is NOT a full
machine emulator: there is no display, no real peripherals, no scheduler yet.
Its job is to prove the CPU core runs the firmware and to MAP what the boot
needs — the console log is that map.

Run:  tools/emu_bringup.py           (needs `unicorn` with the CFV4E model:
      pip install unicorn>=2.1 ; the DEFAULT m68k core is plain-68k and will
      NOT decode this CPU — see docs/EXTERNAL.md on the ColdFire ISA.)

State of the boot, 31 Aug 2026 (docs/EMU.md has the detail):
  * With SP+SR seeded and MMIO modelled, the image executes ~7,000,000
    instructions with zero illegal-instruction faults, through the entire
    early hardware init, and stops at the RTOS multitasking handoff
    (`trap #0` at 0x40000e46). That trap is the Tier-0/Tier-1 boundary.
  * Everything below the trap is modelled here. Reaching the menu code past
    it needs either full RTOS/interrupt emulation or the detour-harness
    approach (call UI functions directly) — a design fork, see docs/EMU.md.
"""
import collections
import os
import sys

try:
    from unicorn import *
    from unicorn.m68k_const import *
except ImportError:
    sys.exit("needs unicorn: pip install 'unicorn>=2.1'")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = open(os.path.join(REPO, "out/raw/section_3_MAIN_OS.bin"), "rb").read()
BASE = ENTRY = 0x40000400          # image load base = 0x40000000 + 0x400 header
BUDGET = 50_000_000

mu = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
mu.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)

# RAM windows (docs/ARCHITECTURE.md §7). The stack top is 0x48000000 and grows
# down into the 0x46000000 region.
for a, sz in {
    0x00000000: 0x00010000, 0x40000000: 0x02000000, 0x46000000: 0x02000000,
    0x48000000: 0x00100000, 0x80000000: 0x01000000, 0x100b0000: 0x00010000,
}.items():
    mu.mem_map(a, sz)
mu.mem_write(BASE, IMG)
# Reset state the vector table would seed. ORDER MATTERS: SR before A7, or the
# supervisor/user stack banks swap and A7 lands in the wrong one.
mu.reg_write(UC_M68K_REG_SR, 0x2700)   # supervisor, IRQs masked
mu.reg_write(UC_M68K_REG_A7, 0x48000000)

# ---- peripheral MMIO model ------------------------------------------------
# Default read = all-ones, which satisfies every "wait until bit SET" poll the
# boot uses (I2C/serial shift-done at 0xfc088000, UART/serial status at
# 0xfc064004, ...). OVERRIDES hold registers whose exact value is load-bearing.
OVERRIDES = {
    # Clock/PLL config. The firmware computes sysclk = (reg>>24)*12MHz and
    # HALTS (`bra *` at 0x4000fa8c) unless it equals 264MHz, so the top byte
    # must be 22 (0x16). Entry reads it at 0x40000418; gate at 0x4000fa78.
    0xfc0c4000: 0x16000000,
}
events = []          # ordered unique (kind, pc, addr[, val]) for the boot map
seen = set()
def _log(kind, pc, addr, size, val=None):
    key = (kind, pc, addr)
    if key not in seen and len(events) < 80:
        seen.add(key); events.append((kind, pc, addr, size, val))

def periph_read(uc, off, size, b):
    a = b + off
    _log("R", uc.reg_read(UC_M68K_REG_PC), a, size)
    if a in OVERRIDES:
        return OVERRIDES[a]
    return (1 << (size * 8)) - 1

def periph_write(uc, off, size, val, b):
    _log("W", uc.reg_read(UC_M68K_REG_PC), b + off, size, val)

for a, sz in {0xfc000000: 0x100000, 0x20000000: 0x1000, 0x90000000: 0x1000}.items():
    mu.mmio_map(a, sz,
                (lambda u, o, s, d, base=a: periph_read(u, o, s, base)), None,
                (lambda u, o, s, v, d, base=a: periph_write(u, o, s, v, base)), None)

# ---- auto-satisfy async completion-flag spins -----------------------------
# Boot polls flags an ISR / the other DSP core would set:
#   `move.w (abs),d0 ; [mvz] ; cmpi.[wl] #imm,d0 ; bne self`
# (word@0 and word@0x2000 == 0xffff observed). A watchdog spots the spin, then
# we decode the read address + compared immediate and write it, faking the
# completion. The write width matches the LOAD (move.w), not the cmpi.
auto_pokes = []
def try_auto_poke(lo, hi):
    blk = mu.mem_read(lo, min(hi - lo + 8, 32))
    if blk[0:2] == b"\x30\x38":                       # move.w (abs).w,d0
        addr = int.from_bytes(blk[2:4], "big", signed=True) & 0xFFFFFFFF; j = 4
    elif blk[0:2] == b"\x30\x39":                     # move.w (abs).l,d0
        addr = int.from_bytes(blk[2:6], "big"); j = 6
    else:
        return False
    imm = None
    while j < len(blk) - 2:
        op = blk[j:j+2]
        if op == b"\x0c\x80":                          # cmpi.l #imm,d0
            imm = int.from_bytes(blk[j+2:j+6], "big"); break
        if op == b"\x0c\x40":                          # cmpi.w #imm,d0
            imm = int.from_bytes(blk[j+2:j+4], "big"); break
        j += 2
    if imm is None:
        return False
    try:
        mu.mem_write(addr, (imm & 0xFFFF).to_bytes(2, "big"))   # load is move.w
    except UcError:
        return False
    auto_pokes.append((lo, addr, imm))
    return True

# ---- watchdog: tell a real spin from a long bounded loop -------------------
# A memset/memcpy writes to advancing addresses and exits; a poll does not.
# Track a write COUNTER and require it to climb, or the window is a spin.
st = {"n": 0, "maxpc": ENTRY, "wc": 0, "stuck": None, "trap": None}
mu.hook_add(UC_HOOK_MEM_WRITE, lambda u, ac, ad, sz, v, x: st.update(wc=st["wc"] + 1))
recent = collections.deque(maxlen=16)
wd = {"win": None, "since": 0, "wc_mark": 0}
def hook_code(uc, address, size, user):
    st["n"] += 1
    recent.append(address)
    if 0x40000000 < address < 0x40200000 and address > st["maxpc"]:
        st["maxpc"] = address
    lo, hi = min(recent), max(recent)
    if hi - lo <= 40 and len(recent) == 16:
        if wd["win"] == (lo, hi):
            wd["since"] += 1
            if wd["since"] % 4096 == 0:
                if st["wc"] - wd["wc_mark"] > 64:      # writes climbing => progress
                    wd["since"] = 0
                wd["wc_mark"] = st["wc"]
            if wd["since"] > 300_000:
                if try_auto_poke(lo, hi):
                    wd["win"] = None; wd["since"] = 0; recent.clear()
                else:
                    st["stuck"] = (lo, hi); uc.emu_stop()
        else:
            wd["win"] = (lo, hi); wd["since"] = 0; wd["wc_mark"] = st["wc"]
    else:
        wd["win"] = None; wd["since"] = 0
mu.hook_add(UC_HOOK_CODE, hook_code)

def on_intr(uc, intno, user):
    # trap #n => exception vector 32+n. Unicorn's CFV4E treats VBR as a no-op,
    # so it will not dispatch: we record and stop. trap #0 (intno 32) is the
    # RTOS scheduler handoff; VBR is loaded from [0x400b9668] at 0x40000db6.
    st["trap"] = (intno, uc.reg_read(UC_M68K_REG_PC)); uc.emu_stop()
mu.hook_add(UC_HOOK_INTR, on_intr)

try:
    mu.emu_start(ENTRY, 0, count=BUDGET)
    outcome = "count cap / clean stop"
except UcError as e:
    outcome = f"UcError: {e}"

print(f"instructions : {st['n']:,}")
print(f"max PC       : 0x{st['maxpc']:08x}")
print(f"outcome      : {outcome}")
if st["trap"]:
    intno, pc = st["trap"]
    print(f"TRAP         : #{intno-32} (vector {intno}) at pc=0x{pc:08x}  "
          f"— RTOS handoff, the Tier-0/Tier-1 boundary")
if st["stuck"]:
    print(f"STUCK        : unrecognised spin 0x{st['stuck'][0]:08x}..0x{st['stuck'][1]:08x}")
print(f"auto-pokes   : {len(auto_pokes)}  " +
      ", ".join(f"@0x{a:x}={v:#x}" for _, a, v in auto_pokes))
print("\nperipheral boot map (first touch of each register):")
for ev in events:
    k, pc, addr, size, val = ev
    v = f" val=0x{val:x}" if k == "W" else ""
    print(f"  {k} 0x{addr:08x} sz{size}{v}   (pc 0x{pc:08x})")
