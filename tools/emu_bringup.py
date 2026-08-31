#!/usr/bin/env python3
"""Tier-0 ColdFire bring-up harness (PLAN.md §5, the workbench emu).

Boots a MAIN OS image on Unicorn's ColdFire V4e core, modelling only as much
of the hardware as the boot path actually touches, and stops at the RTOS
multitasking handoff (`trap #0`). It is a LIMITED emulator: no display, no
real peripherals, no scheduler. Two uses:

  * as a CLI, `tools/emu_bringup.py [image]` prints the boot outcome + map;
  * as a library, `boot(image)` returns a warm machine and `read_menu_tree`
    walks the MAIN MENU tables out of its RAM — so the remix TUI can boot a
    freshly built image and show that it boots clean and that a patched-in
    menu entry (docs/MAINMENU.md) actually resolves.

Needs `unicorn` with the CFV4E model: `pip install 'unicorn>=2.1'`. The
DEFAULT m68k core is plain-68k and will NOT decode this CPU (mvz/mvs/EMAC) —
see docs/EXTERNAL.md. Boot details and the fork past the trap: docs/EMU.md.
"""
import collections
import os
import sys

try:
    from unicorn import *
    from unicorn.m68k_const import *
    HAVE_UNICORN = True
except ImportError:
    HAVE_UNICORN = False

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK_IMAGE = os.path.join(REPO, "out/raw/section_3_MAIN_OS.bin")
BASE = ENTRY = 0x40000400          # load base = 0x40000000 + 0x400 header
BUDGET = 50_000_000

# Root of the MAIN MENU tree (docs/MAINMENU.md). Address = file offset + BASE.
MENU_ROOT_DESC = 0x400cbd8c
ROW_STRIDE = 0x18


class BootResult:
    def __init__(self):
        self.uc = None
        self.instrs = 0
        self.maxpc = ENTRY
        self.stopped = ""          # human-readable stop reason
        self.trap = None           # (intno, pc) if we stopped at a trap
        self.reached_handoff = False
        self.boot_map = []         # ordered unique (kind, pc, addr, size, val)
        self.auto_pokes = []       # (loop_lo, addr, imm)
        self.error = None          # UcError text, if any

    @property
    def clean(self):
        """Booted through all early init to the RTOS handoff with no fault."""
        return self.reached_handoff and self.error is None


def boot(image=None, count=BUDGET):
    """Boot an image to the RTOS handoff. Returns a BootResult."""
    r = BootResult()
    if not HAVE_UNICORN:
        r.stopped = "unicorn not installed (pip install 'unicorn>=2.1')"
        return r
    img = open(image or STOCK_IMAGE, "rb").read()

    mu = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    mu.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    for a, sz in {
        0x00000000: 0x00010000, 0x40000000: 0x02000000, 0x46000000: 0x02000000,
        0x48000000: 0x00100000, 0x80000000: 0x01000000, 0x100b0000: 0x00010000,
    }.items():
        mu.mem_map(a, sz)
    mu.mem_write(BASE, img)
    # Reset state the (absent) vector preamble would seed. SR BEFORE A7, or the
    # supervisor/user stack banks swap and A7 lands in the wrong one.
    mu.reg_write(UC_M68K_REG_SR, 0x2700)     # supervisor, IRQs masked
    mu.reg_write(UC_M68K_REG_A7, 0x48000000)

    # -- peripheral MMIO: default read all-ones (satisfies wait-until-SET) ----
    OVERRIDES = {
        # Clock/PLL: firmware halts (0x4000fa8c) unless (reg>>24)*12MHz==264MHz,
        # so the top byte must be 22 (0x16). entry 0x40000418, gate 0x4000fa78.
        0xfc0c4000: 0x16000000,
    }
    seen = set()
    def _log(kind, pc, addr, size, val=None):
        key = (kind, pc, addr)
        if key not in seen and len(r.boot_map) < 80:
            seen.add(key); r.boot_map.append((kind, pc, addr, size, val))

    def periph_read(uc, off, size, b):
        a = b + off
        _log("R", uc.reg_read(UC_M68K_REG_PC), a, size)
        return OVERRIDES.get(a, (1 << (size * 8)) - 1)

    def periph_write(uc, off, size, val, b):
        _log("W", uc.reg_read(UC_M68K_REG_PC), b + off, size, val)

    for a, sz in {0xfc000000: 0x100000, 0x20000000: 0x1000,
                  0x90000000: 0x1000}.items():
        mu.mmio_map(a, sz,
                    (lambda u, o, s, d, base=a: periph_read(u, o, s, base)), None,
                    (lambda u, o, s, v, d, base=a: periph_write(u, o, s, v, base)),
                    None)

    # -- auto-satisfy async completion-flag spins ---------------------------
    # Given a PC anywhere in a stalled loop, find the `move.w (abs),d0 ; ... ;
    # cmpi.[wl] #imm,d0` pair by scanning a window around it, then write imm to
    # the flag at the LOAD width (move.w, 2 bytes — not the cmpi width, or the
    # low word reads back wrong). Fakes the completion an ISR/other core signals.
    def try_auto_poke(pc_in_loop):
        win_lo = pc_in_loop - 16
        blk = mu.mem_read(win_lo, 48)
        for i in range(0, len(blk) - 6, 2):
            if blk[i:i+2] == b"\x30\x38":             # move.w (abs).w,d0
                addr = int.from_bytes(blk[i+2:i+4], "big", signed=True) & 0xFFFFFFFF
                k = i + 4
            elif blk[i:i+2] == b"\x30\x39":           # move.w (abs).l,d0
                addr = int.from_bytes(blk[i+2:i+6], "big"); k = i + 6
            else:
                continue
            imm = None
            j = k
            while j < min(i + 20, len(blk) - 2):
                if blk[j:j+2] == b"\x0c\x80":         # cmpi.l #imm,d0
                    imm = int.from_bytes(blk[j+2:j+6], "big"); break
                if blk[j:j+2] == b"\x0c\x40":         # cmpi.w #imm,d0
                    imm = int.from_bytes(blk[j+2:j+4], "big"); break
                j += 2
            if imm is None:
                continue
            try:
                mu.mem_write(addr, (imm & 0xFFFF).to_bytes(2, "big"))
            except UcError:
                return False
            r.auto_pokes.append((win_lo + i, addr, imm))
            return True
        return False

    def on_intr(uc, intno, user):
        # trap #0 (intno 32) is the RTOS handoff. Unicorn's CFV4E won't
        # dispatch it (VBR is a no-op); we record and stop. VBR would come
        # from [0x400b9668] (set at 0x40000db6) for a manual dispatcher.
        r.trap = (intno, uc.reg_read(UC_M68K_REG_PC))
        if intno == 32:
            r.reached_handoff = True
        uc.emu_stop()
    mu.hook_add(UC_HOOK_INTR, on_intr)

    # Event-driven write counter: fires only on stores, so a pure poll spin
    # costs nothing, but a memset climbs it. Tells a bounded loop apart from a
    # flag-poll when a stall is suspected.
    st = {"wc": 0}
    mu.hook_add(UC_HOOK_MEM_WRITE,
                lambda u, ac, ad, sz, v, x: st.update(wc=st["wc"] + 1))

    # -- burst execution ----------------------------------------------------
    # A per-instruction Python hook over ~7M instructions costs ~16s; native
    # execution in bursts is ~10x faster. We only turn on an instruction hook
    # BRIEFLY, to pin a loop's exact bounds, once a stall is suspected — a PC
    # confined to a small window across several bursts. A bounded loop
    # (memset) escapes the window within a burst or two; a poll never does.
    BURST = 500_000
    STALL_BURSTS = 4
    stop = {"stuck": None}
    pc = ENTRY
    window = collections.deque(maxlen=STALL_BURSTS)   # (pc, wc) per burst

    while r.instrs < count:
        try:
            mu.emu_start(pc, 0, count=BURST)
        except UcError as e:
            r.error = str(e); break
        if r.trap:
            break
        pc = mu.reg_read(UC_M68K_REG_PC)
        r.instrs += BURST
        if 0x40000000 < pc < 0x40200000 and pc > r.maxpc:
            r.maxpc = pc
        window.append((pc, st["wc"]))
        pcs = [w[0] for w in window]
        if len(window) == STALL_BURSTS and max(pcs) - min(pcs) <= 64:
            writes = window[-1][1] - window[0][1]
            if writes > 2000:
                window.clear()               # a memset making progress, not a spin
            elif try_auto_poke(pc):
                window.clear()
            else:
                stop["stuck"] = (pc, pc); break

    r.uc = mu
    if r.trap:
        r.stopped = (f"trap #{r.trap[0]-32} at 0x{r.trap[1]:08x} "
                     "(RTOS handoff)")
    elif r.error:
        r.stopped = f"fault: {r.error}"
    elif stop["stuck"]:
        r.stopped = (f"unrecognised spin "
                     f"0x{stop['stuck'][0]:08x}..0x{stop['stuck'][1]:08x}")
    else:
        r.stopped = "instruction cap reached (no handoff)"
    return r


def _cstr(uc, addr, limit=40):
    if not addr or addr < 0x40000000:
        return ""
    try:
        raw = uc.mem_read(addr, limit)
    except Exception:
        return ""
    end = raw.find(b"\x00")
    s = (raw[:end] if end >= 0 else raw)
    # menu separator rows are runs of glyph 0x17
    return "".join(chr(b) if 32 <= b < 127 else "" for b in s)


def _u32(uc, addr):
    return int.from_bytes(uc.mem_read(addr, 4), "big")


def read_menu_tree(uc, desc=MENU_ROOT_DESC, depth=0, _seen=None):
    """Walk the MAIN MENU tree out of booted RAM (docs/MAINMENU.md).

    Returns a list of {name, action, page_id, children} dicts. A patched-in
    entry appears here exactly as the firmware would resolve it.
    """
    if _seen is None:
        _seen = set()
    if desc in _seen or depth > 4:
        return []
    _seen.add(desc)
    count = _u32(uc, desc)
    rows = _u32(uc, desc + 0x18)
    if not (0x40000000 <= rows < 0x40200000) or not (0 < count < 64):
        return []
    out = []
    for i in range(count):
        row = rows + ROW_STRIDE * i
        label = _cstr(uc, _u32(uc, row + 0x00))
        action = _u32(uc, row + 0x08)
        child = _u32(uc, row + 0x10)
        page_id = _u32(uc, row + 0x14)
        if not label:
            continue                      # separator / empty
        node = {"name": label, "action": action, "page_id": page_id,
                "children": read_menu_tree(uc, child, depth + 1, _seen)
                            if child else []}
        out.append(node)
    return out


def _cli():
    img = sys.argv[1] if len(sys.argv) > 1 else None
    r = boot(img)
    print(f"image        : {img or STOCK_IMAGE}")
    print(f"instructions : {r.instrs:,}")
    print(f"max PC       : 0x{r.maxpc:08x}")
    print(f"outcome      : {r.stopped}")
    print(f"clean boot   : {r.clean}")
    print(f"auto-pokes   : {len(r.auto_pokes)}  " +
          ", ".join(f"@0x{a:x}={v:#x}" for _, a, v in r.auto_pokes))
    if r.uc and r.reached_handoff:
        print("\nMAIN MENU (walked from booted RAM):")
        for n in read_menu_tree(r.uc):
            kids = ", ".join(c["name"] for c in n["children"])
            print(f"  {n['name']}" + (f"  -> {kids}" if kids else ""))
    print("\nperipheral boot map (first touch of each register):")
    for k, pc, addr, size, val in r.boot_map:
        v = f" val=0x{val:x}" if k == "W" else ""
        print(f"  {k} 0x{addr:08x} sz{size}{v}   (pc 0x{pc:08x})")


if __name__ == "__main__":
    _cli()
