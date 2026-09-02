#!/usr/bin/env python3
"""Tier-0 ColdFire bring-up harness (PLAN.md §5, the remixer emu).

Boots a MAIN OS image on Unicorn's ColdFire V4e core, modelling only as much
of the hardware as the boot path actually touches, and stops at the RTOS
multitasking handoff (`trap #0`). It is a LIMITED emulator: no display, no
real peripherals, no scheduler. Two uses:

  * as a CLI, `tools/emu_bringup.py [image]` prints the boot outcome + map;
  * as a library, `boot(image)` returns a warm machine and `read_menu_tree`
    walks the MAIN MENU tables out of its RAM — so the remix TUI can boot a
    freshly built image and show that it boots clean and that a patched-in
    menu entry (docs/MAINMENU.md) actually resolves.

Needs `unicorn` with the CFV4E model — `make emu-setup` provisions it into
the uv-managed `.venv` (the `emu` extra). The DEFAULT m68k core is plain-68k
and will NOT decode this CPU (mvz/mvs/EMAC) — see docs/EXTERNAL.md. Boot
details and the fork past the trap: docs/EMU.md.
"""
import collections
import os
import re
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

# The universal "draw string at (x,y)" primitive (docs/EMU.md). cdecl, args on
# the stack at callee entry: sp@(0)=return, then font/canvas/x/y/count/str.
DRAW_STRING = 0x40012bd8

# Live-screen detour (docs/EMU.md): open the MAIN MENU window, dispatch its
# draw, and capture every string it emits. These run in task context normally;
# we call them directly against the warm (post-boot) machine.
MENU_OPEN = 0x40064c18       # allocates the menu window from the heap
MENU_DRAW = 0x40064d7c       # dispatches the current menu-state's draw
MENU_STATE = 0x400cbf40      # menu state index (1 = the tree)
MENU_VIEWPORT = 0x400cbd9c   # visible-row clamp; 0 in a cold detour -> no rows
MENU_SELROW = 0x400cbd98     # selected row in the current list (the cursor)
MENU_ROWS = 0x400cbda4       # current display list: rows pointer
MENU_COUNT = 0x400cbda0      # current display list: row count
MENU_FOCUS = 0x400cbda8      # focus descriptor
CALL_SP = 0x47f00000         # scratch stack for a detour call
CALL_RET = 0x000000f0        # sentinel return address a detour stops at

# EFFECT 1 / EFFECT 2 SETUP window openers (docs/MAINMENU.md §7) — the chooser
# + dials. FX1 is page_kind 3 (id byte +0x8ed80); our inserts are all FX2, so
# FX1 shows the stock effects (FILTER, etc.).
FX1_SETUP = 0x40059afc
FX2_SETUP = 0x4005996c
PAGE_STAGE = 0x400554e0      # FUN_400554e0(kind): stage a page kind
TRACK_DRAW = 0x4004d948      # redraw the track screen (playback page)
CUR_TRACK_B = 0x80000000     # current audio track (byte); UI mirror 0x100b14cc

# Assigning an effect to a track's FX2 slot so its real param page resolves
# (docs/EMU.md, the FX-page research). The project DB pointer at 0x46c82456 is
# null on our boot (no project loaded), so we point it at a zeroed scratch Part
# and write the id byte the resolver reads.
PART_PTR = 0x46c82456        # -> project database base (null until we fake it)
PART_STRIDE = 0x18b2         # per-pattern
FX2_ID_OFF = 0x8ed88         # + PAT*stride + track  -> FX2 effect-id byte
FX1_ID_OFF = 0x8ed80         # FX1 effect-id byte (inserts are all FX2, though)
PARAM_VAL_OFF = 0x8f084      # + PAT*stride + track*30 + slot -> displayed value
MACHINE_OFF = 0x8eda2        # + PAT*stride + track -> playback machine type
FAKE_PART = 0x50000000       # where we map the scratch Part
PAT_R = 0x100b14cf           # current PART (resolver mirror) -- named "PAT" historically;
PAT_W = 0x80000003           # current PART (window/drawer mirror). Both are the part the
                             # current pattern (0x80000004) links to; docs/EXTERNAL.md §6.


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


def boot(image=None, count=BUDGET, on_draw=None):
    """Boot an image to the RTOS handoff. Returns a BootResult.

    on_draw(x, y, str): if given, a hook at the string primitive DRAW_STRING
    reports every text draw as it happens — the screen-capture path.
    """
    r = BootResult()
    if not HAVE_UNICORN:
        r.stopped = "unicorn not installed — run: make emu-setup"
        return r
    img = open(image or STOCK_IMAGE, "rb").read()

    mu = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    mu.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)

    if on_draw is not None:
        def _draw_hook(uc, address, size, user):
            sp = uc.reg_read(UC_M68K_REG_A7)
            try:
                x = int.from_bytes(uc.mem_read(sp + 12, 4), "big")
                y = int.from_bytes(uc.mem_read(sp + 16, 4), "big")
                sptr = int.from_bytes(uc.mem_read(sp + 24, 4), "big")
            except UcError:
                return
            on_draw(x, y, _cstr(uc, sptr))
        mu.hook_add(UC_HOOK_CODE, _draw_hook, begin=DRAW_STRING, end=DRAW_STRING)
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


def _call(uc, addr, args=(), count=20_000_000):
    """Invoke a firmware function on a warm machine and run until it returns.

    Sets a scratch stack with a sentinel return address (and cdecl args above
    it) and executes until the function's rts pops it back. Faults propagate
    as UcError.
    """
    sp = CALL_SP - 4 * len(args)
    uc.reg_write(UC_M68K_REG_A7, sp)
    uc.mem_write(sp, CALL_RET.to_bytes(4, "big"))
    for i, a in enumerate(args):
        uc.mem_write(sp + 4 + 4 * i, (a & 0xFFFFFFFF).to_bytes(4, "big"))
    uc.reg_write(UC_M68K_REG_SR, 0x2700)
    uc.emu_start(addr, CALL_RET, count=count)


def _prime_menu(r):
    """One-time setup so a warm machine can redraw the MAIN MENU on demand:
    install the string-capture + fault-survival hooks, flush the JIT cache
    (draw fns were cached during boot WITHOUT the hooks), and open the window.
    """
    uc = r.uc
    r._draws = []

    def draw_hook(u, address, size, user):
        sp = u.reg_read(UC_M68K_REG_A7)
        try:
            x = int.from_bytes(u.mem_read(sp + 12, 4), "big")
            y = int.from_bytes(u.mem_read(sp + 16, 4), "big")
            sptr = int.from_bytes(u.mem_read(sp + 24, 4), "big")
        except UcError:
            return
        t = _cstr(u, sptr)
        if t:
            r._draws.append((x, y, t))

    def on_unmapped(u, access, addr, size, val, user):
        # A cold detour skips some normal setup, so a formatter may hold a
        # stale pointer; map a zero page so its strlen reads "" and the real
        # (valid) row labels still render, instead of faulting the whole draw.
        try:
            u.mem_map(addr & ~0xFFF, 0x1000)
        except UcError:
            pass
        return True

    uc.hook_add(UC_HOOK_CODE, draw_hook, begin=DRAW_STRING, end=DRAW_STRING)
    uc.hook_add(UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED
                | UC_HOOK_MEM_FETCH_UNMAPPED, on_unmapped)
    uc.ctl_flush_tb()
    _open_menu_window(uc)
    # The root descriptor's rows field (0x400cbd8c+0x18) IS the MENU_ROWS
    # global that render repoints, so capture the root list ONCE now — after
    # this, reading the root descriptor gives whatever we last rendered.
    r._root_rows = _u32(uc, MENU_ROOT_DESC + 0x18)
    r._root_count = _u32(uc, MENU_ROOT_DESC)
    r._menu_ready = True


def _open_menu_window(uc):
    """Make the MENU the CURRENT window again.

    ⚠️ Not one-time setup, though it was written as if it were. Rendering an
    FX page (`render_fx2`/`render_fx1`) opens ITS window, and `MENU_DRAW`
    afterwards draws for a window that is no longer the menu's -- it captures
    NOTHING, silently, for the rest of the session. So the main-menu preview
    worked only if it happened to be the first thing rendered, and in the
    remixer it never was: FX2 is the default view. Found 2 Sep 2026 by
    rendering the four views in sequence and counting the draws (12, 26, 0).
    Re-opening is cheap and the round trip works in both directions.
    """
    _call(uc, MENU_OPEN)                     # allocate + set the menu window
    uc.mem_write(MENU_STATE, (1).to_bytes(4, "big"))       # tree state
    uc.mem_write(MENU_VIEWPORT, (6).to_bytes(4, "big"))    # visible rows


def _list_of(r, desc):
    """(rows_ptr, count) for a menu descriptor, using the captured root list
    for the root (whose live fields get repointed by rendering)."""
    if desc == MENU_ROOT_DESC and getattr(r, "_root_rows", None):
        return r._root_rows, r._root_count
    return _u32(r.uc, desc + 0x18), _u32(r.uc, desc)


def menu_children(r, desc=MENU_ROOT_DESC):
    """The rows of a menu descriptor as [(label, child_desc, action)]. A row
    with a non-zero child_desc is a submenu you can descend into."""
    uc = r.uc
    if uc is None:
        return []
    if not getattr(r, "_menu_ready", False) and r.reached_handoff:
        _prime_menu(r)
    rows, count = _list_of(r, desc)
    if not (0 < count < 64) or not (0x40000000 <= rows < 0x40200000):
        return []
    out = []
    for i in range(count):
        row = rows + ROW_STRIDE * i
        label = _cstr(uc, _u32(uc, row + 0x00))
        if label:
            out.append((label, _u32(uc, row + 0x10), _u32(uc, row + 0x08)))
    return out


def render_menu(r, desc=MENU_ROOT_DESC, cursor=0):
    """Point the MAIN MENU display at descriptor `desc`, select `cursor`, and
    capture what the firmware draws, as (x, y, text) — the live screen. The
    root renders two panes (categories + the selected one's children); a
    submenu descriptor renders its items. Re-entrant: first call primes it.
    """
    uc = r.uc
    if uc is None or not r.reached_handoff:
        return []
    def once():
        _open_menu_window(uc)            # an FX render may own the window now
        rows, count = _list_of(r, desc)
        uc.mem_write(MENU_ROWS, rows.to_bytes(4, "big"))
        uc.mem_write(MENU_COUNT, count.to_bytes(4, "big"))
        uc.mem_write(MENU_VIEWPORT, max(count, 6).to_bytes(4, "big"))
        uc.mem_write(MENU_FOCUS, desc.to_bytes(4, "big"))
        uc.mem_write(MENU_SELROW, int(cursor).to_bytes(4, "big"))
        r._draws.clear()
        _call(uc, MENU_DRAW)

    try:
        if not getattr(r, "_menu_ready", False):
            _prime_menu(r)
        once()
        if not r._draws:                 # MENU_OPEN toggles, same as the FX
            once()                       # pages -- see _call_page
    except UcError:
        pass
    return list(r._draws)


def _call_page(uc, entry, draws):
    """Call an FX SETUP entry point and make sure it actually DREW.

    ⚠️ THESE ENTRY POINTS TOGGLE. `FX2_SETUP` opens the page on one call and
    closes it on the next, so consecutive renders alternate 26 draws, 0, 26,
    0 -- and a remixer that re-renders on every keystroke showed an empty
    LCD half the time. Found 2 Sep 2026 by calling render_fx2 four times in
    a row and counting; it reads as "the emulator is broken", which is why
    it survived so long. A second call re-opens it.
    """
    draws.clear()
    _call(uc, entry)
    if not draws:
        _call(uc, entry)


def _prime_part(r):
    """Map a zeroed scratch Part and point the project-DB pointer at it, so the
    FX-page resolvers have somewhere to read the per-track effect id and values.
    The real boot loads a project here; ours (bootstrap-upgrade path) does not.
    """
    uc = r.uc
    if getattr(r, "_part_ready", False):
        return
    uc.mem_map(FAKE_PART, 0x100000)
    uc.mem_write(PART_PTR, FAKE_PART.to_bytes(4, "big"))
    r._part_ready = True


def _part_addr(uc, off, track=4, slot=0, track_stride=1):
    part = int.from_bytes(uc.mem_read(PART_PTR, 4), "big")
    pat = uc.mem_read(PAT_R, 1)[0]
    return part + pat * PART_STRIDE + track * track_stride + slot + off


def assign_fx2(r, track=4, effect_id=0x07):
    """Assign an effect (by FX2 id) to a track so its param page resolves. In
    the BUILT image the id->descriptor table is patched, so 0x07 is ChonVerb,
    0x06 BongDelay, etc. (raw image: those slots are NONE)."""
    uc = r.uc
    _prime_part(r)
    uc.mem_write(CUR_TRACK_B, int(track).to_bytes(1, "big"))
    uc.mem_write(0x100b14cc, int(track).to_bytes(4, "big"))
    uc.mem_write(PAT_W, (0).to_bytes(1, "big"))
    uc.mem_write(PAT_R, (0).to_bytes(1, "big"))
    uc.mem_write(_part_addr(uc, FX2_ID_OFF, track), bytes([effect_id & 0xff]))


def set_fx2_value(r, track, slot, value):
    """Poke a track's FX2 param display value (slot 0..11) — the byte the knob
    drawer reads. Re-render to see it. (Page-2 slots 6..11 have the effect's
    page-2 knobs; the drawer reads them from the same displayed-value array.)"""
    _prime_part(r)
    a = _part_addr(r.uc, PARAM_VAL_OFF, track, slot, track_stride=30)
    r.uc.mem_write(a, bytes([value & 0xff]))


def render_fx2(r, track=4, effect_id=0x07):
    """Detour to EFFECT 2 SETUP for `track` (default 4 = track 5) with
    `effect_id` assigned, and capture what it draws — the chooser plus the
    effect's REAL parameter knobs (e.g. ChonVerb's SHMR/MODE/DIFF/SHFT/GATE/
    RATE). effect_id None leaves whatever is assigned.
    """
    uc = r.uc
    if uc is None or not r.reached_handoff:
        return []
    if not getattr(r, "_menu_ready", False):
        _prime_menu(r)          # installs the capture + fault-survival hooks
    try:
        if effect_id is not None:
            assign_fx2(r, track, effect_id)
        _call_page(uc, FX2_SETUP, r._draws)
    except UcError:
        pass
    return list(r._draws)


def render_playback(r, track=4, machine=1):
    """Render the PLAYBACK page (page_kind 0) with a sample machine assigned —
    the sample-loaded track view (LEV/PTCH/STRT/LEN/RATE). `machine` indexes
    the machine-type table: 0/1 = FLEX/STATIC (sample players), higher = THRU/
    NEIGHBOR (input/routing). Stages the page then redraws the track screen.
    """
    uc = r.uc
    if uc is None or not r.reached_handoff:
        return []
    if not getattr(r, "_menu_ready", False):
        _prime_menu(r)
    try:
        _prime_part(r)
        uc.mem_write(CUR_TRACK_B, int(track).to_bytes(1, "big"))
        uc.mem_write(0x100b14cc, int(track).to_bytes(4, "big"))
        uc.mem_write(PAT_W, (0).to_bytes(1, "big"))
        uc.mem_write(PAT_R, (0).to_bytes(1, "big"))
        uc.mem_write(_part_addr(uc, MACHINE_OFF, track), bytes([machine & 0xff]))
        _call(uc, PAGE_STAGE, (0,))          # stage page_kind 0 (playback)
        r._draws.clear()
        _call(uc, TRACK_DRAW)
    except UcError:
        pass
    return list(r._draws)


def render_fx1(r, track=4, effect_id=0x04):
    """Detour to EFFECT 1 SETUP for `track` with `effect_id` assigned (FX1 id
    byte +0x8ed80, table 0x400d5f58 — stock effects; 0x04 = FILTER). Same shape
    as render_fx2. effect_id None leaves whatever is assigned."""
    uc = r.uc
    if uc is None or not r.reached_handoff:
        return []
    if not getattr(r, "_menu_ready", False):
        _prime_menu(r)
    try:
        if effect_id is not None:
            _prime_part(r)
            uc.mem_write(CUR_TRACK_B, int(track).to_bytes(1, "big"))
            uc.mem_write(0x100b14cc, int(track).to_bytes(4, "big"))
            uc.mem_write(PAT_W, (0).to_bytes(1, "big"))
            uc.mem_write(PAT_R, (0).to_bytes(1, "big"))
            uc.mem_write(_part_addr(uc, FX1_ID_OFF, track),
                         bytes([effect_id & 0xff]))
        _call_page(uc, FX1_SETUP, r._draws)
    except UcError:
        pass
    return list(r._draws)


# The PART window's own text, which the FX pages drag in with them. Its
# coordinates belong to a DIFFERENT window's space, so it lands in the middle
# of the effect list and fuses with it -- "DJ EQUALIZER1" is `DJ EQUALIZER`
# plus the trailing 1 of `Pt:1 PART 1`. It is real, and it is not this page,
# so it comes out as a caption instead of a row (see part_label).
_PART = re.compile(r"^Pt:\d")


def _clean(draws):
    """Deduped, blank-free, this-window-only draws.

    The capture holds each string once per call and the page functions are
    re-issued when nothing came back, so exact duplicates are routine.
    """
    seen, out = set(), []
    for x, y, t in draws:
        if not t.strip() or not (0 <= x <= 128 and 0 <= y <= 64):
            continue
        if _PART.match(t) or (x, y, t) in seen:
            continue
        seen.add((x, y, t))
        out.append((x, y, t))
    return out


def part_label(draws):
    """The PART window's caption, if this capture dragged one in."""
    for _x, _y, t in draws:
        if _PART.match(t):
            return " ".join(t.split())
    return None


# ---- the LCD's own geometry, MEASURED (3 Sep 2026) -------------------------
# A character cell is FOUR pixels wide, so the 128 px screen is 32 characters,
# not the 42 this used to assume. The measurement is exact and falls out of
# the capture: the same column drawn with labels of different length starts at
# a different x, and the shift is 2 px per character -- i.e. the firmware
# CENTRES each label on a fixed anchor.
#
#   page-2 col 1   '12dB' x=55   'LOW' x=57   'HP' x=59   -> centre 63
#   page-1 col 1   'BASE' x=62   'ATK' x=64   'FB' x=66   -> centre 70
#   page-2 col 2   'NONE' x=75   'NUM' x=77   'LP' x=79   'Q' x=81  -> 83
#   page-1 col 2   'WDTH' x=82   'GN1' x=84                         -> 90
#   page-2 col 3   'BASE' x=95   'ENV' x=97                         -> 103
#   page-1 col 3   'RTIM' x=102  'MIX' x=104  'Q1' x=106  'Q' x=108 -> 110
#
# Three parameter columns, each drawn twice 7 px apart (the page-1 name above
# its dial, the page-2 name and value beside it). At 4 px per character that
# 7 px is under two characters, so preserving it buys a ragged indent and
# nothing else -- the columns are SNAPPED to one anchor per column instead,
# which is the whole point of a column.
CELL = 4                                  # px per character
COLS = 128 // CELL
LEFT_X = 40                               # left of this, text is left-aligned
                                          # (the chooser list, the page title)


def _left_aligned(items):
    """The x positions this screen draws text LEFT-aligned at.

    ⚠️ NOT EVERY COLUMN IS CENTRED. The parameter columns are; a LIST is not
    -- the MAIN MENU's two columns are rows of different lengths sharing one
    left edge, and centre-snapping them shuffled `PROJECT` / `SYSTEM` /
    `CONTROL` / `MIDI` into three different indents.

    The two are told apart by the thing that distinguishes them in the
    capture: a centred column's x SHIFTS with the label's length (2 px per
    character), so one x carries one length. A left-aligned one carries
    several.
    """
    lens = collections.defaultdict(set)
    for x, _y, t in items:
        lens[x].add(len(t))
    return {x for x, seen in lens.items() if len(seen) > 1}


def _anchors(items, left, tol=8):
    """The parameter columns: each centre the firmware centres labels on,
    and the widest label that column carries.

    Clustered out of THIS screen's own draws rather than written down, so a
    page laid out differently gets its own columns instead of these.

    -> [(centre_px, widest)], and the widest is what turns a centred column
    into a LEFT-ALIGNED one: see layout_screen.
    """
    seen = {}
    for x, _y, t in items:
        if x < LEFT_X or x in left:
            continue
        c = x + CELL * len(t) / 2
        seen[c] = max(seen.get(c, 0), len(t))
    groups = []
    for c in sorted(seen):
        if groups and c - groups[-1][-1][0] <= tol:
            groups[-1].append((c, seen[c]))
        else:
            groups.append([(c, seen[c])])
    return [(sum(c for c, _w in g) / len(g), max(w for _c, w in g))
            for g in groups]


def layout_screen(draws, cols=COLS, rows=9):
    """Arrange captured (x,y,text) draws into a text grid. The LCD is 128x64
    with a bottom-left-ish origin (the list drawer steps y DOWN per row, so
    larger y = higher on screen).

    Three rules, and they are the three things the LCD does that a character
    grid does not do by itself:

    ⚠️ PARAMETER COLUMNS ARE FOUND BY CENTRE AND DRAWN LEFT-ALIGNED. The
    firmware centres each label on a fixed anchor, which is how the columns
    are identified at all -- but REPRODUCING the centring is what still read
    as ragged, because a 2-character label centred in a 4-wide column starts
    one column in and its left edge no longer lines up with anything. So
    each column is laid out from the left edge of its WIDEST label, which is
    what a column of text is normally expected to do. A LIST is left-aligned
    already and must not be snapped at all (_left_aligned tells them apart).

    ⚠️ A LATER DRAW OVER THE SAME PIXELS WINS. The firmware repaints a
    parameter row in place, so the capture holds the label that WAS there and
    then the one that is -- `PTCH` then `FRQ1` at the same x. Overlapping
    spans are replaced, or the page shows both and reads as an effect with
    seven parameters where the unit draws four.

    ⚠️ TWO STRINGS THAT DO NOT OVERLAP ARE NEVER FUSED. Writing character by
    character let a label whose cell was taken run into its neighbour, and
    the result is a word that does not exist on the unit -- `DJ EQUALIZER1`,
    `COMPRESSORT 1`.
    """
    items = _clean(draws)
    left = _left_aligned(items)
    cols_px = _anchors(items, left)
    grid = [[] for _ in range(rows)]
    for x, y, t in items:
        cy = min(rows - 1, max(0, (64 - y) * rows // 64))
        if x < LEFT_X or x in left or not cols_px:
            cx = int(x / CELL + 0.5)
        else:
            a, w = min(cols_px,
                       key=lambda c: abs(c[0] - (x + CELL * len(t) / 2)))
            cx = int(a / CELL - w / 2 + 0.5)
        cx = min(cols - 1, max(0, cx))
        row = grid[cy]
        row[:] = [(s0, s1) for s0, s1 in row
                  if s0 + len(s1) <= cx or s0 >= cx + len(t)]
        row.append((cx, t))
    out = []
    for frags in grid:
        row = ""
        for cx, t in sorted(frags):
            at = max(cx, len(row) + 1) if row else cx
            row += " " * (at - len(row)) + t
        out.append(row.rstrip())
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
